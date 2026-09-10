#!/usr/bin/env python3
"""Extract the real OnPair eval string columns to a compact .bin the CPU bench reads.

Produces ~CAP_BYTES (default 64 MiB) per column into OUT_DIR (default ~/data/onpair-cpu-cols):
  clickbench_url   <- ~/repos/vortex@fsst-bench/cb_urls_10m.txt (real ClickBench URL column)
  l_comment        <- tpch_sf10.duckdb lineitem.l_comment   (TPC-H, mid-cardinality)
  l_shipinstruct   <- tpch_sf10.duckdb lineitem.l_shipinstruct (TPC-H, very low cardinality)
  book_reviews     <- streamed Amazon-Reviews-2023 Books 'text' (high-cardinality natural text)

.bin format (little-endian): u64 n_rows; (n_rows+1) x u32 offsets (offsets[0]=0); then the bytes.
Each box replicates the sample up to ONPAIR_BENCH_MB before compressing (dict is unchanged by
replication), so a small ship covers a memory-bound working set.
"""
import os
import sys
import struct
import json
import csv
import io
import subprocess
from array import array

csv.field_size_limit(sys.maxsize)  # FineWeb/Wikipedia 'text' rows exceed the 131072 default

CAP = int(os.environ.get("CAP_BYTES", str(64 * 1024 * 1024)))
OUT = os.path.expanduser(os.environ.get("OUT_DIR", "~/data/onpair-cpu-cols"))
CB_URLS = os.path.expanduser("~/repos/vortex@fsst-bench/cb_urls_10m.txt")
DB = os.path.expanduser("~/data/benchmark_data/tpch/tpch_sf10.duckdb")
BR_URL = ("https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/"
          "raw/review_categories/Books.jsonl.gz")
os.makedirs(OUT, exist_ok=True)


def write_bin(name, rows):
    offsets = array("I", [0])
    buf = bytearray()
    for r in rows:
        buf += r
        offsets.append(len(buf))
    n = len(offsets) - 1
    with open(os.path.join(OUT, name + ".bin"), "wb") as f:
        f.write(struct.pack("<Q", n))
        f.write(offsets.tobytes())   # u32 LE on this host; boxes are LE too
        f.write(buf)
    print(f"  {name}: {n} rows, {len(buf)/1e6:.0f} MB")


def capped(it):
    total = 0
    for r in it:
        yield r
        total += len(r)
        if total >= CAP:
            return


def from_textfile(path):
    with open(path, "rb") as f:
        for line in f:
            yield line.rstrip(b"\n")


def from_duckdb(table, col, limit):
    p = subprocess.Popen(["duckdb", "-csv", "-noheader", "-readonly", DB,
                          f"SELECT {col} FROM {table} LIMIT {limit}"],
                         stdout=subprocess.PIPE, text=True)
    for row in csv.reader(p.stdout):
        if row:
            yield row[0].encode("utf-8")
    p.stdout.close(); p.wait()


# HF token (used for the McAuley-Lab Amazon jsonl + HF-hosted parquet, which throttle anonymous).
HF_TOKEN = ""
_tok = os.path.expanduser("~/.cache/huggingface/token")
if os.path.exists(_tok):
    HF_TOKEN = open(_tok).read().strip()
# Same Amazon-Reviews-2023 source the GPU eval used (McAuley Lab); 'text' field per review.
AMAZON_JSONL = ("https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/"
                "raw/review_categories/{cat}.jsonl.gz")
# HF-hosted parquet shards (same URLs as the GPU eval's columns.py).
FINEWEB_HF = "HuggingFaceFW/fineweb/sample/10BT/000_00000.parquet"
WIKIPEDIA_HF = "wikimedia/wikipedia/20231101.en/train-00000-of-00041.parquet"


def from_jsonl_gz(url, field="text"):
    curl = subprocess.Popen(["curl", "-sL", "-H", f"Authorization: Bearer {HF_TOKEN}", url],
                            stdout=subprocess.PIPE)
    gz = subprocess.Popen(["gunzip"], stdin=curl.stdout, stdout=subprocess.PIPE)
    jqp = subprocess.Popen(["jq", "-c", f'select(.{field} != null and .{field} != "") | .{field}'],
                           stdin=gz.stdout, stdout=subprocess.PIPE)
    for line in io.TextIOWrapper(jqp.stdout, encoding="utf-8"):
        try:
            yield json.loads(line).encode("utf-8")
        except Exception:
            continue


def from_hf_parquet(hf_path, col, limit):
    sql = (f"INSTALL httpfs; LOAD httpfs; "
           f"CREATE SECRET hf (TYPE huggingface, TOKEN '{HF_TOKEN}'); "
           f"SELECT {col} FROM read_parquet('hf://datasets/{hf_path}') "
           f"WHERE {col} IS NOT NULL AND length({col}) > 0 LIMIT {limit};")
    p = subprocess.Popen(["duckdb", "-csv", "-noheader", "-c", sql], stdout=subprocess.PIPE, text=True)
    for row in csv.reader(p.stdout):
        if row:
            yield row[0].encode("utf-8")
    p.stdout.close(); p.wait()


# The full GPU eval set (synth + real), same sources. TPC-H from the local duckdb; the rest
# streamed from the same public mirrors the GPU campaign used. synthetic_url stays a generated
# stand-in (the CPU bench produces it inline), matching the GPU's regenerated URL corpus.
jobs = [
    ("clickbench_url", lambda: from_textfile(CB_URLS)),
    ("l_comment", lambda: from_duckdb("lineitem", "l_comment", 5_000_000)),
    ("ps_comment", lambda: from_duckdb("partsupp", "ps_comment", 5_000_000)),
    ("l_shipinstruct", lambda: from_duckdb("lineitem", "l_shipinstruct", 8_000_000)),
    ("fineweb", lambda: from_hf_parquet(FINEWEB_HF, "text", 1_000_000)),
    ("wikipedia", lambda: from_hf_parquet(WIKIPEDIA_HF, "text", 1_000_000)),
    ("book_reviews", lambda: from_jsonl_gz(AMAZON_JSONL.format(cat="Books"))),
    ("amazon_movies", lambda: from_jsonl_gz(AMAZON_JSONL.format(cat="Movies_and_TV"))),
    ("amazon_electronics", lambda: from_jsonl_gz(AMAZON_JSONL.format(cat="Electronics"))),
]
print(f"extracting to {OUT} (cap {CAP//1024//1024} MiB/col)")
for name, src in jobs:
    if os.path.exists(os.path.join(OUT, name + ".bin")) and not os.environ.get("REEXTRACT"):
        print(f"  {name}: exists, skipping (set REEXTRACT=1 to rebuild)")
        continue
    try:
        write_bin(name, capped(src()))
    except Exception as e:
        print(f"  {name}: SKIPPED ({e})")
