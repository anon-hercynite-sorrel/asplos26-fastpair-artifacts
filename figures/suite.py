"""Load measurements from results/suite-<id>/<chip>/.

Missing captures yield None or empty collections; coverage() reports availability.
Columns and named paper legs are declared below.

Token length is sample_bytes / gpu.total_tokens: the token-weighted mean,
not the unweighted dictionary-entry mean. Compression ratio uses sample_bytes /
on_disk_bytes, including the stored codes, dictionary, and offset sidecar.

rate_gb_s() reads the production selector (gpu.auto_kernel). best_rate_gb_s() selects
the best validated configuration, including generated kernels. Both use decimal
GB/s and the minimum iteration time. Choose the accessor to match the comparison.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path


# Generated grid kernels have an Experimental role in the registry. That role
# alone does not exclude a byte-validated configuration from best_rate_gb_s().
# Production-only summaries and full-grid results therefore have different scopes.

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

# The corpus, in the paper's Table 1 order: real above the rule, generated below.
REAL = [
    ("FineWeb2 Mandarin",        "fineweb2-zh",        "text"),
    ("Wikipedia",                "wikipedia",          "text"),
    ("CodeParrot",               "codeparrot",         "content"),
    ("Loghub \\texttt{Android}", "loghub-android",     "line"),
    ("ClickBench \\texttt{URL}", "clickbench",         "URL"),
    ("ClickBench \\texttt{Title}", "clickbench",       "Title"),
    ("Loghub \\texttt{HDFS}",    "loghub-hdfs",        "line"),
    ("Loghub \\texttt{Thunderbird}", "loghub-thunderbird", "line"),
    ("Loghub \\texttt{Spark}",   "loghub-spark",       "line"),
    ("Loghub \\texttt{Windows}", "loghub-windows",     "line"),
]
GEN = [
    ("TPC-H \\texttt{c\\_address}",      "tpch-sf263", "c_address"),
    ("TPC-H \\texttt{l\\_comment}",      "tpch-sf15",  "l_comment"),
    ("TPC-H \\texttt{o\\_clerk}",        "tpch-sf45",  "o_clerk"),
    ("TPC-H \\texttt{l\\_shipinstruct}", "tpch-sf15",  "l_shipinstruct"),
    ("TPC-H \\texttt{ps\\_comment}",     "tpch-sf15",  "ps_comment"),
]
# THE LEG THE PAPER READS, DECLARED. Every figure that does not take an explicit --suite-id gets
# this one. It used to be "the newest results/suite-* by name", which made a directory name into
# a load-bearing decision: any leg whose id sorted after "paper-" silently re-pointed seven
# figures and the claims reducer at data the paper does not describe. The software-baseline leg
# was named "suite-baselines-*" to sort BEFORE this one, which is a workaround for the sort rather
# than a reason the sort is right. Name legs whatever describes them; change this line to move the
# paper.
PAPER_SUITE = "suite-paper-20260821"
# THE COMPARATOR LEG. Three baselines in PAPER_SUITE were measured over a narrower space than we
# gave ourselves: FSST-12 got 19 kernels against OnPair's 583, the Engine's chunk oracle sat at the
# largest of five sizes on 15 of 15 columns, and the Engine alone was fed a flat concatenation with
# no row structure. suite-comparators-20260827 remeasures those three on the same corpus and seed;
# it has no GRID arm, so OnPair still comes from PAPER_SUITE and the two legs are read together.
#
# THAT PAIRING IS LICENSED BY A CONTROL, NOT BY ASSERTION. Both legs ran FSST-12 at the identical 19
# production kernels on the identical fifteen columns, differing only in revision: -0.65% to +0.29%,
# median -0.15%, n=15, inside the 0.82% p99 split-half noise floor. See that leg's README. Re-run
# the control after any kernel change before trusting the pairing.
COMPARATOR_SUITE = "suite-comparators-20260827"
# The payload-only leg. Section 5 measures every technique decoding the string payload alone, so
# the byte-oriented baselines must be read from their FLAT run: the comparator leg framed them
# with a u32 length per row, which nvCOMP Zstd never carried. See results/suite-flat-20260830.
FLAT_SUITE = "suite-flat-20260830"
# THE THREE ZSTD LEVELS THE PAPER REPORTS: fast mode, the default, and the highest below the
# --ultra tier. The comparator leg measured five (-10, 1, 3, 9, 19); 1 and 3 are near-duplicates on
# this corpus -- 50.37x against 49.77x at the top, 183 against 179 GB/s -- so three points spanning
# 1.12x to 62.87x costs the same ink as three spanning 1.12x to 50.37x with a repeat in the middle.
# What was collected and what is plotted are separate decisions; this is the plotted set.
PAPER_ZSTD_LEVELS = (-10, 3, 19)

# The shipped batch granularity: K=6, and a warp batch is 32*K codes. Named because it is
# both the historic charge and the fallback when a kernel's own granularity is unmeasured.
SHIPPED_TOK_PER_BATCH = 192


def flat_root():
    """The payload-only leg, or None. Off by absence, like every other leg here."""
    d = RESULTS / FLAT_SUITE
    return d if d.is_dir() else None


def comparator_root():
    """The comparator leg's directory, or None when it is not present."""
    d = RESULTS / COMPARATOR_SUITE
    return d if d.is_dir() else None

CHIPS_CORE = ["b300", "h100", "a100", "l40s"]   # legacy order; lay figures out with common.DEVICE_ORDER

# A chip that is being brought up appears ONLY once its leg has landed. The four above are the
# paper's committed set and always get a slot, because a labelled gap is the honest rendering of a
# leg that was meant to exist and did not. A fifth chip has no such promise attached yet, so an
# empty slot for it would advertise a hole nobody was told to expect -- and it would change every
# committed figure before there is anything to show. Listing it here instead means the figures
# light up by themselves when the data arrives, with no code change at that moment.
CHIPS_EMERGING = ["rtxpro"]


def _present(chip):
    return chip_root(chip) is not None


