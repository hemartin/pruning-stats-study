# Pruning opportunity, scale `large`

Partition = row group of 8,192 rows. *pruned*: skipped by the row-group min/max zonemap. *scanned, no rows* (3a): fully scanned, no row satisfied all pushed-down filters that are applied to rows (could have been pruned). *scanned, with rows* (3b): at least one such row. *partial/not reached*: query stopped early (LIMIT). *incl. optional, no rows*: like 3a but also requiring the optional (zonemap-only) filters, i.e. IN lists / OR clauses / join IN lists / top-N thresholds. See ../../README.md for the exact semantics.

Scans checked against the invariant: 7017, violations: 0

## Benchmark totals

| benchmark | queries | queries_ok | n_scans | total_row_groups | pruned | scanned | scanned_no_rows | scanned_no_rows_all_segments_skipped | scanned_with_rows | partial_no_rows | not_reached | incl_optional_no_rows | pct_pruned | pct_scanned_no_rows_of_scanned |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| micro | 16000 | 6466 | 6466 | 793005970 | 549095066 | 243910904 | 178208300 | 0 | 65702604 | 0 | 0 | 178208300 | 69.24 | 73.06 |
| tpch | 22 | 22 | 86 | 2054850 | 128 | 2054722 | 6 | 0 | 2054716 | 0 | 0 | 6 | 0.01 | 0 |
| tpcds | 99 | 59 | 421 | 3584879 | 656223 | 2928656 | 35808 | 0 | 2892848 | 0 | 0 | 36698 | 18.31 | 1.22 |
| clickbench | 43 | 43 | 44 | 537108 | 152794 | 384314 | 58762 | 0 | 325552 | 0 | 0 | 59853 | 28.45 | 15.29 |

## Microbenchmarks (per setup; sums over all queries, avg = per query)

| setup | queries ok | avg total | avg pruned | avg scanned | avg scanned no rows (3a) | of which seg-skipped | avg scanned with rows (3b) | avg qualifying rows | % pruned | % of scanned w/o rows | avg ms (counting) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| point_unsorted | 238 | 122723 | 0 | 122723 | 122722.53 | 0 | 0.47 | 0.47 | 0 | 100 | 49785.56 |
| point_outliers | 200 | 122723 | 72613.52 | 50109.47 | 50109.15 | 0 | 0.33 | 0.41 | 59.17 | 100 | 1660.02 |
| point_sorted | 1000 | 122723 | 122722 | 1 | 0.67 | 0 | 0.33 | 0.41 | 100 | 66.9 | 242.93 |
| range_seconds_unsorted | 200 | 122723 | 0 | 122723 | 122337.38 | 0 | 385.62 | 386.24 | 0 | 99.69 | 49748.48 |
| range_seconds_outliers | 200 | 122723 | 72613.48 | 50109.52 | 50108.47 | 0 | 1.04 | 386.24 | 59.17 | 100 | 18061.44 |
| range_seconds_sorted | 1000 | 122723 | 122721.96 | 1.04 | 0 | 0 | 1.04 | 385.73 | 100 | 0 | 310.97 |
| range_minutes_unsorted | 229 | 122723 | 0 | 122723 | 101640 | 0 | 21083 | 23135.9 | 0 | 82.82 | 43974.25 |
| range_minutes_outliers | 200 | 122723 | 72610.66 | 50112.34 | 50108.47 | 0 | 3.87 | 23130.01 | 59.17 | 99.99 | 882.12 |
| range_minutes_sorted | 1000 | 122723 | 122719.17 | 3.83 | 0 | 0 | 3.83 | 23148.6 | 100 | 0 | 59.4 |
| range_hours_unsorted | 200 | 122723 | 0 | 122723 | 1.94 | 0 | 122721.07 | 1388611 | 0 | 0 | 58418.1 |
| range_hours_outliers | 200 | 122723 | 72443.1 | 50279.9 | 50108.47 | 0 | 171.43 | 1388611 | 59.03 | 99.66 | 948.53 |
| range_hours_sorted | 1000 | 122723 | 122551.57 | 171.43 | 0 | 0 | 171.43 | 1388821 | 99.86 | 0 | 81.03 |
| cardinality_100 | 199 | 122071 | 1047.32 | 121023.68 | 59980.27 | 0 | 61043.41 | 10000704 | 0.86 | 49.56 | 1406.08 |
| cardinality_1000 | 200 | 122071 | 484.83 | 121586.17 | 60545.54 | 0 | 61040.64 | 1000094 | 0.4 | 49.8 | 1385.31 |
| cardinality_10000 | 200 | 122071 | 76.82 | 121994.18 | 72795.04 | 0 | 49199.14 | 100033.52 | 0.06 | 59.67 | 1099.94 |
| cardinality_100000 | 200 | 122071 | 17.32 | 122053.68 | 112825.71 | 0 | 9227.98 | 10007.25 | 0.01 | 92.44 | 684.66 |


Sums over the 1,000 queries of each setup:


| setup | total | pruned | scanned | scanned no rows (3a) | scanned with rows (3b) | partial, no rows | not reached | pruned by predicate |
|---|---|---|---|---|---|---|---|---|
| point_unsorted | 29208074 | 0 | 29208074 | 29207963 | 111 | 0 | 0 |  |
| point_outliers | 24544600 | 14522705 | 10021895 | 10021830 | 65 | 0 | 0 | sensor_records.timestamp_ms cmp= [static]: 14522705 |
| point_sorted | 122723000 | 122722000 | 1000 | 669 | 331 | 0 | 0 | sensor_records.timestamp_ms cmp= [static]: 122722000 |
| range_seconds_unsorted | 24544600 | 0 | 24544600 | 24467477 | 77123 | 0 | 0 |  |
| range_seconds_outliers | 24544600 | 14522696 | 10021904 | 10021695 | 209 | 0 | 0 | sensor_records.timestamp_ms cmp<= [static]: 12245427; sensor_records.timestamp_ms cmp>= [static]: 2277269 |
| range_seconds_sorted | 122723000 | 122721964 | 1036 | 0 | 1036 | 0 | 0 | sensor_records.timestamp_ms cmp>= [static]: 61383410; sensor_records.timestamp_ms cmp<= [static]: 61338554 |
| range_minutes_unsorted | 28103567 | 0 | 28103567 | 23275559 | 4828008 | 0 | 0 |  |
| range_minutes_outliers | 24544600 | 14522132 | 10022468 | 10021695 | 773 | 0 | 0 | sensor_records.timestamp_ms cmp<= [static]: 12244863; sensor_records.timestamp_ms cmp>= [static]: 2277269 |
| range_minutes_sorted | 122723000 | 122719172 | 3828 | 0 | 3828 | 0 | 0 | sensor_records.timestamp_ms cmp>= [static]: 61383410; sensor_records.timestamp_ms cmp<= [static]: 61335762 |
| range_hours_unsorted | 24544600 | 0 | 24544600 | 387 | 24544213 | 0 | 0 |  |
| range_hours_outliers | 24544600 | 14488620 | 10055980 | 10021695 | 34285 | 0 | 0 | sensor_records.timestamp_ms cmp<= [static]: 12211351; sensor_records.timestamp_ms cmp>= [static]: 2277269 |
| range_hours_sorted | 122723000 | 122551566 | 171434 | 0 | 171434 | 0 | 0 | sensor_records.timestamp_ms cmp>= [static]: 61383410; sensor_records.timestamp_ms cmp<= [static]: 61168156 |
| cardinality_100 | 24292129 | 208417 | 24083712 | 11936074 | 12147638 | 0 | 0 | sensor_records.user_id cmp= [static]: 208417 |
| cardinality_1000 | 24414200 | 96966 | 24317234 | 12109107 | 12208127 | 0 | 0 | sensor_records.user_id cmp= [static]: 96966 |
| cardinality_10000 | 24414200 | 15364 | 24398836 | 14559008 | 9839828 | 0 | 0 | sensor_records.user_id cmp= [static]: 15364 |
| cardinality_100000 | 24414200 | 3464 | 24410736 | 22565141 | 1845595 | 0 | 0 | sensor_records.user_id cmp= [static]: 3464 |


