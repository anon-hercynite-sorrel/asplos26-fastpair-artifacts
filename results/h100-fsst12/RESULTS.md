# FastPair — FSST-12 (HF columns) + split-vs-stride16 NCU

- rev `2d909147f`, host computeinstance-e00mbvy3axfn0v2pnx, GPU NVIDIA H100 80GB HBM3
- date 2026-08-13T02:15:01Z

## Phase 1 — NCU captures (split8read vs stride-16, same cell)
-rw-rw-r-- 1 ubuntu ubuntu 341010 Aug 13 01:29 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 341286 Aug 13 01:36 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_split4read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 340612 Aug 13 01:29 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 360287 Aug 13 01:32 /home/ubuntu/work/splitncu_clickbench_Referer_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 360970 Aug 13 01:31 /home/ubuntu/work/splitncu_clickbench_Referer_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 360268 Aug 13 01:34 /home/ubuntu/work/splitncu_clickbench_URL_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 377702 Aug 13 01:37 /home/ubuntu/work/splitncu_clickbench_URL_b12_split4read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 360951 Aug 13 01:33 /home/ubuntu/work/splitncu_clickbench_URL_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 362198 Aug 13 01:35 /home/ubuntu/work/splitncu_synthetic_url_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 361091 Aug 13 01:35 /home/ubuntu/work/splitncu_synthetic_url_b12_split8read_details.csv

```
clickbench_MobilePhoneModel_b12_split8read exit=0 rows=1553 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_MobilePhoneModel_b12_onpair_shmem_4tpt exit=0 rows=1569 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_Referer_b12_split8read exit=0 rows=1569 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_Referer_b12_onpair_shmem_4tpt exit=0 rows=1585 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_URL_b12_split8read exit=0 rows=1569 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_URL_b12_onpair_shmem_4tpt exit=0 rows=1585 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
synthetic_url_b12_split8read exit=0 rows=1569 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
synthetic_url_b12_onpair_shmem_4tpt exit=0 rows=1601 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_MobilePhoneModel_b12_split4read exit=0 rows=1553 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split4read Static Shared Memory Per Block=33.28B
clickbench_URL_b12_split4read exit=0 rows=1585 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split4read Static Shared Memory Per Block=33.28B
```