def candidate_roots(chip):
    """Every suite directory holding this chip, declared campaign first.

    For a figure that needs a specific arm rather than just any data for the chip: it can walk these
    and pick the leg that actually timed what it draws, instead of assuming one directory holds
    everything. The campaign comes first so a figure never silently prefers a side leg."""
    out = []
    declared = RESULTS / PAPER_SUITE
    if (declared / chip).is_dir():
        out.append(declared)
    for d in sorted(RESULTS.glob("suite-*"), key=lambda p: p.name):
        if d.is_dir() and (d / chip).is_dir() and d != declared:
            out.append(d)
    return out


def chip_root(chip, suite_id=None):
    """The suite directory that holds THIS chip, preferring the declared paper campaign.

    A campaign is no longer one directory. The paper suite carries four chips; a chip brought up
    later lands in its own leg, and fig:perf_gen has to draw all of them on one axis. Resolving the
    root per chip is what makes that possible, and it is the same merge fig_perf_real already does
    for the software-baseline leg.

    COMPARABILITY IS NOT ASSUMED HERE -- it is the caller's to state. The rtxpro leg qualifies
    because it shares the paper campaign's vortex_rev (94905b572), training seed (20260819), the
    fifteen-column corpus and the identical clock protocol (boost:full max:full 75%:prod 55%:prod
    40%:prod). A leg that differed in any of those would need saying so beside the figure."""
    if suite_id:
        r = latest_root(suite_id)
        return r if r is not None and (r / chip).is_dir() else None
    declared = RESULTS / PAPER_SUITE
    if (declared / chip).is_dir():
        return declared
    for d in sorted(RESULTS.glob("suite-*"), key=lambda p: p.name):
        if d.is_dir() and (d / chip).is_dir():
            return d
    return None


def chips():
    """The chips to draw: the committed four, plus any emerging chip whose data exists."""
    return CHIPS_CORE + [c for c in CHIPS_EMERGING if _present(c)]


CHIPS = chips()




def latest_root(suite_id=None):
    """The suite directory the paper reads. An explicit id always wins.

    Falls back to the newest suite-* by name only when PAPER_SUITE is absent, so a fresh clone or
    a renamed campaign still resolves to something rather than to None -- but it says so, because
    silently reading a different campaign than the declared one is the failure this replaced."""
    if suite_id:
        p = RESULTS / (suite_id if suite_id.startswith("suite-") else f"suite-{suite_id}")
        return p if p.is_dir() else None
    declared = RESULTS / PAPER_SUITE
    if declared.is_dir():
        return declared
    cands = sorted(RESULTS.glob("suite-*"), key=lambda p: p.name)
    if cands:
        print("suite: declared %s is absent; falling back to %s"
              % (PAPER_SUITE, cands[-1].name), file=sys.stderr)
    return cands[-1] if cands else None


def baselines_root(baselines_id=None):
    """The software-baseline leg (gANS, Bitcomp), which is SEPARATE from latest_root()'s leg.

    Its stages are MATERIALIZE SW, so it carries onpair_nvcomp_sw.json and nothing the paper suite
    already has. Verified comparable to suite-paper-20260821 before the two were put on one axis:
    same vortex_rev (94905b572), same training_seed (20260819), same fifteen columns, and
    raw_bytes agrees with sample_bytes per column on every real column.
    """
    if baselines_id:
        p = RESULTS / (baselines_id if baselines_id.startswith("suite-") else f"suite-{baselines_id}")
        return p if p.is_dir() else None
    cands = sorted(RESULTS.glob("suite-baselines-*"), key=lambda p: p.name)
    return cands[-1] if cands else None


def sw_root_for(chip):
    """Where a chip's gANS/Bitcomp cells come from, PER CHIP.

    suite-baselines-20260822 measured them on a FLAT concatenation with no separators -- the last
    techniques whose ratio came from a byte stream rows cannot be recovered from, once the engine
    was framed on 2026-08-27. The comparator leg re-measured them on the same u32-length-framed
    stream every other technique gets. But that leg ran on the **b300 only**, so h100 and l40s still
    have to come from the flat leg.

    Resolved per chip rather than per run, and deliberately not silently: a caller that wants one
    basis across chips must check `sw_is_framed`. The paper reports the b300.

    SUPERSEDED ON THE B300 BY THE FLAT LEG. Section 5 measures every technique decoding the payload
    alone, so the framing the comparator leg added is now the wrong basis, not the right one: it
    made gANS and Bitcomp decompress four bytes a row that nvCOMP Zstd never carried. The flat leg
    re-measured them without it, which is what this returns when present.
    """
    fr = flat_root()
    if fr is not None and (fr / chip / "onpair_nvcomp_sw.json").exists():
        return fr
    cr = comparator_root()
    if cr is not None and (cr / chip / "onpair_nvcomp_sw.json").exists():
        return cr
    return baselines_root()


def sw_is_framed(chip):
    """True when this chip's software baselines carry a u32 length per row inside their output.

    Section 5's basis is payload-only, so False is now the CORRECT state on the b300 rather than a
    gap: the flat leg supersedes the framed comparator leg. Kept because a caller comparing chips
    still needs to know that h100 and l40s come from a different run than the b300.
    """
    fr = flat_root()
    if fr is not None and (fr / chip / "onpair_nvcomp_sw.json").exists():
        return False
    cr = comparator_root()
    return cr is not None and (cr / chip / "onpair_nvcomp_sw.json").exists()


def sw_rows(root, chip="b300"):
    """nvCOMP software-codec cells (gANS, Bitcomp-*), keyed by (dataset_id, column).

    Empty dict when the leg is absent, so a figure degrades to the baselines it does have rather
    than raising."""
    if root is None:
        return {}
    f = Path(root) / chip / "onpair_nvcomp_sw.json"
    try:
        rows = json.load(open(f))
    except (OSError, json.JSONDecodeError):
        return {}
    return {(r.get("dataset_id"), r.get("column")): r for r in rows}


def clock_tags(root, chip):
    """Clock tags present for a chip, boost first then ascending pinned MHz."""
    d = Path(root) / chip
    tags = set()
    for f in d.glob("sweep_summary_*.json"):
        m = re.search(r"_(boost|sm\d+)\.json$", f.name)
        if m:
            tags.add(m.group(1))
    pinned = sorted((t for t in tags if t.startswith("sm")), key=lambda t: int(t[2:]))
    return (["boost"] if "boost" in tags else []) + pinned


