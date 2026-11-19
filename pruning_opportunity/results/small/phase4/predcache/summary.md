# Predicate cache: ClickBench 1M (small scale)

## Correctness

* Counting passes (1 thread), result (row count + order-independent hash) vs. `baseline_pc` cold pass: `baseline_pc` cold 43/43; `baseline_pc` warm 43/43; `ng2000_pc` cold 43/43; `ng2000_pc` warm 43/43; `predcache` cold 43/43; `predcache` warm 43/43; `predcache_ng2000` cold 43/43; `predcache_ng2000` warm 43/43; `predcache_sub` cold 43/43; `predcache_sub` warm 43/43; `predcache_sub_ng2000` cold 43/43; `predcache_sub_ng2000` warm 43/43.
* Counter invariants (`total = pruned + scanned_no_rows + scanned_with_rows + partial_no_rows + not_reached`, `pruned = pruned_minmax + pruned_additional + pruned_predicate_cache`) per scan: 0 violations.
* Cache merge conflicts (a row group recorded once as "no rows" and once as "has rows" for the same key): 0.
* `ng2000_pc`: `scanned_with_rows`, `rows_passed`, `total_row_groups` per query equal to the baseline cold pass: all 86 query executions
* `predcache`: `scanned_with_rows`, `rows_passed`, `total_row_groups` per query equal to the baseline cold pass: all 86 query executions
* `predcache_ng2000`: `scanned_with_rows`, `rows_passed`, `total_row_groups` per query equal to the baseline cold pass: all 86 query executions
* `predcache_sub`: `scanned_with_rows`, `rows_passed`, `total_row_groups` per query equal to the baseline cold pass: all 86 query executions
* `predcache_sub_ng2000`: `scanned_with_rows`, `rows_passed`, `total_row_groups` per query equal to the baseline cold pass: all 86 query executions
* Multi-threaded check passes (8 threads, cold + warm pass in one session) vs. 6 baseline samples (every pass of the baseline check runs `baseline_pc_t8,baseline_pc_t8b,baseline_t8,baseline_t8b`); the baseline samples disagree among themselves on q12, q18, q19, q23, q25, q31, q32, q33, q39, q40, q41 (nondeterministic with threads > 1: ties in `ORDER BY ... LIMIT`, `LIMIT` without `ORDER BY`):
  * `baseline_pc_t8` cold pass: identical to the first baseline run 43/43, to one of the baseline runs 43/43; equal to none: none
  * `baseline_pc_t8` warm pass: identical to the first baseline run 33/43, to one of the baseline runs 43/43; equal to none: none
  * `ng2000_pc_t8` cold pass: identical to the first baseline run 35/43, to one of the baseline runs 36/43; equal to none: q18, q19, q32, q33, q39, q40, q41 (deterministic among them: none)
  * `ng2000_pc_t8` warm pass: identical to the first baseline run 32/43, to one of the baseline runs 35/43; equal to none: q18, q19, q23, q32, q33, q39, q40, q41 (deterministic among them: none)
  * `predcache_t8` cold pass: identical to the first baseline run 35/43, to one of the baseline runs 37/43; equal to none: q18, q19, q33, q39, q40, q41 (deterministic among them: none)
  * `predcache_t8` warm pass: identical to the first baseline run 33/43, to one of the baseline runs 36/43; equal to none: q18, q19, q32, q33, q39, q40, q41 (deterministic among them: none)
  * `predcache_ng2000_t8` cold pass: identical to the first baseline run 35/43, to one of the baseline runs 37/43; equal to none: q18, q19, q32, q39, q40, q41 (deterministic among them: none)
  * `predcache_ng2000_t8` warm pass: identical to the first baseline run 33/43, to one of the baseline runs 36/43; equal to none: q18, q19, q23, q33, q39, q40, q41 (deterministic among them: none)
  * `predcache_sub_t8` cold pass: identical to the first baseline run 33/43, to one of the baseline runs 36/43; equal to none: q18, q19, q23, q33, q39, q40, q41 (deterministic among them: none)
  * `predcache_sub_t8` warm pass: identical to the first baseline run 33/43, to one of the baseline runs 36/43; equal to none: q18, q19, q31, q32, q39, q40, q41 (deterministic among them: none)
  * `predcache_sub_ng2000_t8` cold pass: identical to the first baseline run 34/43, to one of the baseline runs 37/43; equal to none: q18, q19, q33, q39, q40, q41 (deterministic among them: none)
  * `predcache_sub_ng2000_t8` warm pass: identical to the first baseline run 32/43, to one of the baseline runs 37/43; equal to none: q19, q32, q33, q39, q40, q41 (deterministic among them: none)

