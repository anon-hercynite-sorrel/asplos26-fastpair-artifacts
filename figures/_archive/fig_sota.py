# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. sota: the result space on ONE device as throughput vs compression ratio.

Every mark is a B300 measurement. This is deliberate and it is the fix for the previous
form, which drew FastPair and Zstd as boxes spanning four GPUs (A100->B300) while the
Blackwell-only DE and nvCOMP codecs were single B300 points: that compared our four-
generation spread against each baseline's best chip, so the visual understated the
same-device margin the prose claims (a ~1.5x apparent gap where the B300-vs-B300 number
is 2.2x on ClickBench URL). Varying the device is now fig_crossarch's job; this figure
varies the codec and holds the device fixed.

The staircase is the BASELINE Pareto frontier: at each compression ratio, the best decode
rate any non-FastPair baseline achieves at that ratio or better. The paper's claim is
positional, that no baseline decodes faster than FastPair at an equal or better ratio on
the same device, so drawing the frontier makes the claim visible rather than something the
reader must reconstruct from a cloud. FastPair marks above and right of the staircase are
the claim. main() asserts it and prints any violation.

Zstd levels that are Pareto-dominated by another level on the SAME column are omitted:
they sit strictly below-left of a kept point, so they cannot affect the frontier or the
claim, and the three levels cost 30 marks. Throughput is LOG: FastPair (TB/s) and
software Zstd (sub-GB/s) span ~4 orders. Two panels (real | synthetic) share the
throughput axis; the synthetic columns reach far higher ratios, so the x-axes differ.
Source: results/b300/onpair_summary_*.json + b300/onpair_nvcomp_hw.json (DE Deflate/LZ4)
+ b300-campaign-0717/onpair_nvcomp_hw.json (DE Snappy overlay + gANS/Bitcomp).
"""
import json

import numpy as np

import common as C

COLS = [
    ("tpch-sf10", "l_comment", "tpch-sf10", "S"),
    ("tpch-sf10", "ps_comment", "tpch-sf10", "S"),
    ("lship", "l_shipinstruct", "tpch-sf10", "S"),
    ("synthetic", "url", "synthetic", "S"),
    ("clickbench", "URL", "clickbench", "R"),
    ("fineweb", "text", "fineweb", "R"),
    ("wikipedia", "text", "wikipedia", "R"),
    ("book-reviews", "text", "book-reviews", "R"),
    ("amazon-movies", "text", "amazon-movies", "R"),
    ("amazon-electronics", "text", "amazon-electronics", "R"),
]
# configuration -> shade, in technique-family families (FastPair blues / DE oranges / Zstd grays).
CFG = {
    "FastPair-12": "#6baed6", "FastPair-16": "#08519c",
    # FSST-12 decoded by the SAME kernels. Drawn in the FastPair family because it is our
    # decoder on a second codec, not a competing system, so it is a claim mark and the
    # baseline frontier is unaffected. Distinct hue so it does not read as a third preset.
    "FSST-12": "#c994c7",
    # Four engine codecs share the square, so the shade ramp is the only thing separating
    # them. It spans the full ColorBrewer Oranges range, roughly even in lightness, after two
    # narrower attempts: the original clustered three of four steps mid-ramp, and the next put
    # Deflate (5) and LZ4 within one step of each other. fig_crossarch draws each column's
    # WINNING codec as a rule in these same shades, so the codecs that win (Deflate (5) on 5
    # columns, LZ4 on 5) must stay legible and mutually distinct as thin lines. Deflate-fast
    # wins no column anywhere, so it takes the faintest slot.
    "DE Deflate (5)": "#fd8d3c", "DE Deflate (0)": "#fdd0a2", "DE LZ4": "#d94801",
    "DE Snappy": "#7f2704",
    "Zstd (-10)": "#cccccc", "Zstd (1)": "#969696", "Zstd (3)": "#525252",
    # nvCOMP's speed-first software codecs (B300, campaign run): they reach FastPair-class
    # decode rate only by nearly abandoning compression (Bitcomp-sparse ~1.0x, gANS ~1.4-2x).
    # Green family, light->dark: Bitcomp-default, gANS, Bitcomp-sparse.
    "gANS": "#41ab5d", "Bitcomp-default": "#a1d99b", "Bitcomp-sparse": "#006d2c",
}
DE_NAME = {"DEFLATE-hi": "DE Deflate (5)", "DEFLATE-fast": "DE Deflate (0)", "LZ4": "DE LZ4",
           "Snappy": "DE Snappy"}
# SHAPE = family, SHADE = variant within family, FILL = on/off-scale. Every mark is one B300
# point now, so shape is free to carry the grouping that the reader actually needs: which
# technique family a mark belongs to. The previous assignment spent four shapes inside the DE
# family alone (square, diamond, up- and down-triangle) while circles were shared between
# FastPair and Zstd, so shape separated variants and merged families, which is backwards for a
# figure whose claim is about families. Within-family identity now rests on the shade ramp; the
# frontier, not the codec label, is what carries the dominance claim.
FAMILY_MARKER = {"FastPair": "o", "DE": "s", "Zstd": "^", "nvCOMP-sw": "D"}
FAMILY = {
    "FastPair-12": "FastPair", "FastPair-16": "FastPair", "FSST-12": "FastPair",
    "DE Deflate (5)": "DE", "DE Deflate (0)": "DE", "DE LZ4": "DE", "DE Snappy": "DE",
    "Zstd (-10)": "Zstd", "Zstd (1)": "Zstd", "Zstd (3)": "Zstd",
    "gANS": "nvCOMP-sw", "Bitcomp-default": "nvCOMP-sw", "Bitcomp-sparse": "nvCOMP-sw",
}
MARKER = {k: FAMILY_MARKER[v] for k, v in FAMILY.items()}


DEV = "b300"   # the one device this figure reports; see the module docstring.


def fp_cfg(fn, col, bits):
    """(ratio, GB/s) for one FastPair preset on the B300, or (None, None)."""
    c = C.cell(DEV, fn, col, bits)
    t = C.best_shipped(c)
    r = (c or {}).get("mem_ratio")
    return (r, t) if (r and t) else (None, None)


def fsst12_cfg(fn, col):
    """(ratio, GB/s) for FSST-12 on the B300, or (None, None).

    Ratio is the container-matched measure, which is the like-for-like comparison against
    OnPair's BtrBlocks-measured ratio on the same axis; on these columns it agrees with the
    native figure to two decimals. Falls back to native where the field is absent.
    """
    c = C.cell(DEV, fn, col, 12, C.FSST12)
    if not c:
        return (None, None)
    t = C.best_shipped(c)
    r = c.get("mem_ratio_container_matched") or c.get("mem_ratio")
    return (r, t) if (r and t) else (None, None)


def zstd_cfg(fn, col, level):
    """(ratio, GB/s) for one Zstd level on the B300, or (None, None)."""
    c = C.cell(DEV, fn, col, 12) or C.cell(DEV, fn, col, 16)
    for e in ((c or {}).get("gpu") or {}).get("nvcomp_zstd") or []:
        if (isinstance(e, dict) and str(e.get("zstd_level")) == level
                and e.get("compression_ratio") and C.zstd_gb_s(e)):
            return e["compression_ratio"], C.zstd_gb_s(e)
    return None, None


def undominated(pts):
    """Keep only Pareto-optimal (ratio, rate) points: nothing else is >= on both axes.

    Used to prune Zstd levels within a column. A dropped point is strictly worse on both
    axes than a kept one, so it can move neither the frontier nor the dominance claim.
    """
    keep = []
    for i, (r, t, *rest) in enumerate(pts):
        if not any(j != i and pts[j][0] >= r and pts[j][1] >= t
                   and (pts[j][0] > r or pts[j][1] > t) for j in range(len(pts))):
            keep.append((r, t, *rest))
    return keep


def frontier(pts, xlo=None):
    """Step path of F(x) = best baseline rate at ratio x or better, in ASCENDING x.

    F is piecewise constant and non-increasing: raising the ratio requirement can only
    drop competitors. Breakpoints are the baselines' own ratios, and on the interval
    (x_{k-1}, x_k] the qualifying set is {r >= x_k}, so the arrays are meant to be drawn
    with step(where="pre"). Ascending order matters: an earlier version built this path
    right to left, which matplotlib's step renders as a near-flat line and made the
    envelope look like a 1 TB/s ceiling across every ratio.
    """
    if not pts:
        return [], []
    xs = sorted({r for r, _ in pts})
    if xlo is not None and xlo < xs[0]:
        xs = [xlo] + xs
    return xs, [frontier_at(pts, x) for x in xs]


def frontier_at(pts, ratio):
    """Best baseline rate at `ratio` or better; 0.0 if no baseline reaches that ratio."""
    vals = [t for r, t in pts if r >= ratio]
    return max(vals) if vals else 0.0


def _edge(color, f=0.7):
    """A faint outline keyed to the marker's own color (a darker shade), so overlapping
    points stay distinct without a stark white halo."""
    import matplotlib.colors as mc
    r, g, b = mc.to_rgb(color)
    return (r * f, g * f, b * f)


YLO, YHI = 100.0, 2600.0
# Below YLO there is nothing but dominated nvCOMP-Zstd levels, and on a log axis that dead
# band ate ~2.5 of 4 decades, compressing the whole competitive region (and the margin over
# the frontier) into a sliver. Points below the floor are pinned to it as hollow down-
# triangles and their true range is reported for the caption, so they are marked off-scale,
# not dropped.
OFFSCALE = []


def mark(ax, r, t, color, marker="o", s=20, label=None):
    if not (r and t):
        return
    if t < YLO:
        # Off-scale keeps its family's shape and its own color, hollow and pinned to the
        # floor, so it reads as "this series, below the axis" rather than as a fourth
        # family. A dedicated off-scale shape would collide with whichever family it borrowed.
        OFFSCALE.append((label, t))
        ax.scatter([r], [YLO * 1.04], s=s * 0.8, facecolors="none", marker=marker,
                   edgecolors=_edge(color), linewidths=0.7, zorder=4, alpha=0.95)
        return
    ax.scatter([r], [t], s=s, color=color, marker=marker, zorder=5,
               edgecolors=_edge(color), linewidths=0.3, alpha=0.95)


def collect(origin, de, gb):
    """(fastpair, baselines) point lists for one panel, all on DEV.

    fastpair: (ratio, rate, config-label, column-label). baselines: (ratio, rate, label).
    GSST is excluded from the baseline frontier: it is a published A100 number, so folding
    it into a same-device envelope would be exactly the cross-device mixing this figure
    exists to remove. It is still drawn, and the caption marks it cross-paper.
    """
    fps, bases = [], []
    for fn, col, did, orig in COLS:
        if orig != origin:
            continue
        for bits in (12, 16):
            r, t = fp_cfg(fn, col, bits)
            if r:
                fps.append((r, t, "FastPair-%d" % bits, col))
        r, t = fsst12_cfg(fn, col)
        if r:
            fps.append((r, t, "FSST-12", col))
        d = de.get((did, col))
        if d:
            for name, eng in (d.get("codecs") or {}).items():
                lbl = DE_NAME.get(name, "DE %s" % name)
                if lbl in CFG and eng.get("ratio") and eng.get("decode_gib_s"):
                    bases.append((eng["ratio"], eng["decode_gib_s"] * C.GIB_TO_GB, lbl))
            # Those per-codec entries are measured at the DEFAULT chunk size. The engine's
            # declared baseline (Section 6.1) is its best codec AND chunk size per column,
            # carried in top-level best_decode_gib_s/best_ratio and read by common.de_map.
            # It runs up to ~3% faster than any per-codec entry, so the frontier must include
            # it or the envelope understates the engine and flatters the dominance claim.
            blbl = DE_NAME.get(d.get("best_codec"), "DE %s" % d.get("best_codec"))
            if blbl in CFG and d.get("best_ratio") and d.get("best_decode_gib_s"):
                bases.append((d["best_ratio"], d["best_decode_gib_s"] * C.GIB_TO_GB, blbl))
        zs = [(r, t, "Zstd (%s)" % lvl) for lvl in ("-10", "1", "3")
              for r, t in [zstd_cfg(fn, col, lvl)] if r]
        bases.extend(undominated(zs))   # dominated levels add marks, never information
        for name in ("gANS", "Bitcomp-default", "Bitcomp-sparse"):
            e = (gb.get((did, col)) or {}).get(name) or {}
            if e.get("ratio") and e.get("decode_gib_s"):
                bases.append((e["ratio"], e["decode_gib_s"] * C.GIB_TO_GB, name))
    return fps, bases


def panel(ax, origin, title, de, gb):
    fps, bases = collect(origin, de, gb)
    bp = [(r, t) for r, t, _ in bases]
    xs, ys = frontier(bp, xlo=min([r for r, _, _, _ in fps] + [r for r, _ in bp]) * 0.92)
    if xs:
        ax.step(xs, ys, where="pre", color=C.INK, lw=0.8, alpha=0.55, zorder=3)
        ax.fill_between(xs, 1e-3, ys, step="pre", color=C.INK, alpha=0.055,
                        lw=0, zorder=1)
    for r, t, lbl in bases:
        mark(ax, r, t, CFG[lbl], marker=MARKER.get(lbl, "o"), s=26, label=lbl)
    for r, t, lbl, _ in fps:
        mark(ax, r, t, CFG[lbl], marker="o", s=22, label=lbl)
    if origin == "S":
        ax.scatter([2.74], [C.GSST_GBS], s=80, marker="*", color=C.GSST_RED, zorder=5)
    from matplotlib.ticker import FixedLocator, ScalarFormatter, NullFormatter
    ax.set_xscale("log")
    xticks = [1.5, 2, 3, 5, 7, 10, 20] if origin == "S" else [1.5, 2, 3, 5, 7]
    ax.xaxis.set_major_locator(FixedLocator(xticks))
    ax.xaxis.set_major_formatter(ScalarFormatter()); ax.xaxis.set_minor_locator(FixedLocator([]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("compression ratio (log)"); ax.set_title(title, fontsize=8)


def main():
    de = {(e["dataset_id"], e["column"]): e
          for e in json.load(open(C.RESULTS / "b300" / "onpair_nvcomp_hw.json"))}
    # Overlay the DE Snappy codec from the all-codec campaign run (b300-campaign-0717, same B300
    # class, reproduces the canonical b300 Deflate/LZ4). Canonical b300 has no Snappy; this ADDS
    # Snappy points without touching the existing Deflate/LZ4 points. Snappy edges LZ4 only on the
    # long-text columns (~5%); on every throughput-bound headline column Deflate-hi still leads.
    try:
        snap = {(e["dataset_id"], e["column"]): e
                for e in json.load(open(C.RESULTS / "b300-campaign-0717" / "onpair_nvcomp_hw.json"))}
        for k, e in de.items():
            s = snap.get(k, {}).get("codecs", {}).get("Snappy")
            if s and s.get("valid"):
                e["codecs"]["Snappy"] = s
    except FileNotFoundError:
        pass
    gb = {}
    try:
        for line in (C.RESULTS / "b300-campaign-0717" / "gans_bitcomp.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                gb[(r["dataset_id"], r["column"])] = (r.get("sw") or {}).get("codecs", {})
    except FileNotFoundError:
        pass
    plt = C.apply_theme()
    fig, (axR, axS) = plt.subplots(1, 2, figsize=(7.0, 2.03), sharey=True)
    panel(axR, "R", "Real-world columns", de, gb)
    panel(axS, "S", "Synthetic columns", de, gb)
    # Assert the claim the frontier draws: every FastPair mark clears the best baseline
    # available at its ratio or better, on this device. A violation must change the prose,
    # so it fails the build rather than shipping a figure that contradicts the text.
    violations = []
    for origin in ("R", "S"):
        fps, bases = collect(origin, de, gb)
        bp = [(r, t) for r, t, _ in bases]
        for r, t, lbl, col in fps:
            f = frontier_at(bp, r)
            if f and t <= f:
                violations.append("%s %s: %.0f GB/s at ratio %.2f, baseline %.0f" % (col, lbl, t, r, f))
    if violations:
        raise SystemExit("fig_sota: dominance claim VIOLATED on %s:\n  %s"
                         % (DEV, "\n  ".join(violations)))
    print("dominance holds on %s: all %d FastPair marks clear the baseline frontier"
          % (DEV, sum(len(collect(o, de, gb)[0]) for o in ("R", "S"))))
    # LOG throughput: FastPair (TB/s) and software Zstd (sub-GB/s) span ~4 orders; linear buried
    # the low end. Log keeps every family visible on one axis.
    axR.set_yscale("log")
    axR.set_ylim(YLO, YHI)
    axR.set_ylabel("decode (GB/s, log)")
    # Label the decades 100 / 1000, not 10^2 / 10^3. The axis carries GB/s values a reader
    # compares against rates quoted in the prose, and exponent notation adds a step to that.
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
    axR.yaxis.set_major_locator(FixedLocator([100, 200, 500, 1000, 2000]))
    axR.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%d" % v))
    axR.yaxis.set_minor_locator(FixedLocator([]))
    axR.yaxis.set_minor_formatter(NullFormatter())
    if OFFSCALE:
        lo, hi = min(t for _, t in OFFSCALE), max(t for _, t in OFFSCALE)
        fams = sorted({(l or "?").split(" (")[0] for l, _ in OFFSCALE})
        print("off-scale below %.0f GB/s: %d marks, %.1f-%.1f GB/s, families: %s"
              % (YLO, len(OFFSCALE), lo, hi, ", ".join(fams)))
    from matplotlib.lines import Line2D
    import itertools

    def flip(items, ncol):
        return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))

    # Every series is now a single B300 point, so every swatch is its marker shape. The
    # old line swatches encoded the four-GPU range this figure no longer draws.
    codec_handles = [
        Line2D([], [], color=CFG[k], marker=MARKER.get(k, "o"), ls="", ms=5.5, label=k)
        for k in CFG
    ]
    gsst = Line2D([], [], marker="*", color=C.GSST_RED, ls="", ms=9,
                  label="GSST (A100)")
    # Place GSST (a GPU decoder) right after the DE marks so row 1 groups the fast
    # decoders (FastPair + DE + GSST) and Zstd(-10) falls to row 2 with the software field.
    # The off-scale swatch borrows the Zstd triangle because every off-scale mark is Zstd
    # today; the label says "open" so the convention still reads correctly if another
    # family ever falls below the floor.
    offscale_shape = FAMILY_MARKER[FAMILY.get(OFFSCALE[0][0], "Zstd")] if OFFSCALE else "^"
    extra = [
        Line2D([], [], color=C.INK, lw=0.8, alpha=0.55, label="baseline envelope"),
        Line2D([], [], color=C.INK, marker=offscale_shape, ls="", ms=5, markerfacecolor="none",
               label="off-scale (open)"),
    ]
    leg = codec_handles[:6] + [gsst] + codec_handles[6:] + extra
    # Span the full figure width: a 4-tuple bbox (x0, y0, w, h) with mode="expand"
    # stretches the legend columns edge to edge rather than clustering them centered.
    fig.legend(handles=flip(leg, 8), frameon=False, fontsize=6.3, ncol=8, loc="lower center",
               bbox_to_anchor=(0.0, -0.01, 1.0, 0.13), mode="expand",
               columnspacing=0.6, handlelength=1.1, handletextpad=0.45, borderaxespad=0.0)
    fig.tight_layout(rect=(0, 0.155, 1, 1))
    C.save(fig, "fig_sota")


if __name__ == "__main__":
    main()
