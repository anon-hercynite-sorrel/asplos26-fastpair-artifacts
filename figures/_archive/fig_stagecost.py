# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. stagecost: stage-cost decomposition across the dictionary-cardinality gradient.

Each gradient column is a stacked bar of where its decode time goes, attributed to the
four stages (scan / emit / gather / drain). The per-stage share is derived from the
skip-one-stage ablation: removing stage S at speedup f_S implies S accounts for
(1 - 1/f_S) of the time. Those shares overlap on the pipeline and sum to ~1.4, so we
normalize within each column; the decomposition is therefore APPROXIMATE. The absolute
base throughput rides in the x-tick so the normalized bars do not hide the cost gap.
Source: results/b300/onpair_summary_{lship,synthetic,clickbench}.json (the *_ablate* kernels).
"""
import numpy as np
import common as C

GRADIENT = [("lship", "l_shipinstruct"), ("synthetic", "url"), ("clickbench", "URL")]
STAGES = ["scan", "emit", "gather", "drain"]   # stack order, bottom -> top
BASE = "onpair_shmem_4tpt_ablate"
LABEL = {"scan": "offset scan", "emit": "token emit",
         "gather": "dict gather", "drain": "output drain"}
SHORT = {"l_shipinstruct": "l_shipinstruct", "url": "synthetic", "URL": "ClickBench URL"}
ANNOT_MIN = 13.0   # only label a segment at/above this share, to avoid clutter


def shares(ds, col):
    """Approximate per-stage time shares, normalized to sum to 1 within the column."""
    km = C.kernel_map(C.cell("b300", ds, col))
    base = km.get(BASE)
    raw = {}
    for s in STAGES:
        v = km.get(BASE + "_no" + s)
        raw[s] = max(0.0, 1.0 - base / v) if (v and base) else 0.0
    tot = sum(raw.values()) or 1.0
    return {s: raw[s] / tot for s in STAGES}


def main():
    fig, ax = C.new_fig(3.4, 2.6)
    x = np.arange(len(GRADIENT))
    sh = [shares(ds, col) for ds, col in GRADIENT]
    bottom = np.zeros(len(GRADIENT))
    for s in STAGES:
        h = np.array([d[s] for d in sh]) * 100.0
        ax.bar(x, h, 0.62, bottom=bottom, label=LABEL[s], color=C.STAGE[s])
        for xi in range(len(GRADIENT)):
            if h[xi] >= ANNOT_MIN:
                ax.text(x[xi], bottom[xi] + h[xi] / 2, "%.0f%%" % h[xi],
                        ha="center", va="center", fontsize=6, color="white")
        bottom += h

    labels = []
    for ds, col in GRADIENT:
        dc = C.distinct_codes(C.cell("b300", ds, col))
        labels.append("%s\n%s entries" % (SHORT[col], dc))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("stage share of decode time (%)")
    ax.set_ylim(0, 100)
    ax.margins(x=0.08)
    ax.legend(ncol=4, frameon=False, fontsize=6, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), columnspacing=1.0, handlelength=1.2)
    C.save(fig, "fig_stagecost")


if __name__ == "__main__":
    main()
