# Ground-truth check (scale small)

| setup | scans | checked | skipped_early_stop | gt_error | layout_bad | with_rows_checked | with_rows_mismatch | with_rows_not_checkable | rows_mismatch | incl_optional_checked | incl_optional_mismatch | pruned_checked_exact | pruned_mismatch_exact | pruned_checked_approx_varchar | pruned_mismatch_approx_varchar | pruned_unsupported_filter | pruned_skipped_topn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| point_unsorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| point_outliers | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| point_sorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_seconds_unsorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_seconds_outliers | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_seconds_sorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_minutes_unsorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_minutes_outliers | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_minutes_sorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_hours_unsorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_hours_outliers | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| range_hours_sorted | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| cardinality_100 | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| cardinality_1000 | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| cardinality_10000 | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| cardinality_100000 | 100 | 100 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 | 100 | 0 | 0 | 0 | 0 | 0 |
| tpch | 86 | 86 | 0 | 0 | 0 | 86 | 0 | 0 | 0 | 9 | 0 | 61 | 0 | 18 | 0 | 7 | 0 |
| tpcds | 764 | 764 | 0 | 0 | 0 | 762 | 0 | 2 | 0 | 69 | 0 | 658 | 0 | 93 | 0 | 7 | 6 |
| clickbench | 44 | 44 | 0 | 0 | 0 | 39 | 0 | 5 | 0 | 3 | 0 | 26 | 0 | 11 | 0 | 3 | 4 |

Layout (pragma_storage_info): 49 tables, 0 with irregular row groups or count mismatch


Mismatches (exact checks): 0


VARCHAR pruning differences (expected: 8-byte string statistics): 0