## tpch (per query, summed over its table scans)


| query | status | scans | total | pruned | scanned | scanned no rows (3a) | of which seg-skipped | scanned with rows (3b) | partial, no rows | not reached | 3a incl. optional | EMPTY_RESULT ops | bound refs - plan scans | plan scans not executed | ms | pruned by predicate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q01 | ok | 1 | 80894 | 0 | 80894 | 0 | 0 | 80894 | 0 | 0 | 0 | 0 | 0 | 0 | 72881.03 |  |
| q02 | ok | 9 | 24104 | 0 | 24104 | 0 | 0 | 24104 | 0 | 0 | 0 | 0 | 0 | 0 | 9590.69 |  |
| q03 | ok | 3 | 103008 | 0 | 103008 | 0 | 0 | 103008 | 0 | 0 | 0 | 0 | 0 | 0 | 88744.97 |  |
| q04 | ok | 2 | 101136 | 0 | 101136 | 0 | 0 | 101136 | 0 | 0 | 0 | 0 | 0 | 0 | 71039.8 |  |
| q05 | ok | 6 | 103137 | 0 | 103137 | 0 | 0 | 103137 | 0 | 0 | 0 | 0 | 0 | 0 | 75741.67 |  |
| q06 | ok | 1 | 80894 | 0 | 80894 | 0 | 0 | 80894 | 0 | 0 | 0 | 0 | 0 | 0 | 64810.69 |  |
| q07 | ok | 6 | 103137 | 0 | 103137 | 0 | 0 | 103137 | 0 | 0 | 0 | 0 | 0 | 0 | 85288.45 |  |
| q08 | ok | 8 | 105654 | 0 | 105654 | 0 | 0 | 105654 | 0 | 0 | 0 | 0 | 0 | 0 | 57773.95 |  |
| q09 | ok | 6 | 114445 | 0 | 114445 | 0 | 0 | 114445 | 0 | 0 | 0 | 0 | 0 | 0 | 128263.98 |  |
| q10 | ok | 4 | 103009 | 0 | 103009 | 0 | 0 | 103009 | 0 | 0 | 0 | 0 | 0 | 0 | 74512.45 |  |
| q11 | ok | 6 | 21586 | 0 | 21586 | 0 | 0 | 21586 | 0 | 0 | 0 | 0 | 0 | 0 | 10050.28 |  |
| q12 | ok | 2 | 101136 | 0 | 101136 | 0 | 0 | 101136 | 0 | 0 | 0 | 0 | 0 | 0 | 108935.95 |  |
| q13 | ok | 2 | 22114 | 0 | 22114 | 0 | 0 | 22114 | 0 | 0 | 0 | 0 | 0 | 0 | 46455.61 |  |
| q14 | ok | 2 | 83410 | 0 | 83410 | 1 | 0 | 83409 | 0 | 0 | 1 | 0 | 0 | 0 | 57333.08 |  |
| q15 | ok | 2 | 81021 | 126 | 80895 | 0 | 0 | 80895 | 0 | 0 | 0 | 0 | 0 | 0 | 64092.39 | supplier.s_suppkey cmp= [join]: 126 |
| q16 | ok | 3 | 13308 | 0 | 13308 | 3 | 0 | 13305 | 0 | 0 | 3 | 0 | 0 | 0 | 24589.25 |  |
| q17 | ok | 3 | 164304 | 0 | 164304 | 2 | 0 | 164302 | 0 | 0 | 2 | 0 | 0 | 0 | 78738.59 |  |
| q18 | ok | 4 | 183902 | 0 | 183902 | 0 | 0 | 183902 | 0 | 0 | 0 | 0 | 0 | 0 | 157264.91 |  |
| q19 | ok | 2 | 83410 | 0 | 83410 | 0 | 0 | 83410 | 0 | 0 | 0 | 0 | 0 | 0 | 95782.87 |  |
| q20 | ok | 5 | 94203 | 0 | 94203 | 0 | 0 | 94203 | 0 | 0 | 0 | 0 | 0 | 0 | 44465.34 |  |
| q21 | ok | 6 | 263052 | 2 | 263050 | 0 | 0 | 263050 | 0 | 0 | 0 | 0 | 0 | 0 | 211010.91 | lineitem.l_orderkey cmp<= [join]: 2 |
| q22 | ok | 3 | 23986 | 0 | 23986 | 0 | 0 | 23986 | 0 | 0 | 0 | 0 | 0 | 0 | 24979.46 |  |


## tpcds (per query, summed over its table scans)


