#!/usr/bin/env python3
"""Reduce archived or fresh staged-dictionary timing JSON with validation gates."""
import argparse
import json
from pathlib import Path
import statistics

STAGING = {"onpair_shmem_4tpt_" + s for s in ("pdict", "vdict", "shdict8")}


def reduce_cell(cell):
    g = cell.get("gpu")
    if not g or not g.get("decoded_bytes", 0) > 0:
        raise ValueError("Missing GPU result or decoded byte count")
    rows = []
    seen = set()
    for k in g["kernels"]:
        name = k["kernel"]
        if name in seen:
            raise ValueError(f"Duplicate kernel {name}")
        seen.add(name)
        if k.get("applicable") is False:
            if name in STAGING:
                rows.append({"kernel": name, "applicable": False})
            continue
        samples = k.get("decode_ns_iters")
        if (k.get("applicable") is not True or k.get("verified") is not True
                or not samples or any(n <= 0 for n in samples)):
            raise ValueError(f"{name}: applicable result lacks successful validation or timings")
        rows.append({"kernel": name, "applicable": True,
                     "samples": len(samples), "min_ns": min(samples),
                     "median_ns": statistics.median(samples),
                     "min_gb_s": g["decoded_bytes"] / min(samples),
                     "median_gb_s": g["decoded_bytes"] / statistics.median(samples)})
    missing = STAGING - seen
    if missing:
        raise ValueError(f"Missing staging candidates: {sorted(missing)}")
    staged = [r for r in rows if r["applicable"] and r["kernel"] in STAGING]
    global_rows = [r for r in rows if r["applicable"] and r["kernel"] not in STAGING]
    if not global_rows:
        raise ValueError("No validated nonstaging comparison")
    global_best = max(global_rows, key=lambda r: r["min_gb_s"])
    staged_best = max(staged, key=lambda r: r["min_gb_s"]) if staged else None
    return {"decoded_bytes": g["decoded_bytes"],
            "global_candidates": len(global_rows), "staging_candidates": len(staged),
            "global_best": global_best, "staging_best": staged_best,
            "staging_throughput_deficit_pct": None if not staged_best else
                100 * (1 - staged_best["min_gb_s"] / global_best["min_gb_s"]),
            "staging_rows": [r for r in rows if r["kernel"] in STAGING]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    out = []
    for path in args.files:
        data = json.loads(path.read_text())
        cells = data if isinstance(data, list) else [data]
        if not cells:
            raise ValueError(f"{path}: empty result")
        for idx, cell in enumerate(cells):
            out.append({"file": str(path), "cell_index": idx, **reduce_cell(cell)})
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
