# Dataset sources

The main evaluation uses the fifteen columns below. The harness's
[`columns.py`](https://github.com/anon-hercynite-sorrel/fastpair-harness/blob/main/benchmarks/onpair-bench/columns.py)
records download URLs, pinned revisions where available, archive members, and
generation parameters. `run.py` fetches or generates selected inputs into
`vortex-bench/data/` in the harness checkout.

| Dataset ID | Column | Source |
|---|---|---|
| `fineweb2-zh` | `text` | HuggingFace `HuggingFaceFW/fineweb-2`, Mandarin `cmn_Hani`, pinned revision |
| `wikipedia` | `text` | HuggingFace `wikimedia/wikipedia`, `20231101.en`, shards 0–2 |
| `codeparrot` | `content` | HuggingFace `codeparrot/codeparrot-clean` |
| `clickbench` | `URL`, `Title` | ClickHouse `hits_compatible/hits.parquet` |
| `loghub-android` | `line` | Loghub `Android_v2.zip`, Zenodo record 8196385 |
| `loghub-hdfs` | `line` | Loghub `HDFS_v1.zip`, same record |
| `loghub-thunderbird` | `line` | Loghub `Thunderbird.tar.gz`, same record |
| `loghub-spark` | `line` | Loghub `Spark.tar.gz`, same record |
| `loghub-windows` | `line` | Loghub `Windows.tar.gz`, same record |
| `tpch-sf263` | `c_address` | Generated TPC-H, scale factor 263 |
| `tpch-sf15` | `l_comment`, `l_shipinstruct`, `ps_comment` | Generated TPC-H, scale factor 15 |
| `tpch-sf45` | `o_clerk` | Generated TPC-H, scale factor 45 |

The benchmark samples 1,000,000,000 UTF-8 payload bytes per column, subject to row
boundaries. The registry may fetch more input to fill that sample. Use the
recorded `sample_bytes` when computing throughput.

Run `uv run python run.py --list` from `benchmarks/onpair-bench/` to inspect the
registry. Set `HF_TOKEN` if needed for HuggingFace access. The corpora themselves
are not committed; downloads remain subject to their sources' availability and terms.

Earlier supporting captures use other inputs, including TPC-H SF10, synthetic
URLs, and Amazon reviews. Their provenance remains in [MANIFEST.md](../MANIFEST.md);
do not substitute those inputs for the main fifteen-column corpus.

## Windows download and local fallback

The canonical source is
[Loghub's Windows archive](https://zenodo.org/records/8196385/files/Windows.tar.gz?download=1),
member `Windows.log`. Its published complete-archive MD5 is
`8b994d947d30617d51e2a565152ae90f`. Older official records
[3227177](https://zenodo.org/records/3227177) and
[1596245](https://zenodo.org/records/1596245) list the same file and checksum.
The archive is about 1.7 GB compressed and 27 GB uncompressed. The runner streams
only the prefix needed for its 1.15 GB source-cache cap, then the benchmark takes
its 1 GB sample. It removes the initial UTF-8 BOM and line terminators while
preserving line order. A streamed prefix cannot establish the full archive MD5.

The normal `run.py` command downloads this input without credentials. The
[official Loghub registry](https://github.com/logpai/loghub/blob/dd61d0952749ee7963bde24220d1be5ede023033/README.md)
lists the URL above. Zenodo can restrict requests by network, returning HTTP 403
or timing out. Use the complete-archive fallback below when that prevents access.
The GitHub 2,000-line example is a different sample and is not suitable for
reproducing the paper's Windows measurements.

If you already have the **complete original archive**, point the runner at it:

```sh
ONPAIR_LOGHUB_WINDOWS_ARCHIVE=/absolute/path/Windows.tar.gz \
ONPAIR_FAST=1 uv run python run.py \
    --datasets loghub-windows --columns line --bits 12 \
    --chunk-mb 1000 --sample-bytes 1000000000 \
    --gpu-decode --gpu-validate --gpu-iters 100 --jobs 1 \
    --gpu-kernels packed-grid
```

Run this from the harness's `benchmarks/onpair-bench` directory. The loader checks
the full archive MD5 before parsing, fails on a mismatch, and records the checksum
and `verified_local_archive` transport in the generated Parquet manifest. It uses
the normal member selection, normalization, cap, and cache publication path.
The archive is supplied by the user and is not redistributed by this artifact.

An existing source Parquet plus its `.manifest.json` can also be copied into
`vortex-bench/data/onpair-bench-src/loghub-windows/`. Both are needed for the
normal cache path. The source Parquet identified by the B300 validation record has SHA-256
`a3f346845f521f5fd0479ede2260fbb6a8f592da2fa23e0d68881192d21ec96c`.
This identifies that cached file, not a promise that different Parquet-writer
versions produce byte-identical containers. The `ONPAIR_LOCAL_LOGHUB_WINDOWS`
override bypasses the normal source-cache manifest checks.
