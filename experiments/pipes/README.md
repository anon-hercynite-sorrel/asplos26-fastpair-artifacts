# Windows boost pipeline experiment

`fig_pipes` uses each GPU's best confirmed configuration for Windows OnPair-12,
with the recommended `onpair_dw_k6_t256_b4` measured as a control.

## Regenerate without a GPU

From the artifact root:

```sh
python3 experiments/check_pipes.py --check
uv run figures/fig_pipes.py
# Optional: save the freshly reduced per-launch direction data elsewhere.
python3 experiments/check_pipes.py --output /tmp/pipes-directions.json
```

The checker unpacks the 1.5 MB text-evidence archive into a temporary directory,
verifies its checksums, reconstructs the screen/confirmation selection, checks
byte validation, input/source records, launch geometry, missing counters,
observed clocks and timing/profile agreement, then recalculates all five bins.
All forty accepted launches (winner plus recommendation, four launches each,
five GPUs) must agree with the accepted data. No missing-device or old-CSV
fallback is permitted. The renderer repeats the check before drawing.

`results/pipes-boost-20260909/accepted.json` and `directions.json` preserve the
accepted reduction and all four per-launch directional inputs. `evidence.tar.gz`
contains the full timing arrays, profiler CSV exports, metric inventories,
selected kernels, original per-device runner, compiler/profiler/driver logs,
input/binary digests and clock monitors. The initial A100 attempt is retained;
only its settled follow-up enters the figure. Opaque `.ncu-rep` binaries are not
needed for this reduction and are omitted from this public package.
`publication-provenance.json` maps original and published file hashes. Paths
are normalized and GPU serial numbers/UUIDs redacted; numerical CSV fields and
timing samples are unchanged. Cloud provisioning state and credentials are not
part of the package.

The figure's printed annotations are rounded; its bar heights use full precision.

| GPU | Accepted winner | Global direction | L1 total (% peak) | Device memory (% peak) |
|---|---|---|---:|---:|
| b300 | `onpair_ds_k6_t128_b8_s14` | direct data-stage ratio | 98.840 | 24.082 |
| h100 | `onpair_dw_k7_t256_b4` | direct data-stage ratio | 99.010 | 47.910 |
| a100 | `onpair_dw_k4_t128_b2` | estimated tag ratio | 99.000 | 59.525 |
| rtxpro | `onpair_ds_k8_t128_b4_s12` | direct data-stage ratio | 62.705 | 89.803 |
| l40s | `onpair_dg_k8_t128_b2` | estimated tag ratio | 35.223 | 89.743 |

## Five-bin accounting

For each launch, let N be total LSU data-stage wavefronts, S the shared total,
L shared loads and W shared stores. The measured nonshared fraction is
U=(N−S)/N. The bins are:

- global read: Uq;
- global write: U(1−q);
- shared read: L/N;
- shared write: W/N;
- other: (S−L−W)/N.

On H100/B300/RTX PRO, q is the ratio of direct LGDS read commands to read plus
write commands. Local-load/store sectors and shared atomics are zero in these
captures. The raw LGDS counters describe the local/global data path; zero local
sectors support the global label here. Applying the direction ratio to N−S
closes the small difference between counter families (at most 0.14704 points of
total traffic in the direct-counter captures).

A100/L40S do not expose the captured direct LGDS direction counters. There q is
the global-load tag-output wavefront count divided by global-load plus
-store tag-output wavefronts. This estimates the direction mix, not the total:
we do not equate tag-stage and data-stage wavefront counts. Where both counters
exist, the estimate shifts 0.64–2.47 plotted points from writes to reads in the
winning cells. That is a sensitivity comparison, not an error bound for
A100/L40S. No empirical correction is applied to those GPUs.

The other bin always uses the same shared residual, including on GPUs that expose
an explicit misc counter. It is not redistributed into shared reads or writes.
It includes work outside ordinary shared loads/stores; earlier B300 probes
identified scan shuffles as one contributor. It is not exclusively scan work.
Missing optional counters remain missing, never measured zeroes.

Each launch's fractions are multiplied by
`l1tex__data_pipe_lsu_wavefronts.avg.pct_of_peak_sustained_elapsed`. The figure
averages these scaled points over four launches; it does not multiply a mean
fraction by a mean utilization. L2, device memory and SM use their
`pct_of_peak_sustained_elapsed` metrics from those same launches. The older
broad L1 `throughput` active-normalized metric does not set this stack's height.

Global reads include dictionary gathers, code input, lengths and batch offsets;
global writes drain the output. Shared traffic includes output staging/draining
and the high-byte request queue for W8 kernels. The selected A100/H100 W16
kernels omit that queue. Thus operation bins have consistent definitions across
GPUs, while the work a configuration performs can differ.

## Repeat on a reviewer-owned GPU

