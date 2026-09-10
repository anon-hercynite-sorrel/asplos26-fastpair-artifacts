# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. crossarch: per-column decode rate on all four GPUs, for all three techniques.

The companion to fig_sota, which fixes the device and varies the codec; this varies both, and
shows one kernel family covering the whole matrix. One slot per column. Within a slot, three
short connected strips sit side by side, one per technique (OnPair-12, OnPair-16, FSST-12),
each joining that technique's four chips in bandwidth order. A rule per column marks that
column's B300 Decompression Engine rate.

WHY THE TECHNIQUES ARE DODGED RATHER THAN OVERLAID. FSST-12 lands within 10% of OnPair-12 on
eight of the nine columns that carry all three (0.96x FineWeb, 1.01x book-reviews, 1.00x
amazon-electronics). At a shared x they would be one illegible band, and the figure's most
interesting fact, that a second codec tracks the first through the same kernels, would read as
overplotting. Dodging guarantees separation whatever the rates do, so the residual vertical
gap carries information instead of noise.

ENCODING. Colour stays on the GPU: "which chip is this dot" has to survive without a leader
line, and the four-chip ramp is already established across the paper. Technique therefore
takes TWO redundant channels, marker shape and line style, so it survives greyscale printing
and a reader who has not yet consulted the legend.

This replaced a two-panel form (one panel per preset), which could not hold a third technique:
FSST-12 has a single configuration and no preset to be panelled by, so it had nowhere to go.
That in turn replaced a slopegraph (GPUs on x, one line per column), which failed because at
the L40S the eight real columns span just 30%, so ten lines entered almost coincident.