def tag_mhz(tag):
    return None if tag == "boost" else int(tag[2:])


def _cells(root, chip, prefix, tag):
    out = []
    for f in sorted((Path(root) / chip).glob(f"{prefix}_*_{tag}.json")):
        try:
            rows = json.load(open(f))
        except (OSError, json.JSONDecodeError):
            continue          # a partial leg is normal; report it via coverage(), never raise
        if isinstance(rows, list):
            out.extend(rows)
    return out


def cells(root, chip, tag="boost", codec="onpair"):
    """Every cell for a chip at one clock state, keyed by (dataset_id, column, bits).

    FSST-12 and Zstd come from COMPARATOR_SUITE where it exists: in PAPER_SUITE, FSST-12 was
    measured with `--gpu-kernels production` (19 kernels against OnPair's 583) and Zstd was measured
    at three levels that stop short of the ratios it reaches. Zstd is still REPORTED at three
    levels, PAPER_ZSTD_LEVELS, just not the same three. OnPair is never redirected: the comparator
    leg has no GRID arm.
    """
    prefix = {"onpair": "sweep_summary", "fsst12": "fsst12_summary",
              "zstd": "zstd_summary"}[codec]
    src = root
    if codec in ("fsst12", "zstd"):
        cr = comparator_root()
        if cr is not None and (cr / chip).is_dir() and any((cr / chip).glob(f"{prefix}_*_{tag}.json")):
            src = cr
    out = {}
    for c in _cells(src, chip, prefix, tag):
        out[(c.get("dataset_id"), c.get("column"), c.get("bits"))] = c
    return out


def rate_gb_s(c):
    """Shipped-selector decode rate in GB/s, or None if the cell did not time it."""
    if not c:
        return None
    g = c.get("gpu") or {}
    auto = g.get("auto_kernel")
    for k in (g.get("kernels") or []):
        if k.get("kernel") == auto:
            it = k.get("decode_ns_iters") or []
            if it and g.get("decoded_bytes"):
                return g["decoded_bytes"] / min(it)
    return None


def best_rate_gb_s(c):
    """Best decimal GB/s across applicable, byte-validated kernel configurations.

    Includes generated kernels as well as production kernels. Returns None when
    no qualifying kernel has timings. Uses the minimum iteration time.
    """
    g = (c or {}).get("gpu") or {}
    db = g.get("decoded_bytes")
    if not db:
        return None
    best = None
    for k in (g.get("kernels") or []):
        # Timings are usable only for applicable kernels that passed validation.
        if not (k.get("verified") and k.get("applicable")):
            continue
        it = k.get("decode_ns_iters") or []
        if it:
            v = db / min(it)
            if best is None or v > best:
                best = v
    return best


def tokens(c):
    return ((c or {}).get("gpu") or {}).get("distinct_codes")


def mean_len(c):
    """Token-weighted mean decoded bytes per code.

    gpu.total_tokens counts decoded codes. gpu.compressed_bytes also includes
    dictionary bytes and per-entry lengths, so it is not a code-count proxy.
    """
    if not c:
        return None
    count = (c.get("gpu") or {}).get("total_tokens")
    sb = c.get("sample_bytes")
    return (sb / count) if (count and sb) else None


def frac_le8(c):
    return ((c or {}).get("gpu") or {}).get("frac_le8")


_ONPAIR_SIDECAR = None


def _onpair_sidecar_table():
    """{(dataset, column, bits, tok_per_batch): bytes}, summed over chunks.

    KEYED ON GRANULARITY, because the charge is no longer one number per cell. The sidecar holds
    one offset per batch of 32*K codes, so its size is a function of the K the kernel reading it
    was compiled for, and ratio() now charges the K of the kernel whose rate is being reported.

    Prefers onpair_offset_cost_bygran.jsonl, which covers all nine granularities the kernel sweep
    actually produces. The comparator leg's onpair_offset_cost.jsonl measured 32, 128 and 192 only
    and is the fallback for an older results tree; where the two overlap they agree exactly on all
    90 (cell, granularity) pairs, which is the check that licensed the coarser numbers.

    NOT CHIP-SPECIFIC AS A MEASUREMENT: a given (column, K) sidecar is a property of the encoded
    column, identical whichever GPU later decodes it. What IS chip-specific is which K a chip's
    fastest kernel uses, and that lives in the caller.

    Deduped on full chunk identity before summing: the ZSTD stage re-encodes through the same path,
    so the raw file holds each chunk twice and summing it doubles the column.
    """
    global _ONPAIR_SIDECAR
    if _ONPAIR_SIDECAR is not None:
        return _ONPAIR_SIDECAR
    for root, name in ((flat_root(), "onpair_offset_cost_bygran.jsonl"),
                       (comparator_root(), "onpair_offset_cost.jsonl")):
        f = (root / "b300" / name) if root else None
        if not (f and f.exists()):
            continue
        seen = {}
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            seen[(r["dataset"], r["column"], r["bits"], r["tok_per_batch"], r["chunk"])] = r
        acc = {}
        for r in seen.values():
            k = (r["dataset"], r["column"], r["bits"], r["tok_per_batch"])
            acc[k] = acc.get(k, 0) + r["offset_compressed_bytes"]
        if acc:
            _ONPAIR_SIDECAR = acc
            return acc
    _ONPAIR_SIDECAR = {}
    return _ONPAIR_SIDECAR


def onpair_sidecar(ds, col, bits, tok_per_batch=SHIPPED_TOK_PER_BATCH):
    """OnPair's stored output-position sidecar for one cell at one granularity, in bytes.

    Returns 0 when the granularity was not measured, which a caller must treat as a gap rather
    than as free: see kernel_tok_per_batch, which refuses to report an unmeasured one.
    """
    return _onpair_sidecar_table().get((ds, col, bits, tok_per_batch), 0)


