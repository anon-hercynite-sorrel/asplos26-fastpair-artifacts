# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib"]
# ///
"""Fig. perf_gen: decode rate per column across devices AND across SM clock.

The companion to fig_perf_real, which fixes the device and varies the codec. This varies the
device and the clock, and shows one kernel family covering the whole matrix.

LAYOUT. One slot per column. Inside a slot, one short VERTICAL LINE per GPU, packed side by side.
Each line carries that GPU's decode rate at every clock state it was measured at, so the line's
extent IS the clock sensitivity of that chip on that column. Four horizontal BARS across the slot
are the B300 Decompression Engine's four codecs, each at its own best chunk size.

DRAWN AT ITS PRINTED SIZE. This is a two-column float landing at about seven inches, so figsize
matches that. An earlier version was drawn ten inches wide and scaled down on the page, which
shrank every label by a third and made the figure unreadable in print.

ENCODING. Colour is the GPU, grouped by MEMORY TECHNOLOGY: the three HBM parts take a blue ramp
and the GDDR6 L40S green. That is the axis that separates these chips for this kernel, and it also
keeps every chip clear of the orange the DE bar uses. Marker shape is the CLOCK STATE, and it is
assigned by nominal state (boost, max, 75%, 55%, 40%) rather than by absolute MHz, because the
same nominal state lands on different frequencies per part -- 1905 MHz on the B300 is 'max', so is
1830 on the H100 and 2520 on the L40S. Shape therefore means the same experimental condition on
every chip, which is what the reader needs to compare.

WHY THE CLOCK ARM IS HERE AND NOT ITS OWN FIGURE. It is the falsification, not a curiosity: with
the memory clock pinned, decode rate that scales with the SM clock rules out DRAM bandwidth, DRAM
latency, and an L2 request-rate bound, because l1tex runs at the SM clock while L2 and DRAM are
separate domains. It does NOT separate L1 request rate from compute, issue, register file or
shared memory, and this figure does not claim it does.

BEST AGAINST BEST, PER CODEC. Each DE bar is one codec at its best chunk size; our marks are the
best kernel. Both sides tuned, neither handicapped. Collapsing the engine to a single best-of-four
bar named one codec in the legend and hid the other three, so the reader could not see that most
of the engine's spread on these columns is the codec choice rather than the chunk size. Four bars
is not the twenty-configuration cloud an early draft drew: the chunk sweep is still reduced away,
only the codec axis survives.

MISSING CHIPS KEEP THEIR SLOT AND THEIR LEGEND ENTRY. A leg that has not landed leaves a labelled
gap, so a reader sees three chips and a hole rather than assuming three was the design.

Source: results/suite-<id>/<chip>/sweep_summary_*_{boost,sm*}.json + b300/onpair_nvcomp_hw.json.
"""
import argparse
import sys
from pathlib import Path

from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import suite as S  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fig_perf_gen.pdf"

# HBM parts take the blue ramp, the GDDR6 part green. Memory technology is the axis that
# actually separates these chips for this kernel, and keeping the non-HBM part out of the blues
# also keeps every chip clear of the orange the DE bars use.
# GDDR7 joins the GREEN family, not the blues, and takes the dark rung so the GDDR pair reads as a
# ramp exactly like the HBM triple does. That keeps the figure's encoding honest: colour family is
# memory technology, lightness is position within it. It also matters for what this chip is FOR --
# RTX PRO 6000 is Blackwell silicon behind GDDR7, so it sits beside the B300 in architecture and
# opposite it in memory, and a reader must be able to see which of those the colour tracks.
# From common's device family, which is ordered HBM-then-GDDR so scale position carries the
# memory-technology grouping this figure encodes.
# Layout order is the paper-wide one, filtered to the chips whose legs landed.
def ordered_chips():
    return C.devices(S.chips())


CHIP_COLOR = {"a100": C.colour("device-hbm", "A100"), "h100": C.colour("device-hbm", "H100"),
              "b300": C.colour("device-hbm", "B300"),
              "l40s": C.colour("device-gddr", "L40S"),
              "rtxpro": C.colour("device-gddr", "RTX PRO")}
CHIP_MEM = {"b300": "HBM", "h100": "HBM", "a100": "HBM", "l40s": "GDDR6", "rtxpro": "GDDR7"}
CHIP_LABEL = {"b300": "B300", "h100": "H100", "a100": "A100", "l40s": "L40S",
              "rtxpro": "RTX PRO 6000"}
# GLYPH SCALE, LOCAL TO THIS FIGURE. C.MS is shared with fig_perf_real and fig_grid, and this is
# the densest of the three: five clock states x five chips in every column slot, so the marks
# crowd where fig_perf_real's do not. Scaled here rather than in common.py so the other two keep
# the size they were tuned at.
GLYPH = 0.65

