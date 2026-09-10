# Running new measurements

`make measure` prints this document. To check the committed results without a GPU,
run `make analyze` instead.

## Prerequisites and build

Use a target NVIDIA GPU with compute capability at least 8.0, CUDA Toolkit 12.8 or
newer, a compatible driver, Rust, Python 3.11 or newer, and `uv`. The hardware
Decompression Engine baseline requires Blackwell. The harness also needs a C++20
compiler, CMake 3.21 or newer, and libclang. Allow substantial disk space for
downloaded corpora, generated TPC-H tables, and materialized columns.

```sh
git clone https://github.com/anon-hercynite-sorrel/fastpair-harness.git
cd fastpair-harness
cargo build --release --features cuda -p vortex-bench --bin onpair-chunk-bench
```

Build on the GPU being measured: kernels compile with `-arch=native`. The first
build downloads Rust dependencies, nvCOMP, and the pinned OnPair C++ reference.
The FSST-12 encoder is vendored. Set `HF_TOKEN` if needed for HuggingFace downloads.

## One column: configured search

```sh
cd benchmarks/onpair-bench
ONPAIR_FAST=1 uv run python run.py \
    --datasets loghub-windows --columns line \
    --bits 12 --chunk-mb 1000 --sample-bytes 1000000000 \
    --gpu-decode --gpu-validate --gpu-iters 100 --jobs 1 \
    --gpu-kernels packed-grid
```

The runner writes `vortex-bench/data/onpair-bench/summary.json`, relative to the
harness root. Copy it to your result directory before another invocation replaces
it. `--list` lists available inputs; select both dataset and column to bound a run.

This command tests one Windows OnPair-12 cell across the registered configured
kernel grid and production controls, with byte validation. It is the bounded
starting point for checking the paper's per-column configuration search. It does
not reproduce a complete device leg or the final pipes selection/profile protocol.
For that protocol, use [pipes/README.md](pipes/README.md).

For a shorter build-and-decode smoke run, replace `packed-grid` with `production`.
That preset measures the production kernel set and does **not** establish the
paper's best configuration or recommended K6/T256/B4/H1 launch. In the JSON,
`gpu.auto_kernel` records the historical production selector and
`gpu.best_kernel` is restricted to the production set. For the configured winner,
select the best applicable, verified timing in `gpu.kernels`; the figure helper
`suite.best_rate_gb_s` implements this reduction.

Unsetting `ONPAIR_FAST` adds the reference OnPair GPU kernel and bundled nvCOMP
comparison; it does not run the paper's standalone comparator sweeps. See
[data/fetch.md](data/fetch.md#windows-download-and-local-fallback) before starting
Windows if Zenodo is unavailable from the measurement host.

## Paper campaign

The fifteen columns are listed as `label dataset column` in
`results/suite-paper-20260821/<chip>/campaign_targets.txt`. Dataset sources and
generation parameters are described in [data/fetch.md](data/fetch.md) and the
harness's `columns.py`.

The committed campaign separates materialization (`MATERIALIZE`), the kernel grid
(`GRID`), hardware DE (`DE`), software comparators (`SW` and `ZSTD`), FSST-12
(`FSST`), and kernel resource measurements (`LADDER`). These are recorded campaign
stages, not subcommands of the released `run.py`. The campaign orchestrator is
not included. Reproducing a full campaign requires running the relevant drivers,
setting clocks, and collecting their outputs in the recorded layout.

| Setting | Main throughput campaign |
|---|---|
| Sample | First 1,000,000,000 UTF-8 payload bytes, subject to row boundaries |
| Chunk size | `--chunk-mb 1000` = 1000 MiB |
| Iterations | At least 100; rate uses the minimum decode time |
| OnPair code widths | 12 and 16 |
| Dictionary training seed | `Column.training_seed`, normally 20260819 |
| Clock states | Boost, locked maximum, and 75%, 55%, 40% of nominal |

The training seed is separate from `ONPAIR_SHUFFLE_SEED`, which controls kernel
measurement order. Record both when reproducing a run. Use each leg's
`clock-state.txt`, `device_properties.json`, and result metadata for its exact
settings and selected kernels; supporting experiments can use different settings.

Enable byte validation and inspect its results before including a measurement.
Preserve the device, clocks, input size, codec settings, kernel selection, and
validation metadata alongside timings. [METHODOLOGY.md](METHODOLOGY.md) describes
the reductions; [MANIFEST.md](MANIFEST.md) maps the committed captures to claims.

For integrated Zstd reproduction, standalone framing controls, exact settings,
and validation coverage, see [zstd/README.md](zstd/README.md).

## Analyze new results

The figure scripts select named paper legs through `figures/suite.py`. Adding a
directory under `results/` does not automatically redirect figures or the checker.

To use the suite loader, arrange outputs with the same filenames and schemas as
an existing leg under `results/suite-<id>/<chip>/`, then select that suite explicitly
with `suite.latest_root("<id>")`. Use `suite.cells(root, chip, tag)` to load cells
and choose the rate accessor appropriate to the comparison. Some figures merge
separate comparator and device legs, so their inputs must also be selected explicitly.

The released one-column summary is an input to this collection step; it is not a
complete suite directory. `validate.py` checks the paper's recorded values and
does not serve as a general acceptance test for measurements on different hardware.
