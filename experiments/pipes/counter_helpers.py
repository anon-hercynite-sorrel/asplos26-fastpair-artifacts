#!/usr/bin/env python3
"""Read-only NCU reducer. Writes only the explicitly chosen --output-prefix files.

Supports NCU wide (metric headers + units row) and long (Metric Name/Value) CSVs.
Always requires an explicit workload label; never infers that a smoke test is Windows.
"""
import argparse
import csv
import io
import json
import math
import re
import statistics
from pathlib import Path

DEFAULT_KERNELS = ["onpair_shmem_4tpt_b128o12", "onpair_dw_k6_t256_b4", "onpair_dg_k6_t256_b4"]
IDENTITY = ["ID", "Process ID", "Process Name", "Host Name", "Kernel Name", "Context", "Stream", "Block Size", "Grid Size", "Device", "CC"]
SHORT = {
    "duration_s": "gpu__time_duration.sum",
    "sm_hz": "sm__cycles_elapsed.avg.per_second",
    "memory_hz": "dram__cycles_elapsed.avg.per_second",
    "l1_elapsed_pct": "l1tex__data_pipe_lsu_wavefronts.avg.pct_of_peak_sustained_elapsed",
    "l1_active_pct": "l1tex__throughput.avg.pct_of_peak_sustained_active",
    "l2_pct": "lts__throughput.avg.pct_of_peak_sustained_elapsed",
    "dram_pct": "gpu__dram_throughput.avg.pct_of_peak_sustained_elapsed",
    "compute_pct": "sm__throughput.avg.pct_of_peak_sustained_elapsed",
    "bank_read_pct": "l1tex__data_bank_reads.avg.pct_of_peak_sustained_elapsed",
    "bank_write_pct": "l1tex__data_bank_writes.avg.pct_of_peak_sustained_elapsed",
    "wavefronts": "l1tex__data_pipe_lsu_wavefronts.sum",
    "shared_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared.sum",
    "shared_load_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ld.sum",
    "shared_store_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_st.sum",
    "shared_atomic_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_atom.sum",
    "shared_misc_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_misc.sum",
    "shared_ipa_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_ipa.sum",
    "shared_umemsets_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_op_umemsets.sum",
    "shared_cmd_read_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_cmd_read.sum",
    "shared_cmd_write_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_shared_cmd_write.sum",
    "lgds_cmd_read_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_lgds_cmd_read.sum",
    "lgds_cmd_write_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_lgds_cmd_write.sum",
    "lgds_wavefronts": "l1tex__data_pipe_lsu_wavefronts_mem_lgds.sum",
    "global_load_tag_wavefronts": "l1tex__t_output_wavefronts_pipe_lsu_mem_global_op_ld.sum",
    "global_store_tag_wavefronts": "l1tex__t_output_wavefronts_pipe_lsu_mem_global_op_st.sum",
    "global_load_sectors": "l1tex__t_sectors_pipe_lsu_mem_global_op_ld.sum",
    "global_load_requests": "l1tex__t_requests_pipe_lsu_mem_global_op_ld.sum",
    "local_load_sectors": "l1tex__t_sectors_pipe_lsu_mem_local_op_ld.sum",
    "local_store_sectors": "l1tex__t_sectors_pipe_lsu_mem_local_op_st.sum",
    "shared_load_conflicts": "l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_ld.sum",
    "shared_store_conflicts": "l1tex__data_bank_conflicts_pipe_lsu_mem_shared_op_st.sum",
    "occupancy_pct": "sm__warps_active.avg.pct_of_peak_sustained_active",
    "registers": "launch__registers_per_thread",
    "shared_block_bytes": "launch__shared_mem_per_block",
    "shared_config_bytes": "launch__shared_mem_config_size",
}

def numeric(value, unit):
    cleaned = value.strip().replace(",", "").replace("\u00a0", "")
    x = float(cleaned)
    if not math.isfinite(x):
        raise ValueError("nonfinite metric")
    u = unit.strip()
    # NCU --print-units base normally removes prefixes, but retain correct support
    # for the historical exports, which mix GHz/MHz and ns/us/ms among files.
    low = u.lower()
    if low in {"ns", "us", "µs", "μs", "ms", "s", "second"}:
        scale = {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "μs": 1e-6, "ms": 1e-3, "s": 1, "second": 1}[low]
        return x * scale, "s"
    if low in {"hz", "khz", "mhz", "ghz"}:
        return x * {"hz": 1, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}[low], "Hz"
    match = re.fullmatch(r"([KMGTP])?(byte|sector|cycle|inst|request|wavefront)s?", u, re.IGNORECASE)
    if match:
        prefix = (match.group(1) or "").upper()
        return x * {"": 1, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15}[prefix], match.group(2).lower()
    return x, u

