# `h100-widthncu-eval` — the access-width isolation on the H100, evaluated columns

H100 SXM (sm_90), Nebius eu-north1, 2026-08-15. Harness run
`h100-widthncu-eval-20260815-013326`, vortex rev `2d909147f`. Four captures, all
**CAPTURE-VERIFIED** and **WIDTH-PASS-OK**: FineWeb `text` and Wikipedia `text`, each under
`split8read` and the stride-16 `onpair_shmem_4tpt` — the same four cells as
`b300-widthncu-eval` and `a100-widthncu-eval`, so the legs are directly comparable.

split8read relative to stride-16:

| column | wavefronts | sectors | L1 hit% |
|---|---|---|---|
| FineWeb `text` | 0.767 | 1.002 | 89.0 -> 90.9 |
| Wikipedia `text` | 0.784 | 1.004 | 89.3 -> 90.9 |

Indistinguishable from the B300 (0.767 / 0.780) and the A100 (0.770 / 0.775). Wavefronts fall
about a quarter, sector count is flat to within half a percent, and the hit rate moves under
two points — far too little to explain the drop by residency, which is the argument the
isolation exists to make.

The `*_width.csv` files come from an explicit `--metrics` pass (`SHDICT_NCU_WIDTH=1`), kept
separate from the `--set full` capture so that every previously committed result stays
comparable. See `a100-widthncu-eval/README.md` for why that pass exists.
