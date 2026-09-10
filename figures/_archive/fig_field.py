# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. field: OnPair-GPU vs the hardware DE vs software nvCOMP-Zstd on the B200.

Per-column decode throughput (log y). OnPair tops both the hardware and the
software path on every column. The launch-bound dbtext/s_comment columns are set
apart (shaded), since no decoder is throughput-limited there.
Source: results/b200/onpair_summary_*.json + results/b200/onpair_nvcomp_hw.json.
"""
import numpy as np
import common as C

# (dataset, column, short label) -- throughput-bound first, then launch-bound.
COLS = [
    ("clickbench", "URL", "ClickB.\nURL"),
    ("tpch-sf10", "l_comment", "TPC-H\nl_comm"),
    ("tpch-sf10", "ps_comment", "TPC-H\nps_comm"),
    ("synthetic", "url", "synth\nurl"),
    ("lship", "l_shipinstruct", "l_ship\ninstruct"),
    ("fineweb", "text", "FineWeb"),
    ("wikipedia", "text", "Wiki"),
    ("book-reviews", "text", "book-rev"),
    # launch-bound:
    ("tpch-sf10", "s_comment", "TPC-H\ns_comm"),
    ("dbtext", "email", "dbtext\nemail"),
    ("dbtext", "yago", "dbtext\nyago"),
]


def main():
    de = C.de_map()
    fig, ax = C.new_fig(6.8, 1.95)  # full text-width figure
    x = np.arange(len(COLS))
    w = 0.27
    op, hw, sw = [], [], []
    for d, c, _ in COLS:
        cl = C.cell("b200", d, c)
        # The DE output keys by the cell's real dataset_id; lship's file label ("lship")
        # differs from its dataset_id ("tpch-sf10"), so resolve via the cell.
        ds_id = (cl or {}).get("dataset_id", d)
        op.append(C.best_shipped(cl) or np.nan)
        hw.append(de.get((ds_id, c)) or np.nan)
        sw.append(C.software_best(cl) or np.nan)
    ax.bar(x - w, op, w, label="FastPair", color=C.TECH["onpair"])
    ax.bar(x, hw, w, label="hardware DE", color=C.TECH["de"])
    ax.bar(x + w, sw, w, label="software nvCOMP-Zstd", color=C.TECH["software"])
    ax.set_yscale("log")
    ax.set_ylabel("decode throughput (GiB/s)")
    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, _, lbl in COLS])
    # shade the launch-bound region
    first_lb = next(i for i, (d, c, _) in enumerate(COLS) if (d, c) in C.LAUNCH_BOUND)
    ax.axvspan(first_lb - 0.5, len(COLS) - 0.5, color="0.92", zorder=0)
    ax.text((first_lb + len(COLS) - 1) / 2, ax.get_ylim()[1] * 0.6,
            "launch-bound", ha="center", va="top", fontsize=7, color="0.4")
    ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    C.save(fig, "fig_field")


if __name__ == "__main__":
    main()