| query | status | scans | total | pruned | scanned | scanned no rows (3a) | of which seg-skipped | scanned with rows (3b) | partial, no rows | not reached | 3a incl. optional | EMPTY_RESULT ops | bound refs - plan scans | plan scans not executed | ms | pruned by predicate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q01 | ok | 4 | 4166 | 8 | 4158 | 0 | 0 | 4158 | 0 | 0 | 0 | 0 | 0 | 0 | 13760.92 | date_dim.d_year cmp= [static]: 8 |
| q02 | ok | 5 | 28943 | 24 | 28919 | 0 | 0 | 28919 | 0 | 0 | 0 | 0 | 0 | 0 | 23683.85 | date_dim.d_year cmp= [static]: 16; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q03 | ok | 3 | 35650 | 1 | 35649 | 0 | 0 | 35649 | 0 | 0 | 0 | 0 | 0 | 0 | 31849.65 | store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q04 | ok | 18 | 130718 | 30915 | 99803 | 1 | 0 | 99802 | 0 | 0 | 1 | 0 | -9 | 0 | 142000.1 | catalog_sales.cs_sold_date_sk cmp>= [join]: 26830; catalog_sales.cs_sold_date_sk cmp<= [join]: 4034; date_dim.d_year cmp= [static]: 48; store_sales.ss_sold_date_sk cmp>= [join]: 3 |
| q05 | ok | 13 | 80966 | 20848 | 60118 | 83 | 0 | 60035 | 0 | 0 | 83 | 0 | 0 | 0 | 64910.03 | catalog_sales.cs_sold_date_sk cmp<= [join]: 9853; catalog_sales.cs_sold_date_sk cmp>= [join]: 9235; catalog_returns.cr_returned_date_sk cmp<= [join]: 1026; catalog_returns.cr_returned_date_sk cmp>= [join]: 709; date_dim.d_date cmp>= [static]: 12; date_dim.d_date cmp<= [static]: 12; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q06 | ok | 7 | 36084 | 17 | 36067 | 48 | 0 | 36019 | 0 | 0 | 48 | 0 | 0 | 0 | 46228.51 | date_dim.d_year cmp= [static]: 8; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q07 | ok | 5 | 35892 | 9 | 35883 | 2 | 0 | 35881 | 0 | 0 | 2 | 0 | 0 | 0 | 21559.47 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q08 | ok | 6 | 36146 | 14 | 36132 | 5 | 0 | 36127 | 0 | 0 | 5 | 0 | 0 | 0 | 38660.14 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp<= [join]: 6 |
| q09 | ok | 16 | 534181 | 3 | 534178 | 9 | 0 | 534169 | 0 | 0 | 9 | 0 | 0 | 0 | 480942.56 | store_sales.ss_quantity cmp<= [static]: 3 |
| q10 | ok | 9 | 65192 | 18590 | 46602 | 7 | 0 | 46595 | 0 | 0 | 7 | 0 | 0 | 0 | 61034.22 | catalog_sales.cs_sold_date_sk cmp>= [join]: 15346; catalog_sales.cs_sold_date_sk cmp<= [join]: 3218; date_dim.d_year cmp= [static]: 24; store_sales.ss_sold_date_sk cmp>= [join]: 2 |
| q11 | ok | 12 | 91572 | 35 | 91537 | 1 | 0 | 91536 | 0 | 0 | 1 | 0 | -6 | 0 | 162891.76 | date_dim.d_year cmp= [static]: 32; store_sales.ss_sold_date_sk cmp>= [join]: 3 |
| q12 | ok | 3 | 9658 | 8 | 9650 | 61 | 0 | 9589 | 0 | 0 | 61 | 0 | 0 | 0 | 9157.34 | date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q13 | ok | 6 | 35992 | 9 | 35983 | 1 | 0 | 35982 | 0 | 0 | 1 | 0 | 0 | 0 | 45815.06 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q14 | ok | 25 | 193868 | 34252 | 159616 | 12 | 0 | 159604 | 0 | 0 | 12 | 0 | 0 | 0 | 180141.36 | catalog_sales.cs_sold_date_sk cmp>= [join]: 21671; catalog_sales.cs_sold_date_sk cmp<= [join]: 12505; date_dim.d_year cmp>= [static]: 24; date_dim.d_year cmp<= [static]: 24; date_dim.d_year cmp= [static]: 24; store_sales.ss_sold_date_sk cmp>= [join]: 4 |
| q15 | ok | 4 | 19701 | 18743 | 958 | 0 | 0 | 958 | 0 | 0 | 0 | 0 | 0 | 0 | 3455.54 | catalog_sales.cs_sold_date_sk cmp>= [join]: 12035; catalog_sales.cs_sold_date_sk cmp<= [join]: 6700; date_dim.d_year cmp= [static]: 8 |
| q16 | ok | 6 | 40712 | 36798 | 3914 | 0 | 0 | 3914 | 0 | 0 | 0 | 0 | 0 | 0 | 4505.67 | catalog_sales.cs_ship_date_sk cmp>= [join]: 14095; catalog_sales.cs_order_number cmp>= [join]: 14095; catalog_sales.cs_ship_date_sk cmp<= [join]: 3402; catalog_sales.cs_order_number cmp<= [join]: 3402; catalog_returns.cr_order_number cmp>= [join]: 1446; catalog_returns.cr_order_number cmp<= [join]: 350; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q17 | ok | 8 | 58853 | 17165 | 41688 | 8 | 0 | 41680 | 0 | 0 | 8 | 0 | 0 | 0 | 27030.82 | catalog_sales.cs_sold_date_sk cmp>= [join]: 11484; catalog_sales.cs_sold_date_sk cmp<= [join]: 5656; date_dim.d_quarter_name optional(in) [static]: 16; date_dim.d_quarter_name cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q18 | ok | 7 | 20212 | 15497 | 4715 | 0 | 0 | 4715 | 0 | 0 | 0 | 0 | 0 | 0 | 4428.87 | catalog_sales.cs_sold_date_sk cmp<= [join]: 15489; date_dim.d_year cmp= [static]: 8 |
| q19 | ok | 6 | 36047 | 11 | 36036 | 3 | 0 | 36033 | 0 | 0 | 3 | 0 | 0 | 0 | 10811.6 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp<= [join]: 2; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q20 | ok | 3 | 19334 | 19120 | 214 | 0 | 0 | 214 | 0 | 0 | 0 | 0 | 0 | 0 | 821.55 | catalog_sales.cs_sold_date_sk cmp<= [join]: 14989; catalog_sales.cs_sold_date_sk cmp>= [join]: 4123; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q21 | ok | 4 | 49398 | 47666 | 1732 | 0 | 0 | 1732 | 0 | 0 | 0 | 0 | 0 | 0 | 2493.69 | inventory.inv_date_sk cmp<= [join]: 26854; inventory.inv_date_sk cmp>= [join]: 20804; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q22 | ok | 3 | 49397 | 39533 | 9864 | 0 | 0 | 9864 | 0 | 0 | 0 | 0 | 0 | 0 | 14917.09 | inventory.inv_date_sk cmp>= [join]: 19857; inventory.inv_date_sk cmp<= [join]: 19668; date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4 |
| q23 | ok | 14 | 136889 | 19153 | 117736 | 79 | 0 | 117657 | 0 | 0 | 79 | 0 | 0 | 0 | 260193.65 | catalog_sales.cs_sold_date_sk cmp<= [join]: 11297; catalog_sales.cs_sold_date_sk cmp>= [join]: 7822; date_dim.d_year cmp= [static]: 16; date_dim.d_year cmp>= [static]: 8; date_dim.d_year cmp<= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 2 |
| q24 | ok | 6 | 39926 | 1 | 39925 | 0 | 0 | 39925 | 0 | 0 | 0 | 0 | 0 | 0 | 28536.6 | store_returns.sr_ticket_number cmp<= [join]: 1 |
| q25 | ok | 8 | 58853 | 17308 | 41545 | 67 | 0 | 41478 | 0 | 0 | 67 | 0 | 0 | 0 | 24575.83 | catalog_sales.cs_sold_date_sk cmp>= [join]: 12029; catalog_sales.cs_sold_date_sk cmp<= [join]: 5236; date_dim.d_year cmp= [static]: 24; item.i_item_sk optional(in) [join]: 17; store_sales.ss_sold_date_sk cmp>= [join]: 2 |
| q26 | ok | 5 | 19576 | 15453 | 4123 | 0 | 0 | 4123 | 0 | 0 | 0 | 0 | 0 | 0 | 12253.58 | catalog_sales.cs_sold_date_sk cmp<= [join]: 7811; catalog_sales.cs_sold_date_sk cmp>= [join]: 7634; date_dim.d_year cmp= [static]: 8 |
| q27 | ok | 15 | 107676 | 30 | 107646 | 0 | 0 | 107646 | 0 | 0 | 27 | 0 | -10 | 0 | 156466.09 | date_dim.d_year cmp= [static]: 24; store_sales.ss_sold_date_sk cmp>= [join]: 6 |
| q28 | ok | 6 | 213672 | 9 | 213663 | 3 | 0 | 213660 | 0 | 0 | 3 | 0 | 0 | 0 | 245871.23 | store_sales.ss_quantity cmp<= [static]: 9 |
| q29 | ok | 8 | 58853 | 7781 | 51072 | 11 | 0 | 51061 | 0 | 0 | 11 | 0 | 0 | 0 | 62935.78 | catalog_sales.cs_sold_date_sk cmp<= [join]: 3949; catalog_sales.cs_sold_date_sk cmp>= [join]: 3806; date_dim.d_year cmp= [static]: 16; date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4; store_sales.ss_sold_date_sk cmp>= [join]: 1; store_sales.ss_sold_date_sk cmp<= [join]: 1 |
| q30 | ok | 5 | 1449 | 8 | 1441 | 0 | 0 | 1441 | 0 | 0 | 0 | 0 | 0 | 0 | 1555.38 | date_dim.d_year cmp= [static]: 8 |
| q31 | ok | 6 | 45506 | 17 | 45489 | 2 | 0 | 45487 | 0 | 0 | 2 | 0 | 0 | 0 | 50641.3 | date_dim.d_date_sk cmp>= [static]: 8; date_dim.d_date_sk cmp<= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q32 | ok | 5 | 38639 | 37500 | 1139 | 8 | 0 | 1131 | 0 | 0 | 81 | 0 | 0 | 0 | 2814.55 | catalog_sales.cs_sold_date_sk cmp<= [join]: 21900; catalog_sales.cs_sold_date_sk cmp>= [join]: 15584; date_dim.d_date cmp>= [static]: 8; date_dim.d_date cmp<= [static]: 8 |
| q33 | ok | 15 | 65113 | 19141 | 45972 | 101 | 0 | 45871 | 0 | 0 | 101 | 0 | 0 | 0 | 22288.78 | catalog_sales.cs_sold_date_sk cmp<= [join]: 18392; catalog_sales.cs_sold_date_sk cmp>= [join]: 716; date_dim.d_year cmp= [static]: 24; store_sales.ss_sold_date_sk cmp<= [join]: 9 |
| q34 | ok | 5 | 35891 | 9 | 35882 | 0 | 0 | 35882 | 0 | 0 | 9 | 0 | 0 | 0 | 21503.94 | date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q35 | ok | 9 | 65192 | 17163 | 48029 | 1 | 0 | 48028 | 0 | 0 | 1 | 0 | 0 | 0 | 29085.02 | catalog_sales.cs_sold_date_sk cmp>= [join]: 15346; catalog_sales.cs_sold_date_sk cmp<= [join]: 1791; date_dim.d_year cmp= [static]: 24; store_sales.ss_sold_date_sk cmp>= [join]: 2 |
| q36 | ok | 4 | 35651 | 9 | 35642 | 1 | 0 | 35641 | 0 | 0 | 10 | 0 | 0 | 0 | 48695.61 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q37 | ok | 4 | 68693 | 48440 | 20253 | 3 | 0 | 20250 | 0 | 0 | 775 | 0 | 0 | 0 | 15564.95 | inventory.inv_item_sk optional(in) [join]: 22491; inventory.inv_date_sk cmp<= [join]: 14730; inventory.inv_date_sk cmp>= [join]: 11211; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q38 | ok | 9 | 65359 | 15470 | 49889 | 2 | 0 | 49887 | 0 | 0 | 2 | 0 | 0 | 0 | 50013.7 | catalog_sales.cs_sold_date_sk cmp<= [join]: 7811; catalog_sales.cs_sold_date_sk cmp>= [join]: 7634; date_dim.d_month_seq cmp>= [static]: 12; date_dim.d_month_seq cmp<= [static]: 12; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q39 | ok | 4 | 49398 | 47852 | 1546 | 0 | 0 | 1546 | 0 | 0 | 0 | 0 | 0 | 0 | 4478.13 | inventory.inv_date_sk cmp>= [join]: 29690; inventory.inv_date_sk cmp<= [join]: 18154; date_dim.d_year cmp= [static]: 8 |
| q40 | ok | 5 | 21317 | 18932 | 2385 | 0 | 0 | 2385 | 0 | 0 | 0 | 0 | 0 | 0 | 3303.17 | catalog_sales.cs_sold_date_sk cmp<= [join]: 11047; catalog_sales.cs_sold_date_sk cmp>= [join]: 7877; date_dim.d_date cmp>= [static]: 4; date_dim.d_date cmp<= [static]: 4 |
| q41 | ok | 2 | 58 | 0 | 58 | 0 | 0 | 58 | 0 | 0 | 0 | 0 | 0 | 0 | 275.29 |  |
| q42 | ok | 3 | 35650 | 9 | 35641 | 9 | 0 | 35632 | 0 | 0 | 9 | 0 | 0 | 0 | 50684.98 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q43 | ok | 3 | 35622 | 9 | 35613 | 2 | 0 | 35611 | 0 | 0 | 2 | 0 | 0 | 0 | 36374.64 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q44 | ok | 6 | 142506 | 129 | 142377 | 34624 | 0 | 107753 | 0 | 0 | 34624 | 0 | 0 | 0 | 172621.36 | store_sales.ss_store_sk cmp= [static]: 88; item.i_item_sk optional(in) [join]: 41 |
| q45 | ok | 6 | 10083 | 36 | 10047 | 0 | 0 | 10047 | 0 | 0 | 0 | 0 | 0 | 0 | 13696.53 | item.i_item_sk optional(in) [static]: 28; date_dim.d_year cmp= [static]: 8 |
| q46 | ok | 7 | 36147 | 9 | 36138 | 0 | 0 | 36138 | 0 | 0 | 0 | 0 | 0 | 0 | 83168.34 | date_dim.d_year cmp>= [static]: 4; date_dim.d_year cmp<= [static]: 4; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q47 | ok | 4 | 35651 | 9 | 35642 | 0 | 0 | 35642 | 0 | 0 | 0 | 0 | 0 | 0 | 47739.63 | date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q48 | ok | 5 | 35991 | 9 | 35982 | 2 | 0 | 35980 | 0 | 0 | 2 | 0 | 0 | 0 | 60169.82 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q49 | ok | 9 | 71341 | 20653 | 50688 | 9 | 0 | 50679 | 0 | 0 | 9 | 0 | 0 | 0 | 69522.95 | catalog_sales.cs_sold_date_sk cmp>= [join]: 14688; catalog_sales.cs_sold_date_sk cmp<= [join]: 3949; catalog_returns.cr_order_number cmp>= [join]: 1507; catalog_returns.cr_order_number cmp<= [join]: 406; store_returns.sr_return_amt cmp> [static]: 77; date_dim.d_year cmp= [static]: 24; store_sales.ss_sold_date_sk cmp>= [join]: 2 |
| q50 | ok | 5 | 39519 | 16 | 39503 | 0 | 0 | 39503 | 0 | 0 | 0 | 0 | 0 | 0 | 41284.74 | date_dim.d_year cmp= [static]: 8; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q51 | ok | 4 | 45250 | 17 | 45233 | 2 | 0 | 45231 | 0 | 0 | 2 | 0 | 0 | 0 | 82341.21 | date_dim.d_month_seq cmp>= [static]: 8; date_dim.d_month_seq cmp<= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q52 | ok | 3 | 35650 | 9 | 35641 | 9 | 0 | 35632 | 0 | 0 | 9 | 0 | 0 | 0 | 15397.17 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q53 | ok | 4 | 35651 | 9 | 35642 | 2 | 0 | 35640 | 0 | 0 | 2 | 0 | 0 | 0 | 34069.04 | date_dim.d_month_seq cmp>= [static]: 4; date_dim.d_month_seq cmp<= [static]: 4; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q54 | ok | 11 | 64990 | 18681 | 46309 | 9 | 0 | 46300 | 0 | 0 | 9 | 0 | 0 | 0 | 52121.11 | catalog_sales.cs_sold_date_sk cmp<= [join]: 15489; catalog_sales.cs_sold_date_sk cmp>= [join]: 3157; date_dim.d_year cmp= [static]: 24; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4; store_sales.ss_sold_date_sk cmp<= [join]: 2; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q55 | ok | 3 | 35650 | 10 | 35640 | 11 | 0 | 35629 | 0 | 0 | 11 | 0 | 0 | 0 | 32346.74 | date_dim.d_year cmp= [static]: 8; store_sales.ss_sold_date_sk cmp>= [join]: 1; store_sales.ss_sold_date_sk cmp<= [join]: 1 |
| q56 | ok | 15 | 65113 | 19148 | 45965 | 166 | 0 | 45799 | 0 | 0 | 166 | 0 | 0 | 0 | 84776.15 | catalog_sales.cs_sold_date_sk cmp>= [join]: 11674; catalog_sales.cs_sold_date_sk cmp<= [join]: 7449; date_dim.d_year cmp= [static]: 24; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q57 | ok | 4 | 19335 | 14638 | 4697 | 0 | 0 | 4697 | 0 | 0 | 0 | 0 | 0 | 0 | 9732.07 | catalog_sales.cs_sold_date_sk cmp<= [join]: 11473; catalog_sales.cs_sold_date_sk cmp>= [join]: 3157; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |
| q58 | ok | 15 | 64696 | 19266 | 45430 | 444 | 0 | 44986 | 0 | 0 | 444 | 0 | 0 | 0 | 51343.49 | catalog_sales.cs_sold_date_sk cmp<= [join]: 11643; catalog_sales.cs_sold_date_sk cmp>= [join]: 7550; date_dim.d_date cmp= [static]: 24; date_dim.d_week_seq cmp= [join]: 24; date_dim.d_date optional(in) [join]: 24; store_sales.ss_sold_date_sk cmp>= [join]: 1 |
| q59 | ok | 6 | 35641 | 24 | 35617 | 0 | 0 | 35617 | 0 | 0 | 0 | 0 | 0 | 0 | 38597.01 | date_dim.d_month_seq cmp>= [static]: 8; date_dim.d_month_seq cmp<= [static]: 8; date_dim.d_date_sk cmp>= [static]: 4; date_dim.d_date_sk cmp<= [static]: 4 |