Ordering is synthetic then real, each by B300 OnPair-12 rate descending.
Source: results/{a100,l40s,h100,b300}/onpair_summary_*.json (OnPair),
results/{a100,l40s,h100,b300}-fsst12/ (FSST-12), b300/onpair_nvcomp_hw.json (engine, via
common.de_map: best codec AND chunk size per column).
"""
import json

import numpy as np

import common as C

# Ordered by vendor peak bandwidth: L40S 0.86, A100 1.56, H100 3.35, B300 8.0 TB/s.
ORDER = ["l40s", "a100", "h100", "b300"]
# The L40S is the one GDDR6 part and the paper leans on that; give it its own hue and put the
# three HBM chips on a light-to-dark blue ramp so their order reads as a ramp.
GPU_COLOR = {"l40s": "#74c476", "a100": "#9ecae1", "h100": "#3182bd", "b300": "#08519c"}

# (label, bits, codec, marker, linestyle, line colour). Marker and linestyle both carry the
# technique, so neither channel is load-bearing alone. FSST-12's purple matches fig_sota.
TECHS = [
    ("OnPair-12", 12, C.ONPAIR, "o", "-", "#b0b5ba"),
    ("OnPair-16", 16, C.ONPAIR, "s", "--", "#b0b5ba"),
    ("FSST-12", 12, C.FSST12, "^", ":", "#c994c7"),
]
# x offset of each technique's strip within a slot, and of each chip within a strip.
# Sized so each technique's four chips span a visible run rather than a near-vertical
# tick: strips 0.30 wide, centred 0.31 apart, which fills the slot without letting a strip
# cross into its neighbour.
TECH_DODGE = [-0.31, 0.0, 0.31]
GPU_DODGE = [-0.15, -0.05, 0.05, 0.15]

# (dataset, column, label, origin); S = synthetic, R = real, matching fig_sota's split.
COLS = [
    ("tpch-sf10", "l_comment", "TPC-H l_comment", "S"),
    ("tpch-sf10", "ps_comment", "TPC-H ps_comment", "S"),
    ("lship", "l_shipinstruct", "l_shipinstruct", "S"),
    ("synthetic", "url", "synthetic URL", "S"),
    ("clickbench", "URL", "ClickBench URL", "R"),
    ("fineweb", "text", "FineWeb text", "R"),
    ("wikipedia", "text", "Wikipedia text", "R"),
    ("book-reviews", "text", "book-reviews", "R"),
    ("amazon-movies", "text", "amazon-movies", "R"),
    ("amazon-electronics", "text", "amazon-electronics", "R"),
]
# The OnPair matrix files l_shipinstruct under the `lship` alias; the FSST-12 sends filed it
# under its real dataset id. Same column, two keys, so the lookup must bridge them or the
# FSST-12 strip silently vanishes from that slot.
FSST12_ALIAS = {("lship", "l_shipinstruct"): ("tpch-sf10", "l_shipinstruct")}

SHORT = {
    "TPC-H l_comment": "l_comment", "TPC-H ps_comment": "ps_comment",
    "l_shipinstruct": "l_shipinstr.", "synthetic URL": "synth. URL",
    "ClickBench URL": "ClickBench", "FineWeb text": "FineWeb",
    "Wikipedia text": "Wikipedia", "book-reviews": "book-rev.",
    "amazon-movies": "amz-movies", "amazon-electronics": "amz-electr.",
}

DE_CODEC_NAME = {"DEFLATE-hi": "Deflate (5)", "DEFLATE-fast": "Deflate (0)",
                 "LZ4": "LZ4", "Snappy": "Snappy"}
DE_CODEC_COLOR = {"Deflate (5)": "#fd8d3c", "Deflate (0)": "#fdd0a2",
                  "LZ4": "#d94801", "Snappy": "#7f2704"}


def rates(dataset, column, bits, codec=C.ONPAIR):
    """{gpu: GB/s} for one column, preset and codec, omitting GPUs with no cell."""
    if codec == C.FSST12:
        dataset, column = FSST12_ALIAS.get((dataset, column), (dataset, column))
    out = {}
    for g in ORDER:
        t = C.best_shipped(C.cell(g, dataset, column, bits, codec))
        if t:
            out[g] = t
    return out


def de_rates():
    """{(dataset, column): (GB/s, winning codec)} for the B300 engine, via common.de_map().

    MUST go through de_map(), which reads the JSON's top-level best_decode_gib_s: the best
    over codec AND chunk size, the baseline Section 6.1 declares. The per-codec `codecs`
    block is measured at the DEFAULT chunk only, so a max over it understates the engine
    (419.7 against de_map's 432.2 GB/s on ClickBench URL). An earlier version took that max,
    which flattered our margins and briefly propagated into the paper's multiples.
    """
    dm = C.de_map()
    raw = {(e["dataset_id"], e["column"]): e
           for e in json.load(open(C.RESULTS / "b300" / "onpair_nvcomp_hw.json"))}
    out = {}
    for dataset, column, _, _ in COLS:
        did = "tpch-sf10" if dataset in ("tpch-sf10", "lship") else dataset
        rate = dm.get((did, column))
        if not rate:
            continue
        codec = (raw.get((did, column)) or {}).get("best_codec")
        out[(dataset, column)] = (rate, DE_CODEC_NAME.get(codec, codec or "best"))
    return out


def main():
    de = de_rates()
    order = sorted(COLS, key=lambda c: (0 if c[3] == "S" else 1,
                                        -(rates(c[0], c[1], 12).get("b300") or 0)))
    split = sum(1 for c in order if c[3] == "S")

    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(7.0, 3.1))

    for x, (dataset, column, label, _) in enumerate(order):
        for (tlabel, bits, codec, marker, ls, lc), tdodge in zip(TECHS, TECH_DODGE):
            rs = rates(dataset, column, bits, codec)
            if not rs:
                continue
            present = [g for g in ORDER if g in rs]
            xs = [x + tdodge + d for d, g in zip(GPU_DODGE, ORDER) if g in rs]
            ys = [rs[g] for g in present]
            if len(xs) > 1:
                ax.plot(xs, ys, color=lc, lw=0.8, ls=ls, zorder=2)
            else:
                # Only one chip measured for this technique on this column. Draw a short
                # stub so the marker reads as a deliberate single point rather than as a
                # line that failed to render.
                ax.plot([xs[0] - 0.05, xs[0] + 0.05], [ys[0], ys[0]], color=lc, lw=0.8,
                        ls=ls, zorder=2)
            for xi, g in zip(xs, present):
                ax.scatter([xi], [rs[g]], s=12, color=GPU_COLOR[g], marker=marker,
                           zorder=4, edgecolors="white", linewidths=0.25)
        d = de.get((dataset, column))
        if d:
            rate, codec = d
            ax.plot([x - 0.44, x + 0.44], [rate, rate], color=DE_CODEC_COLOR.get(codec, C.WARM),
                    lw=1.6, solid_capstyle="butt", zorder=3)

    # Divide synthetic from real: the two groups answer different questions (low-cardinality
    # dictionaries versus dictionaries that fill) and the engine behaves differently across
    # the seam, so leaving it implicit in the ordering hid it.
    ax.axvline(split - 0.5, color="#b9bdc2", lw=0.7, zorder=1)
    for lo, hi, name in ((0, split, "synthetic"), (split, len(order), "real")):
        ax.text((lo + hi - 1) / 2.0, 1.02, name, fontsize=6.0, style="italic", color=C.INK,
                ha="center", va="bottom", zorder=6, transform=ax.get_xaxis_transform())

    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([SHORT.get(l, l) for _, _, l, _ in order], fontsize=5.8, rotation=47,
                       ha="right", rotation_mode="anchor")
    ax.set_xlim(-0.70, len(order) - 0.30)
    ax.set_yscale("log")
    ax.set_ylim(150, 2600)
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
    ax.yaxis.set_major_locator(FixedLocator([200, 500, 1000, 2000]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%d" % v))
    ax.yaxis.set_minor_locator(FixedLocator([]))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_ylabel("decode (GB/s, log)")

    from matplotlib.lines import Line2D
    tech_h = [Line2D([], [], color=lc, ls=ls, marker=m, markersize=3.4, lw=0.9,
                     markerfacecolor="#5b616b", markeredgecolor="white", label=t)
              for t, _, _, m, ls, lc in TECHS]
    gpu_h = [Line2D([], [], color=GPU_COLOR[g], marker="o", markersize=3.4, lw=0,
                    label=C.GPU_LABEL[g] + (" (GDDR6)" if g == "l40s" else ""))
             for g in ORDER]
    winners = []
    for dataset, column, _, _ in order:
        d = de.get((dataset, column))
        if d and d[1] not in winners:
            winners.append(d[1])
    de_h = [Line2D([], [], color=DE_CODEC_COLOR.get(w, C.WARM), lw=1.6, label="DE %s" % w)
            for w in winners]
    fig.legend(handles=tech_h + gpu_h + de_h, frameon=False, fontsize=6.0, ncol=5,
               loc="lower center", bbox_to_anchor=(0.0, -0.012, 1.0, 0.10), mode="expand",
               columnspacing=0.8, handlelength=1.6, handletextpad=0.45, borderaxespad=0.0)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    C.save(fig, "fig_crossarch")

    # Report what the figure asserts, so the prose quotes derived numbers rather than
    # eyeballed ones. Now covers all three techniques.
    for tlabel, bits, codec, _, _, _ in TECHS:
        clean = tested = 0
        for dataset, column, label, _ in COLS:
            d = de.get((dataset, column))
            rs = rates(dataset, column, bits, codec)
            if not d or not rs:
                continue
            tested += 1
            rate, dcodec = d
            below = [C.GPU_LABEL[g] for g, t in rs.items() if t <= rate]
            if below:
                print("%-10s %-22s engine=%4.0f (%-11s)  below: %s"
                      % (tlabel, label, rate, dcodec, ",".join(below)))
            else:
                clean += 1
        print("%-10s: %d of %d columns where all measured GPUs clear the engine"
              % (tlabel, clean, tested))


if __name__ == "__main__":
    main()