def parse_csv(path):
    raw = path.read_text()
    rows = list(csv.reader(io.StringIO(raw)))
    starts = [i for i, r in enumerate(rows) if "Kernel Name" in r and "ID" in r]
    if len(starts) != 1:
        raise ValueError(f"expected one report header, found {len(starts)}")
    start = starts[0]
    header = rows[start]
    data = rows[start + 1:]
    launches = {}
    errors = []
    long_form = "Metric Name" in header and "Metric Value" in header
    if not long_form:
        if not data:
            raise ValueError("wide report has no units row")
        units = dict(zip(header, data.pop(0)))
    for row in data:
        if not row or len(row) != len(header):
            if row and any(s.strip() for s in row):
                errors.append(f"unexpected row width {len(row)} (expected {len(header)})")
            continue
        d = dict(zip(header, row))
        if not d.get("ID") or not d.get("Kernel Name"):
            continue
        ident = {k: d[k] for k in IDENTITY if k in d}
        key = tuple(ident.get(k, "") for k in ("ID", "Process ID", "Context", "Stream", "Kernel Name"))
        launch = launches.setdefault(key, {"identity": ident, "metrics": {}, "metric_errors": {}})
        if launch["identity"] != ident:
            errors.append(f"identity differs inside launch {key}")
        if long_form:
            entries = [(d["Metric Name"], d["Metric Value"], d.get("Metric Unit", ""))]
        else:
            entries = [(k, v, units.get(k, "")) for k, v in d.items() if k not in IDENTITY]
        for name, value, unit in entries:
            try:
                num, base_unit = numeric(value, unit)
            except ValueError:
                launch["metric_errors"][name] = {"value": value, "unit": unit}
                continue
            item = {"value": num, "unit": base_unit, "original_value": value, "original_unit": unit}
            if name in launch["metrics"] and launch["metrics"][name] != item:
                errors.append(f"conflicting repeated metric {name} in {key}")
            launch["metrics"][name] = item
    if not launches:
        errors.append("zero captured launches")
    return list(launches.values()), errors

def mean_range(values):
    return {"mean": statistics.mean(values), "min": min(values), "max": max(values), "n": len(values)}

def derive(launch, decoded_bytes):
    m = launch["metrics"]
    v = {short: m[name]["value"] for short, name in SHORT.items() if name in m}
    if "bank_read_pct" in v and "bank_write_pct" in v:
        v["bank_normalized_activity_sum_pct"] = v["bank_read_pct"] + v["bank_write_pct"]
    total = v.get("wavefronts", 0)
    if total:
        for label in ("shared", "shared_load", "shared_store", "shared_atomic"):
            if f"{label}_wavefronts" in v:
                v[f"{label}_share_pct"] = 100 * v[f"{label}_wavefronts"] / total
        if "shared_share_pct" in v:
            v["nonshared_share_pct"] = 100 - v["shared_share_pct"]
            tag_total = v.get("global_load_tag_wavefronts", 0) + v.get("global_store_tag_wavefronts", 0)
            if tag_total:
                v["estimated_nonshared_load_share_pct"] = v["nonshared_share_pct"] * v["global_load_tag_wavefronts"] / tag_total
                v["estimated_nonshared_store_share_pct"] = v["nonshared_share_pct"] * v["global_store_tag_wavefronts"] / tag_total
    # These are arithmetic closure diagnostics, not an assumption that the
    # enumerated counters partition physical activity. Keep residuals visible.
    closures = {
        "shared_ld_st_atom_residual": ("shared", ["shared_load", "shared_store", "shared_atomic"]),
        "shared_all_ops_residual": ("shared", ["shared_load", "shared_store", "shared_atomic", "shared_misc", "shared_ipa", "shared_umemsets"]),
        "shared_cmd_residual": ("shared", ["shared_cmd_read", "shared_cmd_write"]),
        "lgds_cmd_residual": ("lgds", ["lgds_cmd_read", "lgds_cmd_write"]),
        "total_memory_family_residual": ("", ["shared", "lgds"]),
    }
    for key, (whole, parts) in closures.items():
        aggregate = f"{whole}_wavefronts" if whole else "wavefronts"
        operands = [f"{part}_wavefronts" for part in parts]
        if aggregate in v and all(x in v for x in operands):
            residual = v[aggregate] - sum(v[x] for x in operands)
            v[key + "_wavefronts"] = residual
            if total:
                v[key + "_share_pct"] = 100 * residual / total
    if total:
        for family in ("shared_misc", "shared_ipa", "shared_umemsets", "shared_cmd_read", "shared_cmd_write", "lgds", "lgds_cmd_read", "lgds_cmd_write"):
            if family + "_wavefronts" in v:
                v[family + "_share_pct"] = 100 * v[family + "_wavefronts"] / total
    if v.get("global_load_requests"):
        v["global_load_sectors_per_request"] = v["global_load_sectors"] / v["global_load_requests"]
    if "shared_load_conflicts" in v and "shared_store_conflicts" in v:
        v["shared_conflict_counter_total"] = v["shared_load_conflicts"] + v["shared_store_conflicts"]
    if decoded_bytes:
        for k in ("wavefronts", "shared_wavefronts", "shared_store_wavefronts", "global_load_sectors", "local_load_sectors", "local_store_sectors"):
            if k in v:
                v[f"{k}_per_output_byte"] = v[k] / decoded_bytes
    return v