def kernel_tok_per_batch(c, basis="best"):
    """Codes per batch of the kernel whose rate `basis` reports, or None.

    THE POINT OF THIS FUNCTION. A cell's sidecar is sized for a particular batch granularity, and
    the kernel sweep varies K, so a rate and a compression ratio only describe one artifact if the
    ratio is charged at the granularity that rate's kernel was compiled for. Charging a fixed 192
    while reporting the best kernel over all K -- which is what every figure did until 2026-09-02 --
    pairs a throughput with a stored representation the kernel does not read.

    `basis` is "best" for best_rate_gb_s (the paper's best-configuration basis) and "shipped" for
    rate_gb_s (the deployed selector). They differ: on the B300 the selector mostly runs 128 while
    the best kernel is usually 192.

    Returns None when the cell timed no such kernel or the kernel records no granularity, so a
    caller can fall back to the shipped charge deliberately instead of silently charging zero.
    """
    g = (c or {}).get("gpu") or {}
    ks = g.get("kernels") or []
    if basis == "shipped":
        auto = g.get("auto_kernel")
        for k in ks:
            if k.get("kernel") == auto:
                return k.get("chunk_size")
        return None
    best = None
    for k in ks:
        if not (k.get("verified") and k.get("applicable")):
            continue
        t = k.get("decode_gib_s")
        if t is None:
            continue
        if best is None or t > best[0]:
            best = (t, k)
    return best[1].get("chunk_size") if best else None


_FSST12_COMPONENTS = None


_FSST12_SIDECAR = None


def fsst12_sidecar(ds, col, tok_per_batch, fallback):
    """FSST-12's stored sidecar at one granularity, or `fallback` when unmeasured.

    MEASURED ONLY WHERE IT CHANGES SOMETHING, and only where a macOS measurement is legitimate.
    FSST-12's sidecar is recorded on the cell at the shipped K=6, and 13 of its 15 B300 best kernels
    run there, so the cell figure is already the right charge for them. The two that do not are
    c_address (K=16) and o_clerk (K=8), and both are among the EIGHT columns whose host-side split
    reproduces the committed cell exactly -- the trained dictionary agrees, so a local measurement
    describes the same artifact. On the seven columns that do not reproduce, a macOS sidecar would
    describe a macOS encode of a Linux-encoded column and is deliberately not used; they fall back
    to the cell, which is correct for them anyway.

    See docs/notes/2026-09-02-fsst12-platform-dependence.md for why that distinction is load-bearing.
    """
    global _FSST12_SIDECAR
    if _FSST12_SIDECAR is None:
        _FSST12_SIDECAR = {}
        fr = flat_root()
        f = (fr / "b300" / "fsst12_sidecar_bygran.jsonl") if fr else None
        if f and f.exists():
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                _FSST12_SIDECAR[(r["dataset_id"], r["column"], r["tok_per_batch"])] = r["sidecar"]
    v = _FSST12_SIDECAR.get((ds, col, tok_per_batch))
    return fallback if v is None else v


def fsst12_components(ds, col):
    """FSST-12's stored footprint by component, or None.

    WHY THIS IS A SEPARATE FILE AND NOT ON THE CELL. Section 5 excludes the row-offsets array from
    the reported ratio, and the committed FSST-12 cells collapse their components into one total,
    so there is nothing to subtract from them. `Fsst12StoredSize::row_offsets` starts as a raw
    (rows+1)*8 placeholder that the cell path overwrites with the compress_offsets result, so it
    cannot be recovered by arithmetic either. These were measured host-side by
    vortex-bench's fsst12-stored bin at the leg revision.

    MEASURED ON A DIFFERENT PLATFORM THAN THE LEG, and the totals say how much that costs: ten of
    the fifteen columns reproduce the committed container-matched total EXACTLY, four land within
    0.18%, and loghub-spark is -1.13%. FSST-12's trainer is deterministic per platform and differs
    across them -- its C++ symbol search does not fix hash iteration order -- so a macOS run cannot
    byte-match a Linux leg. The row-offsets array is the most transferable component of the three,
    since the row counts match exactly on every column.
    """
    global _FSST12_COMPONENTS
    if _FSST12_COMPONENTS is None:
        _FSST12_COMPONENTS = {}
        fr = flat_root()
        f = (fr / "b300" / "fsst12_stored_components.jsonl") if fr else None
        if f and f.exists():
            for line in f.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    _FSST12_COMPONENTS[(r["dataset_id"], r["column"])] = r
    return _FSST12_COMPONENTS.get((ds, col))


_ONPAIR_STORED = None


def onpair_stored_bytes(ds, col, bits, tok_per_batch=SHIPPED_TOK_PER_BATCH):
    """OnPair's stored size under Section 5's rule: what a reader must have to BULK DECOMPRESS.

    Section 5: "As decompressing the row offsets array is not necessary for bulk decompression, we
    do not include it in the compression ratio ... for FSST-family codecs we report uncompressed
    bytes against the sum of cascade-compressed bytes, decoding chunk offsets (sidecar), and
    dictionary data."

    So: codes + dictionary + dictionary offsets + sidecar. OUT: `codes_offsets` (row to code) and
    `uncompressed_lengths` (per-row decoded length). Both are derivable and neither is read by the
    decode kernel, whose four inputs are the widened codes, the sidecar, the padded dictionary and
    the length table -- see onpair_shmem_4tpt's signature.

    THE EXCLUDED PAIR IS NOT SMALL, which is why this is a rule and not a rounding decision:
    together they are 5.2% of the stored column on loghub-android and 30% on l_shipinstruct.

    Returns None when the components are unavailable, so a caller falls back rather than silently
    reporting a different basis.
    """
    global _ONPAIR_STORED
    if _ONPAIR_STORED is None:
        root = comparator_root() or latest_root()
        _ONPAIR_STORED = child_bytes(root) if root else {}
    d = _ONPAIR_STORED.get((ds, col, bits))
    if not d:
        return None
    payload = d["codes"] + d["dict"] + d["dict_offsets"]
    side = onpair_sidecar(ds, col, bits, tok_per_batch)
    if not side and tok_per_batch != SHIPPED_TOK_PER_BATCH:
        # An unmeasured granularity must not be charged as zero, which would silently report a
        # BETTER ratio than the shipped charge. Fall back to the shipped one and let the caller's
        # own reporting say so.
        side = onpair_sidecar(ds, col, bits, SHIPPED_TOK_PER_BATCH)
    return payload + side


