# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. offtrade: the offset-strategy x materialization trade-off vs incoming-filter selectivity.

ClickBench URL (12.25M rows) on the B300. A fixed downstream operator (ClickBench Q20,
COUNT(*) WHERE URL LIKE '%google%') consumes the decoded output; an upstream filter keeps a
fraction m of rows. End-to-end (decode+scan) runtime is shown RELATIVE to OP4-store dense decode
(decode-everything, the shipped path = 1.0). The two mask-independent baselines (OP4 dense, OP2
regenerate-on-GPU) are dashed horizontal lines; the two selectivity-scaling paths (OP4 late-mat,
OP1 early-mat) are line plots. Below 1.0 = pushing the filter into decode beats decoding densely.
Source: results/b300-offtrade/{run1..4}_url.json (B300, min-of-200). CPU reference (OP3) is
~195x dense, off-scale, omitted. min-of-200.
"""
import json
import numpy as np
import common as C

RUNS = [C.RESULTS / "b300-offtrade" / "run1_url.json",
        C.RESULTS / "b300-offtrade" / "run2_url.json",
        C.RESULTS / "b300-offtrade" / "run3_url.json",
        C.RESULTS / "b300-offtrade" / "run4_url.json"]  # run4 (m=0.02/0.005/0.002/0.0005) is reference-only: all below the plotted lo=0.03 floor
LATE = C.PRIMARY   # OP4 store, late-materialization (blue)
EARLY = C.WARM     # OP1 code-offset, early-materialization (orange)


def load():
    cells = []
    for f in RUNS:
        cells += json.load(open(f))["cells"]
    S = {}
    for c in cells:
        e = c["legs"].get("e2e_ms")
        if e is not None:
            S.setdefault((c["strategy"], c["materialization"]), {})[c["m"]] = e
    return S


# Points dropped from the PLOT (all stay in the JSON): run3 near-duplicates (0.6, 0.35, 0.15)
# plus 0.9 and 0.625, which crowd the high-m end. Combined with lo=0.03 (drops 0.02/0.01 and
# the sub-0.01 reference tail), this zooms the plotted range to 1.0..0.03.
SKIP_M = [0.9, 0.625, 0.6, 0.35, 0.15]


def series(S, key, lo=0.03, hi=1.0):
    d = S.get(key, {})
    xs = sorted((m for m in d if lo - 1e-9 <= m <= hi + 1e-9
                 and not any(abs(m - s) < 1e-9 for s in SKIP_M)), reverse=True)
    return xs, [d[x] for x in xs]


def main():
    S = load()
    base = S[("OP4_store", "dense")][1.0]          # normalize: dense decode-all = 1.0
    fig, ax = C.new_fig(7.0, 1.9)

    # selectivity-scaling paths (line plots); identified by the legend box (lower left)
    for key, col, mk, lab in [
        (("OP4_store", "late_mat"), LATE, "o", "stored offsets · late-materialize"),
        (("OP1_proxy", "early_mat"), EARLY, "s", "code offsets · early-materialize"),
    ]:
        xs, ys = series(S, key)
        ax.plot(xs, [y / base for y in ys], "-", marker=mk, color=col, lw=1.8, ms=4,
                label=lab)

    # dense is the single reference line: normalization anchor AND decision boundary.
    # OP2 regen (only ~8% above dense, fused at this scale) is omitted from the plot.
    ax.axhline(1.0, ls="--", color=C.INK, lw=1.3, label="dense decode-all")

    from matplotlib.ticker import NullLocator, FixedLocator, FixedFormatter
    ax.set_xscale("log")
    ax.set_xlim(1.12, 0.026)                          # high selectivity -> low, left to right
    # label every plotted point
    ax.set_xticks([1.0, 0.75, 0.5, 0.375, 0.25, 0.175, 0.1, 0.07, 0.05, 0.03])
    ax.set_xticklabels(["1.0", ".75", ".50", ".375", ".25", ".175", ".10", ".07", ".05", ".03"],
                       fontsize=6.5)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("incoming-filter selectivity $m$ (fraction of rows kept)", fontsize=8)
    ax.set_ylabel("query runtime\n(relative to dense)", fontsize=8)
    # log y expands the sub-1.0 crossover zone (where the story lives) that a linear
    # axis crushes into the bottom quarter; 1.0 (dense) sits at the center.
    ax.set_yscale("log")
    ax.set_ylim(0.18, 4.6)   # 0.2 sits at the bottom-left corner (early-mat bottoms at 0.24 for m>=0.03)
    ax.yaxis.set_major_locator(FixedLocator([0.2, 0.5, 1.0, 2.0, 4.0]))
    ax.yaxis.set_major_formatter(FixedFormatter(["0.2", "0.5", "1", "2", "4"]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.grid(alpha=0.25, lw=0.5, which="major")

    ax.legend(frameon=True, fontsize=7, loc="lower left", handlelength=1.8,
              borderpad=0.5, labelspacing=0.35)
    fig.tight_layout()
    C.save(fig, "fig_offtrade")


if __name__ == "__main__":
    main()