## Totals over the 43 queries (counting pass, 1 thread)

| config | pass | row groups | pruned | of which min/max | of which n-gram stat | of which predicate cache | scanned, no rows (wasted) | scanned with rows | cache entries / bytes at end of pass |
|---|---|---|---|---|---|---|---|---|---|
| baseline | cold | 5535 | 822 | 822 | 0 | 0 | 627 | 4086 |  /  |
| baseline | warm | 5535 | 822 | 822 | 0 | 0 | 627 | 4086 |  /  |
| ng2000 | cold | 5535 | 1033 | 822 | 211 | 0 | 416 | 4086 |  /  |
| ng2000 | warm | 5535 | 1033 | 822 | 211 | 0 | 416 | 4086 |  /  |
| predcache | cold | 5535 | 917 | 822 | 0 | 95 | 532 | 4086 | 16 / 2031 |
| predcache | warm | 5535 | 1216 | 822 | 0 | 394 | 233 | 4086 | 16 / 2031 |
| predcache+ng2000 | cold | 5535 | 1073 | 822 | 156 | 95 | 376 | 4086 | 16 / 2031 |
| predcache+ng2000 | warm | 5535 | 1216 | 822 | 0 | 394 | 233 | 4086 | 16 / 2031 |
| predcache_subset | cold | 5535 | 1012 | 822 | 0 | 190 | 437 | 4086 | 16 / 2031 |
| predcache_subset | warm | 5535 | 1216 | 822 | 0 | 394 | 233 | 4086 | 16 / 2031 |
| predcache_subset+ng2000 | cold | 5535 | 1113 | 822 | 101 | 190 | 336 | 4086 | 16 / 2031 |
| predcache_subset+ng2000 | warm | 5535 | 1216 | 822 | 0 | 394 | 233 | 4086 | 16 / 2031 |

## Cold pass, per query (q01..q43 in execution order)

