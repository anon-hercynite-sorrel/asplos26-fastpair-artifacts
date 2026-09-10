# Zstd baseline reproduction and validation

The Zstd sweep's 329 configurations are in `historical-settings.json`,
extracted from `results/suite-flat-20260830/b300/zstd_frames*.json`. Each entry
records dataset, column, seed, sample size, compression level, values per frame,
frame count, compressed byte count, and requested backend. Frame targets were
converted from bytes using mean payload row length; replay the recorded **values
per frame**, not a fixed byte slice of the concatenated input.

## Framing and validation

The Rust Zstd encoder stores a little-endian u32 length followed by each string's
bytes, then compresses groups of values without a dictionary. Rates and ratios use
string payload bytes as numerator; this does not make the decoded stream flat.
Windows has 999,999,899 payload bytes and 4,139,945 rows, so the framed decoder
produces 1,016,559,679 bytes. The historical level19/271-values cell contains
15,277 frames and 53,516,006 compressed bytes.

The [integrated B300 validation](../../results/b300-validation-20260910/README.md)
uses level 19 and 271 values per frame. It verifies the complete decoded stream
and records 100 timings, with a minimum of 3.122688 ms (320.24 payload GB/s).

`results/zstd-validation-20260909/` additionally compares prefix framing with a
flat control using pinned Zstd 1.5.7 and four 100-iteration blocks per layout
(reuse, reprepare, reprepare, reuse). At an observed 1905 MHz, prefix minima are
304.5–305.8 GB/s and flat-control minima are 329.1–330.5 GB/s. The flat layout is
a framing control; the paper's Zstd baseline uses the prefix layout.

```sh
python experiments/zstd/check.py
```

This checks the exact historical configuration list, archived diagnostic hashes,
all 800 timing samples and summary calculations, and verification coverage in
the standalone controls. The 329 sweep records do not contain
per-frame status or output verification fields. The Rust benchmark resets and
checks every frame's status/size on every launch and compares every output byte
on the first warmup and first/last timed launch. Its output records explicit
`verified`, `framing`, `actual_decoded_bytes`, and `full_byte_checks` fields.
The integrated validation covers the Windows configuration above.

## Replay through the public harness

Build the CUDA harness as described in [../MEASURE.md](../MEASURE.md). From its
`benchmarks/onpair-bench` directory, a bounded replay of the Windows configuration is:

```sh
NVCOMP_ZSTD_LEVELS=19 NVCOMP_ZSTD_VALUES_PER_FRAME=271 \
  uv run python run.py --datasets loghub-windows --columns line \
  --bits 12 --chunk-mb 1000 --sample-bytes 1000000000 \
  --gpu-decode --gpu-validate --gpu-iters 100 --jobs 1 --gpu-kernels production
```

Leave `ONPAIR_FAST` unset so the comparator executes. Copy the resulting
`vortex-bench/data/onpair-bench/summary.json` before another run replaces it.
From the artifact checkout, validate the saved output with:

```sh
python experiments/zstd/check-replay.py /path/to/saved-summary.json
```

This requires the requested `gpu.nvcomp_zstd` entry to have `supported: true`,
`verified: true`, level 19, values_per_frame 271, matching row/frame/compressed
counts, and positive timings. An unsupported result is a failed replay, not a
successful skipped cell. The `default` backend is nvCOMP's automatic selection;
that label alone does not identify the implementation chosen by the library.
To replay another cell, use its dataset, column, sample size, seed, level and
values-per-frame from the settings file.

## Independent framing and preparation check

These standalone tools isolate frame bytes and allocation reuse from Rust's
scheduler. On a host with the materialized Windows parquet, extract the exact
prefix (the default row count and payload SHA256 identify the historical sample):

```sh
python experiments/zstd/extract-row-lengths.py /path/to/windows.parquet \
  --output /path/to/work/windows.lengths.u64 \
  --payload-output /path/to/work/windows.payload.bin
python experiments/zstd/build-pinned-zstd.py \
  --crate /path/to/cargo/registry/src/INDEX/zstd-sys-2.0.16+zstd.1.5.7 \
  --output /path/to/work/pinned-zstd
python experiments/zstd/prepare-frames.py \
  --payload /path/to/work/windows.payload.bin --lengths /path/to/work/windows.lengths.u64 \
  --framing prefix --level 19 --values-per-frame 271 \
  --libzstd /path/to/work/pinned-zstd/libzstd-review-1.5.7.so \
  --output-prefix /path/to/work/windows19-prefix
SDK=/path/to/nvcomp-sdk OUT=/path/to/work/bin bash experiments/zstd/build.sh
/path/to/work/bin/zstd_verify /path/to/work/windows19-prefix.zrv \
  /path/to/work/windows19-prefix.expected.bin /path/to/work/prefix-timings.json \
  100 reuse,reprepare,reprepare,reuse default
```

`extract-row-lengths.py` needs PyArrow. The pinned-library builder verifies the
cached crate archive against Cargo.lock's checksum and all used vendored sources
against that archive; it requires an x86-64 C compiler. Its shared build records
compiler settings and is not claimed to be the historical binary. `build.sh`
requires nvcc and nvCOMP; `CUDA_ARCH` defaults to `native` (override, e.g. `sm_103`,
only when building for another device). No tool changes GPU clocks or provisions
machines. Record the driver, SDK, compiler, achieved clocks and input manifests
with a fresh measurement. For a flat control, repeat preparation with
`--framing flat` and a distinct output prefix.

CUDA events bracket only nvCOMP decoding. Allocation, uploads, sentinel reset,
and validation are outside the interval. Every launch checks host status, every
frame's device status and decoded size. The standalone additionally poisons the
output plus a 256-byte guard and compares all bytes on first warmup and first/last
timed iterations. These checks can affect neighboring cache state; all samples
are retained. Reprepare uses new cudaMalloc allocations per launch; reuse keeps
them for each block. This comparison does not reproduce Rust's buffer allocator
or scheduler exactly. Failures exit nonzero.
