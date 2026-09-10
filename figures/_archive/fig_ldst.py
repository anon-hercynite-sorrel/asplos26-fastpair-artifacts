# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. ldst: is the binding L1/TEX traffic load or store? Both, ~evenly.

L1/TEX global-memory requests split into load (the scattered dictionary gather) and
store (the staged drain), on the B200 (the L1/TEX-binding architecture), across the
cardinality trio. The split is ~53/47 and flat: the drain's stores are a co-equal
consumer of the binding cache pipe's request budget, not a free coalesced
write-through. One independent gather-load + one drain-store per token, by construction.
Source: results/ncu-costsurface-3arch.csv.
"""
import csv
import numpy as np
import common as C

TRIO = [(5, "l_ship"), (169, "synthetic"), (4018, "ClickBench")]
ARCH, BITS = "b200", 16


def main():
    rows = {}
    with open(C.RESULTS / "ncu-costsurface-3arch.csv") as f:
        for r in csv.DictReader(f):
            if r["arch"] == ARCH and int(r["bits"]) == BITS:
                rows[int(r["card"])] = r
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(3.0, 2.1))
    x = np.arange(len(TRIO))
    ld = [float(rows[c]["ld"]) for c, _ in TRIO]
    st = [float(rows[c]["st"]) for c, _ in TRIO]
    ax.bar(x, ld, 0.6, color=C.PRIMARY, label="load (gather)", zorder=3)
    ax.bar(x, st, 0.6, bottom=ld, color=C.WARM, label="store (drain)", zorder=3)
    for xi, l in zip(x, ld):
        ax.text(xi, l / 2, "%d" % round(l), ha="center", va="center", color="white", fontsize=7)
        ax.text(xi, l + (100 - l) / 2, "%d" % round(100 - l), ha="center", va="center",
                color="white", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels([lab for _, lab in TRIO], fontsize=7)
    ax.set_ylim(0, 100); ax.set_ylabel("% of L1/TEX requests")
    ax.set_title("B200 L1/TEX: load vs store", fontsize=8)
    ax.legend(frameon=False, fontsize=6.5, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, 1.32), handlelength=1.0, columnspacing=0.8)
    fig.tight_layout()
    C.save(fig, "fig_ldst")


if __name__ == "__main__":
    main()
