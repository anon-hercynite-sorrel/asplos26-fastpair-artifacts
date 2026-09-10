# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. payoff (frontier variant): decode throughput vs compression ratio on TPC-H
l_comment (B200), each codec as its full speed-ratio frontier rather than one point.

Fixes the ratio-axis muddiness of the scatter version: every codec has a speed/ratio
knob (the DE's three engines, Zstd's levels, OnPair's two presets), so we draw each
codec's whole frontier. FastPair sits far above all of them --- at the best DE's
compression ratio it decodes several times faster --- which is the honest "pop".
Source: results/b200/onpair_summary_tpch-sf10.json + onpair_nvcomp_hw.json.
"""
import json
import numpy as np
import common as C

COL = "l_comment"


def main():
    c = next(x for x in json.load(open(C.RESULTS / "b200" / "onpair_summary_tpch-sf10.json"))
             if x["column"] == COL)  # b12
    c16 = next(x for x in json.load(open(C.RESULTS / "b200" / "onpair_summary_tpch-sf10.json"))
               if x["column"] == COL and x["bits"] == 16)
    de = next(e for e in json.load(open(C.RESULTS / "b200" / "onpair_nvcomp_hw.json"))
              if e["dataset_id"] == "tpch-sf10" and e["column"] == COL)
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(3.6, 2.6))

    def frontier(pts, color, marker, label):
        pts = sorted(pts)  # by ratio
        xs, ys = zip(*pts)
        ax.plot(xs, ys, "-", color=color, lw=1.1, alpha=0.9, zorder=2)
        ax.scatter(xs, ys, s=28, color=color, marker=marker, zorder=3, label=label)

    # OnPair: the two shipped presets (b12, b16)
    op = [(c["mem_ratio"], C.best_shipped(c)), (c16["mem_ratio"], C.best_shipped(c16))]
    frontier(op, C.TECH["onpair"], "o", "FastPair")
    # hardware DE: three engines
    df = [(d["ratio"], d["decode_gib_s"]) for d in de["codecs"].values()]
    frontier(df, C.TECH["de"], "s", "hardware DE")
    # software Zstd: the measured levels
    zf = [(e["compression_ratio"], e["decode_gib_s"]) for e in c["gpu"].get("nvcomp_zstd", [])
          if isinstance(e, dict) and e.get("decode_gib_s")]
    frontier(zf, C.TECH["software"], "D", "software Zstd")
    # GSST: single reported point (A100)
    ax.scatter([2.74], [C.GSST_GIBS], s=46, marker="*", color=C.GSST_RED, zorder=4, label="GSST (A100)")

    ax.set_xlabel("compression ratio"); ax.set_ylabel("decode throughput (GiB/s)")
    ax.set_ylim(0, 1250); ax.set_xlim(1.5, 5.0)
    ax.set_title("TPC-H l_comment, B200", fontsize=8)
    ax.legend(frameon=False, fontsize=6.5, loc="center right", labelspacing=0.3)
    fig.tight_layout()
    C.save(fig, "fig_payoff_frontier")


if __name__ == "__main__":
    main()
