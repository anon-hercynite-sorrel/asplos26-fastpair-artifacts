# MANIFEST — every result, where it came from, what consumes it

The authoritative result→provenance map. For each measurement artifact under `results/`:
the bench source, the code revision, the box, the run config, the reduction, and which
figure/number it backs. Reproduction methodology is in [`METHODOLOGY.md`](METHODOLOGY.md);
re-derivation of the headline numbers is automated in [`validate.py`](validate.py).

The kernels and the bench driver are in the companion repository,
[`fastpair-harness`](https://github.com/anon-hercynite-sorrel/fastpair-harness);
the standalone benches are snapshotted under [`bench/`](bench).

The revisions named per leg identify the source tree used for each measurement.
Configuration, input and clock records define the basis for comparisons between
legs; the companion harness provides the measurement drivers and kernels.

## Bounded workflow validation

[`results/b300-validation-20260910/`](../results/b300-validation-20260910/README.md)
records a Windows OnPair-12 execution on B300 with harness revision
`cc9fbc483f15ccc08e67ede79ee4f3198786f740`: configured grid, boost pipes,
shared-dictionary staging, sidecar persistence/regeneration, and integrated Zstd.
It includes raw timings and counter exports. `experiments/check_bounded.py`
checks these records; the paper figures use their separately listed captures.

## The suite legs (what the submitted paper reads)

The `suite-*` family is the current campaign generation and is what `make analyze` reduces into
every figure and number the paper prints. Layout is `results/suite-<id>/<chip>/`, read by
`figures/suite.py`; the column inventory is each leg's own `campaign_targets.txt`.

| Result | Box(es) | Rev | Config | Consumed by |
|---|---|---|---|---|
| `suite-paper-20260821/{a100,b300,h100,l40s}/` | A100, B300, H100, L40S | `94905b572` | **The primary leg** (`suite.py: PAPER_SUITE`). Fifteen columns × {OnPair-12, OnPair-16, FSST-12}, bits 12+16, 1000 MB chunks, 1 GB sample, 100 iters, byte-exact; stages MATERIALIZE / GRID / DE / ZSTD / FSST / LADDER; five clock states (boost, locked-max, 75/55/40%); training seed `20260819` | `fig:teaser`, `fig:perf_real`, `fig:perf_gen`, `fig:grid`, `fig:hoist`, `fig:gatherwidth`, `fig:lenpredict`, `fig:tokendist`; `tab:datasets` via `figures/tab_datasets_suite.py`; the Section 3–5 claim macros via `paper_claims.py`; the abstract's four literals via `check_abstract.py` |
| `suite-rtxpro-20260823/` | RTX PRO 6000-SE (GDDR7), GCP | `94905b572` | same corpus, seed and protocol; a separate leg because it was rented from a different provider | `fig:perf_gen` (the fifth chip) |
| `suite-comparators-20260827/` | B300 | `876c062b2` | re-measures three baselines that the primary leg measured over a narrower space; **no GRID arm**, so OnPair still comes from the primary leg. The pairing is licensed by a control, not asserted: both legs ran FSST-12 at an identical configuration and agree to a median −0.15% (n=15), inside the 0.82% p99 split-half noise floor | `fig:teaser`, `fig:perf_real`, `fig:lenpredict` |
| `suite-flat-20260830/` | B300 | `876c062b2` | flat DE/gANS/Bitcomp payload runs (`suite.py: FLAT_SUITE`), plus the Zstd frame sweep. Zstd retains a u32 length per value while its numerator counts payload; see `zstd/README.md` | `fig:teaser`, `fig:perf_real`, `fig:perf_gen` |
| `suite-baselines-20260822/` | B300 | `94905b572` | the software-baseline leg | `validate.py` / `paper_claims.py` |
| `suite-hoist0-20260823/` | B300 | `94905b572` | the $H=0$ no-hoist control, scoped to what `fig:hoist` reads | `fig:hoist` |
| `suite-h0probe-20260823/`, `suite-residency-20260823/` | B300 | `94905b572` | narrow probes: the hoist-zero question and observed residency / L1 hit rate under the $S$ sweep | a small number of `validate.py` assertions |
| `b300-regen-corpus-20260906/` | B300 | see that leg's README | the sidecar-regeneration penalty on the current corpus: all fifteen columns, both code widths, shipped $K=6$ and the $K=4$ control, both low-plane widths; 150/150 cells byte-exact | the §3 sidecar range (15.1–33.4%, median 19.4%), re-derived by `regen_penalty.py` |

Each suite leg records its own state in `clock-state.txt` (staged revision, training and
kernel-order seeds, stage list, clock inventory, driver, power limits, memory pin),
`device_properties.json`, and `suite-complete.txt` (the stage-completion record).

## GPU decode matrix (the evaluation)

> **THE "Consumed by" LABELS IN THIS SECTION ARE HISTORICAL.** `fig:payoff`, `fig:scaling`,
> `fig:sota` and `fig:stagecost` are figures the paper no longer prints; their generators are
> excluded from this release. The paper's throughput figures come from the suite legs above. Of
> this section's legs, only `b300/` is still read by anything live — `b300/onpair_nvcomp_hw.json`
> by a handful of checks — and it is on the retired ten-column corpus. The rows are kept as the
> provenance record for that data, not as a map of what the submission uses.


| Result | Box | Rev | Config | Reduction | Consumed by |
|---|---|---|---|---|---|
| `a100/onpair_summary_*.json` | A100-SXM4-40GB, Lambda, 2026-06-05 | fe4a84d65 (+gap-fill 550c3c3ca) | bits 12+16, 1000 MB chunk, 100 iters, kernel-only, `--gpu-validate` | best **shipped** kernel = decoded_bytes / min(decode_ns_iters) | `fig:payoff`, `fig:scaling`, GSST check |
| `l40s/onpair_summary_*.json` | L40S (Ada, GDDR6), Lambda, 2026-06-26 | 49174a3a6 lineage | same | same | `fig:payoff` (GDDR6 leg) |
| `h100/onpair_summary_*.json` | H100 80GB HBM3, Nebius eu-north1, 2026-06-08 | 550c3c3ca | `FAST=0` (adds software Zstd + naive ref), all 8 datasets | same | `fig:payoff`, `fig:scaling`, software multiple |
| `b300/onpair_summary_*.json` | B300 SXM6 (sm_103), Nebius, 2026-06-27 | 62336963e (gold) †| `FAST=0`, **unlocked/boost clocks** (headline), all datasets | same | `fig:payoff`, `fig:teaser`, `fig:scaling`, `fig:gatherwidth`, `fig:stagecost`, DE/software multiples — **the canonical GPU** |
| ~~`b300-locked/onpair_summary_*.json`~~ | B300 SXM6, Nebius, 2026-06-27 | 62336963e (gold) | `FAST=0`, **locked clocks** (tput mode), all datasets | same | **ARCHIVED 2026-09-08.** The suite legs carry five clock states per cell, which supersedes this pinned sibling. |
| ~~`b200/`~~, ~~`gh200/`~~ | B200 Nebius / GH200 Lambda | 550c3c3ca / fe4a84d65 | superseded | — | **ARCHIVED 2026-09-08.** B200 superseded by the B300's complete sweep; GH200 a redundant second Hopper within noise of the H100. |

† The 2026-06-27 **gold re-run** staged fork `62336963e` (gold bench + zero-perf kernel hardening;
decode kernels byte-identical to the 49174a3a6 lineage). `results/b300` is the **unlocked/boost**
headline; `results/b300-locked` was the clock-pinned sibling, now archived. DE rows in
`b300/onpair_nvcomp_hw.json` are from the same rev with the chunk-size sweep (best per column):
each column entry retains its full per-chunk sweep (32\,KiB–512\,KiB) in a `chunk_sweep` field, and
`best_decode_gib_s` is the max over it (the field `de_map()` reads).

## FSST-12 (the generality result, 2026-08-12/13)

FSST-12 normalized into FastPair's decode ABI on the host and decoded by the **unmodified**
shipped kernels. Each run also measures OnPair on the same box in the same session, so the
two codecs are never compared across sends. Every FSST-12 cell is byte-exact verified; the
cell aborts rather than reporting an unvalidated rate. Vortex rev `2d909147f`, branch
`mp/fsst12-bench`; FSST-12 encoder vendored in the harness (upstream `fsst-rs` @ `196a862`, which carries the 1 MB
training-budget fix, without which the 4096-symbol table trains to ~250 entries).

| Result | Box | Rev | Config | Reduction | Consumed by |
|---|---|---|---|---|---|
| `b300-fsst12/{fsst12_summary,onpair_ref}_*.json` | B300 SXM6, Nebius uk-south1, 2026-08-12 | 2d909147f | `--codec fsst12`, 1000 MB chunk, 100 iters, `--gpu-validate`; OnPair reference bits 12+16 | best byte-exact kernel = decoded_bytes / min(decode_ns_iters) | FSST-12 rate + ratio, §6 |
| `h100-fsst12/…` | H100 SXM, Nebius eu-north1, 2026-08-12 | same | same | same | cross-arch FSST-12 |
| `l40s-fsst12/…` | L40S (Ada, GDDR6), Nebius eu-north1, 2026-08-12 | same | same | same | cross-arch FSST-12 (GDDR6 leg) |
| `a100-fsst12/…` | A100-SXM4 40GB, **GCP** us-central1-f, 2026-08-13 | same | same, NCU phase skipped | same | cross-arch FSST-12; the chip where FSST-12 **beats** OnPair-12 |
| `b300-fsst12/` (ClickBench, TPC-H, synthetic cells) | B300 SXM6, Nebius uk-south1, 2026-08-13 | same | recovery send: the non-HF datasets, which earlier runs measured but did not collect | same | `fig:compressibility` synthetic panel, `fig:sota` |

Two ratio fields per FSST-12 cell. `mem_ratio` is native (fixed 12-bit codes);
`mem_ratio_container_matched` measures the code stream through OnPair's own instrument
(BtrBlocks over `u16`). They agree to two decimals on the real text columns and diverge up to
3.3x at low cardinality. **Which one the paper reports is an open disclosure decision.**

## Split-vs-stride16 NCU (the access-width mechanism, 2026-08-12)

| Result | Box | Rev | Config | Reduction | Consumed by |
|---|---|---|---|---|---|
| `{b300,h100,l40s}-splitncu/splitncu_*_{details,raw}.csv` | B300 / H100 / L40S, Nebius, 2026-08-12 | 2d909147f | NCU `--set full`, 16 launches/cell, `split8read` **and** stride-16 `onpair_shmem_4tpt` on the SAME cell; H100 and L40S add `split4read` | `l1tex__data_pipe_lsu_wavefronts.avg` ratio | §5 access-width mechanism (`sec:dd:dict`) |

The pairing no earlier capture set had: every cost-surface capture profiled only the kernel
the selector chose, so no cell held both kernels. **Distinct from `*-shdict-ncu`**, whose
`pdict` baseline is the shared-memory staged dictionary, not the global stride-16 table.

| `b300-widthncu-eval/shdict_ncu_*_{details,raw}.csv` | B300 SXM6, Nebius uk-south1, 2026-08-13 | 2d909147f | NCU `--set full`, 16 launches/cell, `split8read` and stride-16 on FineWeb + Wikipedia (both EVALUATED columns) | `l1tex__data_pipe_lsu_wavefronts.avg` ratio | §5 access-width isolation, replacing the MobilePhoneModel diagnostic column |

## Hardware Decompression Engine (Blackwell-only)

| Result | Box | Rev | Config | Consumed by |
|---|---|---|---|---|
| `b300/onpair_nvcomp_hw.json` (16 cols) | B300, Nebius uk-south1, 2026-06-27 | 62336963e (gold) | `nvcomp_hw_bench.cu`, backend=HARDWARE, Deflate algo 5/0 + LZ4, **chunk-size sweep (best per column)**, fed the **identical** uncompressed bytes OnPair decodes | `fig:payoff`, `fig:teaser`, DE multiple (**2.4–4.6×**) |

Source: [`bench/gpu/nvcomp_hw_bench.cu`](bench/gpu/nvcomp_hw_bench.cu). DE is fixed-function
silicon, byte-identical B200/B300, so `de_map()` (in `figures/common.py`) sources it from B300.

## Sidecar and shared-dictionary reproduction packages

[sidecar/README.md](sidecar/README.md) records the sidecar persistence and
regeneration routes, source provenance and available evidence.
[staging/README.md](staging/README.md) documents the shared-dictionary variants
and their archived measurements. These entry points complement the historical
measurement records below; they do not replace or relabel those result legs.

## Pipeline characterization: current figure and historical captures

The submitted `fig:pipes` and `sec:eval:bound` use
`results/pipes-boost-20260909/`. Each GPU runs its best confirmed Windows
OnPair-12 configuration; the recommended configuration is retained as a control.
The selection, warmup, counter definitions and acceptance checks are documented in
[pipes/README.md](pipes/README.md). Regenerate and validate with:

```sh
python3 experiments/check_pipes.py --check
uv run figures/fig_pipes.py
```

| Result | Box(es) | Config | Consumed by |
|---|---|---|---|
| `pipes-boost-20260909/{evidence.tar.gz,accepted.json,directions.json}` | B300, H100, A100, RTX PRO, L40S; 2026-09-09; public harness `f6d81878715bf322a0917ada32bcf40adffbd3ef` | Windows OnPair-12, 561-candidate screen, two confirmation rounds; winner and recommendation, four NCU launches each; unlocked boost, application replay, no NCU clock/cache control; settled within-process warmup on A100/B300 | **Current `fig:pipes` and §5.2.** Five L1 bins and elapsed-normalized L1/L2/device-memory/SM utilization. `figures/pipes_data.py` reconstructs selection and reduction; `experiments/check_pipes.py` checks all five devices and forty accepted launches. |
| `ncu-costsurface-v2.csv` | L40S + H100 + B300 + A100, 2026-07-05 recapture, rev `ba16fad7f` | NCU `--set full`, exact per-cell kernel filter, sixteen launches/cell | **Historical supporting data, not the current pipes figure.** Source for the earlier 81–96% cost-surface description; retained checks are historical regression checks, not validation of the submitted figure. |
| `ncu-stalls-v2.csv` | same recapture | warp-stall shares, % of warp cycles per issued instruction | Historical stall evidence. `tab:stallmix` is no longer printed; its reference column came from the retired v1 base-kernel capture. |
| `{l40s,h100,b300,a100}-ncu-v2/ncu_costsurface_*_{details,raw}.csv` | per-architecture raw | `--set full`, sixteen launches/cell, mean | Source for the historical v2 CSVs through `figures/extract_costsurface.py` and `figures/extract_stalls.py`. |
| `ncu-costsurface-pipes.csv` | A100, L40S, H100, B300, RTX PRO; 2026-08-24, rev `dd2325b3f` | `--set full`, sixteen launches/cell, production-selector kernels, floating clocks | **Superseded figure cohort.** It produced the former 99% L1 / 12–43% device-memory HBM values and 80/79 and 70/76 GDDR pairs. These are not the revised figure's values. |
| `{a100,l40s,h100,b300,rtxpro}-pipesncu/ncu_costsurface_*_{details,raw}.csv` + logs + `clock-state.txt` | per-architecture raw; Windows + ClickBench URL × bits12/16 | Four cells per device, exact captured symbols verified | Source for historical `ncu-costsurface-pipes.csv`. |
| Retired `ncu-costsurface.csv` and `{b300,h100,l40s}-ncu/` | base reference kernel `onpair_u64` | Captured the first kernels because the original profile lacked an exact kernel filter | Removed from the tree on 2026-09-08. Source of the withdrawn per-chip L2/L1 split; no submitted figure uses it. Recoverable from repository history. |
| Retired `fig_roofline` / `fig_roofline_v2` | derived from historical profiles | Fitted prediction algebraically equivalent to measured rate divided by L1 utilization | Not printed or included in this release; not an independent measurement. |

The current reduction preserves ordinary shared loads, ordinary shared stores and
shared residual work separately. It partitions measured nonshared wavefronts by
direct LGDS command direction on H100/B300/RTX PRO and by an explicitly estimated
global tag-output direction ratio on A100/L40S. Missing counters remain missing.
All four companion bars come from the same accepted launches. The raw initial
A100 attempt is retained, but its stabilized follow-up is the selected cohort.
The new archive does not reinterpret or overwrite the older CSV schemas.

### Limits of the historical cost-surface captures

The following observations describe the July/August captures above, not the new
reviewer capture command:

1. The historical `COSTSURFACE` block in `jobs/onpair-bench.sh` ran before its
   `CLOCK_LOCK` block. July's `CLOCK_LOCK=1` therefore applied to the later
   throughput sweep, not the profiles. Older “locked recapture” names are not
   evidence that these profiles used locked clocks. Percentage-of-peak metrics
   do not by themselves establish equivalent clocks or stable boost; the new
   campaign checks observed profile clocks and uninstrumented timing anchors.
2. The historical job read the production selector's `gpu.auto_kernel`, rather
   than finding the best-performing kernel through the new confirmation screen.
   July's captures used `onpair_shmem_4tpt{,_split8read}` (block 512, static shared
   memory 33.28 KB/block), verified in 56/56 captures. August's symbols vary by
   device: Windows uses `onpair_shmem_4tpt_b128` on A100/H100,
   `onpair_shmem_4tpt_b128o12` on B300/RTX PRO and `onpair_shmem_2tpt` on L40S.
   ClickBench URL uses `onpair_decompress_6tpt` except for L40S's
   `onpair_shmem_2tpt`. Cross-wave differences therefore mix kernel and hardware
   operating-point differences; `figures/compare_costsurface_waves.py` reports
   the shared-cell deltas for inspection.

