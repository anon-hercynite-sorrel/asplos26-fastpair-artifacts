# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. costsurface: which GPU pipe binds, across the cardinality gradient and four
architectures (NSight Compute --set full, dict-16, shipped kernels).

One panel per GPU (A100, L40S, H100, B300). Each shows the four pipes' Speed-of-Light
%-of-peak across the cardinality trio. On every HBM chip the per-SM L1 runs nearest its
peak while DRAM and the SM compute units trail, so the decode is access-rate-bound (L1
cache-line accesses per cycle, the on-GPU analog of storage IOPS, not byte bandwidth);
on the GDDR6 L40S no pipe saturates, and the low-cardinality columns run against GDDR6
itself.

The L1 bar is decomposed by LSU wavefronts into a memory-space x direction 2x2 -- the
dictionary gather (global load) and the aligned drain-out (global store) in the darker
shade, the staged emit (shared store) and scratch readback (shared load) in the lighter
shade, stores hatched. Across the cardinality gradient the gather share climbs while the
emit share falls: at low cardinality the drain/emit scratch traffic dominates the pipe;
at full dictionary the gather rises to roughly co-dominant. L2 and DRAM keep a plain
load/store split; SM (compute) has no memory direction.
Source: results/ncu-costsurface-v2.csv (shipped-kernel locked recapture, 2026-07-05;
the pre-recapture ncu-costsurface.csv profiled the base reference kernel -- see
experiments/MANIFEST.md, "PROVENANCE SPLIT").
"""
import csv
import numpy as np
import common as C

TRIO = [(5, "l_ship\n(5)"), (169, "synthetic\n(160)"), (4018, "ClickBench\n(4016)")]  # 1st = CSV join key (extractor card label); parenthetical = B300 dict-12 distinct_codes (matches tab:datasets, fig:stagecost, and the Sec 5 prose)
GPUS = [("a100", "A100"), ("l40s", "L40S"),
        ("h100", "H100"), ("b300", "B300")]
BITS = 16

# Colours: L1 = two blues (global darker, shared lighter); L2 = orange; global
# memory = purple. Both L2 and global memory stay off the blue family so neither
# reads as part of the L1 stack. SM = grey.
L1_GLOBAL = "#2166ac"
L1_SHARED = "#92c5de"
L2_C = "#fdae6b"
DRAM_C = "#807dba"
SM_C = "#969696"
HATCH = "xxx"  # cross-hatch (x-like) marks the store (write) share of a memory pipe


def load():
    rows = {}
    with open(C.RESULTS / "ncu-costsurface-v2.csv") as f:
        for r in csv.DictReader(f):
            if int(r["bits"]) != BITS:
                continue
            rows[(r["arch"], int(r["card"]))] = r
    return rows


def _col(data, gpu, key):
    return np.array([float(data.get((gpu, card), {}).get(key) or 0) for card, _ in TRIO])


def main():
    data = load()
    plt = C.apply_theme()
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.95), sharey=True)
    x = np.arange(len(TRIO))
    w = 0.2
    for ax, (gpu, title) in zip(axes, GPUS):
        # L1 (j=0): 2x2 wavefront stack. Fractions are %-of-L1-total; scale to the
        # L1 SoL bar height. Order bottom->top: gather, drain-out, readback, emit.
        l1 = _col(data, gpu, "l1tex")
        gld, gst = _col(data, gpu, "l1_gld") / 100, _col(data, gpu, "l1_gst") / 100
        shld, shst = _col(data, gpu, "l1_shld") / 100, _col(data, gpu, "l1_shst") / 100
        xp = x + (0 - 1.5) * w
        b = np.zeros(len(TRIO))
        ax.bar(xp, l1 * gld, w, bottom=b, color=L1_GLOBAL, zorder=3); b = b + l1 * gld
        ax.bar(xp, l1 * gst, w, bottom=b, facecolor="white", edgecolor=L1_GLOBAL,
               linewidth=0.5, hatch=HATCH, zorder=3); b = b + l1 * gst
        ax.bar(xp, l1 * shld, w, bottom=b, color=L1_SHARED, zorder=3); b = b + l1 * shld
        ax.bar(xp, l1 * shst, w, bottom=b, facecolor="white", edgecolor=L1_SHARED,
               linewidth=0.5, hatch=HATCH, zorder=3)
        # L2 (j=1), DRAM (j=2): load (solid) + store (hatched) in the pipe's colour.
        for j, (key, rk, c) in enumerate([("l2", "l2_rd", L2_C), ("dram", "dram_rd", DRAM_C)], start=1):
            xp = x + (j - 1.5) * w
            h = _col(data, gpu, key)
            rd = _col(data, gpu, rk) / 100
            ax.bar(xp, h * rd, w, color=c, zorder=3)
            ax.bar(xp, h * (1 - rd), w, bottom=h * rd, facecolor="white", edgecolor=c,
                   linewidth=0.5, hatch=HATCH, zorder=3)
        # SM (j=3): compute, no memory direction -> single solid bar.
        ax.bar(x + (3 - 1.5) * w, _col(data, gpu, "sm"), w, color=SM_C, zorder=3)
        ax.set_title(title, fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels([lab for _, lab in TRIO], fontsize=6.3)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", color="#e2e5e8", lw=0.6, zorder=0)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("throughput (% of peak)")
    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor=L1_GLOBAL, label="L1 gather (global read)"),
        Patch(facecolor="white", edgecolor=L1_GLOBAL, linewidth=0.5, hatch=HATCH, label="L1 drain (global write)"),
        Patch(facecolor=L1_SHARED, label="L1 readback (shared read)"),
        Patch(facecolor="white", edgecolor=L1_SHARED, linewidth=0.5, hatch=HATCH, label="L1 emit (shared write)"),
        Patch(facecolor=L2_C, label="L2 read"),
        Patch(facecolor="white", edgecolor=L2_C, linewidth=0.5, hatch=HATCH, label="L2 write"),
        Patch(facecolor=DRAM_C, label="global mem read"),
        Patch(facecolor="white", edgecolor=DRAM_C, linewidth=0.5, hatch=HATCH, label="global mem write"),
        Patch(facecolor=SM_C, label="SM (compute)"),
    ]
    fig.legend(handles=handles, frameon=False, fontsize=6.3, ncol=5, loc="lower center",
               handlelength=1.0, columnspacing=1.1, handletextpad=0.5,
               bbox_to_anchor=(0.5, -0.10))
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    C.save(fig, "fig_costsurface")


if __name__ == "__main__":
    main()
