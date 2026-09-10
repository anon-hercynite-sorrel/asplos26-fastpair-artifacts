# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. e2e_sweep: decode vs predicate-evaluation across predicate selectivity.

The decode->scan end-to-end on the ClickBench URL column, swept over substring predicates
(LIKE '%needle%') from near-unique to ubiquitous. Each bar stacks the constant decode time
and the scan (predicate-evaluation) time; the line is the predicate's selectivity (matches as
a % of the column's byte positions, log). The decode floor is fixed, so as selectivity rises the scan overtakes it: a cross-over
from a decode-dominated regime (the consuming operator is nearly free) to a
predicate-evaluation-dominated one. Source: results/e2e/sweep/sweep_*.json (B300, min-of-200).
"""
import glob
import json
import os

import numpy as np

import common as C

DEC, SCAN, SEL = C.PRIMARY, C.WARM, "#2ca25f"  # decode / scan(predicate) / selectivity line
YCAP = 3.4  # ms; the two ubiquitous needles tower far above (annotated), so cap to keep the
            # cross-over region legible.


def load():
    rows = []
    dbytes = None
    for f in glob.glob(str(C.RESULTS / "e2e" / "sweep" / "sweep_*.json")):
        d = json.load(open(f))
        tag = os.path.basename(f)[len("sweep_"):-len(".json")]
        rows.append((tag, d["cpu_matches"], d["decode_ms"], d["scan_ms"]))
        dbytes = d["decoded_bytes"]
    rows.sort(key=lambda r: (r[1] or 0))   # by selectivity (match count)
    return rows, dbytes


def main():
    rows, dbytes = load()
    labels = [r[0] for r in rows]
    matches = np.array([r[1] for r in rows], dtype=float)
    sel_pct = matches / dbytes * 100.0   # match positions as a % of the column's byte positions
    dec = np.array([r[2] for r in rows])
    scan = np.array([r[3] for r in rows])
    x = np.arange(len(rows))

    fig, ax = C.new_fig(7.0, 1.75)  # shrunk further (shorter at \textwidth)
    ax.bar(x, dec, 0.64, color=DEC, label="decode", zorder=3)
    ax.bar(x, scan, 0.64, bottom=dec, color=SCAN, label="scan (predicate eval)", zorder=3)
    ax.set_ylim(0, YCAP)
    ax.set_yticks([0, 1, 2, 3])
    ax.set_axisbelow(True)   # grid behind the bars, so the white off-scale labels stay legible
    ax.set_ylabel("e2e runtime (ms)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.5)
    ax.set_xlim(-0.7, len(rows) - 0.3)

    # Off-scale bars (ubiquitous needles): annotate their true total above the cap.
    for i in range(len(rows)):
        tot = dec[i] + scan[i]
        if tot > YCAP:
            ax.text(x[i], YCAP * 0.84, "%.1f ms↑" % tot, ha="center", va="top",
                    rotation=90, fontsize=6, color="white", fontweight="bold")

    # Cross-over: first needle where scan exceeds decode (predicate eval overtakes decode).
    xo = next((i for i in range(len(rows)) if scan[i] > dec[i]), None)
    if xo is not None:
        xb = xo - 0.5
        ax.axvline(xb, color=C.INK, lw=1.1, ls="--", zorder=4)
        ax.text(xb - 0.15, YCAP * 0.97, "decode-dominated", ha="right", va="top",
                fontsize=6.5, color=C.INK, style="italic")
        ax.text(xb + 0.15, YCAP * 0.97, "predicate-eval-dominated", ha="left", va="top",
                fontsize=6.5, color=C.INK, style="italic")
        ax.text(xb - 0.15, YCAP * 0.87, "cross-over ≈ %.2f%%" % sel_pct[xo], ha="right",
                va="top", fontsize=6, color=C.INK)

    # Selectivity on a secondary log axis, as a % of the column's byte positions.
    ax2 = ax.twinx()
    ax2.grid(False)                                     # only the (faint) left-axis grid shows
    ax2.plot(x, sel_pct, color=SEL, marker="o", ms=3.2, lw=1.2, zorder=5)
    ax2.set_yscale("log")
    ax2.set_ylabel("selectivity (%, log)", color=SEL)
    ax2.tick_params(axis="y", colors=SEL)
    ax2.spines["right"].set_color(SEL)
    ax2.set_ylim(sel_pct.min() * 0.4, sel_pct.max() * 3)

    ax.legend(frameon=False, fontsize=7, loc="upper left", ncol=2, handlelength=1.1,
              columnspacing=1.0)
    fig.tight_layout()  # fill the figure width (match fig_sota's rendered size at \textwidth)
    C.save(fig, "fig_e2e_sweep")


if __name__ == "__main__":
    main()
