# Pruning opportunity, scale `small`

Partition = row group of 8,192 rows. *pruned*: skipped by the row-group min/max zonemap. *scanned, no rows* (3a): fully scanned, no row satisfied all pushed-down filters that are applied to rows (could have been pruned). *scanned, with rows* (3b): at least one such row. *partial/not reached*: query stopped early (LIMIT). *incl. optional, no rows*: like 3a but also requiring the optional (zonemap-only) filters, i.e. IN lists / OR clauses / join IN lists / top-N thresholds. See ../../README.md for the exact semantics.

Scans checked against the invariant: 16894, violations: 0

## Benchmark totals

| benchmark | queries | queries_ok | n_scans | total_row_groups | pruned | scanned | scanned_no_rows | scanned_no_rows_all_segments_skipped | scanned_with_rows | partial_no_rows | not_reached | incl_optional_no_rows | pct_pruned | pct_scanned_no_rows_of_scanned |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| micro | 16000 | 16000 | 16000 | 19536000 | 7788343 | 11747657 | 8497772 | 0 | 3249885 | 0 | 0 | 8497772 | 39.87 | 72.34 |
| tpch | 22 | 22 | 86 | 18699 | 4 | 18695 | 0 | 0 | 18695 | 0 | 0 | 0 | 0.02 | 0 |
| tpcds | 99 | 99 | 764 | 67240 | 16423 | 50817 | 578 | 0 | 50239 | 0 | 0 | 740 | 24.42 | 1.14 |
| clickbench | 43 | 43 | 44 | 5412 | 822 | 4590 | 627 | 0 | 3963 | 0 | 0 | 761 | 15.19 | 13.66 |

## Microbenchmarks (per setup; sums over all queries, avg = per query)

| setup | queries ok | avg total | avg pruned | avg scanned | avg scanned no rows (3a) | of which seg-skipped | avg scanned with rows (3b) | avg qualifying rows | % pruned | % of scanned w/o rows | avg ms (counting) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| point_unsorted | 1000 | 1221 | 0 | 1221 | 1220.99 | 0 | 0.01 | 0.01 | 0 | 100 | 40.96 |
| point_outliers | 1000 | 1221 | 720.7 | 500.3 | 500.3 | 0 | 0.01 | 0.01 | 59.03 | 100 | 16.25 |
| point_sorted | 1000 | 1221 | 1220 | 1 | 0.99 | 0 | 0.01 | 0.01 | 99.92 | 99.2 | 3.15 |
| range_seconds_unsorted | 1000 | 1221 | 0 | 1221 | 1217.13 | 0 | 3.87 | 3.88 | 0 | 99.68 | 31.52 |
| range_seconds_outliers | 1000 | 1221 | 720.7 | 500.3 | 499.32 | 0 | 0.99 | 3.88 | 59.03 | 99.8 | 13.07 |
| range_seconds_sorted | 1000 | 1221 | 1220 | 1 | 0.01 | 0 | 0.99 | 3.88 | 99.92 | 1.3 | 2.89 |
| range_minutes_unsorted | 1000 | 1221 | 0 | 1221 | 1010.46 | 0 | 210.54 | 230.94 | 0 | 82.76 | 35.51 |
| range_minutes_outliers | 1000 | 1221 | 720.67 | 500.33 | 499.3 | 0 | 1.02 | 230.94 | 59.02 | 99.8 | 13.3 |
| range_minutes_sorted | 1000 | 1221 | 1219.97 | 1.02 | 0 | 0 | 1.02 | 230.94 | 99.92 | 0 | 2.2 |
| range_hours_unsorted | 1000 | 1221 | 0 | 1221 | 0.01 | 0 | 1220.99 | 13894.41 | 0 | 0 | 61.19 |
| range_hours_outliers | 1000 | 1221 | 719 | 502 | 499.3 | 0 | 2.7 | 13894.41 | 58.89 | 99.46 | 17.64 |
| range_hours_sorted | 1000 | 1221 | 1218.3 | 2.7 | 0 | 0 | 2.7 | 13894.41 | 99.78 | 0 | 3.12 |
| cardinality_100 | 1000 | 1221 | 26.68 | 1194.32 | 583.73 | 0 | 610.59 | 100012.21 | 2.18 | 48.88 | 54.19 |
| cardinality_1000 | 1000 | 1221 | 1.42 | 1219.58 | 609.35 | 0 | 610.23 | 9998.78 | 0.12 | 49.96 | 52.87 |
| cardinality_10000 | 1000 | 1221 | 0.14 | 1220.86 | 728.8 | 0 | 492.06 | 1000.61 | 0.01 | 59.7 | 41.6 |
| cardinality_100000 | 1000 | 1221 | 0.77 | 1220.23 | 1128.06 | 0 | 92.17 | 99.87 | 0.06 | 92.45 | 37.58 |


Sums over the 1,000 queries of each setup:


| setup | total | pruned | scanned | scanned no rows (3a) | scanned with rows (3b) | partial, no rows | not reached | pruned by predicate |
|---|---|---|---|---|---|---|---|---|
| point_unsorted | 1221000 | 0 | 1221000 | 1220992 | 8 | 0 | 0 |  |
| point_outliers | 1221000 | 720696 | 500304 | 500296 | 8 | 0 | 0 | sensor_records.timestamp_ms cmp= [static]: 720696 |
| point_sorted | 1221000 | 1220000 | 1000 | 992 | 8 | 0 | 0 | sensor_records.timestamp_ms cmp= [static]: 1220000 |
| range_seconds_unsorted | 1221000 | 0 | 1221000 | 1217129 | 3871 | 0 | 0 |  |
| range_seconds_outliers | 1221000 | 720696 | 500304 | 499317 | 987 | 0 | 0 | sensor_records.timestamp_ms cmp<= [static]: 609890; sensor_records.timestamp_ms cmp>= [static]: 110806 |
| range_seconds_sorted | 1221000 | 1220000 | 1000 | 13 | 987 | 0 | 0 | sensor_records.timestamp_ms cmp>= [static]: 610051; sensor_records.timestamp_ms cmp<= [static]: 609949 |
| range_minutes_unsorted | 1221000 | 0 | 1221000 | 1010459 | 210541 | 0 | 0 |  |
| range_minutes_outliers | 1221000 | 720674 | 500326 | 499304 | 1022 | 0 | 0 | sensor_records.timestamp_ms cmp<= [static]: 609868; sensor_records.timestamp_ms cmp>= [static]: 110806 |
| range_minutes_sorted | 1221000 | 1219975 | 1025 | 0 | 1025 | 0 | 0 | sensor_records.timestamp_ms cmp>= [static]: 610051; sensor_records.timestamp_ms cmp<= [static]: 609924 |
| range_hours_unsorted | 1221000 | 0 | 1221000 | 13 | 1220987 | 0 | 0 |  |
| range_hours_outliers | 1221000 | 718996 | 502004 | 499304 | 2700 | 0 | 0 | sensor_records.timestamp_ms cmp<= [static]: 608190; sensor_records.timestamp_ms cmp>= [static]: 110806 |
| range_hours_sorted | 1221000 | 1218296 | 2704 | 0 | 2704 | 0 | 0 | sensor_records.timestamp_ms cmp>= [static]: 610051; sensor_records.timestamp_ms cmp<= [static]: 608245 |
| cardinality_100 | 1221000 | 26676 | 1194324 | 583734 | 610590 | 0 | 0 | sensor_records.user_id cmp= [static]: 26676 |
| cardinality_1000 | 1221000 | 1423 | 1219577 | 609351 | 610226 | 0 | 0 | sensor_records.user_id cmp= [static]: 1423 |
| cardinality_10000 | 1221000 | 140 | 1220860 | 728804 | 492056 | 0 | 0 | sensor_records.user_id cmp= [static]: 140 |
| cardinality_100000 | 1221000 | 771 | 1220229 | 1128064 | 92165 | 0 | 0 | sensor_records.user_id cmp= [static]: 771 |