def ratio(c, tok_per_batch=None):
    """At-rest compression ratio: sample_bytes / on_disk_bytes.

    on_disk_bytes includes packed codes, the dictionary, and the offset sidecar.
    gpu.compressed_bytes counts unpacked u16 codes, dictionary bytes, and per-entry
    lengths; it is not the stored-size denominator.

        CONTAINER-MATCHED WHERE THE CODEC AND ITS CONTAINER DIFFER. FSST-12 stores codes in its own
    fixed 12-bit packing, while OnPair's go through the same integer compressor as the rest of the
    Vortex array, which bit-packs to about log2(cardinality). Dividing by each technique's own
    stored size therefore compares FSST-12's CONTAINER against OnPair's CODEC: on a column with
    five distinct values it charged FSST-12 twelve bits per code and OnPair three. The cells carry
    mem_ratio_container_matched for exactly this, measured through OnPair's instrument, and no
    figure read it -- the decision was taken on 2026-08-12, applied to the ten-column generator,
    and lost when the fifteen-column one replaced it with this codec-agnostic helper. Effect on the
    real columns is 0-10%; on TPC-H l_shipinstruct it is 3.37x to 11.37x.

    CHARGED AT THE GRANULARITY OF THE KERNEL BEING REPORTED, when the caller passes one. The
    sidecar holds one offset per batch of 32*K codes, so its size follows the K its reader was
    compiled for; charging a fixed 192 while reporting the best kernel over all K pairs a
    throughput with a stored representation that kernel does not read. Pass
    kernel_tok_per_batch(c, basis) matching whichever rate you plot. `tok_per_batch=None` keeps
    the shipped 192, which is right for a table that pairs the ratio with no rate at all.

    FSST-12 STAYS AT 192 and that is a scope limit, not an oversight. Its sidecar is measured on
    the cell rather than by granularity, and re-deriving it needs a re-encode from parquet, whose
    trained dictionary is platform-dependent. Thirteen of its fifteen B300 best kernels are at 192
    already; the other two are COARSER, so their true sidecar is smaller than charged and the
    reported ratio is conservative by at most the sidecar's whole share, which is under 1.1%.

    THE SIDECAR IS IN THE DENOMINATOR, on both dictionary codecs. It is storage a reader must have
    to position a batch's output without a serial scan over everything before it, so by the rule in
    docs/notes/2026-08-27-stored-size-accounting.md it counts. The byte-oriented baselines have no
    equivalent because their decode is serial, and charging ourselves for it is the honest way to
    state that trade -- Section 3 prices the alternative, regenerating it on the device, at 14 to
    19% slower.

    ITS SHARE, RE-DERIVED 2026-09-02, and the old figure here was against the wrong denominator.
    This docstring used to say "0.26 to 0.72% of OnPair's stored column". That range is the
    sidecar over the WHOLE .vortex file -- which still measures 0.00 to 0.72% -- but the file also
    carries codes_offsets and uncompressed_lengths, and Section 5 excludes both, so it is not the
    denominator this function divides by. Against the offsets-excluded stored column that IS the
    denominator, the shipped K=6 sidecar is 0.00 to 1.63% (median 0.40%) on OnPair and 0.00 to
    1.46% (median 0.45%) on FSST-12. The maxima are l_shipinstruct, whose denominator the
    offsets-exclusion shrank by 30%, which is exactly why the share moved when the basis did.

    At the FINEST granularity, the 32-code sidecar that can serve any K, it is 0.00 to 8.11%
    (median 1.82%). Anyone quoting a sidecar share must say which granularity they mean.

    It changes no ordering: verified, 0 of 15 columns flip OnPair-12 against OnPair-16 when the
    sidecar is added to or removed from both denominators.
    """
    if not c:
        return None
    sb = c.get("sample_bytes")
    if not sb:
        return None
    cm = c.get("mem_ratio_container_matched")
    if cm:
        # FSST-12 on Section 5's basis: the container-matched total is authoritative, and the
        # row-offsets array measured beside it comes out of it. Without this, OnPair would be on
        # the offsets-excluded basis while its nearest prior-art comparator was not -- on
        # l_shipinstruct that alone reads as a 2.2x advantage that is entirely bookkeeping.
        comp = fsst12_components(c.get("dataset_id"), c.get("column"))
        side = fsst12_sidecar(c.get("dataset_id"), c.get("column"),
                              tok_per_batch or SHIPPED_TOK_PER_BATCH,
                              c.get("sidecar_bytes") or 0)
        if comp and comp.get("row_offsets"):
            den = sb / cm - comp["row_offsets"] + side
            return sb / den if den > 0 else None
        # FSST-12: recover the container-matched denominator, then add its own measured sidecar.
        den = sb / cm + side
        return sb / den if den else None
    # OnPair: the offsets-excluded basis. at_rest_bytes is the WHOLE .vortex file, which also
    # carries codes_offsets and uncompressed_lengths; Section 5 excludes both.
    tpb = tok_per_batch or SHIPPED_TOK_PER_BATCH
    stored = onpair_stored_bytes(
        c.get("dataset_id"), c.get("column"), c.get("bits"), tpb)
    if stored:
        return sb / stored
    den = at_rest_bytes(c)
    if not den:
        return None
    den += onpair_sidecar(c.get("dataset_id"), c.get("column"), c.get("bits"), tpb)
    return sb / den


def at_rest_bytes(c):
    """The stored size: on_disk_bytes, falling back to in_memory_bytes when nothing was written.

    The FSST-12 leg keeps its output in memory and reports on_disk_bytes = 0 and
    disk_ratio = 0.0, so on_disk_bytes alone would blank that codec's whole column. The fallback
    is sound because the two are the same arrays: across the OnPair cells, where both exist,
    on_disk_bytes exceeds in_memory_bytes by 3.3-5.0 KB of file framing, i.e. 0.001%. Both are
    the packed form; neither is gpu.compressed_bytes."""
    if not c:
        return 0
    return (c.get("on_disk_bytes") or 0) or (c.get("in_memory_bytes") or 0)


