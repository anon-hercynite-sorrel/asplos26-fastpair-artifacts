# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. scaling: cross-architecture decode throughput, across code size.

Absolute decode throughput for TPC-H ps_comment across A100 / H100 / B300, at both
dictionary code sizes (dict-12 vs dict-16). Throughput rises with the memory
generation; the wider 16-bit code costs throughput consistently across generations
(a bigger dictionary trades decode rate for compression). One tokens-per-thread
family, selected per chip.
Source: results/{a100,h100,b300}/onpair_summary_tpch-sf10.json.
"""
import numpy as np
import common as C

DATASET, COLUMN = "tpch-sf10", "ps_comment"
BITS = [(12, "dict-12", C.PRIMARY), (16, "dict-16", C.WARM)]


def main():
    fig, ax = C.new_fig(3.3, 2.1)
    x = np.arange(len(C.GPUS))
    w = 0.38
    for j, (bits, label, color) in enumerate(BITS):
        gibs = [C.best_shipped(C.cell(g, DATASET, COLUMN, bits)) for g in C.GPUS]
        xs = x + (j - 0.5) * w
        bars = ax.bar(xs, gibs, w, color=color, label=label, zorder=3)
        for b, v in zip(bars, gibs):
            if v:
                ax.text(b.get_x() + b.get_width() / 2, v + 12, "%d" % round(v),
                        ha="center", va="bottom", fontsize=5.6, rotation=90)
    ax.set_xticks(x)
    ax.set_xticklabels([C.GPU_LABEL[g] for g in C.GPUS])
    ax.set_ylabel("decode throughput (GB/s)")
    ax.set_ylim(0, 1650)
    ax.legend(frameon=False, fontsize=7, loc="upper left", handlelength=1.0)
    C.save(fig, "fig_scaling")


if __name__ == "__main__":
    main()
