# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. grid: why K=6, and what B and T actually do to get there.

This is a MECHANISM figure, not a parameter search. The question is not "which cell won" but why
the winning region is where it is, and the answer is a single interaction: B decides whether the
compiler is allowed to spend registers, and once that is settled K and T are an algorithmic
trade with no occupancy term in it.

THE TWO PANELS ARE THE ARGUMENT.

  B=1 (left).  The launch bound asks for nothing, so ptxas allocates what the kernel wants -- 56
  registers per thread at every K -- and the hardware still resides 4 blocks per SM, unchanged
  across the whole sweep. Occupancy is FLAT. Whatever the rate curve does here is therefore the
  algorithm alone: more tokens per thread amortise the scan and the drain until the live low-plane
  bytes stop paying for themselves. That peak is real and it is K=6 at T=256.

  B=8 (right).  Asking for eight resident blocks caps registers at R/(T*B) = 32. At small K that
  is affordable and buys nominal occupancy. At K>=6 it is not: the working set no longer fits, and
  residency FALLS to 5 blocks anyway. The constraint that was supposed to buy occupancy loses it,
  and the rate collapses to roughly a third.

So the deployment rule is the opposite of the intuition that more resident blocks are better: set
B low and let the compiler and the scheduler settle occupancy themselves. They arrive at the same
residency without being told, and without the register cap that breaks the large-K regime.

T IS THE THIRD PARAMETER AND IT MOVES THE OPTIMUM RATHER THAN THE CEILING. More warps per block
put more tokens in flight, so the K that best amortises a scan shifts up with T: T=64 and T=128
peak at K=4, T=256 at K=6, and T=256 reaches the highest rate of the three. T=128 is the safe
choice because it is never far from either regime -- a median 1.1% and at most 3.0% below the best
T per column -- and it is never the best one.

ONE COLUMN, NAMED. Loghub Windows at OnPair-12, the fastest real column on this device. A median
over ten columns left the reader unable to tell whether the column behind a point changed from K
to K, which is the one thing a shape argument cannot afford. Residency and registers come from the
resource probe at the same coordinate.

