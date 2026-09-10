# Measurement and reduction conventions

[MANIFEST.md](MANIFEST.md) records capture-specific settings and provenance.
The figure generators and checks use `figures/common.py` for older capture layouts
and `figures/suite.py` for the paper's suite campaigns.

## Throughput

Rates are decimal GB/s (10⁹ bytes/s). GPU throughput is decoded bytes divided by
the minimum iteration time; bytes/ns is numerically GB/s. Where older records
store GiB/s, the conversion factor is 2³⁰/10⁹ (`common.GIB_TO_GB`). Main throughput
measurements use at least 100 iterations.

Decode timing covers kernels with codes, dictionaries, and offsets already in
device memory. It excludes host-to-device transfer and input materialization.
The supporting end-to-end scan program measures a different scope and is outside
the submitted evaluation.

## Kernel selection and validation

The suite loader exposes two rate accessors:

- `rate_gb_s()` reads the kernel named by `gpu.auto_kernel`, the production selector.
- `best_rate_gb_s()` takes the best rate across kernels marked both `verified` and
  `applicable`, including generated configurations. This is the configured-kernel
  basis used in the evaluation's comparisons with tuned baselines.

The harness's `gpu.best_decode_gib_s` field ranges over production kernels only,
so it is not interchangeable with the full-grid maximum. `common.best_shipped()`
handles older captures and excludes non-byte-exact ablation builds. Keep these
selection rules explicit when adding analyses.

Run GPU measurements with `--gpu-validate` and inspect the validation metadata.
Ablation kernels that omit work can support stage-cost studies, but their timings
are not valid full-decode rates.

## Inputs and compression ratio

The main campaign samples 1,000,000,000 UTF-8 payload bytes per column, subject to
row boundaries, with `--chunk-mb 1000` (1000 MiB). Rates use the recorded decoded
byte count. OnPair dictionaries use 12- and 16-bit codes. Dictionary training is
seeded through `Column.training_seed`; kernel measurement order uses the separate
`ONPAIR_SHUFFLE_SEED` setting.

At-rest OnPair compression ratio is `sample_bytes / on_disk_bytes`, including the
dictionary, packed codes, and offset sidecar. The in-memory unpacked codes are
two bytes each even for the 12-bit format and are not the stored-size denominator.
Token-weighted mean length is `sample_bytes / gpu.total_tokens`.

See [data/fetch.md](data/fetch.md) for the fifteen-column corpus. Earlier captures
use different corpora; compare them only where the manifest establishes matching inputs.

## Baselines and clocks

Hardware DE measurements use nvCOMP's hardware backend on Blackwell. The main
campaign sweeps Deflate-high, Deflate-fast, LZ4, and Snappy across chunk sizes.
Throughput comparisons select the best setting per column. Throughput-versus-ratio
plots retain each column's baseline Pareto frontier. Software Zstd is swept over
levels; gANS and Bitcomp come from separate comparator legs selected in `suite.py`.
All comparisons use the same underlying column payload. Zstd's encoder additionally
stores a u32 length per value in the decoded stream; its rate numerator excludes
those lengths. See [zstd/README.md](zstd/README.md) for the exact historical
settings, framing fingerprint, and bounded output verification.

The dataset table reports two baseline compression ratios per column: the ratio
at the fastest decoding setting (`CR_f`), and the maximum measured ratio
(up arrow). These settings can coincide. DE varies codec and chunk size; Zstd
varies level and frame size; gANS varies chunk size. Both
ratios come from valid measurements in the same B300 sweeps used by the figures.
The table generator selects the higher ratio when decode rates tie, and the
faster rate when compression ratios tie.

The throughput campaigns record boost, locked maximum, and 75%, 55%, and 40% clock
states. Use each leg's `clock-state.txt` and device metadata for its exact settings.
Rates are from boost runs unless the figure says otherwise.

The current pipes figure uses the September 9 captures of each device's best
verified Windows configuration. Pipe totals are relative to each pipe's reported
peak. The L1 stack separates shared read/write, global read/write, and residual
activity. A100 and L40S need instruction-based estimates for some directions;
[pipes/README.md](pipes/README.md) records the counters, attribution and checks.
Instrumented replay duration is not the decode-throughput measurement. Archived
counter exports, winner selection and achieved-clock checks are independently
reduced by `experiments/check_pipes.py`.

## Supporting experiments

CPU, IAA, and end-to-end benchmark sources are retained for supporting work, but
they back no result in the submitted evaluation. Their timing scopes and reductions
differ from the kernel-only throughput campaign. Historical capture descriptions
in the manifest document those differences; they do not expand the paper's claims.

Sidecar persistence/regeneration and shared-dictionary staging have bounded
reproduction commands and archived checks in [sidecar/README.md](sidecar/README.md)
and [staging/README.md](staging/README.md). These remain separate supporting paths;
the experimental staging candidates do not change the recommended kernel.