Per configuration: pruned (of which by the predicate cache) / scanned, no rows (wasted) / scanned with rows. `total` = row groups scanned or pruned (sum over the query's table scans; equal in all configurations).

| query | total | baseline | ng2000 | predcache | predcache+ng2000 | predcache_subset | predcache_subset+ng2000 |
|---|---|---|---|---|---|---|---|
| q01 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q02 | 123 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 |
| q03 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q04 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q05 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q06 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q07 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q08 | 123 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 |
| q09 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q10 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q11 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q12 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q13 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q14 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q15 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q16 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q17 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q18 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q19 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q20 | 123 | 117 (0) / 6 / 0 | 117 (0) / 6 / 0 | 117 (0) / 6 / 0 | 117 (0) / 6 / 0 | 117 (0) / 6 / 0 | 117 (0) / 6 / 0 |
| q21 | 123 | 0 (0) / 95 / 28 | 55 (0) / 40 / 28 | 0 (0) / 95 / 28 | 55 (0) / 40 / 28 | 0 (0) / 95 / 28 | 55 (0) / 40 / 28 |
| q22 | 123 | 0 (0) / 122 / 1 | 55 (0) / 67 / 1 | 0 (0) / 122 / 1 | 55 (0) / 67 / 1 | 95 (95) / 27 / 1 | 95 (95) / 27 / 1 |
| q23 | 123 | 0 (0) / 76 / 47 | 46 (0) / 30 / 47 | 0 (0) / 76 / 47 | 46 (0) / 30 / 47 | 0 (0) / 76 / 47 | 46 (0) / 30 / 47 |
| q24 | 246 | 0 (0) / 211 / 35 | 55 (0) / 156 / 35 | 95 (95) / 116 / 35 | 95 (95) / 116 / 35 | 95 (95) / 116 / 35 | 95 (95) / 116 / 35 |
| q25 | 246 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 |
| q26 | 123 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 |
| q27 | 123 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 |
| q28 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q29 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q30 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q31 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q32 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q33 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q34 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q35 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q36 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q37 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q38 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q39 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q40 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q41 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q42 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q43 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| **sum** | 5535 | 822 (0) / 627 / 4086 | 1033 (0) / 416 / 4086 | 917 (95) / 532 / 4086 | 1073 (95) / 376 / 4086 | 1012 (190) / 437 / 4086 | 1113 (190) / 336 / 4086 |

## Warm pass, per query (q01..q43 in execution order)

Per configuration: pruned (of which by the predicate cache) / scanned, no rows (wasted) / scanned with rows. `total` = row groups scanned or pruned (sum over the query's table scans; equal in all configurations).

| query | total | baseline | ng2000 | predcache | predcache+ng2000 | predcache_subset | predcache_subset+ng2000 |
|---|---|---|---|---|---|---|---|
| q01 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q02 | 123 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 |
| q03 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q04 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q05 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q06 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q07 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q08 | 123 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 | 3 (0) / 0 / 120 |
| q09 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q10 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q11 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q12 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q13 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q14 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q15 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q16 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q17 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q18 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q19 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q20 | 123 | 117 (0) / 6 / 0 | 117 (0) / 6 / 0 | 123 (6) / 0 / 0 | 123 (6) / 0 / 0 | 123 (6) / 0 / 0 | 123 (6) / 0 / 0 |
| q21 | 123 | 0 (0) / 95 / 28 | 55 (0) / 40 / 28 | 95 (95) / 0 / 28 | 95 (95) / 0 / 28 | 95 (95) / 0 / 28 | 95 (95) / 0 / 28 |
| q22 | 123 | 0 (0) / 122 / 1 | 55 (0) / 67 / 1 | 122 (122) / 0 / 1 | 122 (122) / 0 / 1 | 122 (122) / 0 / 1 | 122 (122) / 0 / 1 |
| q23 | 123 | 0 (0) / 76 / 47 | 46 (0) / 30 / 47 | 76 (76) / 0 / 47 | 76 (76) / 0 / 47 | 76 (76) / 0 / 47 | 76 (76) / 0 / 47 |
| q24 | 246 | 0 (0) / 211 / 35 | 55 (0) / 156 / 35 | 95 (95) / 116 / 35 | 95 (95) / 116 / 35 | 95 (95) / 116 / 35 | 95 (95) / 116 / 35 |
| q25 | 246 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 | 59 (0) / 117 / 70 |
| q26 | 123 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 | 89 (0) / 0 / 34 |
| q27 | 123 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 | 54 (0) / 0 / 69 |
| q28 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q29 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q30 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q31 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q32 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q33 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q34 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q35 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q36 | 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 | 0 (0) / 0 / 123 |
| q37 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q38 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q39 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q40 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q41 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q42 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| q43 | 123 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 | 71 (0) / 0 / 52 |
| **sum** | 5535 | 822 (0) / 627 / 4086 | 1033 (0) / 416 / 4086 | 1216 (394) / 233 / 4086 | 1216 (394) / 233 / 4086 | 1216 (394) / 233 / 4086 | 1216 (394) / 233 / 4086 |

## Cache size and cost (counting pass, 1 thread)

| config | entries after cold / warm pass | bytes after cold / warm pass | lookup ms (cold / warm, all queries) | record ms | static re-check ms |
|---|---|---|---|---|---|
| predcache | 16 / 16 | 2031 / 2031 | 0.674 / 0.675 | 0.051 / 0.043 | 0.025 / 0.023 |
| predcache+ng2000 | 16 / 16 | 2031 / 2031 | 0.657 / 0.644 | 0.051 / 0.048 | 0.024 / 0.022 |
| predcache_subset | 16 / 16 | 2031 / 2031 | 0.614 / 0.643 | 0.051 / 0.045 | 0.022 / 0.022 |
| predcache_subset+ng2000 | 16 / 16 | 2031 / 2031 | 0.743 / 0.648 | 0.05 / 0.044 | 0.025 / 0.022 |

Cache keys (static non-optional pushed-down conjunctions of cacheable scans; `#<n>` = storage column index of `hits`) and the queries using them:

* `#40!=0`: q02, q08
* `#34!=''`: q11, q12
* `#39!=''`: q13, q14, q15, q25, q26, q27, q31, q32
* `#9=435090932899640449`: q20
* `contains(#13, 'google')`: q21, q24
* `contains(#13, 'google') AND #39!=''`: q22
* `contains(#2, 'Google') AND (NOT contains(#13, '.google.')) AND #39!=''`: q23
* `#13!=''`: q28
* `#14!=''`: q29
* `#6=62 AND #13!='' AND #15=0 AND #61=0`: q37
* `#2!='' AND #6=62 AND #15=0 AND #61=0`: q38
* `#6=62 AND #15=0 AND #52!=0 AND #53=0`: q39
* `#6=62 AND #15=0`: q40
* `#6=62 AND #15=0 AND #102=3594120000172545465`: q41
* `#6=62 AND #15=0 AND #61=0 AND #103=2868770270353813622`: q42
* `#6=62 AND #15=0 AND #61=0`: q43

## Query time (engine-side elapsed ms; 8 threads; 3 session(s) per config (baseline_pctime_b, baseline_pctime_c, baseline_pctime_d), each: ingest, then the 43 queries 4 times round-robin; round 1 = cold cache, rounds 2-4 = warm; value = median of the 9 warm executions)

| query | baseline | ng2000 | predcache | predcache+ng2000 | speedup ng2000 | speedup predcache | speedup predcache+ng2000 |
|---|---|---|---|---|---|---|---|
| q01 | 1.00 | 0.95 | 1.07 | 1.05 | 1.05 | 0.93 | 0.95 |
| q02 | 1.21 | 1.10 | 1.23 | 1.09 | 1.10 | 0.98 | 1.11 |
| q03 | 1.34 | 1.45 | 1.37 | 1.37 | 0.92 | 0.98 | 0.98 |
| q04 | 1.55 | 1.48 | 1.54 | 1.43 | 1.05 | 1.01 | 1.09 |
| q05 | 7.36 | 7.58 | 7.47 | 7.83 | 0.97 | 0.99 | 0.94 |
| q06 | 9.02 | 9.53 | 9.32 | 9.01 | 0.95 | 0.97 | 1.00 |
| q07 | 1.06 | 1.08 | 1.04 | 1.14 | 0.98 | 1.02 | 0.93 |
| q08 | 1.42 | 1.70 | 1.71 | 1.50 | 0.84 | 0.83 | 0.95 |
| q09 | 9.68 | 10.49 | 10.17 | 9.65 | 0.92 | 0.95 | 1.00 |
| q10 | 16.39 | 17.00 | 16.91 | 16.68 | 0.96 | 0.97 | 0.98 |
| q11 | 4.27 | 4.25 | 4.25 | 4.22 | 1.00 | 1.00 | 1.01 |
| q12 | 4.72 | 4.57 | 4.68 | 4.60 | 1.03 | 1.01 | 1.03 |
| q13 | 4.88 | 5.25 | 5.29 | 4.72 | 0.93 | 0.92 | 1.03 |
| q14 | 6.97 | 6.93 | 7.28 | 6.70 | 1.01 | 0.96 | 1.04 |
| q15 | 5.46 | 5.35 | 6.02 | 5.32 | 1.02 | 0.91 | 1.03 |
| q16 | 8.00 | 8.25 | 8.04 | 8.07 | 0.97 | 1.00 | 0.99 |
| q17 | 13.54 | 13.65 | 13.49 | 13.38 | 0.99 | 1.00 | 1.01 |
| q18 | 12.67 | 13.09 | 13.14 | 12.66 | 0.97 | 0.96 | 1.00 |
| q19 | 29.52 | 26.37 | 25.02 | 25.34 | 1.12 | 1.18 | 1.16 |
| q20 | 0.84 | 0.82 | 0.88 | 0.84 | 1.03 | 0.96 | 1.00 |
| q21 | 9.86 | 8.45 | 4.41 | 4.11 | 1.17 | 2.24 | 2.40 |
| q22 | 8.41 | 7.07 | 1.99 | 1.84 | 1.19 | 4.23 | 4.56 |
| q23 | 14.47 | 12.33 | 10.74 | 10.47 | 1.17 | 1.35 | 1.38 |
| q24 | 20.07 | 18.56 | 15.36 | 14.78 | 1.08 | 1.31 | 1.36 |
| q25 | 4.47 | 4.51 | 4.78 | 4.54 | 0.99 | 0.94 | 0.99 |
| q26 | 1.71 | 1.83 | 1.80 | 1.70 | 0.94 | 0.95 | 1.01 |
| q27 | 3.47 | 3.34 | 3.19 | 3.16 | 1.04 | 1.09 | 1.10 |
| q28 | 7.08 | 7.74 | 7.91 | 7.39 | 0.91 | 0.89 | 0.96 |
| q29 | 220.34 | 228.15 | 225.11 | 222.48 | 0.97 | 0.98 | 0.99 |
| q30 | 7.78 | 7.27 | 7.76 | 7.53 | 1.07 | 1.00 | 1.03 |
| q31 | 5.73 | 6.33 | 6.38 | 6.72 | 0.91 | 0.90 | 0.85 |
| q32 | 6.96 | 7.30 | 7.35 | 7.42 | 0.95 | 0.95 | 0.94 |
| q33 | 38.76 | 40.72 | 40.43 | 39.82 | 0.95 | 0.96 | 0.97 |
| q34 | 32.59 | 35.14 | 34.61 | 32.70 | 0.93 | 0.94 | 1.00 |
| q35 | 36.01 | 37.19 | 41.45 | 35.05 | 0.97 | 0.87 | 1.03 |
| q36 | 11.04 | 10.84 | 11.58 | 10.52 | 1.02 | 0.95 | 1.05 |
| q37 | 16.21 | 17.43 | 17.94 | 16.30 | 0.93 | 0.90 | 0.99 |
| q38 | 10.51 | 10.24 | 10.48 | 9.96 | 1.03 | 1.00 | 1.06 |
| q39 | 5.70 | 6.06 | 6.66 | 5.65 | 0.94 | 0.86 | 1.01 |
| q40 | 43.29 | 43.99 | 45.48 | 43.53 | 0.98 | 0.95 | 0.99 |
| q41 | 4.10 | 3.85 | 4.29 | 3.96 | 1.07 | 0.96 | 1.04 |
| q42 | 4.49 | 4.42 | 4.88 | 4.59 | 1.02 | 0.92 | 0.98 |
| q43 | 6.05 | 6.01 | 6.92 | 6.24 | 1.01 | 0.88 | 0.97 |
| **sum** | 660.0 | 669.7 | 661.4 | 637.0 | 0.99 | 1.00 | 1.04 |

## Notes

* Configurations: `baseline` = min/max only; `ng2000` = 3-gram statistic, 2000 words, on `hits.URL` and `hits.Title`;
  `predcache` = `PRUNING_PREDICATE_CACHE=1` (exact whole-conjunction keys); `predcache_subset` =
  `PRUNING_PREDICATE_CACHE=subset` (an entry whose leaf set is a subset of the scan's leaf set may also prune).
  Every configuration is ONE CLI process: fresh DB, COPY of the 1M rows, CHECKPOINT, q01..q43 (cold pass), q01..q43
  again (warm pass, tags `#p2`). The cache is empty at process start.
* Order of checks per row group: min/max zonemap, then the predicate cache, then the selective (n-gram) statistic. A
  row group that min/max prunes is attributed to min/max in every pass; in the warm pass the cache answers before the
  n-gram statistic is consulted, hence `of which n-gram stat` = 0 in the warm pass of `predcache+ng2000`.
* The 233 row groups that stay "scanned, no rows" in the warm pass are all in the second (late-materialization)
  scans of q24 (116) and q25 (117): their only filters are runtime join filters on `rowid` (no static filter -> no
  key; uncacheable by design). The first scans of q25-q27 have the key `SearchPhrase <> ''`, whose row groups all
  contain rows; their extra pruning comes from top-N filters (optional, not part of the key).
* Subset lookups (`predcache_subset`) add pruning only in the cold pass: q22 (`contains(URL,'google') AND
  SearchPhrase <> ''`) is pruned by q21's entry `contains(URL,'google')` (95 row groups). In the warm pass every key
  has its own entry, so subset and exact keys prune the same 394 row groups.
* Timing: 3 sessions per configuration (`_b`, `_c`, `_d`, configurations interleaved), 8 threads, on a machine shared
  with another agent's work; per-session totals over all 43 queries vary between 640 and 735 ms for the same
  configuration, so differences below ~10 % are noise. Only q21-q24 change beyond that. (An earlier timing series,
  run before a bug fix — see the README — showed the same picture.)
