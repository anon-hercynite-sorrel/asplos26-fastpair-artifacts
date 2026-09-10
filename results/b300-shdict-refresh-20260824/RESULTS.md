# Staged-dictionary refresh — loghub-windows/line
- rev: `9ab0d327113ec3272851bd3ef03acf66ed6bf5ca`
- gpu: NVIDIA B300 SXM6 AC
- date: 2026-08-24T17:10:51Z
- arms: op12:onpair:12 op14:onpair:14 fsst12:fsst12:0   carveouts: default maxl1   iters: 100
- failures: 1

## Census
```
op12_default OK 1456051 B
op14_default OK 1413937 B
fsst12_default OK 1506489 B
op12_maxl1 OK 1509525 B
op14_maxl1 OK 1467695 B
fsst12_maxl1 OK 1552359 B
op12_default_shmem_4tpt CAPTURE-VERIFIED onpair_shmem_4tpt
op12_default_shmem_4tpt_split8read CAPTURE-VERIFIED onpair_shmem_4tpt_split8read
op12_default_shmem_4tpt_shdict8 CAPTURE-VERIFIED onpair_shmem_4tpt_shdict8
op12_default_shmem_4tpt_pdict CAPTURE-VERIFIED onpair_shmem_4tpt_pdict
op12_default_shmem_4tpt_vdict CAPTURE-VERIFIED onpair_shmem_4tpt_vdict
op12_default_shmem_4tpt_b128o12 CAPTURE-VERIFIED onpair_shmem_4tpt_b128o12
op14_default_shmem_4tpt CAPTURE-VERIFIED onpair_shmem_4tpt
op14_default_shmem_4tpt_split8read CAPTURE-VERIFIED onpair_shmem_4tpt_split8read
op14_default_shmem_4tpt_shdict8 CAPTURE-VERIFIED onpair_shmem_4tpt_shdict8
op14_default_shmem_4tpt_pdict NCU-NONE rc=1 inapplicable: padded dict needs 295168 B shared, over 102400 B cap
op14_default_shmem_4tpt_vdict NCU-NONE rc=1 inapplicable: packed dict needs 128720 B shared, over 102400 B cap
op14_default_shmem_4tpt_b128o12 CAPTURE-VERIFIED onpair_shmem_4tpt_b128o12
fsst12_default NCU-SKIP no-vortex
```

## Achieved shared split
```
# achieved shared split per capture (launch__shared_mem_config_size)
shdictref_ncu_op12_default_shmem_4tpt_b128o12_raw.csv      0.1 KB
shdictref_ncu_op12_default_shmem_4tpt_pdict_raw.csv        0.2 KB
shdictref_ncu_op12_default_shmem_4tpt_raw.csv              0.1 KB
shdictref_ncu_op12_default_shmem_4tpt_shdict8_raw.csv      0.2 KB
shdictref_ncu_op12_default_shmem_4tpt_split8read_raw.csv   0.1 KB
shdictref_ncu_op12_default_shmem_4tpt_vdict_raw.csv        0.2 KB
shdictref_ncu_op14_default_shmem_4tpt_b128o12_raw.csv      0.1 KB
shdictref_ncu_op14_default_shmem_4tpt_raw.csv              0.1 KB
shdictref_ncu_op14_default_shmem_4tpt_shdict8_raw.csv      0.2 KB
shdictref_ncu_op14_default_shmem_4tpt_split8read_raw.csv   0.1 KB
```

## Clocks
```
NVIDIA B300 SXM6 AC, 487 MHz, 3996 MHz
```