# Nominal clock state -> marker. Ordered as the campaign requests them.
STATE_MARK = [("boost", "*"), ("max", "o"), ("75%", "s"), ("55%", "^"), ("40%", "D")]
# SAME BAND AS fig_perf_real AND fig_teaser. The Engine has to be one colour across the paper,
# and it appears in all three of those figures, so it keeps the tech-engine band everywhere and
# the device bands are placed to avoid it rather than the other way round.
DE_SHADE = {"DEFLATE-hi": C.colour("tech-engine", "DE Deflate (5)"),
            "DEFLATE-fast": C.colour("tech-engine", "DE Deflate (0)"),
            "LZ4": C.colour("tech-engine", "DE LZ4"),
            "Snappy": C.colour("tech-engine", "DE Snappy")}
DE_LABEL = {"DEFLATE-hi": "Deflate (5)", "DEFLATE-fast": "Deflate (0)", "LZ4": "LZ4",
            "Snappy": "Snappy"}
BITS = 12          # one preset; adding OnPair-16 would triple the marks per slot


def nominal_states(root, chip):
    """Map this chip's tags to nominal states. Pinned tags ascend 40% < 55% < 75% < max."""
    tags = S.clock_tags(root, chip)
    pinned = [t for t in tags if t != "boost"]
    names = ["40%", "55%", "75%", "max"][-len(pinned):] if pinned else []
    out = {t: n for t, n in zip(pinned, names)}
    if "boost" in tags:
        out["boost"] = "boost"
    return out


def best_rate(c):
    """Best kernel on this cell, GB/s -- the same basis the DE bar uses.

    gpu.best_kernel/best_decode_gib_s range over the production kernels only, which express K but
    not T, B or S, so they were the best rate the CURRENT SELECTOR can reach rather than the best
    the codec reaches. The DE bar beside this one is best-of-twenty (four codecs x five chunk
    sizes), so suite.best_rate_gb_s is what makes the two sides the same kind of number.
    """
    return S.best_rate_gb_s(c)


