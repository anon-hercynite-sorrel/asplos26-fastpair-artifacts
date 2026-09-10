# Batch-offset sidecars

This directory exposes two different experiments: storing and reopening batch
offsets in a **separate Vortex file**, and regenerating those offsets on the GPU
immediately before decoding. It does not integrate a sidecar into the ordinary
serialized string column or measure a complete cascaded decoder.

The companion harness provides the persistence option. `review_gpu_regen.cu`
combines its packed decoder header with the offset-generation implementation
from `benchmarks/onpair-bench/op_gpu_regen.cu`. The source hashes are recorded in
`source-provenance.json`.

## Prerequisites

Follow [MEASURE.md](../MEASURE.md) to build `onpair-chunk-bench` and obtain the
Windows Parquet input. Run the commands below from the artifact repository root,
setting absolute paths for the companion checkout and the input file:

```sh
export HARNESS=/absolute/path/to/fastpair-harness
export WINDOWS_PARQUET=/absolute/path/to/loghub-windows.parquet
export SIDECAR_OUT=/absolute/path/to/new-sidecar-run
mkdir -p "$SIDECAR_OUT"
```

Use a fresh output directory for each run: reports append and sidecar files
reuse names for the same dataset, column, bit width, chunk and batch size.

## Store, reopen, and verify offsets (CPU)

```sh
ONPAIR_FAST=1 \
ONPAIR_OFFSET_COST="$SIDECAR_OUT/offset-cost.jsonl" \
ONPAIR_OFFSET_BATCH=192,128,32 \
ONPAIR_REVIEW_SIDECAR_DIR="$SIDECAR_OUT/persisted" \
  "$HARNESS/target/release/onpair-chunk-bench" run \
  --parquet "$WINDOWS_PARQUET" --column line --dataset-id loghub-windows \
  --bits 12 --codec onpair --chunk-bytes 1048576000 --threshold 0.2 \
  --training-seed 20260819 --sample-bytes 1000000000 \
  --file-target-bytes 200000000 --out-dir "$SIDECAR_OUT/column" \
  > "$SIDECAR_OUT/storage-summary.json"
```

For each granularity, this compresses the offset array, writes an `offsets`
column into its own Vortex file, reopens it through the normal reader, and
compares every u64 value with the source array. Failure returns a nonzero status.
The report is `persisted/sidecar-roundtrip.jsonl`. `192` codes is the K6 batch;
`128` and `32` are controls. Batch offsets exclude the final end sentinel.

Keep three byte counts distinct:

- `compressed_array_nbytes`: compressed in-memory array size, the basis of the
  historical storage estimate;
- `serialized_file_bytes`: actual separate file size, including file metadata;
- the ordinary serialized string-column size: it includes row offsets and does
  not include this separate sidecar file.

This validates standalone persistence and exact values. It does not claim that
the normal GPU loader consumes the persisted sidecar instead of preparing its
own offsets.

## Regenerate K6 offsets and decode (GPU)

Export one encoded column part with the normal validated decoder. Set
`SIDECAR_COLUMN` to the `part_0000.vortex` path reported by the previous command.
The dump contains codes, token lengths, and a padded dictionary, all for this
single part. The export path is last-writer-wins: never export a multi-bit or
multi-column sweep to one dump and then infer its identity from the filename.

```sh
export SIDECAR_COLUMN=/absolute/path/from/storage-summary/part_0000.vortex
ONPAIR_DUMP_E2E="$SIDECAR_OUT/windows12.e2ebin" \
  "$HARNESS/target/release/onpair-chunk-bench" gpu-decode-vortex \
  --vortex "$SIDECAR_COLUMN" --column line --gpu-iters 3 --gpu-validate \
  --gpu-kernels onpair_dw_k6_t256_b4 > "$SIDECAR_OUT/export.json"

# sm_103 is B300; choose the architecture supported by the target and CUDA toolkit.
for width in 16 8; do
  nvcc -O3 -arch=sm_103 -std=c++17 \
    -I"$HARNESS/vortex-cuda/kernels/src" \
    -DREVIEW_K=6 -DREVIEW_W="$width" \
    experiments/sidecar/review_gpu_regen.cu \
    -o "$SIDECAR_OUT/regen-k6-w$width"
  "$SIDECAR_OUT/regen-k6-w$width" "$SIDECAR_OUT/windows12.e2ebin" 200 \
    > "$SIDECAR_OUT/windows12-k6-w$width.json"
done
python3 experiments/sidecar/verify.py --directory "$SIDECAR_OUT"
```

The decoder uses K6/T256/B4/H1/S16 and W16 or W8. W16 is the recommended width
for this Windows-12 input; W8 is a paired control. Offset regeneration retains
the public driver's 512-thread reduction followed by a CUB exclusive scan over
192-code batch sizes. Each arm has three warmup iterations and 200 CUDA-event
samples. Device inputs are already resident; allocation, transfers, dictionary
repacking and CUB scratch allocation are outside the timings. Preserve GPU,
toolkit and clock settings with your results; clocks are not changed here.

The driver checks regenerated offsets, both decoded outputs against a CPU
reference, and 64-byte output tail guards. It times regeneration, preloaded-offset
decode, and back-to-back regeneration plus decode separately. Runtime overhead
is `combined_time / decode_time - 1`; throughput loss is
`1 - decode_time / combined_time`. These are different percentages. Compute the
combined arm directly; do not add separately minimized times. K4 is available
with `-DREVIEW_K=4`, which also changes the offset granularity to 128 codes.

## Preserved verification

`evidence/` contains the September B300 checks: Windows and Wikipedia, 12 and 16
bits, both K6 widths, 200 samples each; plus six Windows persistence roundtrips
(12/16 bits at 192/128/32 codes). Validate checksums and reported
correctness/arithmetic without a GPU:

```sh
(cd experiments/sidecar && sha256sum -c SHA256SUMS)
python3 experiments/sidecar/verify.py
```

At Windows-12/K6, the actual file was 747,280 bytes versus 744,847 bytes of
compressed array storage, with 516,099 offsets reopened exactly. The archived
runtime reports retain raw samples rather than only rounded ratios. Historical
paths within these JSON records describe the machine where they were collected;
they are not prerequisites for the commands above.

`source-provenance.json` records the source hashes tying the standalone driver
to the companion packed decoder and the original regeneration implementation.