The old RTX PRO exports lack `dram__sectors_read/write.sum`.
`extract_costsurface.py` leaves `dram_rd` empty rather than treating a missing
read counter as zero. This device-memory direction field is unrelated to the
new figure's estimated L1 global-read/write split.

The original base-kernel A100 profile was collected later on GCP after counter
access was blocked on Lambda; its raw file was not included in `a100-ncu/`.
The v2 recapture contains committed raw data for all four architectures,
including A100. Historical v2 values (87–96% L1/TEX on the HBM devices, and no
saturated pipe on L40S) remain interpretable as measurements of that earlier
cohort, not as the revised §5.2 source.

## Drain ablation + targeted NCU captures (B300) — `results/b300-drain-e2e/`
> **ARCHIVED OUT OF THE TREE 2026-09-08.** Superseded, and it backs no figure or number the submitted paper prints. The provenance below is kept as the
> record of what was measured; the data itself is in the local retired-legs archive and in
> this repository's git history.


One locked-clock B300 session (SM pinned to 2032 MHz, Nebius, 2026-07-06; rev `ba16fad7f`;
run dir `~/agents/harness/runs/b300-drain-e2e-20260706-210827`). `RESULTS.md` in the dir is
the session digest; NCU captures are `--set full`, 16 launches/cell, exact `-k`,
CAPTURE-VERIFIED.

