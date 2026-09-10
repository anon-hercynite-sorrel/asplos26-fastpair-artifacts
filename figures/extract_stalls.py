# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Rebuild a warp-stall-share CSV row-set from NCU dump dirs (the *_raw.csv
smsp__average_warps_issue_stalled_* ratios), averaging across kernel invocations.

share(x) = smsp__average_warps_issue_stalled_<x>_per_issue_active.ratio
           / smsp__average_warp_latency_per_inst_issued.ratio * 100

The denominator equals NCU's "Warp Cycles Per Issued Instruction", so shares are
percentages of the average cycles a warp spends per issued instruction; the listed
reasons do not sum to 100 (minor stall reasons are omitted).

Usage: uv run extract_stalls.py [results_dir] [dir_suffix]   -> prints CSV (with header)
Defaults: results -ncu-v2  (i.e. results/{l40s,h100,b300,a100}-ncu-v2).
"""
import csv
import glob
import os
import sys

METRICS = ["long_scoreboard", "mio_throttle", "short_scoreboard", "lg_throttle",
           "wait", "not_selected", "selected", "drain", "barrier", "no_instruction"]
ARCHES = ["l40s", "h100", "b300", "a100"]


def shares(raw_path):
    with open(raw_path) as f:
        rdr = csv.DictReader(f)
        cols, denom_col = {m: None for m in METRICS}, None
        for c in rdr.fieldnames:
            for m in METRICS:
                if c.endswith("issue_stalled_%s_per_issue_active.ratio" % m):
                    cols[m] = c
            if c.endswith("average_warp_latency_per_inst_issued.ratio"):
                denom_col = c
        acc = {m: [] for m in METRICS}
        for r in rdr:
            try:
                denom = float(r[denom_col].replace(",", ""))
            except (ValueError, TypeError, AttributeError):
                continue
            if denom <= 0:
                continue
            for m in METRICS:
                if cols[m] and r[cols[m]]:
                    try:
                        acc[m].append(100.0 * float(r[cols[m]].replace(",", "")) / denom)
                    except ValueError:
                        pass
    return {m: (sum(v) / len(v) if v else float("nan")) for m, v in acc.items()}


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "results"
    suffix = sys.argv[2] if len(sys.argv) > 2 else "-ncu-v2"
    print("arch,col,bits," + ",".join(METRICS))
    for a in ARCHES:
        d = os.path.join(base, a + suffix)
        for p in sorted(glob.glob(os.path.join(d, "ncu_costsurface_*_b*_raw.csv"))):
            stem = os.path.basename(p)[len("ncu_costsurface_"):-len("_raw.csv")]
            col, bits = stem.rsplit("_b", 1)
            s = shares(p)
            print("%s,%s,%s," % (a, col, bits) + ",".join("%.1f" % s[m] for m in METRICS))


if __name__ == "__main__":
    main()
