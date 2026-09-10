# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. ablation: what each read-side lever is worth on the device.

Per-lever decode-rate speedup, geometric mean over the throughput-bound columns at
dict-12, on each architecture. Two levers the cost surface motivates:

  fixed-stride -- onpair_shmem_4tpt over _vdict: a single indexed load replacing the
                  variable-stride dependent gather (the read-side layout).
  coarsening   -- onpair_shmem_4tpt over onpair_shmem: four tokens per thread vs one,
                  spending instructions to issue fewer cache requests.

On the HBM GPUs both pay (fixed-stride ~1.7x, the dependency collapse). On the
bandwidth-starved GDDR6 L40S both fall below 1.0: where bandwidth, not requests, is
scarce, the wider load's wasted bytes and the coarser thread's extra work cost more
than the requests they save. (split8read, the third lever, is Fig. gatherwidth.)
Source: results/<gpu>/onpair_summary_*.json (the committed kernel family).
"""
import statistics

import numpy as np

import common as C

# The throughput-bound columns (matches experiments/validate.py's COLS).
COLS = [
    ("tpch-sf10", "l_comment"), ("tpch-sf10", "ps_comment"), ("lship", "l_shipinstruct"),
    ("synthetic", "url"), ("clickbench", "URL"), ("fineweb", "text"), ("wikipedia", "text"),
    ("book-reviews", "text"), ("amazon-movies", "text"), ("amazon-electronics", "text"),
]
# (label, numerator kernel = lever ON, denominator kernel = lever OFF, color).
LEVERS = [
    ("fixed-stride",   "onpair_shmem_4tpt", "onpair_shmem_4tpt_vdict", C.PRIMARY),
    ("4 tokens/thread", "onpair_shmem_4tpt", "onpair_shmem",           C.WARM),
]


def lever_geomean(gpu, num, den):
    rs = []
    for d, c in COLS:
        cl = C.cell(gpu, d, c, 12)
        if not cl:
            continue
        km = C.kernel_map(cl)
        a, b = km.get(num), km.get(den)
        if a and b:
            rs.append(a / b)
    return statistics.geometric_mean(rs) if rs else None


def main():
    fig, ax = C.new_fig(3.3, 1.85)
    x = np.arange(len(C.GPUS))
    w = 0.38
    for j, (label, num, den, color) in enumerate(LEVERS):
        vals = [lever_geomean(g, num, den) for g in C.GPUS]
        xs = x + (j - 0.5) * w
        bars = ax.bar(xs, vals, w, color=color, label=label, zorder=3)
        for b, v in zip(bars, vals):
            if v:
                ax.text(b.get_x() + b.get_width() / 2, v + 0.02, "%.2f" % v,
                        ha="center", va="bottom", fontsize=5.8)
    # The break-even line: bars below it are a lever that does not pay on that chip.
    ax.axhline(1.0, color=C.INK, lw=0.9, ls="--", zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([C.GPU_LABEL[g] for g in C.GPUS])
    ax.set_ylabel("decode speedup (mechanism on / off)")
    ax.set_ylim(0, 2.05)
    ax.legend(frameon=False, fontsize=7, ncol=2, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), handlelength=1.2, columnspacing=1.6)
    C.save(fig, "fig_ablation")


if __name__ == "__main__":
    main()