## tpch (per query, summed over its table scans)


| query | status | scans | total | pruned | scanned | scanned no rows (3a) | of which seg-skipped | scanned with rows (3b) | partial, no rows | not reached | 3a incl. optional | EMPTY_RESULT ops | bound refs - plan scans | plan scans not executed | ms | pruned by predicate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q01 | ok | 1 | 733 | 0 | 733 | 0 | 0 | 733 | 0 | 0 | 0 | 0 | 0 | 0 | 2844.65 |  |
| q02 | ok | 9 | 229 | 0 | 229 | 0 | 0 | 229 | 0 | 0 | 0 | 0 | 0 | 0 | 390.43 |  |
| q03 | ok | 3 | 936 | 0 | 936 | 0 | 0 | 936 | 0 | 0 | 0 | 0 | 0 | 0 | 758.81 |  |
| q04 | ok | 2 | 917 | 0 | 917 | 0 | 0 | 917 | 0 | 0 | 0 | 0 | 0 | 0 | 221.26 |  |
| q05 | ok | 6 | 940 | 0 | 940 | 0 | 0 | 940 | 0 | 0 | 0 | 0 | 0 | 0 | 223.4 |  |
| q06 | ok | 1 | 733 | 0 | 733 | 0 | 0 | 733 | 0 | 0 | 0 | 0 | 0 | 0 | 64.03 |  |
| q07 | ok | 6 | 940 | 0 | 940 | 0 | 0 | 940 | 0 | 0 | 0 | 0 | 0 | 0 | 210.66 |  |
| q08 | ok | 8 | 966 | 0 | 966 | 0 | 0 | 966 | 0 | 0 | 0 | 0 | 0 | 0 | 215.65 |  |
| q09 | ok | 6 | 1043 | 0 | 1043 | 0 | 0 | 1043 | 0 | 0 | 0 | 0 | 0 | 0 | 696.49 |  |
| q10 | ok | 4 | 937 | 0 | 937 | 0 | 0 | 937 | 0 | 0 | 0 | 0 | 0 | 0 | 325.29 |  |
| q11 | ok | 6 | 202 | 0 | 202 | 0 | 0 | 202 | 0 | 0 | 0 | 0 | 0 | 0 | 40.73 |  |
| q12 | ok | 2 | 917 | 0 | 917 | 0 | 0 | 917 | 0 | 0 | 0 | 0 | 0 | 0 | 194.4 |  |
| q13 | ok | 2 | 203 | 0 | 203 | 0 | 0 | 203 | 0 | 0 | 0 | 0 | 0 | 0 | 536.91 |  |
| q14 | ok | 2 | 758 | 0 | 758 | 0 | 0 | 758 | 0 | 0 | 0 | 0 | 0 | 0 | 97.22 |  |
| q15 | ok | 2 | 735 | 1 | 734 | 0 | 0 | 734 | 0 | 0 | 0 | 0 | 0 | 0 | 92.99 | supplier.s_suppkey cmp= [static]: 1 |
| q16 | ok | 3 | 125 | 0 | 125 | 0 | 0 | 125 | 0 | 0 | 0 | 0 | 0 | 0 | 103.73 |  |
| q17 | ok | 3 | 1491 | 0 | 1491 | 0 | 0 | 1491 | 0 | 0 | 0 | 0 | 0 | 0 | 171.59 |  |
| q18 | ok | 4 | 1669 | 3 | 1666 | 0 | 0 | 1666 | 0 | 0 | 0 | 0 | 0 | 0 | 899.98 | lineitem.l_orderkey cmp<= [static]: 2; orders.o_orderkey cmp<= [static]: 1 |
| q19 | ok | 2 | 758 | 0 | 758 | 0 | 0 | 758 | 0 | 0 | 0 | 0 | 0 | 0 | 414.45 |  |
| q20 | ok | 5 | 859 | 0 | 859 | 0 | 0 | 859 | 0 | 0 | 0 | 0 | 0 | 0 | 165.86 |  |
| q21 | ok | 6 | 2386 | 0 | 2386 | 0 | 0 | 2386 | 0 | 0 | 0 | 0 | 0 | 0 | 565.46 |  |
| q22 | ok | 3 | 222 | 0 | 222 | 0 | 0 | 222 | 0 | 0 | 0 | 0 | 0 | 0 | 51.76 |  |


## tpcds (per query, summed over its table scans)