| Result | Config | Consumed by |
|---|---|---|
| `onpair_summary_{clickbench,lship,pscmt,synthetic}.json` (+ `ncu_*_ablate_nodrain_*` captures) | drain ablation: `onpair_shmem` / `_4tpt` / `_4tpt_ablate` / `_4tpt_ablate_nodrain` per cell, min-of-100, kernel-only. The `_ablate*` builds are **diagnostic, not shipped**; `_nodrain` is **not byte-exact** (validation fails by construction) | §5.3 drain sentence + §4.2 — drain = **10–13% of ablate-baseline runtime** across the 5 cells (17.5–20.5% vs plain 4tpt) |
| `ncu_clickbench_URL_b12_onpair_shmem_{details,raw}.csv` + `..._onpair_shmem_4tpt_{details,raw}.csv` | occupancy pair on ClickBench URL b12 | §4.3/§6.4 — 1tpt **89.3%** achieved occupancy @ 32 reg/thread vs 4tpt **45.4%** @ 56 reg (50% theoretical) |
| `ncu_dbtext_ps_comment_b12_onpair_shmem_4tpt_b128o12_*` (+ plain `_4tpt` sibling) | launch-bound capture: dbtext ps_comment b12 (dict-only column) | §6.4 — b128o12 launches **492 blocks**, **19.4%** achieved occupancy: the grid can't fill the chip |
| `toolkit_*` (PTX/SASS + diffs, `toolkit_versions.txt`) + `e2e_tk_*.json` | nvcc 12.8 vs 13.0: PTX + SASS (per-toolkit AOT and fixed-ptxas13.0 JIT analogue) + e2e timing on ClickBench URL b12 | §6.1 disclosure — SASS **differs** 12.8 vs 13.0; 13.0 is **+1.4%** decode (761.2 → 771.5 GB/s) |

## CPU decode sweep (the cross-stack story)
> **ARCHIVED OUT OF THE TREE 2026-09-08.** The CPU decode sweep is in neither version of the paper; the evaluation is GPU decode. The provenance below is kept as the
> record of what was measured; the data itself is in the local retired-legs archive and in
> this repository's git history.


