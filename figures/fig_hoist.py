# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. hoist: decode rate over (K, H), at three launch bounds.

The hoist is not a one-parameter change, which is why lines, arrows and bars all read badly here:
each series had to carry which B AND which H at once, so the reader was asked to hold two
encodings in mind to see a single comparison. It is a surface. Two inputs, K and H, one output,
repeated at each launch bound. B=4 is included because fig_grid shows it is where the register
ceiling still clears the kernel's demand, so it should behave like B=1 rather than like B=8 --- a
prediction this figure either confirms or breaks.

So: a grid. K across, H up, decode rate as colour, one panel per B, ONE shared scale so the panels
can be compared directly. Cells above H = min(K,4) do not exist and are left blank.

WHAT TO LOOK AT. At B=1 and B=4 the colour is flat up each column: raising H changes nothing,
because registers were never scarce, and the two panels are indistinguishable. At B=8 the H=1 row
darkens sharply from K=5 on -- that is the register cap, not the hoist -- and raising H lightens it
again without ever reaching the shade the other two panels hold at the same K. The hoist recovers
ground the launch bound gave away.

The B=4 panel is the prediction fig_grid makes, tested: the ceiling R/(T*B) is 64 registers there
against the kernel's 56, so it should behave like B=1, and it does.

Source: results/suite-<id>/b300/sweep_summary_*_boost.json, dh family for H>1 and dg for H=1, at
matched (K,T,B).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import suite as S  # noqa: E402

KS = list(range(1, 9))
# H=0 is the NO-HOIST control, and it is the row that lets this figure answer its own question.
# H=1 is the shipped decoder and already hoists one round, so a grid of H>=1 shows whether MORE
# hoisting helps and cannot show whether hoisting helps at all. The guard below is
# `H > min(K,4)`, and 0 exceeds nothing, so H=0 is valid at every K and needs no exception.
HS = [0, 1, 2, 3, 4]
BS = [1, 4, 8]
T = 256
DEV, BITS = "b300", 12
COLUMN = ("loghub-windows", "line")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite-id", default=None)
    a = ap.parse_args()
    # THE WHOLE HEATMAP MUST COME FROM ONE LEG. It compares H=0 against H=1..4 in a single panel,
    # so taking the H=0 row from one leg and the rest from another would put a cross-leg, cross-day
    # comparison inside one figure, where run-to-run variation reads as a horizontal artifact. The
    # H=0 arm arrived after the paper campaign, so prefer whichever leg actually timed it at this
    # coordinate, and fall back to the declared campaign (where the H=0 row is simply blank).
    root = S.latest_root(a.suite_id)
    if a.suite_id is None:
        probe = f"onpair_dh_k6_t{T}_b4_h0"
        for cand in S.candidate_roots(DEV):
            cc = S.cells(cand, DEV, "boost", "onpair").get((COLUMN[0], COLUMN[1], BITS))
            names = {k.get("kernel") for k in ((cc or {}).get("gpu") or {}).get("kernels") or []}
            if probe in names:
                root = cand
                break
    if root is None:
        sys.exit("no results/suite-* directory found")
    print(f"reading {root.name}")

    cells = S.cells(root, DEV, "boost", "onpair")
    c = cells.get((COLUMN[0], COLUMN[1], BITS))
    if c is None:
        sys.exit(f"column {COLUMN} absent from this leg")
    g = c.get("gpu") or {}
    db = g.get("decoded_bytes")
    R = {k["kernel"]: db / min(k["decode_ns_iters"])
         for k in (g.get("kernels") or []) if k.get("decode_ns_iters") and db}

    import numpy as np
    grids = {}
    for B in BS:
        M = np.full((len(HS), len(KS)), np.nan)
        for j, K in enumerate(KS):
            for i, H in enumerate(HS):
                if H > min(K, 4):
                    continue
                # dg IS H=1 (the shipped decoder); dh carries every other H, including h0.
                name = (f"onpair_dg_k{K}_t{T}_b{B}" if H == 1
                        else f"onpair_dh_k{K}_t{T}_b{B}_h{H}")
                if name in R:
                    M[i, j] = R[name]
        grids[B] = M
    allv = np.concatenate([m[~np.isnan(m)] for m in grids.values()])
    if not allv.size:
        sys.exit("no dg/dh coordinates found; is this a full-grid pass?")
    # ANCHORED, not data-derived. A scale that tracks min/max re-maps every colour whenever a
    # cell changes, so two renders of this figure are not comparable and neither is a shade here
    # against the same shade in a neighbouring panel from an earlier pass. 700 to 1550 brackets
    # every measured cell on this column with a little margin and matches fig_lenpredict's axis.
    VMIN, VMAX = 700.0, 1550.0
    vmin, vmax = VMIN, VMAX
    lo, hi = float(allv.min()), float(allv.max())
    if lo < vmin or hi > vmax:
        sys.stderr.write("fig_hoist: data spans %.0f-%.0f, outside the anchored scale %.0f-%.0f;"
                         " cells beyond it are clipped\n" % (lo, hi, vmin, vmax))

    plt = C.apply_theme()
    fig, axes = plt.subplots(1, len(BS), figsize=(7.0, 1.45), sharey=True,
                             gridspec_kw={"wspace": 0.06})
    im = None
    for ax, B in zip(axes, BS):
        im = ax.imshow(grids[B], origin="lower", aspect="auto", cmap=C.cmap("analysis"),
                       vmin=vmin, vmax=vmax,
                       extent=(-0.5, len(KS) - 0.5, -0.5, len(HS) - 0.5))
        # The rate is printed in the cell: a reader comparing two panels should not have to
        # estimate a number from a colour.
        for j in range(len(KS)):
            for i in range(len(HS)):
                v = grids[B][i, j]
                if not np.isnan(v):
                    ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=C.FS["annot"],
                            color="white" if v < (vmin + vmax) / 2 else "#222222")
        # Label a subset of K, matching fig_grid: every cell already carries its rate, so a tick
        # per column competes with the numbers for no gain. The axis is categorical, so the tick
        # positions are the INDICES of these K values, not the values.
        kshow = [k for k in (1, 2, 4, 6, 8) if k in KS]
        ax.set_xticks([KS.index(k) for k in kshow])
        ax.set_xticklabels([str(k) for k in kshow])
        ax.set_yticks(range(len(HS)))
        ax.set_yticklabels([str(h) for h in HS])
        ax.set_title(f"B={B}")
        ax.grid(False)
    axes[len(BS) // 2].set_xlabel("K (tokens per thread)")
    axes[0].set_ylabel("H (held rounds)")
    # Every cell carries its rate, so the bar orients the reader between dark and light rather
    # than being read off. Five ticks keep the ramp legible without competing with the numbers.
    # EVENLY SPACED and inside the range. Spanning vmin..vmax in equal fractions gave five ticks
    # at uneven round numbers, which reads worse than four on a regular interval.
    ticks = [t for t in (750, 1000, 1250, 1500) if vmin <= t <= vmax]
    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.015, ticks=ticks)
    cb.set_label("decode (GB/s)", fontsize=C.FS["axis_label"])
    cb.ax.tick_params(labelsize=C.FS["tick"])
    C.save(fig, "fig_hoist", width="text")

    for B in BS:
        for K in (6,):
            vals = [(H, grids[B][HS.index(H), KS.index(K)]) for H in HS
                    if not np.isnan(grids[B][HS.index(H), KS.index(K)])]
            print(f"B={B}, K={K}: " + "  ".join(f"H={h} {v:.0f}" for h, v in vals))


if __name__ == "__main__":
    main()