## clickbench (per query, summed over its table scans)


| query | status | scans | total | pruned | scanned | scanned no rows (3a) | of which seg-skipped | scanned with rows (3b) | partial, no rows | not reached | 3a incl. optional | EMPTY_RESULT ops | bound refs - plan scans | plan scans not executed | ms | pruned by predicate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q01 | ok | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 2166.98 |  |
| q02 | ok | 1 | 12207 | 6346 | 5861 | 0 | 0 | 5861 | 0 | 0 | 0 | 0 | 0 | 0 | 10144.11 | hits.AdvEngineID cmp!= [static]: 6346 |
| q03 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 12178.25 |  |
| q04 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 10167.12 |  |
| q05 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 3521.04 |  |
| q06 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 24055.78 |  |
| q07 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 1268.29 |  |
| q08 | ok | 1 | 12207 | 6346 | 5861 | 0 | 0 | 5861 | 0 | 0 | 0 | 0 | 0 | 0 | 816.95 | hits.AdvEngineID cmp!= [static]: 6346 |
| q09 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 9366.09 |  |
| q10 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 18535.99 |  |
| q11 | ok | 1 | 12207 | 0 | 12207 | 14 | 0 | 12193 | 0 | 0 | 14 | 0 | 0 | 0 | 33484.73 |  |
| q12 | ok | 1 | 12207 | 0 | 12207 | 14 | 0 | 12193 | 0 | 0 | 14 | 0 | 0 | 0 | 10108.62 |  |
| q13 | ok | 1 | 12207 | 0 | 12207 | 72 | 0 | 12135 | 0 | 0 | 72 | 0 | 0 | 0 | 9512.35 |  |
| q14 | ok | 1 | 12207 | 0 | 12207 | 72 | 0 | 12135 | 0 | 0 | 72 | 0 | 0 | 0 | 16061.59 |  |
| q15 | ok | 1 | 12207 | 0 | 12207 | 72 | 0 | 12135 | 0 | 0 | 72 | 0 | 0 | 0 | 9662.2 |  |
| q16 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 23367.55 |  |
| q17 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 55182.47 |  |
| q18 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 37449.38 |  |
| q19 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 65973.18 |  |
| q20 | ok | 1 | 12207 | 9458 | 2749 | 2748 | 0 | 1 | 0 | 0 | 2748 | 0 | 0 | 0 | 3743.21 | hits.UserID cmp= [static]: 9458 |
| q21 | ok | 1 | 12207 | 0 | 12207 | 9032 | 0 | 3175 | 0 | 0 | 9032 | 0 | 0 | 0 | 33171.04 |  |
| q22 | ok | 1 | 12207 | 0 | 12207 | 11620 | 0 | 587 | 0 | 0 | 11620 | 0 | 0 | 0 | 39917.66 |  |
| q23 | ok | 1 | 12207 | 0 | 12207 | 9429 | 0 | 2778 | 0 | 0 | 9429 | 0 | 0 | 0 | 48813.9 |  |
| q24 | ok | 2 | 24414 | 10706 | 13708 | 13325 | 0 | 383 | 0 | 0 | 13558 | 0 | -1 | 0 | 10124.1 | hits.EventTime optional(dynamic_topn) [topn]: 10706 |
| q25 | ok | 2 | 24414 | 11563 | 12851 | 12205 | 0 | 646 | 0 | 0 | 12624 | 0 | -1 | 0 | 565.24 | hits.EventTime optional(dynamic_topn) [topn]: 11563 |
| q26 | ok | 1 | 12207 | 12010 | 197 | 0 | 0 | 197 | 0 | 0 | 20 | 0 | 0 | 0 | 2329.94 | hits.SearchPhrase optional(dynamic_topn) [topn]: 12010 |
| q27 | ok | 1 | 12207 | 11560 | 647 | 8 | 0 | 639 | 0 | 0 | 427 | 0 | 0 | 0 | 804.82 | hits.EventTime optional(dynamic_topn) [topn]: 11560 |
| q28 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 38803.56 |  |
| q29 | ok | 1 | 12207 | 0 | 12207 | 7 | 0 | 12200 | 0 | 0 | 7 | 0 | 0 | 0 | 66183.39 |  |
| q30 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 7859.45 |  |
| q31 | ok | 1 | 12207 | 0 | 12207 | 72 | 0 | 12135 | 0 | 0 | 72 | 0 | 0 | 0 | 47465.64 |  |
| q32 | ok | 1 | 12207 | 0 | 12207 | 72 | 0 | 12135 | 0 | 0 | 72 | 0 | 0 | 0 | 54809.26 |  |
| q33 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 92759.26 |  |
| q34 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 38948.25 |  |
| q35 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 23464.69 |  |
| q36 | ok | 1 | 12207 | 0 | 12207 | 0 | 0 | 12207 | 0 | 0 | 0 | 0 | 0 | 0 | 11654.08 |  |
| q37 | ok | 1 | 12207 | 12115 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 1031.84 | hits.CounterID cmp= [static]: 12115 |
| q38 | ok | 1 | 12207 | 12115 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 265.3 | hits.CounterID cmp= [static]: 12115 |
| q39 | ok | 1 | 12207 | 12115 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 141.49 | hits.CounterID cmp= [static]: 12115 |
| q40 | ok | 1 | 12207 | 12115 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 305.76 | hits.CounterID cmp= [static]: 12115 |
| q41 | ok | 1 | 12207 | 12115 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 2082.53 | hits.CounterID cmp= [static]: 12115 |
| q42 | ok | 1 | 12207 | 12115 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 167.8 | hits.CounterID cmp= [static]: 12115 |
| q43 | ok | 1 | 12207 | 12115 | 92 | 0 | 0 | 92 | 0 | 0 | 0 | 0 | 0 | 0 | 67.69 | hits.CounterID cmp= [static]: 12115 |


