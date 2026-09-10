# GPU benchmark source snapshots

These files are copies from the [companion harness](https://github.com/anon-hercynite-sorrel/fastpair-harness).
Build them in its `benchmarks/onpair-bench/` directory: their relative includes
depend on the harness tree. Source headers document build commands and arguments.

- `nvcomp_hw_bench.cu` measures the Blackwell hardware Decompression Engine on
  the same uncompressed column bytes used by the dictionary-codec benchmarks.
- `e2e_scan.cu` measures decode followed by substring scan. It reads an encoder
  dump produced with `ONPAIR_DUMP_E2E` and validates decode and match counts
  against a CPU reference. This supporting experiment is outside the submitted evaluation.
- `onpair_shmem_4tpt_split8read.cu` is the decode kernel reused by the scan benchmark.
  The complete kernel family is in the harness's `vortex-cuda/kernels/src/`.

The revised pipeline figure profiles the selected public-harness kernels,
not the standalone scan kernel snapshot here. Its raw capture archive,
five-bin reduction, configuration selection and reviewer capture command are
documented in [pipes/README.md](../../pipes/README.md).

See [MEASURE.md](../../MEASURE.md) for the measurement entry points and
[MANIFEST.md](../../MANIFEST.md) for the captures used by the paper.