| query | status | scans | total | pruned | scanned | scanned no rows (3a) | of which seg-skipped | scanned with rows (3b) | partial, no rows | not reached | 3a incl. optional | EMPTY_RESULT ops | bound refs - plan scans | plan scans not executed | ms | pruned by predicate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q01 | ok | 4 | 59 | 8 | 51 | 0 | 0 | 51 | 0 | 0 | 0 | 0 | 0 | 0 | 109.51 | date_dim.d_year cmp= [static]: 8 |
| q02 | ok | 5 | 291 | 24 | 267 | 0 | 0 | 267 | 0 | 0 | 0 | 0 | 0 | 0 | 886.32 | date_dim.d_year cmp= [static]: 16; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q03 | ok | 3 | 364 | 8 | 356 | 0 | 0 | 356 | 0 | 0 | 0 | 0 | 0 | 0 | 1710.97 | date_dim.d_date_sk cmp>= [join]: 4; date_dim.d_date_sk cmp<= [join]: 4 |
| q04 | ok | 18 | 1364 | 328 | 1036 | 0 | 0 | 1036 | 0 | 0 | 0 | 0 | -9 | 0 | 2208.38 | catalog_sales.cs_sold_date_sk cmp>= [static]: 245; date_dim.d_year cmp= [static]: 48; catalog_sales.cs_sold_date_sk cmp<= [static]: 35 |
| q05 | ok | 13 | 798 | 212 | 586 | 0 | 0 | 586 | 0 | 0 | 0 | 0 | 0 | 0 | 391.98 | catalog_sales.cs_sold_date_sk cmp<= [static]: 89; catalog_sales.cs_sold_date_sk cmp>= [static]: 84; date_dim.d_date cmp>= [static]: 12; date_dim.d_date cmp<= [static]: 12; catalog_returns.cr_returned_date_sk cmp<= [static]: 9; catalog_returns.cr_returned_date_sk cmp>= [static]: 6 |
| q06 | ok | 7 | 396 | 16 | 380 | 0 | 0 | 380 | 0 | 0 | 0 | 0 | 0 | 0 | 110.42 | date_dim.d_year cmp= [static]: 8; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q07 | ok | 5 | 600 | 8 | 592 | 0 | 0 | 592 | 0 | 0 | 0 | 0 | 0 | 0 | 308.71 | date_dim.d_year cmp= [static]: 8 |
| q08 | ok | 6 | 389 | 8 | 381 | 0 | 0 | 381 | 0 | 0 | 0 | 0 | 0 | 0 | 377.48 | date_dim.d_year cmp= [static]: 8 |
| q09 | ok | 16 | 5281 | 0 | 5281 | 0 | 0 | 5281 | 0 | 0 | 0 | 0 | 0 | 0 | 544.79 |  |
| q10 | ok | 9 | 898 | 192 | 706 | 0 | 0 | 706 | 0 | 0 | 0 | 0 | 0 | 0 | 213.76 | catalog_sales.cs_sold_date_sk cmp>= [static]: 140; catalog_sales.cs_sold_date_sk cmp<= [static]: 28; date_dim.d_year cmp= [static]: 24 |
| q11 | ok | 12 | 968 | 32 | 936 | 0 | 0 | 936 | 0 | 0 | 0 | 0 | -6 | 0 | 1527.88 | date_dim.d_year cmp= [static]: 32 |
| q12 | ok | 3 | 100 | 8 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 31.34 | date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q13 | ok | 6 | 605 | 8 | 597 | 0 | 0 | 597 | 0 | 0 | 0 | 0 | 0 | 0 | 285.98 | date_dim.d_year cmp= [static]: 8 |
| q14 | ok | 25 | 1950 | 381 | 1569 | 0 | 0 | 1569 | 0 | 0 | 0 | 0 | 0 | 0 | 1040.93 | catalog_sales.cs_sold_date_sk cmp>= [static]: 198; catalog_sales.cs_sold_date_sk cmp<= [static]: 111; date_dim.d_year cmp>= [static]: 24; date_dim.d_year cmp<= [static]: 24; date_dim.d_year cmp= [static]: 24 |
| q15 | ok | 4 | 205 | 178 | 27 | 0 | 0 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | 30.31 | catalog_sales.cs_sold_date_sk cmp>= [static]: 110; catalog_sales.cs_sold_date_sk cmp<= [static]: 60; date_dim.d_year cmp= [static]: 8 |
| q16 | ok | 6 | 387 | 182 | 205 | 0 | 0 | 205 | 0 | 0 | 0 | 0 | 0 | 0 | 79.11 | catalog_sales.cs_order_number cmp>= [static]: 129; catalog_sales.cs_order_number cmp<= [static]: 30; catalog_returns.cr_order_number cmp>= [static]: 12; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4; catalog_returns.cr_order_number cmp<= [static]: 3 |
| q17 | ok | 8 | 595 | 180 | 415 | 0 | 0 | 415 | 0 | 0 | 0 | 0 | 0 | 0 | 109.01 | catalog_sales.cs_sold_date_sk cmp>= [join]: 105; catalog_sales.cs_sold_date_sk cmp<= [join]: 51; date_dim.d_quarter_name optional(in) [static]: 16; date_dim.d_quarter_name cmp= [static]: 8 |
| q18 | ok | 7 | 678 | 148 | 530 | 0 | 0 | 530 | 0 | 0 | 0 | 0 | 0 | 0 | 134.19 | catalog_sales.cs_sold_date_sk cmp<= [static]: 140; date_dim.d_year cmp= [static]: 8 |
| q19 | ok | 6 | 385 | 8 | 377 | 0 | 0 | 377 | 0 | 0 | 0 | 0 | 0 | 0 | 82 | date_dim.d_year cmp= [static]: 8 |
| q20 | ok | 3 | 188 | 181 | 7 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 21.12 | catalog_sales.cs_sold_date_sk cmp<= [static]: 136; catalog_sales.cs_sold_date_sk cmp>= [static]: 37; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q21 | ok | 4 | 1447 | 1392 | 55 | 0 | 0 | 55 | 0 | 0 | 0 | 0 | 0 | 0 | 57.48 | inventory.inv_date_sk cmp<= [static]: 780; inventory.inv_date_sk cmp>= [static]: 604; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q22 | ok | 3 | 1446 | 1155 | 291 | 0 | 0 | 291 | 0 | 0 | 0 | 0 | 0 | 0 | 1320.89 | inventory.inv_date_sk cmp>= [static]: 576; inventory.inv_date_sk cmp<= [static]: 571; date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |
| q23 | ok | 14 | 1411 | 207 | 1204 | 0 | 0 | 1204 | 0 | 0 | 0 | 0 | 0 | 0 | 1221.93 | catalog_sales.cs_sold_date_sk cmp<= [static]: 102; catalog_sales.cs_sold_date_sk cmp>= [static]: 71; date_dim.d_year cmp= [static]: 16; date_dim.d_year cmp>= [static]: 8; date_dim.d_year cmp<= [static]: 8; customer.c_customer_sk cmp<= [join]: 1; customer.c_customer_sk cmp<= [static]: 1 |
| q24 | ok | 6 | 412 | 1 | 411 | 0 | 0 | 411 | 0 | 0 | 0 | 0 | 0 | 0 | 133.77 | store_returns.sr_ticket_number cmp<= [static]: 1 |
| q25 | ok | 8 | 595 | 532 | 63 | 1 | 0 | 62 | 0 | 0 | 2 | 0 | 0 | 0 | 37.57 | store_sales.ss_ticket_number optional(in) [join]: 349; catalog_sales.cs_sold_date_sk cmp>= [join]: 110; catalog_sales.cs_sold_date_sk cmp<= [join]: 47; date_dim.d_year cmp= [static]: 24; item.i_item_sk cmp= [join]: 2 |
| q26 | ok | 5 | 424 | 148 | 276 | 0 | 0 | 276 | 0 | 0 | 0 | 0 | 0 | 0 | 77.6 | catalog_sales.cs_sold_date_sk cmp>= [static]: 70; catalog_sales.cs_sold_date_sk cmp<= [static]: 70; date_dim.d_year cmp= [static]: 8 |
| q27 | ok | 15 | 1800 | 24 | 1776 | 0 | 0 | 1776 | 0 | 0 | 0 | 0 | -10 | 0 | 583.47 | date_dim.d_year cmp= [static]: 24 |
| q28 | ok | 6 | 2112 | 0 | 2112 | 0 | 0 | 2112 | 0 | 0 | 0 | 0 | 0 | 0 | 500.04 |  |
| q29 | ok | 8 | 595 | 24 | 571 | 0 | 0 | 571 | 0 | 0 | 0 | 0 | 0 | 0 | 150.87 | date_dim.d_year cmp= [static]: 16; date_dim.d_date_sk optional(in) [join]: 8 |
| q30 | ok | 5 | 45 | 8 | 37 | 0 | 0 | 37 | 0 | 0 | 0 | 0 | 0 | 0 | 73.68 | date_dim.d_year cmp= [static]: 8 |
| q31 | ok | 6 | 472 | 16 | 456 | 0 | 0 | 456 | 0 | 0 | 0 | 0 | 0 | 0 | 144.35 | date_dim.d_date_sk cmp>= [static]: 8; date_dim.d_date_sk cmp<= [static]: 8 |
| q32 | ok | 5 | 373 | 186 | 187 | 1 | 0 | 186 | 0 | 0 | 23 | 0 | 0 | 0 | 33.19 | catalog_sales.cs_sold_date_sk cmp<= [static]: 99; catalog_sales.cs_sold_date_sk cmp>= [static]: 71; date_dim.d_date cmp>= [static]: 8; date_dim.d_date cmp<= [static]: 8 |
| q33 | ok | 15 | 682 | 197 | 485 | 1 | 0 | 484 | 0 | 0 | 1 | 0 | 0 | 0 | 93.9 | catalog_sales.cs_sold_date_sk cmp<= [static]: 167; date_dim.d_year cmp= [static]: 24; catalog_sales.cs_sold_date_sk cmp>= [static]: 6 |
| q34 | ok | 5 | 376 | 8 | 368 | 0 | 0 | 368 | 0 | 0 | 0 | 0 | 0 | 0 | 107.67 | date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4 |
| q35 | ok | 9 | 898 | 179 | 719 | 0 | 0 | 719 | 0 | 0 | 0 | 0 | 0 | 0 | 271.35 | catalog_sales.cs_sold_date_sk cmp>= [static]: 140; date_dim.d_year cmp= [static]: 24; catalog_sales.cs_sold_date_sk cmp<= [static]: 15 |
| q36 | ok | 4 | 365 | 8 | 357 | 0 | 0 | 357 | 0 | 0 | 0 | 0 | 0 | 0 | 200.47 | date_dim.d_year cmp= [static]: 8 |
| q37 | ok | 4 | 1622 | 1391 | 231 | 70 | 0 | 161 | 0 | 0 | 106 | 0 | 0 | 0 | 30.74 | inventory.inv_date_sk cmp<= [join]: 785; inventory.inv_date_sk cmp>= [join]: 598; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q38 | ok | 9 | 682 | 164 | 518 | 0 | 0 | 518 | 0 | 0 | 0 | 0 | 0 | 0 | 274.31 | catalog_sales.cs_sold_date_sk cmp>= [static]: 70; catalog_sales.cs_sold_date_sk cmp<= [static]: 70; date_dim.d_month_seq cmp>= [static]: 12; date_dim.d_month_seq cmp<= [static]: 12 |
| q39 | ok | 4 | 1447 | 1397 | 50 | 0 | 0 | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 77.61 | inventory.inv_date_sk cmp>= [static]: 862; inventory.inv_date_sk cmp<= [static]: 527; date_dim.d_year cmp= [static]: 8 |
| q40 | ok | 5 | 207 | 180 | 27 | 0 | 0 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | 32.57 | catalog_sales.cs_sold_date_sk cmp<= [static]: 100; catalog_sales.cs_sold_date_sk cmp>= [static]: 72; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q41 | ok | 2 | 6 | 0 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 13.95 |  |
| q42 | ok | 3 | 364 | 8 | 356 | 0 | 0 | 356 | 0 | 0 | 0 | 0 | 0 | 0 | 39.39 | date_dim.d_year cmp= [static]: 8 |
| q43 | ok | 3 | 362 | 8 | 354 | 0 | 0 | 354 | 0 | 0 | 0 | 0 | 0 | 0 | 159.7 | date_dim.d_year cmp= [static]: 8 |
| q44 | ok | 6 | 1414 | 0 | 1414 | 0 | 0 | 1414 | 0 | 0 | 0 | 0 | 0 | 0 | 212.25 |  |
| q45 | ok | 6 | 123 | 10 | 113 | 0 | 0 | 113 | 0 | 0 | 0 | 0 | 0 | 0 | 37.67 | date_dim.d_year cmp= [static]: 8; item.i_item_sk optional(in) [static]: 2 |
| q46 | ok | 7 | 390 | 8 | 382 | 0 | 0 | 382 | 0 | 0 | 0 | 0 | 0 | 0 | 188.07 | date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4 |
| q47 | ok | 4 | 365 | 8 | 357 | 0 | 0 | 357 | 0 | 0 | 0 | 0 | 0 | 0 | 561.22 | date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q48 | ok | 5 | 604 | 8 | 596 | 0 | 0 | 596 | 0 | 0 | 0 | 0 | 0 | 0 | 230.18 | date_dim.d_year cmp= [static]: 8 |
| q49 | ok | 9 | 706 | 209 | 497 | 0 | 0 | 497 | 0 | 0 | 0 | 0 | 0 | 0 | 118.14 | catalog_sales.cs_sold_date_sk cmp>= [join]: 134; catalog_sales.cs_sold_date_sk cmp<= [join]: 35; date_dim.d_year cmp= [static]: 24; catalog_returns.cr_order_number cmp>= [join]: 13; catalog_returns.cr_order_number cmp<= [join]: 3 |
| q50 | ok | 5 | 407 | 16 | 391 | 0 | 0 | 391 | 0 | 0 | 0 | 0 | 0 | 0 | 125.76 | date_dim.d_year cmp= [static]: 8; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q51 | ok | 4 | 458 | 16 | 442 | 0 | 0 | 442 | 0 | 0 | 0 | 0 | 0 | 0 | 1135.93 | date_dim.d_month_seq cmp>= [static]: 8; date_dim.d_month_seq cmp<= [static]: 8 |
| q52 | ok | 3 | 364 | 8 | 356 | 0 | 0 | 356 | 0 | 0 | 0 | 0 | 0 | 0 | 57.45 | date_dim.d_year cmp= [static]: 8 |
| q53 | ok | 4 | 365 | 8 | 357 | 0 | 0 | 357 | 0 | 0 | 0 | 0 | 0 | 0 | 82.67 | date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |
| q54 | ok | 11 | 676 | 201 | 475 | 350 | 0 | 125 | 0 | 0 | 350 | 0 | 0 | 0 | 59.49 | catalog_sales.cs_sold_date_sk cmp<= [static]: 140; catalog_sales.cs_sold_date_sk cmp>= [static]: 29; date_dim.d_year cmp= [static]: 24; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q55 | ok | 3 | 364 | 8 | 356 | 0 | 0 | 356 | 0 | 0 | 0 | 0 | 0 | 0 | 56.55 | date_dim.d_year cmp= [static]: 8 |
| q56 | ok | 15 | 682 | 198 | 484 | 1 | 0 | 483 | 0 | 0 | 1 | 0 | 0 | 0 | 90.29 | catalog_sales.cs_sold_date_sk cmp>= [static]: 107; catalog_sales.cs_sold_date_sk cmp<= [static]: 67; date_dim.d_year cmp= [static]: 24 |
| q57 | ok | 4 | 189 | 141 | 48 | 0 | 0 | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 189.1 | catalog_sales.cs_sold_date_sk cmp<= [static]: 104; catalog_sales.cs_sold_date_sk cmp>= [static]: 29; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q58 | ok | 15 | 706 | 246 | 460 | 1 | 0 | 459 | 0 | 0 | 1 | 0 | 0 | 0 | 79.02 | catalog_sales.cs_sold_date_sk cmp<= [static]: 105; catalog_sales.cs_sold_date_sk cmp>= [static]: 69; date_dim.d_date cmp= [static]: 24; date_dim.d_week_seq cmp= [static]: 24; date_dim.d_date optional(in) [join]: 24 |
| q59 | ok | 6 | 381 | 24 | 357 | 0 | 0 | 357 | 0 | 0 | 0 | 0 | 0 | 0 | 359.83 | date_dim.d_week_seq cmp>= [join]: 8; date_dim.d_week_seq cmp<= [join]: 8; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q60 | ok | 15 | 682 | 195 | 487 | 0 | 0 | 487 | 0 | 0 | 0 | 0 | 0 | 0 | 83.51 | catalog_sales.cs_sold_date_sk cmp<= [static]: 156; date_dim.d_year cmp= [static]: 24; catalog_sales.cs_sold_date_sk cmp>= [static]: 15 |
| q61 | ok | 13 | 771 | 16 | 755 | 0 | 0 | 755 | 0 | 0 | 0 | 0 | 0 | 0 | 142.13 | date_dim.d_year cmp= [static]: 16 |
| q62 | ok | 5 | 100 | 8 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 50.09 | date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |
| q63 | ok | 4 | 365 | 8 | 357 | 0 | 0 | 357 | 0 | 0 | 0 | 0 | 0 | 0 | 73.15 | date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |
| q64 | ok | 19 | 1115 | 214 | 901 | 0 | 0 | 901 | 0 | 0 | 0 | 0 | 0 | 0 | 439.34 | customer_demographics.cd_demo_sk optional(in) [join]: 189; date_dim.d_year optional(or) [static]: 8; date_dim.d_date_sk cmp>= [static]: 8; date_dim.d_date_sk cmp<= [static]: 8; customer_address.ca_address_sk cmp<= [static]: 1 |
| q65 | ok | 6 | 726 | 16 | 710 | 0 | 0 | 710 | 0 | 0 | 0 | 0 | 0 | 0 | 222.37 | date_dim.d_month_seq cmp>= [static]: 8; date_dim.d_month_seq cmp<= [static]: 8 |
| q66 | ok | 10 | 308 | 168 | 140 | 0 | 0 | 140 | 0 | 0 | 0 | 0 | 0 | 0 | 94.68 | catalog_sales.cs_sold_date_sk cmp>= [static]: 105; catalog_sales.cs_sold_date_sk cmp<= [static]: 35; date_dim.d_year cmp= [static]: 16; time_dim.t_time cmp>= [static]: 6; time_dim.t_time cmp<= [static]: 6 |
| q67 | ok | 4 | 365 | 8 | 357 | 0 | 0 | 357 | 0 | 0 | 0 | 0 | 0 | 0 | 2162.42 | date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |
| q68 | ok | 7 | 390 | 8 | 382 | 0 | 0 | 382 | 0 | 0 | 0 | 0 | 0 | 0 | 188.09 | date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4 |
| q69 | ok | 9 | 898 | 194 | 704 | 0 | 0 | 704 | 0 | 0 | 0 | 0 | 0 | 0 | 173.41 | catalog_sales.cs_sold_date_sk cmp>= [static]: 110; catalog_sales.cs_sold_date_sk cmp<= [static]: 60; date_dim.d_year cmp= [static]: 24 |
| q70 | ok | 6 | 724 | 16 | 708 | 0 | 0 | 708 | 0 | 0 | 0 | 0 | 0 | 0 | 227.76 | date_dim.d_month_seq cmp>= [static]: 8; date_dim.d_month_seq cmp<= [static]: 8 |
| q71 | ok | 8 | 657 | 199 | 458 | 0 | 0 | 458 | 0 | 0 | 0 | 0 | 0 | 0 | 89.25 | catalog_sales.cs_sold_date_sk cmp<= [static]: 111; catalog_sales.cs_sold_date_sk cmp>= [static]: 58; date_dim.d_year cmp= [static]: 24; time_dim.t_meal_time optional(or) [static]: 6 |
| q72 | ok | 11 | 1896 | 1306 | 590 | 0 | 0 | 590 | 0 | 0 | 0 | 0 | 0 | 0 | 131.06 | inventory.inv_date_sk cmp<= [join]: 857; inventory.inv_date_sk cmp>= [join]: 285; catalog_sales.cs_sold_date_sk cmp<= [static]: 105; catalog_sales.cs_sold_date_sk cmp>= [static]: 35; date_dim.d_year cmp= [static]: 8; date_dim.d_date_sk cmp>= [static]: 8; date_dim.d_date_sk cmp<= [static]: 8 |
| q73 | ok | 5 | 376 | 20 | 356 | 0 | 0 | 356 | 0 | 0 | 0 | 0 | 0 | 0 | 74.02 | customer.c_customer_sk cmp= [static]: 12; date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4 |
| q74 | ok | 12 | 968 | 32 | 936 | 0 | 0 | 936 | 0 | 0 | 0 | 0 | -6 | 0 | 533.61 | date_dim.d_year cmp= [static]: 32 |
| q75 | ok | 12 | 715 | 139 | 576 | 0 | 0 | 576 | 0 | 0 | 0 | 0 | 0 | 0 | 272.26 | catalog_sales.cs_sold_date_sk cmp>= [static]: 105; date_dim.d_year optional(or) [static]: 24; catalog_returns.cr_order_number cmp>= [static]: 10 |
| q76 | ok | 9 | 652 | 24 | 628 | 39 | 0 | 589 | 0 | 0 | 39 | 0 | 0 | 0 | 107.27 | date_dim.d_date_sk cmp>= [static]: 12; date_dim.d_date_sk cmp<= [static]: 12 |
| q77 | ok | 16 | 737 | 234 | 503 | 0 | 0 | 503 | 0 | 0 | 0 | 0 | 0 | 0 | 98.79 | catalog_sales.cs_sold_date_sk cmp<= [static]: 87; catalog_sales.cs_sold_date_sk cmp>= [static]: 84; date_dim.d_date cmp>= [static]: 24; date_dim.d_date cmp<= [static]: 24; catalog_returns.cr_returned_date_sk cmp<= [static]: 9; catalog_returns.cr_returned_date_sk cmp>= [static]: 6 |
| q78 | ok | 9 | 706 | 164 | 542 | 0 | 0 | 542 | 0 | 0 | 0 | 0 | 0 | 0 | 765.1 | catalog_sales.cs_sold_date_sk cmp>= [static]: 70; catalog_sales.cs_sold_date_sk cmp<= [static]: 70; date_dim.d_year cmp= [static]: 24 |
| q79 | ok | 5 | 376 | 8 | 368 | 0 | 0 | 368 | 0 | 0 | 0 | 0 | 0 | 0 | 247.43 | date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4 |
| q80 | ok | 18 | 722 | 196 | 526 | 0 | 0 | 526 | 0 | 0 | 0 | 0 | 0 | 0 | 189.12 | catalog_sales.cs_sold_date_sk cmp<= [static]: 87; catalog_sales.cs_sold_date_sk cmp>= [static]: 84; date_dim.d_date cmp>= [static]: 12; date_dim.d_date cmp<= [static]: 12; catalog_page.cp_catalog_page_sk cmp<= [join]: 1 |
| q81 | ok | 5 | 54 | 19 | 35 | 0 | 0 | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 71.18 | date_dim.d_year cmp= [static]: 8; catalog_returns.cr_returned_date_sk cmp<= [static]: 7; catalog_returns.cr_returned_date_sk cmp>= [static]: 4 |
| q82 | ok | 4 | 1798 | 1391 | 407 | 2 | 0 | 405 | 0 | 0 | 105 | 0 | 0 | 0 | 52.62 | inventory.inv_date_sk cmp<= [join]: 697; inventory.inv_date_sk cmp>= [join]: 686; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q83 | ok | 15 | 153 | 85 | 68 | 0 | 0 | 68 | 0 | 0 | 0 | 0 | 0 | 0 | 34.95 | date_dim.d_date optional(in) [static]: 24; date_dim.d_week_seq optional(in) [static]: 24; date_dim.d_date optional(in) [join]: 24; catalog_returns.cr_returned_date_sk optional(in) [static]: 13 |
| q84 | ok | 6 | 293 | 220 | 73 | 0 | 0 | 73 | 0 | 0 | 0 | 0 | 0 | 0 | 30.18 | customer_demographics.cd_demo_sk optional(in) [join]: 220 |
| q85 | ok | 8 | 585 | 243 | 342 | 0 | 0 | 342 | 0 | 0 | 0 | 0 | 0 | 0 | 72.82 | customer_demographics.cd_demo_sk cmp= [join]: 234; date_dim.d_year cmp= [static]: 8; customer_demographics.cd_demo_sk cmp<= [join]: 1 |
| q86 | ok | 3 | 100 | 8 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 36.27 | date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |
| q87 | ok | 9 | 682 | 164 | 518 | 0 | 0 | 518 | 0 | 0 | 0 | 0 | 0 | 0 | 239.3 | catalog_sales.cs_sold_date_sk cmp>= [static]: 70; catalog_sales.cs_sold_date_sk cmp<= [static]: 70; date_dim.d_month_seq cmp>= [static]: 12; date_dim.d_month_seq cmp<= [static]: 12 |
| q88 | ok | 32 | 2920 | 76 | 2844 | 59 | 0 | 2785 | 0 | 0 | 59 | 0 | 0 | 0 | 361.52 | time_dim.t_hour cmp= [static]: 76 |
| q89 | ok | 4 | 365 | 8 | 357 | 0 | 0 | 357 | 0 | 0 | 0 | 0 | 0 | 0 | 108.08 | date_dim.d_year cmp= [static]: 8 |
| q90 | ok | 8 | 202 | 18 | 184 | 0 | 0 | 184 | 0 | 0 | 0 | 0 | 0 | 0 | 27.7 | time_dim.t_hour cmp>= [static]: 11; time_dim.t_hour cmp<= [static]: 7 |
| q91 | ok | 7 | 284 | 228 | 56 | 0 | 0 | 56 | 0 | 0 | 0 | 0 | 0 | 0 | 34.07 | customer_demographics.cd_demo_sk optional(in) [join]: 205; catalog_returns.cr_returned_date_sk cmp<= [static]: 15; date_dim.d_year cmp= [static]: 8 |
| q92 | ok | 5 | 197 | 16 | 181 | 0 | 0 | 181 | 0 | 0 | 0 | 0 | 0 | 0 | 92.08 | date_dim.d_date cmp>= [static]: 8; date_dim.d_date cmp<= [static]: 8 |
| q93 | ok | 3 | 389 | 0 | 389 | 0 | 0 | 389 | 0 | 0 | 0 | 0 | 0 | 0 | 216.08 |  |
| q94 | ok | 6 | 202 | 8 | 194 | 0 | 0 | 194 | 0 | 0 | 0 | 0 | 0 | 0 | 52.31 | date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q95 | ok | 9 | 466 | 8 | 458 | 0 | 0 | 458 | 0 | 0 | 0 | 0 | -2 | 0 | 770.82 | date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q96 | ok | 4 | 365 | 9 | 356 | 53 | 0 | 303 | 0 | 0 | 53 | 0 | 0 | 0 | 35.54 | time_dim.t_hour cmp= [static]: 9 |
| q97 | ok | 4 | 546 | 156 | 390 | 0 | 0 | 390 | 0 | 0 | 0 | 0 | 0 | 0 | 205.47 | catalog_sales.cs_sold_date_sk cmp>= [static]: 70; catalog_sales.cs_sold_date_sk cmp<= [static]: 70; date_dim.d_month_seq cmp>= [static]: 8; date_dim.d_month_seq cmp<= [static]: 8 |
| q98 | ok | 3 | 364 | 8 | 356 | 0 | 0 | 356 | 0 | 0 | 0 | 0 | 0 | 0 | 54.02 | date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q99 | ok | 5 | 188 | 133 | 55 | 0 | 0 | 55 | 0 | 0 | 0 | 0 | 0 | 0 | 70.27 | catalog_sales.cs_ship_date_sk cmp<= [static]: 71; catalog_sales.cs_ship_date_sk cmp>= [static]: 54; date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |


