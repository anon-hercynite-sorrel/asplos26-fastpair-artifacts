# Fused-positioning stall + drain-edge experiments

Rate relative to the shipped `onpair_shmem_4tpt_split8read` on the same cell, same run, same box.

`verified` is each kernel's own byte-exactness verdict. An unverified rate is not a result.

| cell | kernel | rel. shipped | GiB/s | verified |
|---|---|---:|---:|---|
| clickbench/URL b12 | fused, base (stalls) | 0.334x | 251 | yes |
| clickbench/URL b12 | fused, NO stall | 0.336x | 252 | yes |
| clickbench/URL b12 | fused base, 4 warps/block | 0.255x | 192 | yes |
| clickbench/URL b12 | fused base, 2 warps/block | 0.215x | 162 | yes |
| clickbench/URL b12 | fused base, 1 warp/block | 0.148x | 111 | yes |
| clickbench/URL b12 | streaming drain edges | 1.004x | 754 | yes |
| tpch-sf10/l_comment b12 | fused, base (stalls) | 0.368x | 389 | yes |
| tpch-sf10/l_comment b12 | fused, NO stall | 0.365x | 387 | yes |
| tpch-sf10/l_comment b12 | fused base, 4 warps/block | 0.270x | 286 | yes |
| tpch-sf10/l_comment b12 | fused base, 2 warps/block | 0.228x | 241 | yes |
| tpch-sf10/l_comment b12 | fused base, 1 warp/block | 0.154x | 163 | yes |
| tpch-sf10/l_comment b12 | streaming drain edges | 0.998x | 1057 | yes |

## Geomean over cells (byte-exact rows only)

- **fused, base (stalls)**: 0.350x of shipped (2 cells)
- **fused, NO stall**: 0.350x of shipped (2 cells)
- **fused base, 4 warps/block**: 0.263x of shipped (2 cells)
- **fused base, 2 warps/block**: 0.221x of shipped (2 cells)
- **fused base, 1 warp/block**: 0.151x of shipped (2 cells)
- **streaming drain edges**: 1.001x of shipped (2 cells)

**Removing the block-wide stall is worth 1.00x** (0.350x -> 0.350x of shipped).

Fused positioning is STILL SLOWER than the shipped decode even without the stall.