| Result | Boxes | Source | Config | Consumed by |
|---|---|---|---|---|
| `cpu-sweep-4phys/cpu-sweep.json` (**gold**; `cpu-sweep/`, `-8phys/` are the older runs) | 10 AWS gens (AMD/Intel/Arm, DDR4/DDR5), bare-ish | [`bench/cpu/`](bench/cpu) @ 175f504 (`target-cpu=native`) | fixed-stride (`fat`) vs variable-stride (`entries`) decode, 256 MB working set, 1/4/8 phys cores, per-pass raw → min-derived | `fig:crossstack` (1 core, extended), CPU fat/entries **1.15× median / 1.63× max** (validate) |
| `cpu-bitsweep/cpu-bitsweep.json` | same fleet | same | dict bit-width 9→16 | `fig:bitsweep` |
| `cpu-sota/*.json` | same fleet | same | compression ratios (codec-independent) | `fig:compressibility`, `fig:cpufield` |
| `cpu-tma/*_raw.tar.gz` | bare-metal Intel Sapphire / AMD Genoa / Arm Graviton4 | [`bench/cpu/`](bench/cpu) under `perf stat --topdown` | `perf stat --topdown` + L2, fat vs entries, 1/4/8 threads | `fig:cputma` |

## IAA accelerator (the CPU analog of the GPU DE) — #29
> **ARCHIVED OUT OF THE TREE 2026-09-08.** The IAA comparison is in neither version of the paper, which does not mention IAA. The provenance below is kept as the
> record of what was measured; the data itself is in the local retired-legs archive and in
> this repository's git history.


| Result | Box | Source | Config | Consumed by |
|---|---|---|---|---|
| `iaa/iaa_aggregate_sapphire.txt` | GCP c3-standard-192-metal (Sapphire, 8 IAA engines), 2026-06-27 | [`bench/iaa/iaa_bench_mt.cpp`](bench/iaa/iaa_bench_mt.cpp) | all 8 engines, shared WQ 8×128, block_on_fault=1, **run as root**, mlock'd; 9 cols × threads {1..96}; min over ≥3 passes | IAA aggregate 28.9 GB/s geomean; `ANALYSIS.md` |
| `iaa/onpair_cpu_sapphire.json` | same box | [`bench/cpu/`](bench/cpu) | FastPair-CPU fat/entries, same columns | IAA comparison (FastPair 1-core 2.35× one engine; 8-core matches the block) |

Setup is reboot-requiring (intel_iommu scalable mode + idxd from `linux-modules-extra`); driven
by [`bench/iaa/iaa_drive.sh`](bench/iaa/iaa_drive.sh) + [`iaa_mt_setup_run.sh`](bench/iaa/iaa_mt_setup_run.sh).

## End-to-end decode→scan (the operator hand-off) — #28
> **ARCHIVED OUT OF THE TREE 2026-09-08.** The end-to-end result is not in the submitted paper, which mentions neither it nor a downstream operator hand-off. The provenance below is kept as the
> record of what was measured; the data itself is in the local retired-legs archive and in
> this repository's git history.


| Result | Box | Rev | Source | Consumed by |
|---|---|---|---|---|
| `e2e/e2e_{clickbench,synthetic}_url.json` | B300, Nebius uk-south1, 2026-06-27 | 6ee03c1d8 (49174a3a6 decode lineage + e2e bench) | [`bench/gpu/e2e_scan.cu`](bench/gpu/e2e_scan.cu) | §6.8 operator hand-off. ClickBench URL: decode 1007 GB/s, scan 4714 GB/s, e2e 827 GB/s (+22%), PCIe-decompressed/decode+scan **14.9×**, full pipeline vs CPU-decode baseline **70×**; needle unique (byte-exact). `ANALYSIS.md` |
| `e2e/sweep/sweep_*.json` (10 needles + `sweep_rare.json` anchor) | B300, Nebius uk-south1, 2026-06-27 | 6ee03c1d8 | [`bench/gpu/e2e_scan.cu`](bench/gpu/e2e_scan.cu), the same decoded ClickBench URL dump swept over needles rare→ubiquitous, min-of-200 | archived predicate-selectivity sweep (rare→ubiquitous needle), superseded in the paper by `fig:offtrade`; 3 `validate.py` cross-over checks |
| `b300-drain-e2e/ncu_e2e_scan_needle_{details,raw}.csv` (+ same-session `e2e_b300_clickbench_url_b12.json`) | B300, locked 2032 MHz, 2026-07-06 | ba16fad7f | NCU `--set full` on the `scan_needle` kernel (ClickBench URL b12 dump, repro-repo `e2e_scan.cu`) | §6.7 scan characterization — DRAM **42.8%** of peak, long_scoreboard **48.5%** of warp cycles, L1/TEX 21.0% |

`e2e_scan.cu` reuses the shipped split-read decode kernel + a rare-string scan; validated against
a CPU reference decode + match count. Inputs dumped from the encoder via `ONPAIR_DUMP_E2E` on the
decode path (the frozen harness fork; see its `benchmarks/onpair-bench/README.md` §3, end-to-end);
the dumps are stashed locally so a scan-kernel tweak re-runs in ~3 min (stage dump + nvcc + run).

## Offsets / materialization trade-off — `results/b300-offtrade/` (`fig:offtrade`, §6.8)

> **NOT IN THE SUBMITTED PAPER.** `fig:offtrade` is no longer printed and the five
> `validate.py` checks over this leg were removed on 2026-09-08. The data is retained in the
> tree because it is small and the trade-off is a likely reviewer question.