## clickbench (per query, summed over its table scans)


| query | status | scans | total | pruned | scanned | scanned no rows (3a) | of which seg-skipped | scanned with rows (3b) | partial, no rows | not reached | 3a incl. optional | EMPTY_RESULT ops | bound refs - plan scans | plan scans not executed | ms | pruned by predicate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q01 | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 4.47 |  |
| q02 | ok | 1 | 123 | 3 | 120 | 0 | 0 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 62.78 | hits.AdvEngineID cmp!= [static]: 3 |
| q03 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 24.88 |  |
| q04 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 30.16 |  |
| q05 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 57.79 |  |
| q06 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 41.9 |  |
| q07 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 2.95 |  |
| q08 | ok | 1 | 123 | 3 | 120 | 0 | 0 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 4.04 | hits.AdvEngineID cmp!= [static]: 3 |
| q09 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 36.33 |  |
| q10 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 80.14 |  |
| q11 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 27.38 |  |
| q12 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 33.3 |  |
| q13 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 30.99 |  |
| q14 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 34.89 |  |
| q15 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 33.91 |  |
| q16 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 20.55 |  |
| q17 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 71.21 |  |
| q18 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 58.88 |  |
| q19 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 369.17 |  |
| q20 | ok | 1 | 123 | 117 | 6 | 6 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0.73 | hits.UserID cmp= [static]: 117 |
| q21 | ok | 1 | 123 | 0 | 123 | 95 | 0 | 28 | 0 | 0 | 95 | 0 | 0 | 0 | 314.92 |  |
| q22 | ok | 1 | 123 | 0 | 123 | 122 | 0 | 1 | 0 | 0 | 122 | 0 | 0 | 0 | 80.32 |  |
| q23 | ok | 1 | 123 | 0 | 123 | 76 | 0 | 47 | 0 | 0 | 76 | 0 | 0 | 0 | 252.05 |  |
| q24 | ok | 2 | 246 | 0 | 246 | 211 | 0 | 35 | 0 | 0 | 222 | 0 | -1 | 0 | 212.6 |  |
| q25 | ok | 2 | 246 | 59 | 187 | 117 | 0 | 70 | 0 | 0 | 170 | 0 | -1 | 0 | 13.12 | hits.EventTime optional(dynamic_topn) [topn]: 59 |
| q26 | ok | 1 | 123 | 89 | 34 | 0 | 0 | 34 | 0 | 0 | 12 | 0 | 0 | 0 | 6.14 | hits.SearchPhrase optional(dynamic_topn) [topn]: 89 |
| q27 | ok | 1 | 123 | 54 | 69 | 0 | 0 | 69 | 0 | 0 | 58 | 0 | 0 | 0 | 10.5 | hits.EventTime optional(dynamic_topn) [topn]: 54 |
| q28 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 56.34 |  |
| q29 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 1853.02 |  |
| q30 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 20.05 |  |
| q31 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 31.56 |  |
| q32 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 59.49 |  |
| q33 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 257.2 |  |
| q34 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 312.28 |  |
| q35 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 189.62 |  |
| q36 | ok | 1 | 123 | 0 | 123 | 0 | 0 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 31.39 |  |
| q37 | ok | 1 | 123 | 71 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 124.66 | hits.CounterID cmp= [static]: 71 |
| q38 | ok | 1 | 123 | 71 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 51.83 | hits.CounterID cmp= [static]: 71 |
| q39 | ok | 1 | 123 | 71 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 23.45 | hits.CounterID cmp= [static]: 71 |
| q40 | ok | 1 | 123 | 71 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 194.55 | hits.CounterID cmp= [static]: 71 |
| q41 | ok | 1 | 123 | 71 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 20.89 | hits.CounterID cmp= [static]: 71 |
| q42 | ok | 1 | 123 | 71 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 15.62 | hits.CounterID cmp= [static]: 71 |
| q43 | ok | 1 | 123 | 71 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 29.6 | hits.CounterID cmp= [static]: 71 |


