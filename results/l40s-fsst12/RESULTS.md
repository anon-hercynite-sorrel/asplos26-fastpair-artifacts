# FastPair — FSST-12 (HF columns) + split-vs-stride16 NCU

- rev `2d909147f`, host computeinstance-e00fgkbvzc4hny41yz, GPU NVIDIA L40S
- date 2026-08-13T03:53:39Z

## Phase 1 — NCU captures (split8read vs stride-16, same cell)
-rw-rw-r-- 1 ubuntu ubuntu 349640 Aug 13 03:11 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 343156 Aug 13 03:17 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_split4read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 342073 Aug 13 03:10 /home/ubuntu/work/splitncu_clickbench_MobilePhoneModel_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 363301 Aug 13 03:13 /home/ubuntu/work/splitncu_clickbench_Referer_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 368318 Aug 13 03:12 /home/ubuntu/work/splitncu_clickbench_Referer_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 361321 Aug 13 03:15 /home/ubuntu/work/splitncu_clickbench_URL_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 380065 Aug 13 03:18 /home/ubuntu/work/splitncu_clickbench_URL_b12_split4read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 368301 Aug 13 03:14 /home/ubuntu/work/splitncu_clickbench_URL_b12_split8read_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 359299 Aug 13 03:16 /home/ubuntu/work/splitncu_synthetic_url_b12_onpair_shmem_4tpt_details.csv
-rw-rw-r-- 1 ubuntu ubuntu 367966 Aug 13 03:16 /home/ubuntu/work/splitncu_synthetic_url_b12_split8read_details.csv

```
clickbench_MobilePhoneModel_b12_split8read exit=0 rows=1456 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_MobilePhoneModel_b12_onpair_shmem_4tpt exit=0 rows=1489 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_Referer_b12_split8read exit=0 rows=1489 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_Referer_b12_onpair_shmem_4tpt exit=0 rows=1505 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_URL_b12_split8read exit=0 rows=1489 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
clickbench_URL_b12_onpair_shmem_4tpt exit=0 rows=1505 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
synthetic_url_b12_split8read exit=0 rows=1494 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split8read Static Shared Memory Per Block=33.28B
synthetic_url_b12_onpair_shmem_4tpt exit=0 rows=1503 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt Static Shared Memory Per Block=33.28B
clickbench_MobilePhoneModel_b12_split4read exit=0 rows=1458 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split4read Static Shared Memory Per Block=33.28B
clickbench_URL_b12_split4read exit=0 rows=1501 CAPTURE-VERIFIED kernel=onpair_shmem_4tpt_split4read Static Shared Memory Per Block=33.28B
```