def offset_cost_rows(root, chip="b300", leg_chunk_bytes=None):
    """Rows of onpair_offset_cost.jsonl: the sidecar sweep, one record per chunk per granularity.

    Written by the ONPAIR_OFFSET_COST path during MATERIALIZE. Fields that matter here:
    dataset, column, bits, chunk, tok_per_batch, n_batches, total_tokens, decoded_bytes,
    compressed_bytes (the chunk's stored OnPair array) and offset_compressed_bytes (the sidecar
    through compress_offsets, the same delta-or-plain path the OnPair children take).

    SMOKE ROWS ARE DROPPED. Before 2026-08-26 the sink was exported ahead of phase 0, so
    onpair-bench.sh's 50 MB build smoke on tpch-sf10/l_comment appended fifteen records describing
    a cell no figure reads. They are separable by chunk size -- the smoke runs at 10 MB against the
    leg's 1000 -- and `leg_chunk_bytes` drops them; pass None to keep everything.
    """
    f = Path(root) / chip / "onpair_offset_cost.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out.append(r)
    if leg_chunk_bytes is not None:
        # The offset-cost record carries no chunk_bytes of its own; the smoke's signature is a
        # dataset id from the OLD ten-column corpus, which this suite does not contain.
        ids = {ds for _l, ds, _c in REAL + GEN}
        out = [r for r in out if r.get("dataset") in ids]
    return out


def sidecar_bytes(root, chip="b300", tok_per_batch=192):
    """{(dataset, column, bits): (sidecar_bytes, stored_bytes)} summed over chunks.

    Summed, not last-wins: a column is many chunks and each writes its own record. Keyed on the
    granularity because the footprint is not linear in it -- measured on this corpus, the sidecar
    runs about 0.44% of stored at 192, 0.53% at 128 and 1.85% at 32.
    """
    acc = {}
    for r in offset_cost_rows(root, chip, leg_chunk_bytes=True):
        if r.get("tok_per_batch") != tok_per_batch:
            continue
        k = (r["dataset"], r["column"], r["bits"])
        side, tot = acc.get(k, (0, 0))
        acc[k] = (side + r["offset_compressed_bytes"], tot + r["compressed_bytes"])
    return acc


def child_bytes(root, chip="b300"):
    """{(dataset, column, bits): {child: bytes}} summed over chunks, plus 'total'.

    From onpair_child_bytes.jsonl. This is what answers "what does the string part cost without
    the offsets" without guessing: `codes_offsets` is the row-to-code offset child, a separate
    Vortex array with its own integer encoding, and on short-row columns it is a large enough
    share of the total that a string-codec comparison including it is measuring offset compression.
    """
    acc = {}
    seen = set()
    f = Path(root) / chip / "onpair_child_bytes.jsonl"
    if not f.exists():
        return acc
    ids = {ds for _l, ds, _c in REAL + GEN}
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("dataset") not in ids:
            continue          # build-smoke row; see offset_cost_rows
        d = acc.setdefault((r["dataset"], r["column"], r["bits"]),
                           {k: 0 for k in ("codes", "codes_offsets", "dict_offsets",
                                           "lengths", "dict", "total")})
        # DEDUPE ON FULL CELL IDENTITY, exactly as onpair_sidecar does. The ZSTD stage re-encodes
        # through the same path, so onpair_child_bytes.jsonl holds 70 records for 35 identities:
        # every bits=12 record appears twice, byte-identical, and tpch-sf10's five chunks appear
        # five times each. Summing raw doubles every bits=12 column. Percentage-of-total figures
        # survive that; bytes per row do not.
        ident = (r["dataset"], r["column"], r["bits"], r["chunk_idx"],
                 r.get("chunk_bytes"), r.get("threshold"), r.get("training_seed"))
        if ident in seen:
            continue
        seen.add(ident)
        for k in d:
            d[k] += r[k]
    return acc


def de_rows(root, chip="b300"):
    """Decompression-Engine cells, one per column, each with its chunk sweep and codec families.

    From COMPARATOR_SUITE where it exists: seven chunk sizes instead of five, on a u32-length-framed
    input rather than a flat concatenation with no row structure. Both changes move the Engine UP
    against us, and the second is the one that matters -- it was the only technique whose ratio was
    measured on a byte stream rows cannot be recovered from.
    """
    # FLAT FIRST. The comparator leg's DE decompresses a u32 length per row that Zstd does not, so
    # its rates carry work no other baseline pays and its ratios count row structure Section 5
    # excludes. The flat leg is the same seven chunk sizes on the payload alone.
    fr = flat_root()
    if fr is not None and (fr / chip / "onpair_nvcomp_hw.json").exists():
        root = fr
    else:
        cr = comparator_root()
        if cr is not None and (cr / chip / "onpair_nvcomp_hw.json").exists():
            root = cr
    f = Path(root) / chip / "onpair_nvcomp_hw.json"
    try:
        return json.load(open(f))
    except (OSError, json.JSONDecodeError):
        return []


def coverage(root):
    """What actually landed. Figures print this so a gap is visible rather than inferred."""
    rep = {}
    for chip in CHIPS:
        d = Path(root) / chip
        if not d.is_dir():
            rep[chip] = {"present": False}
            continue
        tags = clock_tags(root, chip)
        rep[chip] = {
            "present": True,
            "clocks": tags,
            "onpair_cells": len(cells(root, chip, "boost", "onpair")),
            "fsst12_cells": len(cells(root, chip, "boost", "fsst12")),
            "de": len(de_rows(root, chip)),
            "complete": (Path(root) / chip / "suite-complete.txt").exists(),
        }
    return rep


# ============================================================================================
# BASELINE POINT SETS. One definition, shared by fig_perf_real (which plots them and asserts
# per-column dominance) and experiments/paper_claims.py (which derives the numbers the prose
# cites). They used to live only in the figure, so the reducer would have needed a second copy
# of the same extraction -- and two copies of one rule drifting apart is this repository's
# recurring defect, not a hypothetical one.
#
# Every point is (ratio, GB/s, label). Rate is raw min-of-N where the per-iteration timings
# survive, matching rate_gb_s() on our own side of the comparison, and falls back to the
# harness's decode_gib_s only when they do not. The two agree to a tenth of a GB/s wherever
# both exist, so the fallback is a completeness measure rather than a second basis.
# ============================================================================================
GIB_TO_GB = (2 ** 30) / 1e9

