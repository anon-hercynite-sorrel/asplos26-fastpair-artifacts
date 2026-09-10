# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Rebuild a cost-surface CSV row-set from an NCU dump dir (the *_details.csv SOL
section + the *_raw.csv wavefront/sector columns), averaging across kernel invocations.

Usage: uv run extract_costsurface.py <arch> <ncu_dir>   -> prints CSV rows (no header)

The L1 bar is decomposed by LSU wavefronts into a memory-space x direction 2x2:
gather (global load), drain-out (global store), readback (shared load), emit
(shared store). See l1_split() for the counter provenance and the one cross-family
seam (the within-global load:store ratio) that the paper footnotes.
"""
import csv
import sys
import glob
import os

# distinct_codes (dict-12 cardinality) per column, matching the committed CSV.
CARD = {
    "clickbench_URL": 4018, "fineweb_text": 4042, "synthetic_url": 169,
    "tpch-sf10_l_comment": 3863, "tpch-sf10_l_shipinstruct": 5,
    "tpch-sf10_ps_comment": 3870, "wikipedia_text": 4048,
    # 2026-08-24: pre-registered for the Loghub Windows capture fig:pipes wants, so the extractor
    # consumes that dump without an edit. 3551 is gpu.distinct_codes for loghub-windows at twelve
    # bits in suite-paper-20260821; both key spellings are accepted since the NCU filename stem
    # depends on how the capture script slugs the dataset id.
    "loghub-windows_line": 3551, "loghub_windows_line": 3551,
}
SOL = {  # (Section, Metric) -> csv column
    "l1tex": ("GPU Speed Of Light Throughput", "L1/TEX Cache Throughput"),
    "l2":    ("GPU Speed Of Light Throughput", "L2 Cache Throughput"),
    "dram":  ("GPU Speed Of Light Throughput", "DRAM Throughput"),
    "sm":    ("GPU Speed Of Light Throughput", "Compute (SM) Throughput"),
    "l1hit": ("Memory Workload Analysis", "L1/TEX Hit Rate"),
}


def mean(xs):
    xs = [x for x in xs if x is not None and x == x]  # drop None and NaN
    return sum(xs) / len(xs) if xs else 0.0


def sol_means(details_path):
    acc = {k: [] for k in SOL}
    with open(details_path) as f:
        for row in csv.reader(f):
            if len(row) < 15:
                continue
            sect, metric, val = row[11], row[12], row[14]
            for k, (s, m) in SOL.items():
                if sect == s and metric == m:
                    try:
                        acc[k].append(float(val))
                    except ValueError:
                        pass
    return {k: mean(v) for k, v in acc.items()}


# Read/write-split counters for the byte pipes (L2, DRAM), both in sectors (the
# transaction unit). NB: dram__bytes_read/write.sum are degenerate in these dumps
# (single-digit-to-hundreds per launch, an NCU export quirk) and collapse to a
# spurious ~99%-read on some L40S captures; dram__sectors_read/write.sum are sane
# and consistent (~80% write, output streaming, on every chip). Use sectors.
RW = {  # csv column -> (read_suffix, write_suffix)
    "l2": ("lts__t_sectors_srcunit_tex_op_read.sum",
           "lts__t_sectors_srcunit_tex_op_write.sum"),
    "dram": ("dram__sectors_read.sum",
             "dram__sectors_write.sum"),
}

# L1 decomposition counters. The binding L1 pipe carries both the dictionary gather
# (global loads) and the staged drain/emit scratch traffic (shared stores/loads).
# We split it on LSU wavefronts, the currency of the L1 access-rate SoL bar:
#   * the global/shared TOP split comes from data_pipe_lsu_wavefronts (the meter the
#     bar height IS) -- shared vs total, both as %-of-peak (same peak, so the ratio
#     is the wavefront-share ratio);
#   * the within-shared load:store split comes from that same data_pipe family;
#   * the within-GLOBAL load:store ratio is the one cross-family value: the data_pipe
#     family does not op-split its global wavefronts, so we borrow the ratio from
#     t_output_wavefronts. Global stores are only ~4% of the pipe, so this seam moves
#     a thin sliver; the paper footnotes it.
L1_DP_TOT = "l1tex__data_pipe_lsu_wavefronts.sum.pct_of_peak_sustained_elapsed"
L1_DP_SH = "l1tex__data_pipe_lsu_wavefronts_mem_shared.sum.pct_of_peak_sustained_elapsed"
L1_SH = {  # data_pipe shared, by op (counts)
    "ld": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ld.sum",
    "st": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_st.sum",
    "atom": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_atom.sum",
}
L1_G = {  # t_output global, by op (counts) -- ratio only
    "ld": "l1tex__t_output_wavefronts_pipe_lsu_mem_global_op_ld.sum",
    "st": "l1tex__t_output_wavefronts_pipe_lsu_mem_global_op_st.sum",
}


def _resolve(fieldnames, suffix):
    for c in fieldnames:
        if c.endswith(suffix):
            return c
    return None


def _sum_col(rows, col):
    if not col:
        return 0.0
    tot = 0.0
    for r in rows:
        try:
            tot += float((r[col] or "0").replace(",", ""))
        except (ValueError, TypeError):
            pass
    return tot


def rw_read_share(rows, fieldnames):
    """Read share (%) per byte pipe in RW, summed over kernel invocations.

    Returns None for a pipe whose counters are ABSENT FROM THE DUMP, which is not the same thing
    as a measured zero. dram__sectors_read/write.sum do not exist on sm_120 -- verified on the
    2026-08-24 RTX PRO capture, where only the dram__bytes.* family is present -- and _sum_col
    returns 0.0 for a column it cannot resolve. That made the RTX PRO report dram_rd=0.0, i.e. a
    confident "100% of device-memory traffic is writes", from counters nobody had measured.
    fig_costsurface draws this field, so a silent zero becomes a drawn bar. None serialises to an
    empty cell and any consumer that floats() it fails loudly instead."""
    out = {}
    for k, (rd, wr) in RW.items():
        rd_col, wr_col = _resolve(fieldnames, rd), _resolve(fieldnames, wr)
        if rd_col is None and wr_col is None:
            out[k] = None
            continue
        r = _sum_col(rows, rd_col)
        w = _sum_col(rows, wr_col)
        out[k] = 100 * r / (r + w) if (r + w) else 0.0
    return out


def l1_split(rows, fieldnames):
    """L1 wavefront 2x2 as %-of-L1-total: (gather, drain_out, readback, emit).

    gather=global ld, drain_out=global st, readback=shared ld, emit=shared st.
    Returns (0,0,0,0) when the wavefront counters are absent (e.g. a dump without
    the full set)."""
    tot_pct = _sum_col(rows, _resolve(fieldnames, L1_DP_TOT))
    sh_pct = _sum_col(rows, _resolve(fieldnames, L1_DP_SH))
    if not tot_pct:
        return (0.0, 0.0, 0.0, 0.0)
    sh = sh_pct / tot_pct           # shared share of the L1 pipe
    gl = 1.0 - sh                   # global (+local) share
    # within-global load:store ratio, borrowed from t_output (the seam)
    g_ld = _sum_col(rows, _resolve(fieldnames, L1_G["ld"]))
    g_st = _sum_col(rows, _resolve(fieldnames, L1_G["st"]))
    gt = g_ld + g_st
    g_ld_r = g_ld / gt if gt else 1.0
    # within-shared load:store(:atom) ratio, from data_pipe itself
    s_ld = _sum_col(rows, _resolve(fieldnames, L1_SH["ld"]))
    s_st = _sum_col(rows, _resolve(fieldnames, L1_SH["st"]))
    s_at = _sum_col(rows, _resolve(fieldnames, L1_SH["atom"]))
    st = s_ld + s_st + s_at
    s_ld_r = s_ld / st if st else 0.0
    s_st_r = s_st / st if st else (1.0 if st == 0 and sh else 0.0)
    return (100 * gl * g_ld_r, 100 * gl * (1 - g_ld_r),
            100 * sh * s_ld_r, 100 * sh * s_st_r)


def raw_rows(raw_path):
    if not os.path.exists(raw_path):
        return [], []
    with open(raw_path) as f:
        rdr = csv.DictReader(f)
        return list(rdr), rdr.fieldnames


def main():
    arch, ncu_dir = sys.argv[1], sys.argv[2]
    out = []
    for dpath in sorted(glob.glob(os.path.join(ncu_dir, "ncu_costsurface_*_b*_details.csv"))):
        base = os.path.basename(dpath)
        stem = base[len("ncu_costsurface_"):-len("_details.csv")]
        col, bits = stem.rsplit("_b", 1)
        if col not in CARD:
            continue
        s = sol_means(dpath)
        rows, fn = raw_rows(dpath.replace("_details.csv", "_raw.csv"))
        gld, gst, shld, shst = l1_split(rows, fn) if rows else (0.0, 0.0, 0.0, 0.0)
        share = rw_read_share(rows, fn) if rows else {"l2": 0.0, "dram": 0.0}
        out.append((arch, col, CARD[col], int(bits),
                    s["l1tex"], s["l2"], s["dram"], s["sm"], s["l1hit"],
                    gld, gst, shld, shst, share["l2"], share["dram"]))
    for r in sorted(out, key=lambda r: (r[1], r[3])):
        # The two read-share fields may be None (counters absent from the dump, not a measured
        # zero), so they are formatted separately rather than through one %.1f run.
        head = "%s,%s,%d,%d,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f" % r[:13]
        tail = ",".join("" if v is None else "%.1f" % v for v in r[13:])
        print("%s,%s" % (head, tail))


if __name__ == "__main__":
    main()
