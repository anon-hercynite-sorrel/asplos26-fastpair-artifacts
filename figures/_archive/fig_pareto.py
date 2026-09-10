# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. pareto: decode throughput vs compression ratio, on the B200.

Each technique placed in throughput x compression-ratio space, one marker per column.
FastPair occupies the high-throughput frontier on every column; the hardware DE buys
a better ratio on some columns (e.g. URL) but decodes far slower; software Zstd is
dominated. GSST (the prior GPU decoder, A100, l_comment) shown as an off-chip
reference. Real columns filled, synthetic open.
Source: results/b200/onpair_summary_*.json + results/b200/onpair_nvcomp_hw.json.
"""
import json
import numpy as np
import common as C

# (file label, column, short label, origin)
COLS = [
    ("lship", "l_shipinstruct", "l_ship", "synth"),
    ("synthetic", "url", "synth-url", "synth"),
    ("tpch-sf10", "l_comment", "l_comment", "synth"),
    ("tpch-sf10", "ps_comment", "ps_comment", "synth"),
    ("clickbench", "URL", "ClickB URL", "real"),
    ("fineweb", "text", "FineWeb", "real"),
    ("wikipedia", "text", "Wikipedia", "real"),
    ("book-reviews", "text", "book-rev", "real"),
]


def onpair(c):
    return C.best_shipped(c), (c or {}).get("mem_ratio")


def zstd(c):
    g = (c or {}).get("gpu") or {}
    best = None
    for e in (g.get("nvcomp_zstd") or []):
        if isinstance(e, dict) and e.get("decode_gib_s"):
            if best is None or e["decode_gib_s"] > best[0]:
                best = (e["decode_gib_s"], e.get("compression_ratio"))
    return best or (None, None)


def main():
    de = {(e["dataset_id"], e["column"]): e
          for e in json.load(open(C.RESULTS / "b200" / "onpair_nvcomp_hw.json"))}
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(3.4, 2.6))

    series = {"FastPair": (C.TECH["onpair"], "o"),
              "hardware DE": (C.TECH["de"], "s"),
              "software Zstd": (C.TECH["software"], "D")}
    data = {k: {"real": ([], []), "synth": ([], [])} for k in series}
    for fn, col, lab, origin in COLS:
        c = C.cell("b200", fn, col, 12)
        did = (c or {}).get("dataset_id", "tpch-sf10" if fn == "lship" else fn)
        ot, orr = onpair(c)
        if ot and orr:
            data["FastPair"][origin][0].append(orr); data["FastPair"][origin][1].append(ot)
        d = de.get((did, col))
        if d and d.get("best_decode_gib_s"):
            data["hardware DE"][origin][0].append(d["best_ratio"])
            data["hardware DE"][origin][1].append(d["best_decode_gib_s"])
        zt, zr = zstd(c)
        if zt and zr:
            data["software Zstd"][origin][0].append(zr); data["software Zstd"][origin][1].append(zt)

    for name, (color, marker) in series.items():
        for origin in ("real", "synth"):
            xs, ys = data[name][origin]
            ax.scatter(xs, ys, s=34, marker=marker, zorder=3,
                       facecolors=(color if origin == "real" else "none"),
                       edgecolors=color, linewidths=1.1)
    # GSST reference (A100, l_comment): 191 GB/s ~= 178 GiB/s, FSST ratio ~2.74
    ax.scatter([2.74], [C.GSST_GIBS], s=46, marker="*", color=C.GSST_RED, zorder=4)
    ax.annotate("GSST (A100)", (2.74, C.GSST_GIBS), fontsize=6, color=C.GSST_RED,
                xytext=(4, -2), textcoords="offset points", va="top")

    from matplotlib.ticker import FixedLocator, ScalarFormatter, NullFormatter
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator([1.5, 2, 3, 5, 10, 20]))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_locator(FixedLocator([]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("compression ratio (log)")
    ax.set_ylabel("decode throughput (GiB/s)")
    ax.set_ylim(0, 1550)
    # legend: technique by color/marker; fill = origin
    from matplotlib.lines import Line2D
    leg = [Line2D([], [], marker=m, color=clr, ls="", label=n) for n, (clr, m) in series.items()]
    leg += [Line2D([], [], marker="o", color=C.INK, ls="", markerfacecolor=C.INK, label="real"),
            Line2D([], [], marker="o", color=C.INK, ls="", markerfacecolor="none", label="synthetic")]
    ax.legend(handles=leg, frameon=False, fontsize=6, loc="upper right", ncol=1,
              handletextpad=0.2, labelspacing=0.25)
    fig.tight_layout()
    C.save(fig, "fig_pareto")


if __name__ == "__main__":
    main()
