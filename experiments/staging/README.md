# Shared-dictionary experiments

The companion harness builds the following experimental shared-dictionary
variants and global-dictionary control:

| Selector | Dictionary representation | Launch |
| --- | --- | --- |
| `onpair_shmem_4tpt_pdict` | Full padded 16-byte entries in shared memory | persistent K4/T256/B2 |
| `onpair_shmem_4tpt_vdict` | Variable-length bytes, offsets and lengths in shared memory | persistent K4/T256/B2 |
| `onpair_shmem_4tpt_shdict8` | Low eight-byte plane and lengths in shared memory; global high-plane fallback | persistent K4/T256/B2 |
| `onpair_shmem_4tpt_review_t256b2` | Global dictionary, plain K4 decoder | nonpersistent K4/T256/B2 control |

The last selector matches thread count and launch bound, but is not an otherwise
identical kernel: its work assignment is nonpersistent. These experiments compare
implemented designs rather than isolating a storage-location switch. `shdict8`
stages the low eight-byte plane for every dictionary entry.

## Run one column

Build using [MEASURE.md](../MEASURE.md). From the artifact root, set absolute paths:

```sh
export HARNESS=/absolute/path/to/fastpair-harness
export STAGING_COLUMN=/absolute/path/to/windows12/part_0000.vortex
export STAGING_OUT=/absolute/path/to/new-staging-run
mkdir -p "$STAGING_OUT"
```

For a Windows-12 column, compare the three staging variants, the geometry control,
and the recommended K6/T256/B4/W16 configuration:

```sh
ONPAIR_FAST=1 ONPAIR_REVIEW_STAGING_BLOCKS_PER_SM=2 \
  "$HARNESS/target/release/onpair-chunk-bench" gpu-decode-vortex \
  --vortex "$STAGING_COLUMN" --column line --gpu-iters 100 --gpu-validate \
  --gpu-kernels onpair_shmem_4tpt_pdict,onpair_shmem_4tpt_vdict,onpair_shmem_4tpt_shdict8,onpair_shmem_4tpt_review_t256b2,onpair_dw_k6_t256_b4 \
  > "$STAGING_OUT/windows12-grid2.json"
python3 experiments/staging/summarize.py "$STAGING_OUT/windows12-grid2.json"
```

The default persistent grid is `min(work_blocks, 2 * SM_count)`, preserving the
recorded launch. Repeat with `ONPAIR_REVIEW_STAGING_BLOCKS_PER_SM=4` and `8`,
saving each to a different JSON file, to measure grid sensitivity.
The option affects only the three dictionary-staging variants. It changes the
total number of launched blocks, not the hardware's concurrent residency limit.
Each block copies a dictionary before processing its work; that initialization
is included in the kernel timing.

Use identical clock, cache-carveout, input and iteration settings when comparing
these launches. Record those settings; these commands do not lock clocks. The
preserved September B300 sensitivity runs requested 2032 MHz and 100 samples
per kernel. The original paper's archived best-vs-best comparison searched a
larger global-kernel set; the short command above is a bounded recommended-versus-
staging check, not that full search.

For FSST-12, first encode the same Windows input with the harness `run` command,
using `--codec fsst12 --bits 0`; then run the same explicit selectors on its
reported column file. Add `onpair_dg_k6_t256_b4` for the W8 global baseline.
Use the ordinary one-column encoding instructions for input size, training seed,
and threshold. A 12-bit FSST dictionary and a 12-bit FastPair dictionary are
distinct input configurations and should have separate output files.

Large dictionaries can be inapplicable. The host checks the required shared
allocation; `pdict`/`vdict` retain the historical 100 KiB policy cap, while
`shdict8` uses a 224 KiB cap further limited by device capacity. An
`applicable: false` row is a capacity/policy result, not zero throughput. The
summarizer prints it explicitly and rejects applicable rows that failed byte
validation or lack raw timings.

## Reproduce the archived arithmetic without a GPU

```sh
python3 experiments/staging/summarize.py \
  results/b300-shdict-refresh-20260824/shdict_summary_op12_default.json \
  results/b300-shdict-refresh-20260824/shdict_summary_fsst12_default.json
(cd experiments/staging && sha256sum -c SHA256SUMS)
python3 experiments/staging/summarize.py experiments/staging/evidence/*-timings.json
```

The first command accepts the historical list-of-cells schema and recovers
the best measured global and staged candidates separately. It yields 25.74%
and 54.21% staged throughput deficits for the original Windows OP12 and FSST12
default-carveout records. The second dataset preserves six September sensitivity
runs (two codecs, grids 2/4/8), which used a bounded candidate set. Do not combine
the numerator from one run with the denominator from another, or substitute
the top-level `gpu.best_kernel`: that summary can exclude experimental kernels.

The larger grid improves the lower-footprint staging variants. Grid size and
dictionary capacity are separate parameters: the grid controls how many copies
of the dictionary are initialized across the device.

`source-provenance.json` records the wrapper and unchanged CUDA-body hashes.
