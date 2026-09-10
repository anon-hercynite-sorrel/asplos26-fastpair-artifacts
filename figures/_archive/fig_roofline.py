# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. roofline (paper): request-rate roofline prediction vs measured decode rate.

One point per profiled cell (7 columns x 2 presets x 4 arches, 56 cells). x = the
roofline prediction from the NCU capture, decoded_bytes * peak_sector_rate /
binding-pipe sectors (the fullest pipe's rate, i.e. capture throughput / SOL fraction),
scaled by one per-arch clock constant (median measured/predicted; captures are
clock-locked, measurements boost -- the B300's fitted 1.82 equals its independently
measured locked:boost throughput ratio). y = common.best_shipped (the paper's measured
rate). Points on y=x mean the binding pipe's request rate predicts the decode rate.
The three HBM chips hug the line (median |rel err| 1.7/3.8/8.0% on B300/H100/A100);
the L40S scatters (no pipe saturates, so no single pipe's rate is the predictor), and
its DRAM-topped low-cardinality cells are drawn as squares.

Model + extraction: fig_roofline_v2.py (the full diagnostic; this script only restyles
its rows for the paper). Source: results/*-ncu-v2 (shipped-kernel locked recapture).
The superseded v1 diagnostic (base-kernel captures) lives in git history and in
ROOFLINE-FINDINGS.md.
"""
import os
import statistics as st
import sys

import matplotlib.ticker as mticker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import fig_roofline_v2 as V2  # noqa: E402


def main():
    plt = C.apply_theme()
    rows = [r for r in V2.collect() if r["predicted"] and r["measured"]]
    fig, ax = plt.subplots(figsize=(3.4, 2.7))

    lo, hi = float("inf"), 0.0
    for arch in C.GPUS:
        sub = [r for r in rows if r["arch"] == arch]
        if not sub:
            continue
        scale = st.median(r["measured"] / r["predicted"] for r in sub)
        rel = [abs(r["predicted"] * scale - r["measured"]) / r["measured"] for r in sub]
        sys.stderr.write("%s scale=%.2f med|rel|=%.1f%% max|rel|=%.1f%% n=%d\n"
                         % (arch, scale, 100 * st.median(rel), 100 * max(rel), len(sub)))
        for marker, pick in (("o", lambda r: r["binding"] != "dram"),
                             ("s", lambda r: r["binding"] == "dram")):
            pts = [(r["predicted"] * scale, r["measured"]) for r in sub if pick(r)]
            if not pts:
                continue
            xs, ys = zip(*pts)
            ax.scatter(xs, ys, s=16, marker=marker, color=C.GPU_RAMP[arch],
                       edgecolors="white", linewidths=0.4, zorder=3,
                       label=("%s ($\\times$%.2f)" % (C.GPU_LABEL[arch], scale))
                       if marker == "o" else None)
            lo = min(lo, min(xs + ys))
            hi = max(hi, max(xs + ys))

    pad_lo, pad_hi = lo * 0.8, hi * 1.25
    ax.plot([pad_lo, pad_hi], [pad_lo, pad_hi], ls="--", lw=0.8, color="#888888",
            zorder=2, label="y = x")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(pad_lo, pad_hi)
    ax.set_ylim(pad_lo, pad_hi)
    _fmt = mticker.FuncFormatter(lambda v, _: f"{int(v)}")
    for _axis in (ax.xaxis, ax.yaxis):
        _axis.set_major_locator(mticker.FixedLocator([200, 500, 1000, 2000]))
        _axis.set_major_formatter(_fmt)
        _axis.set_minor_formatter(mticker.NullFormatter())
    ax.set_xlabel("predicted decode rate (GB/s)")
    ax.set_ylabel("measured decode rate (GB/s)")
    ax.grid(True, which="both", lw=0.4, color="#ececec")
    ax.legend(frameon=False, fontsize=6.5, loc="upper left", handletextpad=0.3,
              borderaxespad=0.2, labelspacing=0.3)
    fig.tight_layout()
    C.save(fig, "fig_roofline")


if __name__ == "__main__":
    main()
