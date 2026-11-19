# Validation: `occ200` vs. `baseline` (counting passes, per scan)

| setup | queries | result equal | scans | invariant viol. | attribution mismatch | diff total/minmax/incl-opt-with-rows/rows-passed-incl-opt | diff scanned_with_rows | base no-rows | base incl-opt no-rows | pruned additional | of which from base no-rows | from base with-rows (optional filters) | % of base no-rows | % of base incl-opt no-rows | queries with additional pruning |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| point_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 1220992 | 1220992 | 639311 | 639311 | 0 | 52.36 | 52.36 | 1000 |
| range_hours_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 13 | 13 | 7 | 7 | 0 | 53.85 | 53.85 | 7 |
| range_minutes_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 1010459 | 1010459 | 547537 | 547537 | 0 | 54.19 | 54.19 | 1000 |
| range_seconds_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 1217129 | 1217129 | 636947 | 636947 | 0 | 52.33 | 52.33 | 1000 |
| point_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 500296 | 500296 | 499406 | 499406 | 0 | 99.82 | 99.82 | 999 |
| range_hours_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 499304 | 499304 | 499304 | 499304 | 0 | 100.00 | 100.00 | 999 |
| range_minutes_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 499304 | 499304 | 499304 | 499304 | 0 | 100.00 | 100.00 | 999 |
| range_seconds_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 499317 | 499317 | 499306 | 499306 | 0 | 100.00 | 100.00 | 999 |
| point_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 992 | 992 | 557 | 557 | 0 | 56.15 | 56.15 | 557 |
| range_hours_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  | 0 |
| range_minutes_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  | 0 |
| range_seconds_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 13 | 13 | 9 | 9 | 0 | 69.23 | 69.23 | 9 |
| cardinality_100 | 419 | 272 | 419 | 0 | 0 | 0/0/0/0 | 0 | 247619 | 247619 | 247427 | 247427 | 0 | 99.92 | 99.92 | 413 |
| cardinality_100000 | 200 | 200 | 200 | 0 | 0 | 0/0/0/0 | 0 | 225710 | 225710 | 130117 | 130117 | 0 | 57.65 | 57.65 | 200 |
| tpch | 22 | 22 | 86 | 0 | 0 | 0/0/0/0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  | 0 |
| tpcds | 99 | 99 | 764 | 0 | 0 | 0/0/0/0 | 2 | 578 | 740 | 468 | 411 | 57 | 71.11 | 63.24 | 7 |
| clickbench | 43 | 43 | 45 | 0 | 0 | 0/0/0/0 | 0 | 627 | 761 | 6 | 6 | 0 | 0.96 | 0.79 | 1 |

Queries whose scans had to be matched by (table, row groups, filters, rows passed) instead of scan id: point_unsorted 0, range_hours_unsorted 0, range_minutes_unsorted 0, range_seconds_unsorted 0, point_outliers 0, range_hours_outliers 0, range_minutes_outliers 0, range_seconds_outliers 0, point_sorted 0, range_hours_sorted 0, range_minutes_sorted 0, range_seconds_sorted 0, cardinality_100 0, cardinality_100000 0, tpch 0, tpcds 1, clickbench 0

## Pruned row groups by filter category (first leaf whose statistic proves no match)

* point_unsorted: static equality 639311
* range_hours_unsorted: combination: static range 7
* range_minutes_unsorted: combination: static range 547537
* range_seconds_unsorted: combination: static range 636947
* point_outliers: static equality 499406
* range_hours_outliers: combination: static range 499304
* range_minutes_outliers: combination: static range 499304
* range_seconds_outliers: combination: static range 499306
* point_sorted: static equality 557
* range_seconds_sorted: combination: static range 9
* cardinality_100: static equality 247427
* cardinality_100000: static equality 130117
* tpcds: join equality 408, join IN 57, combination: join range 3
* clickbench: static equality 6

## Pruned row groups by column (first column whose complete filter is proven unsatisfiable)

* point_unsorted: sensor_records.timestamp_ms 639311
* range_hours_unsorted: sensor_records.timestamp_ms 7
* range_minutes_unsorted: sensor_records.timestamp_ms 547537
* range_seconds_unsorted: sensor_records.timestamp_ms 636947
* point_outliers: sensor_records.timestamp_ms 499406
* range_hours_outliers: sensor_records.timestamp_ms 499304
* range_minutes_outliers: sensor_records.timestamp_ms 499304
* range_seconds_outliers: sensor_records.timestamp_ms 499306
* point_sorted: sensor_records.timestamp_ms 557
* range_seconds_sorted: sensor_records.timestamp_ms 9
* cardinality_100: sensor_records.user_id 247427
* cardinality_100000: sensor_records.user_id 130117
* tpcds: store_sales.ss_customer_sk 348, catalog_sales.cs_item_sk 69, store_sales.ss_item_sk 48, store_sales.ss_sold_date_sk 3
* clickbench: hits.UserID 6

