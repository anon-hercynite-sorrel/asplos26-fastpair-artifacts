#!/usr/bin/env python3
"""Reduce the staged-dictionary counterfactual: does staging the dictionary in shared
memory (GSST's central design move) help at OnPair dictionary scale?

    python3 figures/extract_shdict.py [--csv out.csv]

Reads results/<chip>-shdict/shdict_summary_*.json. Each summary is a list of cells, one
per bit width, each carrying gpu.kernels = every registered kernel variant with its
decode rate, an `applicable` flag, and a `verified` (byte-exact) flag.

Baseline per cell = the best applicable, byte-exact NON-staging kernel, i.e. the paper's
own best-kernel-per-cell rule, so the comparison is best-vs-best rather than
shipped-vs-strawman. A staging variant whose shared-memory request exceeds the cap reports
applicable=false; that is a RESULT (the capacity boundary), not a missing measurement.
"""
import argparse, csv, glob, json, os, sys

STAGING = {
    "onpair_shmem_4tpt_shdict8": "shdict8",   # stride-8 dict_s8 in shared
    "onpair_shmem_4tpt_pdict":   "pdict",     # padded 16 B/entry in shared, persistent grid
    "onpair_shmem_4tpt_vdict":   "vdict",     # var-len packed in shared, persistent grid
}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def rows():
    for d in sorted(glob.glob(os.path.join(ROOT, "results", "*-shdict"))):
        chip = os.path.basename(d).replace("-shdict", "")
        for f in sorted(glob.glob(os.path.join(d, "shdict_summary_*.json"))):
            for cell in json.load(open(f)):
                g = cell.get("gpu") or {}
                ks = g.get("kernels") or []
                if not ks:
                    continue
                base = max((e["decode_gib_s"] for e in ks
                            if e["kernel"] not in STAGING and e.get("applicable")
                            and e.get("verified") and e.get("decode_gib_s")), default=None)
                var = {}
                for e in ks:
                    nm = STAGING.get(e["kernel"])
                    if nm:
                        var[nm] = {"gib": e.get("decode_gib_s"),
                                   "applicable": bool(e.get("applicable")),
                                   "verified": bool(e.get("verified"))}
                yield {"chip": chip, "dataset": cell["dataset_id"], "column": cell["column"],
                       "bits": cell["bits"], "entries": g.get("dict_entries_max"),
                       "frac_le8": g.get("frac_le8"), "baseline_gib_s": base, "variants": var}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    a = ap.parse_args()
    data = list(rows())
    if not data:
        print("no results/*-shdict data found", file=sys.stderr)
        return 1

    # HEADER SAYS 'gather', NOT 'shipped'. The baseline is the best applicable byte-exact
    # NON-STAGING kernel for the cell, per the rule in the docstring -- not whatever kernel the
    # decoder would pick by default. A reader who took this column for a shipped-default rate
    # would derive a smaller staging penalty than the data supports.
    print(f"{'chip':5s} {'column':12s} {'bits':>4s} {'gather':>8s} | "
          f"{'shdict8':>15s} {'pdict':>15s} {'vdict':>15s}")
    print("-" * 92)
    def cell(v, base):
        if v is None:            return f"{'--':>15s}"
        if not v["applicable"]:  return f"{'INAPPLICABLE':>15s}"
        if not v["verified"]:    return f"{'NOT-BYTE-EXACT':>15s}"
        if not (v["gib"] and base): return f"{'?':>15s}"
        return f"{v['gib']:7.1f} {100*(v['gib']/base-1):+6.1f}%"
    for r in sorted(data, key=lambda r: (r["chip"], r["column"], r["bits"])):
        b = r["baseline_gib_s"]
        print(f"{r['chip']:5s} {r['column'][:12]:12s} {r['bits']:4d} "
              f"{(f'{b:8.1f}' if b else '     n/a')} | "
              + " ".join(cell(r["variants"].get(k), b) for k in ("shdict8", "pdict", "vdict")))

    deltas, wins = [], 0
    for r in data:
        b = r["baseline_gib_s"]
        ok = [v["gib"] for v in r["variants"].values()
              if v["applicable"] and v["verified"] and v["gib"]]
        if b and ok:
            d = 100 * (max(ok) / b - 1)
            deltas.append(d)
            wins += d > 0
    if deltas:
        s = sorted(deltas)
        print(f"\nCells where staging is possible at all: {len(deltas)}. "
              f"Best staging variant per cell: best {max(s):+.1f}%, "
              f"median {s[len(s)//2]:+.1f}%, worst {min(s):+.1f}%. Wins: {wins}.")

    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chip", "dataset", "column", "bits", "entries", "frac_le8",
                        "baseline_gib_s", "variant", "gib_s", "applicable", "verified",
                        "delta_pct"])
            for r in data:
                for nm, v in sorted(r["variants"].items()):
                    dp = (100 * (v["gib"] / r["baseline_gib_s"] - 1)
                          if v["gib"] and r["baseline_gib_s"] and v["applicable"] else "")
                    w.writerow([r["chip"], r["dataset"], r["column"], r["bits"], r["entries"],
                                r["frac_le8"], r["baseline_gib_s"], nm, v["gib"],
                                v["applicable"], v["verified"], dp])
        print(f"wrote {a.csv}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
