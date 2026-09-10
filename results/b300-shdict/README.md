# `b300-shdict` — staged-dictionary counterfactual

Does staging the dictionary in shared memory, which is GSST's central design move, help at
OnPair dictionary scale? Answers the question an external reviewer put to the preprint on
2026-07-27: *would a GSST variant adapted to OnPair match or surpass FastPair, making the
gains purely OnPair's format?*

**Answer on this box: no, and by the widest margin of any chip we tested.** Every staging
variant loses to the shipped L1-served gather on every column at every bit width where staging
is possible at all, and above FastPair-12 it stops being possible.

- Box: NVIDIA B300 SXM6 (Nebius, uk-south1, preemptible). Per-block shared-memory limit 227 KB.
- Rev `9b4714c2a` (the revision this leg ran at). **No kernel
  changes:** all three staging variants were already registered `KernelVariant`s.
- Protocol as the GPU decode matrix: 1 GB single chunk, 100 timed iterations after two
  warm-ups, min-of-100, device-resident inputs, `--gpu-validate` byte-exactness on every
  reported cell.
- Sweep: 4 columns (ClickBench `URL`, TPC-H `l_comment`/`ps_comment`, FineWeb `text`)
  x bits 12/14/16. Landed on attempt 1 despite the preemptible window.

This leg was owed from 2026-07-27, when uk-south1 B300 capacity went into scheduled
maintenance; it was collected 2026-08-04 and completes the counterfactual to four
architectures.

## Result on this chip

Best staging variant per cell, against the best byte-exact non-staging kernel:

| bits | best case | worst case | wins |
|---|---|---|---|
| 12 | −20.3% (`ps_comment`, padded) | −45.1% (FineWeb `text`, padded) | 0 |
| 14 | −55.7% (`ps_comment`) | −65.5% (FineWeb `text`) | 0 |
| 16 | staging impossible (table exceeds 227 KB) | | — |

The padded 16-byte layout is the best of the three on every B300 cell, matching the H100 and
differing from the A100 (stride-8) and the L40S (packed). That is why the paper compares
best-staging-variant-per-cell rather than any single layout.

The B300 being the harshest chip for staging is the direction the argument predicts: the faster
the L1 pipe the shipped gather is riding, the more there is to lose by leaving it.

## The three staging variants

| variant | dictionary layout in shared | shared bytes at bits12 / 14 / 16 |
|---|---|---|
| `onpair_shmem_4tpt_shdict8` | stride-8 `dict_s8`, >8 B tail from global | 52 / 160 / 592 KB |
| `onpair_shmem_4tpt_pdict` | padded 16 B/entry, persistent grid | 84 / 288 / 1024 KB |
| `onpair_shmem_4tpt_vdict` | variable-length packed, persistent grid | ~34 KB / grows / ~490 KB |

`applicable: false` in a summary means the variant's shared request exceeded the cap, so it
never launched. **That is a result, not a gap**: it is the capacity boundary, and the bench
records the byte arithmetic in its inapplicability reason. Caps: `pdict`/`vdict` are gated at
100 KB and `shdict8` at 224 KB by the harness, chosen so resident blocks per SM stay feasible;
these are design-sanity limits, **not** hardware maxima. Only the bits16 verdict rests on
hardware, where 592 KB to 1 MB exceeds even the 227 KB limit of the largest chip.

## Consumed by

`figures/extract_shdict.py` (also writes `results/shdict_summary.csv`). Backs the
staged-dictionary subsection of the paper's microbenchmarks section and the GSST paragraph
of related work.
