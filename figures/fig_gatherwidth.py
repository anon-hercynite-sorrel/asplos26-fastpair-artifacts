# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. gatherwidth: the gather-width lever, W=8 against W=16, at both code widths.

WHAT VARIES. W is how many bytes of a dictionary entry the kernel fetches for every token.
W=16 reads whole entries: no high plane, no request queue, one lookup per token. W=8 reads half
and pays a second lookup for the tokens that need it. So the ratio below is a same-column,
same-code-width, same-campaign comparison of one design parameter.

THE KERNEL SETS ARE THE FAMILY PREFIXES, not a hand-listed set. gen_packed_grid.py stamps
ONPAIR_LOW_PLANE_BYTES 16u on the dw family and leaves the template default of 8 for dg, dh and
ds (onpair_decompress_tpt.cuh:47). That is 120 W=16 kernels against ~444 W=8 kernels per cell,
so each side is at its own best over T, B, H and S rather than at one configuration.

WHY THIS REPLACED THE EARLIER VERSION. The first form of this figure read results/b300, a
pre-2026-08 per-kernel sweep, restricted itself to dict-12, and concluded the gain was a property
of that preset -- that at dict-16 the half-width table doubles and "the residency benefit
evaporates". The campaign leg says otherwise: the SAME relationship holds at OnPair-16, shifted
along the axis, reaching 1.20x on the column whose tokens are all short. What separates the two
presets is not whether the lever works but where their columns sit on frac_le8 -- eleven of
fifteen are below 0.51 at OnPair-16 against two of fifteen at OnPair-12. The mechanism is
therefore the second lookup, not plane residency: residency would not survive a 16x larger plane.

Source: results/suite-paper-20260821/b300 via suite.cells, verified+applicable kernels only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import suite as S  # noqa: E402

WIDE = "onpair_dw_"
NARROW = ("onpair_dg_", "onpair_dh_", "onpair_ds_")


def points(root, chip, bits):
    """(frac_le8, best W=8 / best W=16) per column, plus the two rates."""
    out = []
    for key, c in sorted(S.cells(root, chip, "boost", "onpair").items()):
        if key[2] != bits:
            continue
        g = c["gpu"]
        db = g.get("decoded_bytes")
        w8 = w16 = 0.0
        for k in (g.get("kernels") or []):
            if not (k.get("verified") and k.get("applicable")):
                continue
            it = k.get("decode_ns_iters") or []
            if not it or not db:
                continue
            v = db / min(it)
            name = k["kernel"]
            if name.startswith(WIDE):
                w16 = max(w16, v)
            elif name.startswith(NARROW):
                w8 = max(w8, v)
        f = S.frac_le8(c)
        if w8 and w16 and f is not None:
            out.append((f, w8 / w16, key[0], w8, w16))
    return out


def main():
    root = S.latest_root()
    if root is None:
        sys.exit("no results/suite-* directory found")
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(3.3, 1.82))
    for bits, marker in ((12, "o"), (16, "^")):
        pts = points(root, "b300", bits)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, s=C.MS_SCATTER, marker=marker,
                   color=C.colour("tech-ours", "OnPair-%d" % bits),
                   edgecolor="none", linewidth=0, zorder=3,
                   label="OnPair-%d" % bits)
        for f, r, ds, a, b in pts:
            sys.stderr.write("bits %d  frac_le8 %.2f  ratio %.3f  %-18s %.0f vs %.0f\n"
                             % (bits, f, r, ds, a, b))
    # The rule at 1.0 needs no label: the y axis IS the ratio to the full-width rate, so parity
    # is what 1.0 means. An annotation here only restated the axis.
    ax.axhline(1.0, color=C.INK, lw=0.8, ls="--", zorder=2)
    ax.set_xlabel("fraction of tokens $\\leq 8$ bytes")
    ax.set_ylabel("$W{=}8$ rate / $W{=}16$ rate")
    ax.set_xlim(-0.03, 1.05)
    ax.grid(axis="y", color="#e6e6e6", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    # IN-AXES, upper left. The relationship is monotone increasing, so that corner is the one
    # region with no marks; a legend below collided with the x-axis label at this figure height.
    ax.legend(frameon=False, fontsize=C.FS["legend"], loc="upper left",
              handletextpad=0.3, borderaxespad=0.2)
    fig.tight_layout()
    C.save(fig, "fig_gatherwidth", width="column")


main()
