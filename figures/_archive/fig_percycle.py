# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Fig. percycle: what decode rate scales with across GPU generations.

THE ARGUMENT. If decode were limited by how many bytes a device can deliver, its rate would
track memory bandwidth. It does not. Normalising instead by the SM-cycle budget a device has --
streaming multiprocessors times boost clock -- makes the rate nearly constant across three
generations, which says the scarce resource is SM-side work per byte and not bytes.

Left panel, per device: decoded bytes per SM-cycle that FastPair achieves, against the HBM bytes
per SM-cycle the memory system could supply. The achieved bars sit at a near-constant height on
the HBM parts while the available bars vary by more than 2.5x, and the gap between them is the
headroom the decoder never uses.

Right panel: the same claim as a scaling test. From the A100 to the B300, decode rises about 2.3x
while peak memory bandwidth rises 5.1x and the SM-cycle budget rises 2.0x. Decode follows the
SM-cycle line, not the bandwidth line.

WHY THIS AND NOT A ROOFLINE. An earlier version argued the same point from a sector-rate roofline
built on profiler captures. That model reproduced the ordering within an architecture but missed
the absolute level by an undetermined per-architecture constant (1.22, 1.22, 1.82 on
a100/h100/b300), which is not a clock ratio and which we could not decompose. This construction
needs no profiler, no fitted constant and no derived peak: committed decode rates, published SM
counts and clocks, vendor-rated bandwidth.

THE L40S IS EXPLAINED, NOT EXCLUDED. It supplies 2.4 bytes per SM-cycle, BELOW the 3.4 to 4.0 the
decoder consumes on every HBM part, so it is the one device where the byte term is the binding one
and it lands at 1.22. That is the quantitative version of the boundary the length relation and the
SM-clock sweep both find, and it is the reason it appears here rather than being dropped as an
outlier.

RATE IS THE MEDIAN over the ten real columns at OnPair-12, per device, so no single column's
character sets the comparison. The generated five are excluded as everywhere else.

Source: results/suite-<id>/<chip>/sweep_summary_*_boost.json for rate; SMs and boost clock from
each leg's own device_properties.json; bandwidth is the vendor rating in tab:arch.
"""
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import suite as S  # noqa: E402

# Vendor-rated peak memory bandwidth, TB/s, matching tab:arch. SM count and boost clock are read
# from the leg's device_properties.json rather than hard-coded, so a new chip needs no edit here.
PEAK_TBS = {"a100": 1.56, "l40s": 0.86, "h100": 3.35, "b300": 8.00}
LABEL = {"a100": "A100", "l40s": "L40S", "h100": "H100", "b300": "B300", "rtxpro": "RTX PRO"}
# Plot order is generational, not the CHIPS_CORE order, because the right panel reads as a
# progression. A chip with no committed leg is skipped and reported.
ORDER = C.DEVICE_ORDER   # paper-wide device order; see common.DEVICE_ORDER
REAL = {(ds, col) for _, ds, col in S.REAL}


def device(root, chip):
    """(SMs, boost MHz) from the leg's own device properties, or None if the leg is absent."""
    p = Path(root) / chip / "device_properties.json"
    if not p.exists():
        return None
    d = json.load(open(p))
    if isinstance(d, list):
        d = d[0]
    sms, khz = d.get("multiprocessors"), d.get("clock_khz")
    return (sms, khz / 1000.0) if sms and khz else None


def median_rate(root, chip, bits=12):
    cells = S.cells(root, chip, "boost", "onpair")
    r = [S.rate_gb_s(c) for (ds, col, b), c in cells.items()
         if b == bits and (ds, col) in REAL and S.rate_gb_s(c)]
    return st.median(r) if r else None


def percol(root, ds, col, bits=12):
    """Mean token length for one column, used only to order the x axis."""
    c = S.cells(root, "b300", "boost", "onpair").get((ds, col, bits))
    return S.mean_len(c) if c else None


def short(name):
    """tab:datasets' label, trimmed to fit a rotated tick."""
    return (name.replace("\\texttt{", "").replace("}", "")
                .replace("Loghub ", "").replace("ClickBench ", "CB "))