## Row groups scanned without qualifying rows (3a) by filter shape (columns, kinds)


| benchmark | setup | table | filter_columns_and_kinds | scanned_no_rows |
|---|---|---|---|---|
| micro | point_unsorted | sensor_records | timestamp_ms cmp= | 29207963 |
| micro | range_seconds_unsorted | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 24467477 |
| micro | range_minutes_unsorted | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 23275559 |
| micro | cardinality_100000 | sensor_records | user_id cmp= | 22565141 |
| micro | cardinality_10000 | sensor_records | user_id cmp= | 14559008 |
| micro | cardinality_1000 | sensor_records | user_id cmp= | 12109107 |
| micro | cardinality_100 | sensor_records | user_id cmp= | 11936074 |
| micro | point_outliers | sensor_records | timestamp_ms cmp= | 10021830 |
| micro | range_seconds_outliers | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 10021695 |
| micro | range_minutes_outliers | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 10021695 |
| micro | range_hours_outliers | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 10021695 |
| tpcds | tpcds | store_sales | ss_store_sk cmp= AND ss_addr_sk expression | 32084 |
| clickbench | clickbench | hits | rowid optional(in) [join] AND rowid cmp>= [join] AND rowid cmp<= [join] | 24397 |
| clickbench | clickbench | hits | URL expression AND SearchPhrase cmp!= | 11620 |
| clickbench | clickbench | hits | Title expression AND URL expression AND SearchPhrase cmp!= | 9429 |
| clickbench | clickbench | hits | URL expression | 9032 |
| clickbench | clickbench | hits | UserID cmp= | 2748 |
| tpcds | tpcds | store_sales | ss_store_sk cmp= | 2540 |
| clickbench | clickbench | hits | URL expression AND EventTime optional(dynamic_topn) [topn] | 1125 |
| micro | point_sorted | sensor_records | timestamp_ms cmp= | 669 |
| micro | range_hours_unsorted | sensor_records | timestamp_ms cmp>= AND timestamp_ms cmp<= | 387 |
| clickbench | clickbench | hits | SearchPhrase cmp!= | 360 |
| tpcds | tpcds | store_sales | ss_item_sk cmp>= [join] AND ss_item_sk cmp<= [join] AND ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] | 296 |
| tpcds | tpcds | web_sales | ws_item_sk cmp>= [join] AND ws_item_sk cmp<= [join] AND ws_sold_date_sk cmp>= [join] AND ws_sold_date_sk cmp<= [join] | 209 |
| tpcds | tpcds | store_sales | ss_item_sk cmp>= [join] AND ss_item_sk cmp<= [join] AND ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] AND ss_addr_sk cmp>= [join] AND ss_addr_sk cmp<= [join] | 140 |
| tpcds | tpcds | web_sales | ws_item_sk cmp>= [join] AND ws_item_sk cmp<= [join] AND ws_sold_date_sk cmp>= [join] AND ws_sold_date_sk cmp<= [join] AND ws_bill_addr_sk cmp>= [join] AND ws_bill_addr_sk cmp<= [join] | 127 |
| tpcds | tpcds | web_sales | ws_sold_date_sk cmp>= [join] AND ws_sold_date_sk cmp<= [join] AND ws_bill_customer_sk cmp>= [join] AND ws_bill_customer_sk cmp<= [join] | 79 |
| tpcds | tpcds | store_sales | ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] AND ss_item_sk cmp>= [join] AND ss_item_sk cmp<= [join] AND ss_customer_sk cmp>= [join] AND ss_customer_sk cmp<= [join] AND ss_ticket_number cmp<= AND ss_ticket_number cmp>= [join] AND ss_ticket_number cmp<= [join] | 67 |
| tpcds | tpcds | store_sales | ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] | 64 |
| tpcds | tpcds | store_sales | ss_store_sk cmp>= [join] AND ss_store_sk cmp<= [join] AND ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] | 47 |
| tpcds | tpcds | web_sales | ws_web_site_sk cmp>= [join] AND ws_web_site_sk cmp<= [join] AND ws_sold_date_sk cmp>= [join] AND ws_sold_date_sk cmp<= [join] | 33 |
| tpcds | tpcds | store_sales | ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] AND ss_item_sk cmp>= [join] AND ss_item_sk cmp<= [join] | 32 |
| clickbench | clickbench | hits | MobilePhoneModel cmp!= | 28 |
| clickbench | clickbench | hits | SearchPhrase cmp!= AND EventTime optional(dynamic_topn) [topn] | 16 |
| tpcds | tpcds | store_sales | ss_quantity cmp>= AND ss_quantity cmp<= | 12 |
| tpcds | tpcds | store_sales | ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] AND ss_item_sk cmp>= [join] AND ss_item_sk cmp<= [join] AND ss_store_sk cmp>= [join] AND ss_store_sk cmp<= [join] AND ss_customer_sk cmp>= [join] AND ss_customer_sk cmp<= [join] AND ss_ticket_number cmp<= AND ss_ticket_number cmp>= [join] AND ss_ticket_number cmp<= [join] | 11 |
| tpcds | tpcds | store_sales | ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] AND ss_customer_sk cmp>= [join] AND ss_customer_sk cmp<= [join] | 11 |
| tpcds | tpcds | store_sales | ss_net_profit cmp> AND ss_net_paid cmp> AND ss_quantity cmp> AND ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] | 9 |
| tpcds | tpcds | store_sales | ss_customer_sk cmp>= [join] AND ss_customer_sk cmp<= [join] AND ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] | 8 |
| tpcds | tpcds | store_sales | ss_sold_date_sk cmp>= [join] AND ss_sold_date_sk cmp<= [join] AND ss_ticket_number cmp<= | 8 |