## Phase 2 — FSST-12 cells
| codec | bits | dataset | column | ratio | matched | GiB/s | frac_le8 | verified |
|---|---|---|---|---|---|---|---|---|
| fsst12 | 12 | amazon-electronics | text | 1.97 | 1.97 | 377 | 1.000 | True |
| fsst12 | 12 | amazon-movies | text | 1.93 | 1.93 | 375 | 1.000 | True |
| fsst12 | 12 | book-reviews | text | 1.94 | 1.94 | 376 | 1.000 | True |
| fsst12 | 12 | clickbench | MobilePhoneModel | 0.78 | 1.16 | 814 | 1.000 | True |
| fsst12 | 12 | clickbench | Referer | 1.95 | 1.96 | 377 | 1.000 | True |
| fsst12 | 12 | clickbench | SearchPhrase | 1.55 | 1.67 | 370 | 1.000 | True |
| fsst12 | 12 | clickbench | Title | 1.98 | 1.98 | 378 | 1.000 | True |
| fsst12 | 12 | clickbench | URL | 2.08 | 2.10 | 387 | 1.000 | True |
| fsst12 | 12 | fineweb | dump | 2.76 | 7.66 | 795 | 1.000 | True |
| fsst12 | 12 | fineweb | file_path | 2.70 | 3.01 | 419 | 1.000 | True |
| fsst12 | 12 | fineweb | language | 1.00 | 905.51 | 238 | 1.000 | True |
| fsst12 | 12 | fineweb | text | 1.84 | 1.84 | 368 | 1.000 | True |
| fsst12 | 12 | fineweb | url | 1.80 | 1.81 | 377 | 1.000 | True |
| fsst12 | 12 | synthetic | url | 2.56 | 3.42 | 414 | 1.000 | True |
| fsst12 | 12 | synthetic | url | 2.56 | 3.42 | 414 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_address | 1.21 | 1.22 | 531 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_comment | 2.98 | 3.60 | 434 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_mktsegment | 2.91 | 7.53 | 767 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_name | 2.21 | 2.82 | 748 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | c_phone | 1.62 | 1.96 | 682 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_comment | 2.49 | 2.88 | 419 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_linestatus | 0.50 | 8.00 | 219 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_returnflag | 0.50 | 4.00 | 218 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_shipinstruct | 3.38 | 11.39 | 445 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | l_shipmode | 2.14 | 11.43 | 418 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | n_comment | 0.41 | 0.42 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | n_name | 0.07 | 0.06 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_clerk | 2.50 | 3.00 | 414 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_comment | 2.83 | 3.41 | 430 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_orderpriority | 3.36 | 11.20 | 458 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | o_orderstatus | 0.50 | 4.00 | 333 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_brand | 2.67 | 6.39 | 766 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_comment | 2.02 | 2.35 | 702 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_container | 2.52 | 7.57 | 689 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_mfgr | 2.80 | 12.43 | 909 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_name | 2.59 | 3.47 | 764 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | p_type | 3.62 | 7.29 | 1249 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | ps_comment | 3.19 | 3.83 | 440 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | r_comment | 0.11 | 0.11 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | r_name | 0.01 | 0.01 | 0 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_address | 1.19 | 1.20 | 189 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_comment | 2.89 | 3.48 | 473 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_name | 2.68 | 3.18 | 273 | 1.000 | True |
| fsst12 | 12 | tpch-sf10 | s_phone | 1.60 | 1.92 | 171 | 1.000 | True |
| fsst12 | 12 | wikipedia | text | 1.83 | 1.83 | 367 | 1.000 | True |
| fsst12 | 12 | wikipedia | title | 1.56 | 1.59 | 223 | 1.000 | True |
| fsst12 | 12 | wikipedia | url | 2.46 | 2.49 | 474 | 1.000 | True |
| onpair | 12 | amazon-electronics | text | 2.67 | None | 399 | 0.953 | True |
| onpair | 16 | amazon-electronics | text | 3.43 | None | 295 | 0.672 | True |
| onpair | 12 | amazon-movies | text | 2.48 | None | 392 | 0.962 | True |
| onpair | 16 | amazon-movies | text | 3.18 | None | 264 | 0.735 | True |
| onpair | 12 | book-reviews | text | 2.57 | None | 393 | 0.961 | True |
| onpair | 16 | book-reviews | text | 3.29 | None | 282 | 0.716 | True |
| onpair | 12 | clickbench | MobilePhoneModel | 0.72 | None | 814 | 0.991 | True |
| onpair | 16 | clickbench | MobilePhoneModel | 0.72 | None | 814 | 0.991 | True |
| onpair | 12 | clickbench | Referer | 2.46 | None | 396 | 0.879 | True |
| onpair | 16 | clickbench | Referer | 3.30 | None | 382 | 0.628 | True |
| onpair | 12 | clickbench | SearchPhrase | 2.08 | None | 418 | 0.829 | True |
| onpair | 16 | clickbench | SearchPhrase | 2.41 | None | 419 | 0.443 | True |
| onpair | 12 | clickbench | Title | 3.51 | None | 420 | 0.790 | True |
| onpair | 16 | clickbench | Title | 4.63 | None | 446 | 0.359 | True |
| onpair | 12 | clickbench | URL | 2.89 | None | 425 | 0.809 | True |
| onpair | 16 | clickbench | URL | 3.86 | None | 435 | 0.507 | True |
| onpair | 12 | fineweb | dump | 725.56 | None | 1192 | 0.000 | True |
| onpair | 16 | fineweb | dump | 726.23 | None | 1192 | 0.000 | True |
| onpair | 12 | fineweb | language | 4306.29 | None | 238 | 1.000 | True |
| onpair | 16 | fineweb | language | 4306.29 | None | 238 | 1.000 | True |
| onpair | 12 | fineweb | text | 2.28 | None | 383 | 0.985 | True |
| onpair | 16 | fineweb | text | 2.88 | None | 246 | 0.814 | True |
| onpair | 12 | fineweb | url | 2.14 | None | 408 | 0.950 | True |
| onpair | 16 | fineweb | url | 2.52 | None | 213 | 0.822 | True |
| onpair | 12 | synthetic | url | 9.73 | None | 502 | 0.182 | True |
| onpair | 16 | synthetic | url | 9.88 | None | 503 | 0.132 | True |
| onpair | 12 | synthetic | url | 9.73 | None | 502 | 0.182 | True |
| onpair | 16 | synthetic | url | 9.88 | None | 503 | 0.132 | True |
| onpair | 12 | tpch-sf10 | c_address | 1.19 | None | 533 | 1.000 | True |
| onpair | 16 | tpch-sf10 | c_address | 1.13 | None | 541 | 1.000 | True |
| onpair | 12 | tpch-sf10 | c_comment | 5.61 | None | 535 | 0.401 | True |
| onpair | 16 | tpch-sf10 | c_comment | 5.14 | None | 430 | 0.230 | True |
| onpair | 12 | tpch-sf10 | c_mktsegment | 14.39 | None | 877 | 0.200 | True |
| onpair | 16 | tpch-sf10 | c_mktsegment | 14.39 | None | 877 | 0.200 | True |
| onpair | 12 | tpch-sf10 | c_phone | 2.06 | None | 620 | 1.000 | True |
| onpair | 16 | tpch-sf10 | c_phone | 1.95 | None | 168 | 1.000 | True |
| onpair | 12 | tpch-sf10 | l_comment | 4.17 | None | 442 | 0.576 | True |
| onpair | 16 | tpch-sf10 | l_comment | 4.19 | None | 385 | 0.334 | True |
| onpair | 12 | tpch-sf10 | l_linestatus | 8.00 | None | 218 | 1.000 | True |
| onpair | 16 | tpch-sf10 | l_linestatus | 8.00 | None | 219 | 1.000 | True |
| onpair | 12 | tpch-sf10 | l_returnflag | 4.00 | None | 220 | 1.000 | True |
| onpair | 16 | tpch-sf10 | l_returnflag | 4.00 | None | 219 | 1.000 | True |
| onpair | 12 | tpch-sf10 | l_shipinstruct | 11.16 | None | 481 | 0.400 | True |
| onpair | 16 | tpch-sf10 | l_shipinstruct | 11.16 | None | 480 | 0.400 | True |
| onpair | 12 | tpch-sf10 | l_shipmode | 5.71 | None | 419 | 1.000 | True |
| onpair | 16 | tpch-sf10 | l_shipmode | 5.71 | None | 417 | 1.000 | True |
| onpair | 12 | tpch-sf10 | n_comment | 0.61 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | n_comment | 0.62 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | n_name | 0.18 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | n_name | 0.18 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | o_comment | 5.13 | None | 459 | 0.460 | True |
| onpair | 16 | tpch-sf10 | o_comment | 5.00 | None | 415 | 0.254 | True |
| onpair | 12 | tpch-sf10 | o_orderpriority | 13.44 | None | 498 | 0.800 | True |
| onpair | 16 | tpch-sf10 | o_orderpriority | 13.44 | None | 500 | 0.800 | True |
| onpair | 12 | tpch-sf10 | o_orderstatus | 4.00 | None | 682 | 1.000 | True |
| onpair | 16 | tpch-sf10 | o_orderstatus | 4.00 | None | 682 | 1.000 | True |
| onpair | 12 | tpch-sf10 | p_brand | 12.78 | None | 1119 | 1.000 | True |
| onpair | 16 | tpch-sf10 | p_brand | 12.78 | None | 1119 | 1.000 | True |
| onpair | 12 | tpch-sf10 | p_comment | 3.03 | None | 571 | 0.763 | True |
| onpair | 16 | tpch-sf10 | p_comment | 2.96 | None | 300 | 0.551 | True |
| onpair | 12 | tpch-sf10 | p_container | 6.73 | None | 811 | 0.725 | True |
| onpair | 16 | tpch-sf10 | p_container | 6.73 | None | 811 | 0.725 | True |
| onpair | 12 | tpch-sf10 | p_mfgr | 37.28 | None | 1498 | 0.000 | True |
| onpair | 16 | tpch-sf10 | p_mfgr | 37.28 | None | 1498 | 0.000 | True |
| onpair | 12 | tpch-sf10 | p_name | 4.53 | None | 805 | 0.622 | True |
| onpair | 16 | tpch-sf10 | p_name | 4.67 | None | 423 | 0.272 | True |
| onpair | 12 | tpch-sf10 | p_type | 9.41 | None | 1249 | 0.411 | True |
| onpair | 16 | tpch-sf10 | p_type | 9.41 | None | 1249 | 0.428 | True |
| onpair | 12 | tpch-sf10 | ps_comment | 6.17 | None | 456 | 0.335 | True |
| onpair | 16 | tpch-sf10 | ps_comment | 5.82 | None | 431 | 0.158 | True |
| onpair | 12 | tpch-sf10 | r_comment | 0.28 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | r_comment | 0.36 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | r_name | 0.09 | None | 0 | 1.000 | True |
| onpair | 16 | tpch-sf10 | r_name | 0.09 | None | 0 | 1.000 | True |
| onpair | 12 | tpch-sf10 | s_address | 1.16 | None | 206 | 1.000 | True |
| onpair | 16 | tpch-sf10 | s_address | 1.12 | None | 189 | 1.000 | True |
| onpair | 12 | tpch-sf10 | s_comment | 5.19 | None | 437 | 0.434 | True |
| onpair | 16 | tpch-sf10 | s_comment | 4.67 | None | 315 | 0.373 | True |
| onpair | 12 | tpch-sf10 | s_name | 5.70 | None | 273 | 0.504 | True |
| onpair | 16 | tpch-sf10 | s_name | 5.38 | None | 234 | 0.517 | True |
| onpair | 12 | tpch-sf10 | s_phone | 2.06 | None | 152 | 1.000 | True |
| onpair | 16 | tpch-sf10 | s_phone | 1.90 | None | 124 | 1.000 | True |
| onpair | 12 | wikipedia | text | 2.17 | None | 374 | 0.980 | True |
| onpair | 16 | wikipedia | text | 2.80 | None | 250 | 0.823 | True |
