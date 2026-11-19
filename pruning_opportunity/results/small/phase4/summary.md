# Phase 4: selective pruning statistics (small scale)

* `baseline`: (no selective statistics)
* `ns200`: sensor_records.timestamp_ms:nullspace:200,sensor_records.user_id:nullspace:200,lineitem.l_shipdate:nullspace:200,region.r_name:nullspace:200,part.p_size:nullspace:200,part.p_type:nullspace:200,nation.n_regionkey:nullspace:200,supplier.s_nationkey:nullspace:200,partsupp.ps_partkey:nullspace:200,parts
* `occ200`: sensor_records.timestamp_ms:occupancy:200,sensor_records.user_id:occupancy:200,lineitem.l_shipdate:occupancy:200,part.p_size:occupancy:200,nation.n_regionkey:occupancy:200,supplier.s_nationkey:occupancy:200,partsupp.ps_partkey:occupancy:200,partsupp.ps_suppkey:occupancy:200,orders.o_custkey:occupanc
* `sweep_nul20`: sensor_records.timestamp_ms:nullspace:20,sensor_records.user_id:nullspace:20
* `sweep_occ20`: sensor_records.timestamp_ms:occupancy:20,sensor_records.user_id:occupancy:20

## Row groups (counting pass, threads=1, sums over all queries and scans)

| setup | config | queries | total | pruned min/max | pruned additional | scanned, no rows | scanned, with rows | incl. optional, no rows | % of baseline no-rows pruned (common queries) | % of baseline incl.-optional no-rows pruned |
|---|---|---|---|---|---|---|---|---|---|---|
| point_unsorted | baseline | 1000 | 1221000 | 0 | 0 | 1220992 | 8 | 1220992 | 0.00 | 0.00 |
| point_unsorted | ns200 | 1000 | 1221000 | 0 | 789599 | 431393 | 8 | 431393 | 64.67 | 64.67 |
| point_unsorted | occ200 | 1000 | 1221000 | 0 | 639311 | 581681 | 8 | 581681 | 52.36 | 52.36 |
| point_unsorted | sweep_nul20 | 1000 | 1221000 | 0 | 88501 | 1132491 | 8 | 1132491 | 7.25 | 7.25 |
| point_unsorted | sweep_occ20 | 1000 | 1221000 | 0 | 87819 | 1133173 | 8 | 1133173 | 7.19 | 7.19 |
| range_seconds_unsorted | baseline | 1000 | 1221000 | 0 | 0 | 1217129 | 3871 | 1217129 | 0.00 | 0.00 |
| range_seconds_unsorted | ns200 | 1000 | 1221000 | 0 | 0 | 1217129 | 3871 | 1217129 | 0.00 | 0.00 |
| range_seconds_unsorted | occ200 | 1000 | 1221000 | 0 | 636947 | 580182 | 3871 | 580182 | 52.33 | 52.33 |
| range_minutes_unsorted | baseline | 1000 | 1221000 | 0 | 0 | 1010459 | 210541 | 1010459 | 0.00 | 0.00 |
| range_minutes_unsorted | ns200 | 1000 | 1221000 | 0 | 0 | 1010459 | 210541 | 1010459 | 0.00 | 0.00 |
| range_minutes_unsorted | occ200 | 1000 | 1221000 | 0 | 547537 | 462922 | 210541 | 462922 | 54.19 | 54.19 |
| range_hours_unsorted | baseline | 1000 | 1221000 | 0 | 0 | 13 | 1220987 | 13 | 0.00 | 0.00 |
| range_hours_unsorted | ns200 | 1000 | 1221000 | 0 | 0 | 13 | 1220987 | 13 | 0.00 | 0.00 |
| range_hours_unsorted | occ200 | 1000 | 1221000 | 0 | 7 | 6 | 1220987 | 6 | 53.85 | 53.85 |
| point_outliers | baseline | 1000 | 1221000 | 720696 | 0 | 500296 | 8 | 500296 | 0.00 | 0.00 |
| point_outliers | ns200 | 1000 | 1221000 | 720696 | 324446 | 175850 | 8 | 175850 | 64.85 | 64.85 |
| point_outliers | occ200 | 1000 | 1221000 | 720696 | 499406 | 890 | 8 | 890 | 99.82 | 99.82 |
| point_outliers | sweep_nul20 | 1000 | 1221000 | 720696 | 36490 | 463806 | 8 | 463806 | 7.29 | 7.29 |
| point_outliers | sweep_occ20 | 1000 | 1221000 | 720696 | 499315 | 981 | 8 | 981 | 99.80 | 99.80 |
| range_seconds_outliers | baseline | 1000 | 1221000 | 720696 | 0 | 499317 | 987 | 499317 | 0.00 | 0.00 |
| range_seconds_outliers | ns200 | 1000 | 1221000 | 720696 | 0 | 499317 | 987 | 499317 | 0.00 | 0.00 |
| range_seconds_outliers | occ200 | 1000 | 1221000 | 720696 | 499306 | 11 | 987 | 11 | 100.00 | 100.00 |
| range_minutes_outliers | baseline | 1000 | 1221000 | 720674 | 0 | 499304 | 1022 | 499304 | 0.00 | 0.00 |
| range_minutes_outliers | ns200 | 1000 | 1221000 | 720674 | 0 | 499304 | 1022 | 499304 | 0.00 | 0.00 |
| range_minutes_outliers | occ200 | 1000 | 1221000 | 720674 | 499304 | 0 | 1022 | 0 | 100.00 | 100.00 |
| range_hours_outliers | baseline | 1000 | 1221000 | 718996 | 0 | 499304 | 2700 | 499304 | 0.00 | 0.00 |
| range_hours_outliers | ns200 | 1000 | 1221000 | 718996 | 0 | 499304 | 2700 | 499304 | 0.00 | 0.00 |
| range_hours_outliers | occ200 | 1000 | 1221000 | 718996 | 499304 | 0 | 2700 | 0 | 100.00 | 100.00 |
| point_sorted | baseline | 1000 | 1221000 | 1220000 | 0 | 992 | 8 | 992 | 0.00 | 0.00 |
| point_sorted | ns200 | 1000 | 1221000 | 1220000 | 603 | 389 | 8 | 389 | 60.79 | 60.79 |
| point_sorted | occ200 | 1000 | 1221000 | 1220000 | 557 | 435 | 8 | 435 | 56.15 | 56.15 |
| point_sorted | sweep_nul20 | 1000 | 1221000 | 1220000 | 76 | 916 | 8 | 916 | 7.66 | 7.66 |
| point_sorted | sweep_occ20 | 1000 | 1221000 | 1220000 | 56 | 936 | 8 | 936 | 5.65 | 5.65 |
| range_seconds_sorted | baseline | 1000 | 1221000 | 1220000 | 0 | 13 | 987 | 13 | 0.00 | 0.00 |
| range_seconds_sorted | ns200 | 1000 | 1221000 | 1220000 | 0 | 13 | 987 | 13 | 0.00 | 0.00 |
| range_seconds_sorted | occ200 | 1000 | 1221000 | 1220000 | 9 | 4 | 987 | 4 | 69.23 | 69.23 |
| range_minutes_sorted | baseline | 1000 | 1221000 | 1219975 | 0 | 0 | 1025 | 0 |  |  |
| range_minutes_sorted | ns200 | 1000 | 1221000 | 1219975 | 0 | 0 | 1025 | 0 |  |  |
| range_minutes_sorted | occ200 | 1000 | 1221000 | 1219975 | 0 | 0 | 1025 | 0 |  |  |
| range_hours_sorted | baseline | 1000 | 1221000 | 1218296 | 0 | 0 | 2704 | 0 |  |  |
| range_hours_sorted | ns200 | 1000 | 1221000 | 1218296 | 0 | 0 | 2704 | 0 |  |  |
| range_hours_sorted | occ200 | 1000 | 1221000 | 1218296 | 0 | 0 | 2704 | 0 |  |  |
| cardinality_100 | baseline | 910 | 1111110 | 24557 | 0 | 530876 | 555677 | 530876 | 0.00 | 0.00 |
| cardinality_100 | occ200 | 419 | 511599 | 7975 | 247427 | 192 | 256005 | 192 | 99.92 | 99.92 |
| cardinality_100 | sweep_occ20 | 100 | 122100 | 673 | 60538 | 52 | 60837 | 52 | 99.91 | 99.91 |
| cardinality_1000 | sweep_occ20 | 100 | 122100 | 890 | 60158 | 53 | 60999 | 53 |  |  |
| cardinality_10000 | sweep_occ20 | 100 | 122100 | 0 | 9299 | 63801 | 49000 | 63801 |  |  |
| cardinality_100000 | baseline | 200 | 244200 | 43 | 0 | 225710 | 18447 | 225710 | 0.00 | 0.00 |
| cardinality_100000 | occ200 | 200 | 244200 | 43 | 130117 | 95593 | 18447 | 95593 | 57.65 | 57.65 |
| cardinality_100000 | sweep_occ20 | 100 | 122100 | 43 | 9143 | 103694 | 9220 | 103694 | 8.10 | 8.10 |
| tpch | baseline | 22 | 18699 | 4 | 0 | 0 | 18695 | 0 |  |  |
| tpch | ns200 | 22 | 18699 | 4 | 0 | 0 | 18695 | 0 |  |  |
| tpch | occ200 | 22 | 18699 | 4 | 0 | 0 | 18695 | 0 |  |  |
| tpcds | baseline | 99 | 67240 | 16423 | 0 | 578 | 50239 | 740 | 0.00 | 0.00 |
| tpcds | ns200 | 99 | 67240 | 16423 | 461 | 173 | 50183 | 279 | 70.07 | 62.30 |
| tpcds | occ200 | 99 | 67240 | 16423 | 468 | 167 | 50182 | 272 | 71.11 | 63.24 |
| clickbench | baseline | 43 | 5535 | 822 | 0 | 627 | 4086 | 761 | 0.00 | 0.00 |
| clickbench | ns200 | 43 | 5535 | 822 | 6 | 621 | 4086 | 755 | 0.96 | 0.79 |
| clickbench | occ200 | 43 | 5535 | 822 | 6 | 621 | 4086 | 755 | 0.96 | 0.79 |

Invariant `total = pruned + no_rows + with_rows + partial + not_reached`, `pruned = pruned_minmax + pruned_additional`: baseline: 0 invariant violations []; ns200: 0 invariant violations []; occ200: 0 invariant violations []; sweep_nul20: 0 invariant violations []; sweep_occ20: 0 invariant violations []

## Result check (order-independent result hash vs. baseline counting pass)

| config | mode | queries | equal (vs. baseline count) | different | no reference | not ok | equal (vs. baseline, same mode) | different (same mode) |
|---|---|---|---|---|---|---|---|---|
| baseline | check | 864 | 853 | 11 | 0 | 0 | 864 | 0 |
| baseline | count | 12812 | 12812 | 0 | 0 | 0 | 12812 | 0 |
| baseline_rerun | check | 142 | 131 | 11 | 0 | 0 | 130 | 12 |
| ns200 | check | 164 | 154 | 10 | 0 | 0 | 154 | 10 |
| ns200 | count | 12164 | 12164 | 0 | 0 | 0 | 12164 | 0 |
| occ200 | check | 864 | 853 | 11 | 0 | 0 | 853 | 11 |
| occ200 | count | 12636 | 12636 | 0 | 0 | 0 | 12636 | 0 |
| sweep_nul20 | count | 3000 | 3000 | 0 | 0 | 0 | 3000 | 0 |
| sweep_occ20 | count | 3400 | 3200 | 0 | 200 | 0 | 3200 | 0 |

## Query runtimes (time mode: median per query over rounds x sessions, engine-side elapsed)

| setup | config | queries | sum of medians (ms) | mean (ms) | harness wall (ms) | stat consultation (ms) | speedup vs. baseline |
|---|---|---|---|---|---|---|---|
| point_unsorted | baseline | 100 | 2195.62 | 21.96 | 2231.41 | 0 | 1.00 |
| point_unsorted | baseline_b | 100 | 2336.56 | 23.37 | 2355.90 | 0 | 0.94 |
| point_unsorted | baseline_c | 100 | 2224.78 | 22.25 | 2238.48 | 0 | 0.99 |
| point_unsorted | baseline_d | 100 | 1942.17 | 19.42 | 1950.66 | 0 | 1.13 |
| point_unsorted | baseline_e | 100 | 1887.93 | 18.88 | 1922.67 | 0 | 1.16 |
| point_unsorted | occts200 | 100 | 2036.76 | 20.37 | 2065.70 | 3004.52 | 1.08 |
| point_unsorted | occts200_b | 100 | 2900.08 | 29.00 | 2911.07 | 3920.62 | 0.76 |
| point_unsorted | occts200_c | 100 | 2419.03 | 24.19 | 2391.03 | 3484.89 | 0.91 |
| point_unsorted | stock | 100 | 1918.73 | 19.19 | 1918.73 | 0 | 1.14 |
| point_unsorted | stock_b | 100 | 1858.42 | 18.58 | 1858.42 | 0 | 1.18 |
| point_unsorted | stock_c | 100 | 2376.54 | 23.77 | 2376.54 | 0 | 0.92 |
| point_unsorted | stock_d | 100 | 1644.08 | 16.44 | 1644.08 | 0 | 1.34 |
| point_unsorted | stock_e | 100 | 1985.25 | 19.85 | 1985.25 | 0 | 1.11 |
| range_seconds_unsorted | baseline | 100 | 2255.85 | 22.56 | 2304.70 | 0 | 1.00 |
| range_seconds_unsorted | baseline_b | 100 | 2446.33 | 24.46 | 2488.33 | 0 | 0.92 |
| range_seconds_unsorted | baseline_c | 100 | 2539.75 | 25.40 | 2586.55 | 0 | 0.89 |
| range_seconds_unsorted | occts200 | 100 | 2270.31 | 22.70 | 2327.76 | 3001.27 | 0.99 |
| range_seconds_unsorted | occts200_b | 100 | 2419.81 | 24.20 | 2445.99 | 3296.60 | 0.93 |
| range_seconds_unsorted | occts200_c | 100 | 2648.24 | 26.48 | 2660.77 | 3633.61 | 0.85 |
| range_seconds_unsorted | stock | 100 | 2069.09 | 20.69 | 2069.09 | 0 | 1.09 |
| range_seconds_unsorted | stock_b | 100 | 1939.58 | 19.40 | 1939.58 | 0 | 1.16 |
| range_seconds_unsorted | stock_c | 100 | 2221.32 | 22.21 | 2221.32 | 0 | 1.02 |
| range_minutes_unsorted | baseline | 100 | 3471.75 | 34.72 | 3525.18 | 0 | 1.00 |
| range_minutes_unsorted | baseline_b | 100 | 3500.76 | 35.01 | 3594.55 | 0 | 0.99 |
| range_minutes_unsorted | baseline_c | 100 | 3221.03 | 32.21 | 3318.15 | 0 | 1.08 |
| range_minutes_unsorted | baseline_d | 100 | 2525.98 | 25.26 | 2576.90 | 0 | 1.37 |
| range_minutes_unsorted | baseline_e | 100 | 2395.60 | 23.96 | 2437.15 | 0 | 1.45 |
| range_minutes_unsorted | occts200 | 100 | 2642.03 | 26.42 | 2718.36 | 3001.39 | 1.31 |
| range_minutes_unsorted | occts200_b | 100 | 3421.27 | 34.21 | 3538.35 | 3679.37 | 1.01 |
| range_minutes_unsorted | occts200_c | 100 | 3376.45 | 33.76 | 3408.97 | 3801.98 | 1.03 |
| range_minutes_unsorted | stock | 100 | 2652.59 | 26.53 | 2652.59 | 0 | 1.31 |
| range_minutes_unsorted | stock_b | 100 | 2382.29 | 23.82 | 2382.29 | 0 | 1.46 |
| range_minutes_unsorted | stock_c | 100 | 3019.64 | 30.20 | 3019.64 | 0 | 1.15 |
| range_minutes_unsorted | stock_d | 100 | 2070.57 | 20.71 | 2070.57 | 0 | 1.68 |
| range_minutes_unsorted | stock_e | 100 | 2629.49 | 26.29 | 2629.49 | 0 | 1.32 |
| point_outliers | baseline | 100 | 1169.12 | 11.69 | 1219.68 | 0 | 1.00 |
| point_outliers | baseline_b | 100 | 1308.97 | 13.09 | 1315.79 | 0 | 0.89 |
| point_outliers | baseline_c | 100 | 1328.35 | 13.28 | 1323.75 | 0 | 0.88 |
| point_outliers | occts200 | 100 | 712.97 | 7.13 | 738.91 | 925.83 | 1.64 |
| point_outliers | occts200_b | 100 | 864.19 | 8.64 | 866.14 | 1052.90 | 1.35 |
| point_outliers | occts200_c | 100 | 626.57 | 6.27 | 648.69 | 851.28 | 1.87 |
| point_outliers | stock | 100 | 1105.77 | 11.06 | 1105.77 | 0 | 1.06 |
| point_outliers | stock_b | 100 | 1326.33 | 13.26 | 1326.33 | 0 | 0.88 |
| point_outliers | stock_c | 100 | 991.88 | 9.92 | 991.88 | 0 | 1.18 |
| range_seconds_outliers | baseline | 100 | 1238.80 | 12.39 | 1311.76 | 0 | 1.00 |
| range_seconds_outliers | baseline_b | 100 | 1243.12 | 12.43 | 1258.45 | 0 | 1.00 |
| range_seconds_outliers | baseline_c | 100 | 1379.88 | 13.80 | 1337.03 | 0 | 0.90 |
| range_seconds_outliers | occts200 | 100 | 815.20 | 8.15 | 864.49 | 974.91 | 1.52 |
| range_seconds_outliers | occts200_b | 100 | 869.01 | 8.69 | 890.37 | 1079.08 | 1.43 |
| range_seconds_outliers | occts200_c | 100 | 630.05 | 6.30 | 632.51 | 849.81 | 1.97 |
| range_seconds_outliers | stock | 100 | 1133.72 | 11.34 | 1133.72 | 0 | 1.09 |
| range_seconds_outliers | stock_b | 100 | 1118.28 | 11.18 | 1118.28 | 0 | 1.11 |
| range_seconds_outliers | stock_c | 100 | 1133.15 | 11.33 | 1133.15 | 0 | 1.09 |
| range_minutes_outliers | baseline | 100 | 1262.72 | 12.63 | 1260.38 | 0 | 1.00 |
| range_minutes_outliers | baseline_b | 100 | 1180.10 | 11.80 | 1198.56 | 0 | 1.07 |
| range_minutes_outliers | baseline_c | 100 | 1252.25 | 12.52 | 1312.88 | 0 | 1.01 |
| range_minutes_outliers | occts200 | 100 | 669.94 | 6.70 | 673.96 | 906.47 | 1.88 |
| range_minutes_outliers | occts200_b | 100 | 903.72 | 9.04 | 956.28 | 1036.97 | 1.40 |
| range_minutes_outliers | occts200_c | 100 | 664.67 | 6.65 | 699.71 | 861.50 | 1.90 |
| range_minutes_outliers | stock | 100 | 1236.22 | 12.36 | 1236.22 | 0 | 1.02 |
| range_minutes_outliers | stock_b | 100 | 1188.29 | 11.88 | 1188.29 | 0 | 1.06 |
| range_minutes_outliers | stock_c | 100 | 934.08 | 9.34 | 934.08 | 0 | 1.35 |

## Ingest (COPY elapsed: median over sessions; statistics: buffering + building, per column)