Build the public harness using the [measurement guide](../MEASURE.md). The
accepted campaign used source revision
`f6d81878715bf322a0917ada32bcf40adffbd3ef`. Its input was the cached prepared
`windows12.vortex`, SHA256
`067f1bc2a8df043e0b475eda6b2238cf76c93f497d3ca2b001e3a301e85cd5e6`.
It contains 99,090,926 codes and decodes to 999,999,899 bytes in one chunk;
`frac_le8=0.37251443`. The input is not redistributed. Acquire Windows and
materialize its OnPair-12 Vortex container through the normal
[measurement/preparation route](../MEASURE.md); see
[data acquisition](../data/fetch.md) for the download fallback. A freshly built
container may have a different digest. The local capture accepts that container
only when every timing cell matches the archived decoded-byte count, code count,
chunk count and short-token fraction and passes byte validation against its own
input. Matching statistics do not establish byte identity with the archived
encoded stream or original text. `input-identity.json` records the actual digest
and `archived_input_container_match` explicitly. A changed encoding with different
statistics fails this bounded comparison rather than silently becoming Windows
paper data.

The GPU must be idle and available exclusively to this process. Install NCU and
put `ncu`, `nvcc`, `rustc`, and `nvidia-smi` on PATH. The command resets GPU clock
locks and attempts to reset application clocks; it leaves the GPU unlocked.
It uses sudo for those operations and NCU counter access. No cloud tooling is
required. Choose the matching chip name and a new output directory:

```sh
python3 experiments/pipes/capture.py --chip a100 \
  --harness /path/to/fastpair-harness --vortex /path/to/windows12.vortex \
  --output /tmp/my-a100-pipes
python3 experiments/pipes/check_capture.py /tmp/my-a100-pipes --chip a100 \
  --output /tmp/my-a100-pipes-check.json
```

By default the command records the current harness checkout, its working-tree
status, binary digest and compiler versions. To enforce an exact revision, pass
`--expected-revision <full-commit-hash>`. To enforce exact
prepared-container identity, pass `--expected-input-sha256 <sha256>`; the archived
hash and revision above can be used for a strict historical comparison. Keep
source and input differences visible when interpreting a rerun. The strict
archival checker (`experiments/check_pipes.py`) remains pinned to the accepted
source/input records and submitted values.

The capture script reuses the architecture's
archived metric inventory; a profiler version lacking those required counters
fails explicitly. Do not silently delete missing metrics to obtain a plot.
The historical source remains the reference for comparison.

The candidate lists contain the 561 applicable, verified Windows-12 kernels in
each device's archived boost sweep. The script warms the archived winner for
2000 iterations, screens all candidates for 100 samples with shuffle seed
20260909, then confirms the fresh top three, archived winner and recommendation
(deduplicated) in two independently ordered rounds (seeds 20260910/20260911).
Minimum confirmed CUDA-event time selects the winner; median then kernel name
break exact ties. Sub-percent differences can reflect near-ties.

For A100/B300, each confirmation and timing anchor collects 2100 samples and
retains the last 100 after discarding the first 2000 within the same process.
H100/L40S/RTX PRO use 100 samples. The original A100 campaign reused its first
screen for the settled follow-up; the local script repeats the full screen.
All raw samples are saved before trimming.

Each selected kernel has separate before/after uninstrumented timing anchors.
NCU uses application replay, grid matching, `--clock-control none`,
`--cache-control none`, exact function name matching and four launches. For
H100/L40S/RTX PRO the arguments are `--launch-skip 3` and `--gpu-iters 8`; for
A100/B300 they are `--launch-skip 2003` and `--gpu-iters 2100`. The first three
launches are one validation launch and two built-in warmups. Export uses
`--page raw --csv --print-units base`. There is no concurrent warming workload.

Successful reset alone does not establish a matched operating point. The checks
require pre/post anchor and profile/anchor agreement within 3% for the settled
GPUs and 5% otherwise. A100/B300 profile clocks must be at least 97% of the
archived 1410/2032 MHz references with at most 2% spread. H100 is checked against
97% of 1980 MHz. Both checkers compare profile clocks with loaded clock-monitor samples,
except for the A100 follow-up whose settled per-launch clocks are the acceptance
reference. Review the whole-run monitor as context; it mixes the sweep, setup,
confirmation and profiling phases.
A fresh winner more than 3% below the archived best raises a review flag. These
are operating-point checks, not statistical confidence intervals or proof of
causal bottlenecks. New winners are allowed by `check_capture.py`; changing the
submitted cohort requires a deliberate new reduction.

The [B300 validation record](../../results/b300-validation-20260910/README.md)
contains a complete execution of this collection protocol, including timing
arrays, counter exports, input identity and clock records. The collector selected
`onpair_ds_k6_t128_b8_s12`; its capture passes `check_capture.py` without flags.
