#!/usr/bin/env python3
"""Reduce staged-dictionary NCU captures into the mechanism table for the §5 subsection.

Usage:
    python3 reduce_shdict_ncu.py <dir-with-shdict_ncu_*_raw.csv> [...]

Shows, per (column, bits, kernel), whether relocating the dictionary into shared memory
did what it was designed to do on the read side, and what it cost instead:

  global ld sectors     should COLLAPSE for the staging variants (gather eliminated)
  B/sector              should RISE toward 32 (whatever is left coalesces)
  shared ld conflicts   should EXPLODE (the random gather, reserialized)
  achieved occupancy    should FALL (the staged table's footprint)
  L1 / DRAM SoL         does the bound move, or merely relocate?

NCU's raw page is WIDE: row 0 = metric names as headers, row 1 = units, rows 2+ = one
profiled launch each. (The details page is long-format; do not confuse them.) Metric names
and this layout were verified against
results/a100-ncu-v2/ncu_costsurface_clickbench_URL_b12_raw.csv (in this repo) on 2026-07-27, where the
shipped split8read kernel shows ~87.6k shared-load conflicts as a reference point.
"""
import csv, glob, os, re, sys

METRICS = {
    "shared_ld_conflicts": "l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_ld.sum",
    "global_ld_sectors":   "l1tex__t_sectors_pipe_lsu_mem_global_op_ld.sum",
    "bytes_per_sector":    "smsp__sass_average_data_bytes_per_sector_mem_global_op_ld.ratio",
    "achieved_occ_pct":    "sm__warps_active.avg.pct_of_peak_sustained_active",
    "l1_sol_pct":          "l1tex__data_pipe_lsu_wavefronts.avg.pct_of_peak_sustained_elapsed",
    "dram_rd_sol_pct":     "dram__bytes_read.sum.pct_of_peak_sustained_elapsed",
}

def load(path):
    """Wide raw-page CSV -> {name: mean over profiled launches}."""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 3:
        return {}, None
    hdr, data = rows[0], rows[2:]
    idx = {k: hdr.index(v) for k, v in METRICS.items() if v in hdr}
    out = {}
    for k, i in idx.items():
        vals = []
        for r in data:
            if i < len(r):
                try:
                    vals.append(float(r[i].replace(",", "")))
                except ValueError:
                    pass
        if vals:
            out[k] = sum(vals) / len(vals)
    kern = None
    if "Kernel Name" in hdr:
        ki = hdr.index("Kernel Name")
        seen = {r[ki] for r in data if ki < len(r) and r[ki]}
        kern = "|".join(sorted(seen)) if seen else None
    return out, kern

def parse_tag(fn):
    b = os.path.basename(fn)
    m = re.match(r"shdict_ncu_(.+?)_(.+?)_b(\d+)_(.+?)_raw\.csv$", b)
    if m:
        return m.group(1), m.group(2), int(m.group(3)), m.group(4)
    m = re.match(r"ncu_costsurface_(.+?)_(.+?)_b(\d+)_?(.*)_raw\.csv$", b)  # legacy captures
    if m:
        return m.group(1), m.group(2), int(m.group(3)), m.group(4) or "shipped"
    return None

def main(dirs):
    rows = []
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*_raw.csv"))):
            t = parse_tag(f)
            if not t:
                continue
            m, kern = load(f)
            rows.append((*t, m, kern))
    if not rows:
        print("no *_raw.csv captures found", file=sys.stderr)
        return 1

    print(f"{'column':11s} {'bits':>4s} {'kernel':13s} {'gl_sectors':>12s} {'B/sec':>6s} "
          f"{'sh_conflicts':>13s} {'occ%':>6s} {'L1sol%':>7s} {'DRAMrd%':>8s}  identity")
    print("-" * 108)
    def f(x, w, p=1):
        return f"{x:{w},.{p}f}" if isinstance(x, float) else f"{'--':>{w}s}"
    for ds, col, bits, kern, m, seen in sorted(rows, key=lambda r: (r[1], r[2], r[3])):
        ok = "ok" if (seen and kern.split("_")[-1] in seen) or kern == "shipped" else f"MISMATCH:{seen}"
        print(f"{col[:11]:11s} {bits:4d} {kern[:13]:13s} {f(m.get('global_ld_sectors'),12,0)} "
              f"{f(m.get('bytes_per_sector'),6)} {f(m.get('shared_ld_conflicts'),13,0)} "
              f"{f(m.get('achieved_occ_pct'),6)} {f(m.get('l1_sol_pct'),7)} "
              f"{f(m.get('dram_rd_sol_pct'),8)}  {ok}")

    print("\nRead: within one (column,bits) group, compare each staging variant against the\n"
          "split8read baseline. gl_sectors collapsing and B/sec rising means the gather DID\n"
          "go away as designed; sh_conflicts exploding and occ% falling is what it cost\n"
          "instead. That pairing, not the slowdown alone, is the mechanism claim.")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["."]))
