# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Request-rate roofline, v2: same model as fig_roofline.py, re-run on the CLEAN NCU
recapture (results/{a100,l40s,h100,b300}-ncu-v2 in the MAIN worktree), which profiles the
SHIPPED onpair_shmem_4tpt[_split8read] kernel family (verified per-launch kernel names,
512-thread blocks, 33 KB static shared memory, locked clocks) instead of the base scalar
kernel the v1 captures accidentally profiled.

Model (unchanged from v1):

    predicted_GB/s = decoded_bytes * peak_sector_rate / binding_sectors
                   = (decoded_bytes / duration) / (binding-pipe SOL fraction)

(the two forms are identical when the peak rate is derived from the capture's own
sector-count/duration/SOL triple, as v1 did for the L1). Measured = common.best_shipped
(boost clocks, no profiler), so a *constant per-arch* measured/predicted ratio equal to
the boost:locked clock ratio is the model's success criterion; a per-cell-varying ratio
(v1: 2.9x-33x) is its failure mode.

Differences from v1, all forced by the v2 export or the recapture design:
  * v2 dirs live in the main worktree (override with NCU_V2_RESULTS).
  * a100 added (v2 ships 4 arches x 14 cells, logs included, so decoded_bytes is
    per-arch native, not borrowed).
  * `Duration` rows mix ms and us units in v2; converted per-row via the unit column.
  * a100/l40s ship no total `l1tex__t_sectors.sum`; reconstructed as the sum of the
    l1tex__t_sectors_pipe_*.sum breakdowns (validated against the shipped total on
    h100/b300, where both exist).
  * binding pipe is chosen per cell as the max-SOL pipe among L1/L2/DRAM (v2 shows L1/TEX
    is the near-saturated pipe on a100/h100/b300, not just b300; on l40s nothing
    saturates). The v1 paper map (b300:L1, h100:L2, l40s:L2) is also evaluated for
    apples-to-apples comparison, as are L1-everywhere / L2-everywhere.

