# `l40s-splitncu` — split8read vs stride-16 on the SAME cell

NCU `--set full`, 10 captures, all CAPTURE-VERIFIED (see `SPLITNCU_CENSUS.txt`; each capture
asserts the profiled kernel symbol matches the requested one).

This is the pairing no earlier capture set had. Every cost-surface capture profiled only the
kernel the selector chose for that cell, so no cell held both `split8read` and the stride-16
`onpair_shmem_4tpt`, and the split's mechanism could not be attributed. These captures fix
both kernels on one cell and one preset.

**Do not confuse this with `l40s-shdict-ncu`.** That set pairs `split8read` against `pdict`,
which is the SHARED-MEMORY staged dictionary (86 KB dynamic shared per block), not the global
stride-16 table. `pdict` serves its gathers from shared memory and barely touches L1, so its
sector counts and hit rates are not comparable to a stride-16 baseline.

Load-bearing metric is `l1tex__data_pipe_lsu_wavefronts.avg`: the split lowers it to ~0.72 on
a column whose long-token fallback never fires (ClickBench `MobilePhoneModel`, frac_le8 =
0.991), with sector count flat and hit rate NOT rising, which is what identifies the mechanism
as access width rather than table residency. The control (synthetic `url`, frac_le8 = 0.143)
inverts above 1.0, matching where the timing result flips.
