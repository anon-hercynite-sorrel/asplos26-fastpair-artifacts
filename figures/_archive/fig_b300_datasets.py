# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. b300_datasets: per-dataset B300 decode, labeled.

The range-bar SOTA figures show technique-family dominance but not which column is which.
This isolates one GPU (the B300) and names every dataset: FastPair (best over dict-12/-16)
vs the hardware Decompression Engine (best engine), horizontal bars sorted by FastPair
throughput, with the per-dataset FastPair/DE multiple annotated -- the 2.6-4.6x headline,
broken out by column. One-column companion to fig:payoff.
Source: results/b300/onpair_summary_*.json + b300/onpair_nvcomp_hw.json.
"""
import numpy as np

import common as C

COLS = [  # (dataset, column, DE dataset-id, label)
    ("tpch-sf10", "l_comment", "tpch-sf10", "TPC-H l_comment"),
    ("tpch-sf10", "ps_comment", "tpch-sf10", "TPC-H ps_comment"),
    ("lship", "l_shipinstruct", "tpch-sf10", "TPC-H l_shipinstruct"),
    ("synthetic", "url", "synthetic", "synthetic URL"),
    ("clickbench", "URL", "clickbench", "ClickBench URL"),
    ("fineweb", "text", "fineweb", "FineWeb"),
    ("wikipedia", "text", "wikipedia", "Wikipedia"),
    ("book-reviews", "text", "book-reviews", "Amazon Books"),
    ("amazon-movies", "text", "amazon-movies", "Amazon Movies"),
    ("amazon-electronics", "text", "amazon-electronics", "Amazon Electronics"),
]


def main():
    de = C.de_map()
    rows = []
    for d, c, did, lab in COLS:
        fp = max((C.best_shipped(C.cell("b300", d, c, b)) or 0) for b in (12, 16))
        rows.append((lab, fp, de.get((did, c))))
    rows.sort(key=lambda r: r[1])   # ascending -> fastest at the top under barh
    labs = [r[0] for r in rows]
    fp = np.array([r[1] for r in rows])
    dev = np.array([r[2] if r[2] else np.nan for r in rows])

    y = np.arange(len(rows))
    h = 0.38
    fig, ax = C.new_fig(3.3, 3.7)
    ax.barh(y + h / 2, fp, h, color=C.TECH["onpair"], label="FastPair", zorder=3)
    ax.barh(y - h / 2, dev, h, color=C.TECH["de"], label="hardware DE", zorder=3)
    for i in range(len(rows)):
        if fp[i] and dev[i] and not np.isnan(dev[i]):
            ax.text(fp[i] + 20, y[i] + h / 2, "%.1f×" % (fp[i] / dev[i]),
                    va="center", ha="left", fontsize=5.8, color=C.INK)
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=6.5)
    ax.set_xlabel("B300 decode throughput (GB/s)")
    ax.set_xlim(0, max(fp) * 1.18)
    ax.legend(frameon=False, fontsize=6.8, loc="lower right", handlelength=1.0)
    C.save(fig, "fig_b300_datasets")


if __name__ == "__main__":
    main()
