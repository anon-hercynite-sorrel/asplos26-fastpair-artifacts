# Results

Recorded measurements and reduced data used by the analysis scripts. The JSON
files include per-kernel results and iteration timings.

[MANIFEST.md](../experiments/MANIFEST.md) records each capture's hardware, revision,
configuration, and use in the evaluation.
[METHODOLOGY.md](../experiments/METHODOLOGY.md) defines the reductions.

## Result directories

1. **Legs the paper reads** — the `suite-*` family, `token-freqdist-corpus/`, and parts of
   `b300/`. `make analyze` reduces these into the figures and numbers.
2. **Pipeline figure evidence** — `pipes-boost-20260909/` contains the timing and
   counter records checked and reduced by `make analyze` for `fig:pipes`.
3. **Workflow validation** — [b300-validation-20260910/](b300-validation-20260910/README.md)
   contains one Windows OnPair-12 execution of the published GPU workflows.
4. **Supporting Nsight Compute captures** — `*-ncu-v2/`, `*-pipesncu/`, `*-splitncu/`, `*-shdict*/`,
   `*-widthncu-eval/`. `make analyze` never opens them; it reads the reduced CSVs at the top of
   `results/`. They are here to reproduce the CSV reductions.

## The legs the paper reads

| Leg | Rev | What it is |
|---|---|---|
| `suite-paper-20260821/{a100,b300,h100,l40s}` | `94905b572` | Primary throughput campaign. Declared in `figures/suite.py` as `PAPER_SUITE`; every figure not given an explicit suite id reads it. Fifteen columns x {OnPair-12, OnPair-16, FSST-12} x five clock states, plus the Decompression Engine and software-Zstd stages. |
| `suite-rtxpro-20260823` | `94905b572` | RTX PRO 6000-SE measurements, using the same revision, seed and corpus as the primary leg. |
| `suite-comparators-20260827` | `876c062b2` | `COMPARATOR_SUITE`. Re-measures three baselines that the primary leg measured over a narrower space. OnPair still comes from the primary leg; the control measurement supporting this combination is described in that leg's README. |
| `suite-flat-20260830` | `876c062b2` | `FLAT_SUITE`. Payload-only DE/gANS/Bitcomp measurements and the Zstd frame sweep. Zstd stores a u32 length per value; its rate numerator counts payload bytes. |
| `suite-baselines-20260822` | `94905b572` | The software-baseline leg. |
| `suite-hoist0-20260823`, `suite-h0probe-20260823`, `suite-residency-20260823` | `94905b572` | Narrow control probes, a few cells each, read for a single assertion apiece. |
| `b300/onpair_nvcomp_hw.json` and its summaries | `62336963e` | The earlier B300 leg, still read by `fig:gatherwidth` and several `validate.py` checks. **On the retired corpus** -- see the corpus note below. |
| `token-freqdist-corpus/` | `onpair` 0.0.4 | Dictionary read-frequency distributions. Backs `fig:tokendist`, declared in the appendix (`A_dataanalysis.tex`), which is currently not compiled into `main.tex`. |
| `b300-regen-corpus-20260906/` | see MANIFEST | The sidecar-regeneration penalty on the current corpus, all fifteen columns at both code widths. Re-derived by `experiments/regen_penalty.py`. |
| `b300-offtrade/`, `b300-fusedstall/`, `resource-probe-20260818/` | see MANIFEST | Supporting captures used by individual numerical checks. |

Reduced data files at the top of `results/`:

| File | Reduced from | Backs |
|---|---|---|
| `ncu-costsurface-pipes.csv` | `{a100,l40s,h100,b300,rtxpro}-pipesncu/` | Supporting captures: five devices, Loghub Windows + ClickBench URL x b12/b16, floating clocks. `fig:pipes` uses `pipes-boost-20260909/`. |
| `ncu-costsurface-v2.csv` | `{a100,l40s,h100,b300}-ncu-v2/` | The shipped-kernel cost surface, seven columns. |
| `ncu-stalls-v2.csv` | `{a100,l40s,h100,b300}-ncu-v2/` | The warp-stall composition. |
| `shdict_summary.csv` | `*-shdict*/` | The shared-dictionary microbenchmark. |
| `paper-claims.json`, `token-length-hist.json` | see MANIFEST | The claim macros and the token-length distribution. |

