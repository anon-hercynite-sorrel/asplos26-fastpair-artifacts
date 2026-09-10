# `h100-shdict-ncu` — staged-dictionary mechanism capture

Why shared-memory dictionary staging loses (the timing verdict is in
`results/{a100,h100}-shdict/`). 16 `--set full` NCU captures on an H100 80GB HBM3
(Nebius eu-north1) at rev `9b4714c2a`, same metric set as the NCU cost surface so the
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

Profiling requires `RmProfilingAdminOnly=0`; Nebius boxes allow it, Lambda's A100 does not,
which is why the mechanism leg is H100 (and B300 when its region recovers) rather than all
three chips.

## Reduction

`figures/extract_shdict_ncu.py <this dir>`. NCU's raw page is **wide** (metrics as columns,
a units row before the data), unlike the details page's long format.

## The finding

The staging move works exactly as designed on the read side and still loses. On ClickBench
`URL` bits12, global-load sectors fall 362.4M to 15.6M and bytes per sector rises 6.2 to
29.4 of a 32 B maximum, so the scattered gather did become a near-coalesced stream. Shared
bank conflicts rise 67.7k to 57.0M (842x) and achieved occupancy halves, 43.8% to 24.0%.
L1 SoL falls rather than rising, and DRAM read SoL stays at 2.4-9%, so nothing became
bandwidth-bound. See `experiments/MANIFEST.md` for the full table.
