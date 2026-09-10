# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Is it legitimate to draw two NCU waves in one figure? Compare their shared cells.

fig:pipes draws one bar per chip. Four of those chips were captured on 2026-07-05 and the fifth
(RTX PRO) can only be captured now, so the figure would mix two harness revisions -- fifty-plus
commits apart -- in one set of bars. CLAUDE.md's rule is that numbers from different revisions are
not automatically comparable, so the 2026-08-24 leg re-captures ClickBench URL on the four old
chips as a CONTROL: the same cell, same script path, same floating clocks, measured twice.

This prints the per-cell delta on every shared (arch, col, bits). What to conclude:

  * every shared cell within a couple of points on l1tex/l2/dram and the L1 4-way split
      -> the waves agree, and drawing the new Windows capture beside anything from July is sound.
  * a systematic shift in one direction
      -> something in the harness moved the measurement. The figure must then be drawn from ONE
         wave only, and the July numbers in Section 5.2 need re-deriving rather than extending.
  * one chip disagreeing while the others match
      -> suspect that leg (driver, clock behaviour, a different selector kernel), not the wave.

USAGE
  uv run figures/compare_costsurface_waves.py results/ncu-costsurface-v2.csv <new.csv>

There is deliberately NO pass/fail threshold. The question "is 3.1 points a lot" depends on which
metric moved and on what the prose claims from it, and a script that answers it with a hard-coded
tolerance would let a real shift through under a green check. It reports; a human judges.
"""
import csv
import sys

# The metrics fig:pipes and Section 5.2 actually read. l1hit is included because Section 4.1's
# eviction mechanism cites it, so a shift there matters even though this figure does not draw it.
METRICS = ["l1tex", "l2", "dram", "sm", "l1hit", "l1_gld", "l1_gst", "l1_shld", "l1_shst"]
KEY = ("arch", "col", "bits")


def load(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("%s: no rows" % path)
    missing = [c for c in KEY + tuple(METRICS) if c not in rows[0]]
    if missing:
        sys.exit("%s: missing columns %s" % (path, ", ".join(missing)))
    return {tuple(r[k] for k in KEY): r for r in rows}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip().splitlines()[-1])
    old, new = load(sys.argv[1]), load(sys.argv[2])
    shared = sorted(set(old) & set(new))
    only_old, only_new = sorted(set(old) - set(new)), sorted(set(new) - set(old))

    print("old=%s  %d cells" % (sys.argv[1], len(old)))
    print("new=%s  %d cells" % (sys.argv[2], len(new)))
    print("shared: %d" % len(shared))
    if not shared:
        print("\nNO SHARED CELL. The control did not land, so the two waves cannot be compared and")
        print("must not be drawn together. Check that the new leg captured ClickBench URL.")
        # Still list what is present, so the operator can see WHY they do not intersect.
        for label, cells in (("only in old", only_old), ("only in new", only_new)):
            print("  %s: %s" % (label, ", ".join("/".join(c) for c in cells[:12])))
        return 1

    width = max(len(m) for m in METRICS)
    worst = []
    for key in shared:
        print("\n%s  %s  b%s" % key)
        for m in METRICS:
            try:
                a, b = float(old[key][m]), float(new[key][m])
            except ValueError:
                print("  %-*s  unparseable" % (width, m))
                continue
            d = b - a
            print("  %-*s  %7.1f -> %7.1f   %+6.1f" % (width, m, a, b, d))
            worst.append((abs(d), key, m, a, b, d))

    print("\nlargest shifts across all shared cells:")
    for _, key, m, a, b, d in sorted(worst, reverse=True)[:10]:
        print("  %-6s %-22s b%-3s %-8s %7.1f -> %7.1f  %+6.1f" % (key[0], key[1], key[2], m, a, b, d))

    if only_new:
        print("\nnew cells with no July counterpart (the point of the leg):")
        for c in only_new:
            print("  %s" % "/".join(c))
    if only_old:
        print("\nJuly cells this leg did not re-capture (expected: it captured two columns):")
        print("  %d cells, e.g. %s" % (len(only_old), ", ".join("/".join(c) for c in only_old[:6])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
