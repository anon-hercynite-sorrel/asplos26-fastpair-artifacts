# Sidecar regeneration penalty on the current corpus

150 cells attempted, 150 validated (offsets AND decode byte-exact).

## Per column, all variants

| column | bits | ctl_k4 | k4 W=8 | k4 W=16 | k6 W=8 | k6 W=16 |
|---|---|---|---|---|---|---|
| clickbench/Title | 12 | 20.9% | 26.5% | 24.7% | 23.6% | 20.6% |
| clickbench/Title | 16 | 16.7% | 18.2% | 20.6% | 16.1% | 17.6% |
| clickbench/URL | 12 | 20.8% | 26.9% | 24.5% | 24.4% | 20.7% |
| clickbench/URL | 16 | 17.6% | 19.9% | 20.7% | 17.5% | 17.5% |
| codeparrot/content | 12 | 23.0% | 29.9% | 25.2% | 27.4% | 21.8% |
| codeparrot/content | 16 | 19.2% | 23.0% | 22.9% | 21.0% | 19.8% |
| fineweb2-zh/text | 12 | 26.8% | 32.6% | 26.1% | 30.6% | 22.8% |
| fineweb2-zh/text | 16 | 18.8% | 24.0% | 23.1% | 22.3% | 20.4% |
| loghub-android/line | 12 | 22.1% | 28.4% | 25.3% | 25.9% | 21.6% |
| loghub-android/line | 16 | 17.8% | 19.6% | 21.0% | 17.2% | 17.9% |
| loghub-hdfs/line | 12 | 20.0% | 24.3% | 23.3% | 21.6% | 19.5% |
| loghub-hdfs/line | 16 | 18.6% | 21.5% | 21.7% | 18.7% | 18.2% |
| loghub-spark/line | 12 | 18.2% | 20.8% | 21.1% | 18.0% | 17.2% |
| loghub-spark/line | 16 | 18.1% | 19.5% | 20.7% | 16.5% | 17.4% |
| loghub-thunderbird/line | 12 | 19.4% | 22.9% | 22.4% | 20.0% | 18.9% |
| loghub-thunderbird/line | 16 | 18.5% | 19.8% | 21.2% | 17.0% | 18.0% |
| loghub-windows/line | 12 | 17.6% | 20.2% | 20.6% | 17.2% | 17.3% |
| loghub-windows/line | 16 | 18.2% | 19.5% | 21.4% | 17.0% | 18.3% |
| tpch-sf15/l_comment | 12 | 19.9% | 24.1% | 23.5% | 21.0% | 19.6% |
| tpch-sf15/l_comment | 16 | 15.4% | 16.4% | 19.7% | 14.5% | 17.0% |
| tpch-sf15/l_shipinstruct | 12 | 15.9% | 18.3% | 18.6% | 15.1% | 14.5% |
| tpch-sf15/l_shipinstruct | 16 | 15.9% | 18.4% | 18.6% | 15.1% | 14.4% |
| tpch-sf15/ps_comment | 12 | 18.0% | 20.4% | 20.8% | 16.8% | 17.2% |
| tpch-sf15/ps_comment | 16 | 14.1% | 14.5% | 18.2% | 13.3% | 16.3% |
| tpch-sf263/c_address | 12 | 29.0% | 34.3% | 27.1% | 33.4% | 23.9% |
| tpch-sf263/c_address | 16 | 22.4% | 25.6% | 24.9% | 26.3% | 22.0% |
| tpch-sf45/o_clerk | 12 | 21.6% | 25.8% | 25.8% | 23.4% | 22.9% |
| tpch-sf45/o_clerk | 16 | 14.8% | 15.5% | 20.3% | 13.8% | 17.9% |
| wikipedia/text | 12 | 25.4% | 32.1% | 26.4% | 30.0% | 23.1% |
| wikipedia/text | 16 | 18.4% | 22.8% | 22.9% | 21.1% | 20.1% |

## Shipped reading (K=6, faster W per column)

| column | bits | W | decode GB/s | regen+decode GB/s | penalty |
|---|---|---|---|---|---|
| clickbench/Title | 12 | 8 | 1261 | 1020 | 23.6% |
| clickbench/Title | 16 | 16 | 1253 | 1065 | 17.6% |
| clickbench/URL | 12 | 8 | 1138 | 914 | 24.4% |
| clickbench/URL | 16 | 16 | 1195 | 1017 | 17.5% |
| codeparrot/content | 12 | 8 | 975 | 765 | 27.4% |
| codeparrot/content | 16 | 8 | 979 | 809 | 21.0% |
| fineweb2-zh/text | 12 | 8 | 893 | 684 | 30.6% |
| fineweb2-zh/text | 16 | 8 | 794 | 649 | 22.3% |
| loghub-android/line | 12 | 8 | 1067 | 847 | 25.9% |
| loghub-android/line | 16 | 16 | 1281 | 1086 | 17.9% |
| loghub-hdfs/line | 12 | 8 | 1366 | 1123 | 21.6% |
| loghub-hdfs/line | 16 | 8 | 1284 | 1081 | 18.7% |
| loghub-spark/line | 12 | 8 | 1467 | 1243 | 18.0% |
| loghub-spark/line | 16 | 16 | 1583 | 1349 | 17.4% |
| loghub-thunderbird/line | 12 | 8 | 1405 | 1171 | 20.0% |
| loghub-thunderbird/line | 16 | 16 | 1538 | 1304 | 18.0% |
| loghub-windows/line | 12 | 8 | 1530 | 1306 | 17.2% |
| loghub-windows/line | 16 | 16 | 1618 | 1368 | 18.3% |
| tpch-sf15/l_comment | 12 | 8 | 1424 | 1176 | 21.0% |
| tpch-sf15/l_comment | 16 | 16 | 1151 | 984 | 17.0% |
| tpch-sf15/l_shipinstruct | 12 | 8 | 1762 | 1531 | 15.1% |
| tpch-sf15/l_shipinstruct | 16 | 8 | 1762 | 1531 | 15.1% |
| tpch-sf15/ps_comment | 12 | 16 | 1526 | 1302 | 17.2% |
| tpch-sf15/ps_comment | 16 | 16 | 1316 | 1132 | 16.3% |
| tpch-sf263/c_address | 12 | 8 | 601 | 451 | 33.4% |
| tpch-sf263/c_address | 16 | 8 | 395 | 312 | 26.3% |
| tpch-sf45/o_clerk | 12 | 8 | 1620 | 1313 | 23.4% |
| tpch-sf45/o_clerk | 16 | 16 | 1671 | 1417 | 17.9% |
| wikipedia/text | 12 | 8 | 926 | 712 | 30.0% |
| wikipedia/text | 16 | 8 | 838 | 692 | 21.1% |

**K=6 shipped range: 15.1% to 33.4%** (median 20.0%, n=30).

K=4 control range: 14.1% to 29.0% (n=30). The paper's published 15-19% is this basis, on the retired corpus.

### Control check

On the four columns that survive from b300-campaign-0717, ctl_k4 should land near the committed cell (clickbench/URL 17.5%, tpch l_comment 15.2%, ps_comment 14.2%, l_shipinstruct 16.5% -- all at bits 12). A large gap means the box or the encode moved, not the corpus.