| Result | Box | Rev | Source | Consumed by |
|---|---|---|---|---|
| `b300-offtrade/run{1..4}_url.json` | B300 SXM6, Nebius uk-south1 (preemptible), 2026-07-21 | `9b4714c2a` (flattened; run revs `b0bc051d4` / `9afe81125` / `9b1ee137c` / `8305d35be`) | [`offsets_tradeoff.cu`](https://github.com/anon-hercynite-sorrel/fastpair-harness/blob/main/benchmarks/onpair-bench/offsets_tradeoff.cu) | **`fig:offtrade` (§6.8)** + 5 `validate.py` checks. ClickBench URL (12.25M rows) at FastPair-16, Q20 substring count under an incoming filter of selectivity `m`; four decode strategies (dense over stored offsets, regenerate-on-GPU OP2, late-materialization, early-materialization) relative to dense. Runs 1–3 supply the plotted m-grid (1.0→0.03); run4 adds the sub-0.03 reference tail. Every cell byte-exact + count==oracle; min-of-200. |

The offset-strategy trade-off measures what a pushed-down filter buys against the filter-agnostic
dense decode: dense stays cheapest to ~20% selectivity, early materialization wins below, and the
late-materialization prototype never wins. Driver: `offsets_tradeoff.cu` in the frozen harness
(`mp/fastpair`); the `m`-set is the `mlist` literal in the driver.

## FSST recipe port (the generality check) — `results/a100-fsst/`
> **ARCHIVED OUT OF THE TREE 2026-09-08.** Superseded by the FSST-12 legs and the suite `FSST` stage. The provenance below is kept as the
> record of what was measured; the data itself is in the local retired-legs archive and in
> this repository's git history.


| Result | Box | Rev | Config | Consumed by |
|---|---|---|---|---|
| `fsst_scan_tpch_{l_comment,l_shipinstruct}.json` | A100-SXM4-40GB, locked 1410 MHz, 2026-07-06 | branch `mp/fsst-recipe` @ `24719f925` (pushed to the fork) | naive `fsst.cu` vs recipe `fsst_4tpt.cu`, 100 iters, raw per-iteration ns retained, **byte-exact both** | §6.3 generality sentence + §5.2/§8 scope — recipe **327.7 GB/s** on TPC-H l_comment = **1.72×** GSST's published 191 (naive `fsst.cu` 138.6); l_shipinstruct **570.1** |
| `fastpair_summary_{tpch_lcomment,dbtext}.json` | same box, same run | same | shipped FastPair family on the same cells (incl. the bonus dbtext summary), GiB/s | same-chip FastPair reference for the FSST comparison |

**DISCLOSE:** the recipe port pre-stages a `group_in_off` side table (~539 MB on l_comment)
untimed, like the chunk offsets. `fsst_scan` reports decimal GB/s (decoded bytes / kernel s /
1e9), directly comparable to GSST's 191. Blob provenance: `fsstbin_manifest.txt`;
clocks/driver: `run-env.txt`.

## OP-cluster + fresh baselines (B300) — `results/b300-campaign-0717/`
> **ARCHIVED OUT OF THE TREE 2026-09-08.** The July campaign, superseded wholesale by `suite-paper-20260821`. Its regeneration cells are superseded specifically by `b300-regen-corpus-20260906`. The provenance below is kept as the
> record of what was measured; the data itself is in the local retired-legs archive and in
> this repository's git history.


One-session B300 campaign (Nebius uk-south1 preemptible, boost clocks) at rev `5e10231c5`
(`mp/fastpair`: registry `dump_columns.py` + `op_gpu_regen.cu` OP2 + `ONPAIR_OFFSET_COST`
hook). Value-ordered; the trailing chunk-size steelman was cut by the 3 h timeout (absent by design).
See the dir `README.md` for the full file table.

| Result | Experiment | Reduction | Headline / consumed by |
|---|---|---|---|
| `offset_cost.jsonl` | OP4 store: offset sidecar size + host gen time, per chunk (`ONPAIR_OFFSET_COST`) | per-chunk raw | stored **0.37–1.08%** of compressed (median ~0.6%); raw-u64 2.5–7.3% → the disclosed footprint-with-sidecar config |
| `op_gpu_regen.jsonl` | OP2 regen chunk_offsets on GPU (scan+CUB), byte-exact (`op_gpu_regen.cu`) | min-of-200 | **SUPERSEDED 2026-09-06 by `results/b300-regen-corpus-20260906`.** Reported +15–19%, but the cells are **OnPair-16** (no `bits` field; `ONPAIR_DUMP_E2E` is last-writer-wins and this campaign swept 12+16) at **K=4** only, on a corpus of which four columns survive by name and none by content (sf10 vs today's sf15/sf45/sf263), with no Loghub column at all. The new leg reproduces this file's ClickBench URL cell to 0.1 pp at OnPair-16, so the measurement was sound and only its scope was overstated. |
| `op1_row_decode.jsonl` †sep-run | OP1 row-partition decode: reuse free per-row code offsets + on-device output-offset scan, thread-per-row (`op1_row_decode.cu`, `ONPAIR_DUMP_OP1`) | min-of-200 | **13/13 byte-exact**; decode 24–321 GB/s (med 98) — wins small/uniform rows, craters on long text (fineweb/wiki ~25 @ 3–4.5 KB/row): the thread-per-row load-imbalance signature. †from run `b300-op1chunk` 2026-07-18 rev `7a408d961` |
| `e2e_v2.jsonl` | decode→in-HBM scan (rare needle) | min-of-200 | e2e ≈ decode + ~22% |
| `gans_bitcomp.jsonl` | nvCOMP SM codecs gANS/Bitcomp, same bytes (`nvcomp_sw_bench.cu`) | best-over-chunk-sweep | behind at equal-or-better ratio (§7 SM baseline) |
| `onpair_nvcomp_hw.json` | hardware DE, chunk-swept | best per column | 14–658 GB/s, median 215; ClickBench URL 418 — **reconfirms canonical `b300`** |
| `onpair_summary_*.json` (7) | base OnPair sweep, bits 12+16, FAST=0 | best shipped kernel | reconfirmation of canonical `b300` rates |
| `onpair_chunk_sweep.json` (130) †sep-run | OnPair decode throughput vs chunk size (5 sizes × 2 bits × 13 cols, FAST=1, 30 iters) | best kernel per cell | steelman: near-headline at 1000/100 MB, cliff <10 MB (launch-bound) — ClickBench URL b16 1087→1039→588→103→10 GB/s. †from run `b300-chunksweep` 2026-07-18 rev `7a408d961` |

OP-cluster verdict: **store (OP4) wins — ~0.5–1% space ≪ ~15–19% (OP2) regen time.** OP1 (row-partition,
now measured) is the zero-stored-metadata option but thread-per-row craters on long rows (fineweb/wiki
~25 GB/s), competitive only on small/uniform rows — a load-balanced kernel is future work. OP3 (CPU+stream)
ruled out (~50 ms/GB gen ≫ ~1 ms decode). Raw drop, not folded into figures. FLAG: fresh DE shows Snappy
edging LZ4 on 5 cols → soften §6 "Snappy never leads".

## Sidecar-regeneration penalty, current corpus — `results/b300-regen-corpus-20260906/`

One B300 session (Nebius uk-south1 preemptible, boost) at rev `142e250a1`
(`mp/onpair-seed-corpus-loaders`: adds `op_gpu_regen_grid.cu`, which decodes with the generated
grid kernel so the penalty can be measured at a granularity other than K=4). 150/150 cells
byte-exact; a row failing either validation is dropped, not reported. See the dir `README.md`.

| Result | Experiment | Reduction | Headline / consumed by |
|---|---|---|---|
| `regen_grid.jsonl` (150 = 15 cols × 2 widths × 5 variants) | OP2 regeneration penalty: `ctl_k4` (the July basis, `op_gpu_regen.cu` unchanged) plus `k{4,6}_w{8,16}` on `onpair_dg_k{4,6}_t256_b4` | min-of-200; shipped reading takes K=6 at the faster W per column | **K=6 shipped 15.1–33.4%, median 19.4%**; K=4 control 14.1–29.0%. Penalty tracks mean token length, **r = −0.868**. Consumed by `experiments/regen_penalty.py` (in `make verify`) and by §3's regeneration sentence. |

Replaces `b300-campaign-0717/op_gpu_regen.jsonl` as the basis for the §3 claim, on two grounds
recorded in that row: the published range is an OnPair-16, K=4 number, and its corpus is retired.
Both are reproduction findings, not re-analysis — the OnPair-16 ClickBench URL cell here lands at
17.6% against the committed 17.5%, tokens within 0.09% and decode within 0.1%.

**The mechanism, stated once so it is not re-derived:** regeneration reads every code and reduces
one entry per batch, so it scales with token *count*, while decode scales with decoded *bytes*.
The ratio is therefore a function of mean token length — the same axis §4.2 uses for decode rate,
running the other way — which is why OnPair-12 is worse than OnPair-16 on every column except
`l_shipinstruct`, whose two configurations are byte-identical. All fifteen columns are 1 GB and
throughput-bound, so the old "launch-bound columns cost considerably more" caveat has nothing left
to exclude and should not be restated.

## Review-response E1 (batching) + E3 (drain counterfactual) — `results/b300-e1e3/`
> **ARCHIVED OUT OF THE TREE 2026-09-08.** Answers to a review round whose material is not in the current draft. The provenance below is kept as the
> record of what was measured; the data itself is in the local retired-legs archive and in
> this repository's git history.


One B300 session (Nebius uk-south1 preemptible, boost) at rev `f38924aea`
(`mp/onpair-drain-baseline` = campaign branch's fixed Unit-B batch bench + the E3
`onpair_shmem_4tpt_directstore` kernel). Byte-exact both. Answers content-review M2 + M3;
changes NO headline number (reported decode always uses the shipped staged coalesced drain;
`directstore` is a diagnostic, excluded from best-shipped selection). See the dir `README.md`.

| Result | Experiment | Reduction | Headline / consumed by |
|---|---|---|---|
| `onpair_summary_directstore_{clickbench,tpch-sf10}.json` | E3: byte-exact direct-store drain counterfactual (same gather+scan; per-byte scattered global stores vs the staged coalesced drain), both `verified:true` | best shipped = min(decode_ns_iters); `X = directstore/4tpt` | §5.2/§4.2 `tab:drain` — the staged drain is **1.8–3.3×** faster than the naive byte-exact alternative (write amplification, the write-side mirror of the gather's read amplification) |
| `batch_multidict.jsonl` | E1: batched many-small-row-group decode (239 ~4 MB independently-dicted RGs), 4 launch strategies, all byte-exact | min-of-100, aggregate GB/s | §6.4 launch-bound — streams/multidict recover **~2×** over naive sequential (tpch 413→901/890, ClickBench 453→916/876). Pilot scope (hardcoded 512-thread kernel, synthetic sliced corpus, whole-sequence makespan) |

### `results/b300-shdict-refresh-20260824/`

| file | box / date | rev | protocol | consumed by |
|---|---|---|---|---|
| `shdict_summary_*.json` + `SHDICT_REFRESH_CENSUS.txt` + `clock-state.txt` | B300 SXM6, 2026-08-24 | `dd2325b3f` | staged variants against the best applicable byte-exact non-staging kernel per cell, min of 100 | **`sec:mb:shdict`**: the 25% and 52% penalties (1135 against 1513 GB/s at OnPair-12, 643 against 1338 at FSST-12, Loghub Windows) and the counter pairs in the same paragraph — global load sectors 174M to 7.6M, sectors per request 17.2 to 1.9, bank conflicts 61M to 92M, occupancy 46--67% to 24.5%, L1 97% to 86% |

**Caveat carried into the paper.** The OnPair-14 staged arms report inapplicable
against a 102,400 B harness cap rather than the B300's documented 227 KB per-block
limit, so intermediate-cardinality staging was never tested at the device ceiling.
`sec:mb:shdict`'s 512 KiB argument is unaffected — 512 KiB exceeds both.

### `results/b300-hoiststalls-20260825/` — the hoist's positive test

| file | box / date | rev | protocol | consumed by |
|---|---|---|---|---|
| `ncu_costsurface_loghub-windows_line_b12_onpair_{dg_k1_t256_b1,dh_k1_t256_b1_h0}_{details,raw}.csv` + `*.log` | B300 SXM6, Nebius uk-south1 (preemptible), 2026-08-25 | `24ac18aaf` | `ncu --set full -c 16 -k <symbol>`, two kernels at ONE coordinate (T=256, B=1, K=1), Loghub Windows OnPair-12, floating clocks | **`sec:mb:hoist`** — the stall-reason evidence that the hoist covers load latency rather than merely not hurting |

The pair differs only in `ONPAIR_HELD_HIGH`: `onpair_dg_k1_t256_b1` takes the template default of
1, and `onpair_dh_k1_t256_b1_h0` is the same body with the hoist disabled. Reduced with
`figures/extract_stalls.py`'s `shares()`, as percentages of warp cycles per issued instruction:

| stall reason | H=1 | H=0 | delta |
|---|---|---|---|
| `long_scoreboard` | 33.24 | 39.44 | **−6.21** |
| `mio_throttle` | 3.63 | 1.35 | +2.29 |
| `short_scoreboard` | 20.25 | 18.71 | +1.54 |
| `wait` | 16.32 | 15.37 | +0.95 |

`long_scoreboard` is warps parked on a global load, so the hoist removes about a sixth of the
latency stalls at the coordinate where it gains 6.4% of throughput
(`suite-hoist0-20260823`: 832 against 782 GB/s). The rise in `mio_throttle` and
`short_scoreboard` is the same mechanism seen from the other side: issuing the high-plane reads
earlier converts long-latency waits into queue pressure.

**Not a general claim.** One coordinate, one column, one device, chosen because it is where
`fig:hoist` shows the gain. At the shipped configuration the hoist is neutral, which
`sec:mb:hoist` already reports and this capture does not revisit.

Filenames carry the kernel symbol because two cells sharing a dataset/column/bits would otherwise
share a TAG and overwrite each other; `jobs/onpair-bench.sh` appends the pinned symbol. Note that
`extract_stalls.py`'s directory walker mis-parses these names (`rsplit("_b", 1)` hits the `_b1` in
the kernel symbol) — call `shares()` on the raw CSV directly, as above.

## Staged-dictionary counterfactual — `results/{a100,l40s,h100,b300}-shdict/`

Answers the 2026-07-27 preprint review's central question: *would a GSST variant adapted to
OnPair match or surpass FastPair, so the gains are purely OnPair's format?* Staging the
dictionary in shared memory is GSST's central design move; these runs test it directly on
OnPair's larger table. Rev `9b4714c2a` (the rev this leg ran at) with **no
kernel changes** — `onpair_shmem_4tpt_{shdict8,pdict,vdict}` were already registered
`KernelVariant`s. A100 on Lambda us-east-1, H100 and L40S on Nebius eu-north1 (the L40S PREEMPTIBLE: on-demand
L40S quota in eu-north1 is exhausted for every shape and both families), B300 on Nebius
uk-south1 (preemptible; landed on attempt 1). Protocol identical to the GPU decode matrix
(1 GB chunk, 100 iters, min-of-100, `--gpu-validate`). The B300 leg was owed from 2026-07-27,
when uk-south1 B300 capacity went into scheduled maintenance; collected 2026-08-04. **Ranges
below are over all four chips (A100, L40S, H100, B300).**
L40S runs bits 12/16 only: at bits14 the stride-8 layout needs 164 KB, above Ada's ~100 KB
per-block hardware maximum, and run.py sweeps all widths in one invocation per column, so a
hard launch failure would have taken the usable cells with it. That verdict is arithmetic.

Baseline per cell = best applicable byte-exact **non-staging** kernel, i.e. the same
best-kernel-per-cell rule the evaluation uses, so this is best-vs-best. `applicable:false`
means the variant's shared-memory request exceeded the cap and it never launched: that is
the capacity result, not a missing measurement.

| Result | Experiment | Reduction | Headline / consumed by |
|---|---|---|---|
| `shdict_summary_{clickbench,lcomment,pscomment,fineweb}.json` (per chip) | 3 shared-memory dictionary-staging variants vs the shipped L1-served gather, 4 columns × bits 12/14/16, every reported cell `verified:true` | `figures/extract_shdict.py` → `results/shdict_summary.csv`; per cell, best staging variant vs best non-staging baseline | §5 staged-dictionary subsection + §7 GSST paragraph — **28 cells where staging is possible, 60 byte-exact variant measurements, 0 wins.** Best case **−9.8%** (L40S `l_comment` b12, packed layout), median **−45.4%**, worst **−68.2%** (H100 FineWeb b14). Loss *deepens* with dictionary size: −9.8 to −49.9% at bits12, −50.3 to −68.2% at bits14. At bits16 staging is impossible on every chip (592 KB–1 MB vs 164/227 KB hardware limits) |
| `SHDICT_CENSUS.txt`, `run-env.txt` | box identity + per-cell completion | — | provenance |

### Mechanism capture — `results/{a100,h100,b300}-shdict-ncu/`

Timing says staging loses; this says **why**, which is what makes the result on-thesis. 48 `--set full` captures, 16 each on the H100 (Nebius eu-north1), the B300 (Nebius uk-south1),
and a GCP A100-SXM4-40GB (`a2-highgpu-1g`, the same part as the paper's Lambda A100). Profiling
needs `RmProfilingAdminOnly=0`, which Lambda does not permit, hence GCP for the Ampere leg. Same
metric set as the NCU cost surface. **All 48 `CAPTURE-VERIFIED`**: kernel symbol matched and shared-memory footprint
nonzero, asserted against *dynamic* shared memory for the staging variants (they use
`extern __shared__`) and *static* for the shipped `split8read` (fixed array). Measured
footprints confirm the predicted sizes: `shdict8` 53.5 KB at bits12 and 164.1 KB at bits14,
`pdict` 86.3 KB, `vdict` 38.0 KB.

Reduced by `figures/extract_shdict_ncu.py`. ClickBench `URL` at bits12, **B300** (the paper's
headline chip, and `tab:shdict`'s exhibit as of 2026-08-04; the H100 and A100 reproduce every
direction independently, the A100 with a harsher occupancy penalty: its 164 KB shared limit
leaves the 86 KB padded table one resident block per SM, so `pdict` occupancy falls to 12.5%
against a 41.2% baseline, versus 24.4% against 43.6% here):

| kernel | global ld sectors | B/sector | shared ld conflicts | achieved occ % | L1 SoL % |
|---|---|---|---|---|---|
| `split8read` (shipped) | 360,325,318 | 6.2 | 69,708 | 43.6 | 87.6 |
| `pdict` | 15,590,799 (−96%) | 29.4 | 56,391,825 (**809×**) | 24.4 | 74.5 |
| `shdict8` | 42,961,312 (−88%) | 15.7 | 38,532,300 (553×) | 24.7 | 58.0 |
| `vdict` | 185,981,649 (−48%) | 9.9 | 56,932,836 (817×) | 24.9 | 72.3 |

H100 for comparison (the previous exhibit): `split8read` 362,438,732 / 6.2 / 67,686 / 43.8 /
86.9; `pdict` 15,578,991 / 29.4 / 57,001,584 (842×) / 24.0 / 69.5.

**The move worked on the read side and still lost.** Global-load sectors collapse by up to
96% and bytes per sector rises from 6.2 to 29.4 of a 32 B maximum, so the scattered gather
really did become a near-perfectly-coalesced stream: the hypothesis held. What it cost
instead is shared-memory bank conflicts up to 842× and achieved occupancy halved from ~44%
to ~24%. L1 SoL *falls* (87.6 → 58.0–74.5 on the B300, 86.9 → 49.8–69.5 on the H100), so the
pipe is no longer what saturates; DRAM read SoL stays at or below 9% throughout (at or below
2.3% on the B300), so nothing became bandwidth-bound. At bits14 the 164 KB table allows about
one block per SM and occupancy drops to **12.5%** against the baseline's 44.5–45.2%, which is
why the bits14 loss (−50.3 to −68.2%) is deeper than bits12's.

Reading for the paper: a random gather stays a random gather. Shared memory does not escape
the access-rate bound, it re-denominates wavefront pressure as bank-conflict pressure and
adds an occupancy penalty. Consistent with the pre-paper lab notebook (712× conflicts,
47%→24% occupancy) now reproduced on a paper chip through the paper's own reduction.

Caveat to carry into prose: no single staging layout is strongest, and each of the three
architectures has a different best one, so the fair comparison is best-staging-variant-per-cell.
`shdict8` (stride-8) wins on the A100, `pdict` (padded 16 B) on the H100 and B300, `vdict`
(packed variable-length) on the L40S. Also note the L40S, the off-regime chip where no pipe saturates,
shows the SMALLEST staging losses (9.8 to 50.4%) — removing L1 pressure helps most exactly
where the access-rate reading gives way — and still never wins. The bits14 gates
(100 KB for `pdict`/`vdict`, 224 KB for `shdict8`) are harness design-sanity caps, not
hardware maxima; only the bits16 verdict rests on hardware.

## Token access distribution (Appendix A) — `results/token-freqdist/`

CPU-only, no GPU time and nothing in the evaluation depends on it. The tool trains and
encodes each column at each codec, then reads the frequency of every dictionary entry off the
code stream, so it measures which entries a column actually reads rather than what the table
contains.

| Result | Box | Rev | Config | Reduction | Consumed by |
|---|---|---|---|---|---|
| `token-freqdist/token_freqdist.json` | laptop (CPU only) | `onpair` 0.0.4; FSST-12 vendored `fsst-rs` @ `196a862` | ten selected columns x {OnPair-12, OnPair-16, FSST-12}, **64 MiB sample per column** | cumulative access coverage at 64 log-spaced ranks; bytes of an 8 B plane covering 50/90/99/99.9% of accesses; share of accesses reaching the high plane | `fig:freqbars`, Appendix A |

Two caveats that must travel with these numbers:

- **The sample is 64 MiB, not the 1 GB the evaluation uses.** Sample size changes the trained
  dictionary, so these curves rank and characterise columns; they are not evaluation numbers
  and must not be quoted as such.
- **OnPair trains unseeded**, so re-running retrains and the figures move by a few percent.
  Every number quoted in Appendix A was re-derived from the committed JSON rather than carried
  across from an earlier run.

FSST-12 is pinned to `196a862` rather than the crate or local HEAD because that rev carries
the training-budget fix; without it the trained table is 88% empty.

## FSST-12 stored split, re-measured on Linux — `results/suite-flat-20260830/b300/fsst12_stored_components.jsonl`

**The split is measured host-side, and the host matters.** Section 5 excludes the row-offsets array
from every technique's ratio, and the committed FSST-12 cells collapse their components into one
total, so the split has to be measured separately. It first was, on macOS, and **seven of fifteen
columns did not reproduce the committed cell totals** (`loghub-spark` -1.13%, the rest within
0.19%).

The cause is FSST-12's trained dictionary, which is platform-dependent on real data: candidates tied
on both gain and length are separated by hash iteration order, and hashbrown's probe sequence
depends on an architecture-specific SIMD group width. Small synthetic inputs do not expose it;
columns training ~3750 symbols against a 4096 code space do. Everything else was eliminated first —
not the sample, not nondeterminism, not a revision skew, not rounding.

| Field | Value |
|---|---|
| Bench | `vortex-bench/src/bin/fsst12-stored-rows.rs` @ `e12bb0ba9` |
| Box | `homelab-research`, x86_64 Arch Linux, 16 cores — **CPU only, no GPU** |
| Input | `~/data/onpair-campaign-cols/*.bin`, the campaign's per-column dumps, byte-exact against every committed cell (row count and payload length match on all fifteen) |
| Config | `--tok-per-batch 192` |
| Consumed by | `suite.fsst12_components` → `suite.ratio()`'s row-offsets subtraction |

**Result: all fifteen columns now reproduce the committed cell totals EXACTLY.** The seven that
differed were re-measured on Linux and each landed on its cell to the byte; the eight that already
reproduced on macOS are unchanged, and their agreement across both platforms is what licenses
leaving them. Every row carries `measured_on`.

Corroborating detail worth keeping: the Linux `sidecar` values also reproduce each cell's own
`sidecar_bytes` exactly, and `loghub-spark`'s `row_offsets` moved 11 912 736 → 11 910 696 — the only
component of this file that feeds a reported number.

## Sidecar cost by batch granularity — `results/suite-flat-20260830/b300/onpair_offset_cost_bygran.jsonl`

**Why it exists.** The compression ratio charges OnPair's output-position sidecar, and the sidecar
holds one offset per batch of `32*K` codes, so its size is a function of the `K` its reader was
compiled for. Every figure charged the shipped `K=6` (192 codes) regardless, while the plotted rate
is the best byte-validated kernel for the column and the kernel sweep varies `K`. Where the winning
kernel is not `K=6`, a throughput was paired with a stored representation that kernel does not read.
Raised by a co-author against `fig:perf_real`; the comparator leg had measured 32, 128 and 192 only,
so the granularities several reported kernels actually use had no measurement at all.

| Field | Value |
|---|---|
| Bench | `vortex-bench/src/bin/onpair-offset-cost.rs` → `onpair_sidecar_by_granularity` |
| Box | **Host-side, no GPU** (Apple Silicon laptop, `cargo build --release`, no `cuda` feature) |
| Input | `~/data/corpus-bank/ratio-basis-20260826` — the leg's own materialized cells, `rev=876c062b2e7cc69729339e0c1f1829cfdec0fe78`, 15 columns x bits {12,16} |
| Config | `--tok-per-batch 32,64,96,128,160,192,224,256,512` (every granularity any chip's best or shipped kernel uses) |
| Reduction | `offset_compressed_bytes` summed over chunks per (dataset, column, bits, tok_per_batch), deduped on chunk identity |
| Consumed by | `suite._onpair_sidecar_table` → `suite.ratio(c, tok_per_batch)`; `fig:perf_real` at the best kernel's `K`, `paper_claims` at the shipped selector's |

**No re-encoding, and that is the point.** It reads the committed `.vortex` parts back through
`read_onpair_chunks` and sizes the sidecar over the arrays the leg wrote, so no dictionary is
retrained. That distinction is not academic: FSST-12's trained dictionary IS platform-dependent on
real data (measured 2026-09-02; see below and
`onpair-gpu-paper/docs/notes/2026-09-02-fsst12-platform-dependence.md`), and a re-encode on another
host would not have been comparable with the committed numbers.

**Self-validating.** 32, 128 and 192 were measured alongside the coarser ones and diffed against
the comparator leg's `onpair_offset_cost.jsonl`: **90 overlapping (cell, granularity) pairs, 0
mismatches** on `offset_compressed_bytes`, `n_batches`, `total_tokens` and `compressed_bytes`. That
equality is what licenses the six granularities the leg never measured.

**THE PAPER ALREADY DECLARED THIS BASIS; the reducer was out of compliance with it.** Section 5.0:
"unless stated otherwise, the results in this section report every technique, ours and each
baseline, at its best configuration on each column", and the paragraph before it defines the ratio
against that configuration's compressed representation. Charging a fixed K=6 sidecar while
reporting the best kernel over all K therefore contradicted a stated basis rather than filling a
gap in one, so no prose change was needed to answer the review comment. This is the SECOND time
the same paragraph has been declared and not implemented -- the 2026-08-30 offsets-exclusion fix
has the identical shape ("Section 5.0 states that the row-offsets array is excluded ... The
reducers did not implement that"). When a basis question comes up, read 5.0 first.

**Effect.** 11 of the 30 B300 OnPair marks move, by **-0.24% to +0.27%**. No rendered number in the
paper changes: `claims.tex` regenerates identically and `tab:datasets` compares 195 cells with 0
disagreements. The defect was real and its magnitude is under a third of a percent.

**FSST-12, closed 2026-09-02 for the two columns it affects.** Its sidecar is recorded on the cell
at the shipped K=6, and 13 of its 15 B300 best kernels run there, so the cell figure is already the
right charge for them. The two that do not are `c_address` (K=16) and `o_clerk` (K=8), measured
host-side into `results/suite-flat-20260830/b300/fsst12_sidecar_bygran.jsonl` by
`fsst12-stored-rows` from the byte-exact column dumps.

Measuring those two on macOS is legitimate *because they are among the eight columns whose host-side
split reproduces the committed cell exactly* — the trained dictionary agrees, so a local encode
describes the same artifact. That is not true of the seven columns that do not reproduce (FSST-12's
dictionary is platform-dependent on real data; see
`onpair-gpu-paper/docs/notes/2026-09-02-fsst12-platform-dependence.md`), and those deliberately fall
back to the cell, which is the correct charge for them anyway since their best kernel is K=6.
Self-checked: at 192 the measurement reproduces each cell's `sidecar_bytes` exactly (2 188 344 and
0), and `total_container_matched` reproduces the committed split.

Effect: one mark moves, `c_address` FSST-12 from 1.2639 to 1.2661, +0.175%. `o_clerk`'s sidecar is 0
at every granularity — fixed 15-character values, so its offsets are perfectly regular.

`tab:datasets` still charges 192 deliberately: it pairs the ratio with no rate, so no kernel's `K`
applies.

## Large inputs and binary reports

Datasets are acquired separately; see [`data/fetch.md`](data/fetch.md). Encoded
input dumps can be generated with the companion harness. Pipeline reductions
use the included text counter exports and do not require binary `.ncu-rep` files.

## Zstd reproduction package (2026-09-09)

`experiments/zstd/` records all 329 historical level/frame configurations and
provides an independent framing/preparation driver plus a fresh-result checker.
`results/zstd-validation-20260909/` contains the bounded Windows prefix/flat
control manifests and all 800 timing samples. These checks establish the tested
configuration's output correctness and prefix compression fingerprint; they do
not certify the other historical Zstd decodes. New Rust results record explicit
output validation and actual decoded bytes.