## Phase 2 — FSST-12 cells
| codec | bits | dataset | column | ratio | matched | GiB/s | frac_le8 | verified |
|---|---|---|---|---|---|---|---|---|
| fsst12 | 12 | amazon-electronics | text | 1.97 | 1.97 | 726 | 1.000 | True |
| fsst12 | 12 | amazon-movies | text | 1.93 | 1.93 | 714 | 1.000 | True |
| fsst12 | 12 | book-reviews | text | 1.94 | 1.94 | 716 | 1.000 | True |
| fsst12 | 12 | clickbench | MobilePhoneModel | 0.78 | 1.16 | 914 | 1.000 | True |
| fsst12 | 12 | clickbench | Referer | 1.95 | 1.96 | 723 | 1.000 | True |
| fsst12 | 12 | clickbench | SearchPhrase | 1.55 | 1.67 | 733 | 1.000 | True |
| fsst12 | 12 | clickbench | Title | 1.98 | 1.98 | 752 | 1.000 | True |
| fsst12 | 12 | clickbench | URL | 2.08 | 2.10 | 770 | 1.000 | True |
| fsst12 | 12 | fineweb | dump | 2.76 | 7.66 | 916 | 1.000 | True |
| fsst12 | 12 | fineweb | file_path | 2.70 | 3.01 | 938 | 1.000 | True |
| fsst12 | 12 | fineweb | language | 1.00 | 905.51 | 280 | 1.000 | True |
| fsst12 | 12 | fineweb | text | 1.84 | 1.84 | 672 | 1.000 | True |
| fsst12 | 12 | fineweb | url | 1.80 | 1.81 | 632 | 1.000 | True |
| fsst12 | 12 | synthetic | url | 2.56 | 3.42 | 963 | 1.000 | True |
| fsst12 | 12 | synthetic | url | 2.56 | 3.42 | 963 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_address | 1.21 | 1.22 | 546 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_comment | 2.98 | 3.60 | 995 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_mktsegment | 2.91 | 7.53 | 810 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_name | 2.21 | 2.82 | 812 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_phone | 1.62 | 1.96 | 720 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_comment | 2.49 | 2.88 | 958 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_linestatus | 0.50 | 8.00 | 407 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_returnflag | 0.50 | 4.00 | 410 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_shipinstruct | 3.38 | 11.39 | 1405 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_shipmode | 2.14 | 11.43 | 1112 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | n_comment | 0.41 | 0.42 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | n_name | 0.07 | 0.06 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_clerk | 2.50 | 3.00 | 997 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_comment | 2.83 | 3.41 | 1023 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_orderpriority | 3.36 | 11.20 | 1461 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_orderstatus | 0.50 | 4.00 | 365 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_brand | 2.67 | 6.39 | 856 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_comment | 2.02 | 2.35 | 714 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_container | 2.52 | 7.57 | 778 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_mfgr | 2.80 | 12.43 | 925 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_name | 2.59 | 3.47 | 891 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_type | 3.62 | 7.29 | 1226 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | ps_comment | 3.19 | 3.83 | 1087 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | r_comment | 0.11 | 0.11 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | r_name | 0.01 | 0.01 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_address | 1.19 | 1.20 | 224 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_comment | 2.89 | 3.48 | 516 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_name | 2.68 | 3.18 | 262 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_phone | 1.60 | 1.92 | 183 | 1.000 | True |
| fsst12 | 12 | wikipedia | text | 1.83 | 1.83 | 663 | 1.000 | True |
| fsst12 | 12 | wikipedia | title | 1.56 | 1.59 | 268 | 1.000 | True |
| fsst12 | 12 | wikipedia | url | 2.46 | 2.49 | 539 | 1.000 | True |
| onpair | 12 | amazon-electronics | text | 2.72 | None | 768 | 0.949 | True |
| onpair | 16 | amazon-electronics | text | 3.45 | None | 544 | 0.667 | True |
| onpair | 12 | amazon-movies | text | 2.48 | None | 745 | 0.962 | True |
| onpair | 16 | amazon-movies | text | 3.18 | None | 521 | 0.734 | True |
| onpair | 12 | book-reviews | text | 2.61 | None | 762 | 0.956 | True |
| onpair | 16 | book-reviews | text | 3.28 | None | 533 | 0.721 | True |
| onpair | 12 | clickbench | MobilePhoneModel | 0.72 | None | 887 | 0.991 | True |
| onpair | 16 | clickbench | MobilePhoneModel | 0.72 | None | 888 | 0.991 | True |
| onpair | 12 | clickbench | Referer | 2.47 | None | 718 | 0.875 | True |
| onpair | 16 | clickbench | Referer | 3.31 | None | 717 | 0.625 | True |
| onpair | 12 | clickbench | SearchPhrase | 2.07 | None | 872 | 0.831 | True |
| onpair | 16 | clickbench | SearchPhrase | 2.41 | None | 787 | 0.448 | True |
| onpair | 12 | clickbench | Title | 3.56 | None | 873 | 0.784 | True |
| onpair | 16 | clickbench | Title | 4.63 | None | 931 | 0.358 | True |
| onpair | 12 | clickbench | URL | 2.89 | None | 790 | 0.813 | True |
| onpair | 16 | clickbench | URL | 3.86 | None | 886 | 0.511 | True |
| onpair | 12 | fineweb | dump | 727.10 | None | 1244 | 0.000 | True |
| onpair | 16 | fineweb | dump | 726.03 | None | 1244 | 0.000 | True |
| onpair | 12 | fineweb | file_path | 6.57 | None | 1168 | 0.299 | True |
| onpair | 16 | fineweb | file_path | 6.48 | None | 1204 | 0.277 | True |
| onpair | 12 | fineweb | language | 4306.29 | None | 275 | 1.000 | True |
| onpair | 16 | fineweb | language | 4306.29 | None | 264 | 1.000 | True |
| onpair | 12 | fineweb | text | 2.26 | None | 739 | 0.985 | True |
| onpair | 16 | fineweb | text | 2.87 | None | 477 | 0.814 | True |
| onpair | 12 | fineweb | url | 2.14 | None | 615 | 0.949 | True |
| onpair | 16 | fineweb | url | 2.53 | None | 367 | 0.820 | True |
| onpair | 12 | synthetic | url | 9.73 | None | 1369 | 0.152 | True |
| onpair | 16 | synthetic | url | 9.76 | None | 1362 | 0.177 | True |
| onpair | 12 | synthetic | url | 9.73 | None | 1369 | 0.152 | True |
| onpair | 16 | synthetic | url | 9.76 | None | 1362 | 0.177 | True |
| onpair | 12 | tpch-sf10 | c_address | 1.19 | None | 542 | 1.000 | True |
| onpair | 16 | tpch-sf10 | c_address | 1.13 | None | 554 | 1.000 | True |
| onpair | 12 | tpch-sf10 | c_comment | 5.70 | None | 1073 | 0.390 | True |
| onpair | 16 | tpch-sf10 | c_comment | 5.14 | None | 756 | 0.230 | True |
| onpair | 12 | tpch-sf10 | c_mktsegment | 14.39 | None | 903 | 0.200 | True |
| onpair | 16 | tpch-sf10 | c_mktsegment | 14.39 | None | 867 | 0.200 | True |
| onpair | 12 | tpch-sf10 | c_name | 4.32 | None | 876 | 0.605 | True |
| onpair | 16 | tpch-sf10 | c_name | 4.50 | None | 970 | 0.502 | True |
| onpair | 12 | tpch-sf10 | c_phone | 2.09 | None | 665 | 1.000 | True |
| onpair | 16 | tpch-sf10 | c_phone | 2.03 | None | 298 | 1.000 | True |
| onpair | 12 | tpch-sf10 | l_comment | 4.16 | None | 1035 | 0.579 | True |
| onpair | 16 | tpch-sf10 | l_comment | 4.19 | None | 727 | 0.334 | True |
| onpair | 12 | tpch-sf10 | l_linestatus | 8.00 | None | 718 | 1.000 | True |
| onpair | 16 | tpch-sf10 | l_linestatus | 8.00 | None | 716 | 1.000 | True |
| onpair | 12 | tpch-sf10 | l_returnflag | 4.00 | None | 718 | 1.000 | True |
| onpair | 16 | tpch-sf10 | l_returnflag | 4.00 | None | 718 | 1.000 | True |
| onpair | 12 | tpch-sf10 | l_shipinstruct | 11.16 | None | 1360 | 0.400 | True |
| onpair | 16 | tpch-sf10 | l_shipinstruct | 11.16 | None | 1358 | 0.400 | True |
| onpair | 12 | tpch-sf10 | l_shipmode | 5.71 | None | 1068 | 1.000 | True |
| onpair | 16 | tpch-sf10 | l_shipmode | 5.71 | None | 1066 | 1.000 | True |
| onpair | 12 | tpch-sf10 | n_comment | 0.61 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | n_comment | 0.62 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | n_name | 0.18 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | n_name | 0.18 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | o_clerk | 5.21 | None | 1138 | 0.406 | True |
| onpair | 16 | tpch-sf10 | o_clerk | 8.52 | None | 1373 | 0.000 | True |
| onpair | 12 | tpch-sf10 | o_comment | 5.12 | None | 1101 | 0.458 | True |
| onpair | 16 | tpch-sf10 | o_comment | 5.01 | None | 687 | 0.253 | True |
| onpair | 12 | tpch-sf10 | o_orderpriority | 13.44 | None | 1290 | 0.800 | True |
| onpair | 16 | tpch-sf10 | o_orderpriority | 13.44 | None | 1241 | 0.800 | True |
| onpair | 12 | tpch-sf10 | o_orderstatus | 4.00 | None | 566 | 1.000 | True |
| onpair | 16 | tpch-sf10 | o_orderstatus | 4.00 | None | 580 | 1.000 | True |
| onpair | 12 | tpch-sf10 | p_brand | 12.78 | None | 1155 | 1.000 | True |
| onpair | 16 | tpch-sf10 | p_brand | 12.78 | None | 1147 | 1.000 | True |
| onpair | 12 | tpch-sf10 | p_comment | 3.03 | None | 719 | 0.764 | True |
| onpair | 16 | tpch-sf10 | p_comment | 2.96 | None | 542 | 0.552 | True |
| onpair | 12 | tpch-sf10 | p_container | 6.73 | None | 850 | 0.725 | True |
| onpair | 16 | tpch-sf10 | p_container | 6.73 | None | 840 | 0.725 | True |
| onpair | 12 | tpch-sf10 | p_mfgr | 37.28 | None | 1532 | 0.000 | True |
| onpair | 16 | tpch-sf10 | p_mfgr | 37.28 | None | 1506 | 0.000 | True |
| onpair | 12 | tpch-sf10 | p_name | 4.49 | None | 977 | 0.637 | True |
| onpair | 16 | tpch-sf10 | p_name | 4.68 | None | 883 | 0.266 | True |
| onpair | 12 | tpch-sf10 | p_type | 9.41 | None | 1134 | 0.303 | True |
| onpair | 16 | tpch-sf10 | p_type | 9.40 | None | 1120 | 0.411 | True |
| onpair | 12 | tpch-sf10 | ps_comment | 6.15 | None | 1179 | 0.337 | True |
| onpair | 16 | tpch-sf10 | ps_comment | 5.83 | None | 848 | 0.155 | True |
| onpair | 12 | tpch-sf10 | r_comment | 0.29 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | r_comment | 0.29 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | r_name | 0.09 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | r_name | 0.09 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | s_address | 1.17 | None | 227 | 1.000 | True |
| onpair | 16 | tpch-sf10 | s_address | 1.12 | None | 214 | 1.000 | True |
| onpair | 12 | tpch-sf10 | s_comment | 5.17 | None | 524 | 0.439 | True |
| onpair | 16 | tpch-sf10 | s_comment | 4.68 | None | 492 | 0.375 | True |
| onpair | 12 | tpch-sf10 | s_name | 5.66 | None | 265 | 0.506 | True |
| onpair | 16 | tpch-sf10 | s_name | 5.43 | None | 258 | 0.511 | True |
| onpair | 12 | tpch-sf10 | s_phone | 2.04 | None | 168 | 1.000 | True |
| onpair | 16 | tpch-sf10 | s_phone | 1.93 | None | 172 | 1.000 | True |
| onpair | 12 | wikipedia | text | 2.15 | None | 699 | 0.984 | True |
| onpair | 16 | wikipedia | text | 2.80 | None | 527 | 0.823 | True |
| onpair | 12 | wikipedia | title | 1.68 | None | 253 | 0.979 | True |
| onpair | 16 | wikipedia | title | 1.71 | None | 208 | 0.930 | True |
| onpair | 12 | wikipedia | url | 3.56 | None | 528 | 0.739 | True |
| onpair | 16 | wikipedia | url | 3.31 | None | 502 | 0.646 | True |
