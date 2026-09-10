# B300 workflow validation

This record covers the one-column commands in the [measurement guide](../../experiments/MEASURE.md),
[pipes](../../experiments/pipes/README.md), [staging](../../experiments/staging/README.md),
[sidecar](../../experiments/sidecar/README.md), and [Zstd](../../experiments/zstd/README.md)
guides on Windows OnPair-12. Check the saved records without a GPU:

```sh
python3 experiments/check_bounded.py
```

`make analyze` includes this check. It verifies checksums, the configured-grid
records, pipeline selection and counters, staging timings, sidecar correctness
and arithmetic, and the integrated Zstd output. The paper figures select their
own result directories; they do not read this validation record.

## Environment and input

| Setting | Value |
|---|---|
| Capture date (UTC) | 2026-09-10 |
| GPU | NVIDIA B300 SXM6 AC |
| Driver | 580.159.04 |
| CUDA compiler | 13.0.88 |
| Rust | 1.91.0 |
| Nsight Compute | 2025.3.1 |
| Harness revision | `cc9fbc483f15ccc08e67ede79ee4f3198786f740` |
| Measurement-script revision | `01cacce3ecd6c8b82adfec4f87145a96ae8984eb` |
| Input | Loghub Windows, `line`, OnPair-12 |
| Training seed / threshold | 20260819 / 0.2 |
| Sample | 4,139,945 rows; 999,999,899 UTF-8 payload bytes |
| Encoded input | 99,090,926 codes; one chunk |

The harness was built from the listed revision with CUDA enabled. The source
Parquet and its manifest were cached; the normal loader checked their identity,
and `run.py` encoded the column. Source Parquet SHA256:
`a3f346845f521f5fd0479ede2260fbb6a8f592da2fa23e0d68881192d21ec96c`.
This execution checks preparation from the cache, not acquisition from Zenodo.
The encoded container and benchmark binary digests are included in the evidence.

The pipeline collector resets clock locks and measures at boost. Its per-launch
SM clock is approximately 2.0304 GHz; `pipes/clocks.csv` contains the monitor
samples. The subsequent staging, sidecar and Zstd commands do not change clocks.

## Results

| Workflow | Recorded outcome |
|---|---|
| Configured grid | 585 applicable kernels byte-verified, 100 timings each; best minimum 1,532.09 GB/s |
| Pipes | `onpair_ds_k6_t128_b8_s12` selected; winner and recommendation profiled four times each; all validation checks pass |
| Staging | Three shared-dictionary variants and two global controls byte-verified, 100 timings each |
| Sidecar persistence | Exact roundtrips at 192, 128 and 32 codes per batch |
| K6 regeneration | W16/W8 offsets, decoded outputs and guards verified; 200 samples per arm |
| Integrated Zstd | Level 19, 271 values/frame; 100 timings; per-frame status/size checks and three full-output checks pass |

The pipeline reduction reports 98.8375% L1, 18.2175% L2, 24.0925% device memory,
and 50.1500% SM utilization. The L1 components are global read 27.6587,
global write 5.3738, shared read 6.2645, shared write 54.4062, and other 5.1343
percentage points of peak.

The best of the three staged kernels reaches 1,136.28 GB/s; the recommended
global-dictionary control reaches 1,501.25 GB/s. This comparison uses the five
listed staging/control selectors. Regeneration adds 16.91% elapsed time for W16
and 17.28% for W8, using directly measured combined regeneration/decode times.

Zstd produces 15,277 frames and 53,516,006 compressed bytes. Its decoded stream
contains 1,016,559,679 bytes, including the u32 lengths. The minimum is
3.122688 ms, or 320.24 GB/s using the string payload as numerator. This validation
covers one level/frame configuration on one column and device.

## Evidence layout

`evidence.tar.gz` contains the raw JSON timing and validation records, profiler
CSV exports, clock samples, source/input identities and tool versions.
`publication-provenance.json` maps source and published file hashes. Working paths
are normalized to `/work/fastpair`; GPU serial numbers, UUIDs and PDI are redacted.
Numerical measurements and timing arrays are unchanged. Corpus files, encoded
columns and binary profiler reports are not included.
