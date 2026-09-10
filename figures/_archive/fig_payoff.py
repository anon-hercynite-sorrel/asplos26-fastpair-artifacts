# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. payoff: the paper's headline, merging the codec head-to-head (old fig:field)
and the cross-architecture breadth (old fig:breadth) into one figure.

Left  — throughput x compression-ratio on the B200: FastPair owns the high-throughput
        frontier against the hardware DE, software Zstd, and GSST (the codec win).
Right — FastPair decode throughput across the four GPUs: HBM-class on every
        architecture, rising with the memory generation (the portability).
Real columns filled, synthetic open. Source: results/{a100,gh200,h100,b200}/* + DE json.
"""
import json
import numpy as np
import common as C

# (file label, column, short label, origin) — drives the Pareto.
PCOLS = [
    ("tpch-sf10", "l_comment", "l_comment", "synth"),
    ("tpch-sf10", "ps_comment", "ps_comment", "synth"),
    ("lship", "l_shipinstruct", "l_ship", "synth"),
    ("synthetic", "url", "synth-url", "synth"),
    ("clickbench", "URL", "ClickB URL", "real"),
    ("fineweb", "text", "FineWeb", "real"),
    ("wikipedia", "text", "Wikipedia", "real"),
    ("book-reviews", "text", "book-rev", "real"),
]


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
    from matplotlib.ticker import FixedLocator, ScalarFormatter, NullFormatter
    from matplotlib.lines import Line2D
    fig, (axP, axB) = plt.subplots(1, 2, figsize=(7.0, 2.7),
                                   gridspec_kw={"width_ratios": [1.25, 1]})

    # ---- Left: B200 throughput x compression-ratio Pareto ----
    series = {"FastPair": (C.TECH["onpair"], "o"),
              "hardware DE": (C.TECH["de"], "s"),
              "software Zstd": (C.TECH["software"], "D")}
    data = {k: {"real": ([], []), "synth": ([], [])} for k in series}
    for fn, col, lab, origin in PCOLS:
        c = C.cell("b200", fn, col, 12)
        did = (c or {}).get("dataset_id", "tpch-sf10" if fn == "lship" else fn)
        ot, orr = C.best_shipped(c), (c or {}).get("mem_ratio")
        if ot and orr:
            data["FastPair"][origin][0].append(orr); data["FastPair"][origin][1].append(ot)
        d = de.get((did, col))
        if d and d.get("best_decode_gib_s"):
            data["hardware DE"][origin][0].append(d["best_ratio"]); data["hardware DE"][origin][1].append(d["best_decode_gib_s"])
        zt, zr = zstd(c)
        if zt and zr:
            data["software Zstd"][origin][0].append(zr); data["software Zstd"][origin][1].append(zt)
    for name, (color, marker) in series.items():
        for origin in ("real", "synth"):
            xs, ys = data[name][origin]
            axP.scatter(xs, ys, s=30, marker=marker, zorder=3,
                        facecolors=(color if origin == "real" else "none"),
                        edgecolors=color, linewidths=1.1)
    axP.scatter([2.74], [C.GSST_GIBS], s=46, marker="*", color=C.GSST_RED, zorder=4)
    axP.annotate("GSST", (2.74, C.GSST_GIBS), fontsize=6, color=C.GSST_RED,
                 xytext=(4, -1), textcoords="offset points", va="top")
    axP.set_xscale("log")
    axP.xaxis.set_major_locator(FixedLocator([1.5, 2, 3, 5, 10, 20]))
    axP.xaxis.set_major_formatter(ScalarFormatter()); axP.xaxis.set_minor_locator(FixedLocator([]))
    axP.xaxis.set_minor_formatter(NullFormatter())
    axP.set_xlabel("compression ratio (log)"); axP.set_ylabel("decode throughput (GiB/s)")
    axP.set_ylim(0, 1550); axP.set_title("B200: vs every alternative", fontsize=8)
    leg = [Line2D([], [], marker=m, color=clr, ls="", label=n) for n, (clr, m) in series.items()]
    leg += [Line2D([], [], marker="*", color=C.GSST_RED, ls="", label="GSST (A100)")]
    axP.legend(handles=leg, frameon=False, fontsize=6, loc="upper right", labelspacing=0.25)

    # ---- Right: FastPair across the four GPUs ----
    x = np.arange(len(C.GPUS))
    for ds, col, label in C.REPRESENTATIVE:
        ys = [C.best_shipped(C.cell(g, ds, col)) for g in C.GPUS]
        if any(v is None for v in ys):
            continue
        axB.plot(x, ys, "-o", ms=3, lw=1.0, color=C.PRIMARY, alpha=0.55)
    axB.set_xticks(x); axB.set_xticklabels([C.GPU_LABEL[g] for g in C.GPUS], fontsize=7)
    axB.set_ylim(0, 1550); axB.set_title("FastPair: every architecture", fontsize=8)
    axB.set_ylabel("decode throughput (GiB/s)", fontsize=7)
    axB.text(0.04, 1500, "one kernel family,\nselected per chip", fontsize=6, color=C.INK, va="top")

    fig.tight_layout()
    C.save(fig, "fig_payoff")


if __name__ == "__main__":
    main()
