# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Plot B300 throughput against at-rest compression ratio for the fifteen-column corpus.

Each FastPair point uses its best validated kernel configuration. Baseline sweeps
are reduced to per-column Pareto frontiers; dominance is checked within each column.
The separate device comparison is in fig_perf_gen.py. Named suite and comparator
legs are selected through suite.py.
"""
import argparse
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import suite as S  # noqa: E402

YLO, YHI = 0, 2000

# Family colors and marker shapes identify codecs; CFG order sets legend order.
CFG = {
    "OnPair-16": C.colour("tech-ours", "OnPair-16"),
    "OnPair-12": C.colour("tech-ours", "OnPair-12"),
    "FSST-12": C.colour("tech-ours", "FSST-12"),
    "DE Deflate (5)": C.colour("tech-engine", "DE Deflate (5)"),
    "DE Deflate (0)": C.colour("tech-engine", "DE Deflate (0)"),
    "DE LZ4": C.colour("tech-engine", "DE LZ4"),
    "DE Snappy": C.colour("tech-engine", "DE Snappy"),
    # The DARK three of the neutral ramp, not the light three. Every Zstd mark falls inside the
    # envelope wash, so the lightest grey (#d9d9d9) was a mark you had to already know was there.
    "Zstd (-10)": C.neutral(1), "Zstd (3)": C.neutral(2), "Zstd (19)": C.neutral(3),
    "Bitcomp-default": C.colour("tech-nvcomp", "Bitcomp-default"),
    "Bitcomp-sparse": C.colour("tech-nvcomp", "Bitcomp-sparse"),
    "gANS": C.colour("tech-nvcomp", "gANS"),
}
FAMILY_MARKER = {"OnPair": "o", "DE": "s", "Zstd": "^", "nvCOMP-sw": "D"}
FAMILY = {
    "OnPair-12": "OnPair", "OnPair-16": "OnPair", "FSST-12": "OnPair",
    "DE Deflate (5)": "DE", "DE Deflate (0)": "DE", "DE LZ4": "DE", "DE Snappy": "DE",
    "Zstd (-10)": "Zstd", "Zstd (3)": "Zstd", "Zstd (19)": "Zstd",
    "gANS": "nvCOMP-sw", "Bitcomp-default": "nvCOMP-sw", "Bitcomp-sparse": "nvCOMP-sw",
}
MARKER = {k: FAMILY_MARKER[v] for k, v in FAMILY.items()}
DEV = "b300"
OFFSCALE = []


# BASIS: every byte-validated kernel, via suite.best_rate_gb_s -- the basis sec:evaluation
# declares and the one the baselines already get. The condition the old comment here set for
# revisiting was met: the DE on this plot IS quoted at its best configuration, best of four codec
# families crossed with five chunk sizes, with its ratio moving with the choice.
def oracle_rate(c):
    """Best kernel on this column, GB/s. The oracle side of an oracle-vs-oracle comparison."""
    return S.best_rate_gb_s(c)



def frontier(pts, xlo=None):
    """Best baseline rate available at each ratio or better, as a staircase."""
    if not pts:
        return [], []
    xs, ys, best = [], [], 0.0
    for x, y in sorted(pts, reverse=True):
        best = max(best, y)
        xs.append(x); ys.append(best)
    xs, ys = list(reversed(xs)), list(reversed(ys))
    if xlo is not None and xs:
        xs, ys = [xlo] + xs, [ys[0]] + ys
    return xs, ys


def frontier_at(pts, ratio):
    vals = [y for x, y in pts if x >= ratio]
    return max(vals) if vals else None


def mark(ax, r, t, color, marker="o", s=None, alpha=1.0):
    """Off-scale marks are drawn open at the floor rather than dropped, so a reader can see that
    a family exists below the axis instead of inferring it never ran."""
    s = C.MS_SCATTER if s is None else s
    if t < YLO:
        OFFSCALE.append((None, t))
        ax.scatter([r], [YLO * 1.04], s=s * 0.8, facecolors="none", marker=marker,
                   edgecolors=color, linewidths=0.7, zorder=5, alpha=alpha)
        return
    ax.scatter([r], [t], s=s, color=color, marker=marker, zorder=5, linewidths=0, alpha=alpha)


def collect(root, rows):
    """(ours, baselines) for one panel. ours: (ratio, rate, cfg, column). baselines: (r, t, cfg)."""
    op = S.cells(root, DEV, "boost", "onpair")
    fs = S.cells(root, DEV, "boost", "fsst12")
    zs = S.cells(root, DEV, "boost", "zstd")
    sw = S.sw_rows(S.sw_root_for(DEV), DEV)
    ours, bases, faded = [], [], []
    for _, ds, col in rows:
        # ZSTD IS DRAWN TWICE, and Section 5 says why: its frame size trades ratio against rate
        # rather than admitting a best setting, so there is no oracle to report. The vendor default
        # (64 KiB, nvCOMP's documented starting chunk) is drawn as-is; every other non-dominated
        # (frame, level) is drawn faded. Falls back to the old single-frame cells when the frame
        # sweep is absent, so this file still runs against an older results tree.
        # ZSTD IS NOT A SCATTER SERIES ANY MORE. It is drawn as three hatched regions, one per
        # level, so plotting the vendor default as well put one arbitrary frame size on the panel
        # as though it were the measurement -- the region is the measurement, and 64 KiB is one
        # point inside it that Section 5 names in prose. Its cells still reach the envelope and
        # the per-column dominance test through zstd_level_points and S.baseline_points.
        bases += S.sw_points(sw, ds, col)
        for cfg, store, bits in (("OnPair-12", op, 12), ("OnPair-16", op, 16),
                                 ("FSST-12", fs, 12)):
            c = store.get((ds, col, bits))
            # CHARGED AT THE PLOTTED KERNEL'S OWN GRANULARITY. oracle_rate is the best kernel over
            # the whole sweep, which varies K, and the sidecar is sized per batch of 32*K codes.
            # Charging the shipped 192 regardless paired a rate with a stored representation that
            # kernel does not read -- on the B300, 12 of the 30 OnPair marks win at some other K.
            r, t = S.ratio(c, S.kernel_tok_per_batch(c, "best")), oracle_rate(c)
            if r and t:
                ours.append((r, t, cfg, col))
        bases += S.de_points(root, DEV, ds, col)
    return ours, bases, faded


# THE X CAP, shared by both panels. Zstd at level 19 reaches ratio 138 on the real columns, which
# set the panel's extent to seven times the highest baseline ratio and squeezed every OnPair mark
# into the left third. Both panels stop at XCAP and take the same left edge, so a compression
# ratio sits at the same place on each.
XCAP = 30.0

# One hatch DIRECTION per level, so a crossing reads as two levels rather than as a denser one
# level. Dense enough to mark the region at column width without moire; hatch.linewidth is set
# with the theme below, since the rcParam is global and the default stroke is too heavy here.
ZSTD_HATCH = {-10: "/" * 12, 3: "\\" * 12, 19: "." * 8}

def clip_to_cap(pts, xs, ys):
    """Trim a staircase at XCAP, with a step AT the cap when the data runs past it.

    Clipped, never extended: a series whose sweep stops short of XCAP stops there too, because
    carrying its last step to the edge would draw a ratio nothing in it reached.
    """
    cx, cy = [], []
    for x, y in zip(xs, ys):
        if x <= XCAP:
            cx.append(x); cy.append(y)
    if pts and max(x for x, _ in pts) > XCAP:
        cx.append(XCAP)
        cy.append(frontier_at(pts, XCAP) or (cy[-1] if cy else 0.0))
    return cx, cy


def zstd_frontiers(ax, rows, xlo):
    """Hatch what each Zstd level reaches, in DISJOINT bands, with each level's frontier drawn.

    THREE LEVELS, NOT ONE POOLED CURVE, because they do not nest by construction. Level -10 owns
    the high-rate corner and 19 the high-ratio one, so a single Zstd region would assert a reach
    no single setting has, and the level is the one Zstd knob a user actually sets.

    EACH FRONTIER IS THE WHOLE SWEEP: every frame measured at that level, staircased into the best
    rate the level reaches at each ratio or better. Not the pruned set the faded marks once drew,
    which would be the frontier of an earlier decision rather than of the measurement.

    HATCHED, NOT FILLED. A solid fill covered the baseline envelope with a shape identical to it
    wherever Zstd was the only baseline left, so the envelope appeared to stop at a ratio it does
    not stop at. Hatch marks the area and the envelope reads straight through.

    DISJOINT BANDS. Three hatched regions layered over each other cross into noise exactly where
    the levels overlap, which on the real columns is nearly everywhere. So at each ratio the
    levels are ordered by what they reach and each one hatches only the slice between its own
    frontier and the next one down. No point on the panel carries two patterns, and the band a
    reader lands in names the most restrictive level that gets there.

    POOLED ACROSS THE PANEL'S COLUMNS, like the envelope around it and for the same reason: it is
    orientation. A codec's ratio is a property of the data, so the dominance claim is asserted per
    column in main() and never read off these bands.

    Returns each level's reach for the caller to report, since some of it falls beyond XCAP.
    """
    curves, out = {}, []
    for lv in S.PAPER_ZSTD_LEVELS:
        pts = []
        for _, ds, col in rows:
            pts += S.zstd_level_points(ds, col, lv)
        if not pts:
            continue
        cx, cy = clip_to_cap(pts, *frontier(pts, xlo=xlo))
        if cx:
            curves[lv] = (pts, cx, cy)
            out.append((lv, len(pts), max(x for x, _ in pts), max(y for _, y in pts)))
    if not curves:
        return out

    # One x grid for all three, so the bands can be cut against each other interval by interval.
    grid = sorted({x for _, cx, _ in curves.values() for x in cx})
    val = {lv: [frontier_at(pts, x) or 0.0 for x in grid] for lv, (pts, _, _) in curves.items()}
    lo = {lv: [0.0] * len(grid) for lv in curves}
    for i in range(len(grid)):
        order = sorted(curves, key=lambda lv: -val[lv][i])
        for k, lv in enumerate(order):
            # Floor at the next level down, or at the axis for the lowest. Ordering is recomputed
            # per interval rather than assumed, because the levels only happen to nest on the real
            # columns -- on the generated ones -10 and 19 cross.
            lo[lv][i] = val[order[k + 1]][i] if k + 1 < len(order) else 1e-3
    for lv in curves:
        # Rasterize the dense dot fill, keeping frontiers and other plot elements vector.
        ax.fill_between(grid, lo[lv], val[lv], step="pre", facecolor="none",
                        edgecolor=CFG["Zstd (%s)" % lv], hatch=ZSTD_HATCH[lv], lw=0, zorder=2,
                        rasterized=(lv == 19))
    for lv, (_, cx, cy) in curves.items():
        ax.step(cx, cy, where="pre", color=CFG["Zstd (%s)" % lv], lw=0.9, zorder=2.5)
    return out


def panel_xmin(root, rows):
    """The left edge one panel needs, before the two are reconciled in main()."""
    ours, bases, faded = collect(root, rows)
    allr = ([r for r, _, _, _ in ours] + [r for r, _, _ in bases]
            + [r for r, _, _ in faded]) or [1.0]
    return min(allr) * 0.88


def panel(ax, root, rows, title, xlim):
    from matplotlib.ticker import FixedLocator, StrMethodFormatter, NullFormatter
    ours, bases, faded = collect(root, rows)
    bp = [(r, t) for r, t, _ in bases]
    # ONE X RANGE FOR BOTH PANELS, passed in rather than fitted per panel. They already share y;
    # fitting x separately meant a ratio sat at a different place on each, so the two halves of
    # one figure could not be read against each other. The right edge is XCAP on both.
    xmin, xmax = xlim
    # THE ENVELOPE INCLUDES THE WHOLE ZSTD FRAME SWEEP, not just the vendor default that is drawn
    # as a point. bp holds the marks; the sweep is measured baseline data too, and leaving it out
    # was why the envelope stopped at ratio 19 while the zones ran past 50 -- it looked like the
    # region was missing its right-hand end because it was. With the sweep in, the envelope
    # reaches the panel edge because a baseline actually reaches it, rather than by carrying its
    # last step flat across ratios no baseline attains.
    env = list(bp)
    for lv in S.PAPER_ZSTD_LEVELS:
        for _, ds, col in rows:
            env += S.zstd_level_points(ds, col, lv)
    xs, ys = frontier(env, xlo=xmin)
    xs, ys = clip_to_cap(env, xs, ys)
    zstd_frontiers(ax, rows, xmin)
    if xs:
        # DO NOT CARRY THE LAST STEP TO THE RIGHT EDGE. It used to, back when xmax sat a few
        # percent past the highest baseline ratio and the carry was a cosmetic gap-filler. With
        # the Zstd tails on the panel, xmax is 157 against a best baseline ratio of 19, and the
        # carry drew the envelope flat across eight times the measured range -- reading as the
        # engine holding 630 GB/s at a ratio it never reaches. The envelope now stops where the
        # baselines stop.
        # C.WASH, not a grey at low alpha: the Zstd levels are drawn from C.NEUTRAL and sit
        # inside this region, so a grey ground swallowed them. See common.WASH.
        ax.fill_between(xs, 1e-3, ys, step="pre", color=C.WASH, lw=0, zorder=1)
        ax.step(xs, ys, where="pre", color=C.INK, lw=0.8, alpha=0.55, zorder=3)
    ax.set_xlim(xmin, xmax)
    # NO FADED SERIES. Every non-dominated (frame, level) used to be drawn at alpha 0.28, which
    # is the same information the zones now carry as area -- and carry better, since a zone shows
    # the whole reach rather than the points that survived a prune. What is left on top of the
    # zones is the vendor default, the one Zstd configuration Section 5 reports as an operating
    # point.
    for r, t, cfg in bases:
        mark(ax, r, t, CFG[cfg], marker=MARKER.get(cfg, "s"))
    for r, t, cfg, _ in ours:
        mark(ax, r, t, CFG[cfg], marker=MARKER[cfg])
    ax.set_xscale("log")
    # FILTERED TO THE LIMITS, and carried past 20. The list was fixed at a 20x ceiling from when
    # the Zstd tails were clipped off the panel; with them drawn, the right third of the real
    # panel had no label under it.
    ticks = [t for t in (1, 1.5, 2, 3, 5, 7, 10, 20, 30, 50) if xmin <= t <= xmax]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
    ax.xaxis.set_minor_locator(FixedLocator([]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("compression ratio (log)")
    ax.set_title(title)
    return ours, bp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite-id", default=None)
    a = ap.parse_args()
    root = S.latest_root(a.suite_id)
    if root is None:
        sys.exit("no results/suite-* directory found")

    plt = C.apply_theme()
    # Global rcParam, so it is set here rather than in common: only this figure hatches.
    plt.rcParams["hatch.linewidth"] = 0.35
    fig, (axR, axS) = plt.subplots(1, 2, figsize=(7.0, 2.05), sharey=True)
    xlim = (min(panel_xmin(root, S.REAL), panel_xmin(root, S.GEN)), XCAP)
    oR, bR = panel(axR, root, S.REAL, "Real-world columns", xlim)
    oS, bS = panel(axS, root, S.GEN, "Generated columns", xlim)
    # GSST reports one number: 191 GB/s on an A100, TPC-H l_comment. That is generated data, so it
    # goes on the synthetic panel, and it is another device, so it is drawn but never enters the
    # baseline frontier or the dominance test.
    axS.scatter([2.74], [C.GSST_GBS], s=C.MS_STAR ** 2, marker="*", color=C.GSST_RED, zorder=6)

    # ASSERTED PER COLUMN, not against the pooled staircase. The staircase is drawn for
    # orientation, but a pooled test compares us on one column against a baseline measured on
    # ANOTHER, and a codec's ratio is a property of the data. c_address is the live example:
    # OnPair-16 reaches 1.09x there, below a 697 GB/s baseline that belongs to l_comment or
    # ps_comment -- different data, not a counterexample. On its own column the DE manages 0.99x,
    # and we are not dominated.
    # EVERY PLOTTED BASELINE IS IN THE TEST. gANS and both Bitcomp variants were drawn and
    # folded into the staircase but left out of this loop, which is the wrong way round: they
    # are the FAST baselines. Bitcomp-sparse reaches 1319 GB/s on FineWeb2, above every OnPair
    # mark on the panel, so a test that skipped it asserted less than the paper's sentence does.
    # It clears the test because it stores 1.00x against our 1.99x, and that is the reason to
    # test it rather than a reason to omit it.
    # ONE KNOWN EXCEPTION, PINNED BY NAME so that a NEW one still fails this build. gANS
    # dominates OnPair-16 on c_address: 1.33x at 653 GB/s against 1.02x at 393. c_address is
    # random characters, so a pair-merging dictionary finds nothing to merge while an entropy
    # coder still finds a character distribution. It is a generated column, and the paper pools
    # generated columns into no real-data claim. It is listed rather than skipped because the
    # scope belongs in the sentence that makes the claim, not in a filter here.
    #
    # Note what is NOT dominated on that column: OnPair-12 reaches 1.19x at 783 GB/s, and
    # gANS's better ratio comes with a lower rate. OnPair-16 is worse than OnPair-12 on BOTH
    # axes there, so the dominated point is a preset no per-column selection would choose.
    KNOWN = {("c_address", "OnPair-16")}
    violations, n, excepted = [], 0, []
    for rows in (S.REAL, S.GEN):
        ours, _, _ = collect(root, rows)
        zc = S.cells(root, DEV, "boost", "zstd")
        sw = S.sw_rows(S.sw_root_for(DEV), DEV)
        by_col = {}
        for _, ds, col in rows:
            by_col[col] = S.baseline_points(root, DEV, ds, col, zc, sw)
        for r, t, cfg, col in ours:
            n += 1
            dom = [b for b in by_col.get(col, []) if b[0] >= r and b[1] > t]
            if dom:
                b = max(dom, key=lambda p: p[1])
                msg = ("%s %s: %.0f GB/s at ratio %.2f, %s %.0f at %.2f"
                       % (col, cfg, t, r, b[2], b[1], b[0]))
                (excepted if (col, cfg) in KNOWN else violations).append(msg)
    if violations:
        raise SystemExit("fig_perf_real: per-column dominance VIOLATED on %s:\n  %s"
                         % (DEV, "\n  ".join(violations)))
    print("per-column dominance holds on %s: %d of %d marks clear every baseline on their own "
          "column, against %d pinned exception(s)" % (DEV, n - len(excepted), n, len(excepted)))
    for m in excepted:
        print("  pinned exception (generated column, in no real-data claim): %s" % m)
    for k in sorted(KNOWN):
        if not any(m.startswith("%s %s:" % k) for m in excepted):
            raise SystemExit("fig_perf_real: pinned exception %s no longer occurs. Remove it "
                             "from KNOWN and strengthen the claim." % (k,))

    from matplotlib.ticker import FixedLocator
    axR.set_ylim(YLO, YHI)
    axR.yaxis.set_major_locator(FixedLocator([0, 500, 1000, 1500, 2000]))
    axR.set_ylabel("decode throughput (GB/s)")

    from matplotlib.lines import Line2D

    def flip(items, ncol):
        return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))

    from matplotlib.patches import Patch
    # Zstd's key entries are hatch swatches now, because Zstd is an area on this panel and a
    # marker in the key would advertise a point series the figure no longer draws.
    codec_handles = [
        Patch(facecolor="none", edgecolor=CFG[k], hatch=ZSTD_HATCH[int(k[6:-1])], label=k)
        if k.startswith("Zstd") else
        Line2D([], [], color=CFG[k], marker=MARKER.get(k, "o"), ls="", ms=C.MS_LEGEND, label=k)
        for k in CFG]
    gsst = Line2D([], [], marker="*", color=C.GSST_RED, ls="", ms=C.MS_STAR * 1.2, label="GSST (A100)")
    # No off-scale entry. YLO is 0, so mark()'s t < YLO branch needs a negative decode rate and
    # never fires; the legend was advertising a convention that never appears on the page. The
    # branch stays as a guard in case the floor is ever raised.
    # NO ENVELOPE ENTRY EITHER, for the same reason one step further: the caption already says
    # what the step line is, and a key that repeats the caption spends a slot to say nothing.
    # SEVEN COLUMNS, so the two rows fall where the reader wants them without a filler: our
    # three codecs and the Engine's four on the first, the whole software side -- three Zstd
    # levels, two Bitcomp variants, gANS -- on the second, and GSST last, since it is the one
    # mark measured on another device.
    leg = codec_handles + [gsst]
    fig.tight_layout(pad=0.3)
    # Fourteen entries over seven columns at full width. mode="expand" spreads them across the
    # whole canvas rather than centring a block, so the two rows align; anchored by their top
    # edge C.LEGEND_GAP under the figure, as every other below-axes key is.
    legend = C.legend_below(fig, handles=flip(leg, 7), expand=True, ncol=7,
                            columnspacing=0.6, handlelength=1.1, handletextpad=0.45)
    C.rasterize_dotted_legend(legend)
    C.save(fig, "fig_perf_real", width="text")

    zcells = S.cells(root, DEV, "boost", "zstd")
    nz = sum(len(S.zstd_points(zcells, ds, col)) for _, ds, col in S.REAL + S.GEN)
    print(f"\nZstd points plotted: {nz}")
    print("BASELINE PROVENANCE, so a reader of this output knows what came from where:")
    print("  gANS, Bitcomp-{default,sparse}: the MATERIALIZE+SW leg, not the paper suite, whose")
    print("                 DE stage runs only DEFLATE/LZ4/Snappy. Same rev, seed and columns.")
    print("  GSST           : drawn on the synthetic panel as a cross-device reference (A100, l_comment)")


if __name__ == "__main__":
    main()
