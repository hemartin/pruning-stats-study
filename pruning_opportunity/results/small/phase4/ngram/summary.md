# N-gram statistic (kind `ngram`, n = 3) for LIKE / contains: ClickBench 1M (small scale)

## Correctness

* `ng200`, counting pass (1 thread): results identical for 43 / 43 queries (row count + order-independent hash); per scan, `total_row_groups`, `pruned_minmax`, `scanned_with_rows`, `incl_optional_with_rows`, `rows_passed`, `rows_passed_incl_optional` equal to the baseline: all scans; invariant / attribution violations: 0
* `ng2000`, counting pass (1 thread): results identical for 43 / 43 queries (row count + order-independent hash); per scan, `total_row_groups`, `pruned_minmax`, `scanned_with_rows`, `incl_optional_with_rows`, `rows_passed`, `rows_passed_incl_optional` equal to the baseline: all scans; invariant / attribution violations: 0
* `ng20000`, counting pass (1 thread): results identical for 43 / 43 queries (row count + order-independent hash); per scan, `total_row_groups`, `pruned_minmax`, `scanned_with_rows`, `incl_optional_with_rows`, `rows_passed`, `rows_passed_incl_optional` equal to the baseline: all scans; invariant / attribution violations: 0
* `ng2000`, check pass (3 threads): identical to the first baseline check for 34 / 43 queries; equal to none of the baseline check runs (baseline_t8,baseline_t8b): q18, q23, q25, q31, q32, q39, q40, q41; baseline check runs differ among themselves on q12, q18, q19, q23, q31, q32, q33, q39, q40, q41 (nondeterministic with threads > 1).
* `ng2000_t8`, check pass (8 threads): identical to the first baseline check for 34 / 43 queries; equal to none of the baseline check runs (baseline_t8,baseline_t8b): q18, q19, q25, q31, q32, q33, q39, q40, q41; baseline check runs differ among themselves on q12, q18, q19, q23, q31, q32, q33, q39, q40, q41 (nondeterministic with threads > 1).

## Ground truth (plain SQL, `rowid // 8192`, pip duckdb on the Phase 1 database)

| query | row groups with a qualifying row (SQL) | baseline `scanned_with_rows` | qualifying rows (SQL) | baseline `rows_passed` | |
|---|---|---|---|---|---|
| q21 | 28 | 28 | 95 | 95 | ok |
| q22 | 1 | 1 | 2 | 2 | ok |
| q23 | 47 | 47 | 217 | 217 | ok |
| q24 | 28 | 28 | 95 | 95 | ok |

In every n-gram configuration, for each pruned row group of q21-q24 scan 0 the ground truth has 0 qualifying rows (checked per partition in `partitions_<config>.csv`: column `pruned_with_rows`).

## Wasted reads of q21-q24 (scan 0) pruned

Baseline = min/max only (`baseline_ng`); "wasted" = scanned, no qualifying row. Exact n = the exact set of distinct byte n-grams per row group (computed with plain SQL), full row groups only (the last, partial row group of 575 rows never gets a statistic; it is wasted in q22 and q23).

| query | baseline wasted / with rows | exact n=2 | exact n=3 | exact n=4 | exact n=5 | `ng200` | `ng2000` | `ng20000` |
|---|---|---|---|---|---|---|---|---|
| q21 | 95 / 28 | 0 (0.0 %) | 55 (57.9 %) | 86 (90.5 %) | 94 (98.9 %) | 36 (37.9 %) | 55 (57.9 %) | 55 (57.9 %) |
| q22 | 122 / 1 | 0 (0.0 %) | 55 (45.1 %) | 86 (70.5 %) | 94 (77.0 %) | 36 (29.5 %) | 55 (45.1 %) | 55 (45.1 %) |
| q23 | 76 / 47 | 42 (55.3 %) | 46 (60.5 %) | 46 (60.5 %) | 46 (60.5 %) | 46 (60.5 %) | 46 (60.5 %) | 46 (60.5 %) |
| q24 | 95 / 28 | 0 (0.0 %) | 55 (57.9 %) | 86 (90.5 %) | 94 (98.9 %) | 36 (37.9 %) | 55 (57.9 %) | 55 (57.9 %) |
| total | 388 / 104 | 42 (10.8 %) | 211 (54.4 %) | 304 (78.4 %) | 328 (84.5 %) | 154 (39.7 %) | 211 (54.4 %) | 211 (54.4 %) |