## Row groups scanned without qualifying rows (3a) by filter shape (columns, kinds)


| benchmark | setup | table | filter_columns_and_kinds | scanned_no_rows |
|---|---|---|---|---|
| micro | point_unsorted | sensor_records | timestamp_ms cmp= | 1220992 |
| micro | range_seconds_unsorted | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 1217129 |
| micro | cardinality_100000 | sensor_records | user_id cmp= | 1128064 |
| micro | range_minutes_unsorted | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 1010459 |
| micro | cardinality_10000 | sensor_records | user_id cmp= | 728804 |
| micro | cardinality_1000 | sensor_records | user_id cmp= | 609351 |
| micro | cardinality_100 | sensor_records | user_id cmp= | 583734 |
| micro | point_outliers | sensor_records | timestamp_ms cmp= | 500296 |
| micro | range_seconds_outliers | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 499317 |
| micro | range_minutes_outliers | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 499304 |
| micro | range_hours_outliers | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 499304 |
| micro | point_sorted | sensor_records | timestamp_ms cmp= | 992 |
| tpcds | tpcds | store_sales | ss_customer_sk cmp= | 349 |
| clickbench | clickbench | hits | rowid optional(in) AND rowid cmp>= AND rowid cmp<= | 233 |
| clickbench | clickbench | hits | URL expression AND SearchPhrase cmp!= | 122 |
| tpcds | tpcds | store_sales | ss_sold_time_sk cmp>= AND ss_sold_time_sk cmp<= AND ss_hdemo_sk cmp>= AND ss_hdemo_sk cmp<= AND ss_store_sk cmp= | 109 |
| clickbench | clickbench | hits | URL expression | 95 |
| clickbench | clickbench | hits | URL expression AND EventTime optional(dynamic_topn) [topn] | 95 |
| clickbench | clickbench | hits | Title expression AND URL expression AND SearchPhrase cmp!= | 76 |
| tpcds | tpcds | catalog_sales | cs_item_sk cmp= | 68 |
| tpcds | tpcds | web_sales | ws_ship_customer_sk expression AND ws_sold_date_sk cmp>= [join] AND ws_sold_date_sk cmp<= [join] AND ws_item_sk cmp>= [join] AND ws_item_sk cmp<= [join] | 39 |
| micro | range_seconds_sorted | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 13 |
| micro | range_hours_unsorted | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 13 |
| clickbench | clickbench | hits | UserID cmp= | 6 |
| tpcds | tpcds | inventory | inv_item_sk optional(in) [join] AND inv_item_sk cmp>= [join] AND inv_item_sk cmp<= [join] AND inv_date_sk cmp>= [join] AND inv_date_sk cmp<= [join] AND inv_quantity_on_hand cmp>= AND inv_quantity_on_hand cmp<= | 4 |
| tpcds | tpcds | store_sales | ss_item_sk cmp>= AND ss_item_sk cmp<= AND ss_sold_date_sk cmp>= AND ss_sold_date_sk cmp<= | 3 |
| tpcds | tpcds | time_dim | t_hour cmp= AND t_minute cmp>= | 3 |
| tpcds | tpcds | store_sales | ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] AND ss_item_sk optional(in) [join] AND ss_item_sk cmp>= [join] AND ss_item_sk cmp<= [join] AND ss_customer_sk cmp>= AND ss_customer_sk optional(in) [join] AND ss_customer_sk cmp>= [join] AND ss_customer_sk cmp<= [join] AND ss_ticket_number optional(in) [join] AND ss_ticket_number cmp>= [join] AND ss_ticket_number cmp<= [join] | 1 |
| tpcds | tpcds | item | i_manufact_id cmp= | 1 |
| tpcds | tpcds | customer_address | ca_address_sk cmp>= AND ca_address_sk cmp<= AND ca_county optional(in) AND ca_county cmp= AND ca_state optional(in) AND ca_state cmp= | 1 |