def main():
    root = S.latest_root(S.PAPER_SUITE)
    rows = []
    for chip in ORDER:
        dev, rate = device(root, chip), median_rate(root, chip)
        if not dev or not rate or chip not in PEAK_TBS:
            sys.stderr.write("fig_percycle: skipping %s (no leg or no bandwidth rating)\n" % chip)
            continue
        sms, mhz = dev
        smcyc = sms * mhz * 1e6                       # SM-cycles per second
        rows.append({"chip": chip, "sms": sms, "mhz": mhz, "rate": rate,
                     "achieved": rate * 1e9 / smcyc,  # decoded bytes per SM-cycle
                     "available": PEAK_TBS[chip] * 1e12 / smcyc,
                     "smcyc": smcyc, "tbs": PEAK_TBS[chip]})
    if len(rows) < 2:
        sys.exit("fig_percycle: need at least two devices, have %d" % len(rows))

    import numpy as np
    plt = C.apply_theme()
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(7.0, 2.3),
                                   gridspec_kw={"width_ratios": [1.55, 1.0]})

    # LEFT, and this is the positive claim: per column, decoded bytes per SM-cycle, one series per
    # device. If the decoder simply failed to saturate memory for incidental reasons, this quantity
    # would drift between architectures, since Ampere, Hopper and Blackwell differ in L1 geometry
    # and load/store width. It does not drift: the three HBM series lie on each other. What moves
    # it is the COLUMN, left to right by mean token length. So the work a decoded byte costs is a
    # property of the data and the design, and each device pays it at its own cycle rate.
    cols = [(n, ds, c) for n, ds, c in S.REAL]
    order = sorted(cols, key=lambda t: percol(root, t[1], t[2]) or 0)
    xs = np.arange(len(order))
    for chip, colour, marker in (("a100", "#d81b60", "o"), ("h100", "#f57c00", "s"),
                                 ("b300", "#00897b", "D"), ("l40s", "#7e57c2", "^")):
        r = next((q for q in rows if q["chip"] == chip), None)
        if not r:
            continue
        ys = []
        for _, ds, c in order:
            cell = S.cells(root, chip, "boost", "onpair").get((ds, c, 12))
            rate = S.rate_gb_s(cell) if cell else None
            ys.append(rate * 1e9 / r["smcyc"] if rate else np.nan)
        axl.plot(xs, ys, color=colour, marker=marker, markersize=4.0, linewidth=1.0,
                 label=LABEL.get(chip, chip))
    axl.set_xticks(xs)
    axl.set_xticklabels([short(n) for n, _, _ in order], rotation=38, ha="right", fontsize=5.6)
    axl.tick_params(axis="x", length=0, pad=1)
    axl.set_ylabel("decoded bytes per SM-cycle")
    axl.set_ylim(0, None)

    # RIGHT: what each device could supply per SM-cycle, against what the decoder consumes. This is
    # where the L40S stops being an outlier and becomes an explanation: its supply, 2.4, is BELOW
    # the 2.8 to 4.8 the decoder reaches on every HBM part, so it is the one device where the byte
    # term binds. On the others the supply bar towers over the consumption bar.
    xb = np.arange(len(rows))
    w = 0.38
    axr.bar(xb - w / 2, [r["available"] for r in rows], w, color="#c6dbef",
            edgecolor=C.INK, linewidth=0.6, label="device can supply")
    axr.bar(xb + w / 2, [r["achieved"] for r in rows], w, color="#08519c",
            edgecolor="none", label="decoder consumes (median)")
    axr.set_xticks(xb)
    axr.set_xticklabels([LABEL.get(r["chip"], r["chip"]) for r in rows], fontsize=6.4)
    axr.tick_params(axis="x", length=0, pad=1)
    axr.set_ylabel("bytes per SM-cycle")

    fig.tight_layout(pad=0.3, rect=(0, 0.10, 1, 1))
    h1, l1 = axl.get_legend_handles_labels()
    h2, l2 = axr.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, fontsize=6.4, ncol=6, loc="lower center",
               bbox_to_anchor=(0.5, -0.02), frameon=False, columnspacing=1.1,
               handlelength=1.1, handletextpad=0.35)
    C.save(fig, "fig_percycle")

    hbm = [r for r in rows if r["chip"] != "l40s"]
    a = [r["achieved"] for r in hbm]
    sys.stderr.write("achieved B/SM-cycle, HBM: %.2f-%.2f (spread %.0f%%)\n"
                     % (min(a), max(a), 100 * (max(a) / min(a) - 1)))
    for r in rows:
        sys.stderr.write("  %-6s %3d SM x %.0f MHz  rate %.0f GB/s  achieved %.2f  available %.2f"
                         "  headroom %.1fx\n" % (r["chip"], r["sms"], r["mhz"], r["rate"],
                                                 r["achieved"], r["available"],
                                                 r["available"] / r["achieved"]))
    hbm = [r for r in rows if r["chip"] != "l40s"]
    if len(hbm) >= 2:
        b, l = hbm[0], hbm[-1]
        sys.stderr.write("%s -> %s: decode x%.2f, SM-cycles x%.2f, bandwidth x%.2f\n"
                         % (b["chip"], l["chip"], l["rate"] / b["rate"],
                            l["smcyc"] / b["smcyc"], l["tbs"] / b["tbs"]))
