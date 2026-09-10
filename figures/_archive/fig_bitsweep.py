# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. bitsweep: per-dataset fat/compact across dict bit-widths, two contrasting machines.

Two CPU generations that bracket the behavior -- one where the fixed-stride advantage decays as the
fat table outgrows cache (Intel Granite), one where it grows (Arm Graviton4) -- each a scatter of
the real high-cardinality columns, colored by dataset, with faint lines tracing each across dict
bit-widths 9..16. The fat table doubles each bit (2^bits * 16 bytes, 8 KiB at 9 to 1 MiB at 16).
Source: results/cpu-bitsweep/cpu-bitsweep.json.
"""
import json
import common as C

SWEEP = C.RESULTS / "cpu-bitsweep" / "cpu-bitsweep.json"
MACHINES = [("intel-granite", "Intel Granite Rapids"), ("arm-graviton4", "Arm Graviton4")]
DATASETS = [
    ("book_reviews", "book-reviews", C.PRIMARY),
    ("clickbench_url", "ClickBench URL", C.WARM),
    ("l_comment", "l_comment", "#41ab5d"),
]


def main():
    d = json.load(open(SWEEP))
    bylabel = {m["label"]: m for m in d["machines"]}
    plt = C.apply_theme()
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.7), sharey=True)
    for ax, (lbl, title) in zip(axes, MACHINES):
        m = bylabel[lbl]
        for col, dlab, color in DATASETS:
            rows = sorted((r for r in m["results"]
                           if r["column"] == col and r["threads"] == 1),
                          key=lambda r: r["bits"])
            if not rows:
                continue
            x = [r["bits"] for r in rows]
            y = [r["fat_over_entries"] for r in rows]
            ax.plot(x, y, "-", color=color, lw=0.8, alpha=0.35, zorder=2)
            ax.scatter(x, y, s=20, color=color, zorder=3, label=dlab)
        ax.axhline(1.0, color=C.INK, lw=0.7, ls="--", zorder=1)
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("dictionary bit-width", fontsize=8)
        ax.set_xticks(range(9, 17))
    axes[0].set_ylabel("fixed-stride / variable-stride")
    axes[0].legend(frameon=False, fontsize=6.5, loc="upper right")
    fig.tight_layout()
    C.save(fig, "fig_bitsweep")


if __name__ == "__main__":
    main()
