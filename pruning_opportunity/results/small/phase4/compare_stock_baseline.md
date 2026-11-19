# Phase 4 `baseline` counting pass vs. stock instrumented v1.4.4 (Phase 1 `count` run)

| setup | queries | identical result | identical counters (all scans, all filters) | scans matched by identity (scan ids permuted) | scans with leaves relabelled static -> join |
|---|---|---|---|---|---|
| point_unsorted | 1000 | 1000 | 1000 | 0 | 0 |
| range_seconds_unsorted | 1000 | 1000 | 1000 | 0 | 0 |
| range_minutes_unsorted | 1000 | 1000 | 1000 | 0 | 0 |
| range_hours_unsorted | 1000 | 1000 | 1000 | 0 | 0 |
| point_outliers | 1000 | 1000 | 1000 | 0 | 0 |
| range_seconds_outliers | 1000 | 1000 | 1000 | 0 | 0 |
| range_minutes_outliers | 1000 | 1000 | 1000 | 0 | 0 |
| range_hours_outliers | 1000 | 1000 | 1000 | 0 | 0 |
| point_sorted | 1000 | 1000 | 1000 | 0 | 0 |
| range_seconds_sorted | 1000 | 1000 | 1000 | 0 | 0 |
| range_minutes_sorted | 1000 | 1000 | 1000 | 0 | 0 |
| range_hours_sorted | 1000 | 1000 | 1000 | 0 | 0 |
| cardinality_100 | 910 | 448 | 910 | 0 | 0 |
| cardinality_100000 | 200 | 200 | 200 | 0 | 0 |
| tpch | 22 | 22 | 22 | 0 | 35 |
| tpcds | 99 | 99 | 99 | 1 | 263 |
| clickbench | 43 | 43 | 42 | 0 | 2 |

Differences (first 40, full list in compare_stock_baseline.csv):

* cardinality_100/0311: result_equal=False 
* cardinality_100/0312: result_equal=False 
* cardinality_100/0313: result_equal=False 
* cardinality_100/0314: result_equal=False 
* cardinality_100/0316: result_equal=False 
* cardinality_100/0317: result_equal=False 
* cardinality_100/0318: result_equal=False 
* cardinality_100/0319: result_equal=False 
* cardinality_100/0321: result_equal=False 
* cardinality_100/0322: result_equal=False 
* cardinality_100/0323: result_equal=False 
* cardinality_100/0324: result_equal=False 
* cardinality_100/0326: result_equal=False 
* cardinality_100/0327: result_equal=False 
* cardinality_100/0328: result_equal=False 
* cardinality_100/0329: result_equal=False 
* cardinality_100/0331: result_equal=False 
* cardinality_100/0332: result_equal=False 
* cardinality_100/0333: result_equal=False 
* cardinality_100/0334: result_equal=False 
* cardinality_100/0336: result_equal=False 
* cardinality_100/0337: result_equal=False 
* cardinality_100/0338: result_equal=False 
* cardinality_100/0339: result_equal=False 
* cardinality_100/0341: result_equal=False 
* cardinality_100/0342: result_equal=False 
* cardinality_100/0343: result_equal=False 
* cardinality_100/0344: result_equal=False 
* cardinality_100/0346: result_equal=False 
* cardinality_100/0347: result_equal=False 
* cardinality_100/0348: result_equal=False 
* cardinality_100/0349: result_equal=False 
* cardinality_100/0351: result_equal=False 
* cardinality_100/0352: result_equal=False 
* cardinality_100/0353: result_equal=False 
* cardinality_100/0354: result_equal=False 
* cardinality_100/0356: result_equal=False 
* cardinality_100/0357: result_equal=False 
* cardinality_100/0358: result_equal=False 
* cardinality_100/0359: result_equal=False 
