# b300-regen-corpus-20260906 — the sidecar-regeneration penalty on the current corpus

Re-derives the cost of regenerating the offset sidecar at decode time (OP2) instead of storing it
(OP4), on the fifteen columns Table 1 actually reports, at both code widths, and at the shipped
coarsening as well as the one the published number used.

- **Box:** NVIDIA B300 SXM6 AC, driver 580.159.04, Nebius uk-south1 preemptible. Clocks boost
  (headline convention). See `gpu.csv`.
- **Rev:** `142e250a1` on `mp/onpair-seed-corpus-loaders` (adds `op_gpu_regen_grid.cu`).
- **Run:** one attempt, ~70 min, no preemption. **150/150 cells validated byte-exact** — every
  binary exits non-zero unless both the regenerated offsets and the decoded bytes match a host
  reference, so an unvalidated row is not a measurement and the reducer drops it.

## Why this leg exists

`results/b300-campaign-0717/op_gpu_regen.jsonl` is where the paper's "+15–19%" comes from, and it
can no longer carry that claim.

**The corpus moved.** It measured thirteen columns. Four are still in Table 1 by name
(ClickBench `URL`, TPC-H `l_comment` / `ps_comment` / `l_shipinstruct`) and none by content — its
TPC-H cells are `tpch-sf10` while the current corpus uses sf15/sf45/sf263. The other nine (six
dbtext, a synthetic URL corpus, older FineWeb/Wikipedia samples) were retired. No Loghub column
was ever measured, and Loghub `Windows` is the paper's headline.

**The basis was undeclared.** Its cells are **OnPair-16**, and the file carries no `bits` field.
`ONPAIR_DUMP_E2E` is last-writer-wins and that campaign swept bits 12 and 16, so the dump it
measured was the last cell written. This leg confirms it by reproduction:

| ClickBench `URL` | tokens | decode | penalty |
|---|---|---|---|
| committed `b300-campaign-0717` | 116,612,547 | 1009.5 GB/s | 17.5% |
| **here, OnPair-16** | 116,713,512 | 1010.6 GB/s | **17.6%** |
| here, OnPair-12 | 213,263,632 | 811.5 GB/s | 20.8% |

Token count within 0.09%, decode within 0.1%, penalty within 0.1 pp. The box and the encode path
are therefore sound — what was wrong was the scope of the claim, not the earlier measurement.

**And it was a K=4 number.** `op_gpu_regen.cu` includes `onpair_shmem_4tpt_split8read`, whose batch
is hardcoded at 128 codes, so `-DTOK_PER_BATCH_OVERRIDE=192` can only time regeneration alone (its
own header says so; `runs/b300-regen-gran`, 2026-08-25, measured that alone: −14.7%). The paper
recommends K=6. The penalty is a ratio and both terms move with K, so `op_gpu_regen_grid.cu`
decodes with the generated kernel whose batch matches the granularity.

## Result

**K=6 shipped: 15.1% to 33.4%, median 19.4%** (n=30). K=4 control: 14.1% to 29.0%, median 18.6%.

The penalty tracks **mean token length**, r = −0.868 over all thirty cells:

| column | mean token | penalty |
|---|---|---|
| TPC-H `c_address` (−12) | 1.9 B | 33.4% |
| FineWeb2 Mandarin (−12) | 3.0 B | 30.6% |
| Wikipedia (−12) | 3.2 B | 30.0% |
| … | | |
| Loghub `Windows` (−16) | 12.1 B | 18.3% |
| TPC-H `ps_comment` (−16) | 12.7 B | 16.3% |

Regeneration reads every code and reduces one entry per batch, so its cost scales with token
*count*; decode scales with decoded *bytes*. A three-byte-token column therefore pays roughly three
times the scan per decoded byte that a ten-byte one does. This is the mean-token-length axis
Section 4.2 already uses for decode rate, running the other way. The same mechanism explains the
code-width split: OnPair-12 needs ~1.8× more codes for the same bytes, and every column's −12
penalty exceeds its −16 penalty except `l_shipinstruct`, whose two configurations are identical
(five codes, one dictionary).

The old caveat about launch-bound columns does not apply here: every column is a 1 GB sample and
throughput-bound, so nothing is excluded. K=6 is **not** uniformly cheaper than K=4 — it wins on
most cells but loses on the short-token ones, worst at ClickBench `URL` −12 (24.4% against 20.8%).

## Files

| File | Contents |
|---|---|
| `regen_grid.jsonl` (150) | one row per (column, bits, variant); `op2` holds the full record including per-iteration ns arrays, `offsets_ok`, `decode_ok`, `k`, `low_plane_bytes`, `dict_size` |
| `run-results.md` | the box's own summary, written by `jobs/onpair-regen-corpus.sh` |
| `percell_json.tar.gz` | the 150 raw per-variant JSONs, as the binaries emitted them |
| `builds.txt`, `gpu.csv` | the five nvcc targets, and the device/clock state |
| `logs/*.runlog.gz` | per-cell `run.py` materialize logs |

**Variants.** `ctl_k4` is `op_gpu_regen.cu` unchanged (4tpt_split8read at 128 codes) — the July
basis. `k{4,6}_w{8,16}` are `op_gpu_regen_grid.cu` against `onpair_dg_k{4,6}_t256_b4` at each low-
plane width. Both widths are measured because the shipped selector picks W from the dictionary's
length profile; the reducer takes the faster one per column so the denominator is the shipped rate.

Re-derive with `uv run experiments/regen_penalty.py` (`--check` guards the range, the median and
the token-length relationship against drift; wired into `make verify`).
