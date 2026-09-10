# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Where a column's dictionary accesses land, by rank.

One panel per column. Each curve gives the share of all decoded codes served by the N
most-frequently-read dictionary entries. N is an ABSOLUTE entry count, not a fraction of each
codec's own table, so the three codecs are directly comparable: a codec that trains a smaller
table simply reaches 100% sooner.

Source: results/token-freqdist/token_freqdist.json, produced by the freqdist tool in
bench/ (onpair-cpu-bench). CPU-only: it trains and encodes each column and reads the
frequency of every dictionary entry off the code stream. No GPU time.

Backs Appendix A. NOTE the samples are 64 MiB per column, not the 1 GB the evaluation
uses, so these curves rank and characterise; they are not evaluation numbers.
"""
import json

import numpy as np

import common as C

plt = C.apply_theme()
SRC = C.RESULTS / "token-freqdist" / "token_freqdist.json"

ORDER = [
    ("amz_review_id", "Amazon review_id"),
    ("fineweb2_zh", "FineWeb2 Mandarin"),
    ("wikipedia", "Wikipedia"),
    ("clickbench_url", "ClickBench URL"),
    ("cb_PageCharset", "ClickBench PageCharset"),
    ("l_comment", "TPC-H l_comment"),
    ("ghgit_path", "ghgit path"),
    ("cg_psc_code_description", "PBI psc_code_description"),
    ("cg_naics_name", "PBI naics_name"),
    ("tsp_AUDIENCIA", "PBI AUDIENCIA"),
]
# Same three colours fig:teaser uses for these codecs, so a reader carries one mapping
# through the paper: figures/fig_teaser.py sets FP16 to common.PRIMARY, FP12 to #92c5de,
# FSST to #c994c7.
# Same colours fig:teaser gives these three codecs, so one mapping carries through the paper.
CODECS = [("fsst-12", "FSST-12", "#c994c7"),
          ("onpair-12", "OnPair-12", "#92c5de"),
          ("onpair-16", "OnPair-16", C.PRIMARY)]

# Tick positions, powers of four: 4^6 and 4^8 land exactly on the two dictionary caps. The
# ranks themselves live in common.FREQ_EDGES, shared with the validator that re-derives the
# appendix's prose numbers off this same curve.
EDGES = C.FREQ_EDGES
TICKS = ["1", "4", "16", "64", "256", "1k", "4k", "16k", "64k"]


def curve_xy(curve):
    """The full cumulative curve: (rank, coverage %) at every emitted sample."""
    r = np.array([x for x, _ in curve], dtype=float)
    c = np.array([y for _, y in curve], dtype=float) * 100.0
    return r, c


def main():
    data = json.loads(SRC.read_text())
    by = {(r["column"], r["codec"]): r for r in data}
    rows = [(k, lbl) for k, lbl in ORDER if any((k, c) in by for c, _, _ in CODECS)]

    ncol = 3
    nrow = (len(rows) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(7.0, 1.6 * nrow),
                             sharex=True, sharey=True)
    axes = np.atleast_2d(axes)

    for n, (key, label) in enumerate(rows):
        ax = axes[n // ncol][n % ncol]
        for k, (code, cname, colour) in enumerate(CODECS):
            r = by.get((key, code))
            if r is None:
                continue
            rr, cc = curve_xy(r["curve"])
            ax.plot(rr, cc, color=colour, lw=1.4,
                    label=cname if n == 0 else None)
        ax.set_title(label, fontsize=7.5, pad=3)
        ax.set_xscale("log")
        ax.set_xticks(EDGES)
        ax.set_xticklabels(TICKS)
        ax.set_xlim(1, 70000)
        ax.set_ylim(0, 102)
        ax.minorticks_off()
        ax.tick_params(length=2)

    for n in range(len(rows), nrow * ncol):
        axes[n // ncol][n % ncol].axis("off")
    # The grid is not full, so the bottom row does not carry every column. Put the tick
    # labels on the lowest panel that actually exists in each column instead.
    for j in range(ncol):
        last = max((n // ncol for n in range(len(rows)) if n % ncol == j), default=None)
        if last is not None:
            axes[last][j].tick_params(labelbottom=True)
    # One label per axis, centred on the grid. The axes are shared, so repeating the label
    # on every row and column is three times the ink for the same information.
    # Figure-level labels: the grid is not full, so an axis-level label lands on a cell that
    # may be turned off, and one label per axis is the point of sharing them anyway.
    fig.supylabel("accesses served by the top-$N$ entries (%)", fontsize=8, x=0.005)
    fig.supxlabel("$N$, dictionary entries kept, most-frequently-read first", fontsize=8, y=0.005)

    fig.legend(loc="upper center", bbox_to_anchor=(0.5, 1.005),
               ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    C.save(fig, "fig_freqbars")


if __name__ == "__main__":
    main()
