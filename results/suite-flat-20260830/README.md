# suite-flat-20260830 — the payload-only basis, and the Zstd frame sweep

B300 SXM6, leg revision `876c062b2e7cc69729339e0c1f1829cfdec0fe78`, boost clocks, training seed
20260819, 1 GB sample per column. The standalone DE/gANS/Bitcomp cells were byte-checked by `de_stage.py`; Zstd uses a separate Rust path (see below).

## Why this leg exists

Section 5 measures every technique decoding the **string payload alone**, and excludes the row
offsets from the compression ratio on the ground that they are not read during bulk decompression.

The DE, gANS and Bitcomp runs use flat concatenated payloads. Zstd goes through
Rust's variable-length encoder, which prefixes each value with its little-endian
u32 length before grouping values into frames. Its `raw_bytes` numerator counts
only string payload. Equal payload numerators do **not** establish equal decoded
framing. The September 9 bounded validation matches the historical Windows
compressed-byte fingerprint with that prefix representation; see
[the Zstd reproduction notes](../../experiments/zstd/README.md).

The historical Zstd outputs do not record per-frame status/size or full-output
verification. The current harness adds these checks; the bounded validation does
not retroactively certify every archived Zstd cell.

## Contents

| file | what it is |
|---|---|
| `b300/onpair_nvcomp_hw.json` | the DE, flat, **7 chunk sizes** (32 KiB–2 MiB) |
| `b300/onpair_nvcomp_hw_5chunk.json` | the DE, flat, the historical 5 — isolates sweep width from framing |
| `b300/onpair_nvcomp_sw.json` | gANS and both Bitcomp modes, flat, 5 chunk sizes |
| `b300/zstd_frames.json` | Zstd, 14 columns × 3 levels × 7 byte-anchored frame targets |
| `b300/zstd_frames_shipinstruct.json` | `l_shipinstruct`, measured first, at **5** levels × 7 frames |

`framing` is `"flat"` and `raw_bytes == payload_bytes` on every row of the three nvCOMP files.

## Historical producer changes

The comparator leg's numbers were produced by files pushed to a box by
`runs/pilot-comparator-fixes.sh` and never committed, so pinning this leg to `876c062b2` reverted
all three. Each was restored by pushing a file, and the job asserts the markers on the box before
building:

| file | at `876c062b2` | used here |
|---|---|---|
| `nvcomp_hw_bench.cu` | `sweep_chunks[5]` | `sweep_chunks[7]`, from the campaign worktree |
| `nvcomp_sw_bench.cu` | no payload basis | `c8fa5200b`, reads `NVCOMP_PAYLOAD_BYTES` |
| `onpair_bench.rs` | `NVCOMP_ZSTD_LEVELS = [-10, 1, 3]`, frame pinned at 2048 values | `[-10, 3, 19]` plus a byte-anchored frame axis |

The DE bench failed **silently** when reverted: it produced 15 valid columns whose optima all sat at
the largest swept size, which is a boundary rather than an optimum. The restored Zstd environment controls and exact historical values are documented in
[experiments/zstd](../../experiments/zstd/README.md).

## The frame axis

`NVCOMP_ZSTD_VALUES_PER_FRAME` pinned Zstd at 2048 **values**, which is 24 KiB on `l_shipinstruct`
(12 B rows) and 8.5 MB on `wikipedia` (4,276 B rows) — a 350x spread, and above nvCOMP's documented
16 MB maximum on `codeparrot`. The patched bench takes **byte** targets and converts them per column
from that column's mean row length, so Zstd shares the DE's grid.

Un-pinning is worth, median over 14 columns: level −10 +4.1% ratio / +59.4% rate; level 3 +5.8% /
+30.7%; level 19 +11.8% / +22.0%. All in the baseline's favour.

**There is no oracle on this axis.** In 0 of 42 (column, level) pairs does one frame dominate the
others on both ratio and rate; the median frontier is 6 of 7 frames. Best-ratio sits at the 2 MiB
grid top on 14 of 14 columns and the rate peak at the 32 KiB floor on 25 of 42 pairs, so the grid
bounds the curve rather than bracketing it.

**Large-frame rates are a sample-size artifact.** Frame count is `sample_bytes / frame_bytes`, so
2 MiB frames give 478 frames at 1 GB — too few to fill a B300. 41 of the 67 Zstd points that reach
the baseline envelope have under 2,000 frames. Their ratios are real; their rates would rise on a
larger sample. Section 5 therefore reports Zstd at a fixed 64 KiB frame (nvCOMP's documented
starting chunk size, ~15,000 frames on every column here) as the vendor default, with the best-found
points shown faded.

## What this leg does NOT settle

FSST-12's stored components are still collapsed by `Fsst12StoredSize` into `in_memory_bytes`, so its
row offsets cannot be separated from its codes and the offsets-excluded rule cannot be applied to
it from committed data. That needs the producer to emit components the way `ONPAIR_CHILD_BYTES`
does, then a CPU-only re-encode — `compress_offsets` is explicitly not cuda-gated.
