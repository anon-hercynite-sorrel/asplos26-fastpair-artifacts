# `l40s-shdict` — staged-dictionary counterfactual

Does staging the dictionary in shared memory, which is GSST's central design move, help at
OnPair dictionary scale? Answers the question an external reviewer put to the preprint on
2026-07-27: *would a GSST variant adapted to OnPair match or surpass FastPair, making the
gains purely OnPair's format?*

**Answer on this box: no, and this is the friendliest box for staging.** The L40S is the
off-regime chip where no pipe saturates, so removing L1 pressure ought to help most here, and
the losses are indeed the smallest measured (9.8 to 50.4%). Staging still never wins. Every staging variant loses to the shipped L1-served gather on
every column at every bit width where staging is possible at all, and above FastPair-12 it
stops being possible.

- Box: NVIDIA L40S 48GB, Ada, GDDR6 (Nebius eu-north1, PREEMPTIBLE: on-demand L40S quota in that region is exhausted). Per-block shared-memory limit ~100 KB (Ada).
- Rev `9b4714c2a` (the revision this leg ran at). **No kernel
  changes:** all three staging variants were already registered `KernelVariant`s.
- Protocol as the GPU decode matrix: 1 GB single chunk, 100 timed iterations after two
  warm-ups, min-of-100, device-resident inputs, `--gpu-validate` byte-exactness on every
  reported cell.
- Sweep: 4 columns (ClickBench `URL`, TPC-H `l_comment`/`ps_comment`, FineWeb `text`)
  x bits 12/16. **bits14 is deliberately absent**: the stride-8 layout needs 164 KB there,
above Ada's ~100 KB per-block hardware maximum, and because run.py sweeps all bit widths in
one invocation per column a hard launch failure would have taken bits12 and bits16 with it.
That verdict is arithmetic, not measured.

## The three staging variants

| variant | dictionary layout in shared | shared bytes at bits12 / 14 / 16 |
|---|---|---|
| `onpair_shmem_4tpt_shdict8` | stride-8 `dict_s8`, >8 B tail from global | 52 / 160 / 592 KB |
| `onpair_shmem_4tpt_pdict` | padded 16 B/entry, persistent grid | 84 / 288 / 1024 KB |
| `onpair_shmem_4tpt_vdict` | variable-length packed, persistent grid | ~34 KB / grows / ~490 KB |

`applicable: false` in a summary means the variant's shared request exceeded the cap, so it
never launched. **That is a result, not a gap**: it is the capacity boundary, and the bench
records the byte arithmetic in its inapplicability reason. Caps: `pdict`/`vdict` are gated
at 100 KB and `shdict8` at 224 KB by the harness, chosen so resident blocks per SM stay
feasible; these are design-sanity limits, **not** hardware maxima. Only the bits16 verdict
rests on hardware, where 592 KB to 1 MB exceeds even the 227 KB limit of the largest chip.

## Consumed by

`figures/extract_shdict.py` (also writes `results/shdict_summary.csv`). Backs the
staged-dictionary subsection of the paper's microbenchmarks section and the GSST paragraph
of related work.
