#!/usr/bin/env python3
"""Re-derive the sidecar-regeneration penalty from results/b300-regen-corpus-20260906.

WHAT THIS REPLACES. `results/b300-campaign-0717/op_gpu_regen.jsonl` is the source of the paper's
"+15-19%" and it cannot carry that claim any more, for two reasons found on 2026-09-06:

  1. CORPUS. It measured thirteen columns of which only four are still in Table 1 by name, and
     none by content -- its TPC-H cells are sf10 while the current corpus is sf15/sf45/sf263. No
     Loghub column was ever in it, and Loghub Windows is the paper's headline.
  2. BASIS. Its cells are OnPair-16, and the file has no `bits` field saying so. ONPAIR_DUMP_E2E
     is last-writer-wins and that campaign swept bits 12 and 16, so the dump it measured was the
     last cell written. Confirmed by reproduction: this leg's OnPair-16 ClickBench URL lands at
     17.6% against the committed 17.5%, with token count within 0.09% and decode within 0.1%,
     while its OnPair-12 cell reads 20.8% off 1.8x the tokens. The box and encode path are sound;
     the published range was measured on the mildest half of the configuration space.

WHAT THE PENALTY DEPENDS ON. Regeneration reads every code and reduces one entry per batch, so it
scales with token COUNT; decode scales with decoded BYTES. The ratio therefore tracks mean token
length, and does so strongly: r = -0.87 over the thirty (column, code width) cells. A 1.9-byte
column (c_address) pays 33.4% where a 12.7-byte one (ps_comment) pays 16.3%. This is the same
axis Section 4.2 uses for decode rate, running the other way.

Usage:  uv run experiments/regen_penalty.py [--check]
"""
import argparse
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEG = ROOT / "results" / "b300-regen-corpus-20260906" / "regen_grid.jsonl"

# The claim this file licenses, as the range and median over the shipped reading. Bounds are the
# measured values; --check fails on drift so a re-run that moves them cannot pass silently.
EXPECT = {"lo": 15.1, "hi": 33.4, "median": 19.4, "n": 30, "pearson_max": -0.80}


def load():
    """Validated cells only: a row whose offsets or decode did not match the host reference is
    not a measurement, and every binary exits non-zero in that case."""
    cells = {}
    total = 0
    for line in LEG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        r = json.loads(line)
        o = r.get("op2") or {}
        if not (o.get("offsets_ok") and o.get("decode_ok")):
            continue
        cells.setdefault((r["dataset_id"], r["column"], r["bits"]), {})[r["variant"]] = o
    return cells, total


def shipped(cells):
    """K=6 is the recommended coarsening; W is whichever plane width decodes faster on that
    column, which is what the shipped selector picks from the dictionary's length profile. Taking
    the faster W is what makes the denominator the rate the paper reports."""
    out = []
    for key, d in cells.items():
        cands = [d.get(f"k6_w{w}") for w in (8, 16)]
        cands = [o for o in cands if o]
        if not cands:
            continue
        o = max(cands, key=lambda o: o["decode_gbps"])
        out.append((key, o, o["decoded_bytes"] / o["total_tokens"]))
    return sorted(out, key=lambda t: t[2])


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / den


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail on drift from EXPECT")
    a = ap.parse_args()

    cells, total = load()
    validated = sum(len(v) for v in cells.values())
    rows = shipped(cells)
    pens = [o["regen_overhead_pct"] for _, o, _ in rows]
    mts = [mt for _, _, mt in rows]
    r = pearson(mts, pens)

    print(f"regeneration penalty — {LEG.relative_to(ROOT)}")
    print(f"  {validated}/{total} rows validated (offsets AND decode byte-exact)\n")
    print(f"  {'column':<30}{'meanTok':>8}{'W':>4}{'decode':>9}{'penalty':>9}")
    for (ds, col, bits), o, mt in rows:
        print(f"  {ds + '/' + col + ' b' + str(bits):<30}{mt:>8.1f}"
              f"{o['low_plane_bytes']:>4}{o['decode_gbps']:>9.0f}"
              f"{o['regen_overhead_pct']:>8.1f}%")
    med = statistics.median(pens)
    print(f"\n  K=6 shipped: {min(pens):.1f}% .. {max(pens):.1f}%  median {med:.1f}%  n={len(pens)}")
    ctl = sorted(d["ctl_k4"]["regen_overhead_pct"] for d in cells.values() if "ctl_k4" in d)
    print(f"  K=4 control: {ctl[0]:.1f}% .. {ctl[-1]:.1f}%  median {statistics.median(ctl):.1f}%")
    print(f"  pearson r(mean token length, penalty) = {r:.3f}")

    if not a.check:
        return 0
    bad = []
    if validated != total:
        bad.append(f"{total - validated} rows failed validation")
    for k, got in (("lo", min(pens)), ("hi", max(pens)), ("median", med)):
        if abs(got - EXPECT[k]) > 0.15:
            bad.append(f"{k}: {got:.1f}% vs expected {EXPECT[k]}%")
    if len(pens) != EXPECT["n"]:
        bad.append(f"n: {len(pens)} vs expected {EXPECT['n']}")
    if r > EXPECT["pearson_max"]:
        bad.append(f"pearson {r:.3f} is weaker than {EXPECT['pearson_max']}")
    if bad:
        print("\nFAIL:")
        for b in bad:
            print("  -", b)
        return 1
    print("\nOK — range, median and the token-length relationship all reproduce.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