DE_NAME = {"DEFLATE-hi": "DE Deflate (5)", "DEFLATE-fast": "DE Deflate (0)",
           "LZ4": "DE LZ4", "Snappy": "DE Snappy"}


def _rate(entry, raw_bytes):
    """Decode rate in GB/s, over the STRING PAYLOAD rather than the file.

    The Decompression Engine used to be handed a flat concatenation of values with no separators,
    so its file and its payload were the same bytes and `raw_bytes` was an unambiguous numerator.
    It is now fed a u32-length-framed record stream -- the row structure every other technique
    already stored and it alone did not -- so the file is payload plus four bytes per row. Dividing
    by the file counts framing as decoded output: on a twelve-byte column that is a third of the
    reported rate, invented.

    `basis_bytes` is the numerator the producer itself used, per codec, and is preferred where
    present; `payload_bytes` is the same quantity at the top of the record. `raw_bytes` remains the
    file size and is the fallback for producers that predate the distinction -- for which the two
    coincide, because nothing was framed."""
    it = entry.get("decode_ns_iters") or []
    basis = entry.get("basis_bytes") or raw_bytes
    if it and basis:
        return basis / min(it)
    return (entry.get("decode_gib_s") or 0) * GIB_TO_GB or None


def _payload(row):
    """The string bytes in a producer record, whatever the file around them cost. See `_rate`."""
    return row.get("payload_bytes") or row.get("raw_bytes")


def _pareto(pts):
    """Drop points another point of the SAME baseline beats on both axes.

    A dominated configuration cannot move the frontier or the dominance verdict, and dropping it
    keeps the engine's twenty cells per column from becoming a cloud nobody would ship. This is
    the rule already applied by hand to the Zstd levels."""
    return [p for p in pts
            if not any(q[0] >= p[0] and q[1] >= p[1] and (q[0], q[1]) != (p[0], p[1])
                       for q in pts)]


def de_points(root, chip, ds, col):
    """The Decompression Engine's whole sweep for a column: four codecs by five chunk sizes.

    NOT best_codec/best_chunk_bytes alone. Those name the engine's FASTEST setting, so quoting
    only that mark drops its high-ratio half -- and that half is the interesting one. On Loghub
    Thunderbird, DEFLATE-hi at 512 KB stores 18.8x against OnPair-16's 5.2x, at 629 GB/s. It
    loses on rate, which is the claim; a test that never saw it was not testing the claim."""
    raw = []
    for r in de_rows(root, chip):
        if r.get("dataset_id") != ds or r.get("column") != col:
            continue
        passes = [(r.get("chunk_bytes"), r.get("codecs") or {})]
        passes += [(p.get("chunk_bytes"), p.get("codecs") or {})
                   for p in (r.get("chunk_sweep") or [])]
        seen = set()
        for chunk, codecs in passes:
            for name, e in codecs.items():
                if (name, chunk) in seen:
                    continue
                seen.add((name, chunk))
                if not e.get("valid") or e.get("validation_failed") or not e.get("ratio"):
                    continue
                rate = _rate(e, _payload(r))
                if rate:
                    raw.append((e["ratio"], rate, DE_NAME.get(name, "DE %s" % name)))
    return _pareto(raw)


def de_by_codec(root, chip, ds, col):
    """{raw codec name: best rate over that codec's chunk sweep, GB/s} for one column.

    The per-CODEC counterpart to de_points, which pools all four and returns the frontier. A
    figure drawing one line per codec needs them kept apart, and it wants each codec's own best
    chunk size rather than a chunk held fixed across four codecs whose optima differ. Keyed on the
    RAW harness name (DEFLATE-hi, DEFLATE-fast, LZ4, Snappy), not DE_NAME's display string, so a
    caller can look up its own colour and label without a reverse map."""
    out = {}
    for r in de_rows(root, chip):
        if r.get("dataset_id") != ds or r.get("column") != col:
            continue
        passes = [(r.get("chunk_bytes"), r.get("codecs") or {})]
        passes += [(p.get("chunk_bytes"), p.get("codecs") or {})
                   for p in (r.get("chunk_sweep") or [])]
        seen = set()
        for chunk, codecs in passes:
            for name, e in codecs.items():
                if (name, chunk) in seen:
                    continue
                seen.add((name, chunk))
                if not e.get("valid") or e.get("validation_failed"):
                    continue
                rate = _rate(e, _payload(r))
                if rate and rate > out.get(name, 0):
                    out[name] = rate
    return out


ZSTD_FRAME_BYTES_DEFAULT = 65536
_ZSTD_FRAMES = None


def zstd_frame_rows():
    """{(dataset, column): cell} from the frame sweep, or {} when the leg is absent.

    The sweep measured 3 levels x 7 byte-anchored frame targets per column. l_shipinstruct was
    measured first, at five levels, and lives in its own file.
    """
    global _ZSTD_FRAMES
    if _ZSTD_FRAMES is not None:
        return _ZSTD_FRAMES
    _ZSTD_FRAMES = {}
    fr = flat_root()
    if fr is None:
        return _ZSTD_FRAMES
    for name in ("zstd_frames.json", "zstd_frames_shipinstruct.json"):
        f = fr / "b300" / name
        if not f.exists():
            continue
        for r in json.load(open(f)):
            _ZSTD_FRAMES[(r["dataset_id"], r["column"])] = r
    return _ZSTD_FRAMES


def _zstd_cells(ds, col):
    r = zstd_frame_rows().get((ds, col))
    if not r:
        return [], 1.0
    rows = r.get("rows") or 1
    bpr = r["sample_bytes"] / rows
    cells = [e for e in ((r.get("gpu") or {}).get("nvcomp_zstd") or [])
             if e.get("supported") and e.get("compression_ratio") and e.get("decode_gib_s")
             and e.get("zstd_level") in PAPER_ZSTD_LEVELS]
    return cells, bpr


