# Result check (scale small): counting on vs off, and vs pip duckdb

| setup | queries | on_off_compared | on_off_mismatch | pip_compared | pip_rowcount_mismatch | pip_hash_compared | pip_hash_mismatch | pip_error |
|---|---|---|---|---|---|---|---|---|
| point_unsorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| point_outliers | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| point_sorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_seconds_unsorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_seconds_outliers | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_seconds_sorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_minutes_unsorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_minutes_outliers | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_minutes_sorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_hours_unsorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_hours_outliers | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| range_hours_sorted | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| cardinality_100 | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| cardinality_1000 | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| cardinality_10000 | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| cardinality_100000 | 1000 | 1000 | 0 | 1000 | 0 | 1000 | 0 | 0 |
| tpch | 22 | 22 | 0 | 22 | 0 | 0 | 0 | 0 |
| tpcds | 99 | 99 | 0 | 99 | 0 | 0 | 0 | 0 |
| clickbench | 43 | 43 | 0 | 43 | 0 | 0 | 0 | 0 |

Mismatching queries: 0