# de_best is gone: it returned one rate and the name of the codec that produced it, which is what
# a single bar per slot needed. suite.de_by_codec returns all four, keyed by codec.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite-id", default=None)
    a = ap.parse_args()
    root = S.latest_root(a.suite_id)
    if root is None:
        sys.exit("no results/suite-* directory found")

    rows = [(lab, ds, col, "real") for lab, ds, col in S.REAL] + \
           [(lab, ds, col, "gen") for lab, ds, col in S.GEN]
    # PER-CHIP ROOT. The fifth chip was brought up after the paper campaign and lives in its own
    # leg, at the same revision, seed, corpus and clock protocol -- so it belongs on this axis, but
    # it is not in the same directory. Resolving the root per chip is what lets one figure draw a
    # multi-leg campaign; using a single root silently drew it as an absent series.
    roots = {c: (S.chip_root(c, a.suite_id) or root) for c in ordered_chips()}
    states = {c: nominal_states(roots[c], c) for c in ordered_chips()}
    data = {c: {t: S.cells(roots[c], c, t, "onpair") for t in S.clock_tags(roots[c], c)}
            for c in ordered_chips()}

    # SIZED TO ITS RENDERED WIDTH. This is a two-column float, so it lands at about 7 inches. A
    # 10-inch figsize is scaled down by a third on the page and takes every font with it, which
    # is why the previous version could not be read at print size. Draw it the size it is shown.
    # THE THEME, which this generator went without: it imported pyplot directly and drew on
    # matplotlib's defaults, so its ticks and axis labels came out at 10pt against the 7 and 8
    # every other figure declares, and it kept the default four-sided box. That is why it was
    # the one figure whose type looked oversized on the page.
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(7.1, 2.05))
    slot = 1.0
    per_chip = (slot * 0.72) / len(ordered_chips())
    absent, drawn, de_seen = [], 0, set()

    for i, (lab, ds, col, grp) in enumerate(rows):
        x0 = i * slot
        # FOUR BARS: every codec the engine offers, each at its own best chunk size. A single
        # best-of-four bar named one codec in the legend and hid the other three, so a reader
        # could not see how much of the engine's spread is the codec choice -- which on these
        # columns is most of it. Drawn in DE_SHADE order so the z-stacking is deterministic
        # where two codecs land on the same rate.
        per_codec = S.de_by_codec(root, "b300", ds, col)
        for codec in DE_SHADE:
            v = per_codec.get(codec)
            if v is None:
                continue
            de_seen.add(codec)
            ax.hlines(v, x0 - slot * 0.44, x0 + slot * 0.44,
                      color=DE_SHADE[codec], lw=1.4, alpha=.95, zorder=2)
        for codec in per_codec:
            if codec not in DE_SHADE:
                sys.stderr.write("fig_perf_gen: no shade for engine codec %r, not drawn\n" % codec)

        for j, chip in enumerate(ordered_chips()):
            xc = x0 - slot * 0.39 + per_chip * (j + 0.5)
            tags = states.get(chip) or {}
            pts = []
            for tag, nominal in tags.items():
                c = data[chip].get(tag, {}).get((ds, col, BITS))
                v = best_rate(c)
                if v is not None:
                    pts.append((nominal, v))
            if not pts:
                absent.append(f"{chip}/{ds}/{col}")
                continue
            ys = [v for _, v in pts]
            # Thin and dotted: the line exists to tie one chip's clock states together, not to
            # be read as a value, so it should not carry more ink than the marks it connects.
            ax.vlines(xc, min(ys), max(ys), color=CHIP_COLOR[chip], lw=0.6, alpha=.85,
                      linestyles=(0, (1, 1.2)), zorder=3)
            for nominal, v in pts:
                mk = dict(STATE_MARK).get(nominal, ".")
                # No marker edge. A white edge on a white ground eats into the mark and haloes
                # wherever two clock states land close together, which is most of this figure.
                ax.plot([xc], [v], marker=mk,
                        ms=GLYPH * (C.MS if mk != "*" else C.MS_STAR),
                        color=CHIP_COLOR[chip], mec="none", zorder=4, ls="")
                drawn += 1

    ax.set_xticks([i * slot for i in range(len(rows))])
    SHORT = {"FineWeb2 Mandarin": "FineWeb2", "Loghub \\texttt{Android}": "Android",
             "ClickBench \\texttt{URL}": "URL", "ClickBench \\texttt{Title}": "Title",
             "Loghub \\texttt{HDFS}": "HDFS", "Loghub \\texttt{Thunderbird}": "Thunderbird",
             "Loghub \\texttt{Spark}": "Spark", "Loghub \\texttt{Windows}": "Windows",
             "TPC-H \\texttt{c\\_address}": "c_address",
             "TPC-H \\texttt{l\\_comment}": "l_comment",
             "TPC-H \\texttt{o\\_clerk}": "o_clerk",
             "TPC-H \\texttt{l\\_shipinstruct}": "l_shipinstruct",
             "TPC-H \\texttt{ps\\_comment}": "ps_comment"}
    ax.set_xticklabels([SHORT.get(lab, lab) for lab, _, _, _ in rows],
                       rotation=40, ha="right")
    # The rule between real and generated columns: they are never pooled into one claim.
    ax.axvline(len(S.REAL) * slot - slot * 0.5, color="#444444", lw=.9, ls=":")
    from matplotlib.ticker import FixedLocator
    ax.set_ylim(0, 2000)
    ax.yaxis.set_major_locator(FixedLocator([0, 500, 1000, 1500, 2000]))
    ax.set_ylabel("decode throughput (GB/s)")
    ax.grid(axis="y", alpha=.25, lw=.5)
    ax.set_axisbelow(True)

    # Every chip keeps its entry whether or not the leg has landed; results drop straight in.
    chips = [Line2D([], [], color=CHIP_COLOR[c], lw=2, label=f"{CHIP_LABEL[c]} ({CHIP_MEM[c]})")
             for c in ordered_chips()]
    marks = [Line2D([], [], color="#444444", marker=m, ls="", label=n,
                    markersize=GLYPH * C.MS_LEGEND) for n, m in STATE_MARK]
    de = [Line2D([], [], color=DE_SHADE[k], lw=1.4, label=f"DE {DE_LABEL[k]}")
          for k in DE_SHADE if k in de_seen]
    # BELOW the axes, matching fig_perf_real so the two read as a pair. The x labels are rotated
    # column names and occupy the lower margin, so the anchor sits below them rather than at the
    # axes edge; bbox_inches="tight" then grows the canvas to include it.
    fig.tight_layout(pad=0.3)
    # CHIPS, then the DE bars, then the clock states. The clock states sat between the two
    # colour groups, which put the one non-colour distinction in the figure between the two that
    # are colour; reading the key meant crossing it twice.
    #
    # Keep each group in whole columns, with three rows to fit the larger legend.
    def pad(group, rows=3):
        return group + [Line2D([], [], ls="", marker="", label="")] * ((-len(group)) % rows)

    handles = pad(chips) + pad(de) + pad(marks)
    C.legend_below(fig, handles=handles, expand=True, ncol=len(handles) // 3,
                   columnspacing=0.9, handlelength=1.3, handletextpad=0.45)

    # Through C.save, like every other figure: it is what draws this at the exact width the
    # figure* float prints it at, so the sizes in C.FS are the sizes on the page.
    C.save(fig, "fig_perf_gen", width="text")
    print(f"points drawn: {drawn}")
    if absent:
        print(f"ABSENT series: {len(absent)} (slot and legend entry kept)")
        for c in ordered_chips():
            n = sum(1 for x in absent if x.startswith(c + "/"))
            if n:
                print(f"  {c}: {n} columns")


if __name__ == "__main__":
    main()
