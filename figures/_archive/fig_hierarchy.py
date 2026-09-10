# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. hierarchy: zoom from the GPU into one SM, where the decode binds.

Two panes. Left: the GPU -- a grid of many SMs over a device-wide L2 and a larger HBM. Right (the
zoom of one highlighted SM): its 32 warp lanes gather random entries from the cache-resident L1/TEX
dictionary; one lane misses and falls back out to L2/HBM; the decoded bytes are written into a
contiguous, coalesced output. Purple marks the zoom selection (which SM), warm the gather, cool the
miss. "..." = more than drawn. PowerPoint-grade shapes; frames the Sec 2 architecture.
"""
import common as C
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon, FancyArrowPatch
from matplotlib.path import Path

WARM, COOL, INK, GREY = C.WARM, C.PRIMARY, C.INK, "#9aa0a6"
LITE = "#eef2f6"   # idle cells (SMs, dictionary entries)
DIM = "#dbe2ea"    # warp lanes
PURPLE, PURPLE_LITE = "#6a51a3", "#cbc9e2"   # the zoom selection: which SM <-> the SM pane


def panel(ax, x, y, w, h, title, ec="#9aa0a6", lw=1.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.003,rounding_size=0.012",
                                fc="white", ec=ec, lw=lw, zorder=2))
    ax.text(x + w / 2, y + h + 0.03, title, ha="center", fontsize=8, color=INK)


def frustum(ax, sx, sytop, sybot, tx, tytop, tybot):
    """Zoom lens: a small source edge (sx, sybot..sytop) opening to a pane edge (tx, tybot..tytop)."""
    ax.add_patch(Polygon([(sx, sytop), (tx, tytop), (tx, tybot), (sx, sybot)],
                         closed=True, fc=LITE, ec="none", zorder=1))
    ax.plot([sx, tx], [sytop, tytop], color="#cbd0d5", lw=0.8, zorder=1)
    ax.plot([sx, tx], [sybot, tybot], color="#cbd0d5", lw=0.8, zorder=1)


def main():
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(7.0, 2.45))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # ===================== LEFT: the GPU (SMs over device-wide L2 + HBM) =====================
    panel(ax, 0.02, 0.18, 0.205, 0.62, "GPU")
    colx = [0.05, 0.09, 0.17]   # two SMs, dots between, one more (top-right highlighted)
    hl = (2, 0)
    for r in range(2):
        yy = 0.595 - r * 0.145
        for c, x0 in enumerate(colx):
            on = (c, r) == hl
            ax.add_patch(Rectangle((x0, yy), 0.03, 0.11, fc=(PURPLE_LITE if on else LITE),
                                   ec=(PURPLE if on else "#b8bdc2"), lw=(1.1 if on else 0.6), zorder=3))
        ax.text(0.145, yy + 0.055, "$\\cdots$", ha="center", va="center", fontsize=8, color=GREY, zorder=4)
    sx = 0.17 + 0.03

    # L2 (small, light; comfortable text margin) and HBM (clearly larger, darker, no clutter)
    ax.add_patch(Rectangle((0.05, 0.36), 0.145, 0.044, fc="#e7ecf1", ec="#b8bdc2", lw=0.6, zorder=3))
    ax.text(0.1225, 0.382, "L2", ha="center", va="center", fontsize=5, color=INK, zorder=4)
    ax.add_patch(Rectangle((0.04, 0.27), 0.165, 0.072, fc="#c2cdda", ec="#a7b3c0", lw=0.6, zorder=3))
    ax.text(0.1225, 0.306, "HBM", ha="center", va="center", fontsize=6.5, color=INK, zorder=4)

    # zoom: the highlighted SM opens into the big SM pane
    frustum(ax, sx, 0.705, 0.595, 0.37, 0.80, 0.18)

    # ===================== RIGHT (big): one SM -- the dictionary gather =====================
    panel(ax, 0.37, 0.18, 0.61, 0.62, "one SM", ec=PURPLE, lw=1.6)
    cx = 0.675
    ax.text(cx, 0.74, "32 warp lanes $\\to$ a random entry each", ha="center", fontsize=5.4,
            color=INK, zorder=4)
    # warp lanes: 3 ... 3
    lane_cx = [cx + (i - 3) * 0.077 for i in range(7)]
    for i, lcx in enumerate(lane_cx):
        if i == 3:
            continue
        ax.add_patch(Rectangle((lcx - 0.009, 0.635), 0.018, 0.075, fc=DIM, ec="#b8bdc2", lw=0.5, zorder=4))
    ax.text(cx, 0.6725, "$\\cdots$", ha="center", va="center", fontsize=7, color=GREY, zorder=5)

    # the L1/TEX dictionary (cache-resident): two cell groups around a "..." gap, one cool miss
    cells = [0.44 + i * 0.04 for i in range(5)] + [0.725 + i * 0.04 for i in range(5)]
    miss = 8
    for i, x0 in enumerate(cells):
        cool = (i == miss)
        ax.add_patch(Rectangle((x0, 0.42), 0.025, 0.085,
                               fc=("#cfe1f2" if cool else LITE), ec=(COOL if cool else "#b8bdc2"),
                               lw=(0.9 if cool else 0.5), zorder=4))
    ax.text(cx, 0.4625, "$\\cdots$", ha="center", va="center", fontsize=9, color=GREY, zorder=5)
    ax.text(cx, 0.38, "L1 dictionary (cache-resident)", ha="center", fontsize=5, color=INK, zorder=4)

    # the gather: each lane -> a random dict cell (warm); one misses (cool)
    lanes_used = [lane_cx[i] for i in (0, 1, 2, 4, 5, 6)]
    tgt = [3, 6, 1, 9, miss, 5]
    for lcx, t in zip(lanes_used, tgt):
        ax.add_patch(FancyArrowPatch((lcx, 0.635), (cells[t] + 0.0125, 0.505), arrowstyle="-|>",
                                     mutation_scale=6, color=(COOL if t == miss else WARM), lw=0.9, zorder=3))

    # the miss routes back out to the device-wide L2/HBM (left pane): down, across, up
    mx = cells[miss] + 0.0125
    miss_path = Path([(mx, 0.42), (mx, 0.10), (0.19, 0.10), (0.19, 0.30)],
                     [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO])
    ax.add_patch(FancyArrowPatch(path=miss_path, arrowstyle="-|>", mutation_scale=7,
                                 color=COOL, lw=1.0, ls=(0, (2.4, 1.6)), zorder=5))
    ax.text(0.45, 0.06, "a miss falls back out to L2 / HBM", ha="center", fontsize=5, color=COOL,
            style="italic", zorder=5)

    # the decoded output: contiguous + coalesced, the opposite of the scattered gather
    for i in range(11):
        ax.add_patch(Rectangle((cx - 0.077 + i * 0.014, 0.27), 0.014, 0.05, fc="#e8eaed",
                               ec="#c4c8cc", lw=0.4, zorder=4))
    ax.text(cx, 0.24, "decoded output (coalesced)", ha="center", fontsize=4.6, color=GREY, zorder=4)

    C.save(fig, "fig_hierarchy")


if __name__ == "__main__":
    main()