## TPC-H / TPC-DS / ClickBench: filter sets responsible for 3a row groups (top 40)


| benchmark | table | filter_set | scans | scanned_no_rows |
|---|---|---|---|---|
| tpcds | store_sales | ss_customer_sk=26788 | 1 | 349 |
| clickbench | hits | contains(URL, 'google') AND SearchPhrase!='' | 1 | 122 |
| clickbench | hits | optional:rowid IN (40489, 40490, 78307, 78308, 125324, 255310, 391714, 391715, 502115, 502116) AND rowid>=40489 AND rowid<=502116 | 1 | 117 |
| clickbench | hits | optional:rowid IN (130994, 130995, 584482, 734925, 734927, 738471, 773423, 773424, 856160, 943202) AND rowid>=130994 AND rowid<=943202 | 1 | 116 |
| clickbench | hits | contains(URL, 'google') | 1 | 95 |
| clickbench | hits | contains(URL, 'google') AND optional:topn:EventTime<'2013-07-14 22:59:22'::TIMESTAMP [topn] | 1 | 95 |
| clickbench | hits | contains(Title, 'Google') AND (NOT contains(URL, '.google.')) AND SearchPhrase!='' | 1 | 76 |
| tpcds | catalog_sales | cs_item_sk=7255 | 1 | 68 |
| tpcds | store_sales | ss_sold_time_sk>=73800 AND ss_sold_time_sk<=75599 AND ss_hdemo_sk>=840 AND ss_hdemo_sk<=6959 AND ss_store_sk=4 | 1 | 52 |
| tpcds | web_sales | (ws_ship_customer_sk IS NULL) AND ws_sold_date_sk>=2450816 [join] AND ws_sold_date_sk<=2452642 [join] AND ws_item_sk>=1 [join] AND ws_item_sk<=18000 [join] | 1 | 39 |
| tpcds | store_sales | ss_sold_time_sk>=30600 AND ss_sold_time_sk<=32399 AND ss_hdemo_sk>=1 AND ss_hdemo_sk<=7200 AND ss_store_sk=4 | 1 | 34 |
| tpcds | store_sales | ss_sold_time_sk>=41400 AND ss_sold_time_sk<=43199 AND ss_hdemo_sk>=1 AND ss_hdemo_sk<=7200 AND ss_store_sk=4 | 1 | 6 |
| clickbench | hits | UserID=435090932899640449 | 1 | 6 |
| tpcds | store_sales | ss_sold_time_sk>=34200 AND ss_sold_time_sk<=35999 AND ss_hdemo_sk>=1 AND ss_hdemo_sk<=7200 AND ss_store_sk=4 | 1 | 5 |
| tpcds | store_sales | ss_sold_time_sk>=39600 AND ss_sold_time_sk<=41399 AND ss_hdemo_sk>=1 AND ss_hdemo_sk<=7200 AND ss_store_sk=4 | 1 | 4 |
| tpcds | store_sales | ss_sold_time_sk>=43200 AND ss_sold_time_sk<=44999 AND ss_hdemo_sk>=1 AND ss_hdemo_sk<=7200 AND ss_store_sk=4 | 1 | 4 |
| tpcds | store_sales | ss_sold_time_sk>=32400 AND ss_sold_time_sk<=34199 AND ss_hdemo_sk>=1 AND ss_hdemo_sk<=7200 AND ss_store_sk=4 | 1 | 3 |
| tpcds | inventory | optional:inv_item_sk IN (7255, 8572) [join] AND inv_item_sk>=7255 [join] AND inv_item_sk<=8572 [join] AND inv_date_sk>=2451576 [join] AND inv_date_sk<=2451636 [join] AND inv_quantity_on_hand>=100 AND inv_quantity_on_hand<=500 | 1 | 2 |
| tpcds | inventory | optional:inv_item_sk IN (8514, 10123, 11300, 13677) [join] AND inv_item_sk>=8514 [join] AND inv_item_sk<=13677 [join] AND inv_date_sk>=2451690 [join] AND inv_date_sk<=2451750 [join] AND inv_quantity_on_hand>=100 AND inv_quantity_on_hand<=500 | 1 | 2 |
| tpcds | store_sales | ss_sold_date_sk>=2452001 [join] AND ss_sold_date_sk<=2452030 [join] AND optional:ss_item_sk IN (7463, 9361, 13613) [join] AND ss_item_sk>=7463 [join] AND ss_item_sk<=13613 [join] AND ss_customer_sk>=2 AND optional:ss_customer_sk IN (5250, 38356, 77477) [join] AND ss_customer_sk>=5250 [join] AND ss_customer_sk<=77477 [join] AND optional:ss_ticket_number IN (2995, 16602, 112678) [join] AND ss_ticket_number>=2995 [join] AND ss_ticket_number<=112678 [join] | 1 | 1 |
| tpcds | item | i_manufact_id=977 | 1 | 1 |
| tpcds | store_sales | ss_item_sk>=2 AND ss_item_sk<=18000 AND ss_sold_date_sk>=2450935 AND ss_sold_date_sk<=2450965 | 1 | 1 |
| tpcds | customer_address | ca_address_sk>=63 AND ca_address_sk<=49954 AND optional:ca_county IN ('Williamson County') AND ca_county='Williamson County' AND optional:ca_state IN ('TN') AND ca_state='TN' | 1 | 1 |
| tpcds | store_sales | ss_item_sk>=118 AND ss_item_sk<=17922 AND ss_sold_date_sk>=2451942 AND ss_sold_date_sk<=2451969 | 1 | 1 |
| tpcds | store_sales | ss_item_sk>=1 AND ss_item_sk<=18000 AND ss_sold_date_sk>=2451541 AND ss_sold_date_sk<=2451547 | 1 | 1 |
| tpcds | time_dim | t_hour=9 AND t_minute>=30 | 1 | 1 |
| tpcds | time_dim | t_hour=11 AND t_minute>=30 | 1 | 1 |
| tpcds | store_sales | ss_sold_time_sk>=36000 AND ss_sold_time_sk<=37799 AND ss_hdemo_sk>=1 AND ss_hdemo_sk<=7200 AND ss_store_sk=4 | 1 | 1 |
| tpcds | time_dim | t_hour=20 AND t_minute>=30 | 1 | 1 |


