# CPU bench source (snapshot)

The fixed-stride vs variable-stride OnPair decode benchmark — the cross-stack story (the same
fixed-stride dictionary that minimizes GPU cache requests collapses OnPair's two-deep dependent
gather into one independent load on the CPU). Snapshot of the `onpair-cpu-bench` crate.

- `main.rs` — the bench: `fat` (fixed-stride) vs `entries` (variable-stride, the published
  OnPair) vs `naive` decode loops, over a 256 MB working set, pinned to N physical cores.
- `competitors.rs` — the stock-library competitors (FSST, Zstd, LZ4, zlib), single core.
- `extract_cols.py` — samples the column `.bin` inputs from the source parquets.
- `Cargo.toml` — crate manifest.

Build with native codegen (the inlined load/copy primitives must target the host ISA):
`RUSTFLAGS="-C target-cpu=native" cargo build --release`. Driven across the 10-generation AWS
fleet by author-machine orchestration (not shipped); also used for the IAA comparison (FastPair-CPU on Sapphire,
`results/iaa/onpair_cpu_sapphire.json`). Output: `cpu-sweep.json` (fat/entries rates + ratio).