Consult time per consulted row group (µs, `consult_ns / consultations`, single thread) and engine-side elapsed time per query (ms):

| query | baseline elapsed | `ng200` consult µs/RG; elapsed | `ng2000` consult µs/RG; elapsed | `ng20000` consult µs/RG; elapsed |
|---|---|---|---|---|
| q21 | 39.6 | 5.67; 47.2 | 20.28; 32.2 | 347.43; 91.2 |
| q22 | 34.4 | 5.04; 30.2 | 20.09; 24.7 | 358.17; 90.4 |
| q23 | 46.9 | 3.56; 47.8 | 24.77; 47.4 | 79.17; 70.7 |
| q24 | 59.2 | 5.21; 62.5 | 20.71; 46.6 | 353.08; 110.1 |

## Statistic per row group (122 full row groups per column)

| config | column | built / useless / empty | distinct trigrams min / median / max | budget bits per distinct trigram (median) | stored bytes per RG mean / max | expected FP rate per absent trigram min / median / max | build ms/RG | buffering ms/RG |
|---|---|---|---|---|---|---|---|---|
| `ng200` | title | 122 / 0 / 0 | 1056 / 9945 / 11003 | 1.287 | 1598 / 1600 | 0.000287 / 0.428 / 0.463 | 30.39 | 2.04 |
| `ng200` | url | 122 / 0 / 0 | 13160 / 14171 / 32980 | 0.903 | 1596 / 1600 | 0.529 / 0.565 / 0.814 | 34.49 | 1.60 |
| `ng2000` | title | 122 / 0 / 0 | 1056 / 9945 / 11003 | 12.871 | 15449 / 16000 | 5.72e-17 / 0.000172 / 0.000753 | 39.97 | 1.98 |
| `ng2000` | url | 122 / 0 / 0 | 13160 / 14171 / 32980 | 9.032 | 15999 / 16000 | 0.00142 / 0.00508 / 0.0705 | 166.34 | 1.52 |
| `ng20000` | title | 122 / 0 / 0 | 1056 / 9945 / 11003 | 128.708 | 44845 / 71608 | 5.72e-17 / 5.39e-16 / 5.96e-16 | 12.65 | 2.27 |
| `ng20000` | url | 122 / 0 / 0 | 13160 / 14171 / 32980 | 90.323 | 122936 / 160000 | 7.13e-16 / 7.68e-16 / 5.78e-12 | 43.71 | 1.96 |

Distinct trigram counts of the engine (exact bitmap at n = 3) equal the Python count of the ground truth for every full row group: yes.

## Measured vs. expected pruning

Expected = sum over the wasted full row groups of 1 - eps^k, where eps is the row group's expected false-positive rate per absent n-gram (from the build) and k the number of the literal's trigrams absent from the exact set (independent hash positions assumed).

| config | query | wasted full RGs prunable exactly | pruned | expected | pruned RG with qualifying row |
|---|---|---|---|---|---|
| `ng200` | q21 | 55 | 36 | 36.1 | 0 |
| `ng200` | q22 | 55 | 36 | 36.1 | 0 |
| `ng200` | q23 | 46 | 46 | 46.0 | 0 |
| `ng200` | q24 | 55 | 36 | 36.1 | 0 |
| `ng2000` | q21 | 55 | 55 | 54.9 | 0 |
| `ng2000` | q22 | 55 | 55 | 54.9 | 0 |
| `ng2000` | q23 | 46 | 46 | 46.0 | 0 |
| `ng2000` | q24 | 55 | 55 | 54.9 | 0 |
| `ng20000` | q21 | 55 | 55 | 55.0 | 0 |
| `ng20000` | q22 | 55 | 55 | 55.0 | 0 |
| `ng20000` | q23 | 46 | 46 | 46.0 | 0 |
| `ng20000` | q24 | 55 | 55 | 55.0 | 0 |
