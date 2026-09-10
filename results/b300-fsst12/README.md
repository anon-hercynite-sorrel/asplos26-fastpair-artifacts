# `b300-fsst12` — FSST-12 decoded by the shipped FastPair kernels

B300 SXM6 (sm_103), Nebius uk-south1, vortex rev `2d909147f` (branch `mp/fsst12-bench`).
Two harness runs, both at that rev, contribute to this directory:

- `b300-fsst12-ncu-20260812-191207` (2026-08-12) — the five HuggingFace text columns.
- `b300-fsst12-recover-20260813-222109` (2026-08-13) — ClickBench, TPC-H, synthetic URL,
  imported in commit `0f7bcc6`.

Do **not** import `b300-fsst12-preempt-20260812-101333`, which covers the same non-HF
datasets: it predates the ratio fix, so its `mem_ratio` values are the broken pre-fix ones
(ClickBench URL 1.77 where the correct value is 2.08) and it has no
`mem_ratio_container_matched` field at all.

FSST-12 normalized into FastPair's decode ABI on the host (dense 12-bit codes unpacked to
`u16`, 8-byte symbols widened to 16-byte cells, per-code length table supplied) and decoded
by the **unmodified** shipped kernels. `fsst12_summary_*.json` are the FSST-12 cells;
`onpair_ref_*.json` are OnPair cells measured in the **same run on the same box**, so the two
codecs are compared without crossing sends.

- 46 unique FSST-12 cells, all reporting `verified: true` (byte-exact against the CPU
  reference). `run_cell_fsst12` aborts a cell that fails validation rather than emitting a rate.
- **Two ratio fields.** `mem_ratio` is NATIVE: codes in FSST-12's own fixed 12-bit packing.
  `mem_ratio_container_matched` measures the code stream through the instrument OnPair's codes
  go through (BtrBlocks over a `u16` array). Use the container-matched figure for
  codec-vs-codec claims against OnPair-in-Vortex.
- **The two bases agree on the evaluated text columns, and the divergence is not simply
  cardinality.** They are equal to two decimals on the five real text columns the paper
  evaluates (`fineweb/text` 1.84 and `wikipedia/text` 1.83 on either basis), which is why the
  basis choice moves no reported number. They separate wherever BtrBlocks can compress the code
  stream further than a fixed twelve bits: the generated TPC-H columns diverge 1.2 to 1.3x
  **despite high cardinality** (`p_name`, 2.0M distinct, is 2.59 native vs 3.47 matched), and
  low-cardinality columns diverge further still -- `l_shipinstruct` (4 distinct) 3.38 vs 11.39,
  `l_linestatus` (2 distinct) 0.50 vs 8.00, and at the degenerate end `fineweb/language`
  (1 distinct) 1.00 vs 905.51. Any summary bound has to name the column set it covers.
  `experiments/validate.py` asserts both the agreement and the divergence.
- **Filenames are not scopes.** `run.py` writes one `summary.json` per invocation and the job
  snapshots it per dataset, so a file named for one dataset can contain cells for others. Key
  on each cell's own `dataset_id` / `column` / `bits` / `codec`.
- **One duplicated record, byte-identical.** `synthetic/url` appears in both
  `fsst12_summary_synthetic.json` and `fsst12_summary_lship.json`: `lship` does not resolve as
  a dataset alias in this job (its column lands under `tpch-sf10`), and the failed snapshot
  captured the preceding invocation's `summary.json`. The two records match field for field,
  and `common.py:cell()` returns the first match, so nothing double-counts — but a consumer
  that aggregates must key on `dataset_id`/`column`/`bits`/`codec` rather than count records.
  47 records, 46 unique cells.
- `codec` is `"fsst12"` or `"onpair"`. `figures/common.py:cell()` takes a `codec=` argument;
  records written before FSST-12 existed carry no `codec` key and default to OnPair.
