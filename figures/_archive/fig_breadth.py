# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. breadth: OnPair-GPU decode throughput across the four GPUs, per dataset.

Small multiples, one panel per representative column. One tokens-per-thread family
selected per chip reaches HBM-class rates on every architecture; absolute throughput
rises with the memory generation across the board.
Source: results/{a100,gh200,h100,b200}/onpair_summary_*.json.
"""
import numpy as np
import common as C

PANELS = C.REPRESENTATIVE  # 8 (dataset, column, label) tuples


def main():
    ncol = 4
    nrow = (len(PANELS) + ncol - 1) // ncol
    plt = C.apply_theme()
    fig, axes = plt.subplots(nrow, ncol, figsize=(6.8, 3.0), sharey=False)
    axes = axes.ravel()
    for ax, (ds, col, label) in zip(axes, PANELS):
        vals = [C.best_shipped(C.cell(g, ds, col)) or 0 for g in C.GPUS]
        ax.bar(range(len(C.GPUS)), vals, color=[C.GPU_RAMP[g] for g in C.GPUS], width=0.7)
        if (ds, col) == C.GSST_COL:
            ax.axhline(C.GSST_GIBS, color=C.GSST_RED, ls="--", lw=0.9, alpha=0.9, zorder=3)
            ax.text(len(C.GPUS) - 0.55, C.GSST_GIBS, "GSST (A100)", color=C.GSST_RED,
                    fontsize=5, va="bottom", ha="right")
        ax.set_xticks(range(len(C.GPUS)))
        ax.set_xticklabels([C.GPU_LABEL[g] for g in C.GPUS], rotation=45, ha="right", fontsize=6)
        ax.set_title(label, fontsize=7)
        ax.tick_params(axis="y", labelsize=6)
    for ax in axes[len(PANELS):]:
        ax.set_visible(False)
    fig.supylabel("decode throughput (GiB/s)", fontsize=8)
    fig.tight_layout()
    C.save(fig, "fig_breadth")


if __name__ == "__main__":
    main()