## Query runtimes


| run | setup | queries | ok | failed | total_s | mean_s | median_s | max_s |
|---|---|---|---|---|---|---|---|---|
| count | point_unsorted | 1000 | 1000 | 0 | 41.35 | 0.04 | 0.03 | 1.35 |
| count | point_outliers | 1000 | 1000 | 0 | 16.54 | 0.02 | 0.01 | 0.61 |
| count | point_sorted | 1000 | 1000 | 0 | 3.32 | 0 | 0 | 0.09 |
| count | range_seconds_unsorted | 1000 | 1000 | 0 | 31.88 | 0.03 | 0.03 | 0.68 |
| count | range_seconds_outliers | 1000 | 1000 | 0 | 13.39 | 0.01 | 0.01 | 0.15 |
| count | range_seconds_sorted | 1000 | 1000 | 0 | 3.17 | 0 | 0 | 0.04 |
| count | range_minutes_unsorted | 1000 | 1000 | 0 | 36.72 | 0.04 | 0.03 | 0.64 |
| count | range_minutes_outliers | 1000 | 1000 | 0 | 14.4 | 0.01 | 0.01 | 0.2 |
| count | range_minutes_sorted | 1000 | 1000 | 0 | 3.27 | 0 | 0 | 0.07 |
| count | range_hours_unsorted | 1000 | 1000 | 0 | 107.01 | 0.11 | 0.1 | 0.42 |
| count | range_hours_outliers | 1000 | 1000 | 0 | 92.38 | 0.09 | 0.09 | 0.34 |
| count | range_hours_sorted | 1000 | 1000 | 0 | 108.89 | 0.11 | 0.11 | 0.28 |
| count | cardinality_100 | 1000 | 1000 | 0 | 732.5 | 0.73 | 0.78 | 1.36 |
| count | cardinality_1000 | 1000 | 1000 | 0 | 97.11 | 0.1 | 0.09 | 0.34 |
| count | cardinality_10000 | 1000 | 1000 | 0 | 46.26 | 0.05 | 0.04 | 0.32 |
| count | cardinality_100000 | 1000 | 1000 | 0 | 38.49 | 0.04 | 0.04 | 0.18 |
| count | tpch | 22 | 22 | 0 | 9.44 | 0.43 | 0.22 | 2.86 |
| count | tpcds | 99 | 99 | 0 | 28.6 | 0.29 | 0.12 | 2.21 |
| count | clickbench | 43 | 43 | 0 | 5.21 | 0.12 | 0.04 | 1.85 |
| count_mt12 | point_outliers | 200 | 200 | 0 | 1.01 | 0.01 | 0 | 0.06 |
| count_mt12 | range_minutes_unsorted | 200 | 200 | 0 | 1.98 | 0.01 | 0.01 | 0.11 |
| count_mt12 | cardinality_1000 | 200 | 200 | 0 | 2.44 | 0.01 | 0.01 | 0.07 |
| count_mt12 | tpch | 22 | 22 | 0 | 1.89 | 0.09 | 0.05 | 0.54 |
| count_mt12 | tpcds | 99 | 99 | 0 | 8.85 | 0.09 | 0.04 | 1.18 |
| count_mt12 | clickbench | 43 | 43 | 0 | 1.28 | 0.03 | 0.02 | 0.32 |
| nocount | point_unsorted | 1000 | 1000 | 0 | 40.98 | 0.04 | 0.03 | 1.55 |
| nocount | point_outliers | 1000 | 1000 | 0 | 17.11 | 0.02 | 0.01 | 0.8 |
| nocount | point_sorted | 1000 | 1000 | 0 | 2.7 | 0 | 0 | 0.05 |
| nocount | range_seconds_unsorted | 1000 | 1000 | 0 | 29.77 | 0.03 | 0.03 | 0.55 |
| nocount | range_seconds_outliers | 1000 | 1000 | 0 | 12.69 | 0.01 | 0.01 | 0.14 |
| nocount | range_seconds_sorted | 1000 | 1000 | 0 | 2.29 | 0 | 0 | 0.06 |
| nocount | range_minutes_unsorted | 1000 | 1000 | 0 | 37.04 | 0.04 | 0.03 | 0.74 |
| nocount | range_minutes_outliers | 1000 | 1000 | 0 | 14.04 | 0.01 | 0.01 | 0.27 |
| nocount | range_minutes_sorted | 1000 | 1000 | 0 | 2.55 | 0 | 0 | 0.07 |
| nocount | range_hours_unsorted | 1000 | 1000 | 0 | 106.83 | 0.11 | 0.1 | 0.68 |
| nocount | range_hours_outliers | 1000 | 1000 | 0 | 94.81 | 0.09 | 0.09 | 2.42 |
| nocount | range_hours_sorted | 1000 | 1000 | 0 | 109.36 | 0.11 | 0.11 | 0.26 |
| nocount | cardinality_100 | 1000 | 1000 | 0 | 737.23 | 0.74 | 0.79 | 1.65 |
| nocount | cardinality_1000 | 1000 | 1000 | 0 | 96.57 | 0.1 | 0.09 | 0.24 |
| nocount | cardinality_10000 | 1000 | 1000 | 0 | 45.41 | 0.05 | 0.04 | 0.16 |
| nocount | cardinality_100000 | 1000 | 1000 | 0 | 37.87 | 0.04 | 0.04 | 0.15 |
| nocount | tpch | 22 | 22 | 0 | 7.98 | 0.36 | 0.21 | 1.45 |
| nocount | tpcds | 99 | 99 | 0 | 28.29 | 0.29 | 0.12 | 2.26 |
| nocount | clickbench | 43 | 43 | 0 | 5.52 | 0.13 | 0.05 | 1.92 |
| time | point_unsorted | 1000 | 1000 | 0 | 33.41 | 0.03 | 0.03 | 1.2 |
| time | point_outliers | 1000 | 1000 | 0 | 15.94 | 0.02 | 0.01 | 0.35 |
| time | point_sorted | 1000 | 1000 | 0 | 2.11 | 0 | 0 | 0.04 |
| time | range_seconds_unsorted | 1000 | 1000 | 0 | 35.6 | 0.04 | 0.03 | 0.2 |
| time | range_seconds_outliers | 1000 | 1000 | 0 | 15.37 | 0.02 | 0.01 | 0.12 |
| time | range_seconds_sorted | 1000 | 1000 | 0 | 1.66 | 0 | 0 | 0.02 |
| time | range_minutes_unsorted | 1000 | 1000 | 0 | 37.89 | 0.04 | 0.03 | 0.25 |
| time | range_minutes_outliers | 1000 | 1000 | 0 | 15.9 | 0.02 | 0.01 | 0.62 |
| time | range_minutes_sorted | 1000 | 1000 | 0 | 2.36 | 0 | 0 | 0.03 |
| time | range_hours_unsorted | 1000 | 1000 | 0 | 54.15 | 0.05 | 0.05 | 2.19 |
| time | range_hours_outliers | 1000 | 1000 | 0 | 14.72 | 0.01 | 0.01 | 0.17 |
| time | range_hours_sorted | 1000 | 1000 | 0 | 2.09 | 0 | 0 | 0.02 |
| time | cardinality_100 | 1000 | 1000 | 0 | 42.66 | 0.04 | 0.04 | 0.18 |
| time | cardinality_1000 | 1000 | 1000 | 0 | 37.51 | 0.04 | 0.03 | 1.43 |
| time | cardinality_10000 | 1000 | 1000 | 0 | 26.25 | 0.03 | 0.02 | 1.89 |
| time | cardinality_100000 | 1000 | 1000 | 0 | 25.64 | 0.03 | 0.02 | 0.62 |
| time | tpch | 22 | 22 | 0 | 16.5 | 0.75 | 0.16 | 8.69 |
| time | tpcds | 99 | 99 | 0 | 38.15 | 0.39 | 0.14 | 6.86 |
| time | clickbench | 43 | 43 | 0 | 19.13 | 0.44 | 0.05 | 3.78 |