| config | mode | group | table | column | statistic | sessions | COPY ms (median) | COPY ms (min) | COPY wall ms | buffer ms | build ms | bytes | row groups |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | check | clickbench | checkpoint |  |  | 1 | 53.19 | 53.19 | 70.41 |  |  |  |  |
| baseline | check | clickbench | hits |  |  | 1 | 68959.84 | 68959.84 | 69013.83 |  |  |  |  |
| baseline | check | micro_cardinality_100 | checkpoint |  |  | 1 | 70.30 | 70.30 | 24.50 |  |  |  |  |
| baseline | check | micro_cardinality_100 | sensor_records |  |  | 1 | 10892.05 | 10892.05 | 10916.90 |  |  |  |  |
| baseline | check | micro_cardinality_100000 | checkpoint |  |  | 1 | 3.02 | 3.02 | 1.44 |  |  |  |  |
| baseline | check | micro_cardinality_100000 | sensor_records |  |  | 1 | 8237.58 | 8237.58 | 8261.53 |  |  |  |  |
| baseline | check | micro_outliers | checkpoint |  |  | 1 | 81.85 | 81.85 | 74.67 |  |  |  |  |
| baseline | check | micro_outliers | sensor_records |  |  | 1 | 12577.07 | 12577.07 | 12613.23 |  |  |  |  |
| baseline | check | micro_sorted | checkpoint |  |  | 1 | 3.92 | 3.92 | 2.01 |  |  |  |  |
| baseline | check | micro_sorted | sensor_records |  |  | 1 | 17036.83 | 17036.83 | 17065.39 |  |  |  |  |
| baseline | check | micro_unsorted | checkpoint |  |  | 1 | 2.09 | 2.09 | 7.05 |  |  |  |  |
| baseline | check | micro_unsorted | sensor_records |  |  | 1 | 13565.71 | 13565.71 | 13589.52 |  |  |  |  |
| baseline | check | tpcds | call_center |  |  | 1 | 67.13 | 67.13 | 92.53 |  |  |  |  |
| baseline | check | tpcds | catalog_page |  |  | 1 | 257.42 | 257.42 | 1120.01 |  |  |  |  |
| baseline | check | tpcds | catalog_returns |  |  | 1 | 2317.36 | 2317.36 | 1232.50 |  |  |  |  |
| baseline | check | tpcds | catalog_sales |  |  | 1 | 16866.59 | 16866.59 | 16905.57 |  |  |  |  |
| baseline | check | tpcds | checkpoint |  |  | 1 | 532.02 | 532.02 | 566.87 |  |  |  |  |
| baseline | check | tpcds | customer |  |  | 1 | 1605.90 | 1605.90 | 1581.76 |  |  |  |  |
| baseline | check | tpcds | customer_address |  |  | 1 | 1032.78 | 1032.78 | 1044.35 |  |  |  |  |
| baseline | check | tpcds | customer_demographics |  |  | 1 | 11762.16 | 11762.16 | 11762.93 |  |  |  |  |
| baseline | check | tpcds | date_dim |  |  | 1 | 2480.92 | 2480.92 | 2494.26 |  |  |  |  |
| baseline | check | tpcds | household_demographics |  |  | 1 | 582.80 | 582.80 | 579.47 |  |  |  |  |
| baseline | check | tpcds | income_band |  |  | 1 | 83.91 | 83.91 | 80.27 |  |  |  |  |
| baseline | check | tpcds | inventory |  |  | 1 | 18244.56 | 18244.56 | 18262.96 |  |  |  |  |
| baseline | check | tpcds | item |  |  | 1 | 612.62 | 612.62 | 609.95 |  |  |  |  |
| baseline | check | tpcds | promotion |  |  | 1 | 46.69 | 46.69 | 44.84 |  |  |  |  |
| baseline | check | tpcds | reason |  |  | 1 | 31.49 | 31.49 | 34.46 |  |  |  |  |
| baseline | check | tpcds | ship_mode |  |  | 1 | 14.23 | 14.23 | 14.53 |  |  |  |  |
| baseline | check | tpcds | store |  |  | 1 | 13.63 | 13.63 | 14.04 |  |  |  |  |
| baseline | check | tpcds | store_returns |  |  | 1 | 2498.27 | 2498.27 | 2518.38 |  |  |  |  |
| baseline | check | tpcds | store_sales |  |  | 1 | 18248.88 | 18248.88 | 18259.25 |  |  |  |  |
| baseline | check | tpcds | time_dim |  |  | 1 | 363.98 | 363.98 | 361.60 |  |  |  |  |
| baseline | check | tpcds | warehouse |  |  | 1 | 11.57 | 11.57 | 10.13 |  |  |  |  |
| baseline | check | tpcds | web_page |  |  | 1 | 14.48 | 14.48 | 16.97 |  |  |  |  |
| baseline | check | tpcds | web_returns |  |  | 1 | 404.91 | 404.91 | 402.03 |  |  |  |  |
| baseline | check | tpcds | web_sales |  |  | 1 | 4704.27 | 4704.27 | 4705.88 |  |  |  |  |
| baseline | check | tpcds | web_site |  |  | 1 | 29.53 | 29.53 | 29.98 |  |  |  |  |
| baseline | check | tpch | checkpoint |  |  | 1 | 337.60 | 337.60 | 338.31 |  |  |  |  |
| baseline | check | tpch | customer |  |  | 1 | 2140.50 | 2140.50 | 2160.14 |  |  |  |  |
| baseline | check | tpch | lineitem |  |  | 1 | 67118.34 | 67118.34 | 67126.94 |  |  |  |  |
| baseline | check | tpch | nation |  |  | 1 | 80.81 | 80.81 | 73.61 |  |  |  |  |
| baseline | check | tpch | orders |  |  | 1 | 12385.26 | 12385.26 | 12421.95 |  |  |  |  |
| baseline | check | tpch | part |  |  | 1 | 2729.35 | 2729.35 | 2731.22 |  |  |  |  |
| baseline | check | tpch | partsupp |  |  | 1 | 6818.24 | 6818.24 | 6841.06 |  |  |  |  |
| baseline | check | tpch | region |  |  | 1 | 43.43 | 43.43 | 32.90 |  |  |  |  |
| baseline | check | tpch | supplier |  |  | 1 | 220.67 | 220.67 | 219.53 |  |  |  |  |
| baseline | count | clickbench | checkpoint |  |  | 1 | 1.32 | 1.32 | 7.17 |  |  |  |  |
| baseline | count | clickbench | hits |  |  | 1 | 38164.51 | 38164.51 | 38177.96 |  |  |  |  |
| baseline | count | micro_cardinality_100 | checkpoint |  |  | 1 | 0.71 | 0.71 | 0.96 |  |  |  |  |
| baseline | count | micro_cardinality_100 | sensor_records |  |  | 1 | 11130.43 | 11130.43 | 11131.73 |  |  |  |  |
| baseline | count | micro_cardinality_100000 | checkpoint |  |  | 1 | 0.37 | 0.37 | 0.44 |  |  |  |  |
| baseline | count | micro_cardinality_100000 | sensor_records |  |  | 1 | 16133.42 | 16133.42 | 16134.19 |  |  |  |  |
| baseline | count | micro_outliers | checkpoint |  |  | 1 | 0.37 | 0.37 | 0.66 |  |  |  |  |
| baseline | count | micro_outliers | sensor_records |  |  | 1 | 15286.70 | 15286.70 | 15288.12 |  |  |  |  |
| baseline | count | micro_sorted | checkpoint |  |  | 1 | 7.46 | 7.46 | 7.71 |  |  |  |  |
| baseline | count | micro_sorted | sensor_records |  |  | 1 | 4873.08 | 4873.08 | 4874.53 |  |  |  |  |
| baseline | count | micro_unsorted | checkpoint |  |  | 1 | 1.88 | 1.88 | 4.33 |  |  |  |  |
| baseline | count | micro_unsorted | sensor_records |  |  | 1 | 12036.98 | 12036.98 | 12045.35 |  |  |  |  |
| baseline | count | tpcds | call_center |  |  | 1 | 116.83 | 116.83 | 118.52 |  |  |  |  |
| baseline | count | tpcds | catalog_page |  |  | 1 | 466.43 | 466.43 | 480.65 |  |  |  |  |
| baseline | count | tpcds | catalog_returns |  |  | 1 | 1800.06 | 1800.06 | 1787.72 |  |  |  |  |
| baseline | count | tpcds | catalog_sales |  |  | 1 | 13143.17 | 13143.17 | 13158.25 |  |  |  |  |
| baseline | count | tpcds | checkpoint |  |  | 1 | 313.75 | 313.75 | 327.31 |  |  |  |  |
| baseline | count | tpcds | customer |  |  | 1 | 1965.93 | 1965.93 | 1973.11 |  |  |  |  |
| baseline | count | tpcds | customer_address |  |  | 1 | 881.16 | 881.16 | 867.83 |  |  |  |  |
| baseline | count | tpcds | customer_demographics |  |  | 1 | 8898.55 | 8898.55 | 8982.77 |  |  |  |  |
| baseline | count | tpcds | date_dim |  |  | 1 | 1720.75 | 1720.75 | 1643.36 |  |  |  |  |
| baseline | count | tpcds | household_demographics |  |  | 1 | 55.51 | 55.51 | 56.88 |  |  |  |  |
| baseline | count | tpcds | income_band |  |  | 1 | 23.09 | 23.09 | 23.51 |  |  |  |  |
| baseline | count | tpcds | inventory |  |  | 1 | 16568.33 | 16568.33 | 16601.28 |  |  |  |  |
| baseline | count | tpcds | item |  |  | 1 | 1534.84 | 1534.84 | 1544.06 |  |  |  |  |
| baseline | count | tpcds | promotion |  |  | 1 | 143.17 | 143.17 | 140.76 |  |  |  |  |
| baseline | count | tpcds | reason |  |  | 1 | 122.60 | 122.60 | 117.42 |  |  |  |  |
| baseline | count | tpcds | ship_mode |  |  | 1 | 43.24 | 43.24 | 43.31 |  |  |  |  |
| baseline | count | tpcds | store |  |  | 1 | 45.17 | 45.17 | 69.76 |  |  |  |  |
| baseline | count | tpcds | store_returns |  |  | 1 | 4815.37 | 4815.37 | 4835.83 |  |  |  |  |
| baseline | count | tpcds | store_sales |  |  | 1 | 17028.16 | 17028.16 | 17029.56 |  |  |  |  |
| baseline | count | tpcds | time_dim |  |  | 1 | 323.26 | 323.26 | 323.35 |  |  |  |  |
| baseline | count | tpcds | warehouse |  |  | 1 | 9.71 | 9.71 | 9.79 |  |  |  |  |
| baseline | count | tpcds | web_page |  |  | 1 | 15.37 | 15.37 | 15.65 |  |  |  |  |
| baseline | count | tpcds | web_returns |  |  | 1 | 410.50 | 410.50 | 410.82 |  |  |  |  |
| baseline | count | tpcds | web_sales |  |  | 1 | 3344.89 | 3344.89 | 3345.93 |  |  |  |  |
| baseline | count | tpcds | web_site |  |  | 1 | 15.22 | 15.22 | 15.27 |  |  |  |  |
| baseline | count | tpch | checkpoint |  |  | 1 | 240.15 | 240.15 | 240.34 |  |  |  |  |
| baseline | count | tpch | customer |  |  | 1 | 1881.21 | 1881.21 | 1885.73 |  |  |  |  |
| baseline | count | tpch | lineitem |  |  | 1 | 94149.26 | 94149.26 | 94461.59 |  |  |  |  |
| baseline | count | tpch | nation |  |  | 1 | 273.20 | 273.20 | 156.76 |  |  |  |  |
| baseline | count | tpch | orders |  |  | 1 | 21920.62 | 21920.62 | 21771.27 |  |  |  |  |
| baseline | count | tpch | part |  |  | 1 | 2637.84 | 2637.84 | 2641.22 |  |  |  |  |
| baseline | count | tpch | partsupp |  |  | 1 | 6778.68 | 6778.68 | 6782.68 |  |  |  |  |
| baseline | count | tpch | region |  |  | 1 | 23.56 | 23.56 | 21.55 |  |  |  |  |
| baseline | count | tpch | supplier |  |  | 1 | 179.47 | 179.47 | 182.38 |  |  |  |  |
| baseline | time | micro_outliers | checkpoint |  |  | 1 | 2.73 | 2.73 | 1.96 |  |  |  |  |
| baseline | time | micro_outliers | sensor_records |  |  | 1 | 8619.09 | 8619.09 | 8641.59 |  |  |  |  |
| baseline | time | micro_unsorted | checkpoint |  |  | 1 | 2.59 | 2.59 | 10.00 |  |  |  |  |
| baseline | time | micro_unsorted | sensor_records |  |  | 1 | 9578.44 | 9578.44 | 9595.63 |  |  |  |  |
| baseline_b | time | micro_outliers | checkpoint |  |  | 1 | 5.61 | 5.61 | 9.15 |  |  |  |  |
| baseline_b | time | micro_outliers | sensor_records |  |  | 1 | 28673.19 | 28673.19 | 28706.67 |  |  |  |  |
| baseline_b | time | micro_unsorted | checkpoint |  |  | 1 | 4.60 | 4.60 | 4.27 |  |  |  |  |
| baseline_b | time | micro_unsorted | sensor_records |  |  | 1 | 18925.35 | 18925.35 | 18951.79 |  |  |  |  |
| baseline_c | time | micro_outliers | checkpoint |  |  | 1 | 2.96 | 2.96 | 12.70 |  |  |  |  |
| baseline_c | time | micro_outliers | sensor_records |  |  | 1 | 31877.07 | 31877.07 | 32079.67 |  |  |  |  |
| baseline_c | time | micro_unsorted | checkpoint |  |  | 1 | 182.26 | 182.26 | 168.05 |  |  |  |  |
| baseline_c | time | micro_unsorted | sensor_records |  |  | 1 | 35733.13 | 35733.13 | 35776.04 |  |  |  |  |
| baseline_d | time | micro_unsorted | checkpoint |  |  | 1 | 18.95 | 18.95 | 6.20 |  |  |  |  |
| baseline_d | time | micro_unsorted | sensor_records |  |  | 1 | 15074.41 | 15074.41 | 15127.94 |  |  |  |  |
| baseline_e | time | micro_unsorted | checkpoint |  |  | 1 | 13.40 | 13.40 | 11.25 |  |  |  |  |
| baseline_e | time | micro_unsorted | sensor_records |  |  | 1 | 16448.17 | 16448.17 | 16459.49 |  |  |  |  |
| baseline_rerun | check | clickbench | checkpoint |  |  | 1 | 19.23 | 19.23 | 12.64 |  |  |  |  |
| baseline_rerun | check | clickbench | hits |  |  | 1 | 87440.86 | 87440.86 | 87512.94 |  |  |  |  |
| baseline_rerun | check | tpcds | call_center |  |  | 1 | 85.02 | 85.02 | 90.36 |  |  |  |  |
| baseline_rerun | check | tpcds | catalog_page |  |  | 1 | 320.92 | 320.92 | 319.34 |  |  |  |  |
| baseline_rerun | check | tpcds | catalog_returns |  |  | 1 | 1780.81 | 1780.81 | 1784.27 |  |  |  |  |
| baseline_rerun | check | tpcds | catalog_sales |  |  | 1 | 32218.63 | 32218.63 | 32229.64 |  |  |  |  |
| baseline_rerun | check | tpcds | checkpoint |  |  | 1 | 528.68 | 528.68 | 587.72 |  |  |  |  |
| baseline_rerun | check | tpcds | customer |  |  | 1 | 1973.67 | 1973.67 | 1981.01 |  |  |  |  |
| baseline_rerun | check | tpcds | customer_address |  |  | 1 | 1556.05 | 1556.05 | 1598.68 |  |  |  |  |
| baseline_rerun | check | tpcds | customer_demographics |  |  | 1 | 19883.18 | 19883.18 | 19865.30 |  |  |  |  |
| baseline_rerun | check | tpcds | date_dim |  |  | 1 | 3114.21 | 3114.21 | 3134.06 |  |  |  |  |
| baseline_rerun | check | tpcds | household_demographics |  |  | 1 | 77.80 | 77.80 | 77.66 |  |  |  |  |
| baseline_rerun | check | tpcds | income_band |  |  | 1 | 22.90 | 22.90 | 60.19 |  |  |  |  |
| baseline_rerun | check | tpcds | inventory |  |  | 1 | 28737.11 | 28737.11 | 28713.83 |  |  |  |  |
| baseline_rerun | check | tpcds | item |  |  | 1 | 521.89 | 521.89 | 519.59 |  |  |  |  |
| baseline_rerun | check | tpcds | promotion |  |  | 1 | 21.95 | 21.95 | 22.48 |  |  |  |  |
| baseline_rerun | check | tpcds | reason |  |  | 1 | 16.40 | 16.40 | 16.86 |  |  |  |  |
| baseline_rerun | check | tpcds | ship_mode |  |  | 1 | 19.02 | 19.02 | 19.48 |  |  |  |  |
| baseline_rerun | check | tpcds | store |  |  | 1 | 33.86 | 33.86 | 36.89 |  |  |  |  |
| baseline_rerun | check | tpcds | store_returns |  |  | 1 | 3034.48 | 3034.48 | 3035.49 |  |  |  |  |
| baseline_rerun | check | tpcds | store_sales |  |  | 1 | 24722.94 | 24722.94 | 24730.30 |  |  |  |  |
| baseline_rerun | check | tpcds | time_dim |  |  | 1 | 558.24 | 558.24 | 561.98 |  |  |  |  |
| baseline_rerun | check | tpcds | warehouse |  |  | 1 | 13.17 | 13.17 | 8.73 |  |  |  |  |
| baseline_rerun | check | tpcds | web_page |  |  | 1 | 21.97 | 21.97 | 22.27 |  |  |  |  |
| baseline_rerun | check | tpcds | web_returns |  |  | 1 | 538.94 | 538.94 | 543.52 |  |  |  |  |
| baseline_rerun | check | tpcds | web_sales |  |  | 1 | 7506.80 | 7506.80 | 7514.33 |  |  |  |  |
| baseline_rerun | check | tpcds | web_site |  |  | 1 | 38.60 | 38.60 | 39.03 |  |  |  |  |
| ns200 | check | clickbench | checkpoint |  |  | 1 | 6.75 | 6.75 | 13.35 |  |  |  |  |
| ns200 | check | clickbench | hits |  |  | 1 | 164836.43 | 164836.43 | 164920.77 |  |  |  |  |
| ns200 | check | clickbench | hits | advengineid | nullspace:200 | 1 |  |  |  | 19.54 | 55.70 | 5416 | 122 |
| ns200 | check | clickbench | hits | counterid | nullspace:200 | 1 |  |  |  | 20.22 | 63.23 | 2048 | 122 |
| ns200 | check | clickbench | hits | dontcounthits | nullspace:200 | 1 |  |  |  | 18.30 | 52.28 | 4880 | 122 |
| ns200 | check | clickbench | hits | eventtime | nullspace:200 | 1 |  |  |  | 21.16 | 8931.32 | 194976 | 122 |
| ns200 | check | clickbench | hits | isdownload | nullspace:200 | 1 |  |  |  | 20.56 | 50.86 | 3176 | 122 |
| ns200 | check | clickbench | hits | islink | nullspace:200 | 1 |  |  |  | 20.09 | 50.44 | 3392 | 122 |
| ns200 | check | clickbench | hits | isrefresh | nullspace:200 | 1 |  |  |  | 311.52 | 64.31 | 4880 | 122 |
| ns200 | check | clickbench | hits | mobilephonemodel | nullspace:200 | 1 |  |  |  | 5.41 | 26.33 | 4912 | 122 |
| ns200 | check | clickbench | hits | referer | nullspace:200 | 1 |  |  |  | 73.73 | 4262.43 | 195072 | 122 |
| ns200 | check | clickbench | hits | refererhash | nullspace:200 | 1 |  |  |  | 20.90 | 4284.59 | 195144 | 122 |
| ns200 | check | clickbench | hits | searchphrase | nullspace:200 | 1 |  |  |  | 9.10 | 298.44 | 123488 | 122 |
| ns200 | check | clickbench | hits | title | nullspace:200 | 1 |  |  |  | 110.67 | 1970.06 | 187032 | 122 |
| ns200 | check | clickbench | hits | traficsourceid | nullspace:200 | 1 |  |  |  | 23.20 | 66.97 | 9552 | 122 |
| ns200 | check | clickbench | hits | url | nullspace:200 | 1 |  |  |  | 85.55 | 7433.35 | 195128 | 122 |
| ns200 | check | clickbench | hits | urlhash | nullspace:200 | 1 |  |  |  | 25.59 | 7732.27 | 195144 | 122 |
| ns200 | check | clickbench | hits | userid | nullspace:200 | 1 |  |  |  | 19.60 | 1550.61 | 195200 | 122 |
| ns200 | check | tpcds | call_center |  |  | 1 | 174.69 | 174.69 | 175.78 |  |  |  |  |
| ns200 | check | tpcds | catalog_page |  |  | 1 | 854.74 | 854.74 | 857.75 |  |  |  |  |
| ns200 | check | tpcds | catalog_returns |  |  | 1 | 8196.91 | 8196.91 | 8212.61 |  |  |  |  |
| ns200 | check | tpcds | catalog_sales |  |  | 1 | 96642.48 | 96642.48 | 96701.34 |  |  |  |  |
| ns200 | check | tpcds | checkpoint |  |  | 1 | 631.48 | 631.48 | 640.94 |  |  |  |  |
| ns200 | check | tpcds | customer |  |  | 1 | 7897.75 | 7897.75 | 7824.75 |  |  |  |  |
| ns200 | check | tpcds | customer_address |  |  | 1 | 2073.31 | 2073.31 | 2035.89 |  |  |  |  |
| ns200 | check | tpcds | customer_demographics |  |  | 1 | 38517.75 | 38517.75 | 38618.98 |  |  |  |  |
| ns200 | check | tpcds | date_dim |  |  | 1 | 3354.85 | 3354.85 | 3361.26 |  |  |  |  |
| ns200 | check | tpcds | household_demographics |  |  | 1 | 97.80 | 97.80 | 91.95 |  |  |  |  |
| ns200 | check | tpcds | income_band |  |  | 1 | 23.43 | 23.43 | 15.21 |  |  |  |  |
| ns200 | check | tpcds | inventory |  |  | 1 | 201922.17 | 201922.17 | 201967.72 |  |  |  |  |
| ns200 | check | tpcds | item |  |  | 1 | 1213.09 | 1213.09 | 1170.78 |  |  |  |  |
| ns200 | check | tpcds | promotion |  |  | 1 | 25.99 | 25.99 | 23.95 |  |  |  |  |
| ns200 | check | tpcds | reason |  |  | 1 | 16.58 | 16.58 | 18.50 |  |  |  |  |
| ns200 | check | tpcds | ship_mode |  |  | 1 | 18.45 | 18.45 | 18.70 |  |  |  |  |
| ns200 | check | tpcds | store |  |  | 1 | 28.43 | 28.43 | 30.30 |  |  |  |  |
| ns200 | check | tpcds | store_returns |  |  | 1 | 13304.97 | 13304.97 | 13313.40 |  |  |  |  |
| ns200 | check | tpcds | store_sales |  |  | 1 | 164032.59 | 164032.59 | 164065.55 |  |  |  |  |
| ns200 | check | tpcds | time_dim |  |  | 1 | 1785.47 | 1785.47 | 1753.70 |  |  |  |  |
| ns200 | check | tpcds | warehouse |  |  | 1 | 16.23 | 16.23 | 15.86 |  |  |  |  |
| ns200 | check | tpcds | web_page |  |  | 1 | 57.99 | 57.99 | 57.66 |  |  |  |  |
| ns200 | check | tpcds | web_returns |  |  | 1 | 2745.56 | 2745.56 | 2746.35 |  |  |  |  |
| ns200 | check | tpcds | web_sales |  |  | 1 | 37428.41 | 37428.41 | 37444.68 |  |  |  |  |
| ns200 | check | tpcds | web_site |  |  | 1 | 92.97 | 92.97 | 76.42 |  |  |  |  |
| ns200 | check | tpcds | call_center | cc_county | nullspace:200 | 1 |  |  |  | 0.07 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | catalog_page | cp_catalog_page_sk | nullspace:200 | 1 |  |  |  | 0.11 | 109.69 | 1600 | 1 |
| ns200 | check | tpcds | catalog_returns | cr_catalog_page_sk | nullspace:200 | 1 |  |  |  | 1.43 | 319.51 | 27200 | 17 |
| ns200 | check | tpcds | catalog_returns | cr_item_sk | nullspace:200 | 1 |  |  |  | 0.78 | 1432.96 | 27168 | 17 |
| ns200 | check | tpcds | catalog_returns | cr_order_number | nullspace:200 | 1 |  |  |  | 2.72 | 1448.11 | 27152 | 17 |
| ns200 | check | tpcds | catalog_returns | cr_return_amount | nullspace:200 | 1 |  |  |  | 3.66 | 1629.95 | 27136 | 17 |
| ns200 | check | tpcds | catalog_returns | cr_returned_date_sk | nullspace:200 | 1 |  |  |  | 0.72 | 118.10 | 27176 | 17 |
| ns200 | check | tpcds | catalog_sales | cs_bill_addr_sk | nullspace:200 | 1 |  |  |  | 9.64 | 2675.85 | 280000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_bill_customer_sk | nullspace:200 | 1 |  |  |  | 11.45 | 2630.64 | 280000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_bill_hdemo_sk | nullspace:200 | 1 |  |  |  | 10.48 | 2582.60 | 280000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_call_center_sk | nullspace:200 | 1 |  |  |  | 14.90 | 76.01 | 8424 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_catalog_page_sk | nullspace:200 | 1 |  |  |  | 9.48 | 1005.31 | 277144 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_item_sk | nullspace:200 | 1 |  |  |  | 13.01 | 12875.44 | 279552 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_net_paid | nullspace:200 | 1 |  |  |  | 7.20 | 17279.50 | 279544 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_net_profit | nullspace:200 | 1 |  |  |  | 67.22 | 17850.69 | 279336 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_order_number | nullspace:200 | 1 |  |  |  | 7.10 | 2678.58 | 280000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_promo_sk | nullspace:200 | 1 |  |  |  | 8.75 | 447.65 | 280000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_quantity | nullspace:200 | 1 |  |  |  | 7.57 | 211.24 | 133000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_ship_addr_sk | nullspace:200 | 1 |  |  |  | 8.15 | 2667.22 | 280000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_ship_customer_sk | nullspace:200 | 1 |  |  |  | 10.35 | 2660.44 | 280000 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_ship_date_sk | nullspace:200 | 1 |  |  |  | 9.48 | 172.34 | 131456 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_ship_mode_sk | nullspace:200 | 1 |  |  |  | 8.30 | 125.67 | 30800 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_sold_date_sk | nullspace:200 | 1 |  |  |  | 9.25 | 72.42 | 19672 | 175 |
| ns200 | check | tpcds | catalog_sales | cs_warehouse_sk | nullspace:200 | 1 |  |  |  | 8.61 | 100.59 | 11200 | 175 |
| ns200 | check | tpcds | customer | c_birth_month | nullspace:200 | 1 |  |  |  | 0.73 | 6.93 | 1440 | 12 |
| ns200 | check | tpcds | customer | c_current_addr_sk | nullspace:200 | 1 |  |  |  | 0.42 | 1178.36 | 19152 | 12 |
| ns200 | check | tpcds | customer | c_current_hdemo_sk | nullspace:200 | 1 |  |  |  | 0.55 | 904.93 | 19168 | 12 |
| ns200 | check | tpcds | customer | c_customer_id | nullspace:200 | 1 |  |  |  | 1.78 | 1105.09 | 19112 | 12 |
| ns200 | check | tpcds | customer | c_customer_sk | nullspace:200 | 1 |  |  |  | 0.43 | 1104.42 | 19136 | 12 |
| ns200 | check | tpcds | customer | c_first_sales_date_sk | nullspace:200 | 1 |  |  |  | 0.55 | 655.19 | 19200 | 12 |
| ns200 | check | tpcds | customer | c_first_shipto_date_sk | nullspace:200 | 1 |  |  |  | 0.51 | 646.25 | 19200 | 12 |
| ns200 | check | tpcds | customer | c_preferred_cust_flag | nullspace:200 | 1 |  |  |  | 2.40 | 7.32 | 480 | 12 |
| ns200 | check | tpcds | customer_address | ca_address_sk | nullspace:200 | 1 |  |  |  | 0.21 | 648.98 | 9568 | 6 |
| ns200 | check | tpcds | customer_address | ca_city | nullspace:200 | 1 |  |  |  | 1.74 | 89.74 | 9600 | 6 |
| ns200 | check | tpcds | customer_address | ca_country | nullspace:200 | 1 |  |  |  | 1.90 | 4.26 | 96 | 6 |
| ns200 | check | tpcds | customer_address | ca_county | nullspace:200 | 1 |  |  |  | 1.89 | 106.39 | 9600 | 6 |
| ns200 | check | tpcds | customer_address | ca_gmt_offset | nullspace:200 | 1 |  |  |  | 0.84 | 4.60 | 432 | 6 |
| ns200 | check | tpcds | customer_address | ca_state | nullspace:200 | 1 |  |  |  | 1.58 | 6.12 | 2400 | 6 |
| ns200 | check | tpcds | customer_address | ca_zip | nullspace:200 | 1 |  |  |  | 1.84 | 194.14 | 9600 | 6 |
| ns200 | check | tpcds | customer_demographics | cd_demo_sk | nullspace:200 | 1 |  |  |  | 11.21 | 21696.75 | 372832 | 234 |
| ns200 | check | tpcds | customer_demographics | cd_education_status | nullspace:200 | 1 |  |  |  | 54.43 | 116.32 | 18720 | 234 |
| ns200 | check | tpcds | customer_demographics | cd_gender | nullspace:200 | 1 |  |  |  | 44.88 | 101.07 | 9360 | 234 |
| ns200 | check | tpcds | customer_demographics | cd_marital_status | nullspace:200 | 1 |  |  |  | 44.83 | 103.84 | 14976 | 234 |
| ns200 | check | tpcds | date_dim | d_date | nullspace:200 | 1 |  |  |  | 0.23 | 694.89 | 12744 | 8 |
| ns200 | check | tpcds | date_dim | d_date_sk | nullspace:200 | 1 |  |  |  | 0.78 | 653.51 | 12752 | 8 |
| ns200 | check | tpcds | date_dim | d_dom | nullspace:200 | 1 |  |  |  | 0.67 | 5.46 | 2048 | 8 |
| ns200 | check | tpcds | date_dim | d_dow | nullspace:200 | 1 |  |  |  | 0.64 | 3.29 | 640 | 8 |
| ns200 | check | tpcds | date_dim | d_month_seq | nullspace:200 | 1 |  |  |  | 0.95 | 9.12 | 12800 | 8 |
| ns200 | check | tpcds | date_dim | d_moy | nullspace:200 | 1 |  |  |  | 1.01 | 2.87 | 960 | 8 |
| ns200 | check | tpcds | date_dim | d_qoy | nullspace:200 | 1 |  |  |  | 0.61 | 2.70 | 448 | 8 |
| ns200 | check | tpcds | date_dim | d_quarter_name | nullspace:200 | 1 |  |  |  | 1.90 | 3.23 | 5544 | 8 |
| ns200 | check | tpcds | date_dim | d_week_seq | nullspace:200 | 1 |  |  |  | 0.58 | 117.46 | 12800 | 8 |
| ns200 | check | tpcds | date_dim | d_year | nullspace:200 | 1 |  |  |  | 0.69 | 3.07 | 1624 | 8 |
| ns200 | check | tpcds | household_demographics | hd_buy_potential | nullspace:200 | 1 |  |  |  | 1.53 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | household_demographics | hd_demo_sk | nullspace:200 | 1 |  |  |  | 0.07 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | household_demographics | hd_dep_count | nullspace:200 | 1 |  |  |  | 1.75 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | household_demographics | hd_income_band_sk | nullspace:200 | 1 |  |  |  | 0.32 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | household_demographics | hd_vehicle_count | nullspace:200 | 1 |  |  |  | 0.87 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | income_band | ib_lower_bound | nullspace:200 | 1 |  |  |  | 3.48 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | income_band | ib_upper_bound | nullspace:200 | 1 |  |  |  | 0.10 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | inventory | inv_date_sk | nullspace:200 | 1 |  |  |  | 62.25 | 458.23 | 29168 | 1433 |
| ns200 | check | tpcds | inventory | inv_item_sk | nullspace:200 | 1 |  |  |  | 59.89 | 133691.27 | 2281848 | 1433 |
| ns200 | check | tpcds | inventory | inv_quantity_on_hand | nullspace:200 | 1 |  |  |  | 435.88 | 22620.76 | 2292800 | 1433 |
| ns200 | check | tpcds | inventory | inv_warehouse_sk | nullspace:200 | 1 |  |  |  | 47.22 | 535.54 | 54200 | 1433 |
| ns200 | check | tpcds | item | i_category | nullspace:200 | 1 |  |  |  | 0.75 | 0.81 | 208 | 2 |
| ns200 | check | tpcds | item | i_class | nullspace:200 | 1 |  |  |  | 1.57 | 1.50 | 1504 | 2 |
| ns200 | check | tpcds | item | i_color | nullspace:200 | 1 |  |  |  | 0.52 | 1.25 | 1408 | 2 |
| ns200 | check | tpcds | item | i_current_price | nullspace:200 | 1 |  |  |  | 0.24 | 52.13 | 3200 | 2 |
| ns200 | check | tpcds | item | i_item_id | nullspace:200 | 1 |  |  |  | 0.63 | 139.68 | 3200 | 2 |
| ns200 | check | tpcds | item | i_item_sk | nullspace:200 | 1 |  |  |  | 0.42 | 196.31 | 3192 | 2 |
| ns200 | check | tpcds | item | i_manager_id | nullspace:200 | 1 |  |  |  | 0.22 | 1.69 | 1520 | 2 |
| ns200 | check | tpcds | item | i_manufact | nullspace:200 | 1 |  |  |  | 0.84 | 33.15 | 3200 | 2 |
| ns200 | check | tpcds | item | i_manufact_id | nullspace:200 | 1 |  |  |  | 0.14 | 35.66 | 3200 | 2 |
| ns200 | check | tpcds | promotion | p_channel_tv | nullspace:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | reason | r_reason_desc | nullspace:200 | 1 |  |  |  | 0.09 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | reason | r_reason_sk | nullspace:200 | 1 |  |  |  | 0.03 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | ship_mode | sm_carrier | nullspace:200 | 1 |  |  |  | 0.03 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store | s_city | nullspace:200 | 1 |  |  |  | 0.07 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store | s_county | nullspace:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store | s_market_id | nullspace:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store | s_number_employees | nullspace:200 | 1 |  |  |  | 0.09 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store | s_state | nullspace:200 | 1 |  |  |  | 0.07 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store | s_store_name | nullspace:200 | 1 |  |  |  | 0.02 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store | s_store_sk | nullspace:200 | 1 |  |  |  | 0.10 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | store_returns | sr_cdemo_sk | nullspace:200 | 1 |  |  |  | 0.88 | 2656.00 | 55864 | 35 |
| ns200 | check | tpcds | store_returns | sr_customer_sk | nullspace:200 | 1 |  |  |  | 0.92 | 1733.31 | 55952 | 35 |
| ns200 | check | tpcds | store_returns | sr_item_sk | nullspace:200 | 1 |  |  |  | 2.03 | 1584.00 | 55832 | 35 |
| ns200 | check | tpcds | store_returns | sr_return_amt | nullspace:200 | 1 |  |  |  | 0.96 | 2257.10 | 55872 | 35 |
| ns200 | check | tpcds | store_returns | sr_returned_date_sk | nullspace:200 | 1 |  |  |  | 1.26 | 633.92 | 56000 | 35 |
| ns200 | check | tpcds | store_returns | sr_store_sk | nullspace:200 | 1 |  |  |  | 0.91 | 15.05 | 2520 | 35 |
| ns200 | check | tpcds | store_returns | sr_ticket_number | nullspace:200 | 1 |  |  |  | 0.88 | 2146.44 | 55968 | 35 |
| ns200 | check | tpcds | store_sales | ss_addr_sk | nullspace:200 | 1 |  |  |  | 14.90 | 4829.91 | 561600 | 351 |
| ns200 | check | tpcds | store_sales | ss_customer_sk | nullspace:200 | 1 |  |  |  | 14.33 | 4634.99 | 561600 | 351 |
| ns200 | check | tpcds | store_sales | ss_hdemo_sk | nullspace:200 | 1 |  |  |  | 17.51 | 4855.36 | 561600 | 351 |
| ns200 | check | tpcds | store_sales | ss_item_sk | nullspace:200 | 1 |  |  |  | 12.99 | 22375.90 | 559904 | 351 |
| ns200 | check | tpcds | store_sales | ss_net_paid | nullspace:200 | 1 |  |  |  | 14.01 | 32525.40 | 560136 | 351 |
| ns200 | check | tpcds | store_sales | ss_net_profit | nullspace:200 | 1 |  |  |  | 17.06 | 32640.60 | 560224 | 351 |
| ns200 | check | tpcds | store_sales | ss_promo_sk | nullspace:200 | 1 |  |  |  | 14.87 | 768.16 | 561600 | 351 |
| ns200 | check | tpcds | store_sales | ss_quantity | nullspace:200 | 1 |  |  |  | 24.25 | 396.28 | 266760 | 351 |
| ns200 | check | tpcds | store_sales | ss_sold_date_sk | nullspace:200 | 1 |  |  |  | 19.84 | 4904.06 | 561600 | 351 |
| ns200 | check | tpcds | store_sales | ss_sold_time_sk | nullspace:200 | 1 |  |  |  | 15.79 | 4639.44 | 561600 | 351 |
| ns200 | check | tpcds | store_sales | ss_store_sk | nullspace:200 | 1 |  |  |  | 15.89 | 149.08 | 25272 | 351 |
| ns200 | check | tpcds | store_sales | ss_ticket_number | nullspace:200 | 1 |  |  |  | 11.68 | 4701.33 | 561600 | 351 |
| ns200 | check | tpcds | time_dim | t_hour | nullspace:200 | 1 |  |  |  | 0.27 | 2.14 | 496 | 10 |
| ns200 | check | tpcds | time_dim | t_meal_time | nullspace:200 | 1 |  |  |  | 0.90 | 1.24 | 112 | 7 |
| ns200 | check | tpcds | time_dim | t_minute | nullspace:200 | 1 |  |  |  | 0.26 | 2.44 | 4720 | 10 |
| ns200 | check | tpcds | time_dim | t_time | nullspace:200 | 1 |  |  |  | 0.35 | 632.11 | 15952 | 10 |
| ns200 | check | tpcds | time_dim | t_time_sk | nullspace:200 | 1 |  |  |  | 0.59 | 664.75 | 15952 | 10 |
| ns200 | check | tpcds | web_page | wp_char_count | nullspace:200 | 1 |  |  |  | 0.00 | 0.00 | 0 | 0 |
| ns200 | check | tpcds | web_returns | wr_item_sk | nullspace:200 | 1 |  |  |  | 1.58 | 336.02 | 12752 | 8 |
| ns200 | check | tpcds | web_returns | wr_order_number | nullspace:200 | 1 |  |  |  | 0.84 | 504.29 | 12784 | 8 |
| ns200 | check | tpcds | web_returns | wr_return_amt | nullspace:200 | 1 |  |  |  | 1.31 | 524.96 | 12760 | 8 |
| ns200 | check | tpcds | web_returns | wr_returned_date_sk | nullspace:200 | 1 |  |  |  | 0.30 | 143.86 | 12800 | 8 |
| ns200 | check | tpcds | web_returns | wr_web_page_sk | nullspace:200 | 1 |  |  |  | 1.63 | 4.27 | 3776 | 8 |
| ns200 | check | tpcds | web_sales | ws_bill_addr_sk | nullspace:200 | 1 |  |  |  | 4.96 | 1027.03 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_item_sk | nullspace:200 | 1 |  |  |  | 4.54 | 4616.71 | 138784 | 87 |
| ns200 | check | tpcds | web_sales | ws_net_paid | nullspace:200 | 1 |  |  |  | 4.96 | 7757.06 | 138832 | 87 |
| ns200 | check | tpcds | web_sales | ws_net_profit | nullspace:200 | 1 |  |  |  | 3.52 | 7406.97 | 138840 | 87 |
| ns200 | check | tpcds | web_sales | ws_order_number | nullspace:200 | 1 |  |  |  | 4.62 | 1058.52 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_promo_sk | nullspace:200 | 1 |  |  |  | 5.21 | 172.21 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_quantity | nullspace:200 | 1 |  |  |  | 3.44 | 82.48 | 66120 | 87 |
| ns200 | check | tpcds | web_sales | ws_ship_addr_sk | nullspace:200 | 1 |  |  |  | 4.81 | 1035.48 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_ship_customer_sk | nullspace:200 | 1 |  |  |  | 3.96 | 1053.76 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_ship_date_sk | nullspace:200 | 1 |  |  |  | 4.24 | 1696.94 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_ship_hdemo_sk | nullspace:200 | 1 |  |  |  | 3.57 | 1054.16 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_ship_mode_sk | nullspace:200 | 1 |  |  |  | 4.42 | 49.39 | 15312 | 87 |
| ns200 | check | tpcds | web_sales | ws_sold_date_sk | nullspace:200 | 1 |  |  |  | 4.76 | 1009.33 | 139200 | 87 |
| ns200 | check | tpcds | web_sales | ws_warehouse_sk | nullspace:200 | 1 |  |  |  | 4.49 | 40.78 | 5568 | 87 |
| ns200 | check | tpcds | web_sales | ws_web_page_sk | nullspace:200 | 1 |  |  |  | 4.04 | 61.60 | 41064 | 87 |
| ns200 | check | tpcds | web_sales | ws_web_site_sk | nullspace:200 | 1 |  |  |  | 4.72 | 53.95 | 21576 | 87 |
| ns200 | check | tpcds | web_site | web_company_name | nullspace:200 | 1 |  |  |  | 0.19 | 0.00 | 0 | 0 |
| ns200 | check | tpch | checkpoint |  |  | 1 | 557.78 | 557.78 | 563.50 |  |  |  |  |
| ns200 | check | tpch | customer |  |  | 1 | 8993.81 | 8993.81 | 9005.76 |  |  |  |  |
| ns200 | check | tpch | lineitem |  |  | 1 | 385806.53 | 385806.53 | 385989.27 |  |  |  |  |
| ns200 | check | tpch | nation |  |  | 1 | 162.60 | 162.60 | 23.18 |  |  |  |  |
| ns200 | check | tpch | orders |  |  | 1 | 76603.89 | 76603.89 | 76627.57 |  |  |  |  |
| ns200 | check | tpch | part |  |  | 1 | 5047.86 | 5047.86 | 5022.05 |  |  |  |  |
| ns200 | check | tpch | partsupp |  |  | 1 | 20558.71 | 20558.71 | 20662.11 |  |  |  |  |
| ns200 | check | tpch | region |  |  | 1 | 64.83 | 64.83 | 15.30 |  |  |  |  |
| ns200 | check | tpch | supplier |  |  | 1 | 502.39 | 502.39 | 468.20 |  |  |  |  |
| ns200 | check | tpch | customer | c_acctbal | nullspace:200 | 1 |  |  |  | 3.46 | 1739.07 | 28776 | 18 |
| ns200 | check | tpch | customer | c_custkey | nullspace:200 | 1 |  |  |  | 3.37 | 1600.15 | 28712 | 18 |
| ns200 | check | tpch | customer | c_mktsegment | nullspace:200 | 1 |  |  |  | 8.22 | 15.55 | 1152 | 18 |
| ns200 | check | tpch | customer | c_nationkey | nullspace:200 | 1 |  |  |  | 3.84 | 24.95 | 3888 | 18 |
| ns200 | check | tpch | customer | c_phone | nullspace:200 | 1 |  |  |  | 7.06 | 1798.18 | 28672 | 18 |
| ns200 | check | tpch | lineitem | l_commitdate | nullspace:200 | 1 |  |  |  | 25.96 | 48760.66 | 1171200 | 732 |
| ns200 | check | tpch | lineitem | l_discount | nullspace:200 | 1 |  |  |  | 114.78 | 460.24 | 81984 | 732 |
| ns200 | check | tpch | lineitem | l_orderkey | nullspace:200 | 1 |  |  |  | 31.87 | 15578.88 | 1171152 | 732 |
| ns200 | check | tpch | lineitem | l_partkey | nullspace:200 | 1 |  |  |  | 28.83 | 70435.92 | 1169704 | 732 |
| ns200 | check | tpch | lineitem | l_quantity | nullspace:200 | 1 |  |  |  | 26.58 | 599.79 | 292800 | 732 |
| ns200 | check | tpch | lineitem | l_receiptdate | nullspace:200 | 1 |  |  |  | 25.88 | 50899.76 | 1171192 | 732 |
| ns200 | check | tpch | lineitem | l_returnflag | nullspace:200 | 1 |  |  |  | 167.99 | 328.61 | 35136 | 732 |
| ns200 | check | tpch | lineitem | l_shipdate | nullspace:200 | 1 |  |  |  | 30.17 | 50424.25 | 1171184 | 732 |
| ns200 | check | tpch | lineitem | l_shipinstruct | nullspace:200 | 1 |  |  |  | 199.43 | 431.29 | 40992 | 732 |
| ns200 | check | tpch | lineitem | l_shipmode | nullspace:200 | 1 |  |  |  | 174.44 | 442.02 | 58560 | 732 |
| ns200 | check | tpch | lineitem | l_suppkey | nullspace:200 | 1 |  |  |  | 23.91 | 47069.06 | 1169520 | 732 |
| ns200 | check | tpch | nation | n_name | nullspace:200 | 1 |  |  |  | 0.04 | 0.00 | 0 | 0 |
| ns200 | check | tpch | nation | n_regionkey | nullspace:200 | 1 |  |  |  | 0.04 | 0.00 | 0 | 0 |
| ns200 | check | tpch | orders | o_comment | nullspace:200 | 1 |  |  |  | 61.65 | 14768.37 | 291984 | 183 |
| ns200 | check | tpch | orders | o_custkey | nullspace:200 | 1 |  |  |  | 6.38 | 15118.58 | 292296 | 183 |
| ns200 | check | tpch | orders | o_orderdate | nullspace:200 | 1 |  |  |  | 6.50 | 10503.38 | 292800 | 183 |
| ns200 | check | tpch | orders | o_orderkey | nullspace:200 | 1 |  |  |  | 8.83 | 15160.32 | 291536 | 183 |
| ns200 | check | tpch | orders | o_orderstatus | nullspace:200 | 1 |  |  |  | 33.08 | 75.19 | 8784 | 183 |
| ns200 | check | tpch | part | p_brand | nullspace:200 | 1 |  |  |  | 2.54 | 14.01 | 5184 | 24 |
| ns200 | check | tpch | part | p_container | nullspace:200 | 1 |  |  |  | 7.48 | 16.37 | 7872 | 24 |
| ns200 | check | tpch | part | p_name | nullspace:200 | 1 |  |  |  | 6.60 | 2084.41 | 38224 | 24 |
| ns200 | check | tpch | part | p_size | nullspace:200 | 1 |  |  |  | 3.07 | 14.29 | 9600 | 24 |
| ns200 | check | tpch | part | p_type | nullspace:200 | 1 |  |  |  | 8.45 | 20.63 | 26688 | 24 |
| ns200 | check | tpch | partsupp | ps_partkey | nullspace:200 | 1 |  |  |  | 3.25 | 1963.01 | 155184 | 97 |
| ns200 | check | tpch | partsupp | ps_suppkey | nullspace:200 | 1 |  |  |  | 3.02 | 8600.20 | 154456 | 97 |
| ns200 | check | tpch | region | r_name | nullspace:200 | 1 |  |  |  | 0.00 | 0.00 | 0 | 0 |
| ns200 | check | tpch | supplier | s_comment | nullspace:200 | 1 |  |  |  | 0.52 | 108.50 | 1592 | 1 |
| ns200 | check | tpch | supplier | s_nationkey | nullspace:200 | 1 |  |  |  | 0.11 | 0.57 | 216 | 1 |
| ns200 | check | tpch | supplier | s_suppkey | nullspace:200 | 1 |  |  |  | 0.09 | 104.37 | 1600 | 1 |
| ns200 | count | clickbench | checkpoint |  |  | 1 | 8.20 | 8.20 | 8.15 |  |  |  |  |
| ns200 | count | clickbench | hits |  |  | 1 | 145440.18 | 145440.18 | 145476.10 |  |  |  |  |
| ns200 | count | clickbench | hits | advengineid | nullspace:200 | 1 |  |  |  | 12.43 | 74.46 | 5416 | 122 |
| ns200 | count | clickbench | hits | counterid | nullspace:200 | 1 |  |  |  | 15.67 | 65.59 | 2048 | 122 |
| ns200 | count | clickbench | hits | dontcounthits | nullspace:200 | 1 |  |  |  | 21.26 | 61.02 | 4880 | 122 |
| ns200 | count | clickbench | hits | eventtime | nullspace:200 | 1 |  |  |  | 20.67 | 10302.55 | 194976 | 122 |
| ns200 | count | clickbench | hits | isdownload | nullspace:200 | 1 |  |  |  | 16.31 | 50.24 | 3176 | 122 |
| ns200 | count | clickbench | hits | islink | nullspace:200 | 1 |  |  |  | 12.54 | 64.05 | 3392 | 122 |
| ns200 | count | clickbench | hits | isrefresh | nullspace:200 | 1 |  |  |  | 16.62 | 80.56 | 4880 | 122 |
| ns200 | count | clickbench | hits | mobilephonemodel | nullspace:200 | 1 |  |  |  | 4.64 | 29.90 | 4912 | 122 |
| ns200 | count | clickbench | hits | referer | nullspace:200 | 1 |  |  |  | 72.74 | 4853.22 | 195072 | 122 |
| ns200 | count | clickbench | hits | refererhash | nullspace:200 | 1 |  |  |  | 60.13 | 5185.86 | 195144 | 122 |
| ns200 | count | clickbench | hits | searchphrase | nullspace:200 | 1 |  |  |  | 9.32 | 418.84 | 123488 | 122 |
| ns200 | count | clickbench | hits | title | nullspace:200 | 1 |  |  |  | 141.62 | 2160.56 | 187032 | 122 |
| ns200 | count | clickbench | hits | traficsourceid | nullspace:200 | 1 |  |  |  | 20.40 | 75.44 | 9552 | 122 |
| ns200 | count | clickbench | hits | url | nullspace:200 | 1 |  |  |  | 81.48 | 8292.91 | 195128 | 122 |
| ns200 | count | clickbench | hits | urlhash | nullspace:200 | 1 |  |  |  | 25.57 | 8922.01 | 195144 | 122 |
| ns200 | count | clickbench | hits | userid | nullspace:200 | 1 |  |  |  | 16.40 | 1882.65 | 195200 | 122 |
| ns200 | count | micro_outliers | checkpoint |  |  | 1 | 0.84 | 0.84 | 9.51 |  |  |  |  |
| ns200 | count | micro_outliers | sensor_records |  |  | 1 | 105202.65 | 105202.65 | 105263.15 |  |  |  |  |
| ns200 | count | micro_outliers | sensor_records | timestamp_ms | nullspace:200 | 1 |  |  |  | 39.17 | 92088.11 | 1951552 | 1220 |
| ns200 | count | micro_sorted | checkpoint |  |  | 1 | 3.70 | 3.70 | 3.76 |  |  |  |  |
| ns200 | count | micro_sorted | sensor_records |  |  | 1 | 156051.39 | 156051.39 | 156067.90 |  |  |  |  |
| ns200 | count | micro_sorted | sensor_records | timestamp_ms | nullspace:200 | 1 |  |  |  | 341.99 | 131667.45 | 1951616 | 1220 |
| ns200 | count | micro_unsorted | checkpoint |  |  | 1 | 2.22 | 2.22 | 2.47 |  |  |  |  |
| ns200 | count | micro_unsorted | sensor_records |  |  | 1 | 106520.24 | 106520.24 | 106536.52 |  |  |  |  |
| ns200 | count | micro_unsorted | sensor_records | timestamp_ms | nullspace:200 | 1 |  |  |  | 44.11 | 90667.35 | 1943520 | 1220 |
| ns200 | count | tpcds | call_center |  |  | 1 | 59.55 | 59.55 | 60.04 |  |  |  |  |
| ns200 | count | tpcds | catalog_page |  |  | 1 | 740.97 | 740.97 | 750.02 |  |  |  |  |
| ns200 | count | tpcds | catalog_returns |  |  | 1 | 6484.26 | 6484.26 | 6491.63 |  |  |  |  |
| ns200 | count | tpcds | catalog_sales |  |  | 1 | 77539.56 | 77539.56 | 77551.17 |  |  |  |  |
| ns200 | count | tpcds | checkpoint |  |  | 1 | 557.52 | 557.52 | 557.71 |  |  |  |  |
| ns200 | count | tpcds | customer |  |  | 1 | 7992.42 | 7992.42 | 7996.57 |  |  |  |  |
| ns200 | count | tpcds | customer_address |  |  | 1 | 1962.38 | 1962.38 | 1961.44 |  |  |  |  |
| ns200 | count | tpcds | customer_demographics |  |  | 1 | 37955.64 | 37955.64 | 37986.24 |  |  |  |  |
| ns200 | count | tpcds | date_dim |  |  | 1 | 2908.52 | 2908.52 | 2912.17 |  |  |  |  |
| ns200 | count | tpcds | household_demographics |  |  | 1 | 75.19 | 75.19 | 64.53 |  |  |  |  |
| ns200 | count | tpcds | income_band |  |  | 1 | 13.97 | 13.97 | 14.90 |  |  |  |  |
| ns200 | count | tpcds | inventory |  |  | 1 | 197815.90 | 197815.90 | 198069.41 |  |  |  |  |
| ns200 | count | tpcds | item |  |  | 1 | 1521.96 | 1521.96 | 1304.58 |  |  |  |  |
| ns200 | count | tpcds | promotion |  |  | 1 | 19.35 | 19.35 | 18.21 |  |  |  |  |
| ns200 | count | tpcds | reason |  |  | 1 | 41.63 | 41.63 | 40.75 |  |  |  |  |
| ns200 | count | tpcds | ship_mode |  |  | 1 | 126.27 | 126.27 | 129.89 |  |  |  |  |
| ns200 | count | tpcds | store |  |  | 1 | 66.75 | 66.75 | 69.83 |  |  |  |  |
| ns200 | count | tpcds | store_returns |  |  | 1 | 15416.32 | 15416.32 | 15420.66 |  |  |  |  |
| ns200 | count | tpcds | store_sales |  |  | 1 | 174596.20 | 174596.20 | 174608.59 |  |  |  |  |
| ns200 | count | tpcds | time_dim |  |  | 1 | 2789.23 | 2789.23 | 2803.25 |  |  |  |  |
| ns200 | count | tpcds | warehouse |  |  | 1 | 28.47 | 28.47 | 22.62 |  |  |  |  |
| ns200 | count | tpcds | web_page |  |  | 1 | 66.08 | 66.08 | 66.54 |  |  |  |  |
| ns200 | count | tpcds | web_returns |  |  | 1 | 3314.00 | 3314.00 | 3325.67 |  |  |  |  |
| ns200 | count | tpcds | web_sales |  |  | 1 | 51428.04 | 51428.04 | 51450.89 |  |  |  |  |
| ns200 | count | tpcds | web_site |  |  | 1 | 61.19 | 61.19 | 33.30 |  |  |  |  |
| ns200 | count | tpcds | call_center | cc_county | nullspace:200 | 1 |  |  |  | 0.10 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | catalog_page | cp_catalog_page_sk | nullspace:200 | 1 |  |  |  | 0.10 | 202.55 | 1600 | 1 |
| ns200 | count | tpcds | catalog_returns | cr_catalog_page_sk | nullspace:200 | 1 |  |  |  | 0.53 | 260.13 | 27200 | 17 |
| ns200 | count | tpcds | catalog_returns | cr_item_sk | nullspace:200 | 1 |  |  |  | 0.60 | 1323.15 | 27168 | 17 |
| ns200 | count | tpcds | catalog_returns | cr_order_number | nullspace:200 | 1 |  |  |  | 1.03 | 1251.67 | 27152 | 17 |
| ns200 | count | tpcds | catalog_returns | cr_return_amount | nullspace:200 | 1 |  |  |  | 1.44 | 1711.65 | 27136 | 17 |
| ns200 | count | tpcds | catalog_returns | cr_returned_date_sk | nullspace:200 | 1 |  |  |  | 0.74 | 124.20 | 27176 | 17 |
| ns200 | count | tpcds | catalog_sales | cs_bill_addr_sk | nullspace:200 | 1 |  |  |  | 15.86 | 2183.77 | 280000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_bill_customer_sk | nullspace:200 | 1 |  |  |  | 8.09 | 2223.80 | 280000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_bill_hdemo_sk | nullspace:200 | 1 |  |  |  | 9.02 | 2206.03 | 280000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_call_center_sk | nullspace:200 | 1 |  |  |  | 8.15 | 58.96 | 8424 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_catalog_page_sk | nullspace:200 | 1 |  |  |  | 9.61 | 817.24 | 277144 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_item_sk | nullspace:200 | 1 |  |  |  | 7.82 | 11048.42 | 279552 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_net_paid | nullspace:200 | 1 |  |  |  | 10.54 | 14655.99 | 279544 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_net_profit | nullspace:200 | 1 |  |  |  | 35.17 | 14735.67 | 279336 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_order_number | nullspace:200 | 1 |  |  |  | 6.52 | 2341.72 | 280000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_promo_sk | nullspace:200 | 1 |  |  |  | 7.05 | 361.04 | 280000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_quantity | nullspace:200 | 1 |  |  |  | 9.13 | 168.79 | 133000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_ship_addr_sk | nullspace:200 | 1 |  |  |  | 6.74 | 2266.01 | 280000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_ship_customer_sk | nullspace:200 | 1 |  |  |  | 7.96 | 2200.39 | 280000 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_ship_date_sk | nullspace:200 | 1 |  |  |  | 9.72 | 136.78 | 131456 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_ship_mode_sk | nullspace:200 | 1 |  |  |  | 12.43 | 116.41 | 30800 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_sold_date_sk | nullspace:200 | 1 |  |  |  | 7.41 | 57.57 | 19672 | 175 |
| ns200 | count | tpcds | catalog_sales | cs_warehouse_sk | nullspace:200 | 1 |  |  |  | 8.95 | 85.53 | 11200 | 175 |
| ns200 | count | tpcds | customer | c_birth_month | nullspace:200 | 1 |  |  |  | 0.59 | 8.67 | 1440 | 12 |
| ns200 | count | tpcds | customer | c_current_addr_sk | nullspace:200 | 1 |  |  |  | 0.60 | 1072.68 | 19152 | 12 |
| ns200 | count | tpcds | customer | c_current_hdemo_sk | nullspace:200 | 1 |  |  |  | 0.59 | 839.30 | 19168 | 12 |
| ns200 | count | tpcds | customer | c_customer_id | nullspace:200 | 1 |  |  |  | 1.60 | 988.41 | 19112 | 12 |
| ns200 | count | tpcds | customer | c_customer_sk | nullspace:200 | 1 |  |  |  | 0.86 | 1004.93 | 19136 | 12 |
| ns200 | count | tpcds | customer | c_first_sales_date_sk | nullspace:200 | 1 |  |  |  | 0.55 | 623.48 | 19200 | 12 |
| ns200 | count | tpcds | customer | c_first_shipto_date_sk | nullspace:200 | 1 |  |  |  | 0.64 | 648.04 | 19200 | 12 |
| ns200 | count | tpcds | customer | c_preferred_cust_flag | nullspace:200 | 1 |  |  |  | 2.36 | 4.86 | 480 | 12 |
| ns200 | count | tpcds | customer_address | ca_address_sk | nullspace:200 | 1 |  |  |  | 0.21 | 545.87 | 9568 | 6 |
| ns200 | count | tpcds | customer_address | ca_city | nullspace:200 | 1 |  |  |  | 1.55 | 75.94 | 9600 | 6 |
| ns200 | count | tpcds | customer_address | ca_country | nullspace:200 | 1 |  |  |  | 2.74 | 2.05 | 96 | 6 |
| ns200 | count | tpcds | customer_address | ca_county | nullspace:200 | 1 |  |  |  | 2.53 | 113.37 | 9600 | 6 |
| ns200 | count | tpcds | customer_address | ca_gmt_offset | nullspace:200 | 1 |  |  |  | 64.31 | 2.84 | 432 | 6 |
| ns200 | count | tpcds | customer_address | ca_state | nullspace:200 | 1 |  |  |  | 34.01 | 4.95 | 2400 | 6 |
| ns200 | count | tpcds | customer_address | ca_zip | nullspace:200 | 1 |  |  |  | 2.10 | 111.98 | 9600 | 6 |
| ns200 | count | tpcds | customer_demographics | cd_demo_sk | nullspace:200 | 1 |  |  |  | 9.23 | 21699.04 | 372832 | 234 |
| ns200 | count | tpcds | customer_demographics | cd_education_status | nullspace:200 | 1 |  |  |  | 51.29 | 91.61 | 18720 | 234 |
| ns200 | count | tpcds | customer_demographics | cd_gender | nullspace:200 | 1 |  |  |  | 46.35 | 104.81 | 9360 | 234 |
| ns200 | count | tpcds | customer_demographics | cd_marital_status | nullspace:200 | 1 |  |  |  | 46.51 | 106.09 | 14976 | 234 |
| ns200 | count | tpcds | date_dim | d_date | nullspace:200 | 1 |  |  |  | 0.25 | 698.57 | 12744 | 8 |
| ns200 | count | tpcds | date_dim | d_date_sk | nullspace:200 | 1 |  |  |  | 0.56 | 654.17 | 12752 | 8 |
| ns200 | count | tpcds | date_dim | d_dom | nullspace:200 | 1 |  |  |  | 0.28 | 4.17 | 2048 | 8 |
| ns200 | count | tpcds | date_dim | d_dow | nullspace:200 | 1 |  |  |  | 0.52 | 2.65 | 640 | 8 |
| ns200 | count | tpcds | date_dim | d_month_seq | nullspace:200 | 1 |  |  |  | 0.27 | 11.90 | 12800 | 8 |
| ns200 | count | tpcds | date_dim | d_moy | nullspace:200 | 1 |  |  |  | 0.25 | 8.46 | 960 | 8 |
| ns200 | count | tpcds | date_dim | d_qoy | nullspace:200 | 1 |  |  |  | 0.49 | 1.97 | 448 | 8 |
| ns200 | count | tpcds | date_dim | d_quarter_name | nullspace:200 | 1 |  |  |  | 1.85 | 4.76 | 5544 | 8 |
| ns200 | count | tpcds | date_dim | d_week_seq | nullspace:200 | 1 |  |  |  | 0.33 | 140.47 | 12800 | 8 |
| ns200 | count | tpcds | date_dim | d_year | nullspace:200 | 1 |  |  |  | 0.30 | 2.57 | 1624 | 8 |
| ns200 | count | tpcds | household_demographics | hd_buy_potential | nullspace:200 | 1 |  |  |  | 0.43 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | household_demographics | hd_demo_sk | nullspace:200 | 1 |  |  |  | 0.02 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | household_demographics | hd_dep_count | nullspace:200 | 1 |  |  |  | 0.25 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | household_demographics | hd_income_band_sk | nullspace:200 | 1 |  |  |  | 0.06 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | household_demographics | hd_vehicle_count | nullspace:200 | 1 |  |  |  | 0.24 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | income_band | ib_lower_bound | nullspace:200 | 1 |  |  |  | 0.16 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | income_band | ib_upper_bound | nullspace:200 | 1 |  |  |  | 0.13 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | inventory | inv_date_sk | nullspace:200 | 1 |  |  |  | 62.33 | 569.93 | 29168 | 1433 |
| ns200 | count | tpcds | inventory | inv_item_sk | nullspace:200 | 1 |  |  |  | 49.13 | 135601.27 | 2281848 | 1433 |
| ns200 | count | tpcds | inventory | inv_quantity_on_hand | nullspace:200 | 1 |  |  |  | 132.99 | 23385.96 | 2292800 | 1433 |
| ns200 | count | tpcds | inventory | inv_warehouse_sk | nullspace:200 | 1 |  |  |  | 49.48 | 547.43 | 54200 | 1433 |
| ns200 | count | tpcds | item | i_category | nullspace:200 | 1 |  |  |  | 0.50 | 0.85 | 208 | 2 |
| ns200 | count | tpcds | item | i_class | nullspace:200 | 1 |  |  |  | 0.43 | 1.14 | 1504 | 2 |
| ns200 | count | tpcds | item | i_color | nullspace:200 | 1 |  |  |  | 1.59 | 1.17 | 1408 | 2 |
| ns200 | count | tpcds | item | i_current_price | nullspace:200 | 1 |  |  |  | 0.25 | 24.60 | 3200 | 2 |
| ns200 | count | tpcds | item | i_item_id | nullspace:200 | 1 |  |  |  | 0.29 | 90.57 | 3200 | 2 |
| ns200 | count | tpcds | item | i_item_sk | nullspace:200 | 1 |  |  |  | 0.10 | 116.58 | 3192 | 2 |
| ns200 | count | tpcds | item | i_manager_id | nullspace:200 | 1 |  |  |  | 0.94 | 1.42 | 1520 | 2 |
| ns200 | count | tpcds | item | i_manufact | nullspace:200 | 1 |  |  |  | 1.40 | 22.58 | 3200 | 2 |
| ns200 | count | tpcds | item | i_manufact_id | nullspace:200 | 1 |  |  |  | 0.06 | 20.58 | 3200 | 2 |
| ns200 | count | tpcds | promotion | p_channel_tv | nullspace:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | reason | r_reason_desc | nullspace:200 | 1 |  |  |  | 0.16 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | reason | r_reason_sk | nullspace:200 | 1 |  |  |  | 0.08 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | ship_mode | sm_carrier | nullspace:200 | 1 |  |  |  | 0.11 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store | s_city | nullspace:200 | 1 |  |  |  | 0.06 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store | s_county | nullspace:200 | 1 |  |  |  | 0.08 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store | s_market_id | nullspace:200 | 1 |  |  |  | 0.10 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store | s_number_employees | nullspace:200 | 1 |  |  |  | 0.08 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store | s_state | nullspace:200 | 1 |  |  |  | 0.12 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store | s_store_name | nullspace:200 | 1 |  |  |  | 0.09 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store | s_store_sk | nullspace:200 | 1 |  |  |  | 0.12 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | store_returns | sr_cdemo_sk | nullspace:200 | 1 |  |  |  | 1.20 | 2871.64 | 55864 | 35 |
| ns200 | count | tpcds | store_returns | sr_customer_sk | nullspace:200 | 1 |  |  |  | 1.09 | 1915.90 | 55952 | 35 |
| ns200 | count | tpcds | store_returns | sr_item_sk | nullspace:200 | 1 |  |  |  | 1.17 | 1698.54 | 55832 | 35 |
| ns200 | count | tpcds | store_returns | sr_return_amt | nullspace:200 | 1 |  |  |  | 3.35 | 2480.24 | 55872 | 35 |
| ns200 | count | tpcds | store_returns | sr_returned_date_sk | nullspace:200 | 1 |  |  |  | 1.32 | 638.30 | 56000 | 35 |
| ns200 | count | tpcds | store_returns | sr_store_sk | nullspace:200 | 1 |  |  |  | 5.22 | 16.53 | 2520 | 35 |
| ns200 | count | tpcds | store_returns | sr_ticket_number | nullspace:200 | 1 |  |  |  | 0.89 | 2482.56 | 55968 | 35 |
| ns200 | count | tpcds | store_sales | ss_addr_sk | nullspace:200 | 1 |  |  |  | 17.81 | 4863.29 | 561600 | 351 |
| ns200 | count | tpcds | store_sales | ss_customer_sk | nullspace:200 | 1 |  |  |  | 20.98 | 4777.42 | 561600 | 351 |
| ns200 | count | tpcds | store_sales | ss_hdemo_sk | nullspace:200 | 1 |  |  |  | 18.79 | 5113.71 | 561600 | 351 |
| ns200 | count | tpcds | store_sales | ss_item_sk | nullspace:200 | 1 |  |  |  | 22.50 | 23300.55 | 559904 | 351 |
| ns200 | count | tpcds | store_sales | ss_net_paid | nullspace:200 | 1 |  |  |  | 19.66 | 34536.00 | 560136 | 351 |
| ns200 | count | tpcds | store_sales | ss_net_profit | nullspace:200 | 1 |  |  |  | 20.76 | 34850.86 | 560224 | 351 |
| ns200 | count | tpcds | store_sales | ss_promo_sk | nullspace:200 | 1 |  |  |  | 20.57 | 792.15 | 561600 | 351 |
| ns200 | count | tpcds | store_sales | ss_quantity | nullspace:200 | 1 |  |  |  | 18.66 | 385.27 | 266760 | 351 |
| ns200 | count | tpcds | store_sales | ss_sold_date_sk | nullspace:200 | 1 |  |  |  | 38.29 | 4694.37 | 561600 | 351 |
| ns200 | count | tpcds | store_sales | ss_sold_time_sk | nullspace:200 | 1 |  |  |  | 19.20 | 4858.01 | 561600 | 351 |
| ns200 | count | tpcds | store_sales | ss_store_sk | nullspace:200 | 1 |  |  |  | 19.53 | 149.89 | 25272 | 351 |
| ns200 | count | tpcds | store_sales | ss_ticket_number | nullspace:200 | 1 |  |  |  | 24.50 | 4913.18 | 561600 | 351 |
| ns200 | count | tpcds | time_dim | t_hour | nullspace:200 | 1 |  |  |  | 1.60 | 3.32 | 496 | 10 |
| ns200 | count | tpcds | time_dim | t_meal_time | nullspace:200 | 1 |  |  |  | 1.27 | 3.42 | 112 | 7 |
| ns200 | count | tpcds | time_dim | t_minute | nullspace:200 | 1 |  |  |  | 0.62 | 4.05 | 4720 | 10 |
| ns200 | count | tpcds | time_dim | t_time | nullspace:200 | 1 |  |  |  | 0.49 | 1008.48 | 15952 | 10 |
| ns200 | count | tpcds | time_dim | t_time_sk | nullspace:200 | 1 |  |  |  | 0.84 | 981.71 | 15952 | 10 |
| ns200 | count | tpcds | web_page | wp_char_count | nullspace:200 | 1 |  |  |  | 0.00 | 0.00 | 0 | 0 |
| ns200 | count | tpcds | web_returns | wr_item_sk | nullspace:200 | 1 |  |  |  | 0.31 | 499.65 | 12752 | 8 |
| ns200 | count | tpcds | web_returns | wr_order_number | nullspace:200 | 1 |  |  |  | 0.54 | 679.54 | 12784 | 8 |
| ns200 | count | tpcds | web_returns | wr_return_amt | nullspace:200 | 1 |  |  |  | 0.85 | 717.12 | 12760 | 8 |
| ns200 | count | tpcds | web_returns | wr_returned_date_sk | nullspace:200 | 1 |  |  |  | 0.34 | 193.26 | 12800 | 8 |
| ns200 | count | tpcds | web_returns | wr_web_page_sk | nullspace:200 | 1 |  |  |  | 1.23 | 5.68 | 3776 | 8 |
| ns200 | count | tpcds | web_sales | ws_bill_addr_sk | nullspace:200 | 1 |  |  |  | 3.07 | 1276.97 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_item_sk | nullspace:200 | 1 |  |  |  | 3.27 | 5934.30 | 138784 | 87 |
| ns200 | count | tpcds | web_sales | ws_net_paid | nullspace:200 | 1 |  |  |  | 3.26 | 9148.42 | 138832 | 87 |
| ns200 | count | tpcds | web_sales | ws_net_profit | nullspace:200 | 1 |  |  |  | 4.15 | 10544.80 | 138840 | 87 |
| ns200 | count | tpcds | web_sales | ws_order_number | nullspace:200 | 1 |  |  |  | 2.88 | 1274.28 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_promo_sk | nullspace:200 | 1 |  |  |  | 2.99 | 213.09 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_quantity | nullspace:200 | 1 |  |  |  | 2.89 | 109.59 | 66120 | 87 |
| ns200 | count | tpcds | web_sales | ws_ship_addr_sk | nullspace:200 | 1 |  |  |  | 3.93 | 1291.50 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_ship_customer_sk | nullspace:200 | 1 |  |  |  | 5.50 | 1359.00 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_ship_date_sk | nullspace:200 | 1 |  |  |  | 5.24 | 2283.22 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_ship_hdemo_sk | nullspace:200 | 1 |  |  |  | 3.17 | 1352.61 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_ship_mode_sk | nullspace:200 | 1 |  |  |  | 3.45 | 65.82 | 15312 | 87 |
| ns200 | count | tpcds | web_sales | ws_sold_date_sk | nullspace:200 | 1 |  |  |  | 3.95 | 1241.77 | 139200 | 87 |
| ns200 | count | tpcds | web_sales | ws_warehouse_sk | nullspace:200 | 1 |  |  |  | 3.41 | 47.27 | 5568 | 87 |
| ns200 | count | tpcds | web_sales | ws_web_page_sk | nullspace:200 | 1 |  |  |  | 2.94 | 82.90 | 41064 | 87 |
| ns200 | count | tpcds | web_sales | ws_web_site_sk | nullspace:200 | 1 |  |  |  | 3.03 | 73.09 | 21576 | 87 |
| ns200 | count | tpcds | web_site | web_company_name | nullspace:200 | 1 |  |  |  | 0.62 | 0.00 | 0 | 0 |
| ns200 | count | tpch | checkpoint |  |  | 1 | 354.83 | 354.83 | 352.75 |  |  |  |  |
| ns200 | count | tpch | customer |  |  | 1 | 8758.05 | 8758.05 | 8786.44 |  |  |  |  |
| ns200 | count | tpch | lineitem |  |  | 1 | 363191.99 | 363191.99 | 363487.33 |  |  |  |  |
| ns200 | count | tpch | nation |  |  | 1 | 278.35 | 278.35 | 74.14 |  |  |  |  |
| ns200 | count | tpch | orders |  |  | 1 | 88686.35 | 88686.35 | 88688.50 |  |  |  |  |
| ns200 | count | tpch | part |  |  | 1 | 6285.80 | 6285.80 | 6307.37 |  |  |  |  |
| ns200 | count | tpch | partsupp |  |  | 1 | 19037.76 | 19037.76 | 19017.02 |  |  |  |  |
| ns200 | count | tpch | region |  |  | 1 | 103.91 | 103.91 | 109.88 |  |  |  |  |
| ns200 | count | tpch | supplier |  |  | 1 | 475.09 | 475.09 | 474.30 |  |  |  |  |
| ns200 | count | tpch | customer | c_acctbal | nullspace:200 | 1 |  |  |  | 2.98 | 1939.44 | 28776 | 18 |
| ns200 | count | tpch | customer | c_custkey | nullspace:200 | 1 |  |  |  | 1.89 | 1878.88 | 28712 | 18 |
| ns200 | count | tpch | customer | c_mktsegment | nullspace:200 | 1 |  |  |  | 5.76 | 9.61 | 1152 | 18 |
| ns200 | count | tpch | customer | c_nationkey | nullspace:200 | 1 |  |  |  | 4.60 | 13.29 | 3888 | 18 |
| ns200 | count | tpch | customer | c_phone | nullspace:200 | 1 |  |  |  | 8.14 | 2132.20 | 28672 | 18 |
| ns200 | count | tpch | lineitem | l_commitdate | nullspace:200 | 1 |  |  |  | 22.59 | 47445.86 | 1171200 | 732 |
| ns200 | count | tpch | lineitem | l_discount | nullspace:200 | 1 |  |  |  | 23.01 | 444.00 | 81984 | 732 |
| ns200 | count | tpch | lineitem | l_orderkey | nullspace:200 | 1 |  |  |  | 54.92 | 14877.35 | 1171152 | 732 |
| ns200 | count | tpch | lineitem | l_partkey | nullspace:200 | 1 |  |  |  | 24.23 | 67784.57 | 1169704 | 732 |
| ns200 | count | tpch | lineitem | l_quantity | nullspace:200 | 1 |  |  |  | 22.25 | 599.96 | 292800 | 732 |
| ns200 | count | tpch | lineitem | l_receiptdate | nullspace:200 | 1 |  |  |  | 24.09 | 48227.71 | 1171192 | 732 |
| ns200 | count | tpch | lineitem | l_returnflag | nullspace:200 | 1 |  |  |  | 147.27 | 328.33 | 35136 | 732 |
| ns200 | count | tpch | lineitem | l_shipdate | nullspace:200 | 1 |  |  |  | 26.20 | 49412.07 | 1171184 | 732 |
| ns200 | count | tpch | lineitem | l_shipinstruct | nullspace:200 | 1 |  |  |  | 213.25 | 409.07 | 40992 | 732 |
| ns200 | count | tpch | lineitem | l_shipmode | nullspace:200 | 1 |  |  |  | 170.29 | 428.36 | 58560 | 732 |
| ns200 | count | tpch | lineitem | l_suppkey | nullspace:200 | 1 |  |  |  | 23.99 | 44840.93 | 1169520 | 732 |
| ns200 | count | tpch | nation | n_name | nullspace:200 | 1 |  |  |  | 0.29 | 0.00 | 0 | 0 |
| ns200 | count | tpch | nation | n_regionkey | nullspace:200 | 1 |  |  |  | 0.34 | 0.00 | 0 | 0 |
| ns200 | count | tpch | orders | o_comment | nullspace:200 | 1 |  |  |  | 62.42 | 16593.61 | 291984 | 183 |
| ns200 | count | tpch | orders | o_custkey | nullspace:200 | 1 |  |  |  | 10.49 | 16983.93 | 292296 | 183 |
| ns200 | count | tpch | orders | o_orderdate | nullspace:200 | 1 |  |  |  | 10.19 | 11389.18 | 292800 | 183 |
| ns200 | count | tpch | orders | o_orderkey | nullspace:200 | 1 |  |  |  | 11.13 | 16541.04 | 291536 | 183 |
| ns200 | count | tpch | orders | o_orderstatus | nullspace:200 | 1 |  |  |  | 49.04 | 107.29 | 8784 | 183 |
| ns200 | count | tpch | part | p_brand | nullspace:200 | 1 |  |  |  | 2.05 | 21.40 | 5184 | 24 |
| ns200 | count | tpch | part | p_container | nullspace:200 | 1 |  |  |  | 7.51 | 22.13 | 7872 | 24 |
| ns200 | count | tpch | part | p_name | nullspace:200 | 1 |  |  |  | 8.44 | 2430.38 | 38224 | 24 |
| ns200 | count | tpch | part | p_size | nullspace:200 | 1 |  |  |  | 1.34 | 18.88 | 9600 | 24 |
| ns200 | count | tpch | part | p_type | nullspace:200 | 1 |  |  |  | 6.28 | 30.03 | 26688 | 24 |
| ns200 | count | tpch | partsupp | ps_partkey | nullspace:200 | 1 |  |  |  | 3.62 | 2055.68 | 155184 | 97 |
| ns200 | count | tpch | partsupp | ps_suppkey | nullspace:200 | 1 |  |  |  | 3.16 | 9569.04 | 154456 | 97 |
| ns200 | count | tpch | region | r_name | nullspace:200 | 1 |  |  |  | 0.00 | 0.00 | 0 | 0 |
| ns200 | count | tpch | supplier | s_comment | nullspace:200 | 1 |  |  |  | 0.60 | 107.90 | 1592 | 1 |
| ns200 | count | tpch | supplier | s_nationkey | nullspace:200 | 1 |  |  |  | 0.10 | 0.62 | 216 | 1 |
| ns200 | count | tpch | supplier | s_suppkey | nullspace:200 | 1 |  |  |  | 0.04 | 122.61 | 1600 | 1 |
| occ200 | check | clickbench | checkpoint |  |  | 1 | 17.03 | 17.03 | 18.18 |  |  |  |  |
| occ200 | check | clickbench | hits |  |  | 1 | 70496.05 | 70496.05 | 70524.87 |  |  |  |  |
| occ200 | check | clickbench | hits | advengineid | occupancy:200 | 1 |  |  |  | 8.92 | 59.57 | 1952 | 122 |
| occ200 | check | clickbench | hits | counterid | occupancy:200 | 1 |  |  |  | 4.70 | 23.18 | 1952 | 122 |
| occ200 | check | clickbench | hits | dontcounthits | occupancy:200 | 1 |  |  |  | 17.32 | 14.75 | 1952 | 122 |
| occ200 | check | clickbench | hits | eventtime | occupancy:200 | 1 |  |  |  | 5.84 | 1426.43 | 195056 | 122 |
| occ200 | check | clickbench | hits | isdownload | occupancy:200 | 1 |  |  |  | 9.98 | 13.61 | 1952 | 122 |
| occ200 | check | clickbench | hits | islink | occupancy:200 | 1 |  |  |  | 9.81 | 15.29 | 1952 | 122 |
| occ200 | check | clickbench | hits | isrefresh | occupancy:200 | 1 |  |  |  | 8.44 | 17.99 | 1952 | 122 |
| occ200 | check | clickbench | hits | refererhash | occupancy:200 | 1 |  |  |  | 19.46 | 669.13 | 195112 | 122 |
| occ200 | check | clickbench | hits | traficsourceid | occupancy:200 | 1 |  |  |  | 9.13 | 23.51 | 1952 | 122 |
| occ200 | check | clickbench | hits | urlhash | occupancy:200 | 1 |  |  |  | 17.65 | 1041.69 | 195032 | 122 |
| occ200 | check | clickbench | hits | userid | occupancy:200 | 1 |  |  |  | 6.93 | 132.71 | 195200 | 122 |
| occ200 | check | micro_cardinality_100 | checkpoint |  |  | 1 | 15.77 | 15.77 | 25.11 |  |  |  |  |
| occ200 | check | micro_cardinality_100 | sensor_records |  |  | 1 | 29975.95 | 29975.95 | 30022.90 |  |  |  |  |
| occ200 | check | micro_cardinality_100 | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 45.63 | 16758.58 | 1945344 | 1220 |
| occ200 | check | micro_cardinality_100 | sensor_records | user_id | occupancy:200 | 1 |  |  |  | 63.78 | 751.16 | 29280 | 1220 |
| occ200 | check | micro_cardinality_100000 | checkpoint |  |  | 1 | 31.31 | 31.31 | 31.78 |  |  |  |  |
| occ200 | check | micro_cardinality_100000 | sensor_records |  |  | 1 | 39755.56 | 39755.56 | 39777.63 |  |  |  |  |
| occ200 | check | micro_cardinality_100000 | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 44.34 | 13167.31 | 1945344 | 1220 |
| occ200 | check | micro_cardinality_100000 | sensor_records | user_id | occupancy:200 | 1 |  |  |  | 63.91 | 15344.26 | 1922360 | 1220 |
| occ200 | check | micro_outliers | checkpoint |  |  | 1 | 4.38 | 4.38 | 2.37 |  |  |  |  |
| occ200 | check | micro_outliers | sensor_records |  |  | 1 | 24442.21 | 24442.21 | 24454.51 |  |  |  |  |
| occ200 | check | micro_outliers | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 110.74 | 11959.43 | 1946296 | 1220 |
| occ200 | check | micro_sorted | checkpoint |  |  | 1 | 424.94 | 424.94 | 404.52 |  |  |  |  |
| occ200 | check | micro_sorted | sensor_records |  |  | 1 | 30094.11 | 30094.11 | 30149.23 |  |  |  |  |
| occ200 | check | micro_sorted | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 80.12 | 16570.50 | 1945344 | 1220 |
| occ200 | check | micro_unsorted | checkpoint |  |  | 1 | 27.77 | 27.77 | 4.02 |  |  |  |  |
| occ200 | check | micro_unsorted | sensor_records |  |  | 1 | 34065.84 | 34065.84 | 34100.07 |  |  |  |  |
| occ200 | check | micro_unsorted | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 87.61 | 19773.19 | 1942240 | 1220 |
| occ200 | check | tpcds | call_center |  |  | 1 | 90.41 | 90.41 | 77.08 |  |  |  |  |
| occ200 | check | tpcds | catalog_page |  |  | 1 | 312.56 | 312.56 | 316.97 |  |  |  |  |
| occ200 | check | tpcds | catalog_returns |  |  | 1 | 2150.94 | 2150.94 | 2150.70 |  |  |  |  |
| occ200 | check | tpcds | catalog_sales |  |  | 1 | 28833.14 | 28833.14 | 28858.16 |  |  |  |  |
| occ200 | check | tpcds | checkpoint |  |  | 1 | 598.52 | 598.52 | 596.16 |  |  |  |  |
| occ200 | check | tpcds | customer |  |  | 1 | 2136.94 | 2136.94 | 2122.59 |  |  |  |  |
| occ200 | check | tpcds | customer_address |  |  | 1 | 842.92 | 842.92 | 844.10 |  |  |  |  |
| occ200 | check | tpcds | customer_demographics |  |  | 1 | 9788.49 | 9788.49 | 9800.44 |  |  |  |  |
| occ200 | check | tpcds | date_dim |  |  | 1 | 1713.60 | 1713.60 | 1721.97 |  |  |  |  |
| occ200 | check | tpcds | household_demographics |  |  | 1 | 89.51 | 89.51 | 88.94 |  |  |  |  |
| occ200 | check | tpcds | income_band |  |  | 1 | 25.57 | 25.57 | 24.19 |  |  |  |  |
| occ200 | check | tpcds | inventory |  |  | 1 | 34157.73 | 34157.73 | 34163.02 |  |  |  |  |
| occ200 | check | tpcds | item |  |  | 1 | 485.78 | 485.78 | 479.76 |  |  |  |  |
| occ200 | check | tpcds | promotion |  |  | 1 | 34.30 | 34.30 | 37.11 |  |  |  |  |
| occ200 | check | tpcds | reason |  |  | 1 | 19.00 | 19.00 | 19.08 |  |  |  |  |
| occ200 | check | tpcds | ship_mode |  |  | 1 | 23.27 | 23.27 | 29.44 |  |  |  |  |
| occ200 | check | tpcds | store |  |  | 1 | 32.84 | 32.84 | 33.27 |  |  |  |  |
| occ200 | check | tpcds | store_returns |  |  | 1 | 5655.80 | 5655.80 | 5668.35 |  |  |  |  |
| occ200 | check | tpcds | store_sales |  |  | 1 | 48871.34 | 48871.34 | 49133.81 |  |  |  |  |
| occ200 | check | tpcds | time_dim |  |  | 1 | 1097.66 | 1097.66 | 896.73 |  |  |  |  |
| occ200 | check | tpcds | warehouse |  |  | 1 | 33.35 | 33.35 | 35.09 |  |  |  |  |
| occ200 | check | tpcds | web_page |  |  | 1 | 35.41 | 35.41 | 35.81 |  |  |  |  |
| occ200 | check | tpcds | web_returns |  |  | 1 | 1187.85 | 1187.85 | 1198.19 |  |  |  |  |
| occ200 | check | tpcds | web_sales |  |  | 1 | 12109.40 | 12109.40 | 12110.12 |  |  |  |  |
| occ200 | check | tpcds | web_site |  |  | 1 | 62.47 | 62.47 | 67.23 |  |  |  |  |
| occ200 | check | tpcds | catalog_page | cp_catalog_page_sk | occupancy:200 | 1 |  |  |  | 0.10 | 2.58 | 24 | 1 |
| occ200 | check | tpcds | catalog_returns | cr_catalog_page_sk | occupancy:200 | 1 |  |  |  | 0.97 | 26.09 | 2608 | 17 |
| occ200 | check | tpcds | catalog_returns | cr_item_sk | occupancy:200 | 1 |  |  |  | 0.46 | 217.66 | 19448 | 17 |
| occ200 | check | tpcds | catalog_returns | cr_order_number | occupancy:200 | 1 |  |  |  | 1.72 | 75.02 | 19648 | 17 |
| occ200 | check | tpcds | catalog_returns | cr_return_amount | occupancy:200 | 1 |  |  |  | 0.96 | 298.30 | 27152 | 17 |
| occ200 | check | tpcds | catalog_returns | cr_returned_date_sk | occupancy:200 | 1 |  |  |  | 0.99 | 19.97 | 512 | 17 |
| occ200 | check | tpcds | catalog_sales | cs_bill_addr_sk | occupancy:200 | 1 |  |  |  | 6.28 | 250.12 | 146080 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_bill_customer_sk | occupancy:200 | 1 |  |  |  | 5.80 | 272.36 | 166528 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_bill_hdemo_sk | occupancy:200 | 1 |  |  |  | 5.50 | 225.75 | 86408 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_call_center_sk | occupancy:200 | 1 |  |  |  | 5.75 | 31.37 | 2800 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_catalog_page_sk | occupancy:200 | 1 |  |  |  | 7.51 | 153.62 | 18832 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_item_sk | occupancy:200 | 1 |  |  |  | 5.67 | 2048.76 | 200200 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_net_paid | occupancy:200 | 1 |  |  |  | 6.82 | 2685.94 | 279248 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_net_profit | occupancy:200 | 1 |  |  |  | 29.03 | 2646.12 | 279336 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_order_number | occupancy:200 | 1 |  |  |  | 9.02 | 95.33 | 4200 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_promo_sk | occupancy:200 | 1 |  |  |  | 6.24 | 128.42 | 2800 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_quantity | occupancy:200 | 1 |  |  |  | 7.56 | 116.66 | 2800 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_ship_addr_sk | occupancy:200 | 1 |  |  |  | 6.07 | 272.27 | 146088 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_ship_customer_sk | occupancy:200 | 1 |  |  |  | 6.78 | 247.40 | 166560 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_ship_date_sk | occupancy:200 | 1 |  |  |  | 6.90 | 102.52 | 2800 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_ship_mode_sk | occupancy:200 | 1 |  |  |  | 5.62 | 77.94 | 2800 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_sold_date_sk | occupancy:200 | 1 |  |  |  | 8.32 | 27.25 | 2800 | 175 |
| occ200 | check | tpcds | catalog_sales | cs_warehouse_sk | occupancy:200 | 1 |  |  |  | 6.20 | 50.56 | 2800 | 175 |
| occ200 | check | tpcds | customer | c_birth_month | occupancy:200 | 1 |  |  |  | 2.74 | 5.86 | 192 | 12 |
| occ200 | check | tpcds | customer | c_current_addr_sk | occupancy:200 | 1 |  |  |  | 3.41 | 175.98 | 19000 | 12 |
| occ200 | check | tpcds | customer | c_current_hdemo_sk | occupancy:200 | 1 |  |  |  | 1.37 | 66.96 | 10272 | 12 |
| occ200 | check | tpcds | customer | c_customer_sk | occupancy:200 | 1 |  |  |  | 1.50 | 38.33 | 288 | 12 |
| occ200 | check | tpcds | customer | c_first_sales_date_sk | occupancy:200 | 1 |  |  |  | 1.80 | 36.18 | 3056 | 12 |
| occ200 | check | tpcds | customer | c_first_shipto_date_sk | occupancy:200 | 1 |  |  |  | 7.65 | 24.20 | 3056 | 12 |
| occ200 | check | tpcds | customer_address | ca_address_sk | occupancy:200 | 1 |  |  |  | 0.18 | 12.59 | 144 | 6 |
| occ200 | check | tpcds | customer_address | ca_gmt_offset | occupancy:200 | 1 |  |  |  | 0.25 | 1.65 | 144 | 6 |
| occ200 | check | tpcds | customer_demographics | cd_demo_sk | occupancy:200 | 1 |  |  |  | 9.81 | 675.45 | 5616 | 234 |
| occ200 | check | tpcds | date_dim | d_date | occupancy:200 | 1 |  |  |  | 0.53 | 22.46 | 192 | 8 |
| occ200 | check | tpcds | date_dim | d_date_sk | occupancy:200 | 1 |  |  |  | 0.52 | 15.54 | 192 | 8 |
| occ200 | check | tpcds | date_dim | d_dom | occupancy:200 | 1 |  |  |  | 0.62 | 3.02 | 128 | 8 |
| occ200 | check | tpcds | date_dim | d_dow | occupancy:200 | 1 |  |  |  | 0.51 | 1.88 | 128 | 8 |
| occ200 | check | tpcds | date_dim | d_month_seq | occupancy:200 | 1 |  |  |  | 0.46 | 1.88 | 128 | 8 |
| occ200 | check | tpcds | date_dim | d_moy | occupancy:200 | 1 |  |  |  | 0.47 | 1.30 | 128 | 8 |
| occ200 | check | tpcds | date_dim | d_qoy | occupancy:200 | 1 |  |  |  | 0.59 | 1.01 | 128 | 8 |
| occ200 | check | tpcds | date_dim | d_week_seq | occupancy:200 | 1 |  |  |  | 0.72 | 4.58 | 192 | 8 |
| occ200 | check | tpcds | date_dim | d_year | occupancy:200 | 1 |  |  |  | 0.47 | 1.03 | 128 | 8 |
| occ200 | check | tpcds | household_demographics | hd_demo_sk | occupancy:200 | 1 |  |  |  | 0.03 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | household_demographics | hd_dep_count | occupancy:200 | 1 |  |  |  | 0.69 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | household_demographics | hd_income_band_sk | occupancy:200 | 1 |  |  |  | 0.09 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | household_demographics | hd_vehicle_count | occupancy:200 | 1 |  |  |  | 0.74 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | income_band | ib_lower_bound | occupancy:200 | 1 |  |  |  | 0.07 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | income_band | ib_upper_bound | occupancy:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | inventory | inv_date_sk | occupancy:200 | 1 |  |  |  | 58.81 | 144.78 | 22928 | 1433 |
| occ200 | check | tpcds | inventory | inv_item_sk | occupancy:200 | 1 |  |  |  | 43.17 | 9951.84 | 818256 | 1433 |
| occ200 | check | tpcds | inventory | inv_quantity_on_hand | occupancy:200 | 1 |  |  |  | 129.36 | 1377.15 | 34392 | 1433 |
| occ200 | check | tpcds | inventory | inv_warehouse_sk | occupancy:200 | 1 |  |  |  | 38.63 | 166.28 | 22928 | 1433 |
| occ200 | check | tpcds | item | i_current_price | occupancy:200 | 1 |  |  |  | 0.20 | 5.04 | 1680 | 2 |
| occ200 | check | tpcds | item | i_item_sk | occupancy:200 | 1 |  |  |  | 0.24 | 4.01 | 48 | 2 |
| occ200 | check | tpcds | item | i_manager_id | occupancy:200 | 1 |  |  |  | 0.26 | 0.70 | 32 | 2 |
| occ200 | check | tpcds | item | i_manufact_id | occupancy:200 | 1 |  |  |  | 0.29 | 1.43 | 112 | 2 |
| occ200 | check | tpcds | reason | r_reason_sk | occupancy:200 | 1 |  |  |  | 0.03 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | store | s_market_id | occupancy:200 | 1 |  |  |  | 0.03 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | store | s_number_employees | occupancy:200 | 1 |  |  |  | 0.00 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | store | s_store_sk | occupancy:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | store_returns | sr_cdemo_sk | occupancy:200 | 1 |  |  |  | 1.13 | 499.51 | 55976 | 35 |
| occ200 | check | tpcds | store_returns | sr_customer_sk | occupancy:200 | 1 |  |  |  | 3.72 | 390.86 | 54440 | 35 |
| occ200 | check | tpcds | store_returns | sr_item_sk | occupancy:200 | 1 |  |  |  | 2.55 | 404.72 | 40040 | 35 |
| occ200 | check | tpcds | store_returns | sr_return_amt | occupancy:200 | 1 |  |  |  | 1.17 | 463.61 | 55784 | 35 |
| occ200 | check | tpcds | store_returns | sr_returned_date_sk | occupancy:200 | 1 |  |  |  | 6.28 | 50.33 | 3480 | 35 |
| occ200 | check | tpcds | store_returns | sr_store_sk | occupancy:200 | 1 |  |  |  | 1.33 | 9.20 | 560 | 35 |
| occ200 | check | tpcds | store_returns | sr_ticket_number | occupancy:200 | 1 |  |  |  | 0.95 | 80.70 | 26952 | 35 |
| occ200 | check | tpcds | store_sales | ss_addr_sk | occupancy:200 | 1 |  |  |  | 16.39 | 341.28 | 234408 | 351 |
| occ200 | check | tpcds | store_sales | ss_customer_sk | occupancy:200 | 1 |  |  |  | 17.46 | 333.05 | 265312 | 351 |
| occ200 | check | tpcds | store_sales | ss_hdemo_sk | occupancy:200 | 1 |  |  |  | 15.16 | 344.05 | 145504 | 351 |
| occ200 | check | tpcds | store_sales | ss_item_sk | occupancy:200 | 1 |  |  |  | 19.26 | 4722.81 | 401544 | 351 |
| occ200 | check | tpcds | store_sales | ss_net_paid | occupancy:200 | 1 |  |  |  | 14.93 | 5024.62 | 560664 | 351 |
| occ200 | check | tpcds | store_sales | ss_net_profit | occupancy:200 | 1 |  |  |  | 15.43 | 4691.14 | 560704 | 351 |
| occ200 | check | tpcds | store_sales | ss_promo_sk | occupancy:200 | 1 |  |  |  | 19.45 | 229.59 | 5616 | 351 |
| occ200 | check | tpcds | store_sales | ss_quantity | occupancy:200 | 1 |  |  |  | 19.33 | 226.06 | 5616 | 351 |
| occ200 | check | tpcds | store_sales | ss_sold_date_sk | occupancy:200 | 1 |  |  |  | 21.48 | 309.11 | 77616 | 351 |
| occ200 | check | tpcds | store_sales | ss_sold_time_sk | occupancy:200 | 1 |  |  |  | 14.91 | 366.37 | 231136 | 351 |
| occ200 | check | tpcds | store_sales | ss_store_sk | occupancy:200 | 1 |  |  |  | 16.21 | 58.32 | 5616 | 351 |
| occ200 | check | tpcds | store_sales | ss_ticket_number | occupancy:200 | 1 |  |  |  | 23.12 | 134.26 | 8424 | 351 |
| occ200 | check | tpcds | time_dim | t_hour | occupancy:200 | 1 |  |  |  | 1.68 | 2.79 | 160 | 10 |
| occ200 | check | tpcds | time_dim | t_minute | occupancy:200 | 1 |  |  |  | 1.27 | 1.72 | 160 | 10 |
| occ200 | check | tpcds | time_dim | t_time | occupancy:200 | 1 |  |  |  | 1.20 | 23.32 | 240 | 10 |
| occ200 | check | tpcds | time_dim | t_time_sk | occupancy:200 | 1 |  |  |  | 2.74 | 20.25 | 240 | 10 |
| occ200 | check | tpcds | web_page | wp_char_count | occupancy:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| occ200 | check | tpcds | web_returns | wr_item_sk | occupancy:200 | 1 |  |  |  | 1.13 | 89.58 | 9152 | 8 |
| occ200 | check | tpcds | web_returns | wr_order_number | occupancy:200 | 1 |  |  |  | 1.40 | 16.68 | 6216 | 8 |
| occ200 | check | tpcds | web_returns | wr_return_amt | occupancy:200 | 1 |  |  |  | 0.65 | 98.72 | 12768 | 8 |
| occ200 | check | tpcds | web_returns | wr_returned_date_sk | occupancy:200 | 1 |  |  |  | 0.46 | 8.19 | 1008 | 8 |
| occ200 | check | tpcds | web_returns | wr_web_page_sk | occupancy:200 | 1 |  |  |  | 1.33 | 3.32 | 128 | 8 |
| occ200 | check | tpcds | web_sales | ws_bill_addr_sk | occupancy:200 | 1 |  |  |  | 2.75 | 80.19 | 58160 | 87 |
| occ200 | check | tpcds | web_sales | ws_item_sk | occupancy:200 | 1 |  |  |  | 4.06 | 925.16 | 99528 | 87 |
| occ200 | check | tpcds | web_sales | ws_net_paid | occupancy:200 | 1 |  |  |  | 6.43 | 1112.26 | 138840 | 87 |
| occ200 | check | tpcds | web_sales | ws_net_profit | occupancy:200 | 1 |  |  |  | 4.76 | 1360.12 | 138800 | 87 |
| occ200 | check | tpcds | web_sales | ws_order_number | occupancy:200 | 1 |  |  |  | 3.14 | 31.30 | 2088 | 87 |
| occ200 | check | tpcds | web_sales | ws_promo_sk | occupancy:200 | 1 |  |  |  | 4.34 | 60.07 | 1392 | 87 |
| occ200 | check | tpcds | web_sales | ws_quantity | occupancy:200 | 1 |  |  |  | 3.97 | 48.09 | 1392 | 87 |
| occ200 | check | tpcds | web_sales | ws_ship_addr_sk | occupancy:200 | 1 |  |  |  | 4.24 | 83.27 | 58104 | 87 |
| occ200 | check | tpcds | web_sales | ws_ship_customer_sk | occupancy:200 | 1 |  |  |  | 4.52 | 77.69 | 65800 | 87 |
| occ200 | check | tpcds | web_sales | ws_ship_date_sk | occupancy:200 | 1 |  |  |  | 3.37 | 97.83 | 7968 | 87 |
| occ200 | check | tpcds | web_sales | ws_ship_hdemo_sk | occupancy:200 | 1 |  |  |  | 3.23 | 87.73 | 36096 | 87 |
| occ200 | check | tpcds | web_sales | ws_ship_mode_sk | occupancy:200 | 1 |  |  |  | 4.90 | 30.91 | 1392 | 87 |
| occ200 | check | tpcds | web_sales | ws_sold_date_sk | occupancy:200 | 1 |  |  |  | 4.83 | 67.94 | 19272 | 87 |
| occ200 | check | tpcds | web_sales | ws_warehouse_sk | occupancy:200 | 1 |  |  |  | 5.31 | 22.82 | 1392 | 87 |
| occ200 | check | tpcds | web_sales | ws_web_page_sk | occupancy:200 | 1 |  |  |  | 3.44 | 36.69 | 1392 | 87 |
| occ200 | check | tpcds | web_sales | ws_web_site_sk | occupancy:200 | 1 |  |  |  | 3.49 | 32.24 | 1392 | 87 |
| occ200 | check | tpch | checkpoint |  |  | 1 | 858.25 | 858.25 | 856.15 |  |  |  |  |
| occ200 | check | tpch | customer |  |  | 1 | 2885.18 | 2885.18 | 2884.91 |  |  |  |  |
| occ200 | check | tpch | lineitem |  |  | 1 | 99395.60 | 99395.60 | 99491.49 |  |  |  |  |
| occ200 | check | tpch | nation |  |  | 1 | 116.96 | 116.96 | 88.43 |  |  |  |  |
| occ200 | check | tpch | orders |  |  | 1 | 26035.13 | 26035.13 | 26051.96 |  |  |  |  |
| occ200 | check | tpch | part |  |  | 1 | 3786.60 | 3786.60 | 3795.25 |  |  |  |  |
| occ200 | check | tpch | partsupp |  |  | 1 | 12108.85 | 12108.85 | 12112.81 |  |  |  |  |
| occ200 | check | tpch | region |  |  | 1 | 71.77 | 71.77 | 76.18 |  |  |  |  |
| occ200 | check | tpch | supplier |  |  | 1 | 339.26 | 339.26 | 340.93 |  |  |  |  |
| occ200 | check | tpch | customer | c_acctbal | occupancy:200 | 1 |  |  |  | 0.62 | 279.83 | 28800 | 18 |
| occ200 | check | tpch | customer | c_custkey | occupancy:200 | 1 |  |  |  | 0.88 | 49.36 | 432 | 18 |
| occ200 | check | tpch | customer | c_nationkey | occupancy:200 | 1 |  |  |  | 0.79 | 10.57 | 288 | 18 |
| occ200 | check | tpch | lineitem | l_commitdate | occupancy:200 | 1 |  |  |  | 23.29 | 1221.86 | 73736 | 732 |
| occ200 | check | tpch | lineitem | l_discount | occupancy:200 | 1 |  |  |  | 26.76 | 274.97 | 11712 | 732 |
| occ200 | check | tpch | lineitem | l_orderkey | occupancy:200 | 1 |  |  |  | 33.75 | 1537.92 | 575392 | 732 |
| occ200 | check | tpch | lineitem | l_partkey | occupancy:200 | 1 |  |  |  | 38.39 | 8974.67 | 1156328 | 732 |
| occ200 | check | tpch | lineitem | l_quantity | occupancy:200 | 1 |  |  |  | 37.47 | 404.52 | 46848 | 732 |
| occ200 | check | tpch | lineitem | l_receiptdate | occupancy:200 | 1 |  |  |  | 23.78 | 1180.97 | 86016 | 732 |
| occ200 | check | tpch | lineitem | l_shipdate | occupancy:200 | 1 |  |  |  | 29.27 | 1175.18 | 82672 | 732 |
| occ200 | check | tpch | lineitem | l_suppkey | occupancy:200 | 1 |  |  |  | 27.25 | 3573.79 | 928624 | 732 |
| occ200 | check | tpch | nation | n_regionkey | occupancy:200 | 1 |  |  |  | 0.05 | 0.00 | 0 | 0 |
| occ200 | check | tpch | orders | o_custkey | occupancy:200 | 1 |  |  |  | 57.63 | 2443.91 | 289056 | 183 |
| occ200 | check | tpch | orders | o_orderdate | occupancy:200 | 1 |  |  |  | 8.31 | 295.95 | 15056 | 183 |
| occ200 | check | tpch | orders | o_orderkey | occupancy:200 | 1 |  |  |  | 9.45 | 2211.81 | 284016 | 183 |
| occ200 | check | tpch | part | p_size | occupancy:200 | 1 |  |  |  | 2.30 | 9.88 | 384 | 24 |
| occ200 | check | tpch | partsupp | ps_partkey | occupancy:200 | 1 |  |  |  | 4.60 | 71.36 | 2328 | 97 |
| occ200 | check | tpch | partsupp | ps_suppkey | occupancy:200 | 1 |  |  |  | 3.32 | 318.78 | 76600 | 97 |
| occ200 | check | tpch | supplier | s_nationkey | occupancy:200 | 1 |  |  |  | 0.19 | 1.55 | 16 | 1 |
| occ200 | check | tpch | supplier | s_suppkey | occupancy:200 | 1 |  |  |  | 0.53 | 1.60 | 24 | 1 |
| occ200 | count | clickbench | checkpoint |  |  | 1 | 3.62 | 3.62 | 13.44 |  |  |  |  |
| occ200 | count | clickbench | hits |  |  | 1 | 99431.64 | 99431.64 | 99511.14 |  |  |  |  |
| occ200 | count | clickbench | hits | advengineid | occupancy:200 | 1 |  |  |  | 9.44 | 29.23 | 1952 | 122 |
| occ200 | count | clickbench | hits | counterid | occupancy:200 | 1 |  |  |  | 11.47 | 16.60 | 1952 | 122 |
| occ200 | count | clickbench | hits | dontcounthits | occupancy:200 | 1 |  |  |  | 14.72 | 23.15 | 1952 | 122 |
| occ200 | count | clickbench | hits | eventtime | occupancy:200 | 1 |  |  |  | 16.42 | 1532.68 | 195056 | 122 |
| occ200 | count | clickbench | hits | isdownload | occupancy:200 | 1 |  |  |  | 9.99 | 26.83 | 1952 | 122 |
| occ200 | count | clickbench | hits | islink | occupancy:200 | 1 |  |  |  | 12.15 | 20.08 | 1952 | 122 |
| occ200 | count | clickbench | hits | isrefresh | occupancy:200 | 1 |  |  |  | 11.86 | 28.38 | 1952 | 122 |
| occ200 | count | clickbench | hits | refererhash | occupancy:200 | 1 |  |  |  | 27.66 | 747.70 | 195112 | 122 |
| occ200 | count | clickbench | hits | traficsourceid | occupancy:200 | 1 |  |  |  | 10.10 | 26.10 | 1952 | 122 |
| occ200 | count | clickbench | hits | urlhash | occupancy:200 | 1 |  |  |  | 33.72 | 1199.95 | 195032 | 122 |
| occ200 | count | clickbench | hits | userid | occupancy:200 | 1 |  |  |  | 10.06 | 161.35 | 195200 | 122 |
| occ200 | count | micro_cardinality_100 | checkpoint |  |  | 1 | 2.04 | 2.04 | 1.58 |  |  |  |  |
| occ200 | count | micro_cardinality_100 | sensor_records |  |  | 1 | 30784.32 | 30784.32 | 30790.83 |  |  |  |  |
| occ200 | count | micro_cardinality_100 | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 58.97 | 16025.87 | 1945344 | 1220 |
| occ200 | count | micro_cardinality_100 | sensor_records | user_id | occupancy:200 | 1 |  |  |  | 120.87 | 625.11 | 29280 | 1220 |
| occ200 | count | micro_cardinality_100000 | checkpoint |  |  | 1 | 35.79 | 35.79 | 71.05 |  |  |  |  |
| occ200 | count | micro_cardinality_100000 | sensor_records |  |  | 1 | 59304.37 | 59304.37 | 59371.79 |  |  |  |  |
| occ200 | count | micro_cardinality_100000 | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 72.85 | 16482.19 | 1945344 | 1220 |
| occ200 | count | micro_cardinality_100000 | sensor_records | user_id | occupancy:200 | 1 |  |  |  | 156.34 | 18963.44 | 1922360 | 1220 |
| occ200 | count | micro_outliers | checkpoint |  |  | 1 | 2.88 | 2.88 | 1.94 |  |  |  |  |
| occ200 | count | micro_outliers | sensor_records |  |  | 1 | 23537.19 | 23537.19 | 23550.93 |  |  |  |  |
| occ200 | count | micro_outliers | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 50.83 | 11551.83 | 1946296 | 1220 |
| occ200 | count | micro_sorted | checkpoint |  |  | 1 | 1.27 | 1.27 | 5.59 |  |  |  |  |
| occ200 | count | micro_sorted | sensor_records |  |  | 1 | 39522.48 | 39522.48 | 39546.54 |  |  |  |  |
| occ200 | count | micro_sorted | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 107.68 | 20555.92 | 1945344 | 1220 |
| occ200 | count | micro_unsorted | checkpoint |  |  | 1 | 0.97 | 0.97 | 1.02 |  |  |  |  |
| occ200 | count | micro_unsorted | sensor_records |  |  | 1 | 34796.42 | 34796.42 | 34798.38 |  |  |  |  |
| occ200 | count | micro_unsorted | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 46.11 | 18732.72 | 1942240 | 1220 |
| occ200 | count | tpcds | call_center |  |  | 1 | 86.63 | 86.63 | 89.55 |  |  |  |  |
| occ200 | count | tpcds | catalog_page |  |  | 1 | 251.92 | 251.92 | 246.76 |  |  |  |  |
| occ200 | count | tpcds | catalog_returns |  |  | 1 | 3351.35 | 3351.35 | 3371.69 |  |  |  |  |
| occ200 | count | tpcds | catalog_sales |  |  | 1 | 26464.31 | 26464.31 | 26496.91 |  |  |  |  |
| occ200 | count | tpcds | checkpoint |  |  | 1 | 660.25 | 660.25 | 712.25 |  |  |  |  |
| occ200 | count | tpcds | customer |  |  | 1 | 1932.48 | 1932.48 | 1901.93 |  |  |  |  |
| occ200 | count | tpcds | customer_address |  |  | 1 | 1966.80 | 1966.80 | 1986.07 |  |  |  |  |
| occ200 | count | tpcds | customer_demographics |  |  | 1 | 15538.87 | 15538.87 | 15590.56 |  |  |  |  |
| occ200 | count | tpcds | date_dim |  |  | 1 | 1662.66 | 1662.66 | 1612.42 |  |  |  |  |
| occ200 | count | tpcds | household_demographics |  |  | 1 | 74.04 | 74.04 | 73.94 |  |  |  |  |
| occ200 | count | tpcds | income_band |  |  | 1 | 12.50 | 12.50 | 12.91 |  |  |  |  |
| occ200 | count | tpcds | inventory |  |  | 1 | 40846.67 | 40846.67 | 40911.80 |  |  |  |  |
| occ200 | count | tpcds | item |  |  | 1 | 1704.15 | 1704.15 | 1709.25 |  |  |  |  |
| occ200 | count | tpcds | promotion |  |  | 1 | 361.71 | 361.71 | 366.27 |  |  |  |  |
| occ200 | count | tpcds | reason |  |  | 1 | 31.03 | 31.03 | 30.37 |  |  |  |  |
| occ200 | count | tpcds | ship_mode |  |  | 1 | 47.33 | 47.33 | 51.83 |  |  |  |  |
| occ200 | count | tpcds | store |  |  | 1 | 27.75 | 27.75 | 28.53 |  |  |  |  |
| occ200 | count | tpcds | store_returns |  |  | 1 | 7595.83 | 7595.83 | 7605.00 |  |  |  |  |
| occ200 | count | tpcds | store_sales |  |  | 1 | 55099.43 | 55099.43 | 55192.98 |  |  |  |  |
| occ200 | count | tpcds | time_dim |  |  | 1 | 1029.99 | 1029.99 | 1032.66 |  |  |  |  |
| occ200 | count | tpcds | warehouse |  |  | 1 | 29.52 | 29.52 | 32.32 |  |  |  |  |
| occ200 | count | tpcds | web_page |  |  | 1 | 33.67 | 33.67 | 32.41 |  |  |  |  |
| occ200 | count | tpcds | web_returns |  |  | 1 | 1219.42 | 1219.42 | 1391.31 |  |  |  |  |
| occ200 | count | tpcds | web_sales |  |  | 1 | 15450.01 | 15450.01 | 15291.29 |  |  |  |  |
| occ200 | count | tpcds | web_site |  |  | 1 | 56.64 | 56.64 | 54.34 |  |  |  |  |
| occ200 | count | tpcds | catalog_page | cp_catalog_page_sk | occupancy:200 | 1 |  |  |  | 0.09 | 1.80 | 24 | 1 |
| occ200 | count | tpcds | catalog_returns | cr_catalog_page_sk | occupancy:200 | 1 |  |  |  | 1.32 | 40.98 | 2608 | 17 |
| occ200 | count | tpcds | catalog_returns | cr_item_sk | occupancy:200 | 1 |  |  |  | 0.55 | 209.89 | 19448 | 17 |
| occ200 | count | tpcds | catalog_returns | cr_order_number | occupancy:200 | 1 |  |  |  | 7.35 | 71.28 | 19648 | 17 |
| occ200 | count | tpcds | catalog_returns | cr_return_amount | occupancy:200 | 1 |  |  |  | 5.22 | 314.54 | 27152 | 17 |
| occ200 | count | tpcds | catalog_returns | cr_returned_date_sk | occupancy:200 | 1 |  |  |  | 0.86 | 17.19 | 512 | 17 |
| occ200 | count | tpcds | catalog_sales | cs_bill_addr_sk | occupancy:200 | 1 |  |  |  | 6.58 | 242.61 | 146080 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_bill_customer_sk | occupancy:200 | 1 |  |  |  | 5.60 | 223.68 | 166528 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_bill_hdemo_sk | occupancy:200 | 1 |  |  |  | 5.43 | 198.97 | 86408 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_call_center_sk | occupancy:200 | 1 |  |  |  | 6.07 | 34.15 | 2800 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_catalog_page_sk | occupancy:200 | 1 |  |  |  | 7.06 | 154.56 | 18832 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_item_sk | occupancy:200 | 1 |  |  |  | 5.62 | 1989.27 | 200200 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_net_paid | occupancy:200 | 1 |  |  |  | 5.24 | 2784.12 | 279248 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_net_profit | occupancy:200 | 1 |  |  |  | 28.44 | 2679.22 | 279336 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_order_number | occupancy:200 | 1 |  |  |  | 7.67 | 77.35 | 4200 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_promo_sk | occupancy:200 | 1 |  |  |  | 11.49 | 151.35 | 2800 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_quantity | occupancy:200 | 1 |  |  |  | 5.56 | 92.77 | 2800 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_ship_addr_sk | occupancy:200 | 1 |  |  |  | 5.95 | 244.34 | 146088 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_ship_customer_sk | occupancy:200 | 1 |  |  |  | 29.99 | 242.05 | 166560 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_ship_date_sk | occupancy:200 | 1 |  |  |  | 5.80 | 115.24 | 2800 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_ship_mode_sk | occupancy:200 | 1 |  |  |  | 6.70 | 74.27 | 2800 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_sold_date_sk | occupancy:200 | 1 |  |  |  | 6.66 | 34.68 | 2800 | 175 |
| occ200 | count | tpcds | catalog_sales | cs_warehouse_sk | occupancy:200 | 1 |  |  |  | 5.71 | 44.88 | 2800 | 175 |
| occ200 | count | tpcds | customer | c_birth_month | occupancy:200 | 1 |  |  |  | 0.55 | 6.97 | 192 | 12 |
| occ200 | count | tpcds | customer | c_current_addr_sk | occupancy:200 | 1 |  |  |  | 1.35 | 158.89 | 19000 | 12 |
| occ200 | count | tpcds | customer | c_current_hdemo_sk | occupancy:200 | 1 |  |  |  | 0.50 | 48.83 | 10272 | 12 |
| occ200 | count | tpcds | customer | c_customer_sk | occupancy:200 | 1 |  |  |  | 0.64 | 29.05 | 288 | 12 |
| occ200 | count | tpcds | customer | c_first_sales_date_sk | occupancy:200 | 1 |  |  |  | 0.52 | 29.96 | 3056 | 12 |
| occ200 | count | tpcds | customer | c_first_shipto_date_sk | occupancy:200 | 1 |  |  |  | 0.45 | 27.18 | 3056 | 12 |
| occ200 | count | tpcds | customer_address | ca_address_sk | occupancy:200 | 1 |  |  |  | 0.68 | 11.89 | 144 | 6 |
| occ200 | count | tpcds | customer_address | ca_gmt_offset | occupancy:200 | 1 |  |  |  | 0.36 | 1.39 | 144 | 6 |
| occ200 | count | tpcds | customer_demographics | cd_demo_sk | occupancy:200 | 1 |  |  |  | 8.45 | 547.87 | 5616 | 234 |
| occ200 | count | tpcds | date_dim | d_date | occupancy:200 | 1 |  |  |  | 0.28 | 27.01 | 192 | 8 |
| occ200 | count | tpcds | date_dim | d_date_sk | occupancy:200 | 1 |  |  |  | 0.38 | 23.19 | 192 | 8 |
| occ200 | count | tpcds | date_dim | d_dom | occupancy:200 | 1 |  |  |  | 0.65 | 2.30 | 128 | 8 |
| occ200 | count | tpcds | date_dim | d_dow | occupancy:200 | 1 |  |  |  | 1.05 | 1.53 | 128 | 8 |
| occ200 | count | tpcds | date_dim | d_month_seq | occupancy:200 | 1 |  |  |  | 5.55 | 2.10 | 128 | 8 |
| occ200 | count | tpcds | date_dim | d_moy | occupancy:200 | 1 |  |  |  | 4.66 | 1.03 | 128 | 8 |
| occ200 | count | tpcds | date_dim | d_qoy | occupancy:200 | 1 |  |  |  | 1.81 | 0.94 | 128 | 8 |
| occ200 | count | tpcds | date_dim | d_week_seq | occupancy:200 | 1 |  |  |  | 1.61 | 3.09 | 192 | 8 |
| occ200 | count | tpcds | date_dim | d_year | occupancy:200 | 1 |  |  |  | 2.33 | 0.94 | 128 | 8 |
| occ200 | count | tpcds | household_demographics | hd_demo_sk | occupancy:200 | 1 |  |  |  | 0.03 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | household_demographics | hd_dep_count | occupancy:200 | 1 |  |  |  | 1.64 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | household_demographics | hd_income_band_sk | occupancy:200 | 1 |  |  |  | 0.09 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | household_demographics | hd_vehicle_count | occupancy:200 | 1 |  |  |  | 2.85 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | income_band | ib_lower_bound | occupancy:200 | 1 |  |  |  | 0.07 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | income_band | ib_upper_bound | occupancy:200 | 1 |  |  |  | 0.02 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | inventory | inv_date_sk | occupancy:200 | 1 |  |  |  | 82.08 | 178.10 | 22928 | 1433 |
| occ200 | count | tpcds | inventory | inv_item_sk | occupancy:200 | 1 |  |  |  | 44.99 | 11884.12 | 818256 | 1433 |
| occ200 | count | tpcds | inventory | inv_quantity_on_hand | occupancy:200 | 1 |  |  |  | 185.56 | 1664.87 | 34392 | 1433 |
| occ200 | count | tpcds | inventory | inv_warehouse_sk | occupancy:200 | 1 |  |  |  | 62.61 | 207.74 | 22928 | 1433 |
| occ200 | count | tpcds | item | i_current_price | occupancy:200 | 1 |  |  |  | 0.40 | 3.02 | 1680 | 2 |
| occ200 | count | tpcds | item | i_item_sk | occupancy:200 | 1 |  |  |  | 0.64 | 4.39 | 48 | 2 |
| occ200 | count | tpcds | item | i_manager_id | occupancy:200 | 1 |  |  |  | 0.44 | 0.87 | 32 | 2 |
| occ200 | count | tpcds | item | i_manufact_id | occupancy:200 | 1 |  |  |  | 0.41 | 1.75 | 112 | 2 |
| occ200 | count | tpcds | reason | r_reason_sk | occupancy:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | store | s_market_id | occupancy:200 | 1 |  |  |  | 0.19 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | store | s_number_employees | occupancy:200 | 1 |  |  |  | 0.26 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | store | s_store_sk | occupancy:200 | 1 |  |  |  | 0.05 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | store_returns | sr_cdemo_sk | occupancy:200 | 1 |  |  |  | 3.87 | 525.66 | 55976 | 35 |
| occ200 | count | tpcds | store_returns | sr_customer_sk | occupancy:200 | 1 |  |  |  | 2.17 | 485.54 | 54440 | 35 |
| occ200 | count | tpcds | store_returns | sr_item_sk | occupancy:200 | 1 |  |  |  | 2.19 | 520.02 | 40040 | 35 |
| occ200 | count | tpcds | store_returns | sr_return_amt | occupancy:200 | 1 |  |  |  | 3.24 | 599.68 | 55784 | 35 |
| occ200 | count | tpcds | store_returns | sr_returned_date_sk | occupancy:200 | 1 |  |  |  | 4.74 | 50.54 | 3480 | 35 |
| occ200 | count | tpcds | store_returns | sr_store_sk | occupancy:200 | 1 |  |  |  | 2.14 | 17.86 | 560 | 35 |
| occ200 | count | tpcds | store_returns | sr_ticket_number | occupancy:200 | 1 |  |  |  | 5.25 | 90.10 | 26952 | 35 |
| occ200 | count | tpcds | store_sales | ss_addr_sk | occupancy:200 | 1 |  |  |  | 14.51 | 385.90 | 234408 | 351 |
| occ200 | count | tpcds | store_sales | ss_customer_sk | occupancy:200 | 1 |  |  |  | 15.91 | 400.62 | 265312 | 351 |
| occ200 | count | tpcds | store_sales | ss_hdemo_sk | occupancy:200 | 1 |  |  |  | 14.83 | 364.79 | 145504 | 351 |
| occ200 | count | tpcds | store_sales | ss_item_sk | occupancy:200 | 1 |  |  |  | 14.10 | 4779.95 | 401544 | 351 |
| occ200 | count | tpcds | store_sales | ss_net_paid | occupancy:200 | 1 |  |  |  | 21.85 | 5357.38 | 560664 | 351 |
| occ200 | count | tpcds | store_sales | ss_net_profit | occupancy:200 | 1 |  |  |  | 13.69 | 5070.97 | 560704 | 351 |
| occ200 | count | tpcds | store_sales | ss_promo_sk | occupancy:200 | 1 |  |  |  | 12.95 | 278.94 | 5616 | 351 |
| occ200 | count | tpcds | store_sales | ss_quantity | occupancy:200 | 1 |  |  |  | 14.01 | 217.46 | 5616 | 351 |
| occ200 | count | tpcds | store_sales | ss_sold_date_sk | occupancy:200 | 1 |  |  |  | 24.57 | 320.01 | 77616 | 351 |
| occ200 | count | tpcds | store_sales | ss_sold_time_sk | occupancy:200 | 1 |  |  |  | 16.80 | 395.64 | 231136 | 351 |
| occ200 | count | tpcds | store_sales | ss_store_sk | occupancy:200 | 1 |  |  |  | 18.23 | 60.89 | 5616 | 351 |
| occ200 | count | tpcds | store_sales | ss_ticket_number | occupancy:200 | 1 |  |  |  | 12.85 | 143.09 | 8424 | 351 |
| occ200 | count | tpcds | time_dim | t_hour | occupancy:200 | 1 |  |  |  | 1.56 | 1.08 | 160 | 10 |
| occ200 | count | tpcds | time_dim | t_minute | occupancy:200 | 1 |  |  |  | 1.04 | 1.57 | 160 | 10 |
| occ200 | count | tpcds | time_dim | t_time | occupancy:200 | 1 |  |  |  | 1.82 | 19.23 | 240 | 10 |
| occ200 | count | tpcds | time_dim | t_time_sk | occupancy:200 | 1 |  |  |  | 2.61 | 21.82 | 240 | 10 |
| occ200 | count | tpcds | web_page | wp_char_count | occupancy:200 | 1 |  |  |  | 0.01 | 0.00 | 0 | 0 |
| occ200 | count | tpcds | web_returns | wr_item_sk | occupancy:200 | 1 |  |  |  | 0.78 | 91.28 | 9152 | 8 |
| occ200 | count | tpcds | web_returns | wr_order_number | occupancy:200 | 1 |  |  |  | 0.40 | 18.78 | 6216 | 8 |
| occ200 | count | tpcds | web_returns | wr_return_amt | occupancy:200 | 1 |  |  |  | 0.42 | 108.81 | 12768 | 8 |
| occ200 | count | tpcds | web_returns | wr_returned_date_sk | occupancy:200 | 1 |  |  |  | 0.59 | 10.45 | 1008 | 8 |
| occ200 | count | tpcds | web_returns | wr_web_page_sk | occupancy:200 | 1 |  |  |  | 0.35 | 3.16 | 128 | 8 |
| occ200 | count | tpcds | web_sales | ws_bill_addr_sk | occupancy:200 | 1 |  |  |  | 3.33 | 110.03 | 58160 | 87 |
| occ200 | count | tpcds | web_sales | ws_item_sk | occupancy:200 | 1 |  |  |  | 3.90 | 1425.59 | 99528 | 87 |
| occ200 | count | tpcds | web_sales | ws_net_paid | occupancy:200 | 1 |  |  |  | 3.79 | 1632.68 | 138840 | 87 |
| occ200 | count | tpcds | web_sales | ws_net_profit | occupancy:200 | 1 |  |  |  | 2.94 | 1511.44 | 138800 | 87 |
| occ200 | count | tpcds | web_sales | ws_order_number | occupancy:200 | 1 |  |  |  | 7.31 | 43.86 | 2088 | 87 |
| occ200 | count | tpcds | web_sales | ws_promo_sk | occupancy:200 | 1 |  |  |  | 3.66 | 73.22 | 1392 | 87 |
| occ200 | count | tpcds | web_sales | ws_quantity | occupancy:200 | 1 |  |  |  | 25.04 | 57.82 | 1392 | 87 |
| occ200 | count | tpcds | web_sales | ws_ship_addr_sk | occupancy:200 | 1 |  |  |  | 4.48 | 102.97 | 58104 | 87 |
| occ200 | count | tpcds | web_sales | ws_ship_customer_sk | occupancy:200 | 1 |  |  |  | 3.23 | 100.53 | 65800 | 87 |
| occ200 | count | tpcds | web_sales | ws_ship_date_sk | occupancy:200 | 1 |  |  |  | 6.33 | 150.93 | 7968 | 87 |
| occ200 | count | tpcds | web_sales | ws_ship_hdemo_sk | occupancy:200 | 1 |  |  |  | 4.44 | 86.67 | 36096 | 87 |
| occ200 | count | tpcds | web_sales | ws_ship_mode_sk | occupancy:200 | 1 |  |  |  | 3.69 | 41.90 | 1392 | 87 |
| occ200 | count | tpcds | web_sales | ws_sold_date_sk | occupancy:200 | 1 |  |  |  | 7.25 | 107.18 | 19272 | 87 |
| occ200 | count | tpcds | web_sales | ws_warehouse_sk | occupancy:200 | 1 |  |  |  | 3.40 | 37.56 | 1392 | 87 |
| occ200 | count | tpcds | web_sales | ws_web_page_sk | occupancy:200 | 1 |  |  |  | 2.88 | 52.50 | 1392 | 87 |
| occ200 | count | tpcds | web_sales | ws_web_site_sk | occupancy:200 | 1 |  |  |  | 13.51 | 54.20 | 1392 | 87 |
| occ200 | count | tpch | checkpoint |  |  | 1 | 294.29 | 294.29 | 290.67 |  |  |  |  |
| occ200 | count | tpch | customer |  |  | 1 | 2343.61 | 2343.61 | 2349.69 |  |  |  |  |
| occ200 | count | tpch | lineitem |  |  | 1 | 90353.89 | 90353.89 | 90405.18 |  |  |  |  |
| occ200 | count | tpch | nation |  |  | 1 | 127.51 | 127.51 | 143.91 |  |  |  |  |
| occ200 | count | tpch | orders |  |  | 1 | 29899.03 | 29899.03 | 29908.37 |  |  |  |  |
| occ200 | count | tpch | part |  |  | 1 | 3638.66 | 3638.66 | 3656.43 |  |  |  |  |
| occ200 | count | tpch | partsupp |  |  | 1 | 12611.06 | 12611.06 | 12659.80 |  |  |  |  |
| occ200 | count | tpch | region |  |  | 1 | 174.46 | 174.46 | 75.19 |  |  |  |  |
| occ200 | count | tpch | supplier |  |  | 1 | 219.84 | 219.84 | 221.44 |  |  |  |  |
| occ200 | count | tpch | customer | c_acctbal | occupancy:200 | 1 |  |  |  | 3.12 | 229.43 | 28800 | 18 |
| occ200 | count | tpch | customer | c_custkey | occupancy:200 | 1 |  |  |  | 2.08 | 35.67 | 432 | 18 |
| occ200 | count | tpch | customer | c_nationkey | occupancy:200 | 1 |  |  |  | 2.30 | 6.46 | 288 | 18 |
| occ200 | count | tpch | lineitem | l_commitdate | occupancy:200 | 1 |  |  |  | 29.54 | 1040.66 | 73736 | 732 |
| occ200 | count | tpch | lineitem | l_discount | occupancy:200 | 1 |  |  |  | 23.01 | 254.57 | 11712 | 732 |
| occ200 | count | tpch | lineitem | l_orderkey | occupancy:200 | 1 |  |  |  | 30.96 | 1346.31 | 575392 | 732 |
| occ200 | count | tpch | lineitem | l_partkey | occupancy:200 | 1 |  |  |  | 24.72 | 7980.56 | 1156328 | 732 |
| occ200 | count | tpch | lineitem | l_quantity | occupancy:200 | 1 |  |  |  | 29.48 | 370.85 | 46848 | 732 |
| occ200 | count | tpch | lineitem | l_receiptdate | occupancy:200 | 1 |  |  |  | 27.46 | 1109.88 | 86016 | 732 |
| occ200 | count | tpch | lineitem | l_shipdate | occupancy:200 | 1 |  |  |  | 31.02 | 1059.23 | 82672 | 732 |
| occ200 | count | tpch | lineitem | l_suppkey | occupancy:200 | 1 |  |  |  | 23.33 | 3193.16 | 928624 | 732 |
| occ200 | count | tpch | nation | n_regionkey | occupancy:200 | 1 |  |  |  | 0.06 | 0.00 | 0 | 0 |
| occ200 | count | tpch | orders | o_custkey | occupancy:200 | 1 |  |  |  | 7.00 | 2262.37 | 289056 | 183 |
| occ200 | count | tpch | orders | o_orderdate | occupancy:200 | 1 |  |  |  | 7.92 | 269.39 | 15056 | 183 |
| occ200 | count | tpch | orders | o_orderkey | occupancy:200 | 1 |  |  |  | 9.10 | 2362.73 | 284016 | 183 |
| occ200 | count | tpch | part | p_size | occupancy:200 | 1 |  |  |  | 1.06 | 9.15 | 384 | 24 |
| occ200 | count | tpch | partsupp | ps_partkey | occupancy:200 | 1 |  |  |  | 5.50 | 74.89 | 2328 | 97 |
| occ200 | count | tpch | partsupp | ps_suppkey | occupancy:200 | 1 |  |  |  | 3.65 | 291.45 | 76600 | 97 |
| occ200 | count | tpch | supplier | s_nationkey | occupancy:200 | 1 |  |  |  | 0.28 | 0.33 | 16 | 1 |
| occ200 | count | tpch | supplier | s_suppkey | occupancy:200 | 1 |  |  |  | 0.32 | 1.41 | 24 | 1 |
| occts200 | time | micro_outliers | checkpoint |  |  | 1 | 7.84 | 7.84 | 4.13 |  |  |  |  |
| occts200 | time | micro_outliers | sensor_records |  |  | 1 | 25012.76 | 25012.76 | 25026.58 |  |  |  |  |
| occts200 | time | micro_outliers | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 77.57 | 12141.45 | 1946296 | 1220 |
| occts200 | time | micro_unsorted | checkpoint |  |  | 1 | 7.25 | 7.25 | 10.39 |  |  |  |  |
| occts200 | time | micro_unsorted | sensor_records |  |  | 1 | 22592.74 | 22592.74 | 22614.29 |  |  |  |  |
| occts200 | time | micro_unsorted | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 38.63 | 14268.44 | 1942240 | 1220 |
| occts200_b | time | micro_outliers | checkpoint |  |  | 1 | 6.71 | 6.71 | 2.69 |  |  |  |  |
| occts200_b | time | micro_outliers | sensor_records |  |  | 1 | 27710.15 | 27710.15 | 27762.39 |  |  |  |  |
| occts200_b | time | micro_outliers | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 58.40 | 13040.32 | 1946296 | 1220 |
| occts200_b | time | micro_unsorted | checkpoint |  |  | 1 | 45.96 | 45.96 | 20.55 |  |  |  |  |
| occts200_b | time | micro_unsorted | sensor_records |  |  | 1 | 35145.79 | 35145.79 | 35180.52 |  |  |  |  |
| occts200_b | time | micro_unsorted | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 58.97 | 21304.32 | 1942240 | 1220 |
| occts200_c | time | micro_outliers | checkpoint |  |  | 1 | 4.34 | 4.34 | 7.41 |  |  |  |  |
| occts200_c | time | micro_outliers | sensor_records |  |  | 1 | 29545.20 | 29545.20 | 29564.81 |  |  |  |  |
| occts200_c | time | micro_outliers | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 164.19 | 12079.48 | 1946296 | 1220 |
| occts200_c | time | micro_unsorted | checkpoint |  |  | 1 | 4.11 | 4.11 | 8.10 |  |  |  |  |
| occts200_c | time | micro_unsorted | sensor_records |  |  | 1 | 37701.55 | 37701.55 | 37732.33 |  |  |  |  |
| occts200_c | time | micro_unsorted | sensor_records | timestamp_ms | occupancy:200 | 1 |  |  |  | 56.57 | 22213.85 | 1942240 | 1220 |
| stock | time | micro_outliers | checkpoint |  |  | 1 |  |  | 2.11 |  |  |  |  |
| stock | time | micro_outliers | sensor_records |  |  | 1 |  |  | 14905.80 |  |  |  |  |
| stock | time | micro_unsorted | checkpoint |  |  | 1 |  |  | 5.70 |  |  |  |  |
| stock | time | micro_unsorted | sensor_records |  |  | 1 |  |  | 14461.37 |  |  |  |  |
| stock_b | time | micro_outliers | checkpoint |  |  | 1 |  |  | 5.09 |  |  |  |  |
| stock_b | time | micro_outliers | sensor_records |  |  | 1 |  |  | 22817.25 |  |  |  |  |
| stock_b | time | micro_unsorted | checkpoint |  |  | 1 |  |  | 8.01 |  |  |  |  |
| stock_b | time | micro_unsorted | sensor_records |  |  | 1 |  |  | 11785.26 |  |  |  |  |
| stock_c | time | micro_outliers | checkpoint |  |  | 1 |  |  | 6.78 |  |  |  |  |
| stock_c | time | micro_outliers | sensor_records |  |  | 1 |  |  | 24958.53 |  |  |  |  |
| stock_c | time | micro_unsorted | checkpoint |  |  | 1 |  |  | 35.92 |  |  |  |  |
| stock_c | time | micro_unsorted | sensor_records |  |  | 1 |  |  | 19786.68 |  |  |  |  |
| stock_d | time | micro_unsorted | checkpoint |  |  | 1 |  |  | 0.56 |  |  |  |  |
| stock_d | time | micro_unsorted | sensor_records |  |  | 1 |  |  | 13998.20 |  |  |  |  |
| stock_e | time | micro_unsorted | checkpoint |  |  | 1 |  |  | 4.88 |  |  |  |  |
| stock_e | time | micro_unsorted | sensor_records |  |  | 1 |  |  | 12453.98 |  |  |  |  |
| sweep_nul20 | count | micro_cardinality_100 | sensor_records |  |  | 1 | 19141.10 | 19141.10 |  |  |  |  |  |
| sweep_nul20 | count | micro_cardinality_100 | sensor_records | timestamp_ms | nullspace:20 | 1 |  |  |  | 33.62 | 12913.58 | 193576 | 1220 |
| sweep_nul20 | count | micro_cardinality_100 | sensor_records | user_id | nullspace:20 | 1 |  |  |  | 59.41 | 1483.04 | 195200 | 1220 |
| sweep_nul20 | count | micro_outliers | checkpoint |  |  | 1 | 9.57 | 9.57 | 1.30 |  |  |  |  |
| sweep_nul20 | count | micro_outliers | sensor_records |  |  | 1 | 32721.80 | 32721.80 | 32738.52 |  |  |  |  |
| sweep_nul20 | count | micro_outliers | sensor_records | timestamp_ms | nullspace:20 | 1 |  |  |  | 94.58 | 18187.51 | 193568 | 1220 |
| sweep_nul20 | count | micro_sorted | checkpoint |  |  | 1 | 11.35 | 11.35 | 8.56 |  |  |  |  |
| sweep_nul20 | count | micro_sorted | sensor_records |  |  | 1 | 22358.82 | 22358.82 | 22360.83 |  |  |  |  |
| sweep_nul20 | count | micro_sorted | sensor_records | timestamp_ms | nullspace:20 | 1 |  |  |  | 45.51 | 15574.41 | 193576 | 1220 |
| sweep_nul20 | count | micro_unsorted | checkpoint |  |  | 1 | 64.25 | 64.25 | 57.31 |  |  |  |  |
| sweep_nul20 | count | micro_unsorted | sensor_records |  |  | 1 | 33286.31 | 33286.31 | 33301.19 |  |  |  |  |
| sweep_nul20 | count | micro_unsorted | sensor_records | timestamp_ms | nullspace:20 | 1 |  |  |  | 111.91 | 17407.19 | 193376 | 1220 |
| sweep_occ20 | count | micro_cardinality_100 | checkpoint |  |  | 1 | 3.30 | 3.30 | 1.43 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_100 | sensor_records |  |  | 1 | 24189.99 | 24189.99 | 24206.26 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_100 | sensor_records | timestamp_ms | occupancy:20 | 1 |  |  |  | 57.43 | 8973.33 | 193384 | 1220 |
| sweep_occ20 | count | micro_cardinality_100 | sensor_records | user_id | occupancy:20 | 1 |  |  |  | 205.24 | 988.62 | 29280 | 1220 |
| sweep_occ20 | count | micro_cardinality_1000 | checkpoint |  |  | 1 | 2.99 | 2.99 | 0.78 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_1000 | sensor_records |  |  | 1 | 16044.36 | 16044.36 | 16059.26 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_1000 | sensor_records | timestamp_ms | occupancy:20 | 1 |  |  |  | 43.09 | 6328.13 | 193384 | 1220 |
| sweep_occ20 | count | micro_cardinality_1000 | sensor_records | user_id | occupancy:20 | 1 |  |  |  | 57.67 | 1048.38 | 165920 | 1220 |
| sweep_occ20 | count | micro_cardinality_10000 | checkpoint |  |  | 1 | 1.90 | 1.90 | 1.01 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_10000 | sensor_records |  |  | 1 | 20741.56 | 20741.56 | 20760.36 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_10000 | sensor_records | timestamp_ms | occupancy:20 | 1 |  |  |  | 41.66 | 6654.95 | 193384 | 1220 |
| sweep_occ20 | count | micro_cardinality_10000 | sensor_records | user_id | occupancy:20 | 1 |  |  |  | 89.59 | 3076.70 | 131544 | 1220 |
| sweep_occ20 | count | micro_cardinality_100000 | checkpoint |  |  | 1 | 32.63 | 32.63 | 23.21 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_100000 | sensor_records |  |  | 1 | 24893.25 | 24893.25 | 24904.57 |  |  |  |  |
| sweep_occ20 | count | micro_cardinality_100000 | sensor_records | timestamp_ms | occupancy:20 | 1 |  |  |  | 42.30 | 7400.38 | 193384 | 1220 |
| sweep_occ20 | count | micro_cardinality_100000 | sensor_records | user_id | occupancy:20 | 1 |  |  |  | 55.87 | 5145.07 | 190192 | 1220 |
| sweep_occ20 | count | micro_outliers | checkpoint |  |  | 1 | 18.70 | 18.70 | 20.41 |  |  |  |  |
| sweep_occ20 | count | micro_outliers | sensor_records |  |  | 1 | 22879.02 | 22879.02 | 22943.34 |  |  |  |  |
| sweep_occ20 | count | micro_outliers | sensor_records | timestamp_ms | occupancy:20 | 1 |  |  |  | 103.10 | 10982.90 | 194824 | 1220 |
| sweep_occ20 | count | micro_sorted | checkpoint |  |  | 1 | 2.51 | 2.51 | 1.64 |  |  |  |  |
| sweep_occ20 | count | micro_sorted | sensor_records |  |  | 1 | 21764.85 | 21764.85 | 21784.84 |  |  |  |  |
| sweep_occ20 | count | micro_sorted | sensor_records | timestamp_ms | occupancy:20 | 1 |  |  |  | 63.75 | 8381.95 | 193384 | 1220 |
| sweep_occ20 | count | micro_unsorted | checkpoint |  |  | 1 | 1.45 | 1.45 | 5.50 |  |  |  |  |
| sweep_occ20 | count | micro_unsorted | sensor_records |  |  | 1 | 37078.26 | 37078.26 | 37094.23 |  |  |  |  |
| sweep_occ20 | count | micro_unsorted | sensor_records | timestamp_ms | occupancy:20 | 1 |  |  |  | 53.87 | 15092.26 | 193720 | 1220 |

