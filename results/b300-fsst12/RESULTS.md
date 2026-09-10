# FastPair — FSST-12 (HF columns) + split-vs-stride16 NCU

- rev `2d909147f`, host computeinstance-e03bpj65t595hscm0s, GPU NVIDIA B300 SXM6 AC
- date 2026-08-12T23:51:09Z

## Phase 1 — NCU captures (split8read vs stride-16, same cell)
-rw-rw-r-- 1 ubuntu ubuntu 346042 Aug 12 23:28 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 345515 Aug 12 23:28 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 364496 Aug 12 23:31 /home/ubuntu/work/splitncu_clickbench_Referer_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 382085 Aug 12 23:30 /home/ubuntu/work/splitncu_clickbench_Referer_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 364483 Aug 12 23:34 /home/ubuntu/work/splitncu_clickbench_URL_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 382054 Aug 12 23:33 /home/ubuntu/work/splitncu_clickbench_URL_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 366504 Aug 12 23:36 /home/ubuntu/work/splitncu_synthetic_url_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 384272 Aug 12 23:35 /home/ubuntu/work/splitncu_synthetic_url_b12_split8read_details.csv

```
clickbench_MobilePhoneModel_b12_split8read exit=0 rows=1570 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_MobilePhoneModel_b12_onpair_shmem_4tpt exit=0 rows=1587 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_Referer_b12_split8read exit=0 rows=1601 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_Referer_b12_onpair_shmem_4tpt exit=0 rows=1601 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_URL_b12_split8read exit=0 rows=1601 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_URL_b12_onpair_shmem_4tpt exit=0 rows=1601 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
synthetic_url_b12_split8read exit=0 rows=1617 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
synthetic_url_b12_onpair_shmem_4tpt exit=0 rows=1617 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
```

## Phase 2 — FSST-12 cells
| codec | bits | dataset | column | ratio | matched | GiB/s | frac_le8 | verified |
|---|---|---|---|---|---|---|---|---|
| fsst12 | 12 | amazon-electronics | text | 1.97 | 1.97 | 875 | 1.000 | True |
| fsst12 | 12 | amazon-movies | text | 1.93 | 1.93 | 858 | 1.000 | True |
| fsst12 | 12 | book-reviews | text | 1.94 | 1.94 | 868 | 1.000 | True |
| fsst12 | 12 | fineweb | dump | 2.76 | 7.66 | 930 | 1.000 | True |
| fsst12 | 12 | fineweb | file_path | 2.70 | 3.01 | 1114 | 1.000 | True |
| fsst12 | 12 | fineweb | language | 1.00 | 905.51 | 267 | 1.000 | True |
| fsst12 | 12 | fineweb | text | 1.84 | 1.84 | 815 | 1.000 | True |
| fsst12 | 12 | fineweb | url | 1.80 | 1.81 | 754 | 1.000 | True |
| fsst12 | 12 | wikipedia | text | 1.83 | 1.83 | 802 | 1.000 | True |
| fsst12 | 12 | wikipedia | title | 1.56 | 1.59 | 251 | 1.000 | True |
| fsst12 | 12 | wikipedia | url | 2.46 | 2.49 | 567 | 1.000 | True |
| onpair | 12 | amazon-electronics | text | 2.66 | None | 872 | 0.954 | True |
| onpair | 16 | amazon-electronics | text | 3.43 | None | 780 | 0.673 | True |
| onpair | 12 | amazon-movies | text | 2.52 | None | 850 | 0.960 | True |
| onpair | 16 | amazon-movies | text | 3.18 | None | 736 | 0.736 | True |
| onpair | 12 | book-reviews | text | 2.63 | None | 866 | 0.953 | True |
| onpair | 16 | book-reviews | text | 3.27 | None | 745 | 0.722 | True |
| onpair | 12 | fineweb | dump | 727.57 | None | 1241 | 0.000 | True |
| onpair | 16 | fineweb | dump | 726.40 | None | 1192 | 0.000 | True |
| onpair | 12 | fineweb | file_path | 6.06 | None | 1275 | 0.407 | True |
| onpair | 16 | fineweb | file_path | 6.58 | None | 1388 | 0.152 | True |
| onpair | 12 | fineweb | language | 4306.29 | None | 255 | 1.000 | True |
| onpair | 16 | fineweb | language | 4306.29 | None | 262 | 1.000 | True |
| onpair | 12 | fineweb | text | 2.27 | None | 850 | 0.984 | True |
| onpair | 16 | fineweb | text | 2.86 | None | 665 | 0.820 | True |
| onpair | 12 | fineweb | url | 2.14 | None | 694 | 0.950 | True |
| onpair | 16 | fineweb | url | 2.52 | None | 592 | 0.824 | True |
| onpair | 12 | wikipedia | text | 2.18 | None | 811 | 0.982 | True |
| onpair | 16 | wikipedia | text | 2.81 | None | 661 | 0.822 | True |
| onpair | 12 | wikipedia | title | 1.68 | None | 241 | 0.978 | True |
| onpair | 16 | wikipedia | title | 1.71 | None | 241 | 0.931 | True |
| onpair | 12 | wikipedia | url | 3.56 | None | 525 | 0.738 | True |
| onpair | 16 | wikipedia | url | 3.31 | None | 496 | 0.647 | True |