def zstd_default_points(ds, col):
    """Zstd at the VENDOR DEFAULT frame: one point per reported level.

    nvCOMP documents 64 KiB as a good starting chunk size and it is what Section 5 reports as the
    default. Crucially it is a BYTE size: the bench's old 2048-VALUES constant meant 24 KiB on
    l_shipinstruct and 8.5 MB on wikipedia, so it compared different things on different columns.
    At 64 KiB every column here holds ~15,000 frames, well clear of the point where too few frames
    underuse the device.
    """
    cells, bpr = _zstd_cells(ds, col)
    out = []
    for lv in PAPER_ZSTD_LEVELS:
        s = [c for c in cells if c["zstd_level"] == lv]
        if not s:
            continue
        e = min(s, key=lambda c: abs(c["values_per_frame"] * bpr - ZSTD_FRAME_BYTES_DEFAULT))
        out.append((e["compression_ratio"], e["decode_gib_s"] * GIB_TO_GB, "Zstd (%s)" % lv))
    return out


def zstd_default_rate(ds, col, level):
    """Decode rate at the VENDOR DEFAULT frame for one level, or None.

    fig_teaser used to read the old zstd_summary cells, which sat at the bench's pinned 2048
    VALUES per frame -- 24 KiB on l_shipinstruct and 8.5 MB on wikipedia. A caption calling that
    a default window size would not be true of any column. This is the 64 KiB point.
    """
    cells, bpr = _zstd_cells(ds, col)
    s = [c for c in cells if c["zstd_level"] == level]
    if not s:
        return None
    e = min(s, key=lambda c: abs(c["values_per_frame"] * bpr - ZSTD_FRAME_BYTES_DEFAULT))
    return e["decode_gib_s"] * GIB_TO_GB


def zstd_best_points(ds, col):
    """Every non-dominated (frame, level) Zstd configuration -- the faded series in Section 5.

    Shown because no single frame is best: across 42 (column, level) pairs, NOT ONE has a frame
    that dominates the others on both ratio and rate, and the median frontier is 6 of 7 frames.
    Frame size trades the two axes, so "Zstd's best configuration" is a choice of operating point
    rather than an optimum, and the honest figure shows the default and the frontier it sits on.

    CAVEAT FOR ANYONE READING RATES OFF THE HIGH-RATIO END: frame count is sample_bytes divided by
    frame bytes, so a 2 MiB frame is 478 frames at the 1 GB sample -- too few to fill a B300. Those
    ratios are real; those rates would rise on a larger sample.
    """
    cells, _ = _zstd_cells(ds, col)
    pts = [(e["compression_ratio"], e["decode_gib_s"] * GIB_TO_GB, "Zstd (%s)" % e["zstd_level"])
           for e in cells]
    return _pareto(pts)


def zstd_level_points(ds, col, level):
    """EVERY frame-sweep cell for one column at one level, dominated ones included.

    zstd_best_points prunes to the non-dominated set and pools the levels, which is what the
    faded marks want. A per-level REGION wants the opposite: the whole measured set, so the
    frontier drawn over it is the frontier of what was actually run rather than of what survived
    an earlier prune.
    """
    cells, _ = _zstd_cells(ds, col)
    return [(e["compression_ratio"], e["decode_gib_s"] * GIB_TO_GB)
            for e in cells if e["zstd_level"] == level]


def zstd_points(zcells, ds, col):
    """The three nvCOMP Zstd levels for one column, from the OnPair-12 cell that carries them.

    The fields are decode_gib_s and compression_ratio. An earlier reader asked for
    decompress_gib_s and ratio, got None for both, and concluded the data had never been
    collected. It had."""
    c = zcells.get((ds, col, 12))
    out = []
    for e in (((c or {}).get("gpu") or {}).get("nvcomp_zstd") or []):
        # Only the reported levels. A leg may measure more; plotting whatever a leg happens to hold
        # would let the figure's baseline set change with the data rather than with a decision.
        if e.get("zstd_level") not in PAPER_ZSTD_LEVELS:
            continue
        if e.get("supported") and e.get("decode_gib_s") and e.get("compression_ratio"):
            out.append((e["compression_ratio"], e["decode_gib_s"] * GIB_TO_GB,
                        "Zstd (%s)" % e.get("zstd_level")))
    return _pareto(out)


def sw_points(sw, ds, col):
    """gANS and both Bitcomp variants for one column, from the MATERIALIZE+SW leg.

    NOT Pareto-filtered across the three. They are three distinct codecs -- an entropy coder
    and two Bitcomp modes -- so each is its own baseline, unlike the Engine's four codecs, which
    are four settings of one fixed-function unit and are pooled accordingly. Pooling these
    dropped Bitcomp-default from the figure entirely on every column, since gANS beats it on both
    axes, which left a legend entry with no mark behind it.

    EVERY CHUNK SIZE, not just the 256 KiB cell. This read only the top-level `codecs` block and
    its docstring asserted "each codec contributes one measured configuration per column, so there
    is nothing to filter within one" -- which was simply false: the producer records a five-size
    `chunk_sweep`, and de_points has always iterated the Engine's. So the fixed-function unit was
    plotted at its best of twenty configurations while the three software codecs were pinned to one
    of five, in a figure whose stated basis is "every technique at its best configuration on each
    column". It cost the baselines 4.4 to 13.9% and it cost them in our favour. Each codec is still
    reduced to its own best rather than pooled across the three, for the reason above.
    """
    row = sw.get((ds, col)) or {}
    passes = [row.get("codecs") or {}] + [p.get("codecs") or {}
                                          for p in (row.get("chunk_sweep") or [])]
    best = {}
    for codecs in passes:
        for name, e in codecs.items():
            if not e.get("supported") or not e.get("valid") or not e.get("ratio"):
                continue
            rate = _rate(e, _payload(row))
            if rate and rate > best.get(name, (0, 0))[1]:
                best[name] = (e["ratio"], rate)
    return [(r, rate, name) for name, (r, rate) in best.items()]


def baseline_points(root, chip, ds, col, zcells=None, sw=None):
    """Every baseline configuration measured for one column on one chip."""
    pts = de_points(root, chip, ds, col)
    if zcells is not None:
        pts += zstd_points(zcells, ds, col)
    if sw is not None:
        pts += sw_points(sw, ds, col)
    return pts
