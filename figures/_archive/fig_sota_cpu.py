# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. sota-cpu: the CPU decode field as throughput vs compression ratio.

Mirrors fig:payoff one level down the stack. Each (column, configuration) is its per-CPU-
generation points (the ten AMD/Intel/Arm gens) over a faint range bar, at the column's
compression ratio; color = configuration in technique shades (OnPair fixed-stride dict-12/-16
blues, the variable-stride greens, FSST, Zstd levels, LZ4, zlib Deflate). Intel's
IAA hardware engine (one engine, Sapphire) is a tick -- the CPU mirror of the GPU DE. Log
single-core throughput (matching fig:payoff): the fixed-stride decode leads the field on every
column. No per-gen
shape legend (the generations stack the same way in every config).
Source: results/cpu-sota/*.json + results/<gpu>/onpair_summary_*.json (ratio) + results/iaa/.
"""
import json
import re

import numpy as np

import common as C

COLMAP = {  # cpu column -> (GPU dataset-id, GPU column, panel)
    "l_comment": ("tpch-sf10", "l_comment", "S"),
    "ps_comment": ("tpch-sf10", "ps_comment", "S"),
    "l_shipinstruct": ("lship", "l_shipinstruct", "S"),
    "synthetic_url": ("synthetic", "url", "S"),
    "clickbench_url": ("clickbench", "URL", "R"),
    "fineweb": ("fineweb", "text", "R"),
    "wikipedia": ("wikipedia", "text", "R"),
    "book_reviews": ("book-reviews", "text", "R"),
    "amazon_movies": ("amazon-movies", "text", "R"),
    "amazon_electronics": ("amazon-electronics", "text", "R"),
}
GENS = ["amd-rome", "amd-milan", "amd-genoa", "amd-turin", "intel-icelake",
        "intel-sapphire", "intel-granite", "arm-graviton2", "arm-graviton3", "arm-graviton4"]
CFG = {  # legend reads in this order (row-major via flip); IAA sits at the end of row 1,
         # pushing the Zstd/Deflate software field onto row 2.
    "FastPair-12": "#6baed6", "FastPair-16": "#08519c",
    "OnPair-12": "#a1d99b", "OnPair-16": "#31a354",
    "FSST": "#9e9ac8",
    "IAA": C.WARM,
    "Zstd (-10)": "#cccccc", "Zstd (1)": "#969696", "Zstd (3)": "#525252",
    "LZ4": "#a63603", "Deflate (9)": "#fdae61", "Deflate (1)": "#f16913",
}
RENAME = {"Deflate-hi": "Deflate (9)", "Deflate-fast": "Deflate (1)"}


def onpair_ratio(did, col, bits):
    """OnPair dict-`bits` ratio (device-independent; B300 canonical, same as fig:payoff)."""
    c = C.cell("b300", did, col, bits)
    if c and c.get("mem_ratio"):
        return c["mem_ratio"]
    for g in C.GPUS:
        c = C.cell(g, did, col, bits)
        if c and c.get("mem_ratio"):
            return c["mem_ratio"]
    return None


def load_gen(stem):
    f = C.RESULTS / "cpu-sota" / (stem + ".json")
    return json.load(open(f)) if f.exists() else None


def iaa_one_engine():
    out = {}
    p = C.RESULTS / "iaa" / "iaa_aggregate_sapphire.txt"
    if p.exists():
        for ln in p.read_text(errors="ignore").splitlines():
            m = re.search(r"/([a-z_]+)\.bin threads=1\s+ratio ([\d.]+)x\s+IAA-decode ([\d.]+) GB/s", ln)
            if m:
                out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def _edge(color, f=0.7):
    """A faint outline keyed to the marker's own color (a darker shade), so overlapping
    dots stay distinct without a stark white halo."""
    import matplotlib.colors as mc
    r, g, b = mc.to_rgb(color)
    return (r * f, g * f, b * f)


def range_marks(ax, x, ts, color):
    """Per-config box over the ten CPU-generation decode rates, at the column's ratio x.
    Width scales with x so boxes look uniform on the log x-axis."""
    if not x or not ts:
        return
    if len(ts) < 3:
        ax.scatter([x] * len(ts), ts, s=12, color=color, zorder=4,
                   edgecolors=_edge(color), linewidths=0.3, alpha=0.9)
        return
    ax.boxplot([ts], positions=[x], widths=[x * 0.06], patch_artist=True,
               whis=(0, 100), showfliers=False, manage_ticks=False, zorder=3,
               medianprops=dict(lw=0),   # whiskers span full min..max (no hidden fliers); median line off
               whiskerprops=dict(color=color, lw=0.6), capprops=dict(color=color, lw=0.6),
               boxprops=dict(facecolor=color, edgecolor=_edge(color), alpha=0.6, lw=0.6))


def panel(ax, origin, iaa):
    cols = {cpu: m for cpu, m in COLMAP.items() if m[2] == origin}
    gens = [d for d in (load_gen(s) for s in GENS) if d]
    for cpucol, (did, gcol, _) in cols.items():
        for bits in (12, 16):
            x = onpair_ratio(did, gcol, bits)
            fat = [r["fat_gibs"] * C.GIB_TO_GB for d in gens for r in d.get("results", [])
                   if r["threads"] == 1 and r["column"] == cpucol and r["bits"] == bits and r.get("fat_gibs")]
            ent = [r["entries_gibs"] * C.GIB_TO_GB for d in gens for r in d.get("results", [])
                   if r["threads"] == 1 and r["column"] == cpucol and r["bits"] == bits and r.get("entries_gibs")]
            range_marks(ax, x, fat, CFG["FastPair-%d" % bits])
            range_marks(ax, x, ent, CFG["OnPair-%d" % bits])
        comp = {}
        for d in gens:
            for c in d.get("competitors", []):
                code = RENAME.get(c["codec"], c["codec"])
                if c["column"] == cpucol and code in CFG and c.get("ratio") and c.get("decode_gbs"):
                    comp.setdefault(code, {"r": [], "t": []})
                    comp[code]["r"].append(c["ratio"]); comp[code]["t"].append(c["decode_gbs"])
        for code, dd in comp.items():
            range_marks(ax, float(np.median(dd["r"])), dd["t"], CFG[code])
        if cpucol in iaa:
            r, g = iaa[cpucol]
            ax.scatter([r], [g], s=14, color=CFG["IAA"], zorder=5, edgecolors=_edge(CFG["IAA"]), linewidths=0.3)
    from matplotlib.ticker import FixedLocator, ScalarFormatter, NullFormatter
    ax.set_xscale("log")
    xticks = [2, 3, 5, 7, 10, 15] if origin == "S" else [1.5, 2, 3, 5, 7]
    ax.xaxis.set_major_locator(FixedLocator(xticks))
    ax.xaxis.set_major_formatter(ScalarFormatter()); ax.xaxis.set_minor_locator(FixedLocator([]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("compression ratio (log)")
    ax.set_title("Real-world columns" if origin == "R" else "Synthetic columns", fontsize=8)


def main():
    iaa = iaa_one_engine()
    plt = C.apply_theme()
    fig, (axR, axS) = plt.subplots(1, 2, figsize=(7.2, 2.0), sharey=True)
    panel(axR, "R", iaa)
    panel(axS, "S", iaa)
    axR.set_yscale("log")                          # LOG single-core throughput (matches fig:payoff)
    axR.set_ylim(0.1, 30)
    axR.set_ylabel("decode (GB/s, log)")
    from matplotlib.lines import Line2D
    import itertools

    def flip(items, ncol):
        return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))

    leg = [Line2D([], [], color=CFG[k], lw=5, label=k) for k in CFG]
    # Spread edge-to-edge like fig_sota: 4-tuple bbox + mode="expand" stretches the columns
    # across the full width; handletextpad matches fig_sota's icon-label spacing.
    fig.legend(handles=flip(leg, 6), frameon=False, fontsize=6.2, ncol=6, loc="lower center",
               bbox_to_anchor=(0.0, -0.04, 1.0, 0.12), mode="expand",
               columnspacing=1.0, handlelength=1.0, handletextpad=0.7, borderaxespad=0.0)
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    C.save(fig, "fig_sota_cpu")


if __name__ == "__main__":
    main()