`ncu-costsurface-pipes.csv` and `ncu-costsurface-v2.csv` come from different harness
revisions and corpora. Comparisons between them establish ordering only; their
numerical ranges must be kept separate.

## Capture conditions

The supporting A100 cost-surface data combines profiling and timing from two
instances of the same GPU model. The `pipes-boost-20260909/` capture has its own
paired timing anchors and counter records; see the [pipes protocol](../experiments/pipes/README.md).

Each suite leg records its own state in `clock-state.txt` (staged revision, training and
kernel-order seeds, stage list, clock inventory, driver, power limits, memory pin),
`device_properties.json`, and `campaign_targets.txt` (the column inventory). Older legs carry
`run-env.txt` instead.

## The corpus

Fifteen columns, ten real-world and five generated; the list is in the top-level README and,
authoritatively, in each leg's own `campaign_targets.txt`. It is mirrored in `figures/suite.py` as
`REAL` and `GEN`.

The paper reports generated columns separately because an FSST-family trainer and a value
generator both build a fixed table of strings, and where the two coincide the codec stops
compressing strings and becomes an index into the generator's own table. TPC-H scale factors
differ per column (SF 263, 15, 45) so each yields a comparable byte volume.

### An older corpus is still present

`b300/` and `figures/common.py`'s `COLS` are keyed on an earlier, smaller corpus — `book-reviews`,
`amazon-*`, a synthetic URL column, TPC-H at SF10 — none of which is in the paper. A few
`validate.py` checks still read it. Check which corpus a leg carries before comparing any number
here against the manuscript.

## Not in the paper

`experiments/bench/cpu` and `experiments/bench/iaa` back no result in the paper — a CPU decode
sweep, an Intel IAA comparison and an end-to-end decode-then-scan, none of which the manuscript
contains. Their source code is included; their measurement legs are not committed.

## Schema

A suite leg is `results/suite-<id>/<chip>/`, read by `figures/suite.py`. Per chip:
`campaign_targets.txt` (the inventory), `clock-state.txt`, `device_properties.json`,
`suite-complete.txt` (the stage-completion record), `materialize_summary_<label>.json` (the
encode, carrying a sha256 per `.vortex` file), `sweep_summary_<label>_<clock>.json` (the decode
sweep), `zstd_summary_<label>.json`, `fsst12_summary_<label>.json`, `onpair_nvcomp_hw.json` (the
DE), and `kernel_resources.jsonl` / `kernel_ptxas.txt` (per-kernel register and shared-memory
footprint).

Definitions used by `figures/suite.py`:

- **rate** -- `decoded_bytes / min(decode_ns_iters)` for the shipped selector
  (`gpu.auto_kernel`), in GB/s. Bytes per nanosecond is exactly GB/s.
- **configured rate** -- `best_rate_gb_s()` selects the highest rate among applicable,
  byte-verified kernels in `gpu.kernels`, including generated configurations.
- **tokens** -- `gpu.distinct_codes`, how many distinct codes appear in the encoded column.
- **len** -- `sample_bytes / (gpu.compressed_bytes / 2)`, the token-weighted mean decoded bytes
  per code. Not `gpu.dict_mean_len`, which is unweighted over dictionary *entries* and runs about
  25% higher.
- **ratio** -- `sample_bytes / on_disk_bytes`, at rest: string bytes in, against the stored
  representation including bit-packed codes, dictionary and offset sidecar.
  `gpu.compressed_bytes` instead measures the in-memory unpacked codes.
- **le8** -- `gpu.frac_le8`, the share of decoded codes whose token is eight bytes or fewer.

The pre-suite legs use the older, flatter layout that `figures/common.py` reads:
`results/<gpu>/onpair_summary_<dataset>.json`, an array of cells keyed by `(column, bits)`. Its
`gpu` object carries `best_kernel` / `best_decode_gib_s` (best over the whole family),
`auto_kernel` / `auto_decode_gib_s` (what the shipped selector picks), and `kernels[]` (every
kernel timed, with the raw per-iteration timings, `applicable`, and `verified`). The figures use
`common.best_shipped()`, which excludes any `*ablate*` instrumentation build and any kernel that
failed byte-validation.
