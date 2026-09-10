# `b300-shdict-ncu` — staged-dictionary mechanism capture

Why shared-memory dictionary staging loses (the timing verdict is in
`results/{a100,l40s,h100,b300}-shdict/`). 16 `--set full` NCU captures on a B300 SXM6
(Nebius uk-south1) at rev `9b4714c2a`, same metric set as the NCU cost surface so the numbers
are comparable to `fig:costsurface` and `tab:bottleneck`.

Cells: ClickBench `URL` and TPC-H `l_comment` at bits12 (4 kernels) and bits14 (2 kernels,
`pdict`/`vdict` exceed the 100 KB cap and never launch), FineWeb `text` at bits12 (4).

**All 16 CAPTURE-VERIFIED.** Each capture asserts its own identity: the profiled kernel symbol
must match the requested one, and its shared-memory footprint must be nonzero. The assertion
checks *dynamic* shared memory for the staging variants, which use `extern __shared__`, and
*static* for the shipped `split8read`, which uses a fixed array. Measured footprints match
prediction: `shdict8` 53.5 KB (bits12) / 164.1 KB (bits14), `pdict` 86.3 KB, `vdict` 34–49 KB.

This is the paper's headline chip, so `tab:shdict` now draws its exhibit from here rather than
from the H100. The two agree closely enough that the choice is about which chip the reader
already has in mind, not about which result is true.

## Reduction

`figures/extract_shdict_ncu.py <this dir>`. NCU's raw page is **wide** (metrics as columns, a
units row before the data), unlike the details page's long format.

## The finding

The staging move works exactly as designed on the read side and still loses. On ClickBench
`URL` at bits12:

| kernel | global ld sectors | B/sector | shared ld conflicts | achieved occ % | L1 SoL % |
|---|---|---|---|---|---|
| `split8read` (shipped) | 360,325,318 | 6.2 | 69,708 | 43.6 | 87.6 |
| `pdict` | 15,590,799 (−96%) | 29.4 | 56,391,825 (**809×**) | 24.4 | 74.5 |
| `shdict8` | 42,961,312 (−88%) | 15.7 | 38,532,300 (553×) | 24.7 | 58.0 |
| `vdict` | 185,981,649 (−48%) | 9.9 | 56,932,836 (817×) | 24.9 | 72.3 |

Global-load sectors collapse by up to 96% and bytes per sector rises from 6.2 to 29.4 of a
32 B maximum, so the scattered gather really did become a near-coalesced stream. What it cost
instead is bank conflicts up to 809× and achieved occupancy roughly halved. L1 SoL *falls*
rather than rising (87.6 → 58.0–74.5), so the pipe is no longer what saturates, and DRAM read
SoL stays at or below 2.3% on every staged capture, so nothing became bandwidth-bound.

At bits14 the 164 KB table allows about one block per SM: `shdict8` occupancy drops to **12.5%**
against the shipped decode's 45.2%, and L1 SoL to 36.0% against 93.2%. That is why the bits14
losses (−55.7 to −65.5% here) run deeper than bits12's.

A random gather stays a random gather. Shared memory does not escape the access-rate bound; it
re-denominates cache-line misses as bank conflicts and charges occupancy on top. See
`experiments/MANIFEST.md` for the cross-chip table.