Emits: table CSV to stdout + figures/out/fig_roofline_v2.csv, fit stats per binding
variant to stderr, scatter to figures/out/fig_roofline_v2.pdf.
"""
import csv
import glob
import os
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

# The clean recapture lives in the MAIN worktree; this branch's results/ has no -ncu-v2.
V2_RESULTS = Path(os.environ.get(
    "NCU_V2_RESULTS", str(Path(__file__).resolve().parent.parent / "results")))

CELL_MAP = {
    "clickbench_URL": ("clickbench", "URL"),
    "synthetic_url": ("synthetic", "url"),
    "fineweb_text": ("fineweb", "text"),
    "wikipedia_text": ("wikipedia", "text"),
    "tpch-sf10_l_comment": ("tpch-sf10", "l_comment"),
    "tpch-sf10_l_shipinstruct": ("lship", "l_shipinstruct"),
    "tpch-sf10_ps_comment": ("tpch-sf10", "ps_comment"),
}

ARCHES = ("a100", "l40s", "h100", "b300")

# v1 paper map (tab:bottleneck provenance = base kernel); kept only for comparison.
PAPER_BINDING = {"a100": "l2", "b300": "l1", "h100": "l2", "l40s": "l2"}

OCC_MIN = 30.0  # same filter as v1 (v2 shipped-kernel captures all sit at 38-57%).

_DUR_NS = {"ns": 1.0, "nsecond": 1.0, "us": 1e3, "usecond": 1e3,
           "ms": 1e6, "msecond": 1e6, "s": 1e9, "second": 1e9}


def _median_raw(raw_path, suffix, exclude_prefixes=True):
    """Median over the profiled launches of the raw column ending with `suffix`.
    Prefer the plain (unsectioned) column; fall back to the section-prefixed one
    (populated in the v2 export, unlike v1)."""
    with open(raw_path) as f:
        r = csv.reader(f)
        hdr = next(r)
        next(r)  # units row
        rows = list(r)
    cands = [i for i, h in enumerate(hdr) if h.endswith(suffix)]
    plain = [i for i in cands if "." not in hdr[i][:len(hdr[i]) - len(suffix)]]
    idx = (plain or cands)
    if not idx:
        return None
    i = idx[0]
    xs = []
    for row in rows:
        v = row[i].replace(",", "").strip()
        if v:
            try:
                xs.append(float(v))
            except ValueError:
                pass
    return st.median(xs) if xs else None


def _l1_pipe_sum(raw_path):
    with open(raw_path) as f:
        hdr = next(csv.reader(f))
    pipe_re = re.compile(r"^l1tex__t_sectors_pipe_[a-z0-9_]+\.sum$")
    s = 0.0
    found = False
    for h in hdr:
        if pipe_re.match(h) and "lookup" not in h:
            v = _median_raw(raw_path, h)
            if v:
                s += v
                found = True
    return s if found else None


def _l1_sectors(raw_path):
    """Total L1/TEX sectors: the shipped total where the export has one (h100/b300),
    else the sum of the per-pipe breakdowns (a100/l40s). Where both exist, warn if they
    disagree by more than 3% (validates the pipe-sum reconstruction)."""
    tot = _median_raw(raw_path, "l1tex__t_sectors.sum")
    ps = _l1_pipe_sum(raw_path)
    if tot and ps and abs(ps - tot) / tot > 0.03:
        sys.stderr.write("WARN %s: l1 pipe-sum %.3e vs total %.3e (%.1f%% off)\n"
                         % (os.path.basename(raw_path), ps, tot, 100 * abs(ps - tot) / tot))
    return tot or ps


def _details(details_path):
    """{(Section, Metric): median value} with Duration normalized to ns (v2 mixes ms/us).
    Also returns the kernel name."""
    acc, kern = {}, None
    with open(details_path) as f:
        for row in csv.reader(f):
            if len(row) < 15:
                continue
            if kern is None and row[4] and row[4] != "Kernel Name":
                kern = row[4]
            key = (row[11], row[12])
            try:
                v = float(row[14].replace(",", ""))
            except ValueError:
                continue
            if key == ("GPU Speed Of Light Throughput", "Duration"):
                v *= _DUR_NS.get(row[13].strip().lower(), 1e6)  # -> ns
            acc.setdefault(key, []).append(v)
    return {k: st.median(v) for k, v in acc.items() if v}, kern


def _decoded_bytes(arch, stem, bits):
    """(decoded bytes per profiled LAUNCH, chunk count). The bench decodes the sample in
    `chunks` kernel launches (1 for every v2 cell except l_comment b12, which uses a 50 MB
    sample in 5 chunks), and every NCU metric here is per-launch, so the model's
    decoded_bytes must be per-launch too."""
    p = V2_RESULTS / f"{arch}-ncu-v2" / f"ncu_costsurface_{stem}_b{bits}.log"
    if p.exists():
        txt = p.read_text(errors="ignore")
        m = re.search(r'"decoded_bytes":\s*(\d+)', txt)
        c = re.search(r'"chunks":\s*(\d+)', txt)
        n = int(c.group(1)) if c else 1
        if m:
            return int(m.group(1)) / n, n
    return None, None


STALLS = ("mio_throttle", "short_scoreboard", "long_scoreboard", "lg_throttle",
          "wait", "not_selected", "barrier", "drain", "no_instruction", "math_pipe_throttle",
          "tex_throttle", "branch_resolving", "dispatch_stall", "imc_miss", "membar",
          "misc", "sleeping")


def collect():
    rows = []
    for arch in ARCHES:
        for dp in sorted(glob.glob(str(V2_RESULTS / f"{arch}-ncu-v2" / "ncu_costsurface_*_details.csv"))):
            stem = os.path.basename(dp)[len("ncu_costsurface_"):-len("_details.csv")]
            col, bits_s = stem.rsplit("_b", 1)
            bits = int(bits_s)
            if col not in CELL_MAP:
                continue
            rawp = dp.replace("_details.csv", "_raw.csv")
            if not os.path.exists(rawp):
                continue
            det, kern = _details(dp)
            occ = det.get(("Occupancy", "Achieved Occupancy"))
            if occ is None or occ != occ or occ <= OCC_MIN:
                continue
            db, chunks = _decoded_bytes(arch, col, bits)
            ds, column = CELL_MAP[col]
            meas = common.best_shipped(common.cell(arch, ds, column, bits))
            if not (db and meas):
                continue
            dur_ns = det[("GPU Speed Of Light Throughput", "Duration")]
            in_rate = db / dur_ns  # GB/s at the locked profiling clock, in-capture

            sol = {
                "l1": det.get(("GPU Speed Of Light Throughput", "L1/TEX Cache Throughput")),
                "l2": det.get(("GPU Speed Of Light Throughput", "L2 Cache Throughput")),
                "dram": det.get(("GPU Speed Of Light Throughput", "DRAM Throughput")),
                "sm": det.get(("GPU Speed Of Light Throughput", "Compute (SM) Throughput")),
            }

            # device-wide L2 (timing-independent peak from the per_second/pct pair)
            l2_sec = _median_raw(rawp, "lts__t_sectors.sum")
            l2_ps = _median_raw(rawp, "lts__t_sectors.sum.per_second")            # sector/ns
            l2_pct = _median_raw(rawp, "lts__t_sectors.sum.pct_of_peak_sustained_elapsed")
            l2_peak = l2_ps / (l2_pct / 100.0) if (l2_ps and l2_pct) else None

            # L1/TEX (peak derived from SOL% + duration, as in v1)
            l1_sec = _l1_sectors(rawp)
            l1_pct = _median_raw(rawp, "l1tex__throughput.avg.pct_of_peak_sustained_elapsed")
            l1_peak = ((l1_sec / dur_ns) / (l1_pct / 100.0)) if (l1_sec and l1_pct) else None

            pred_l1 = db * l1_peak / l1_sec if (l1_sec and l1_peak) else None
            pred_l2 = db * l2_peak / l2_sec if (l2_sec and l2_peak) else None
            pred_dram = in_rate / (sol["dram"] / 100.0) if sol.get("dram") else None

            binding = max(("l1", "l2", "dram"), key=lambda p: sol[p] or 0)
            pred_binding = {"l1": pred_l1, "l2": pred_l2, "dram": pred_dram}[binding]
            pred_paper = {"l1": pred_l1, "l2": pred_l2}[PAPER_BINDING[arch]]

            stall = {}
            for s in STALLS:
                stall[s] = _median_raw(
                    rawp, "smsp__average_warps_issue_stalled_%s_per_issue_active.ratio" % s) or 0.0
            top = sorted(stall, key=lambda s: -stall[s])
            tot_stall = sum(stall.values()) or 1.0

            rows.append({
                "arch": arch, "col": col, "bits": bits, "kernel": kern, "occ": occ,
                "decoded_bytes": db, "chunks": chunks, "dur_ms": dur_ns / 1e6, "in_rate": in_rate,
                "sol_l1": sol["l1"], "sol_l2": sol["l2"], "sol_dram": sol["dram"], "sol_sm": sol["sm"],
                "l1_sec": l1_sec, "l2_sec": l2_sec, "l1_peak": l1_peak, "l2_peak": l2_peak,
                "binding": binding, "predicted": pred_binding,
                "pred_l1": pred_l1, "pred_l2": pred_l2, "pred_paper": pred_paper,
                "measured": meas,
                "stall_top1": "%s=%.2f" % (top[0], stall[top[0]]),
                "stall_top2": "%s=%.2f" % (top[1], stall[top[1]]),
                "long_sb_share": 100.0 * stall["long_scoreboard"] / tot_stall,
            })
    return rows


def _r2(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    ybar = sum(ys) / n
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    ss_res = sum((y - x) ** 2 for x, y in zip(xs, ys))
    return 1 - ss_res / ss_tot if ss_tot else float("nan")


def _fit_stats(label, pairs):
    import math
    pairs = [(p, m) for p, m in pairs if p and m]
    if len(pairs) < 2:
        return
    preds = [p for p, _ in pairs]
    meas = [m for _, m in pairs]
    ratios = [m / p for p, m in pairs]
    rel = [abs(p - m) / m for p, m in pairs]
    lp = [math.log(p) for p in preds]
    lm = [math.log(m) for m in meas]
    n = len(lp)
    mp, mm = sum(lp) / n, sum(lm) / n
    cov = sum((a - mp) * (b - mm) for a, b in zip(lp, lm))
    vp = math.sqrt(sum((a - mp) ** 2 for a in lp))
    vm = math.sqrt(sum((b - mm) ** 2 for b in lm))
    r_log = cov / (vp * vm) if vp and vm else float("nan")
    sys.stderr.write(
        "%-28s n=%2d  R2(y=x)=%7.3f  r(log-log)=%.3f  med|rel|=%5.1f%%  "
        "meas/pred median %.2fx range %.2f-%.2fx\n"
        % (label, n, _r2(preds, meas), r_log, 100 * st.median(rel),
           st.median(ratios), min(ratios), max(ratios)))


def main():
    rows = collect()
    fields = ["arch", "col", "bits", "kernel", "chunks", "occ", "dur_ms", "in_capture_GBps",
              "sol_l1", "sol_l2", "sol_dram", "sol_sm", "binding",
              "l1_sec_per_byte", "l2_sec_per_byte", "l1_peak_sec_ns", "l2_peak_sec_ns",
              "pred_GBps", "pred_l1_GBps", "pred_l2_GBps", "pred_paper_GBps",
              "measured_GBps", "ratio_meas_over_pred",
              "stall_top1", "stall_top2", "long_scoreboard_share_pct"]
    out = [fields]
    for r in rows:
        p = r["predicted"]
        out.append([
            r["arch"], r["col"], r["bits"], r["kernel"], r["chunks"], round(r["occ"], 1),
            "%.3f" % r["dur_ms"], "%.1f" % r["in_rate"],
            "%.1f" % r["sol_l1"], "%.1f" % r["sol_l2"], "%.1f" % r["sol_dram"], "%.1f" % r["sol_sm"],
            r["binding"],
            "%.3f" % (r["l1_sec"] / r["decoded_bytes"]) if r["l1_sec"] else "",
            "%.3f" % (r["l2_sec"] / r["decoded_bytes"]) if r["l2_sec"] else "",
            "%.1f" % r["l1_peak"] if r["l1_peak"] else "",
            "%.1f" % r["l2_peak"] if r["l2_peak"] else "",
            "%.1f" % p if p else "",
            "%.1f" % r["pred_l1"] if r["pred_l1"] else "",
            "%.1f" % r["pred_l2"] if r["pred_l2"] else "",
            "%.1f" % r["pred_paper"] if r["pred_paper"] else "",
            "%.1f" % r["measured"],
            "%.2f" % (r["measured"] / p) if p else "",
            r["stall_top1"], r["stall_top2"], "%.1f" % r["long_sb_share"],
        ])

    w = csv.writer(sys.stdout)
    for line in out:
        w.writerow(line)
    common.OUTDIR.mkdir(exist_ok=True)
    with open(common.OUTDIR / "fig_roofline_v2.csv", "w", newline="") as f:
        cw = csv.writer(f)
        for line in out:
            cw.writerow(line)

    sys.stderr.write("\n=== v2 (shipped-kernel captures): fit per binding variant ===\n")
    _fit_stats("binding=max-SOL pipe", [(r["predicted"], r["measured"]) for r in rows])
    _fit_stats("binding=v1 paper map", [(r["pred_paper"], r["measured"]) for r in rows])
    _fit_stats("L1 everywhere", [(r["pred_l1"], r["measured"]) for r in rows])
    _fit_stats("L2 everywhere", [(r["pred_l2"], r["measured"]) for r in rows])

    # v1's 21 device-filled cells, for apples-to-apples with ROOFLINE-FINDINGS.md.
    V1_CELLS = {("b300", c, b) for c in ("clickbench_URL", "synthetic_url",
                                         "tpch-sf10_l_shipinstruct", "tpch-sf10_ps_comment")
                for b in (12, 16)} | {("b300", "tpch-sf10_l_comment", 16)} \
        | {("h100", c, 12) for c in ("clickbench_URL", "synthetic_url", "tpch-sf10_l_shipinstruct")} \
        | {("l40s", c, b) for c in ("clickbench_URL", "synthetic_url",
                                    "tpch-sf10_l_shipinstruct", "tpch-sf10_ps_comment")
           for b in (12, 16)} | {("l40s", "tpch-sf10_l_comment", 16)}
    sub = [r for r in rows if (r["arch"], r["col"], r["bits"]) in V1_CELLS]
    _fit_stats("v1 21-cell subset", [(r["predicted"], r["measured"]) for r in sub])

    sys.stderr.write("\nper-arch, binding=max-SOL (clock_scale = per-arch median meas/pred,\n"
                     "physically the boost:locked clock ratio; captures are clock-locked):\n")
    for arch in ARCHES:
        sub = [r for r in rows if r["arch"] == arch and r["predicted"]]
        _fit_stats("  %s" % arch, [(r["predicted"], r["measured"]) for r in sub])
        ratios = [r["measured"] / r["predicted"] for r in sub]
        scale = st.median(ratios)
        scaled = [(r["predicted"] * scale, r["measured"]) for r in sub]
        rel = [abs(p - m) / m for p, m in scaled]
        ir = [r["measured"] / r["in_rate"] for r in sub]
        sys.stderr.write(
            "  %s clock_scale=%.2f -> R2(y=x)=%6.3f  med|rel|=%.1f%%  max|rel|=%.1f%%   "
            "(meas/in-capture: median %.2fx range %.2f-%.2fx)\n"
            % (arch, scale, _r2([p for p, _ in scaled], [m for _, m in scaled]),
               100 * st.median(rel), 100 * max(rel), st.median(ir), min(ir), max(ir)))

    _plot(rows)


def _plot(rows):
    plt = common.apply_theme()
    fig, ax = common.new_fig(w=5.2, h=4.4)
    cmap = {"a100": "#e7298a", "b300": "#1b9e77", "h100": "#d95f02", "l40s": "#7570b3"}
    mmap = {"l1": "o", "l2": "s", "dram": "^"}
    for r in rows:
        if not r["predicted"]:
            continue
        ax.scatter(r["predicted"], r["measured"], s=34, color=cmap[r["arch"]],
                   marker=mmap[r["binding"]], edgecolor="black", linewidth=0.4, zorder=3)
        ax.annotate("%s %s b%d" % (r["arch"], r["col"].replace("tpch-sf10_", "").replace("_URL", ""), r["bits"]),
                    (r["predicted"], r["measured"]), fontsize=4.2,
                    xytext=(3, 2), textcoords="offset points")
    allv = [v for r in rows if r["predicted"] for v in (r["predicted"], r["measured"])]
    lo, hi = min(allv) * 0.6, max(allv) * 1.4
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=0.8, zorder=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("predicted decode GB/s (max-SOL-pipe sector-rate roofline, locked clock)")
    ax.set_ylabel("measured shipped decode GB/s (boost clock)")
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=c, label=a.upper(),
                          markeredgecolor="black", markeredgewidth=0.4)
               for a, c in cmap.items()]
    handles += [plt.Line2D([], [], marker=mk, linestyle="", color="#999999",
                           label="binding=%s" % b.upper(), markeredgecolor="black",
                           markeredgewidth=0.4) for b, mk in mmap.items()]
    handles.append(plt.Line2D([], [], linestyle="--", color="black", label="y=x"))
    ax.legend(handles=handles, fontsize=5.5, loc="lower right")
    ax.set_title("Request-rate roofline vs measured throughput (v2, shipped kernel)", fontsize=7)
    common.save(fig, "fig_roofline_v2")


if __name__ == "__main__":
    main()