Source: results/suite-<id>/b300/sweep_summary_*_boost.json (dg family) joined to
kernel_resources.jsonl on (K, T, B).
"""
import argparse
import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import suite as S  # noqa: E402

KS = list(range(1, 9))
TS = [64, 128, 256]
PANELS = [(1, "B=1"), (4, "B=4"), (8, "B=8")]
# From common's threads family: viridis sampled at 0.25, 0.5 and 0.75, i.e. five evenly
# spaced points with both ends dropped. T is an order rather than a set of identities, so a
# ramp is the right encoding, and dropping the ends keeps both extremes of the scale off the
# page -- viridis is near-black at 0 and near-yellow at 1.
T_COLOR = {64: C.colour("threads", "T=64"), 128: C.colour("threads", "T=128"),
           256: C.colour("threads", "T=256")}
# The occupancy overlay is a different quantity on a different axis, so it is deliberately
# NOT from the threads ramp; it takes the darkest context grey.
OCC_COLOR = C.neutral(3)
DEV, BITS = "b300", 12
COLUMN = ("loghub-windows", "line")   # fastest real column on the B300 at OnPair-12


def dg_rates(cell):
    out = {}
    g = cell.get("gpu") or {}
    db = g.get("decoded_bytes")
    for k in (g.get("kernels") or []):
        m = re.match(r"onpair_dg_k(\d+)_t(\d+)_b(\d+)$", k.get("kernel", ""))
        if m and k.get("decode_ns_iters") and db:
            out[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = db / min(k["decode_ns_iters"])
    return out


def resources(root, chip):
    """(K,T,B) -> probe row, H=1 only: the dg family carries no hoist."""
    out = {}
    f = Path(root) / chip / "kernel_resources.jsonl"
    if not f.exists():
        return out
    for line in open(f):
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("buildable") and d.get("held_high", 1) == 1:
            out[(d["tokens_per_thread"], d["block_threads"], d["min_blocks"])] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite-id", default=None)
    a = ap.parse_args()
    root = S.latest_root(a.suite_id)
    if root is None:
        sys.exit("no results/suite-* directory found")

    cells = S.cells(root, DEV, "boost", "onpair")
    real = {(ds, col) for _, ds, col in S.REAL}
    cell = cells.get((COLUMN[0], COLUMN[1], BITS))
    if cell is None:
        sys.exit(f"column {COLUMN} absent from this leg")
    grid = dg_rates(cell)
    grids = [grid]
    res = resources(root, DEV)
    if not grids:
        sys.exit("no dg coordinates found; is this a full-grid pass?")

    plt = C.apply_theme()
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.10), sharey=True)
    for ax, (B, title) in zip(axes, PANELS):
        for T in TS:
            ys = [grid.get((K, T, B)) for K in KS]
            xs = [k for k, y in zip(KS, ys) if y]
            yy = [y for y in ys if y]
            ax.plot(xs, yy, marker="o", ms=C.MS, lw=C.LW, color=T_COLOR[T], label=f"T={T}")
        # Residency for the two widest blocks, so the reader can see it is flat at B=1 for both
        # and falls at B=8 for both, rather than taking one T on trust.
        ax2 = ax.twinx()
        # A twinx axes is drawn ABOVE its host whatever zorder its artists carry, so the
        # residency dashes landed on top of the rate markers. Swapping the axes' own zorder puts
        # them underneath; the host's patch has to go transparent or it would then hide them.
        ax2.set_zorder(ax.get_zorder() - 1)
        ax.patch.set_visible(False)
        for T, dash in ((64, (0, (1, 1))), (128, (0, (1, 1.6))), (256, (0, (3, 2)))):
            occ = [(K, res[(K, T, B)]["blocks_per_sm"]) for K in KS if (K, T, B) in res]
            if occ:
                ax2.plot([k for k, _ in occ], [b for _, b in occ], color=OCC_COLOR, lw=C.LW,
                         ls=dash, zorder=1)
        ax2.set_ylim(0, 20)
        ax2.set_yticks([4, 9, 18])
        ax2.tick_params(axis="y", colors=OCC_COLOR, labelsize=C.FS["tick"])
        if B == PANELS[-1][0]:
            ax2.set_ylabel("blocks/SM", color=OCC_COLOR, fontsize=C.FS["axis_label"])
        else:
            ax2.set_yticklabels([])
        ax.set_title(title)
        ax.set_xticks([1, 2, 4, 6, 8])
        ax.grid(alpha=.25, lw=.4)
        ax.set_axisbelow(True)
    from matplotlib.ticker import FixedLocator
    axes[len(PANELS) // 2].set_xlabel("K (tokens per thread)")
    axes[0].set_ylabel("decode (GB/s)")
    axes[0].set_ylim(0, 2000)
    axes[0].yaxis.set_major_locator(FixedLocator([0, 500, 1000, 1500, 2000]))

    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=T_COLOR[T], marker="o", ms=C.MS_LEGEND, lw=C.LW, label=f"T={T}")
               for T in TS]
    occ_handles = [Line2D([], [], color=OCC_COLOR, lw=C.LW, ls=d, label=f"T={T}")
                   for T, d in ((64, (0, (1, 1))), (128, (0, (1, 1.6))), (256, (0, (3, 2))))]
    # Two legends, set apart, because the two groups share their T labels and the axis names the
    # quantity. Repeating "blocks/SM" on every swatch spent three labels saying one thing.
    # Hung by their TOP edge one C.LEGEND_GAP under the figure, and tight_layout is given the
    # full canvas: reserving a band at the bottom AND anchoring outside it stacked two gaps, so
    # the key floated well clear of the x label it belongs to.
    l1 = C.legend_below(fig, x=0.27, handles=handles, ncol=3, columnspacing=1.0,
                        handlelength=1.6, title="decode")
    fig.add_artist(l1)
    C.legend_below(fig, x=0.73, handles=occ_handles, ncol=3, columnspacing=1.0,
                   handlelength=1.6, title="blocks/SM")
    fig.tight_layout(pad=0.3)
    C.save(fig, "fig_grid", width="text")

    for B, _ in PANELS:
        row = res.get((6, 256, B), {})
        peak = max([(K, grid[(K, 256, B)]) for K in KS if (K, 256, B) in grid],
                   key=lambda kv: kv[1])
        print(f"B={B}: T=256 regs={row.get('regs_per_thread')} "
              f"blocks(K=6)={row.get('blocks_per_sm')}  peak at K={peak[0]} ({peak[1]:.0f} GB/s)")
    for T in TS:
        pts = [(K, grid[(K, T, 1)]) for K in KS if (K, T, 1) in grid]
        if pts:
            peak = max(pts, key=lambda kv: kv[1])
            print(f"B=1, T={T}: peak at K={peak[0]} ({peak[1]:.0f} GB/s)")


if __name__ == "__main__":
    main()
