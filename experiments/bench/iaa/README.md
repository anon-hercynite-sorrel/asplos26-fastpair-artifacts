# IAA bench + setup (#29)

The Intel IAA (In-memory Analytics Accelerator) aggregate decode benchmark — the CPU analog
of the GPU Decompression Engine. Run on a GCP `c3-standard-192-metal` (Sapphire Rapids, 8 IAA
engines). Result: `results/iaa/` (`iaa_aggregate_sapphire.txt`, `ANALYSIS.md`, `run-env.txt`).

- `iaa_bench_mt.cpp` — the multi-engine bench: T worker threads, each with its own hardware
  `qpl_job`, decode 256 KB blocks (software-compressed once, so the bytes match what OnPair sees)
  on the IAA hardware-Deflate path; reports aggregate GB/s vs thread count. Verifies byte-exact.
- `iaa_bench.cpp` — the single-WQ per-engine bench (cross-check; T=1 reproduces it).
- `iaa_mt_setup_run.sh` — **on-box** idempotent setup across the one required reboot: phase 1
  enables `intel_iommu=on,sm_on` + installs `idxd` (from `linux-modules-extra`) and reboots;
  phase 2 configures a shared WQ per device (8×128, `block_on_fault=1`), builds Intel QPL from
  source + the bench, and runs the sweep **as root** (the earlier status-503 was WQ-sizing, not
  privilege — the per-engine data was always root; mlock'd buffers + more/bigger WQs cure it).
- `iaa_drive.sh` — **laptop-side** driver: creates the metal box (with a `--max-run-duration`
  DELETE backstop), stages, runs phase 1 (reboot), waits, runs phase 2, collects, tears down.
  The reboot is why this can't use the harness's teardown-trap flow.

Run: `bash iaa_drive.sh` (drives the whole lifecycle from the laptop).
