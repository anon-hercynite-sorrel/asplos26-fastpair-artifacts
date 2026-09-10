# `a100-shdict-ncu` — staged-dictionary mechanism capture

Why shared-memory dictionary staging loses (the timing verdict is in
`results/{a100,h100}-shdict/`). 16 `--set full` NCU captures on a GCP A100-SXM4-40GB (`a2-highgpu-1g`,
us-central1-a), the same part as the paper's Lambda A100, so the mechanism data matches the
chip the timing sweep used at rev `9b4714c2a`, same metric set as the NCU cost surface so the
numbers are comparable to `fig:costsurface` and `tab:bottleneck`.

Cells: ClickBench `URL` and TPC-H `l_comment` at bits12 (4 kernels) and bits14 (2 kernels,
`pdict`/`vdict` exceed the 100 KB cap and never launch), FineWeb `text` at bits12 (4).

**All 16 CAPTURE-VERIFIED.** Each capture asserts its own identity: the profiled kernel
symbol must match the requested one, and its shared-memory footprint must be nonzero. The
assertion checks *dynamic* shared memory for the staging variants, which use
`extern __shared__`, and *static* for the shipped `split8read`, which uses a fixed array.
Asserting static-only (as the cost-surface job does) would mark every staging capture
invalid. Measured footprints match prediction: `shdict8` 53.5 KB (bits12) / 164.1 KB
(bits14), `pdict` 86.3 KB, `vdict` 38.0 KB.

Profiling requires `RmProfilingAdminOnly=0`, which Lambda's A100 does not permit, so this
Ampere capture runs on GCP instead. `a2-highgpu-1g` (40GB) was chosen over `a2-ultragpu-1g`
(80GB) both because it matches the paper's part and because it exists in 19 zones rather
than 7.

## Reduction

`figures/extract_shdict_ncu.py <this dir>`. NCU's raw page is **wide** (metrics as columns,
a units row before the data), unlike the details page's long format.

## The finding

The staging move works exactly as designed on the read side and still loses. On ClickBench
`URL` bits12, global-load sectors fall 363.4M to 15.5M and bytes per sector rises 6.2 to
29.4 of a 32 B maximum, so the scattered gather did become a near-coalesced stream. Shared
bank conflicts rise 91k to 54.8M (602x) and achieved occupancy falls 41.2% to 12.5%: on the
A100 the 164 KB shared limit leaves the 86 KB padded table only ONE resident block per SM,
so the occupancy penalty is harsher here than the H100's 24.0%.
L1 SoL falls rather than rising, and DRAM read SoL stays at 2.4-9%, so nothing became
bandwidth-bound. See `experiments/MANIFEST.md` for the full table.