## TPC-H / TPC-DS / ClickBench: filter sets responsible for 3a row groups (top 40)


| benchmark | table | filter_set | scans | scanned_no_rows |
|---|---|---|---|---|
| tpcds | store_sales | ss_store_sk=4 AND (ss_addr_sk IS NULL) | 2 | 32084 |
| clickbench | hits | optional:rowid IN (10541520, 60152823, 60152825, 60152827, 69445322, 70910707, 81981850, 81981851, 97004984, 98655788) [join] AND rowid>=10541520 [join] AND rowid<=98655788 [join] | 1 | 12200 |
| clickbench | hits | optional:rowid IN (10125682, 10221901, 11061732, 12626049, 59477121, 69422307, 70843268, 71055038, 91061613, 98635203) [join] AND rowid>=10125682 [join] AND rowid<=98635203 [join] | 1 | 12197 |
| clickbench | hits | contains(URL, 'google') AND SearchPhrase!='' | 1 | 11620 |
| clickbench | hits | contains(Title, 'Google') AND (NOT contains(URL, '.google.')) AND SearchPhrase!='' | 1 | 9429 |
| clickbench | hits | contains(URL, 'google') | 1 | 9032 |
| clickbench | hits | UserID=435090932899640449 | 1 | 2748 |
| tpcds | store_sales | ss_store_sk=4 | 2 | 2540 |
| clickbench | hits | contains(URL, 'google') AND optional:topn:EventTime<'2013-07-01 23:08:40'::TIMESTAMP [topn] | 1 | 1125 |
| clickbench | hits | SearchPhrase!='' | 5 | 360 |
| tpcds | store_sales | ss_item_sk>=1 [join] AND ss_item_sk<=204000 [join] AND ss_sold_date_sk>=2451541 [join] AND ss_sold_date_sk<=2451547 [join] | 1 | 296 |
| tpcds | web_sales | ws_item_sk>=1 [join] AND ws_item_sk<=204000 [join] AND ws_sold_date_sk>=2451541 [join] AND ws_sold_date_sk<=2451547 [join] | 1 | 148 |
| tpcds | store_sales | ss_item_sk>=118 [join] AND ss_item_sk<=203910 [join] AND ss_sold_date_sk>=2451942 [join] AND ss_sold_date_sk<=2451969 [join] AND ss_addr_sk>=3 [join] AND ss_addr_sk<=1000000 [join] | 1 | 90 |
| tpcds | web_sales | ws_sold_date_sk>=2451576 [join] AND ws_sold_date_sk<=2451604 [join] AND ws_bill_customer_sk>=2 [join] AND ws_bill_customer_sk<=1999992 [join] | 1 | 79 |
| tpcds | web_sales | ws_item_sk>=118 [join] AND ws_item_sk<=203910 [join] AND ws_sold_date_sk>=2451942 [join] AND ws_sold_date_sk<=2451969 [join] AND ws_bill_addr_sk>=3 [join] AND ws_bill_addr_sk<=1000000 [join] | 1 | 76 |
| tpcds | store_sales | ss_sold_date_sk>=2452001 [join] AND ss_sold_date_sk<=2452030 [join] AND ss_item_sk>=1 [join] AND ss_item_sk<=203999 [join] AND ss_customer_sk>=3 [join] AND ss_customer_sk<=1999995 [join] AND ss_ticket_number<=23999996 AND ss_ticket_number>=6 [join] AND ss_ticket_number<=23999975 [join] | 1 | 67 |
| tpcds | web_sales | ws_item_sk>=3 [join] AND ws_item_sk<=203997 [join] AND ws_sold_date_sk>=2451232 [join] AND ws_sold_date_sk<=2451262 [join] | 1 | 61 |
| tpcds | web_sales | ws_item_sk>=1 [join] AND ws_item_sk<=204000 [join] AND ws_sold_date_sk>=2450935 [join] AND ws_sold_date_sk<=2450965 [join] AND ws_bill_addr_sk>=3 [join] AND ws_bill_addr_sk<=1000000 [join] | 1 | 51 |
| tpcds | store_sales | ss_item_sk>=1 [join] AND ss_item_sk<=204000 [join] AND ss_sold_date_sk>=2450935 [join] AND ss_sold_date_sk<=2450965 [join] AND ss_addr_sk>=3 [join] AND ss_addr_sk<=1000000 [join] | 1 | 50 |
| tpcds | store_sales | ss_sold_date_sk>=2451911 [join] AND ss_sold_date_sk<=2451941 [join] | 1 | 48 |
| tpcds | store_sales | ss_store_sk>=1 [join] AND ss_store_sk<=400 [join] AND ss_sold_date_sk>=2451780 [join] AND ss_sold_date_sk<=2451794 [join] | 1 | 42 |
| tpcds | web_sales | ws_web_site_sk>=1 [join] AND ws_web_site_sk<=24 [join] AND ws_sold_date_sk>=2451780 [join] AND ws_sold_date_sk<=2451794 [join] | 1 | 33 |
| clickbench | hits | MobilePhoneModel!='' | 2 | 28 |
| tpcds | store_sales | ss_sold_date_sk>=2451850 [join] AND ss_sold_date_sk<=2451879 [join] AND ss_item_sk>=114 [join] AND ss_item_sk<=203961 [join] | 2 | 18 |
| tpcds | store_sales | ss_sold_date_sk>=2452215 [join] AND ss_sold_date_sk<=2452244 [join] | 1 | 12 |
| tpcds | store_sales | ss_sold_date_sk>=2451423 [join] AND ss_sold_date_sk<=2451452 [join] AND ss_item_sk>=1 [join] AND ss_item_sk<=203998 [join] AND ss_store_sk>=1 [join] AND ss_store_sk<=400 [join] AND ss_customer_sk>=1 [join] AND ss_customer_sk<=1999999 [join] AND ss_ticket_number<=23999996 AND ss_ticket_number>=4 [join] AND ss_ticket_number<=23999968 [join] | 1 | 11 |
| tpcds | store_sales | ss_sold_date_sk>=2451484 [join] AND ss_sold_date_sk<=2451513 [join] AND ss_item_sk>=37 [join] AND ss_item_sk<=203935 [join] | 1 | 11 |
| tpcds | store_sales | ss_net_profit>1.00 AND ss_net_paid>0.00 AND ss_quantity>0 AND ss_sold_date_sk>=2452245 [join] AND ss_sold_date_sk<=2452275 [join] | 1 | 9 |
| tpcds | store_sales | ss_sold_date_sk>=2451180 [join] AND ss_sold_date_sk<=2451269 [join] AND ss_customer_sk>=16 [join] AND ss_customer_sk<=1999997 [join] | 1 | 9 |
| tpcds | store_sales | ss_sold_date_sk>=2451911 [join] AND ss_sold_date_sk<=2452001 [join] AND ss_ticket_number<=23999996 | 1 | 8 |
| tpcds | item | i_manufact_id=977 | 1 | 8 |
| clickbench | hits | SearchPhrase!='' AND optional:topn:EventTime<'2013-07-01 20:00:08'::TIMESTAMP [topn] | 1 | 8 |
| clickbench | hits | SearchPhrase!='' AND optional:topn:EventTime<='2013-07-01 20:00:08'::TIMESTAMP [topn] | 1 | 8 |
| tpcds | store_returns | sr_store_sk>=1 [join] AND sr_store_sk<=400 [join] AND sr_returned_date_sk>=2451780 [join] AND sr_returned_date_sk<=2451794 [join] | 1 | 7 |
| tpcds | store_sales | ss_customer_sk>=74 [join] AND ss_customer_sk<=1999984 [join] AND ss_sold_date_sk>=2452276 [join] AND ss_sold_date_sk<=2452395 [join] | 1 | 7 |
| clickbench | hits | Referer!='' | 1 | 7 |
| tpcds | store_sales | ss_quantity>=41 AND ss_quantity<=60 | 3 | 6 |
| tpcds | store_sales | ss_store_sk>=4 [join] AND ss_store_sk<=396 [join] AND ss_sold_date_sk>=2450906 [join] AND ss_sold_date_sk<=2450996 [join] | 1 | 5 |
| tpch | supplier | (s_comment ~~ '%Customer%Complaints%') | 1 | 3 |
| tpcds | store_sales | ss_quantity>=21 AND ss_quantity<=40 | 3 | 3 |


