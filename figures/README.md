# Figures

Generate the nine figures listed in `experiments/paper-figures.txt` from the
committed measurements in [results/](../results). Run `make analyze` from the
repository root to build all figures, or `uv run figures/fig_teaser.py` to build
one. PDFs are written to `figures/out/`. No GPU is needed.

`common.py` and `suite.py` contain the loading and reduction functions shared with
`validate.py`. `suite.py` declares the named paper legs and the fifteen columns.
Its rate accessors distinguish the production selector from the best validated
kernel configuration; see [METHODOLOGY.md](../experiments/METHODOLOGY.md).

## Generated figures

| Script | Label | What it plots | Source under `results/` |
|---|---|---|---|
| `fig_teaser` | `fig:teaser` | Decode throughput on a B300 for the three codecs FastPair decodes, against the fixed-function DE at its best codec per column | `suite-paper-20260821` (+ the comparator and flat legs) |
| `fig_perf_real` | `fig:perf_real` | Decode throughput against at-rest compression ratio on a B300, real-world and generated columns | `suite-paper-20260821`, `suite-comparators-20260827`, `suite-flat-20260830` |
| `fig_perf_gen` | `fig:perf_gen` | Decode rate per column at OnPair-12 on five GPUs across five clock states — boost, locked-max, and locked at 75/55/40% | `suite-paper-20260821`, `suite-rtxpro-20260823`, `suite-flat-20260830` |
| `fig_grid` | `fig:grid` | Decode rate and blocks/SM as $K$ varies | `suite-paper-20260821` |
| `fig_pipes` | `fig:pipes` | Throughput of each unit as a fraction of its own reported peak, decoding Loghub `Windows` at OnPair-12 on five GPUs | `pipes-boost-20260909/` (selected boost captures; five L1 bins) |
| `fig_hoist` | `fig:hoist` | Decode rate as $(K,H)$ varies | `suite-paper-20260821`, `suite-hoist0-20260823` |
| `fig_gatherwidth` | `fig:gatherwidth` | Ratio of decode rates between $W=8$ and $W=16$ per column, ordered by the fraction of tokens $\leq 8$ bytes | `suite-paper-20260821` |
| `fig_lenpredict` | `fig:lenpredict` | Decode rate against mean token length on a B300 | `suite-paper-20260821`, `suite-comparators-20260827` |
| `fig_tokendist` | `fig:tokendist` | Dictionary-entry read frequency, sorted, per column, at OnPair-12 | `token-freqdist-corpus/`, `suite-paper-20260821` |

## Supporting scripts

These scripts produce or check the reduced data used by the figures. The final
pipes figure uses the [boost-capture protocol](../experiments/pipes/README.md),
including its A100/L40S estimation rules; `experiments/check_pipes.py --check`
validates the selected captures and their five-bin reduction. The older
`extract_costsurface.py` and its four-category CSVs remain historical evidence
and are not inputs to the current pipes figure.

| Script | What it does |
|---|---|
| `extract_costsurface.py` | reduces per-device Nsight Compute captures (`*-pipesncu/`, `*-ncu-v2/`) into cost-surface CSV rows, decomposing the L1 bar by LSU wavefronts into gather / drain-out / readback / emit |
| `extract_stalls.py` | reduces the same dumps into the warp-stall composition (`ncu-stalls-v2.csv`) |
| `extract_shdict.py`, `extract_shdict_ncu.py` | reduce the shared-dictionary microbenchmark legs into `shdict_summary.csv` |
| `compare_costsurface_waves.py` | checks whether the ordering of pipeline measurements agrees across captures made with different harness revisions and corpora |
| `check_occupancy_model.py` | checks the occupancy model against the per-kernel register and shared-memory footprints |
| `tab_datasets_suite.py` | generates dataset-table rows; `experiments/check_tab_datasets.py` compares them with a supplied manuscript |
