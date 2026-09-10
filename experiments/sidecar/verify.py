#!/usr/bin/env python3
"""Validate sidecar timing/persistence records; no CUDA or third-party packages."""
import argparse
import json
from pathlib import Path
import statistics


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--directory", type=Path, default=Path(__file__).parent / "evidence")
    args = ap.parse_args()
    files = sorted(args.directory.glob("*-k6-w*.json"))
    require(files, "No K6 regeneration records found")
    for path in files:
        r = json.loads(path.read_text())
        require(all(r.get(k) is True for k in
                    ("decode_valid", "offsets_ok", "decode_ok", "baseline_ok", "guard_ok")),
                f"{path}: missing or failed correctness check")
        require((r["k"], r["tok_per_batch"], r["block_threads"], r["min_blocks"],
                 r["held_high"], r["stage_bytes"], r["regen_block_threads"])
                == (6, 192, 256, 4, 1, 16, 512), f"{path}: unexpected configuration")
        require(r["low_plane_bytes"] in (8, 16), f"{path}: unsupported width")
        require(r["n_chunks"] == (r["total_tokens"] + 191) // 192,
                f"{path}: wrong batch count")
        for arm in ("regen", "decode", "regen_plus_decode"):
            samples = r[arm + "_ns_iters"]
            require(len(samples) == r["iters"] and len(samples) >= 3
                    and all(n > 0 for n in samples), f"{path}: invalid {arm} samples")
            require(abs(min(samples) / 1e6 - r[arm + "_ms"]) < 0.000011,
                    f"{path}: {arm} minimum disagrees with samples")
        decode = min(r["decode_ns_iters"])
        combined = min(r["regen_plus_decode_ns_iters"])
        overhead = 100 * (combined / decode - 1)
        loss = 100 * (1 - decode / combined)
        require(abs(overhead - r["regen_overhead_pct"]) < 0.02,
                f"{path}: overhead disagrees with samples")
        for arm in ("decode", "regen_plus_decode"):
            require(abs(r["decoded_bytes"] / min(r[arm + "_ns_iters"])
                        - r[arm + "_gbps"]) < 0.02,
                    f"{path}: {arm} throughput disagrees with samples")
        med_overhead = 100 * (statistics.median(r["regen_plus_decode_ns_iters"])
                              / statistics.median(r["decode_ns_iters"]) - 1)
        print(f"{path.name}: {r['iters']} samples; overhead {overhead:.2f}%, "
              f"throughput loss {loss:.2f}%; median overhead {med_overhead:.2f}%")
    reports = list(args.directory.glob("**/sidecar-roundtrip.jsonl"))
    require(reports, "No persistence roundtrip report found")
    count = 0
    for path in reports:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            require(r["roundtrip_ok"] is True, f"{path}: failed persistence check")
            require(r["n_offsets"] == (r["total_tokens"] + r["tok_per_batch"] - 1)
                    // r["tok_per_batch"], f"{path}: wrong stored offset count")
            require(0 < r["compressed_array_nbytes"] <= r["serialized_file_bytes"],
                    f"{path}: invalid byte counts")
            count += 1
    require(count > 0, "Empty persistence report")
    print(f"OK: {len(files)} regeneration records and {count} persistence records")


if __name__ == "__main__":
    main()
