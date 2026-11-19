# Validation: `ns200` vs. `baseline` (counting passes, per scan)

| setup | queries | result equal | scans | invariant viol. | attribution mismatch | diff total/minmax/incl-opt-with-rows/rows-passed-incl-opt | diff scanned_with_rows | base no-rows | base incl-opt no-rows | pruned additional | of which from base no-rows | from base with-rows (optional filters) | % of base no-rows | % of base incl-opt no-rows | queries with additional pruning |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| point_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 1220992 | 1220992 | 789599 | 789599 | 0 | 64.67 | 64.67 | 1000 |
| range_hours_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 13 | 13 | 0 | 0 | 0 | 0.00 | 0.00 | 0 |
| range_minutes_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 1010459 | 1010459 | 0 | 0 | 0 | 0.00 | 0.00 | 0 |
| range_seconds_unsorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 1217129 | 1217129 | 0 | 0 | 0 | 0.00 | 0.00 | 0 |
| point_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 500296 | 500296 | 324446 | 324446 | 0 | 64.85 | 64.85 | 999 |
| range_hours_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 499304 | 499304 | 0 | 0 | 0 | 0.00 | 0.00 | 0 |
| range_minutes_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 499304 | 499304 | 0 | 0 | 0 | 0.00 | 0.00 | 0 |
| range_seconds_outliers | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 499317 | 499317 | 0 | 0 | 0 | 0.00 | 0.00 | 0 |
| point_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 992 | 992 | 603 | 603 | 0 | 60.79 | 60.79 | 603 |
| range_hours_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  | 0 |
| range_minutes_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  | 0 |
| range_seconds_sorted | 1000 | 1000 | 1000 | 0 | 0 | 0/0/0/0 | 0 | 13 | 13 | 0 | 0 | 0 | 0.00 | 0.00 | 0 |
| tpch | 22 | 22 | 86 | 0 | 0 | 0/0/0/0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  | 0 |
| tpcds | 99 | 99 | 764 | 0 | 0 | 0/0/0/0 | 2 | 578 | 740 | 461 | 405 | 56 | 70.07 | 62.30 | 7 |
| clickbench | 43 | 43 | 45 | 0 | 0 | 0/0/0/0 | 0 | 627 | 761 | 6 | 6 | 0 | 0.96 | 0.79 | 1 |

Queries whose scans had to be matched by (table, row groups, filters, rows passed) instead of scan id: point_unsorted 0, range_hours_unsorted 0, range_minutes_unsorted 0, range_seconds_unsorted 0, point_outliers 0, range_hours_outliers 0, range_minutes_outliers 0, range_seconds_outliers 0, point_sorted 0, range_hours_sorted 0, range_minutes_sorted 0, range_seconds_sorted 0, tpch 0, tpcds 1, clickbench 0

## Pruned row groups by filter category (first leaf whose statistic proves no match)

* point_unsorted: static equality 789599
* point_outliers: static equality 324446
* point_sorted: static equality 603
* tpcds: join equality 402, join IN 56, combination: join range 3
* clickbench: static equality 6

## Pruned row groups by column (first column whose complete filter is proven unsatisfiable)

* point_unsorted: sensor_records.timestamp_ms 789599
* point_outliers: sensor_records.timestamp_ms 324446
* point_sorted: sensor_records.timestamp_ms 603
* tpcds: store_sales.ss_customer_sk 348, catalog_sales.cs_item_sk 64, store_sales.ss_item_sk 46, store_sales.ss_sold_date_sk 3
* clickbench: hits.UserID 6