## Query runtimes


| run | setup | queries | ok | failed | total_s | mean_s | median_s | max_s |
|---|---|---|---|---|---|---|---|---|
| count | point_unsorted | 238 | 238 | 0 | 11863.37 | 49.85 | 40.75 | 256.07 |
| count | point_outliers | 200 | 200 | 0 | 332.37 | 1.66 | 0.91 | 28.41 |
| count | point_sorted | 1000 | 1000 | 0 | 244.74 | 0.24 | 0.11 | 5.3 |
| count | range_seconds_unsorted | 200 | 200 | 0 | 9966.85 | 49.83 | 42.94 | 133.97 |
| count | range_seconds_outliers | 200 | 200 | 0 | 3617.73 | 18.09 | 8.57 | 123.67 |
| count | range_seconds_sorted | 1000 | 1000 | 0 | 313.44 | 0.31 | 0.14 | 7.62 |
| count | range_minutes_unsorted | 229 | 229 | 0 | 10104.15 | 44.12 | 36.4 | 224.97 |
| count | range_minutes_outliers | 200 | 200 | 0 | 176.63 | 0.88 | 0.64 | 27.35 |
| count | range_minutes_sorted | 1000 | 1000 | 0 | 60.04 | 0.06 | 0.04 | 0.5 |
| count | range_hours_unsorted | 200 | 200 | 0 | 11715.39 | 58.58 | 53.91 | 134.49 |
| count | range_hours_outliers | 200 | 200 | 0 | 189.97 | 0.95 | 0.61 | 33.75 |
| count | range_hours_sorted | 1000 | 1000 | 0 | 81.81 | 0.08 | 0.05 | 0.99 |
| count | cardinality_100 | 200 | 199 | 1 | 285.94 | 1.44 | 1.27 | 11.52 |
| count | cardinality_1000 | 200 | 200 | 0 | 283.02 | 1.42 | 1.27 | 6.58 |
| count | cardinality_10000 | 200 | 200 | 0 | 224.91 | 1.12 | 0.96 | 7.42 |
| count | cardinality_100000 | 200 | 200 | 0 | 138.11 | 0.69 | 0.44 | 19.65 |
| count | tpch | 22 | 22 | 0 | 1653.91 | 75.18 | 72.04 | 211.28 |
| count | tpcds | 59 | 59 | 0 | 3411.99 | 57.83 | 34.14 | 481.89 |
| count | clickbench | 43 | 43 | 0 | 879.39 | 20.45 | 10.15 | 92.91 |
| count_misaligned | cardinality_100 | 200 | 200 | 0 | 585.21 | 2.93 | 2.53 | 23.24 |
| count_misaligned | cardinality_1000 | 200 | 200 | 0 | 581.74 | 2.91 | 2.46 | 18.44 |
| count_misaligned | cardinality_10000 | 200 | 200 | 0 | 421.91 | 2.11 | 1.89 | 13.75 |
| count_misaligned | cardinality_100000 | 200 | 200 | 0 | 278.78 | 1.39 | 1.14 | 26.65 |
| count_misaligned | clickbench | 43 | 43 | 0 | 1008.86 | 23.46 | 17.63 | 98.14 |
| count_oldlabels | tpch | 22 | 22 | 0 | 5624.38 | 255.65 | 129.09 | 2205.73 |
| count_oldlabels | tpcds | 66 | 66 | 0 | 5522.21 | 83.67 | 57.53 | 571.54 |
