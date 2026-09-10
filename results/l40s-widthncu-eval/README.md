# `l40s-widthncu-eval` — the L40S moves the same way, but does NOT isolate width

L40S (sm_89, GDDR6), Nebius eu-north1, 2026-08-15. Harness run
`l40s-widthncu-eval-20260815-013327`, vortex rev `2d909147f`. Four captures, all
**CAPTURE-VERIFIED** and **WIDTH-PASS-OK**, same four cells as the other three chips.

## Read this before citing it alongside the HBM legs

split8read relative to stride-16, with the three HBM parts for contrast:

| chip | column | wavefronts | sectors | L1 hit% |
|---|---|---|---|---|
| **L40S** | FineWeb | **0.835** | 1.002 | **50.6 -> 58.4 (+7.8)** |
| **L40S** | Wikipedia | **0.845** | 1.004 | **52.3 -> 60.8 (+8.5)** |
| B300 | FineWeb | 0.767 | 1.002 | 89.0 -> 90.9 (+2.0) |
| H100 | FineWeb | 0.767 | 1.002 | 89.0 -> 90.9 (+2.0) |
| A100 | FineWeb | 0.770 | 1.004 | 87.6 -> 90.2 (+2.6) |

Two differences, and both matter.

1. **The wavefront reduction is smaller** — 0.84 rather than 0.77.
2. **The hit rate moves about eight points, not two.** On the HBM parts the isolation
   argument is that a sub-three-point residency gain cannot produce a 23% drop in accesses.
   On the L40S that argument does not hold: its L1 is the one the megabyte dictionary
   overruns worst (hit rate near 51% against 88-89%), so halving the hot table's footprint
   genuinely improves residency. Here the split buys width AND residency, and this capture
   does not separate them.

So the L40S corroborates the DIRECTION on a fourth architecture and a second memory
technology, and it is not an isolation. §5.3 states it that way.

## The elapsed-cycle counter disagrees with the timing runs here — do not use it as rate

`sm__cycles_elapsed.avg` gives split8read/stride-16 as 0.808 on FineWeb but **1.319** on
Wikipedia, i.e. slower. The committed timing data says the opposite and by a wide margin:
`results/l40s/onpair_summary_*.json` has split8read at **1.160x** on FineWeb and **1.765x**
on Wikipedia, the largest gain of any chip. The counter is not tracking wall-clock rate on
this part, and the paper's rates come from the timing runs, not from here. Use these captures
for wavefronts, sectors and hit rate only.

(The B300, H100 and A100 cycle ratios of 0.89-0.91 do agree with their measured 1.06-1.12x
rates, so this is specific to the L40S.)

## Why this capture exists at all

The earlier L40S captures had NO hit-rate counters — Ada exposes a different metric set under
`--set full`, and that gap is why the paper previously said the L40S carried the wavefront
counter but not the hit rate. The explicit `--metrics` pass (`SHDICT_NCU_WIDTH=1`) collects
both by name. The eight-point hit-rate move above is a fact that could not be seen before.
