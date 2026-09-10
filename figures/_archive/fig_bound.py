# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. bound: which cache ceiling decode runs into, and whether a sector-rate model predicts it.

TWO PANELS, TWO DIFFERENT STRENGTHS OF CLAIM, deliberately side by side.

LEFT is a direct counter reading and carries the paper's claim. Per profiled cell it plots the
L1 pipe's utilisation against DRAM's, both as a percentage of that unit's own peak. No model, no
fit, no scale factor: if the marks sit high on the L1 axis and low on the DRAM axis, the access
rate is the ceiling decode reaches and byte bandwidth is not. On the three HBM devices they do,
and the binding pipe is L1 on every one of 42 cells. On the GDDR6 L40S they scatter and the
binding pipe splits across L1, L2 and DRAM, which is the boundary the paper draws elsewhere by
sweeping the SM clock and by the length relation.

RIGHT is a MODEL and is weaker, which the caption has to say. Predicting decode rate as
decoded_bytes * peak_sector_rate / binding_sectors reproduces the ordering within an
architecture very tightly (log-log r = 0.98 on the A100, 0.99 on the H100, 1.00 on the B300) but
lands off the diagonal by a constant per architecture, 1.22, 1.22 and 1.82. THAT CONSTANT IS NOT
DERIVED AND IS NOT A CLOCK RATIO -- the boost:locked ratio on this hardware is about 1.06, so
1.82 cannot be one. The captures are clock-locked and serialised under the profiler while the
measurement is free-running at boost; the constant absorbs that difference and we do not
decompose it. Drawing it un-normalised, offset and all, is the honest rendering: normalising per
arch would hide exactly the thing we cannot explain.

So: the left panel is evidence, the right panel is a model that predicts variation but not level.
Do not promote the right panel's fit into a claim about absolute throughput.

CORPUS CAVEAT. This leg profiles seven columns (the pre-2026-08 corpus: ClickBench URL, FineWeb,
Wikipedia, and four TPC-H at sf10), not the fifteen of tab_datasets. It is a separate capture from
the campaign the rest of the evaluation uses, so it is scoped as a mechanism study and no headline
rate comes from it.

Source: figures/out/fig_roofline_v2.csv, written by fig_roofline_v2.py from results/*-ncu-v2.
Regenerate that first if the captures change.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

CSV = Path(__file__).resolve().parent / "out" / "fig_roofline_v2.csv"
# Fixed order and colour per device, matching fig_perf_gen so a hue means one chip paper-wide.
ARCH = [("a100", "#d81b60", "A100"), ("h100", "#f57c00", "H100"),
        ("b300", "#00897b", "B300"), ("l40s", "#7e57c2", "L40S")]
MARK = {"l1": "o", "l2": "s", "dram": "^"}


def load():
    if not CSV.exists():
        sys.exit("missing %s -- run fig_roofline_v2.py first" % CSV)
    rows = [r for r in csv.DictReader(open(CSV)) if r.get("sol_l1")]
    if not rows:
        sys.exit("no usable rows in %s" % CSV)
    return rows


def main():
    rows = load()
    plt = C.apply_theme()
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(7.0, 2.5))

    for arch, colour, label in ARCH:
        sel = [r for r in rows if r["arch"] == arch]
        if not sel:
            sys.stderr.write("fig_bound: no rows for %s\n" % arch)
            continue
        for r in sel:
            axl.scatter(float(r["sol_dram"]), float(r["sol_l1"]),
                        s=22, color=colour, marker=MARK.get(r["binding"], "o"),
                        edgecolor="white", linewidth=0.4, zorder=2)
        axr.scatter([float(r["pred_GBps"]) for r in sel],
                    [float(r["measured_GBps"]) for r in sel],
                    s=22, color=colour, edgecolor="white", linewidth=0.4,
                    zorder=2, label=label)

    # LEFT: the two ceilings. A diagonal would be meaningless here -- the axes are different
    # units of "how full" -- so the reference is the 100% edge, not a line of equality.
    axl.set_xlabel("DRAM read, % of its byte ceiling")
    axl.set_ylabel("L1 pipe, % of its access ceiling")
    axl.set_xlim(0, 100)
    axl.set_ylim(0, 100)
    axl.axhline(100, color=C.INK, linewidth=0.6, linestyle=":")
    axl.set_aspect("equal", adjustable="box")

    # RIGHT: measured against modelled, log-log, with y=x drawn. Points above the line are the
    # per-arch constant the model does not derive.
    allv = [float(r[k]) for r in rows for k in ("pred_GBps", "measured_GBps")]
    lo, hi = min(allv) * 0.85, max(allv) * 1.18
    axr.plot([lo, hi], [lo, hi], color=C.INK, linewidth=0.7, linestyle="--", zorder=1)
    axr.set_xscale("log")
    axr.set_yscale("log")
    axr.set_xlim(lo, hi)
    axr.set_ylim(lo, hi)
    axr.set_xlabel("modelled decode rate (GB/s)")
    axr.set_ylabel("measured decode rate (GB/s)")
    axr.set_aspect("equal", adjustable="box")

    # Log ticks collide at this width, so label only the decade-ish anchors.
    from matplotlib.ticker import FixedLocator, FuncFormatter
    ticks = [300, 500, 1000, 2000]
    for setter in (axr.set_xticks, axr.set_yticks):
        setter(ticks)
    axr.xaxis.set_minor_locator(FixedLocator([]))
    axr.yaxis.set_minor_locator(FixedLocator([]))
    fmt = FuncFormatter(lambda v, _: "%d" % v)
    axr.xaxis.set_major_formatter(fmt)
    axr.yaxis.set_major_formatter(fmt)

    fig.tight_layout(pad=0.3, rect=(0, 0.09, 1, 1))
    fig.legend(fontsize=6.6, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.01),
               frameon=False, columnspacing=1.4, handlelength=1.0, handletextpad=0.35)
    C.save(fig, "fig_bound")

    # Report what the prose is allowed to say.
    hbm = [r for r in rows if r["arch"] != "l40s"]
    l1 = [float(r["sol_l1"]) for r in hbm]
    dr = [float(r["sol_dram"]) for r in hbm]
    sys.stderr.write("HBM cells n=%d: L1 SOL %.0f-%.0f%%, DRAM SOL %.0f-%.0f%%, binding=L1 on %d\n"
                     % (len(hbm), min(l1), max(l1), min(dr), max(dr),
                        sum(1 for r in hbm if r["binding"] == "l1")))
    l4 = [r for r in rows if r["arch"] == "l40s"]
    sys.stderr.write("L40S cells n=%d: L1 SOL %.0f-%.0f%%, binding %s\n"
                     % (len(l4), min(float(r["sol_l1"]) for r in l4),
                        max(float(r["sol_l1"]) for r in l4),
                        {b: sum(1 for r in l4 if r["binding"] == b) for b in ("l1", "l2", "dram")}))


if __name__ == "__main__":
    main()
