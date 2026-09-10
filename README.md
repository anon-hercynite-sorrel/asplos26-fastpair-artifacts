# FastPair reproducibility artifacts

Measurements and analysis scripts for *FastPair: GPU-Optimized String Decoding*.
CUDA kernels and benchmark drivers are in the
[companion harness](https://github.com/anon-hercynite-sorrel/fastpair-harness).

## Reproduce figures and check results

Install [`uv`](https://docs.astral.sh/uv/), then run:

```sh
make analyze
```

This regenerates the nine figures listed in `experiments/paper-figures.txt`,
writes their PDFs to `figures/out/`, and checks the recorded numerical claims.
The command exits nonzero if a figure fails to build or a check fails.
No GPU is needed; `uv` installs each script's dependencies.

To run only the headline-number checks:

```sh
uv run experiments/validate.py
```

If a manuscript checkout is available, `PAPER_DIR=/path/to/paper make analyze`
also checks its figure list, dataset table, abstract numbers, and claim macros.
These comparisons are skipped when no manuscript is found.

## Run measurements

[MEASURE.md](experiments/MEASURE.md) gives the harness build requirements,
a one-column benchmark command, and instructions for collecting and analyzing
new results. The [pipes protocol](experiments/pipes/README.md) covers configuration
confirmation and counter reduction; the [Zstd guide](experiments/zstd/README.md)
records the baseline settings, framing, and validation coverage.
`make measure` prints the measurement guide. The harness's first build downloads
dependencies. Cloud provisioning and campaign orchestration are not included.

The [B300 validation record](results/b300-validation-20260910/README.md) contains
checked outputs for the one-column grid, pipes, staging, sidecar, and integrated
Zstd workflows. `make analyze` also verifies these records without a GPU.

## Evaluation inputs

The main campaign measures OnPair-12, OnPair-16, and FSST-12 on B300, H100, A100,
RTX PRO 6000-SE, and L40S GPUs. Decode timing covers kernels with inputs already
in device memory. Rates use the minimum time over at least 100 iterations;
outputs are checked byte-for-byte against the CPU decoder.

**Real-world columns:** FineWeb2 Mandarin `text`, Wikipedia `text`, CodeParrot `content`,
ClickBench `URL` and `Title`, Loghub `Android`, `HDFS`, `Thunderbird`, `Spark`, `Windows`.

**Generated columns:** TPC-H `c_address` (SF 263), `l_comment`, `l_shipinstruct`,
`ps_comment` (SF 15), and `o_clerk` (SF 45).

Baselines include the Blackwell hardware Decompression Engine, nvCOMP software
Zstd, gANS and Bitcomp, and a thread-per-row OnPair decoder.
[MANIFEST.md](experiments/MANIFEST.md) records the hardware, configurations, and
source revisions for each capture. [METHODOLOGY.md](experiments/METHODOLOGY.md)
defines the timing, compression-ratio, and kernel-selection rules.

## Repository contents

| Path | Contents |
|---|---|
| [results/](results/README.md) | Measurements, reduced CSVs, and result schemas |
| [figures/](figures/README.md) | Figure generators, table generator, and shared reduction functions |
| [experiments/data/fetch.md](experiments/data/fetch.md) | Dataset downloads and generation parameters |
| `experiments/validate.py` | Checks of the headline numerical claims |
| `experiments/paper_claims.py` | Claim-macro generation and checks |
| `experiments/regen_penalty.py` | Sidecar-regeneration measurements and checks |
| `experiments/bench/` | GPU source snapshots and supporting CPU, IAA, and scan benchmarks |
