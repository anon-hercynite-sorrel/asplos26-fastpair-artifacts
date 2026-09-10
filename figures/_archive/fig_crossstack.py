# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. crossstack: the fixed-stride CPU advantage as a distribution across generations.

One box per column per dict preset: the distribution of the fixed-stride (fat) over
variable-stride (OnPair's original layout) decode-rate ratio at one physical core, across the
ten CPU generations (AMD/Intel/Arm, DDR4/DDR5). There is no clean banding by
generation, so we show the spread rather than trace each chip: the ratio sits above
one on nearly every column, by a modest median, widening on the natural-text columns
at the wider dict-16 preset. A low-signal, compact panel.
Source: results/cpu-sweep-4phys/cpu-sweep.json.
"""
import json
import numpy as np
import common as C

SWEEP = C.RESULTS / "cpu-sweep-4phys" / "cpu-sweep.json"
COLS = [  # grouped synthetic-then-real, matching tab:datasets; data keys verified against cpu-sweep.json
    ("l_shipinstruct", "l_ship"), ("l_comment", "l_comment"),
    ("ps_comment", "ps_comment"), ("synthetic_url", "synth. URL"),
    ("clickbench_url", "ClickBench"), ("fineweb", "FineWeb"),
    ("wikipedia", "Wikipedia"), ("book_reviews", "Books"),
]


def main():
    d = json.load(open(SWEEP))
    machines = d["machines"]
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(6.8, 1.5))  # full width, short — a low-signal panel
    x = np.arange(len(COLS))
    w = 0.34
    for j, (bits, color) in enumerate(((12, C.PRIMARY), (16, C.WARM))):
        data = []
        for col, _ in COLS:
            vals = [r["fat_over_entries"] for m in machines for r in m["results"]
                    if r["column"] == col and r["bits"] == bits and r["threads"] == 1]
            data.append(vals)
        pos = x + (j - 0.5) * w
        bp = ax.boxplot(data, positions=pos, widths=w * 0.9, patch_artist=True,
                        showfliers=False, medianprops=dict(color=C.INK, lw=1.0),
                        whiskerprops=dict(color=color, lw=0.8), capprops=dict(color=color, lw=0.8),
                        boxprops=dict(facecolor=color, edgecolor=color, alpha=0.55, lw=0.8))
        bp["boxes"][0].set_label("FastPair-%d" % bits)
    ax.axhline(1.0, color=C.INK, lw=0.7, ls="--", zorder=1)
    ax.set_xticks(x)
    ax.set_xticklabels([lab for _, lab in COLS], rotation=25, ha="right", fontsize=6.5)
    ax.set_ylabel("fixed / variable", fontsize=7.5)
    ax.set_ylim(0, 2.0)
    ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0])
    ax.legend(frameon=False, fontsize=7, loc="lower left", ncol=2, handlelength=1.0)
    fig.tight_layout()
    C.save(fig, "fig_crossstack_strip")


if __name__ == "__main__":
    main()
