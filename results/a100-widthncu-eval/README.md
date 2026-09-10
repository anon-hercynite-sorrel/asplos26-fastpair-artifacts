# `a100-widthncu-eval` — the access-width isolation on the A100, COMPLETE

A100-SXM4 40GB (sm_80), GCP us-central1-a, 2026-08-15. Harness run
`a100-widthncu2-20260815-003637`, vortex rev `2d909147f`. Four captures, all
**CAPTURE-VERIFIED** and all **WIDTH-PASS-OK**: FineWeb `text` and Wikipedia `text`, each
under `split8read` and the stride-16 `onpair_shmem_4tpt` — the same four cells as
`b300-widthncu-eval`, so the two legs are directly comparable.

## The counters are collectable on sm_80; `--set full` just omits them

The width isolation rests on LSU **wavefronts** falling while **sector** count stays flat:
that pair is what separates "each access is narrower" from "the table became more
cache-resident". An earlier version of this directory could not carry that result, because
`--set full` does not include `l1tex__data_pipe_lsu_wavefronts` or `l1tex__t_sectors` on
sm_80 — and `results/a100-shdict-ncu`, captured months earlier the same way, is missing them
too, so the gap looked architectural.

It is not. Both counters exist on this chip and are collected by asking for them by name.
`jobs/onpair-shdict-ncu.sh` now takes a second, explicit `--metrics` pass under
`SHDICT_NCU_WIDTH=1`, producing the `*_width.csv` files here. The pass is deliberately
SEPARATE from the `--set full` capture: folding the metrics into that invocation would change
the capture every previously committed result was produced by, and those are what the paper's
other chips are measured on. The census records `WIDTH-PASS-OK` per cell, and the job treats
an empty width CSV as a failure rather than as evidence the counters are absent.

## split8read relative to stride-16

| column | wavefronts | sectors | L1 hit% | SM cycles |
|---|---|---|---|---|
| FineWeb `text` | **0.770** | 1.004 | 87.6 -> 90.2 | 0.903 |
| Wikipedia `text` | **0.775** | 1.005 | 87.9 -> 90.3 | 0.904 |

The same four cells on the B300 (`b300-widthncu-eval`):

| column | wavefronts | sectors | L1 hit% | SM cycles |
|---|---|---|---|---|
| FineWeb `text` | 0.767 | 1.002 | 89.0 -> 90.9 | 0.893 |
| Wikipedia `text` | 0.780 | 1.004 | 89.1 -> 91.0 | 0.903 |

Every quantity agrees with the B300 to within a point: wavefronts fall by about a quarter,
sector count is flat to within half a percent, the hit rate moves under three points, and
decode time falls about a tenth. A hit-rate move that small cannot produce a wavefront
reduction that large, which is the argument the isolation exists to make.

**The mechanism now holds on four chips**, and on the evaluated columns rather than only on
the ClickBench `MobilePhoneModel` diagnostic: B300, H100 and L40S from the earlier captures,
and the A100 here — the oldest measured generation, the narrowest L1 headroom, and the one
chip where FSST-12 decodes faster than OnPair-12 on every text column.

Scope note, so this is not over-read: these captures isolate `split8read` against the
stride-16 gather. They do not isolate why FSST-12 inverts on this chip specifically; §6 states
that as consistent with the access-width account rather than as isolated, because the four
chips differ in more than L1 headroom.

## Provenance

This directory previously held the 2026-08-14 run `a100-widthncu-20260814-014524`, which was
identical in configuration but lacked the width pass. It was replaced wholesale rather than
merged, so every file here comes from one session on one box; mixing `--set full` from one run
with `--metrics` from another would make the ratios cross-run without saying so.

An A100 GPU hardware-faulted mid-capture on 2026-08-13 (`nvidia-smi` reporting `ERR!`, every
later launch returning CUDA error 9). The capture-identity assertion in
`jobs/onpair-shdict-ncu.sh` marked all five post-fault captures CAPTURE-INVALID, so no bad
data entered then, and every capture here is `CAPTURE-VERIFIED` with its kernel name and
static shared memory recorded in the census.
