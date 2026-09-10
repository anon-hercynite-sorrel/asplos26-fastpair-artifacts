# suite-comparators-20260827 — the comparator re-measurement

B300 SXM6, rev `876c062b2e7cc69729339e0c1f1829cfdec0fe78`, boost clocks, memory clock pinned,
training seed 20260819, fifteen columns, 1 GB sample, 1000 MB chunk. Byte-exactness verified on
every reported cell.

## Why this leg exists

Three comparators were measured over a narrower space than we gave ourselves, all found by an
artifact-first audit on 2026-08-26. None of the three changes our own configuration space; all
three can only move a baseline up.

| what | before | here |
|---|---|---|
| FSST-12 kernels | 19 (`--gpu-kernels production`) | 607 (`packed-grid`), the set OnPair gets |
| DE chunk sizes | 5, optimum at the largest on 15/15 columns | 7, adding 1 and 2 MiB |
| Zstd levels | −10, 1, 3 | −10, 1, 3, 9, 19 |
| DE input | flat concatenation, no row structure | u32-length-framed records |

## What is in here

- `fsst12_summary_*_boost.json` — FSST-12 at `packed-grid`. **This is the comparable basis** and is
  what the figures read.
- `production-basis/fsst12_summary_*.json` — the same fifteen columns at 19 kernels, kept as the
  control described below. Deliberately in a subdirectory: two bases under names matching
  `fsst12_summary_*_boost.json` in one directory would be read as duplicate cells for the same
  column, which is the class of defect this whole leg answers.
- `onpair_nvcomp_hw.json` — the DE over 7 chunk sizes, framed.
- `onpair_nvcomp_hw_5chunk.json` — the DE over the historical 5, framed. Isolates the sweep width
  from the framing.
- `zstd_summary_*_boost.json` — Zstd at five levels.
- `onpair_offset_cost.jsonl` — the output-position sidecar at 192, 128 and 32 codes per entry, per
  chunk. 30 cells x 3 granularities.
- `onpair_child_bytes.jsonl` — the stored bytes of each OnPair child (codes, row offsets,
  dictionary offsets, token lengths, dictionary) per chunk, so any denominator can be recomputed
  rather than assumed.

**No OnPair GPU cells.** Stages were `MATERIALIZE DE FSST`; there is no `GRID` arm here, so OnPair
rates still come from `suite-paper-20260821`.

## The control that licenses mixing the two legs

Mixing legs needs more than an assertion that the revisions are close, so it was measured. Both
legs ran FSST-12 at the identical 19 production kernels on the identical fifteen columns, differing
only in revision (`94905b572` there, `876c062b2` here):

    spread  -0.65% to +0.29%,  median -0.15%,  n = 15

That is inside the B300's documented split-half noise floor (0.82% p99), and the kernel diff between
the two revisions is *additional* `dh_k8` variants rather than edits to existing kernels. So this
leg's FSST-12 and DE numbers are comparable with `suite-paper-20260821`'s OnPair numbers, and
`figures/suite.py` reads them together on that basis. Re-run the control before trusting the pairing
after any further kernel change.

## Results

FSST-12 at the full kernel set, against the same columns at 19 kernels: **−0.4% to +8.1%, median
+6.4%**. Only `c_address` is flat, which is the degenerate random-character column. Loghub
`Windows`, the column §4.5 quotes, goes 1324.7 → 1405.8 GB/s.

The DE's optimum moves above 512 KiB on 10 of 15 columns, so the old five-size sweep was reporting a
boundary rather than an optimum — but the rate gain is small: +0.1% to +2.5%, median +0.7%, with
three columns marginally slower. On Loghub `Windows` the two effects separate as framing −3.8%
(647 flat → 622.6 framed, five sizes) and sweep width +2.2% (622.6 → 636.0).

Sidecar at the shipped 192 codes per entry: 0.37–0.45% of the stored column, against 0.51% at 128
and 1.7–2.2% at 32. Not linear in the granularity, which is why the granularity is recorded on every
row.
