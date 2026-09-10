# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Re-derive every numeric claim in the paper's Sections 2, 3 and 4, and check it.

WHY THIS EXISTS. Those sections' numbers were derived in ad-hoc sessions and then typed into
prose. That is exactly how the project's recurring defect happens: a number outlives the state it
was measured in, and nobody can tell which. This script recomputes each one from committed data,
writes them to results/paper-claims.json for the record, and with --check compares them against
what the paper currently asserts.

    uv run experiments/paper_claims.py            # derive + write results/paper-claims.json
    uv run experiments/paper_claims.py --check     # non-zero exit on any drift

DECLARED vs DERIVED. `DECLARED` below is what the paper says today, transcribed by hand and cited
to a section. Everything else is computed. A mismatch means either the prose is stale or the data
moved, and the script does not guess which -- it prints both and fails.

SOURCES, all inside this repository:
  results/resource-probe-20260818/<chip>_kernel_resources.jsonl   one capture per chip, 120 configs
  results/resource-probe-20260818/<chip>_device_properties.json   per-SM budgets
  results/campaign-20260820/<chip>/sweep_summary_<label>_<policy>.json   the coarsening campaign
"""
import argparse
import glob
import json
import math
import os
import re
import statistics as st
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "results", "resource-probe-20260818")
CAMPAIGN = os.path.join(ROOT, "results", "campaign-20260820")
OUT = os.path.join(ROOT, "results", "paper-claims.json")

CHIPS_CAMPAIGN = ["b300", "h100", "a100"]          # the l40s leg never landed
CHIPS_PROBE = ["a100", "l40s", "h100", "b300"]
GEN_PREFIXES = ("tpch-sf15", "tpch-sf45", "tpch-sf263")
CAMPAIGN_TARGETS = {
    ("fineweb2", "fineweb2-zh", "text"),
    ("wikipedia", "wikipedia", "text"),
    ("codeparrot", "codeparrot", "content"),
    ("android", "loghub-android", "line"),
    ("url", "clickbench", "URL"),
    ("thunderbird", "loghub-thunderbird", "line"),
    ("title", "clickbench", "Title"),
    ("hdfs", "loghub-hdfs", "line"),
    ("spark", "loghub-spark", "line"),
    ("windows", "loghub-windows", "line"),
    ("caddress", "tpch-sf263", "c_address"),
    ("lcomment", "tpch-sf15", "l_comment"),
    ("oclerk", "tpch-sf45", "o_clerk"),
    ("shipinstruct", "tpch-sf15", "l_shipinstruct"),
    ("pscomment", "tpch-sf15", "ps_comment"),
}
DG_COORDS = {(k, t, b)
             for k in range(1, 9) for t in (64, 128, 256) for b in (1, 2, 4, 6, 8)}
DH_COORDS = {(k, t, b, h)
             for k in range(1, 9) for t in (64, 128, 256) for b in (1, 2, 4, 6, 8)
             for h in range(2, min(k, 4) + 1)}

# Model constants. Each is a hardware allocation rule, not a tuning choice.
REGS_PER_SM = 65536
WARP = 32
REG_GRANULE_PER_WARP = 256      # -> 8 registers per thread
SHARED_GRANULE = 128            # a block's total shared allocation rounds up to this
PER_BLOCK_RESERVED = 1024       # runtime reservation, in neither static_shared nor M

# What the paper asserts today. Keys are checked; `tol` is absolute unless it ends in '%'.
# DECLARED is now the SMALL residue: values the paper does not cite through a generated macro.
# Anything in TEX below needs no declaration -- the emitted file is the contract, and verify.sh
# fails if the committed file differs from a fresh derivation. That removes the failure codex
# found in pass 3: a declaration and a derivation sharing one bug cannot disagree, so checking
# them against each other proved nothing.
#
# Tolerance 0 everywhere: every value is already rounded to its reporting precision, so a
# nonzero tolerance spans whole display units and would hide a real regression rather than
# absorb floating-point noise.
# THREE ENTRIES REMOVED 2026-08-23, and why, so they are not restored as a fix:
#   occ.l40s_shared_limited (77), occ.h100_regs_limited (116), occ.a100_shared_limited (35)
# Section 3.1 states no per-chip limiter count -- it argues the feasibility rule B*M <= A
# qualitatively and cites only \claimOccConfigs and \claimOccExact, both generated. So these
# asserted numbers the paper does not make, which is not a check that can pass or fail
# meaningfully. They were also measured on the 480-configuration standalone probe (120 per chip)
# while the emitted macros already read the suite leg's 1560 (390 per chip), so on the current
# basis they read 306, 374 and 140. The counts are still derived below and land in
# results/paper-claims.json; promote them to TEX if a sentence ever needs them.
DECLARED = {
    "s3.regs_per_sm":              (65536, 0, "3.1"),
}

derived = {}
notes = {}


def put(key, value, note):
    derived[key] = value
    notes[key] = note


# ---------------------------------------------------------------- probe / occupancy
def reg_alloc_for_usage(r):
    """Registers ALLOCATED per thread for a warp that USES r. Rounds UP to the granule."""
    if r <= 0:
        return 0
    return (-(-(r * WARP) // REG_GRANULE_PER_WARP) * REG_GRANULE_PER_WARP) // WARP


def reg_ceiling(quotient):
    """The largest per-thread count a (T,B) budget admits. Rounds DOWN to the granule: you
    cannot allocate a granule you do not have room for. Confusing this with the round-up above
    is what made the checker disagree with a correct paper value of 40 at B=6."""
    return int(quotient) // (REG_GRANULE_PER_WARP // WARP) * (REG_GRANULE_PER_WARP // WARP)


def probe_paths(chip):
    """Both layouts. A standalone probe capture names its files <chip>_*, while a suite leg lands
    them unprefixed inside its own <chip>/ directory. Returning both candidate shapes lets one
    reducer read either without the caller needing to know which produced the data."""
    return ((os.path.join(PROBE, "%s_kernel_resources.jsonl" % chip),
             os.path.join(PROBE, "%s_device_properties.json" % chip)),
            (os.path.join(PROBE, chip, "kernel_resources.jsonl"),
             os.path.join(PROBE, chip, "device_properties.json")))


def load_probe():
    rows, shared_per_sm = [], {}
    for chip in CHIPS_PROBE:
        f = dp = None
        for cand_f, cand_dp in probe_paths(chip):
            # A kernel file without its device budgets is not a usable capture. Keep looking for
            # the other supported layout instead of selecting a partial first candidate.
            if os.path.isfile(cand_f) and os.path.isfile(cand_dp):
                f, dp = cand_f, cand_dp
                break
        if f is None:
            continue
        for line in open(f):
            line = line.strip()
            if line:
                d = json.loads(line)
                if not isinstance(d, dict):
                    sys.exit("probe %s contains a non-object row" % chip)
                d["_chip"] = chip
                rows.append(d)
        if dp and os.path.exists(dp):
            p = json.load(open(dp))
            if not isinstance(p, dict):
                sys.exit("probe %s device properties are not an object" % chip)
            shared_per_sm[chip] = p.get("shared_per_sm_bytes") or p.get("shared_per_block_optin_bytes")
    return rows, shared_per_sm


def require_complete_probe(rows, shared_per_sm):
    """An explicitly selected probe must contain one whole, uniform capture for every chip."""
    h1 = {(k, t, b, 1)
          for k in range(1, 9) for t in (64, 128, 256) for b in (1, 2, 4, 6, 8)}
    h_aware = {(k, t, b, h)
               for k in range(1, 9) for t in (64, 128, 256) for b in (1, 2, 4, 6, 8)
               for h in range(1, min(k, 4) + 1)}
    inventory_kinds = set()
    for chip in CHIPS_PROBE:
        sub = [row for row in rows if row.get("_chip") == chip]
        if any(row.get("buildable") is not True for row in sub):
            sys.exit("probe %s contains an unbuildable coordinate" % chip)
        coords = [(row.get("tokens_per_thread"), row.get("block_threads"),
                   row.get("min_blocks"), row.get("held_high", 1)) for row in sub]
        try:
            coord_set = set(coords)
        except TypeError:
            sys.exit("probe %s contains a non-scalar coordinate" % chip)
        if len(coords) != len(coord_set):
            sys.exit("probe %s repeats a resource coordinate" % chip)
        if coord_set == h1:
            inventory_kinds.add("h1")
        elif coord_set == h_aware:
            inventory_kinds.add("h-aware")
        else:
            sys.exit("probe %s is incomplete: %d unique coordinates (wanted exactly 120 or 390)"
                     % (chip, len(coord_set)))
        shared = shared_per_sm.get(chip)
        if not isinstance(shared, int) or isinstance(shared, bool) or shared <= 0:
            sys.exit("probe %s has no positive shared-memory budget" % chip)
        flat, nested = probe_paths(chip)
        flat_complete = all(os.path.isfile(path) for path in flat)
        nested_complete = all(os.path.isfile(path) for path in nested)
        if not flat_complete and nested_complete:
            marker_path = os.path.join(PROBE, chip, "suite-complete.txt")
            try:
                marker = open(marker_path).read()
            except OSError as error:
                sys.exit("suite probe %s has no readable completion marker: %s" % (chip, error))
            if "failed_stages:" in marker or "stage_LADDER_rc: 0" not in marker:
                sys.exit("suite probe %s has no successful LADDER completion record" % chip)
    if len(inventory_kinds) != 1:
        sys.exit("probe inputs mix H=1 and H-aware inventories across chips")


def occupancy(rows, shared_per_sm):
    usable = [r for r in rows if r.get("buildable") and r.get("blocks_per_sm")
              and r.get("block_threads") and r.get("regs_per_thread")
              and r["_chip"] in shared_per_sm]

    def pred(r, reg_round=True, reserve=True, shared_gran=True):
        T = r["block_threads"]
        regs = reg_alloc_for_usage(r["regs_per_thread"]) if reg_round else r["regs_per_thread"]
        sh = (r.get("static_shared_bytes") or 0) + (PER_BLOCK_RESERVED if reserve else 0)
        if sh and shared_gran:
            sh = -(-sh // SHARED_GRANULE) * SHARED_GRANULE
        by_r = REGS_PER_SM // (regs * T)
        by_s = shared_per_sm[r["_chip"]] // sh if sh else 10 ** 6
        by_w = (r.get("max_warps_per_sm") or 64) // max(1, T // WARP)
        return min(by_r, by_s, by_w), by_r, by_s, by_w

    put("occ.configs", len(usable), "unique kernel configurations, one capture per chip")
    put("occ.exact", sum(1 for r in usable if pred(r)[0] == r["blocks_per_sm"]),
        "formula == cuOccupancyMaxActiveBlocksPerMultiprocessor (NOT observed residency)")
    put("occ.exact_no_reservation",
        sum(1 for r in usable if pred(r, reserve=False)[0] == r["blocks_per_sm"]),
        "ablation: drop the 1 KiB per-block reservation")
    put("occ.exact_no_shared_granule",
        sum(1 for r in usable if pred(r, shared_gran=False)[0] == r["blocks_per_sm"]),
        "ablation: drop the 128 B shared-allocation granule")
    put("occ.exact_no_reg_granule",
        sum(1 for r in usable if pred(r, reg_round=False)[0] == r["blocks_per_sm"]),
        "ablation: drop register granule rounding")

    for chip in CHIPS_PROBE:
        sub = [r for r in usable if r["_chip"] == chip]
        if not sub:
            continue
        lim = defaultdict(int)
        for r in sub:
            _, br, bs, bw = pred(r)
            lo = min(br, bs, bw)
            if br == lo:
                lim["regs"] += 1
            if bs == lo:
                lim["shared"] += 1
            if bw == lo:
                lim["warps"] += 1
        for term in ("regs", "shared", "warps"):
            put("occ.%s_%s_limited" % (chip, term), lim[term],
                "configs where %s is a limiting term (ties counted in each)" % term)
        put("occ.%s_configs" % chip, len(sub), "configs for this chip")
    # Registers observed, to keep the "multiple of 8" claim honest
    vals = sorted({r["regs_per_thread"] for r in usable})
    put("occ.regs_observed", vals, "distinct regs_per_thread across all configs")
    put("occ.regs_all_multiple_of_8", all(v % 8 == 0 for v in vals),
        "FALSE means some kernel reports a non-granule register count")


# ---------------------------------------------------------------- model arithmetic
def model_arithmetic(shared_per_sm):
    K, S, T, B, W = 6, 16, 256, 4, 8
    M = T * (K * (S + 4) + 1)
    put("s3.regs_per_sm", REGS_PER_SM, "identical on every device measured")
    put("s3.M_bytes_K6_S16_T256", M, "M = T*(K*(S+4)+1) at the shipped point")
    block = -(-(M + PER_BLOCK_RESERVED) // SHARED_GRANULE) * SHARED_GRANULE
    put("s3.block_kib_with_reserve", round(block / 1024, 2), "M + 1 KiB reservation, granule-rounded")
    put("s3.four_blocks_kib", round(4 * block / 1024, 2), "four resident blocks")
    put("s3.regs_T256_B4", reg_ceiling(REGS_PER_SM / (T * B)), "granule-floored quotient at B=4")
    put("s3.quotient_T256_B6", round(REGS_PER_SM / (T * 6), 2), "raw quotient at B=6")
    put("s3.alloc_T256_B6", reg_ceiling(REGS_PER_SM / (T * 6)), "granule-floored at B=6")
    put("s3.low_plane_kib_op12", 2 ** 12 * W // 1024, "2^b * W")
    put("s3.low_plane_kib_op16", 2 ** 16 * W // 1024, "2^b * W")
    put("s3.fits_devices",
        {c: (4 * block <= shared_per_sm[c]) for c in sorted(shared_per_sm)},
        "does the four-block shipped point fit each device's shared carveout")


# ---------------------------------------------------------------- campaign
def rate_of(cell, which="auto"):
    g = cell["gpu"]
    nb = g["decoded_bytes"]
    per = {}
    for k in g.get("kernels") or []:
        it = k.get("decode_ns_iters") or []
        if it:
            per[k["kernel"]] = (nb / min(it), k.get("role"))
    if not per:
        return None
    if which == "auto":
        v = per.get(g.get("auto_kernel"))
        return v[0] if v else None
    if which == "prod":
        c = [v[0] for v in per.values() if v[1] == "production"]
        return max(c) if c else None
    return max(v[0] for v in per.values())


def load_campaign():
    out = {}
    for chip in CHIPS_CAMPAIGN:
        d = os.path.join(CAMPAIGN, chip)
        if not os.path.isdir(d):
            continue
        for f in sorted(glob.glob(os.path.join(d, "sweep_summary_*_boost.json"))):
            for c in json.load(open(f)):
                out[(chip, c["dataset_id"], c["column"], c["bits"])] = c
    return out


def require_complete_suite_campaign():
    """Refuse a suite root unless all paper-consumed chips contain the exact boost corpus."""
    expected_cells = {(ds, col, bits)
                      for _, ds, col in CAMPAIGN_TARGETS for bits in (12, 16)}
    for chip in CHIPS_CAMPAIGN:
        directory = os.path.join(CAMPAIGN, chip)
        if not os.path.isdir(directory):
            sys.exit("suite campaign is incomplete: missing chip directory %s" % chip)

        marker_path = os.path.join(directory, "suite-complete.txt")
        targets_path = os.path.join(directory, "campaign_targets.txt")
        clock_path = os.path.join(directory, "clock-state.txt")
        try:
            marker = open(marker_path).read()
            target_rows = [tuple(line.split()) for line in open(targets_path) if line.strip()]
            clock = open(clock_path).read()
        except OSError as error:
            sys.exit("suite %s provenance is unreadable: %s" % (chip, error))
        if "failed_stages:" in marker or "stage_GRID_boost_rc: 0" not in marker:
            sys.exit("suite %s has no successful boost GRID completion record" % chip)
        if set(target_rows) != CAMPAIGN_TARGETS or len(target_rows) != len(CAMPAIGN_TARGETS):
            sys.exit("suite %s campaign_targets.txt is not the fixed 15-column corpus" % chip)
        if "mem_pin: FAILED" in clock or not re.search(r"^mem_pin: [1-9][0-9]* MHz$", clock, re.M):
            sys.exit("suite %s has no successful memory-clock pin" % chip)

        observed = []
        for path in sorted(glob.glob(os.path.join(directory, "sweep_summary_*_boost.json"))):
            try:
                cells = json.load(open(path))
            except (OSError, json.JSONDecodeError) as error:
                sys.exit("suite %s boost summary is unreadable: %s" % (chip, error))
            if not isinstance(cells, list):
                sys.exit("suite %s boost summary is not a cell list: %s" % (chip, path))
            for cell in cells:
                if not isinstance(cell, dict):
                    sys.exit("suite %s boost summary contains a non-object cell" % chip)
                identity = (cell.get("dataset_id"), cell.get("column"), cell.get("bits"))
                observed.append(identity)
                gpu = cell.get("gpu")
                kernels = gpu.get("kernels") if isinstance(gpu, dict) else None
                if cell.get("codec") != "onpair" or cell.get("training_seed") != 20260819 \
                        or cell.get("verified") is not True or not isinstance(gpu, dict) \
                        or gpu.get("validated") is not True or gpu.get("verified") is not True \
                        or gpu.get("iterations") != 100 or not isinstance(kernels, list):
                    sys.exit("suite %s boost cell %r is not a full, verified packed-grid result"
                             % (chip, identity))
                dg, dh, timed = set(), set(), set()
                for kernel in kernels:
                    if not isinstance(kernel, dict):
                        continue
                    name = kernel.get("kernel")
                    samples = kernel.get("decode_ns_iters")
                    if not isinstance(samples, list) or len(samples) != 100 \
                            or not all(isinstance(value, int) and not isinstance(value, bool)
                                       and value > 0 for value in samples):
                        continue
                    timed.add(name)
                    match = re.fullmatch(r"onpair_dg_k(\d+)_t(\d+)_b(\d+)", str(name))
                    if match:
                        dg.add(tuple(map(int, match.groups())))
                    match = re.fullmatch(r"onpair_dh_k(\d+)_t(\d+)_b(\d+)_h(\d+)", str(name))
                    if match:
                        dh.add(tuple(map(int, match.groups())))
                if dg != DG_COORDS or dh != DH_COORDS or gpu.get("auto_kernel") not in timed:
                    sys.exit("suite %s boost cell %r lacks the exact timed dg/dh/auto inventory"
                             % (chip, identity))
        try:
            observed_set = set(observed)
        except TypeError:
            sys.exit("suite %s contains a non-scalar cell identity" % chip)
        if len(observed) != len(expected_cells) or observed_set != expected_cells:
            sys.exit("suite %s boost corpus is incomplete: %d cells, %d unique (wanted 30 exact)"
                     % (chip, len(observed), len(observed_set)))


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def campaign_stats(cells):
    is_gen = lambda ds: ds.startswith(GEN_PREFIXES)

    # dg grid on the b300, real columns: K x T x B
    grid = defaultdict(dict)
    for (chip, ds, col, bits), c in cells.items():
        if chip != "b300" or is_gen(ds):
            continue
        nb = c["gpu"]["decoded_bytes"]
        for k in c["gpu"]["kernels"]:
            m = re.fullmatch(r"onpair_dg_k(\d+)_t(\d+)_b(\d+)", k["kernel"])
            it = k.get("decode_ns_iters") or []
            if m and it:
                grid[(ds, col, bits)][tuple(map(int, m.groups()))] = nb / min(it)

    kspread, bl, bh, p90 = [], [], [], defaultdict(list)
    twin = defaultdict(int)
    t128_def = []
    for key, g in grid.items():
        tb = defaultdict(dict)
        kb = defaultdict(dict)
        for (k, t, b), v in g.items():
            tb[(t, b)][k] = v
            kb[(k, t)][b] = v
        for _, ks in tb.items():
            if len(ks) >= 6:
                kspread.append((max(ks.values()) / min(ks.values()) - 1) * 100)
        for (k, t), bs in kb.items():
            for want, sink in (((1, 2, 4), bl), ((4, 6, 8), bh)):
                have = [bs[b] for b in want if b in bs]
                if len(have) == len(want):
                    s = (max(have) / min(have) - 1) * 100
                    sink.append(s)
                    if want == (4, 6, 8):
                        p90[k].append(s)
        # T comparison at fixed (K,B)
        byk = defaultdict(dict)
        for (k, t, b), v in g.items():
            byk[(k, b)][t] = v
        for _, ts in byk.items():
            if {64, 128, 256} <= set(ts):
                t128_def.append((max(ts.values()) / ts[128] - 1) * 100)
        # per-column argmax T
        (bk, bt, bb) = max(g, key=lambda kk: g[kk])
        twin[bt] += 1

    put("s4.k_spread_median_pct", round(st.median(kspread), 1), "dg grid, b300, real columns")
    put("s4.k_spread_max_pct", round(max(kspread), 1), "same")
    put("s4.b_low_spread_median_pct", round(st.median(bl), 2), "B in {1,2,4} at fixed (K,T)")
    put("s4.b_high_spread_median_pct", round(st.median(bh), 1), "B in {4,6,8} at fixed (K,T)")
    # NEAREST-RANK p90, stated rather than implied. `v[int(0.9*n)]` selects the 55th of 60, which
    # is not any standard convention and inflated three of four published values (K=5 by 25%).
    def p90_of(v):
        v = sorted(v)
        return v[max(0, math.ceil(0.9 * len(v)) - 1)]
    for k in sorted(p90):
        put("s4.b_p90_k%d_pct" % k, round(p90_of(p90[k]), 1),
            "nearest-rank p90 of the B in {4,6,8} spread (n=%d)" % len(p90[k]))
    for t in (64, 128, 256):
        put("s4.t%d_argmax_count" % t, twin.get(t, 0), "column-preset pairs whose best dg cell uses this T")
    put("s4.t128_median_deficit_pct", round(st.median(t128_def), 2),
        "how far T=128 trails the best T at fixed (K,B)")

    # frac_le8 / mean-length / concentration correlations, per chip and preset
    for chip in CHIPS_CAMPAIGN:
        for bits in (12, 16):
            pts = [(c["gpu"]["frac_le8"], c["gpu"]["dict_mean_len"],
                    c["gpu"].get("access_top4096_frac"), rate_of(c))
                   for (ch, ds, col, b), c in cells.items()
                   if ch == chip and b == bits and not is_gen(ds) and rate_of(c)]
            if len(pts) < 3:
                continue
            fl, ml, t4, rt = zip(*pts)
            put("s4.r_fracle8_%s_op%d" % (chip, bits), round(pearson(fl, rt), 2), "frac_le8 vs shipped rate")
            put("s4.r_meanlen_%s_op%d" % (chip, bits), round(pearson(ml, rt), 2), "mean token length vs rate")
            if bits == 16 and all(v is not None for v in t4):
                put("s4.top4096_min", round(min(t4), 3), "concentration range, real columns, OP-16")
                put("s4.top4096_max", round(max(t4), 3), "same")
                r_t4, r_ml, r_x = pearson(t4, rt), pearson(ml, rt), pearson(ml, t4)
                partial = (r_t4 - r_ml * r_x) / math.sqrt((1 - r_ml ** 2) * (1 - r_x ** 2))
                put("s4.partial_r_top4096_op16_%s" % chip, round(partial, 2),
                    "concentration vs rate on %s, controlling for mean token length" % chip)

    # H: the hoisted high-plane read cap. H>1 can only fire once the long-token queue is deeper
    # than one hoist round of 32, and the expected depth is 32*K*(1-frac_le8). Compare each dh
    # rung against dg (which IS H=1) at the SAME (K,T,B), and only on columns where the queue is
    # deep enough -- a "no effect" on a shallow-queue column measures nothing.
    h_gain, h_live, h_dead = [], 0, 0
    for (chip, ds, col, bits), c in cells.items():
        if is_gen(ds):
            continue
        nb = c["gpu"]["decoded_bytes"]
        fle8 = c["gpu"].get("frac_le8")
        base, held = {}, defaultdict(dict)
        for k in c["gpu"]["kernels"]:
            it = k.get("decode_ns_iters") or []
            if not it:
                continue
            m = re.fullmatch(r"onpair_dg_k(\d+)_t(\d+)_b(\d+)", k["kernel"])
            if m:
                base[tuple(map(int, m.groups()))] = nb / min(it)
                continue
            m = re.fullmatch(r"onpair_dh_k(\d+)_t(\d+)_b(\d+)_h(\d+)", k["kernel"])
            if m:
                kk, tt, bb, hh = map(int, m.groups())
                held[(kk, tt, bb)][hh] = nb / min(it)
        for (kk, tt, bb), rungs in held.items():
            if (kk, tt, bb) not in base or fle8 is None:
                continue
            depth = 32 * kk * (1 - fle8)
            if depth <= 32:
                h_dead += 1
                continue
            h_live += 1
            b1 = base[(kk, tt, bb)]
            best = max(rungs.values())
            h_gain.append((best / b1 - 1) * 100)
    if h_gain:
        h_gain.sort()
        put("s4.h_configs_queue_deep", h_live, "dh configs whose queue exceeds one hoist round")
        put("s4.h_configs_queue_shallow", h_dead, "dh configs where H>1 structurally cannot fire")
        put("s4.h_best_gain_median_pct", round(st.median(h_gain), 2),
            "best H rung against H=1 at the same (K,T,B), deep-queue configs only")
        put("s4.h_best_gain_p90_pct", round(h_gain[max(0, math.ceil(0.9*len(h_gain))-1)], 2),
            "same, nearest-rank 90th percentile")
        put("s4.h_best_gain_max_pct", round(h_gain[-1], 2), "same, maximum")
        put("s4.h_configs_improved", sum(1 for g in h_gain if g > 0.5),
            "deep-queue configs where some H>1 beats H=1 by more than the 0.5% noise floor")

    # preset flip: worst OP-16 penalty on a real column.
    # BEST basis, not auto. sec:evaluation reports every technique at its best configuration, so a
    # penalty measured through the shipped selector would compare two arbitrary kernel choices
    # rather than the two codecs. On auto this read 51%; on best it is 38.7% (a100, wikipedia).
    worst = 0.0
    for chip in CHIPS_CAMPAIGN:
        for (ch, ds, col, b), c in cells.items():
            if ch != chip or b != 12 or is_gen(ds):
                continue
            c16 = cells.get((chip, ds, col, 16))
            r12, r16 = rate_of(c, "best"), rate_of(c16, "best") if c16 else None
            if r12 and r16 and r16 < r12:
                worst = max(worst, (1 - r16 / r12) * 100)
    put("s4.preset_flip_worst_pct", round(worst, 1), "largest OP-16 penalty on a real column")

    # clock policy: boost:locked on the shipped path
    for chip in CHIPS_CAMPAIGN:
        rr = []
        for f in sorted(glob.glob(os.path.join(CAMPAIGN, chip, "sweep_summary_*_locked.json"))):
            for lc in json.load(open(f)):
                bc = cells.get((chip, lc["dataset_id"], lc["column"], lc["bits"]))
                rb, rl = (rate_of(bc) if bc else None), rate_of(lc)
                if rb and rl:
                    rr.append(rb / rl)
        if rr:
            put("s4.boost_locked_median_%s" % chip, round(st.median(rr), 3),
                "boost:locked on the shipped kernel")

    # headline rates, real subset only
    for chip in CHIPS_CAMPAIGN:
        for bits in (12, 16):
            rs = [(rate_of(c), ds + "/" + col) for (ch, ds, col, b), c in cells.items()
                  if ch == chip and b == bits and not is_gen(ds) and rate_of(c)]
            if rs:
                v, who = max(rs)
                put("s4.peak_shipped_%s_op%d" % (chip, bits), round(v),
                    "GB/s, shipped selector, real columns; %s" % who)



# Section 4's launch-shape and hoist claims. These are derived from ONE named column, Loghub
# Windows at OnPair-12, because that is what fig_grid and fig_hoist draw: a median over ten
# columns leaves a reader unable to tell whether the column behind a point changed, and a prose
# number derived on a different basis from its figure is how the two drift apart.
HOIST_COL = ("loghub-windows", "line")
HOIST_T = 256


def launch_stats(cells, rows):
    key = ("b300", HOIST_COL[0], HOIST_COL[1], 12)
    c = cells.get(key)
    if not c:
        print("WARNING: %s absent; section 4 launch claims not derived" % (HOIST_COL,),
              file=sys.stderr)
        return
    nb = c["gpu"]["decoded_bytes"]
    R = {k["kernel"]: nb / min(k["decode_ns_iters"])
         for k in c["gpu"]["kernels"] if k.get("decode_ns_iters")}

    # Where the K optimum sits for each block width, at the unconstrained launch bound.
    for T in (64, 128, 256):
        pts = [(K, R[f"onpair_dg_k{K}_t{T}_b1"]) for K in range(1, 9)
               if f"onpair_dg_k{K}_t{T}_b1" in R]
        if pts:
            put("s4.peak_k_t%d" % T, max(pts, key=lambda kv: kv[1])[0],
                "K at which %s peaks, T=%d, B=1" % ("/".join(HOIST_COL), T))

    # The hoist, at the coordinate the prose works through.
    K = 6
    b1 = R.get(f"onpair_dg_k{K}_t{HOIST_T}_b1")
    b8 = R.get(f"onpair_dg_k{K}_t{HOIST_T}_b8")
    hs = [R[n] for h in range(2, 5)
          for n in [f"onpair_dh_k{K}_t{HOIST_T}_b{8}_h{h}"] if n in R]
    if b1 and b8 and hs:
        put("s4.hoist_b8_h1", round(b8), "GB/s, B=8 H=1 baseline at K=6 T=256")
        put("s4.hoist_b8_best", round(max(hs)), "GB/s, best H>1 at the same coordinate")
        put("s4.hoist_b1", round(b1), "GB/s, B=1 at the same K and T, no hoist")
        put("s4.hoist_gain_pct", round(100 * (max(hs) / b8 - 1)), "% the hoist lifts its own baseline")
        put("s4.hoist_of_b1_pct", round(100 * max(hs) / b1),
            "% of the B=1 rate the best hoist configuration reaches")
    # Flatness where registers are not scarce: H changes nothing at B=1 or B=4.
    for B in (1, 4):
        v = [R[n] for h in range(1, 5)
             for n in [(f"onpair_dg_k{K}_t{HOIST_T}_b{B}" if h == 1
                        else f"onpair_dh_k{K}_t{HOIST_T}_b{B}_h{h}")] if n in R]
        if len(v) == 4:
            put("s4.hoist_flat_b%d_pct" % B, round(100 * (max(v) / min(v) - 1), 1),
                "%% spread across H=1..4 at B=%d, K=6, T=256" % B)

    # Registers and residency at the two regimes, from the probe rather than the model.
    for B in (1, 4, 8):
        for r in rows:
            if (r.get("_chip") == "b300" and r.get("tokens_per_thread") == K
                    and r.get("block_threads") == HOIST_T and r.get("min_blocks") == B
                    and r.get("held_high", 1) == 1):
                put("s4.regs_b%d" % B, r["regs_per_thread"],
                    "registers/thread, K=6 T=256 B=%d" % B)
                put("s4.blocks_b%d" % B, r["blocks_per_sm"],
                    "resident blocks/SM at the same coordinate")
                break


def field_stats():
    """Section 5's field comparison: FastPair against every baseline configuration measured.

    WHY THIS IMPORTS figures/suite.py. That module already defines at-rest ratio, min-of-N rate
    and the three baseline point sets, and fig_perf_real asserts the dominance property from
    them. A second copy of those rules here is how the number in the prose and the number in the
    figure come to disagree, which has happened in this repository before. suite.py has no third-
    party dependencies, so importing it does not change this script's dependency set.

    THE TEST IS PER COLUMN, AND ON THE REAL COLUMNS. A codec's ratio is a property of the data,
    so comparing our mark on one column against a baseline measured on another is not a
    comparison. The generated five are pooled into no real-data claim anywhere in the paper, and
    they are where the single counterexample lives -- gANS beats OnPair-16 on c_address, random
    characters that a pair-merging dictionary cannot merge. It is derived and reported here
    rather than filtered out, because the scope belongs in the sentence, not in a filter.
    """
    sys.path.insert(0, os.path.join(ROOT, "figures"))
    import suite as S
    from pathlib import Path

    # HONOUR --suite-root. The rest of this script reads CAMPAIGN, so resolving the leg
    # independently here would let one invocation derive Section 4 from one campaign and Section 5
    # from another and report both as one set of claims.
    root = Path(CAMPAIGN) if os.path.isdir(CAMPAIGN) else S.latest_root()
    brt = S.baselines_root()
    if root is None:
        print("WARNING: no suite root; section 5 field claims not derived", file=sys.stderr)
        return
    chip = "b300"                     # the DE is Blackwell-only, so the field panel is one chip
    op = S.cells(root, chip, "boost", "onpair")
    fs = S.cells(root, chip, "boost", "fsst12")
    zc = S.cells(root, chip, "boost", "zstd")
    sw = S.sw_rows(S.sw_root_for(chip), chip)
    if not (op and sw):
        print("WARNING: field legs incomplete; section 5 field claims not derived", file=sys.stderr)
        return

    def ours(ds, col):
        out = []
        for cfg, store, bits in (("OnPair-12", op, 12), ("OnPair-16", op, 16), ("FSST-12", fs, 12)):
            c = store.get((ds, col, bits))
            # SHIPPED granularity, because the rate beside it is the shipped selector's. The
            # sidecar is sized per batch of 32*K codes and the selector mostly runs K=4, not the
            # K=6 that used to be charged here regardless.
            r, t = S.ratio(c, S.kernel_tok_per_batch(c, "shipped")), S.rate_gb_s(c)
            if r and t:
                out.append((r, t, cfg))
        return out

    # Raw configuration count per column, BEFORE the per-baseline Pareto reduction the figure
    # draws. The reduction cannot change a verdict -- a point beaten on both axes by another of
    # the same baseline cannot dominate anything the beater does not -- so the honest count to
    # quote as "what it was tested against" is the measured one.
    de_raw = 0
    for r in S.de_rows(root, chip):
        if (r.get("dataset_id"), r.get("column")) == (S.REAL[0][1], S.REAL[0][2]):
            seen = set()
            for chunk, codecs in ([(r.get("chunk_bytes"), r.get("codecs") or {})]
                                  + [(p.get("chunk_bytes"), p.get("codecs") or {})
                                     for p in (r.get("chunk_sweep") or [])]):
                for name, e in codecs.items():
                    if e.get("valid") and not e.get("validation_failed"):
                        seen.add((name, chunk))
            de_raw = len(seen)
    z_raw = len(S.zstd_points(zc, S.REAL[0][1], S.REAL[0][2]))
    # THE SOFTWARE CODECS ALSO GET A CHUNK SWEEP, and it has to be counted the same way the DE's
    # is directly above, or the total understates what was measured. This counted the top-level
    # `codecs` block alone -- three configurations against the fifteen actually recorded -- for the
    # same reason suite.sw_points only plotted one of five chunk sizes. The count is a disclosure
    # about search-size asymmetry, so undercounting the baselines' half misstates the disclosure.
    _sw_row = sw.get((S.REAL[0][1], S.REAL[0][2])) or {}
    _sw_seen = set()
    for chunk, codecs in ([(_sw_row.get("chunk_bytes"), _sw_row.get("codecs") or {})]
                          + [(p.get("chunk_bytes"), p.get("codecs") or {})
                             for p in (_sw_row.get("chunk_sweep") or [])]):
        for name, e in codecs.items():
            if e.get("supported") and e.get("valid"):
                _sw_seen.add((name, chunk))
    sw_raw = len(_sw_seen)
    put("s5.field_configs_per_col", de_raw + z_raw + sw_raw,
        "baseline configurations measured per column: DE codecs x chunk sizes, Zstd levels, "
        "nvCOMP software codecs")

    marks = dominated = 0
    beaten_on_rate = 0            # columns where SOME baseline is faster, at any ratio
    fastest = (0.0, 0.0, "")      # the quickest baseline anywhere on the real panel
    biggest = (0.0, 0.0, "")      # and the one that stores the most
    biggest_col = None            # which column that was, so ours on it can be quoted beside it
    de_biggest = (0.0, 0.0, "")   # the engine alone, which is what Section 6 discusses
    for _, ds, col in S.REAL:
        base = S.baseline_points(root, chip, ds, col, zc, sw)
        if not base:
            continue
        best_rate = max(base, key=lambda p: p[1])
        best_ratio = max(base, key=lambda p: p[0])
        if best_rate[1] > fastest[1]:
            fastest = best_rate
        if best_ratio[0] > biggest[0]:
            biggest, biggest_col = best_ratio, (ds, col)
        de = S.de_points(root, chip, ds, col)
        if de:
            d = max(de, key=lambda p: p[0])
            if d[0] > de_biggest[0]:
                de_biggest = d
        mine = ours(ds, col)
        if mine and best_rate[1] > max(t for _, t, _ in mine):
            beaten_on_rate += 1
        for r, t, _cfg in mine:
            marks += 1
            if any(b[0] >= r and b[1] > t for b in base):
                dominated += 1
    # ---- Section 5.1 and 5.2 headline sentences, so the prose carries no literals. -----------
    # Every one of these was a hardcoded number in the text and every one of them moved when the
    # compression-ratio basis changed on 2026-08-30. The column NAME is derived too: "the fastest
    # column is Loghub Windows" is a claim about the data, not a fact about the corpus.
    def _our_rate(ds, col, bits, store=None):
        """ORACLE rate, not the shipped selector's. Section 5 reports every technique "at its best
        configuration on each column", so the span the prose quotes is best_rate_gb_s. The selector
        rate is 4 to 9% lower and is the subject of its own claim; using it here would silently
        restate the headline on a basis Section 5 does not describe."""
        c = (store if store is not None else op).get((ds, col, bits))
        return S.best_rate_gb_s(c) if c else None

    def _span(bits):
        rr = [t for _, ds, col in S.REAL for t in [_our_rate(ds, col, bits)] if t]
        return (round(min(rr)), round(max(rr))) if rr else (0, 0)

    lo12, hi12 = _span(12)
    lo16, hi16 = _span(16)
    put("s5.b300_real_min_twelve", lo12, "B300, OnPair-12: slowest of the ten real columns")
    put("s5.b300_real_max_twelve", hi12, "and the quickest")
    put("s5.b300_real_min_sixteen", lo16, "B300, OnPair-16: slowest of the ten real columns")
    put("s5.b300_real_max_sixteen", hi16, "and the quickest")

    # The fastest (column, preset) pair on the B300, and what sits beside it on that column.
    best = (0.0, None, None)
    for _, ds, col in S.REAL:
        for bits in (12, 16):
            t = _our_rate(ds, col, bits)
            if t and t > best[0]:
                best = (t, (ds, col), bits)
    if best[1]:
        bds, bcol = best[1]
        # LaTeX-ready, because the prose says "Loghub \texttt{Windows}" and a bare id would
        # render as tpch-sf15/l_comment mid-sentence. LABEL is the corpus's own short name.
        label = next((lab for lab, d, c in S.REAL if (d, c) == (bds, bcol)), bcol)
        pretty = {"windows": "Loghub \\texttt{Windows}", "spark": "Loghub \\texttt{Spark}",
                  "hdfs": "Loghub \\texttt{HDFS}", "android": "Loghub \\texttt{Android}",
                  "thunderbird": "Loghub \\texttt{Thunderbird}",
                  "url": "ClickBench \\texttt{URL}", "title": "ClickBench \\texttt{Title}",
                  "lcomment": "TPC-H \\texttt{l\\_comment}",
                  "pscomment": "TPC-H \\texttt{ps\\_comment}",
                  "shipinstruct": "TPC-H \\texttt{l\\_shipinstruct}",
                  "oclerk": "TPC-H \\texttt{o\\_clerk}"}.get(label, label)
        put("s5.fastest_column", pretty,
            "the fastest real column on the B300, as the prose names it")
        put("s5.fastest_column_rate", round(best[0]), "its rate")
        put("s5.fastest_column_preset", "OnPair-%d" % best[2], "and the preset that reaches it")
        de = S.de_points(root, chip, bds, bcol)
        if de:
            put("s5.fastest_column_de_rate", round(max(p[1] for p in de)),
                "the engine's best codec and chunk size on that same column")
        h100_op = S.cells(root, "h100", "boost", "onpair")
        h = _our_rate(bds, bcol, best[2], store=h100_op)
        if h:
            put("s5.fastest_column_h100_rate", round(h),
                "and an H100 on it, which is above the newer part's engine")

    # ---- Section 5.2: how each chip stands against the B300's engine, per real column. --------
    # These moved when the engine went onto the payload-only basis and gained two chunk sizes: it
    # got faster, so it clears one more L40S column than the prose said.
    put("s5.real_columns", len(S.REAL), "real columns in the corpus")
    de_best = {}
    for _, ds, col in S.REAL:
        d = S.de_points(root, chip, ds, col)
        if d:
            de_best[(ds, col)] = max(p[1] for p in d)
    for other in ("h100", "a100", "rtxpro", "l40s"):
        oroot = S.chip_root(other) or root
        ostore = S.cells(oroot, other, "boost", "onpair")
        beat = seen = short_log = 0
        for _, ds, col in S.REAL:
            d = de_best.get((ds, col))
            t = _our_rate(ds, col, 12, store=ostore)
            if not (d and t):
                continue
            seen += 1
            if t > d:
                beat += 1
            elif "loghub" in ds:
                short_log += 1
        if seen:
            # QUANTIFIER, NOT A COUNT. The prose says "all ten real columns"; that sentence stays
            # readable if the count falls, which is exactly why it gets an alarm rather than a
            # substituted number. See the header emit_tex writes.
            WORDS = {5: "five", 10: "ten", 15: "fifteen"}
            put("s5.beats_de_%s_phrase" % other,
                ("all %s" % WORDS.get(seen, seen)) if beat == seen else
                ("\\claimAlarm{%s clears the B300 engine on only %d of %d real columns}"
                 % (other, beat, seen)),
                "wording for %s's coverage, or an alarm if it stops being all of them" % other)
            put("s5.beats_de_%s" % other, beat,
                "real columns where %s decodes above the B300 engine" % other)
            if beat < seen:
                put("s5.short_loghub_%s_phrase" % other,
                    "all five" if short_log == 5
                    else "%s of the five" % {1: "one", 2: "two", 3: "three",
                                             4: "four"}.get(short_log, short_log),
                    "wording for the Loghub shortfall; a count here is a fact, not a quantifier")
                put("s5.short_loghub_%s" % other, short_log,
                    "of the five Loghub columns, how many %s falls short on" % other)

    # ONE PHRASE FOR THE SENTENCE THAT NAMES THREE CHIPS. Per-chip phrases each guard their own
    # chip, but the prose asserts all three at once, so a regression on the A100 alone would leave
    # the H100's macro happily rendering "all ten". This is the macro that sentence should cite.
    trio = ("h100", "a100", "rtxpro")
    covered = {c: derived.get("s5.beats_de_%s" % c) for c in trio}
    total = derived.get("s5.real_columns")
    if total and all(v is not None for v in covered.values()):
        broken = [c for c, v in covered.items() if v != total]
        put("s5.beats_de_trio_phrase",
            ("all %s" % {10: "ten", 5: "five", 15: "fifteen"}.get(total, total)) if not broken
            else ("\\claimAlarm{%s no longer clear the B300 engine on every real column (%s)}"
                  % (", ".join(broken),
                     "; ".join("%s %d of %d" % (c, covered[c], total) for c in broken))),
            "wording for the H100/A100/RTX PRO sentence; alarms if ANY of the three slips")
    # The L40S count sits in the same sentence, where the surrounding numbers are spelled out.
    l40 = derived.get("s5.beats_de_l40s")
    if l40 is not None:
        put("s5.beats_de_l40s_phrase",
            {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
             7: "seven", 8: "eight", 9: "nine", 10: "ten"}.get(l40, l40),
            "the L40S's count, spelled to match the sentence around it")

    put("s5.field_marks", marks, "our per-column marks on the ten real columns, three codecs each")
    put("s5.field_dominated", dominated,
        "how many a baseline beats at an equal or better at-rest ratio on the same column")
    put("s5.field_beaten_on_rate", beaten_on_rate,
        "real columns where some baseline decodes faster than us at ANY ratio")
    put("s5.field_fastest_rate", round(fastest[1]), "GB/s of the quickest baseline configuration")
    put("s5.field_fastest_ratio", round(fastest[0], 2), "and what it stores at that rate")
    put("s5.field_biggest_ratio", round(biggest[0], 1), "the best at-rest ratio any baseline reaches")
    put("s5.field_biggest_rate", round(biggest[1]), "and the rate it reaches it at")
    put("s5.field_de_biggest_ratio", round(de_biggest[0], 1),
        "best at-rest ratio the Decompression Engine reaches on a real column")
    put("s5.field_de_biggest_rate", round(de_biggest[1]),
        "and its rate there -- the engine's high-ratio arm, not its fastest setting")
    if biggest_col:
        mine = max(ours(*biggest_col), key=lambda p: p[1])
        put("s5.field_biggest_ours_ratio", round(mine[0], 2),
            "our at-rest ratio on the column where that baseline ratio occurs")
        put("s5.field_biggest_ours_rate", round(mine[1]),
            "and our rate there: the trade the positional claim is about")

    # THE OTHER TWO CHIPS, TESTED THE SAME WAY. The software-codec leg also ran on the h100 and
    # l40s, and the test there has to stay PER COLUMN. A tempting shortcut -- a ratio belongs to
    # the data, not the device, so compare the best software ratio anywhere against our worst
    # anywhere and be done -- does not work: the best software ratio on a real column (1.70x,
    # gANS) is above our worst mark (1.62x, FSST-12 on a different column), so the pooled form
    # reports a violation that no column exhibits. That is the pooled-frontier error this
    # comparison already avoids on the b300. No Decompression Engine on either part, so the
    # baseline set there is the three software codecs and the three Zstd levels.
    other = {}
    for c in ("h100", "l40s"):
        cop = S.cells(root, c, "boost", "onpair")
        cfs = S.cells(root, c, "boost", "fsst12")
        czc = S.cells(root, c, "boost", "zstd")
        csw = S.sw_rows(S.sw_root_for(c), c)
        if not (cop and csw):
            continue
        m = d = 0
        for _, ds, col in S.REAL:
            base = S.zstd_points(czc, ds, col) + S.sw_points(csw, ds, col)
            if not base:
                continue
            for cfg, store, bits in (("OnPair-12", cop, 12), ("OnPair-16", cop, 16),
                                     ("FSST-12", cfs, 12)):
                cell = store.get((ds, col, bits))
                r, t = S.ratio(cell, S.kernel_tok_per_batch(cell, "shipped")), S.rate_gb_s(cell)
                if not (r and t):
                    continue
                m += 1
                if any(b[0] >= r and b[1] > t for b in base):
                    d += 1
        other[c] = (m, d)
    if other:
        put("s5.field_other_marks", sum(m for m, _ in other.values()),
            "our marks on the real columns of the two non-Blackwell chips the software leg covered")
        put("s5.field_other_dominated", sum(d for _, d in other.values()),
            "how many of those a baseline beats at an equal or better ratio on the same column")

    # The one generated-column counterexample, worked out in full so the prose can state it.
    gen = {c: (ds, c) for _, ds, c in S.GEN}
    ds, col = gen["c_address"]
    base = S.baseline_points(root, chip, ds, col, zc, sw)
    for r, t, cfg in ours(ds, col):
        tag = {"OnPair-12": "twelve", "OnPair-16": "sixteen"}.get(cfg)
        if not tag:
            continue
        put("s5.caddress_%s_ratio" % tag, round(r, 2), "c_address at %s: at-rest ratio" % cfg)
        put("s5.caddress_%s_rate" % tag, round(t), "c_address at %s: GB/s" % cfg)
    dom = [b for b in base if b[2] == "gANS"]
    if dom:
        put("s5.caddress_gans_ratio", round(dom[0][0], 2), "gANS on c_address: at-rest ratio")
        put("s5.caddress_gans_rate", round(dom[0][1]), "gANS on c_address: GB/s")


# Values the paper cites, as LaTeX macros. THIS REPLACES TRANSCRIPTION: the paper says
# \claimKSpreadMedian, not "80%", so a number cannot go stale in prose. A key absent from
# `derived` is a hard error rather than an empty macro, because an empty macro renders as
# nothing and a missing number is invisible in a PDF.
#
# Grouped, with a description per group and per macro, because the emitted file is read by
# people who know the paper's argument but not this script's internals.
#   (key, macro, format, one-line description)
TEX_GROUPS = [
    ("Launch shape: K, T, B", [
        "How the decoder is configured. K is codes per lane, T threads per block, B the minimum",
        "resident blocks the launch bound demands. B is the one that bites: asking for B blocks",
        "caps registers at R/(T*B), and that cap is what breaks the large-K regime.",
    ], [
        ("s4.k_spread_median_pct", "claimKSpreadMedian", "{:.0f}\\%",
         "median rate spread sweeping K=1..8 at fixed (T,B) -- K is the dominant parameter"),
        ("s4.k_spread_max_pct", "claimKSpreadMax", "{:.0f}\\%",
         "worst such spread: a misparameterised K costs a factor, not a few percent"),
        ("s4.peak_k_t64", "claimPeakKTsixtyfour", "{:d}",
         "K at which rate peaks when T=64 -- the optimum moves with T"),
        ("s4.peak_k_t128", "claimPeakKTonetwoeight", "{:d}", "same at T=128"),
        ("s4.peak_k_t256", "claimPeakKTtwofivesix", "{:d}",
         "same at T=256, which also reaches the highest rate"),
        ("s4.b_low_spread_median_pct", "claimBLowSpread", "{:.2f}\\%",
         "median spread across B in {1,2,4}, where the cap does not bind: the noise floor"),
        ("s4.b_high_spread_median_pct", "claimBHighSpread", "{:.1f}\\%",
         "median spread across B in {4,6,8}, where it starts to"),
        ("s4.b_p90_k4_pct", "claimBPninetyKfour", "{:.1f}\\%",
         "90th percentile of that spread at K=4 -- the tail grows with K as the model predicts"),
        ("s4.b_p90_k5_pct", "claimBPninetyKfive", "{:.1f}\\%", "same at K=5"),
        ("s4.b_p90_k6_pct", "claimBPninetyKsix", "{:.1f}\\%", "same at K=6"),
        ("s4.b_p90_k7_pct", "claimBPninetyKseven", "{:.1f}\\%", "same at K=7"),
        ("s4.t256_argmax_count", "claimTargmaxTwoFiveSix", "{:d}",
         "column-preset pairs (of 20) whose best T is 256"),
        ("s4.t64_argmax_count", "claimTargmaxSixtyFour", "{:d}",
         "pairs whose best T is 64 -- all text-heavy at OnPair-12"),
        ("s4.t128_median_deficit_pct", "claimTonetwoeightDeficit", "{:.1f}\\%",
         "how far T=128 trails the best T: safe everywhere, optimal nowhere"),
        ("s4.regs_b1", "claimRegsBoneLaunch", "{:d}",
         "registers/thread ptxas keeps at B=1, where nothing was demanded of it"),
        ("s4.regs_b8", "claimRegsBeightLaunch", "{:d}",
         "registers/thread at B=8, capped by R/(T*B)"),
        ("s4.blocks_b1", "claimBlocksBone", "{:d}",
         "blocks/SM the scheduler reaches at B=1 anyway, unasked"),
        ("s4.blocks_b8", "claimBlocksBeight", "{:d}",
         "blocks/SM at B=8 once K is large: demanding eight yields fewer"),
    ]),
    ("The hoist (H)", [
        "H holds up to H-1 long-token requests across rounds instead of re-issuing them. The",
        "numbers below are one worked coordinate (K=6, T=256, Loghub Windows) plus corpus-wide",
        "distributions. The point of the first five is that H's apparent win has the wrong",
        "baseline: it is measured against a rate the register cap already collapsed.",
    ], [
        ("s4.hoist_b8_h1", "claimHoistBeightBase", "{:d}",
         "GB/s without the hoist at B=8 -- the collapsed baseline H is credited against"),
        ("s4.hoist_b8_best", "claimHoistBeightBest", "{:d}", "GB/s with the best H at B=8"),
        ("s4.hoist_gain_pct", "claimHoistGain", "{:d}\\%", "the gain those two imply"),
        ("s4.hoist_b1", "claimHoistBone", "{:d}",
         "GB/s at B=1 with NO hoist -- the configuration one would actually ship"),
        ("s4.hoist_of_b1_pct", "claimHoistOfBone", "{:d}\\%",
         "what the best hoist reaches as a fraction of that: a regression, not a gain"),
        ("s4.hoist_flat_b1_pct", "claimHoistFlatBone", "{:.1f}\\%",
         "spread across H=1..4 at B=1: where registers are plentiful, H does nothing"),
        ("s4.hoist_flat_b4_pct", "claimHoistFlatBfour", "{:.1f}\\%", "same at B=4"),
        ("s4.h_configs_queue_deep", "claimHDeepConfigs", "{:d}",
         "configurations whose expected queue is deep enough for H to fire"),
        ("s4.h_configs_queue_shallow", "claimHShallowConfigs", "{:d}", "and those where it is not"),
        ("s4.h_best_gain_median_pct", "claimHGainMedian", "{:.1f}\\%",
         "median gain of the best H rung over H=1, across the corpus"),
        ("s4.h_best_gain_p90_pct", "claimHGainPninety", "{:.1f}\\%", "the 90th percentile of it"),
        ("s4.h_configs_improved", "claimHImproved", "{:d}",
         "configurations improving by more than the 0.5% noise floor"),
    ]),
    ("Dictionary width and residency", [
        "The two presets are two different problems rather than two points on a curve. OnPair-12's",
        "low plane fits in cache and OnPair-16's does not, so what predicts rate changes with it.",
    ], [
        ("s3.low_plane_kib_op12", "claimLowPlaneTwelve", "{:.0f}",
         "KiB of low plane at OnPair-12 -- resident everywhere"),
        ("s3.low_plane_kib_op16", "claimLowPlaneSixteen", "{:.0f}",
         "KiB at OnPair-16 -- cannot be resident, so access concentration starts to matter"),
        ("s4.top4096_min", "claimTopFourKMin", "{:.3f}",
         "lowest fraction of accesses landing in the hottest 4096 dictionary entries"),
        ("s4.top4096_max", "claimTopFourKMax", "{:.3f}", "and the highest"),
        ("s4.partial_r_top4096_op16_b300", "claimPartialRBthreehundred", "{:+.2f}",
         "partial correlation of that concentration with rate on the B300, mean length held fixed"),
        ("s4.partial_r_top4096_op16_h100", "claimPartialRHonehundred", "{:+.2f}", "same on the H100"),
        ("s4.partial_r_top4096_op16_a100", "claimPartialRAonehundred", "{:+.2f}", "same on the A100"),
        ("s4.preset_flip_worst_pct", "claimPresetFlipWorst", "{:.0f}\\%",
         "worst penalty from choosing OnPair-16 on a column that wanted -12"),
    ]),
    ("Occupancy model", [
        "Section 3's allocation rule predicts how many blocks fit per SM from registers, shared",
        "memory and warp slots. These say how often it is exactly right, and which term matters:",
        "dropping a term and re-counting shows what that term was doing.",
    ], [
        ("occ.configs", "claimOccConfigs", "{:d}",
         "kernel configurations measured across every chip"),
        ("occ.exact", "claimOccExact", "{:d}",
         "of them the rule predicts exactly -- the headline is that these two are equal"),
        ("occ.exact_no_reservation", "claimOccNoReserve", "{:d}",
         "how many survive if the per-block runtime reservation is dropped"),
        ("occ.exact_no_shared_granule", "claimOccNoSharedGran", "{:d}",
         "and if shared memory is not rounded to its granule"),
        ("s3.block_kib_with_reserve", "claimBlockKiB", "{:.2f}",
         "KiB one block occupies including that reservation"),
        ("s3.four_blocks_kib", "claimFourBlocksKiB", "{:.0f}",
         "KiB four resident blocks need -- the number that decides whether a chip fits them"),
    ]),
    ("Design model: worked values", [
        "Section 3 works the allocation rule through one concrete configuration. These are the",
        "intermediate quantities that walkthrough names, kept so the prose can cite them rather",
        "than restate arithmetic the reader would otherwise have to trust.",
    ], [
        ("s3.M_bytes_K6_S16_T256", "claimMbytes", "{:d}",
         "bytes of shared memory one block needs at K=6, S=16, T=256"),
        ("s3.regs_T256_B4", "claimRegsBfour", "{:d}",
         "registers/thread the ceiling allows at T=256, B=4"),
        ("s3.quotient_T256_B6", "claimQuotientBsix", "{:.1f}",
         "the raw R/(T*B) quotient at B=6, before rounding to the granule"),
        ("s3.alloc_T256_B6", "claimAllocBsix", "{:d}",
         "what that rounds down to -- the granule is why these differ"),
    ]),
    ("Field comparison: every baseline, per column", [
        "Section 5's positional claim. A baseline gets its whole sweep and is compared to us on",
        "ITS OWN column, because a compression ratio is a property of the data. Our side is the",
        "SHIPPED SELECTOR's rate, not the best kernel, so the claim is about what a deployment",
        "gets. The last four say what the frontier looks like either side of us: the quick",
        "baselines barely compress, and the one that compresses hardest is slow.",
    ], [
        ("s5.field_configs_per_col", "claimFieldConfigs", "{:d}",
         "baseline configurations measured per column: DE codecs x chunks, Zstd levels, nvCOMP sw"),
        ("s5.b300_real_min_twelve", "claimBthreeRealMinTwelve", "{:d}",
         "B300, OnPair-12: slowest of the ten real columns"),
        ("s5.b300_real_max_twelve", "claimBthreeRealMaxTwelve", "{:d}",
         "and the quickest"),
        ("s5.b300_real_min_sixteen", "claimBthreeRealMinSixteen", "{:d}",
         "B300, OnPair-16: slowest of the ten real columns"),
        ("s5.b300_real_max_sixteen", "claimBthreeRealMaxSixteen", "{:d}",
         "and the quickest"),
        ("s5.fastest_column", "claimFastestColumn", "{}",
         "the fastest real column on the B300, LaTeX-ready as the prose names it"),
        ("s5.fastest_column_preset", "claimFastestColumnPreset", "{}",
         "and the preset that reaches it"),
        ("s5.fastest_column_rate", "claimFastestColumnRate", "{:d}",
         "its rate"),
        ("s5.fastest_column_de_rate", "claimFastestColumnDeRate", "{:d}",
         "the engine's best codec and chunk size on that same column"),
        ("s5.fastest_column_h100_rate", "claimFastestColumnHopperRate", "{:d}",
         "and an H100 on it, above the newer part's engine"),
        ("s5.beats_de_trio_phrase", "claimBeatsDeTrioPhrase", "{}",
         "wording for the H100/A100/RTX PRO sentence; alarms if any of the three slips"),
        ("s5.beats_de_l40s_phrase", "claimBeatsDeLfortySPhrase", "{}",
         "the L40S's count, spelled to match the sentence around it"),
        ("s5.beats_de_h100_phrase", "claimBeatsDeHopperPhrase", "{}",
         "wording for the H100's coverage; expands to an alarm if it stops being all of them"),
        ("s5.beats_de_a100_phrase", "claimBeatsDeAmperePhrase", "{}",
         "the same for the A100"),
        ("s5.beats_de_rtxpro_phrase", "claimBeatsDeRtxProPhrase", "{}",
         "and the RTX PRO 6000"),
        ("s5.short_loghub_l40s_phrase", "claimShortLoghubLfortySPhrase", "{}",
         "wording for the L40S's Loghub shortfall"),
        ("s5.real_columns", "claimRealColumns", "{:d}",
         "real columns in the corpus"),
        ("s5.beats_de_h100", "claimBeatsDeHopper", "{:d}",
         "real columns where an H100 decodes above the B300 engine"),
        ("s5.beats_de_a100", "claimBeatsDeAmpere", "{:d}",
         "and an A100"),
        ("s5.beats_de_rtxpro", "claimBeatsDeRtxPro", "{:d}",
         "and the RTX PRO 6000"),
        ("s5.beats_de_l40s", "claimBeatsDeLfortyS", "{:d}",
         "and the L40S, the one part that does not clear it everywhere"),
        ("s5.short_loghub_l40s", "claimShortLoghubLfortyS", "{:d}",
         "of the five Loghub columns, how many the L40S falls short on"),
        ("s5.field_marks", "claimFieldMarks", "{:d}",
         "our marks on the ten real columns: three codecs each"),
        ("s5.field_dominated", "claimFieldDominated", "{:d}",
         "how many a baseline beats at an equal or better at-rest ratio on the same column"),
        ("s5.field_beaten_on_rate", "claimFieldBeatenOnRate", "{:d}",
         "real columns where a baseline decodes faster than us at ANY ratio"),
        ("s5.field_fastest_rate", "claimFieldFastestRate", "{:d}",
         "GB/s of the quickest baseline configuration measured"),
        ("s5.field_fastest_ratio", "claimFieldFastestRatio", "{:.2f}",
         "what it stores while doing it"),
        ("s5.field_de_biggest_ratio", "claimFieldDeRatio", "{:.1f}",
         "the engine's best at-rest ratio on a real column: its high-ratio arm"),
        ("s5.field_de_biggest_rate", "claimFieldDeRate", "{:d}", "and its rate there"),
        ("s5.field_biggest_ratio", "claimFieldBestRatio", "{:.1f}",
         "the best at-rest ratio ANY baseline reaches on a real column"),
        ("s5.field_biggest_rate", "claimFieldBestRatioRate", "{:d}", "and the rate it reaches it at"),
        ("s5.field_biggest_ours_ratio", "claimFieldBestRatioOurs", "{:.2f}",
         "our at-rest ratio on that same column"),
        ("s5.field_biggest_ours_rate", "claimFieldBestRatioOursRate", "{:d}", "and our rate there"),
        ("s5.field_other_marks", "claimFieldOtherMarks", "{:d}",
         "our marks on the real columns of the H100 and L40S, where the software leg also ran"),
        ("s5.field_other_dominated", "claimFieldOtherDominated", "{:d}",
         "how many of those a baseline beats at an equal or better ratio on the same column"),
        ("s5.caddress_twelve_ratio", "claimCaddrTwelveRatio", "{:.2f}",
         "c_address, OnPair-12: at-rest ratio. Random characters, so nothing merges"),
        ("s5.caddress_twelve_rate", "claimCaddrTwelveRate", "{:d}", "and its rate"),
        ("s5.caddress_sixteen_ratio", "claimCaddrSixteenRatio", "{:.2f}",
         "OnPair-16 on the same column: worse than OnPair-12 on BOTH axes"),
        ("s5.caddress_sixteen_rate", "claimCaddrSixteenRate", "{:d}", "and its rate"),
        ("s5.caddress_gans_ratio", "claimCaddrGansRatio", "{:.2f}",
         "gANS there: the corpus's one baseline that dominates one of our marks"),
        ("s5.caddress_gans_rate", "claimCaddrGansRate", "{:d}", "and its rate"),
    ]),
]
TEX = [(k, m, f) for _, _, items in TEX_GROUPS for k, m, f, _ in items]


def emit_tex(path):
    """Write the macro file, grouped and annotated.

    The reader of this file knows the paper's argument and not this script, so each group says
    what it is about in two or three lines and each macro carries a one-line gloss. Without that
    the file is fifty opaque numbers and the only way to learn what one means is to grep the
    prose that cites it."""
    missing = [k for k, _, _ in TEX if k not in derived]
    if missing:
        raise SystemExit("cannot emit: %d claim(s) not derived: %s" % (len(missing), ", ".join(missing)))
    W = 62      # macro column width; keeps the trailing glosses aligned and readable
    lines = ["% GENERATED by experiments/paper_claims.py -- do not edit.",
             "% Every value is re-derived from committed results/. The paper cites these macros",
             "% instead of transcribing numbers, so prose cannot drift from the data.",
             "%",
             "% QUANTIFIER CLAIMS FAIL THE BUILD RATHER THAN RENDERING A WRONG SENTENCE.",
             "% A sentence like \"all ten real columns\" stays grammatical when the count drops to",
             "% eight, so a number swap alone would leave the paper quietly asserting something",
             "% false. The *Phrase macros below expand to the wording the prose needs while the",
             "% claim holds, and to \\claimAlarm otherwise, which stops the compile and names what",
             "% broke. Re-derive with experiments/paper_claims.py after any data change.",
             "\\providecommand{\\claimAlarm}[1]{%",
             "  \\GenericError{}{FastPair claim no longer holds: #1}{}%",
             "    {A quantifier in the prose is now false. Re-derive the macros and fix the sentence.}}",
             f"%   probe:    {os.path.relpath(PROBE, ROOT)}",
             f"%   campaign: {os.path.relpath(CAMPAIGN, ROOT)}"]
    for title, blurb, items in TEX_GROUPS:
        lines += ["", "% " + "-" * 74, "% " + title.upper()]
        lines += ["% " + b for b in blurb]
        lines.append("% " + "-" * 74)
        for key, macro, fmt, desc in items:
            cmd = "\\newcommand{\\%s}{%s}" % (macro, fmt.format(derived[key]))
            lines.append("%-*s %% %s" % (W, cmd, desc))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s (%d macros in %d groups)" % (path, len(TEX), len(TEX_GROUPS)))


def newer_suites(consumed):
    """Suite directories this invocation is NOT reading. The reducer used to hard-code the August
    campaign, so a freshly ingested leg was invisible: `--check` went green against stale data and
    read as confirmation of the run that had just finished. Never let that be silent again.

    ONLY A CAMPAIGN COUNTS AS UNREAD. The guard is about deriving Section 3-4 statistics from a
    stale campaign while a newer one sits unread, and those statistics come from the GRID stage
    over the fixed fifteen columns. A leg with no GRID cannot supply them, so it is not a
    candidate and naming it here would only force --allow-unconsumed -- a flag that then covers a
    genuinely unread campaign as collateral, which is the failure this guard exists to prevent.
    That covers the baseline leg (MATERIALIZE + SW) and any narrowed single-question leg, without
    either having to be special-cased by name."""
    root = os.path.join(ROOT, "results")
    consumed = os.path.abspath(consumed)
    out = []
    for d in glob.glob(os.path.join(root, "suite-*")):
        if not os.path.isdir(d) or os.path.abspath(d) == consumed:
            continue
        if not _is_campaign(d):
            continue
        out.append(d)
    return sorted(out)


def _is_campaign(suite_dir):
    """Could this leg supply the Section 3-4 claims? It needs a GRID stage AND a chip we derive from.

    THE CHIP CONDITION MATTERS. The claims come from CHIPS_CAMPAIGN, so a leg that ran GRID on some
    OTHER chip cannot move them however complete it is. The rtxpro leg is the case that showed this:
    a full five-state GRID over fifteen columns, read by fig:perf_gen and tab:arch, containing no
    chip this reducer derives from. Reporting it as an unread campaign forced --allow-unconsumed,
    and that flag then covers a genuinely unread campaign as collateral -- the exact failure the
    guard exists to prevent.

    Reads each chip's suite-complete.txt, the file every leg writes for provenance. A leg with no
    readable record is treated AS a campaign: unreadable provenance should make the guard louder,
    not quieter."""
    if not any(os.path.isdir(os.path.join(suite_dir, c)) for c in CHIPS_CAMPAIGN):
        return False
    records = [r for r in glob.glob(os.path.join(suite_dir, "*", "suite-complete.txt"))
               if os.path.basename(os.path.dirname(r)) in CHIPS_CAMPAIGN]
    if not records:
        return True
    for rec in records:
        try:
            text = open(rec).read()
        except OSError:
            return True
        # A LEG THAT DECLARES ITSELF PARTIAL CANNOT SUPPLY THESE CLAIMS. Section 3-4's statistics are
        # defined over the fixed fifteen columns -- require_complete_suite_campaign() enforces
        # exactly that -- so a narrowed leg is not a candidate however complete its GRID stage is.
        # The hoist0 leg is the case: one column, five hundred kernels, a full boost pass, and no
        # ability to move a single claim. Reporting it as an unread campaign forces
        # --allow-unconsumed, and that flag then covers a genuinely unread campaign as collateral.
        if re.search(r"^partial_corpus:", text, re.M):
            continue
        if re.search(r"^stage_GRID_\S*_rc:", text, re.M):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare against DECLARED and exit non-zero on drift")
    ap.add_argument("--emit-tex", metavar="PATH", help="write the LaTeX macro file the paper inputs")
    ap.add_argument("--suite-root", metavar="PATH",
                    help="read campaign cells (and probe captures, if present) from this suite "
                         "directory instead of the default campaign; path may be repo-relative")
    ap.add_argument("--probe-root", metavar="PATH",
                    help="read probe captures from here; defaults to --suite-root, then the "
                         "standalone probe capture")
    ap.add_argument("--allow-unconsumed", action="store_true",
                    help="proceed even though newer suite directories exist that this run ignores")
    args = ap.parse_args()

    global PROBE, CAMPAIGN
    if args.suite_root:
        CAMPAIGN = args.suite_root if os.path.isabs(args.suite_root) \
            else os.path.join(ROOT, args.suite_root)
        if not os.path.isdir(CAMPAIGN):
            sys.exit("--suite-root %s is not a directory" % CAMPAIGN)
        PROBE = CAMPAIGN
    if args.probe_root:
        PROBE = args.probe_root if os.path.isabs(args.probe_root) \
            else os.path.join(ROOT, args.probe_root)
        if not os.path.isdir(PROBE):
            sys.exit("--probe-root %s is not a directory" % PROBE)

    # A leg that landed but is not being read is the failure this guard exists for.
    unconsumed = newer_suites(CAMPAIGN)
    if unconsumed and not args.allow_unconsumed:
        sys.exit("REFUSING to derive from %s while these suite legs are unread:\n  %s\n"
                 "Pass --suite-root <one of them> to use a leg, or --allow-unconsumed to ignore "
                 "them deliberately." % (os.path.relpath(CAMPAIGN, ROOT),
                                         "\n  ".join(os.path.relpath(d, ROOT) for d in unconsumed)))

    rows, shared = load_probe()
    if not rows:
        sys.exit("no probe rows under %s" % PROBE)
    if args.suite_root or args.probe_root:
        require_complete_probe(rows, shared)
    occupancy(rows, shared)
    model_arithmetic(shared)
    if args.suite_root:
        require_complete_suite_campaign()
    cells = load_campaign()
    if cells:
        campaign_stats(cells)
        launch_stats(cells, rows)
        field_stats()
    else:
        print("WARNING: no campaign cells under %s; section 4 claims not derived" % CAMPAIGN,
              file=sys.stderr)

    payload = {"derived": derived, "notes": notes,
               "sources": {"probe": os.path.relpath(PROBE, ROOT),
                           "campaign": os.path.relpath(CAMPAIGN, ROOT)}}
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print("wrote %s (%d derived values)" % (os.path.relpath(OUT, ROOT), len(derived)))

    if args.emit_tex:
        emit_tex(args.emit_tex)

    if not args.check:
        for k in sorted(derived):
            print("  %-38s %s" % (k, derived[k]))
        return 0

    bad, missing = [], []
    for key, (want, tol, sec) in sorted(DECLARED.items()):
        if key not in derived:
            missing.append((key, sec))
            continue
        got = derived[key]
        ok = abs(got - want) <= tol if isinstance(got, (int, float)) else got == want
        if not ok:
            bad.append((key, sec, want, got, tol))
    for key, sec, want, got, tol in bad:
        print("DRIFT  §%-5s %-34s paper says %s, data says %s (tol %s)" % (sec, key, want, got, tol))
    for key, sec in missing:
        print("MISSING §%-5s %-34s declared but not derived" % (sec, key))
    print("\n%d/%d declared claims re-derive" % (len(DECLARED) - len(bad) - len(missing), len(DECLARED)))
    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
