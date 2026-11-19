# Pruning opportunity study (Phase 1)

How many partitions (row groups of 8,192 rows) does **stock DuckDB v1.4.4** prune with its min/max zonemaps, and how
many does it scan although no row in them qualifies (i.e. a better partition summary could have pruned them)?

## Small-scale results (summary)

Full tables: `results/small/summary.md` (Markdown) and CSVs in `results/small/`: `micro_summary.csv` (16 setups,
sums and per-query averages), `established_queries.csv` (one row per TPC-H/TPC-DS/ClickBench query, summed over
scans, with `pruned_by_predicate`), `benchmark_totals.csv`, `scan_detail.csv` (per query × scan, incl. filter
set), `filter_detail.csv` (per query × scan × filter leaf: `pruned_first`, `prunable_alone`),
`pruned_by_predicate.csv`, `wasted_by_filterset.csv` / `wasted_by_filter_shape.csv` (filter sets responsible for 3a),
`runtimes.csv`, `ground_truth*.{csv,md}`, `result_check.{csv,md}`, `invariants.txt`.

Data: micro 10M rows (1,221 row groups), TPC-H SF1, TPC-DS SF1, ClickBench first 1,000,000 lines of `hits.csv`
(999,977 rows loaded – presumably quoted fields spanning lines). All 16,164 queries ran without error/timeout.

Microbenchmarks (per query averages over 1,000 queries; total = 1,221 row groups):

| setup | pruned | scanned, no qualifying row (3a) | scanned with rows (3b) | % pruned | % of scanned that is 3a |
|---|---|---|---|---|---|
| point_unsorted | 0 | 1,221.0 | 0.008 | 0 | 100 |
| point_outliers | 720.7 | 500.3 | 0.008 | 59.0 | 100 |
| point_sorted | 1,220.0 | 0.99 | 0.008 | 99.9 | 99.2 |
| range_seconds_unsorted | 0 | 1,217.1 | 3.9 | 0 | 99.7 |
| range_seconds_outliers | 720.7 | 499.3 | 1.0 | 59.0 | 99.8 |
| range_seconds_sorted | 1,220.0 | 0.013 | 0.99 | 99.9 | 1.3 |
| range_minutes_unsorted | 0 | 1,010.5 | 210.5 | 0 | 82.8 |
| range_minutes_outliers | 720.7 | 499.3 | 1.0 | 59.0 | 99.8 |
| range_minutes_sorted | 1,220.0 | 0 | 1.0 | 99.9 | 0 |
| range_hours_unsorted | 0 | 0.013 | 1,221.0 | 0 | 0 |
| range_hours_outliers | 719.0 | 499.3 | 2.7 | 58.9 | 99.5 |
| range_hours_sorted | 1,218.3 | 0 | 2.7 | 99.8 | 0 |
| cardinality_100 | 26.7 | 583.7 | 610.6 | 2.2 | 48.9 |
| cardinality_1000 | 1.4 | 609.4 | 610.2 | 0.1 | 50.0 |
| cardinality_10000 | 0.14 | 728.8 | 492.1 | 0.0 | 59.7 |
| cardinality_100000 | 0.77 | 1,128.1 | 92.2 | 0.1 | 92.5 |

Sanity vs. the paper: unsorted → min/max prunes nothing; sorted → everything but the 1–3 row groups containing the
value/range; outliers: the 500 row groups that contain one of the outliers (one every 10,000 rows) are never
pruned, the other 721 always are; cardinality: min/max prunes ~nothing (every row group spans ~[0, N)), while about
half of the row groups (by construction a random half of the ids per row group) contain no matching row. Note that at
10M rows a random timestamp is ~100× less likely to exist than at 1B rows, so point queries mostly return 0 rows.

Established benchmarks (sums over all queries and scans):

| benchmark | queries | scans | row groups | pruned | 3a | 3b | 3a incl. optional filters | % pruned | % of scanned that is 3a |
|---|---|---|---|---|---|---|---|---|---|
| TPC-H SF1 | 22 | 86 | 18,699 | 4 | 0 | 18,695 | 0 | 0.02 | 0 |
| TPC-DS SF1 | 99 | 764 | 67,240 | 16,423 | 578 | 50,239 | 740 | 24.4 | 1.1 |
| ClickBench 1M | 43 | 44 | 5,412 | 822 | 627 | 3,963 | 761 | 15.2 | 13.7 |

* TPC-H: data is in orderkey order and dates are random per order, so no date predicate can prune and every row
  group that is scanned has qualifying rows; only Q15/Q18 prune 1–3 row groups (key predicates).
* TPC-DS: pruning mostly by `*_sold_date_sk` ranges (static, derived from `date_dim` via statistics) and join
  filters (`origin=join`, incl. optional join IN lists); 3a comes from point predicates on unclustered keys
  (`ss_customer_sk=…` 349, `cs_item_sk=…` 68), `store_sales` time/household ranges (q88/q96), `IS NULL` expression
  filters (q76). Including optional filters (IN lists, OR clauses), 3a rises to 740 (q32, q37, q82).
* ClickBench: `CounterID=62` prunes 71/123 (q37–q43), `UserID=…` 117 (q20), top-N filters prune 54–89 (q25–q27);
  3a mostly from `contains(URL,'google')`-style expression filters (q21–q24) and from late-materialization rowid
  scans (q24/q25: `RowGroup::CheckZonemap` never prunes on rowid filters; only vectors are skipped).
  `SELECT COUNT(*) FROM hits` (q01) has no scan at all (answered from statistics: `bound − plan scans = 1`).
* No query produced an EMPTY_RESULT plan, and no scan stopped early (all LIMITs are top-N); segment-level zonemap
  skipping never triggered (with 8,192-row row groups each column segment covers the whole row group).

### Runtimes at small scale (per query, single thread, `results/small/runtimes.csv`)

Run `time` (counting off, results discarded): unsorted/outlier micro point/range queries 15–55 ms (mean),
sorted 2 ms, cardinality 26–43 ms; TPC-H 22 queries 16.5 s total (max 8.7 s, cold cache), TPC-DS 99 queries 38 s,
ClickBench 43 queries 19 s. Counting run (results hashed, so output-bound for large result sets): micro 23 min
in total (`cardinality_100` alone 12 min because of 50k result rows per query), TPC-H 9.4 s, TPC-DS 28.6 s, ClickBench
5.2 s. Counting on vs. off with identical output handling (`count` vs `nocount`): within ±5 % for all setups that
scan most row groups, up to +40 % for the 2–3 ms sorted-data queries (fixed per-query cost of building and
writing the JSON lines), TPC-H +18 %.

**Large-scale extrapolation** (×100 rows, single thread, counting, results discarded): unsorted micro setups
~3.5–5.5 s/query → ~1–1.5 h per setup (8 setups), outlier setups ~1.5 s/query → ~25 min each, sorted setups
minutes; ≈ 12–15 h for all 16 micro setups. TPC-H SF100 ≈ 15–30 min, TPC-DS SF100 ≈ 1 h (both more if joins
spill at `memory_limit=6GB`), ClickBench 100M ≈ 10–30 min. Loading single-threaded: ~5–10 min per 1B-row micro CSV,
~1–1.5 h each for TPC-H/TPC-DS SF100 and ClickBench (`LOAD_THREADS` can speed this up; `ground_truth.py` then reports
whether row groups are still exactly 8,192-row aligned). DB sizes ≈ 100× small: ~32 GB micro, ~32 GB TPC-H,
~34 GB TPC-DS, ~22 GB ClickBench.


## Files

| Path | Purpose |
|---|---|
| `patches/duckdb-v1.4.4-pruning-counters.patch` | Instrumentation of pristine DuckDB v1.4.4 (tracked) |
| `build_stock.sh` | Clones v1.4.4 into `stock/duckdb` (gitignored), applies the patch, builds release with ninja, `-j6`, `tpch`+`tpcds` built in, `OVERRIDE_GIT_DESCRIBE=v1.4.4`, no unit tests |
| `harness/common.py` | Paths, setups (16 micro + TPC-H/TPC-DS/ClickBench), SQL-file parsing (DDL/COPY taken from `experiments/sql/...`) |
| `harness/gen_queries.py` | Corrected cardinality query files → `queries/sql_queries_cardinality_<N>.sql` |
| `harness/prepare_small.py` | Small-scale inputs in `data/small/` (micro symlinks, TPC-H/DS SF1 CSV export, ClickBench head 1M) |
| `harness/build_db.py` | Persistent DBs `db/<scale>/<name>.db` (ROW_GROUP_SIZE 8192, threads 1, memory_limit 6GB, temp dir `db/tmp`) |
| `harness/run.py` | Query runner: batches of queries per CLI process, per-query timeout, crash isolation, resumable |
| `harness/aggregate.py` | Result tables → `results/<scale>/` |
| `harness/compare_results.py` | Result equality: counting on vs off; vs pip `duckdb` |
| `harness/ground_truth.py` | Independent per-row-group ground truth with plain SQL (pip `duckdb`) |
| `harness/compare_threads.py` | Counters of two counting runs (e.g. threads 1 vs 12) per query and scan |
| `run_small.sh`, `run_large.sh` | End-to-end pipelines |
| `queries/` | Generated cardinality queries (1,000 each, seed 20260101+N, ids uniform in `[0, N)`) |
| `results/small/` | Small-scale result tables (tracked); raw logs in `results/raw/` (gitignored) |

## How to run

Small scale (everything, ~1.5 h on this machine; resumable, re-run to continue):

```bash
cd pruning_opportunity
./build_stock.sh            # once (~30-40 min at -j6)
./run_small.sh              # data prep, DB build, 3 runs (count / nocount / time), checks, tables
```

Large scale (after the CSVs exist in `data/large/{micro,tpch,tpcds}/`; ClickBench from the repo-root `hits.csv`):

```bash
cd pruning_opportunity
STEP=db  ./run_large.sh     # build db/large/*.db (single-threaded load like the paper; LOAD_THREADS=N to change)
STEP=run ./run_large.sh     # counting pass, threads=1, results discarded, per-query timeout TIMEOUT=7200 s
SETUPS=tpch,point_sorted STEP=run ./run_large.sh   # subsets; finished queries are skipped on re-run
../.venv/bin/python harness/aggregate.py --scale large
../.venv/bin/python harness/ground_truth.py --scale large --micro-sample 50 --setups micro   # optional, slow
```

Individual steps take `--scale small|large`; `run.py --help` lists all options (`--setups`, `--timeout`,
`--batch`, `--limit`, `--sample`, `--count`, `--hash`, `--label`). Timing runs use the same binary without
`DUCKDB_PRUNING_STATS` (`run.py --scale large --label time --threads 12`).

## Instrumentation design

Enabled only if `DUCKDB_PRUNING_STATS=<file>` is set (checked once via a function-local static). Otherwise no state
is created; the only cost is a null-pointer check per row group and per scanned vector (`CollectionScanState::
pruning_local`). Changed files: `row_group.cpp` (hooks), `table_scan.cpp` (per-scan/per-thread state),
`scan_state.hpp/.cpp`, `row_group.hpp` (friend), `client_context.cpp` (registers a `ClientContextState`),
`executor.cpp` (plan summary), `duck_table_entry.cpp` (bound table references), new `pruning_stats.{hpp,cpp}`.

* **Per scan** (`DuckTableScanInitGlobal`, i.e. once per `PhysicalTableScan` execution): a `PruningScanStats`
  with one atomic record per row group (indexed by the row group's segment-tree index; `total_row_groups` = number
  of row groups of the table). Per thread (`InitLocalState`) a `PruningScanLocal`. Thread-safe: per-row-group
  atomics, per-query registry under a mutex, output under a global mutex.
* **Pruned**: `RowGroup::InitializeScan[WithOffset]` when `CheckZonemap` returns false. Attribution: the pushed-down
  filters are flattened over AND into *leaves*; for a pruned row group every leaf is checked alone against the row
  group statistics. `pruned_first` = the first leaf (in the engine's check order, i.e. by scan column) that proves
  "no match" (sums to `pruned` minus `pruned_unattributed`, which never occurred); `prunable_alone` = every leaf that
  alone could prune it.
* **Static vs dynamic**: dynamic join filters are merged into the scan's filters at runtime
  (`DynamicTableFilterSet::GetFinalTableFilters` copies the static filter first and ANDs join filters after it);
  leaves are labelled `origin = static | join | topn` (top-N filters are `OptionalFilter(DynamicFilter)` pushed at
  plan time). The rendering of a dynamic filter is its value at the end of the query.
* **Scanned**: row group passed `CheckZonemap` and was entered. In `RowGroup::TemplatedScan` every vector (2,048
  rows) reports rows processed and rows that survived *all filters applied to rows*; vectors skipped by
  `CheckZonemapSegments` (segment-level zonemaps) are counted separately. At query end each row group is classified:
  * `scanned_with_rows` (3b): ≥1 qualifying row (includes `scanned_with_rows_partial`: early stop after a hit);
  * `scanned_no_rows` (3a): all vectors processed or segment-skipped, zero qualifying rows;
    sub-counts `scanned_no_rows_all_segments_skipped` (every vector skipped by segment zonemaps, no data read) and
    `..._some_segments_skipped`;
  * `partial_no_rows`: entered but not finished (query stopped early), no qualifying row so far;
  * `not_reached`: never handed to the scan (LIMIT / early termination, or the scan was cut short);
  * invariant: `total = pruned + scanned_no_rows + scanned_with_rows + partial_no_rows + not_reached`.
  A scan without pushed-down filters (`has_filters=false`) puts every completed row group in 3b.
* **Which filters are "applied to rows"**: constant comparisons (incl. join min/max filters), IS [NOT] NULL, OR of
  comparisons when not optional, expression filters, struct filters. `OptionalFilter`s (IN lists with >1 non-dense
  value, OR-of-comparison clauses, join IN lists from small hash tables, top-N thresholds) are **zonemap-only**:
  DuckDB never evaluates them in the scan (the real predicate is evaluated by a filter operator above, or not at all
  for join/top-N). Hence `rows_passed` / 3a / 3b refer to the non-optional filters. Additionally, in counting mode
  the optional filters' children are evaluated on the surviving rows (ExpressionExecutor), giving
  `rows_passed_incl_optional` and `incl_optional_{with_rows,no_rows,partial_no_rows}` – the opportunity for a
  better summary on IN/OR/join-IN/top-N predicates. Top-N thresholds change during the scan, so that variant uses
  the threshold valid at the time the row group was scanned.
* Filters that are not pushed into the scan (multi-column predicates, LIKE '%x%', functions not pushable) do not
  count: a row group with rows passing the pushed filters but failing such predicates is 3b.
* **Plan-time removal**: each query record lists `bound_tables` (base-table references bound), `plan_scan_tables`
  (table scans in the physical plan), `plan_empty_results` (EMPTY_RESULT operators, e.g. predicates proven false
  from table statistics) and `n_scans` (scans that were initialised). Aggregated as
  `removed_scans = bound − plan scans` and `unexecuted_plan_scans = plan scans − executed scans`.
* **Not instrumented**: index (ART) scans (the benchmark tables have no indexes), transaction-local storage,
  `TABLESAMPLE` (no such queries).

### Log format (`results/raw/<scale>/<label>/<setup>/pruning.jsonl`)

One `{"type":"query"}` line per statement (`session, seq, tag, elapsed_ms, error, n_scans, plans,
plan_empty_results, plan_scan_tables, bound_tables, sql`) followed by one `{"type":"scan"}` line per table scan
(`table, total_rows, total_row_groups, has_filters, has_optional, pruned, scanned, scanned_no_rows, ...,
rows_passed, rows_passed_incl_optional, vectors_scanned, vectors_segment_skipped, filters:[{col, col_type, kind,
origin, dynamic, applied_to_rows, filter, sql, op, value|values, pruned_first, prunable_alone}]`). `tag` is the
session variable `pruning_tag` that the runner sets before each query (`SET VARIABLE pruning_tag='<setup>/<qid>'`),
so the file alone suffices for aggregation; a re-executed tag supersedes earlier lines.

## Correctness checks (small scale)

1. **Results unchanged by counting** (`compare_results.py`, `results/small/result_check.md`): all 16,164 queries,
   instrumented binary with counting on vs. off: identical output hash, row count and status (0 mismatches).
   Against pip `duckdb` 2.0.0 (independent build): identical row counts for all 16,164 queries, and identical full
   result content (order-independent hash) for all 16,000 microbenchmark queries (0 mismatches).
   (Not done: comparison against a pristine, unpatched v1.4.4 binary; with counting off the patch only adds
   null-pointer checks.)
2. **Invariant** `total = pruned + 3a + 3b + partial_no_rows + not_reached` and `scanned = 3a + 3b + partial`:
   16,894 scans, 0 violations (`invariants.txt`); `pruned_unattributed` = 0 everywhere.
3. **Ground truth** (`ground_truth.py`, `results/small/ground_truth.md`), plain SQL with pip `duckdb` on the same files:
   * layout: all 49 tables have row groups of exactly 8,192 rows except the last (pragma_storage_info), row-group
     counts equal `total_row_groups` → `rowid // 8192` is the row-group number;
   * micro, 100 random queries per setup (1,600 scans): row groups with ≥1 matching row = `scanned_with_rows`,
     matching rows = `rows_passed`, min/max-predicted prunable row groups = `pruned` – 0 mismatches;
   * all scans of TPC-H (86), TPC-DS (764), ClickBench (44), with the scan's rendered filters incl. join filters:
     `scanned_with_rows`/`rows_passed` checked for 887 scans, 0 mismatches; incl.-optional variant checked for 81
     scans, 0 mismatches; `pruned` predicted from exact min/max for 745 scans (exact) + 122 (VARCHAR, approximate) –
     0 mismatches. Not checkable: 10 scans whose pruning depends on top-N thresholds (time-varying; for 5 of them `scanned_with_rows` could still be checked), 2 rowid
     late-materialization scans (see below), 17 scans with expression filters for the pruning prediction.
   * Mismatches seen during development and explained: (a) row groups pruned by *optional* filters contain rows
     that satisfy the applied filters → the ground truth now excludes row groups predicted to be pruned;
     (b) `RowIdColumnData::Filter` evaluates the whole rowid filter, including the optional IN list, against each
     vector's rowid range, so for late-materialization scans `rows_passed` counts rows of 2,048-row vectors that
     contain a listed rowid (vector-level, not row-level semantics); (c) the pip-hash comparison needed CRLF line
     endings (CLI csv mode).
4. **Thread safety** (`compare_threads.py`): TPC-H/TPC-DS/ClickBench + 600 micro queries with 12 threads vs. 1 thread:
   751 of 754 non-top-N queries have identical per-scan counters; the 3 others (TPC-DS q04/q11/q74) receive
   different join filters (plan/build order differs with parallelism), not a counter race. Top-N queries differ as
   expected (threshold evolution depends on scan order).

## Caveats / semantics summary

* "Could have been pruned" (3a) is relative to the filters pushed into the scan and applied to rows. Predicates that
  stay above the scan (multi-column, non-pushable functions) are invisible; optional filters are covered only by the
  `incl_optional_*` columns.
* Dynamic join filters (min/max constant filters) are applied to rows and so are part of 3a/3b; their constants are
  rendered as final values. Top-N filters are optional and change during the scan; their `pruned_first` counts and
  the incl.-optional numbers depend on scan order (single thread → deterministic).
* Row groups are attributed to the first leaf filter that alone proves "no match" in the engine's check order
  (`pruned_first`); `prunable_alone` lists every leaf that alone could prune (useful for alternative statistics).
* LIMIT without ORDER BY would show up as `partial_no_rows` / `scanned_with_rows_partial` / `not_reached`; none of
  the benchmark queries does this.
* Rowid filters from late materialization never prune row groups (stock v1.4.4 behaviour) and are vector-level.
* String statistics in DuckDB hold 8-byte prefixes; the ground truth's exact min/max matched anyway at small scale.
* The original `experiments/sql/cardinality/*.sql` query non-existent ids (~1e19); this study uses
  `queries/sql_queries_cardinality_*.sql` (ids uniform in `[0, N)`).
* Not verified: large scale (needs the large CSVs); overhead of the disabled instrumentation vs. a pristine build.


# Phase 3/4: selective, per-column near-optimal pruning statistics

## What was built (Phase 3)

One binary, `duckdb/build/selective/duckdb` (reports v1.4.4), built from the repository's `duckdb/` tree by
`build_selective.sh` (release, ninja, `JOBS` default 3, build dir `duckdb/build/selective`, `BUILD_TPC=1` adds the
tpch/tpcds extensions). The tree now is **pristine v1.4.4 + the Phase 1 counter patch + runtime-selectable
statistics**:

* The paper's compile-time, all-columns framework was removed from the engine (restored to pristine v1.4.4:
  `column_data.{hpp,cpp}` temp-vector buffering of *every* column under a global mutex, `RowGroup::InitStats`,
  `ConstantFilter` querying additional stats, the BETWEEN hack and the unsynchronised `scanned_partitions` set in
  `RowGroup::CheckZonemap`, `BaseStatistics::additional_stats`/`id`, the `FinishInitialiseStats` operator hooks and
  the per-statement stderr logging in `tools/shell/shell.cpp` — `SQL_COMMAND_RUN_*`, `SCANNED_PARTITIONS`,
  `END_INITIALISE_ADDITIONAL_STATS`). The old headers in `storage/statistics/additional/` are still in the tree
  (unused); `OccupancyAdditionalStats`/`NullspaceAdditionalStats` and `pruning_codec.hpp` were taken from
  `origin/near-optimal-pruning-stats`, and the codecs of `pruning_codec.hpp` are used unchanged. Consequence: the
  paper's `compile_all.sh` binaries can no longer be built from this working tree (they still can from `main`).
* New: `src/include/duckdb/storage/table/selective_stats.hpp`, `src/storage/table/selective_stats.cpp`; hooks in
  `row_group.cpp` (build on append, consult in `CheckZonemap`, invalidate on update/revert), `column_data.hpp`
  (one `unique_ptr<SelectiveColumnState> selective` per column), `data_table_info.hpp` + `data_table.cpp`
  (per-table column specs, resolved by name at CREATE/load), `client_context.cpp` (timing log), counters in
  `pruning_stats.{hpp,cpp}` (Phase 1 patch, extended).

### Environment variables

| variable | meaning |
|---|---|
| `PRUNING_STATS_COLUMNS` | `table.column:kind[:words],...` (also `;`/space separated, case-insensitive). `kind` = `occupancy` or `nullspace`, `words` = size budget in 64-bit words per row group (default 200, ≥ 2). `table.*` selects all supported columns of a table; an exact entry wins over `*`. Unset/empty = **baseline** (min/max only). Invalid entries are reported on stderr and ignored; unsupported column types are reported and skipped. |
| `DUCKDB_PRUNING_STATS=<file>` | pruning counters (Phase 1 format, extended, see below) |
| `PRUNING_STATS_TIMING=<file>` | timing log (JSON lines, see below); independent of the counters |

Example: `PRUNING_STATS_COLUMNS="sensor_records.timestamp_ms:occupancy:200,store_sales.ss_customer_sk:nullspace:200"`.

### Semantics

* **Build**: for selected columns of a table, `RowGroup::InitializeEmpty` attaches a `SelectiveColumnState` to the
  column; `RowGroup::Append` maps every non-NULL value to a 64-bit key and buffers it (only for selected columns;
  other columns pay nothing); when the row group reaches its full size (8,192 rows) the statistic is encoded
  (`OccupancyCodec` / `NullspaceCodec` with the column's budget, exactly as on the branch), only the words actually
  needed are stored (+1 zero padding word), the buffer is freed, and the statistic is published with a release store.
  The last, partial row group of an append gets no statistic. Row groups re-created by vacuum/merges of parallel
  loads get one when they become full; partial row groups at batch boundaries of parallel loads do not.
  UPDATE of a column, or a reverted append, drops the column's statistic in that row group for good (DELETE keeps
  it: a superset is safe). DROP COLUMN / ALTER TYPE stop building statistics for new row groups of the table.
  Statistics live in memory only (not persisted): ingest and queries must run in the same process. They survive
  CHECKPOINT (verified: the harness checkpoints after loading).
* **Keys**: ordered key (occupancy): integers/DATE/TIME/TIMESTAMP/DECIMAL(≤18)/ENUM order-preserving and exact;
  DOUBLE/FLOAT order-preserving (−0 = 0, NaN largest); HUGEINT/UHUGEINT/DECIMAL(>18) saturating (exact in the
  int64/uint64 range); VARCHAR/BLOB the 8-byte big-endian prefix (monotone, not exact). Point key (nullspace): the
  ordered key for ≤ 64-bit types, DuckDB's hash for 128-bit integers and strings. Not supported: TIME_TZ, INTERVAL,
  BIT, BIGNUM, collated VARCHAR, nested types.
* **Use**: in `RowGroup::CheckZonemap`, only after the min/max zonemaps of *all* filtered columns failed to prune
  (and skipping filters that min/max proved always-true), each filtered column with a statistic is consulted with its
  complete pushed-down filter. A row group is pruned only if the filter provably matches no row:
  * `=`, `IS NOT DISTINCT FROM` (non-NULL constant) → point query (nullspace or occupancy);
  * `IN` lists (static `InFilter`, also inside `OptionalFilter`, e.g. join IN lists) → pruned if no element may be
    present (NULL elements ignored);
  * any AND (incl. nested ANDs, static + appended join filters, and ANDs inside optional filters) of `>=, >, <=, <`
    and equality on the column → one interval; with both bounds, occupancy `QueryRange`; nullspace enumerates
    integer intervals of < 64 values point by point; exclusive bounds are ±1 in key space for exact (integer/bool)
    keys (with overflow checks; a bound beyond the domain makes the interval empty), otherwise treated as inclusive;
  * `DynamicFilter` (top-N, and join filters) is read under its lock, as the engine does; uninitialised = no
    constraint;
  * OR: pruned if every disjunct can be pruned; `<>`, `IS [NOT] NULL`, expression/struct filters: never.
  * Half-open ranges are not sent to the statistic (min/max is exact for them).
  * Constants of another physical type than the column, NULL constants: no pruning.
* **Overhead when not selected**: a static-bool check per row group (`SelectiveStats::Enabled()`, cached) and a
  null check of `ColumnData::selective` per filtered column; nothing at ingest.

### Counters (`DUCKDB_PRUNING_STATS`)

Per scan, in addition to the Phase 1 fields: `pruned_minmax`, `pruned_additional` (`pruned` = their sum; row-group
state 3 = pruned by an additional statistic), `pruned_additional_no_single_leaf` (pruned only by a combination of
leaves, e.g. a range made of a static `>=` and a join `<=`), `additional_columns: [{col, pruned_first}]` (first
filtered column whose complete filter was proven unsatisfiable), `additional_columns_unattributed`; per filter leaf
`pruned_first_additional`, `prunable_alone_additional`. `pruned_first`/`prunable_alone` keep their Phase 1 meaning
(min/max only). Invariant: `total = pruned + scanned_no_rows + scanned_with_rows + partial_no_rows + not_reached`,
`pruned = pruned_minmax + pruned_additional`.

### Timing log (`PRUNING_STATS_TIMING`)

* first line per process: `{"type":"config","columns":...,"errors":[...]}`;
* per statement: `{"type":"query_timing","tag","elapsed_ms","consultations","consult_ns","pruned_additional","sql"}`
  (engine-side `steady_clock` from query begin to end; `consult_ns` = time spent consulting statistics after min/max
  failed, measured once per consulted row group and column, accumulated with relaxed atomics; per statement as the
  difference of process-wide counters, so it assumes one active connection, as in the harness);
* per selected column at the end of every statement that appended to it (COPY/INSERT/CTAS):
  `{"type":"ingest","table","column","kind","words","values","row_groups_built","row_groups_failed","bytes",
  "buffer_ns","build_ns"}` (buffering = key extraction per appended chunk, build = sort + encode per row group).

## Harness (Phase 4)

New files in `harness/` (existing scripts unchanged):

| file | purpose |
|---|---|
| `phase4.py` | runner: per group (dataset) / config / mode ONE CLI process per session: fresh DB `db/<scale>/phase4/…` (ROW_GROUP_SIZE 8192), DDL/COPY verbatim from `experiments/sql`, CHECKPOINT, then all queries of all setups using that dataset (`micro_unsorted` serves `point_unsorted` + the 3 `range_*_unsorted` setups, etc.). Modes: `count` (threads 1, counters, result hashes), `check` (default threads, result hashes), `time` (default threads or `--threads`, `.mode trash`, `--rounds 3` round-robin, `--sessions 3` each with its own ingest). Per-query timeout → kill, record, restart the session (re-ingest) skipping finished and hanging queries; status flushed per query; re-running resumes. `phase4.py spec` prints column specs. |
| `phase4_aggregate.py` | → `results/<scale>/phase4/`: `counts_per_query.csv`, `counts_per_setup.csv`, `results_check.csv`, `runtimes_per_query.csv`, `runtimes_per_setup.csv`, `ingest.csv`, `summary.md` |
| `phase4_compare_stock.py` | baseline counting pass vs. the stock binary's Phase 1 `results/raw/<scale>/count` (results + all counters per scan and filter; scans matched by scan id, or by (table, row groups, filters, rows passed) when the ids are permuted; origin labels `static`→`join` tolerated, see the counter fix below) |
| `phase4_validate.py` | per-scan validation of a selective counting pass vs. the baseline pass (result hashes, invariants, attribution sums, equal min/max pruning / `incl_optional_with_rows` / `rows_passed_incl_optional`, `scanned_with_rows` changes) and attribution of the pruned row groups to table.column and filter category → `results/<scale>/phase4/validate_<config>{.md,_scans.csv,_attribution.csv}` |
| `phase4_selftest.py` | randomized correctness test on all supported types and predicate shapes (incl. joins, top-N, UPDATE/DELETE/INSERT afterwards), baseline vs. occupancy/nullspace at several sizes |

Raw output: `results/raw/<scale>/phase4/<config>/<mode>/<group>/session_<k>/attempt_<a>/{status,timing,pruning}.jsonl`
(+ `script.sql`, `cli.log` without result rows). `--columns` accepts a literal spec, `@file`, or
`preset:<broad|micro>:<kind>:<words>[:varchar]` (`broad` = the micro columns + every TPC-H/TPC-DS/ClickBench column
with a pushed-down filter in `results/small/filter_detail.csv`, rowid excluded, VARCHAR only with `:varchar`).

Further `phase4.py run` options: `--threads N` (count: default 1; check/time: default = DuckDB's), `--memory-limit`,
`--load-threads`, `--limit N` (first N queries per setup), `--sample k` (every k-th query: indices 0, k, 2k, … after
`--limit`, the same selection as `run.py --sample`), `--sample-setups unsorted,outliers,cardinality` (apply
`--sample` only to setups whose name contains one of the substrings), `--setups`, `--timeout`, `--ingest-timeout`,
`--max-restarts`, `--sorted-hash-max-lines` (default 500,000: results with more lines get only the streaming
`hash_multiset`, not the `hash_sorted` that needs all lines in memory; comparisons use `hash_sorted` when both sides
have it, else `hash_multiset`). **Resume**: re-running the same command skips every query with a final status in
`status.jsonl` (also across sessions/reboots); `run.json` records the settings and a re-run with different settings
(columns, threads, binary, memory limit, sample, …) into the same `--config` directory is refused
(`--force-resume` overrides).

```bash
cd pruning_opportunity
./build_selective.sh                                  # ~1.2 h at -j3 from scratch on this machine (under load)
PY=../.venv/bin/python
$PY harness/phase4_selftest.py --queries 3000 --words 20,200            # ~5 min
# small scale (memory_limit as you like; I used 1500MB)
$PY harness/phase4.py run --scale small --groups all --config baseline --mode count
$PY harness/phase4.py run --scale small --groups all --config occ200 --columns preset:broad:occupancy:200 --mode count
$PY harness/phase4.py run --scale small --groups all --config ns200  --columns preset:broad:nullspace:200:varchar --mode count
$PY harness/phase4.py run --scale small --groups all --config baseline --mode check      # multi-threaded hashes
$PY harness/phase4.py run --scale small --groups micro_unsorted --config baseline --mode time
$PY harness/phase4.py run --scale small --groups micro_unsorted --config stock --binary stock/duckdb/build/release/duckdb --mode time
$PY harness/phase4.py run --scale small --groups micro_unsorted --config occ200 --columns preset:broad:occupancy:200 --mode time
$PY harness/phase4_aggregate.py --scale small && $PY harness/phase4_compare_stock.py --scale small
$PY harness/phase4_validate.py --scale small --config occ200      # per-scan validation + attribution
```

### Large scale (commands; not run yet)

One DuckDB process per command; the statistics live in memory, so every command ingests its group itself
(`--load-threads 1` keeps row group k = rows k·8192…, as the Phase 1 databases; the statistic build runs on the
loading thread: ≈ 15 ms per row group and column for occupancy@200, ≈ 75 ms for nullspace@200 → for a 1B-row
column ≈ 30 min / 2.5 h). Use `--threads 8` for counting passes that are compared with the Phase 1 large `count`
run (it used 8 threads; with 1 thread top-N/join-filter counters differ). Every command is resumable (re-run it).

```bash
cd pruning_opportunity; PY=../.venv/bin/python
L="--scale large --memory-limit 5GB --sample 5 --sample-setups unsorted,outliers,cardinality"
# micro: every 5th query of the unsorted/outliers/cardinality setups (= the Phase 1 large run), all sorted queries
for g in micro_unsorted micro_outliers micro_sorted micro_cardinality_100 micro_cardinality_1000 \
         micro_cardinality_10000 micro_cardinality_100000; do
  $PY harness/phase4.py run $L --groups $g --config baseline --mode count --threads 8
  $PY harness/phase4.py run $L --groups $g --config occts200 --mode count --threads 8 \
      --columns sensor_records.timestamp_ms:occupancy:200
done
$PY harness/phase4_compare_stock.py --scale large          # baseline (8 threads) vs. Phase 1 stock large count
$PY harness/phase4_validate.py --scale large --config occts200
# timing (3 rounds x 3 sessions; stock = Phase 1 binary for the overhead check)
for c in "baseline" "stock --binary stock/duckdb/build/release/duckdb" \
         "occts200 --columns sensor_records.timestamp_ms:occupancy:200"; do
  $PY harness/phase4.py run $L --groups micro_unsorted,micro_outliers --mode time --threads 8 --config $c
done
# TPC-H/TPC-DS/ClickBench: the selective columns that pruned anything at small scale
B="--scale large --memory-limit 5GB --threads 8"
$PY harness/phase4.py run $B --groups tpcds,clickbench --config baseline --mode count
$PY harness/phase4.py run $B --groups tpcds,clickbench --config sel --mode count --columns \
  "store_sales.ss_customer_sk:occupancy:200,store_sales.ss_item_sk:occupancy:200,store_sales.ss_sold_date_sk:occupancy:200,catalog_sales.cs_item_sk:occupancy:200,hits.UserID:occupancy:200"
$PY harness/phase4_aggregate.py --scale large
```


## Small-scale validation (status: DONE for small scale; numbers 2026-11-17)

All runs: `--memory-limit 1500MB`, one DuckDB process at a time, machine shared with the large-scale Phase 1 run
(timings are noisy). Raw data `results/raw/small/phase4/`, tables `results/small/phase4/` (`summary.md`,
`compare_stock_baseline.md`, `validate_<config>.md`, …).

* **Self-test** (`phase4_selftest.py --queries 3000 --words 20,200`, 4 threads, 48 full row groups, 21 columns of all
  supported types incl. HUGEINT/UHUGEINT/DECIMAL(4/18/38)/DATE/TIME/TIMESTAMP/DOUBLE/FLOAT/VARCHAR/BOOLEAN with NULLs):
  3,300 queries per config, results of occ20/nul20/occ200/nul200 **identical** to baseline; 1,008 statistics built
  per config, ~126k consultations, 59k–63k row groups pruned. The first version of the test found a real bug
  (occupancy point queries on 128-bit/string columns used the hash instead of the ordered key; fixed).
* **Harness fixes exercised**: bounded output queue + no result rows in `cli.log` + `stdbuf -oL`: cardinality_100
  (≈100k result rows per query) ran with a driver+CLI peak RSS of 249 MB (40 queries, hashes identical to the
  earlier run); all later runs (≈ 30 CLI sessions) without problems.
* **(b) Baseline vs. stock** (`phase4_compare_stock.py`, counting pass, threads 1): identical counters for every
  scan and filter leaf in **all** compared queries — 12 sortedness/range micro setups 12,000/12,000,
  cardinality_100 910/910, cardinality_100000 200/200, TPC-H 22/22, TPC-DS 99/99, ClickBench 42/43; identical
  results wherever both sides have a hash (all of the above; cardinality_100 448 of 910 have a hash on both sides).
  Explained differences: ClickBench q01 (`SELECT COUNT(*) FROM hits`) has no table scan in the Phase 1 run (count
  answered from the persisted table's metadata) and one in the in-session run; in 1 TPC-DS query of the final run (3 — q02, q05, q54 — in an earlier run; order varies between runs)
  the scan ids of two UNION branches are permuted (scans are matched by table/row groups/filters/rows passed then).
* **Counter labelling bug found and fixed** (`pruning_stats.cpp`, Phase 1 code, labels only): leaves of a scan
  whose physical table scan has *no* plan-time filters (all filters come from join filter pushdown) were labelled
  `origin=static`; now `join`. Affects 35 TPC-H, 263 TPC-DS, 2 ClickBench scans; counts are unchanged.
  **The Phase 1 stock binary (and the running large-scale measurement) still has the old labelling**: in Phase 1
  results, `static` leaves of scans without a `join` leaf may be join filters (e.g. TPC-DS q32/q37/q82/q54).
  `phase4_compare_stock.py` tolerates exactly this relabelling.
* **(a) Results, counting pass (threads 1), selective vs. baseline**: identical row count + order-independent hash
  for every query: occ200 (`preset:broad:occupancy:200`, 145 columns) TPC-H 22/22, TPC-DS 99/99, ClickBench 43/43,
  micro 12,000/12,000, cardinality_100 272/272 (with hash), cardinality_100000 200/200; ns200
  (`preset:broad:nullspace:200:varchar`) TPC-H 22/22, TPC-DS 99/99, ClickBench 43/43, micro 12,000/12,000.
* **(c) Per scan** (`phase4_validate.py`, every scan of every query; TPC-H 86, TPC-DS 764, ClickBench 45 scans per
  config): 0 invariant violations (`total = pruned + no_rows + with_rows + partial + not_reached`,
  `pruned = pruned_minmax + pruned_additional`, per-leaf and per-column attribution sums = `pruned_additional`);
  `total_row_groups`, `pruned_minmax`, `incl_optional_with_rows` and `rows_passed_incl_optional` identical to the
  baseline in every scan; `scanned_with_rows` identical except 2 TPC-DS scans per config, both explained:
  q32 `catalog_sales` (176 → 167 occ / 166 ns) and q82 `store_sales` (352 → 304 / 306). There the only filters are
  join-derived `cs_item_sk`/`ss_item_sk >= min AND <= max` (applied to rows) plus an *optional* join IN list
  (`IN (4118, 4119, 5343, 9583)` / `IN (10123, 11300)`, not applied to rows). Every row group passes the range, so
  the baseline counts all as "with rows"; the statistic proves the IN list absent and prunes them — rows of those
  row groups pass only the non-optional filters, never the complete filter. Ground truth (plain SQL on the Phase 1
  DB, `count(DISTINCT rowid // 8192)` of rows satisfying the IN list / equality): q32 154, q82 272, q37 108,
  q54 3, ClickBench q20 0 row groups — exactly the `incl_optional_with_rows` of baseline and selective passes, i.e.
  no row group with a qualifying row was pruned.
* **(d) Pruned "scanned, no rows" row groups** (counting pass; "incl.-opt." = the baseline's row groups with no row
  satisfying all pushed-down filters incl. optional ones):

| setup | baseline no rows | baseline incl.-opt. no rows | occ200 pruned (of no-rows / % ; of incl.-opt. %) | ns200 pruned |
|---|---|---|---|---|
| TPC-H (22 q.) | 0 | 0 | 0 | 0 |
| TPC-DS (99 q.) | 578 | 740 | 468 (411 / 71.1 %; 63.2 %) | 461 (405 / 70.1 %; 62.3 %) |
| ClickBench (43 q.) | 627 | 761 | 6 (6 / 0.96 %; 0.79 %) | 6 |
| point_unsorted / outliers / sorted | 1,220,992 / 500,296 / 992 | same | 52.4 % / 99.8 % / 56.2 % | 64.7 % / 64.9 % / 60.8 % |
| range_{seconds,minutes,hours}_unsorted | 1,217,129 / 1,010,459 / 13 | same | 52.3 / 54.2 / 53.8 % | 0 (no range support) |
| range_*_outliers | 499,317 / 499,304 / 499,304 | same | 100 % | 0 |
| cardinality_100 (419 q.) / 100000 (200 q., every 5th) | 247,619 / 225,710 | same | 99.9 % / 57.7 % | |

  Per query (occ200; ns200 in parentheses where different) — table.column, filter category, pruned / baseline
  no-rows / baseline incl.-opt. no-rows / total row groups:
  TPC-DS q54 `store_sales.ss_customer_sk` join equality 348/349/349/352; q37 `catalog_sales.cs_item_sk` join
  equality 60 (54)/68/68/176; q82 `store_sales.ss_item_sk` join IN 48 (46)/0/80/352; q32 `catalog_sales.cs_item_sk`
  join IN 9 (10)/0/22/176; q33, q56, q58 `store_sales.ss_sold_date_sk` join range (combination of join `>=`/`<=`
  leaves) 1/1/1/352 each; ClickBench q20 `hits.UserID` static equality 6/6/6/123. By category (TPC-DS, occ200):
  join equality 408, join IN 57, join range 3; ClickBench: static equality 6; micro: static equality (point) and
  static range (BETWEEN = two leaves). No static IN / top-N pruning occurred.
  Not pruned: TPC-DS — conjunctions whose columns are each satisfiable (q88/q96 `store_sales` hdemo/time/store,
  109 RGs; q76 `web_sales` with an expression filter, 39; `inventory` in q37/q82); ClickBench — VARCHAR `LIKE`
  expression / `<>` filters, rowid late-materialization filters (q24/q25), top-N filters (q24–q27); TPC-H has no
  "no rows" row group at SF1 at all (statistics were built and consulted: 9,374 row groups, 16,147 consultations).
* **Multi-threaded `check` (3 threads)**: micro (every 20th query of 14 setups, 700 queries: unsorted, outliers,
  sorted, cardinality_100, cardinality_100000) and TPC-H: occ200 = baseline for all; TPC-DS/ClickBench: occ200
  differs from the baseline check in 11 queries, ns200 in 10 (TPC-DS q39; ClickBench q12/18/19/23/25/31/32/33/39/
  40/41 — subsets of one set). These are nondeterministic with threads > 1: a second baseline check
  (`baseline_rerun`) differs from the first in exactly that set (TPC-DS q39 = float stddev aggregation; ClickBench =
  `ORDER BY count LIMIT 10` with ties, `GROUP BY … LIMIT` without ORDER BY, top-10 by EventTime). With 1 thread all
  of them are identical (above).
* **Ingest cost** (10M rows, single-threaded COPY in-session, 1,220 statistics on `sensor_records.timestamp_ms`):

| | COPY (ms, 3 sessions) | statistic build (ms) | key buffering (ms) | statistic size |
|---|---|---|---|---|
| unsorted baseline | 9,578 / 18,925 / 35,733 | – | – | – |
| unsorted occupancy@200 | 22,593 / 35,146 / 37,702 | 14,268 / 21,304 / 22,214 | 39 / 59 / 57 | 1,942,240 B |
| outliers baseline | 8,619 / 28,673 / 31,877 | – | – | – |
| outliers occupancy@200 | 25,013 / 27,710 / 29,545 | 12,141 / 13,040 / 12,079 | 78 / 58 / 164 | 1,946,296 B |
| stock binary (wall) unsorted / outliers | 14,461 / 11,785 / 19,787 ; 14,906 / 22,817 / 24,959 | | | |

  Build ≈ 10–18 ms per row group (sort + encode, on the loading thread); nullspace@200 ≈ 75 ms per row group
  (micro, ns200 count: 90.7 s for 1,220 row groups; TPC-H broad 9,374 row groups 357 s).
* **Query runtimes** (time mode, 3 threads, 100 queries per setup = every 10th, median of 3 rounds per query, mean
  over queries in ms; harness wall time; three independent repetitions a/b/c, each with its own ingest):

| setup | stock | baseline | occupancy@200 | speedup occ vs. baseline | consult time / query (CPU, all threads) |
|---|---|---|---|---|---|
| point_unsorted | 19.2 / 18.6 / 23.8 | 22.3 / 23.6 / 22.4 | 20.7 / 29.1 / 23.9 | ≈ 1.0 | 30 / 39 / 35 ms |
| range_seconds_unsorted | 20.7 / 19.4 / 22.2 | 23.0 / 24.9 / 25.9 | 23.3 / 24.5 / 26.6 | ≈ 1.0 | 30 / 33 / 36 ms |
| range_minutes_unsorted | 26.5 / 23.8 / 30.2 | 35.3 / 35.9 / 33.2 | 27.2 / 35.4 / 34.1 | 1.0–1.3 | 30 / 37 / 38 ms |
| point_outliers | 11.1 / 13.3 / 9.9 | 12.2 / 13.2 / 13.2 | 7.4 / 8.7 / 6.5 | 1.5–2.0 | 9 / 11 / 9 ms |
| range_seconds_outliers | 11.3 / 11.2 / 11.3 | 13.1 / 12.6 / 13.4 | 8.6 / 8.9 / 6.3 | 1.4–2.1 | 10 / 11 / 9 ms |
| range_minutes_outliers | 12.4 / 11.9 / 9.3 | 12.6 / 12.0 / 13.1 | 6.7 / 9.6 / 7.0 | 1.3–1.9 | 9 / 10 / 9 ms |

  Consultation cost: ≈ 18–25 µs per row group and column at 200 words (`OccupancyCodec::MayContain` decodes the
  Golomb-coded cell list sequentially; the codec is the branch's, unchanged). For a single-column UBIGINT table this
  is about as expensive as scanning the row group, so on `unsorted` (1,220 consultations, ≈ 52 % pruned per query)
  the gain is ~0; on `outliers` (507 consultations per query after min/max, ~100 % pruned) 1.3–2×. Statistics
  consultation is CPU time summed over threads.
  **Baseline vs. stock**: in-session, stock was faster in 4 of 5 interleaved repetitions on `unsorted` (point
  16–24 vs. 19–24 ms, range_minutes 21–30 vs. 24–36 ms), mixed on `outliers`; on the persisted Phase 1 database
  (`-readonly`, same 300 queries, 4 interleaved repetitions) the selective binary in baseline configuration was
  *faster* (range_minutes 9.4 s vs. 10.3 s total, point 7.0 s vs. 8.7 s; selective + timing log 8.4 / 7.4 s).
  The code differences on the baseline path are a cached static-bool check per row group and a null check per
  filtered column; I conclude there is no overhead measurable above the noise of this loaded machine (± 30 %), but
  a clean overhead number needs the quiet-machine/large-scale timing runs.

### Not done / unverified

* Large scale (commands above). Cardinality_1000/10000 (selective counting), nullspace/occupancy word sweeps
  beyond 20/200, `time` mode for TPC-H/TPC-DS/ClickBench, multiple `--sessions` in time mode at small scale.
* cardinality_100: 462 of the 910 baseline counting-pass queries (from the run stopped by the memory incident) have
  counters but no result hash.
* Leftover files: `db/small/phase4/{ns200,sweep_nul20}__count__micro_cardinality_100__session_0.db*` from the stopped runs (43 MB; the harness deletes its DBs, these are
  from killed processes), `duckdb/build/selective/` build tree, and in the scratchpad of this session the previous
  binary and pre-fix raw runs (not needed).


# Row-id range check (late-materialization rescans)

**Problem.** Top-N queries that project many columns (ClickBench q24/q25: `SELECT * / SearchPhrase ... ORDER BY
EventTime LIMIT 10`) are planned by v1.4.4's late materialization as `HASH_JOIN SEMI (rowid = rowid)` between a full
`SEQ_SCAN hits` (probe) and `TOP_N` over a narrow scan (build). Join filter pushdown adds to the probe scan, on the
rowid column (`COLUMN_IDENTIFIER_ROW_ID`), one `CONJUNCTION_AND` of `rowid >= min`, `rowid <= max` (constant
filters, applied to rows) and `OPTIONAL_FILTER(IN_FILTER(rowid IN (<the 10 row ids>)))`. `RowGroup::CheckZonemap`
checks it with `GetColumn(ROW_ID).CheckZonemap(filter)` against the `RowIdColumnData`'s statistics, which are *empty*
(min > max → `NO_PRUNING_POSSIBLE`), so every row group is entered; only `RowIdColumnData::Filter` skips per
2,048-row vector (`CheckRowIdFilter` on the vector's row-id range). Plain `WHERE rowid IN (...)`/`= x`/`BETWEEN`
behave the same (the IN list alone is an optional filter and is not even evaluated per vector).

**Fix** (`patches/duckdb-v1.4.4-rowid-range.patch`, on top of the counter patch, ~65 changed lines in
`row_group.{hpp,cpp}`, `pruning_stats.{hpp,cpp}`; tree `rowid/duckdb`, gitignored; build like `build_stock.sh` with
`CMAKE_BUILD_PARALLEL_LEVEL=2`): new `RowGroup::CheckColumnZonemap(column, filter)`, used by `CheckZonemap` and by the
counters' attribution. With env `PRUNING_ROWID_SKIP=1` (read once), for the rowid column it evaluates the filter
(any shape: =, IN, ranges, AND/OR conjunctions, optional wrappers – via `TableFilter::CheckStatistics`) against
synthetic statistics `[start, start + count - 1]` of the row group and skips the row group on `FILTER_ALWAYS_FALSE`,
exactly like zonemap pruning (counted as `pruned`). Any other outcome falls back to the stock check, so scanned row
groups behave exactly as before (no new "always true" short-cut). Flag off = stock behaviour and byte-identical
counter output. With the flag on, scan records get `pruned_rowid_range` (pruned row groups whose first proving leaf
is a rowid filter; leaves' `pruned_first`/`prunable_alone` are attributed as usual) and `pruned_rowid_only` (no
non-rowid leaf alone could prune). Invariant `total = pruned + scanned_no_rows + scanned_with_rows + partial_no_rows
+ not_reached` unchanged. (Development bug found: `COLUMN_IDENTIFIER_ROW_ID == INVALID_INDEX`, so the counter's
`optional_idx` lookup threw as soon as a rowid filter pruned – stock never got there.)

**Results** (`results/small/phase4/rowid/`: `summary.md`, `per_query.csv`, `timing.csv`, `checks.csv`,
`selftest.json`; pipeline `run_rowid_small.sh` → `harness/rowid_aggregate.py`; tests `harness/rowid_selftest.py`).
Small ClickBench, 1 thread counters: wasted reads (scanned_no_rows) over 43 queries **627 → 394 (−37 %)**; only
q24 (211 → 95, 116 pruned by rowid_range; the remaining 95 are the first scan's `URL LIKE '%google%'`) and q25
(117 → 0) change. Timing (median of 3, 12 threads): q24 80 → 41 ms; all others within noise. Correctness: 1-thread
results identical stock/base/rowid for 43/43; base counters = stock counters 43/43; 250 hand-written tests
(=, IN, BETWEEN, comparisons, OR, boundaries, out of range, top-N late materialization on clickbench, micro_sorted,
micro_unsorted, TPC-H lineitem) pass at 1 and 8 threads with exact row-group pruning. At 8 threads 11 ClickBench
queries are nondeterministic within one configuration (ties in `ORDER BY ... LIMIT`), so they cannot be compared
by hash; q24/q25 with a `rowid` tie-breaker are identical.

Caveats: the patch applies cleanly to `stock/duckdb`, but the selective `duckdb/` tree needs a manual merge of the
JSON-output hunk in `pruning_stats.cpp` (and a check of the `CheckZonemap` hunk, which applies with fuzz). Not run at
large scale. Transaction-local storage (uncommitted appends) has row groups starting at `MAX_ROW_ID`, consistent with its row ids, so the check should be correct there too, but it is not tested.


# Phase 4b: 3-gram statistic validation (ng2000 on `hits.URL`, `hits.Title`)

Only 3-gram statistics (kind `ngram`, n = 3), budget 2000 words = 16 KB per row group and column. Tables:
`results/small/phase4/ngram/` (`validation.md` + `validation.csv`; pruning per budget in `summary.md`, produced by
`harness/ngram_eval.py truth|report`).

* **Results**: identical to the baseline for all 43 ClickBench queries with 1 thread (`ng2000` vs `baseline_ng`;
  `ng2000_pc` cold + warm pass vs `baseline_pc`) and with 8 threads (`ng2000_t8`, `ng2000_pc_t8`: every deterministic
  query identical; the 11 queries whose result varies between baseline runs with 8 threads — ties under
  `ORDER BY ... LIMIT`, `LIMIT` without `ORDER BY` — have the same row counts; 6 baseline samples).
* **Randomized self-test** (`phase4_selftest.py --suite ngram --ngram-configs ng3w20:20:3,ng3w200:200:3,ng3w2000:2000:3`,
  3,301 queries, threads 1 and 8): 0 result differences; 67k-68k row groups pruned. The generator now also emits empty
  literals, 1-2 byte literals (no trigram), case variants and constant patterns (`LIKE NULL`, `contains(col, NULL)`,
  `LIKE '%'`, `LIKE ''`, `LIKE '_'`, ...), in addition to `%` / `_` wildcards, ESCAPE, ILIKE, NULL rows.
* **Cost**: build URL 123-166 ms, Title 30-40 ms per row group (COPY of 1M rows 8-14 s → 27-38 s); lookup 20-25 µs
  per consulted row group; q21/q22/q23/q24 9.9/8.4/14.5/20.1 ms → 8.5/7.1/12.3/18.6 ms (8 threads, warm medians,
  `results/small/phase4/predcache/timing.csv`).


# Phase 5: predicate cache (`PRUNING_PREDICATE_CACHE`)

After Schmidt et al., "Predicate Caching" (SIGMOD 2024) and ClickHouse's query condition cache. In-process,
in-memory, empty at process start; default off (unset = exactly the previous behaviour; the only cost is a null
check per row group / vector, like the counters).

| `PRUNING_PREDICATE_CACHE` | meaning |
|---|---|
| unset / `0` / `off` | no cache |
| `1` / `on` / `exact` | whole-conjunction keys |
| `2` / `subset` | additionally, an entry whose conjunct (leaf) set is a subset of the scan's leaf set may prune |

**Files**: new `src/include/duckdb/storage/table/predicate_cache.hpp`, `src/storage/table/predicate_cache.cpp`;
hooks in `row_group.cpp` (lookup in `CheckZonemap` after min/max and before the selective statistics; scan events),
`row_group_collection.{hpp,cpp}` (per-table cache, invalidation), `scan_state.hpp` (per-scan pointer),
`row_group.hpp`, `table_scan.cpp` (creation per table scan), `pruning_stats.{hpp,cpp}` (cause + JSON),
`selective_stats.cpp` (timing log fields), `storage/table/CMakeLists.txt`. Patches:
`patches/duckdb-v1.4.4-predicate-cache.patch` (incremental, against the tree state before this change = v1.4.4 +
counters + selective statistics; verified to reproduce the current files) and
`patches/duckdb-v1.4.4-full-selective-predicate-cache.patch` (complete `src/` diff of the current tree vs.
pristine v1.4.4, verified; includes the unused paper headers in `storage/statistics/additional/`).

**Key**: per table (`RowGroupCollection`), the static (plan-time, `PhysicalTableScan::table_filters`) pushed-down
filters flattened over AND into leaves; `OptionalFilter` leaves (IN lists, OR clauses, top-N) are left out; dynamic
join filters are never part of the static set. Each leaf = storage column (incl. struct child path) + binary
serialization of the `TableFilter` (exact: constant types, ExpressionFilter expressions such as
`contains(URL, 'google')`); leaves are sorted and de-duplicated, so the key does not depend on the projection or
filter order. Uncacheable (no entry, no lookup): no static non-optional filter, filters on `rowid`/virtual columns,
optional/dynamic filters nested inside a non-optional leaf, non-serializable filters, TABLESAMPLE.

**Value**: per row group a `known` and a `has_rows` bit (2 bits per row group and key). Recorded at the end of the
scan (destructor of the scan's global state) under the table's lock:
* pruned by min/max or a selective statistic → "no rows", but if the scan also had optional or dynamic filters
  (which can prune on their own), only after re-checking that the static non-optional filters alone prune it;
* entered and ≥ 1 row passed the applied filters → "has rows" (applied ⊇ static, so valid for the key);
* entered, zero rows → "no rows" only if (i) the filters applied to rows are exactly the key's leaves (no dynamic
  join filter), (ii) every vector of the row group was processed (all filters are evaluated per vector until the
  selection is empty, so the whole conjunction is decided for every row; per-conjunct results are *not* recorded),
  (iii) every row was visible to the transaction (no deletes / uncommitted appends in that row group) and (iv) the
  filtered columns have no update information;
* everything else (LIMIT early stop, cancellation, not reached, top-N/join-pruned) stays unknown.
Use: a known "no rows" bit skips the row group (`pruned_predicate_cache` in the counters, row-group state 4;
`pruned = pruned_minmax + pruned_additional + pruned_predicate_cache`). The lookup bitmap is copied once per scan.

**Invalidation**: every write entry point of the table's `RowGroupCollection` (InitializeAppend, Append,
FinalizeAppend, CommitAppend, RevertAppend, MergeStorage, Delete, Update, UpdateColumn, Checkpoint, CommitDropColumn,
Add/RemoveColumn, AlterType) bumps the table's epoch and clears its entries; a scan records only if the epoch is
unchanged since it started. ALTER creates a new collection (new, empty cache). The ClickBench table is read-only after
load + CHECKPOINT, so nothing is invalidated during the experiment.

**Reporting**: counters get `pruned_predicate_cache` and `predicate_cache: {cacheable, reason | key, leaves,
exact_applied, needs_recheck, entries_used, known_empty_at_start}` per scan; the timing log gets `pc_*` fields per
statement (`pc_pruned`, `pc_recorded_empty/rows`, `pc_conflicts`, `pc_lookup_ns`, `pc_record_ns`, `pc_recheck_ns`,
`pc_invalidations`, `pc_entries`, `pc_bytes` = serialized keys + bitmaps).

**Harness**: `phase4.py run --passes 2` (count/check: run the query list twice in one session, second pass tagged
`#p2`) and `--predicate-cache 1|subset` (config names other than `baseline*`/`stock*` may omit `--columns`);
`phase4_selftest.py --suite predcache`; `harness/predcache_aggregate.py` (`summary.md` is regenerated; the
"Notes" section at its end was appended by hand).

```bash
cd pruning_opportunity; PY=../.venv/bin/python; NG="--columns hits.URL:ngram:2000,hits.Title:ngram:2000"
B="--scale small --groups clickbench --memory-limit 1500MB --passes 2"
$PY harness/phase4.py run $B --mode count --config baseline_pc
$PY harness/phase4.py run $B --mode count --config ng2000_pc $NG
$PY harness/phase4.py run $B --mode count --config predcache --predicate-cache 1
$PY harness/phase4.py run $B --mode count --config predcache_ng2000 --predicate-cache 1 $NG
$PY harness/phase4.py run $B --mode count --config predcache_sub --predicate-cache subset      # (+ _ng2000)
$PY harness/phase4.py run $B --mode check --threads 8 --config predcache_t8 --predicate-cache 1   # etc., + baseline_pc_t8{,b}
T="--scale small --groups clickbench --memory-limit 1500MB --mode time --threads 8 --rounds 4 --sessions 1"
$PY harness/phase4.py run $T --config predcache_time_b --predicate-cache 1      # etc., suffixes _b _c _d
$PY harness/phase4_selftest.py --suite predcache --queries 600 --threads 4
$PY harness/predcache_aggregate.py --scale small --configs baseline_pc,ng2000_pc,predcache,predcache_ng2000,predcache_sub,predcache_sub_ng2000 \
   --check-baselines baseline_pc_t8,baseline_pc_t8b,baseline_t8,baseline_t8b \
   --time-configs baseline_pctime,ng2000_pctime,predcache_time,predcache_ng2000_time --time-reps _b,_c,_d
```

## Results (small scale, 2026-11-17; `results/small/phase4/predcache/summary.md`, CSVs alongside)

One session per configuration, cold cache, q01..q43 then q01..q43 again; 1 thread; sums over 43 queries (5,535
row-group decisions per pass):

| config | pass | pruned | by predicate cache | scanned, no rows (wasted) | scanned with rows |
|---|---|---|---|---|---|
| baseline | cold = warm | 822 | – | 627 | 4,086 |
| ng2000 | cold = warm | 1,033 | – | 416 | 4,086 |
| predcache | cold | 917 | 95 (q24 reuses q21's key) | 532 | 4,086 |
| predcache | warm | 1,216 | 394 | 233 | 4,086 |
| predcache + ng2000 | cold | 1,073 | 95 | 376 | 4,086 |
| predcache + ng2000 | warm | 1,216 | 394 | 233 | 4,086 |
| predcache_subset | cold | 1,012 | 190 (+ q22 via q21's entry) | 437 | 4,086 |
| predcache_subset + ng2000 | cold | 1,113 | 190 | 336 | 4,086 |
| predcache_subset (± ng2000) | warm | 1,216 | 394 | 233 | 4,086 |

* Warm pass: the cache removes every wasted read of cacheable scans (q20 6, q21 95, q22 122, q23 76, q24 first scan
  95); the remaining 233 are the `rowid` late-materialization scans of q24/q25 (only dynamic join filters → no key).
  Cache: 16 entries, 2,031 bytes. Lookup 0.6 ms, recording 0.05 ms, static re-check 0.02 ms over all 43 queries.
* Correctness: results identical to the baseline in all 6 configurations × 2 passes with 1 thread (516 executions);
  with 8 threads (cold + warm pass) every deterministic query identical, the nondeterministic 11 vary as between
  baseline runs, row counts identical everywhere. Counter invariants 0 violations, cache merge conflicts 0,
  `scanned_with_rows` / `rows_passed` identical to the baseline for every query. Self-test `--suite predcache`
  (types table, 48 row groups; ≈ 6k queries incl. LIMIT early stops, conjunction extensions for subset lookups,
  joins / top-N, UPDATE, BEGIN/DELETE/ROLLBACK, BEGIN/UPDATE/ROLLBACK, BEGIN/INSERT/ROLLBACK, INSERT, DELETE,
  CHECKPOINT, each followed by repeated queries, and the static part of every top-N query re-run as a count;
  configs exact, subset, subset + occupancy@200; threads 1, 4, 8 (two seeds)): 0 differences, 0 conflicts,
  56k-71k row groups pruned by the cache per config.
* **Bug found by the self-test and fixed**: segment-level zonemap skips (`RowGroup::CheckZonemapSegments`, per vector)
  use the scan's complete column filter, i.e. also an optional top-N threshold ANDed with the static filter of the
  same column. With several threads the threshold tightens in the middle of a row group, the remaining vectors are
  skipped, and the first version recorded the row group as "no rows" for the key without the top-N filter. With 4
  threads this produced 1-3 merge conflicts and, after adding the count re-runs of top-N predicates to the
  self-test, 2-6 wrong results in later queries (`results/raw/small/phase4/selftest_predcache_before_fix/`). Fix:
  if the scan has optional or dynamic filters, a segment skip makes the row group undecidable (unknown). All
  ClickBench runs above were repeated with the fixed binary (identical counts).
* Time (8 threads, warm, median of 9 executions in 3 sessions; machine shared, totals vary ±10 % between sessions):
  q21 9.9 → 4.4 ms (predcache) / 4.1 ms (predcache + ng2000), q22 8.4 → 2.0 / 1.8 ms, q23 14.5 → 10.7 / 10.5 ms,
  q24 20.1 → 15.4 / 14.8 ms (ng2000 alone: 8.5 / 7.1 / 12.3 / 18.6 ms); all 43 queries 660 → 661 / 637 ms, i.e.
  no measurable overhead on the other queries.

Caveats: small scale only; the warm-pass benefit assumes exact repetition of the static conjunction (literal
constants are part of the key); recording happens at the end of a scan, so a second scan with the same key inside the
same query does not profit; per-single-conjunct recording is not implemented (lazy per-vector filter evaluation makes
it unsound), only the subset *lookup* of whole-conjunction entries, which is sound; deletes conservatively clear the
cache although "no rows" would stay valid.


# Merge: row-id range check in the selective tree (2026-11-17)

`duckdb/` (binary `duckdb/build/selective/duckdb`) now = v1.4.4 + counters + selective statistics (occupancy,
nullspace, 3-gram) + predicate cache + **row-id range check** (`PRUNING_ROWID_SKIP=1`, default off; semantics as in
the "Row-id range check" section) + **build-on-load** (`PRUNING_STATS_BUILD_ON_LOAD`, see Step 4 below). Manual merge
of `patches/duckdb-v1.4.4-rowid-range.patch`: `RowGroup::RowIdSkipEnabled` / `CheckColumnZonemap` in
`row_group.{hpp,cpp}`, used by the min/max loop of `RowGroup::CheckZonemap` (before the predicate-cache lookup and
the selective statistics; a rowid-pruned row group has cause 1 = zonemap) and by the counters' attribution
(`PruningScanLocal::OnPruned`, no `optional_idx` for the rowid column); `pruned_rowid_range` / `pruned_rowid_only`
in the scan JSON only when the flag is on. Interaction with the predicate cache: scans with a rowid filter are never
recorded (a static rowid filter makes the scan uncacheable, a dynamic one forces the static re-check, which ignores
the rowid filter), so a rowid-pruned row group is never stored as "no rows".
Full patch: `patches/duckdb-v1.4.4-combined.patch` (complete `src/` diff vs. pristine v1.4.4 = `git archive` of the
v1.4.4 tag; verified: applying it to pristine `src/` reproduces `duckdb/src` exactly; supersedes
`duckdb-v1.4.4-full-selective-predicate-cache.patch`).

Verification (`run_combined_small.sh`, `harness/combined_aggregate.py`, `results/small/phase4/combined/`):
* all flags off, persisted `db/small/clickbench.db`, 1 thread: results 43/43 and all counters of the stock binary's
  fields 43/43 identical to the stock binary (`results/raw/small/rowidexp/stock_count`);
* `PRUNING_ROWID_SKIP=1`: results and counters 43/43 identical to the separate rowid binary; wasted 627 -> 394;
* in-session (phase4.py) each feature alone reproduces the earlier numbers: ng2000 416 wasted, predcache cold 532 /
  warm 233, rowid 394; 1 thread: all 6 configs x 2 passes identical results to the baseline; 8 threads (rowid,
  all; 2 passes): every deterministic query identical, only the known nondeterministic ORDER BY ... LIMIT queries
  vary (as between baseline runs); counter invariants 0 violations.

# Combined small-scale ClickBench experiment (1M rows)

`run_combined_small.sh` (phase4.py `--rowid-skip` is new), one session per config, cache cold at start, pass 1 =
q01..q43, pass 2 = q01..q43, 1 thread. Wasted reads (`scanned_no_rows`) over 43 queries, cold / warm:
baseline 627/627, ng2000 416/416, predcache 532/233, rowid 394/394, ng2000+rowid 183/183, **all 143/0**.
"all" warm reaches 0 wasted reads (predcache 394 + rowid 233 on top of min/max 822). The 143 cold remaining are
q20 6 (`UserID = c`: no statistic on UserID in these configs; occupancy on hits.UserID would prune them), q21 40,
q22 67, q23 30 (3-gram false positives / conjunctions: row groups that contain all trigrams of 'google'/'Google'
but no matching value, or a matching value but no row that also satisfies `SearchPhrase <> ''` / `URL NOT LIKE`;
the predicate cache has no entry yet in the cold pass, q22 uses another key than q21). Per-query tables in
`results/small/phase4/combined/summary.md`. Timing (8 threads, 3 interleaved sessions per config, `run_combined_timing.sh`, machine otherwise idle): warm medians q21 7.8 -> 4.0 ms, q22 7.7 -> 1.7 ms, q23 12.7 -> 10.9 ms (all), the 3-gram and rowid gains (q21-q24) are within ±2 ms at 1M rows; whole-suite sums 520 ms (baseline) vs. 600-630 ms for every other config, including configs that change nothing on most queries (e.g. rowid on q29) -> a systematic session effect/noise, not an overhead of the features (the code path on those queries is a null/bool check). Small-scale timing is not conclusive; see Step 4.

# Step 4 at full scale: persistence of the statistics and build-on-load (prepared, not run)

**Are the statistics persisted?** No. Selective statistics (occupancy, nullspace, 3-gram) live in
`ColumnData::selective` and are built only in `RowGroup::Append` (in-session ingest); a row group deserialized from
a `.db` file has none. The predicate cache is in-memory by design (empty at process start); the row-id range check
needs no state. So querying the persistent Phase 1 databases (`db/large/*.db`) with the old binary would show no
statistic at all.

**Approach (simplest sound one): build on load.** `PRUNING_STATS_BUILD_ON_LOAD=N` (default off; N = threads):
when a table is loaded from disk (`DataTable` constructor, i.e. database open or `ATTACH`) and
`PRUNING_STATS_COLUMNS` selects columns of it, `RowGroupCollection::BuildSelectiveStatsOnLoad` streams the row
groups (N worker threads over disjoint row groups) and, per selected column, scans the committed column data vector
by vector (`ColumnData::ScanCommitted`), feeds the same `SelectiveColumnState::Append`/`Finish` as at ingest, and
attaches the statistic. Memory = the statistics (≈ 1.6 KB per row group for occupancy/nullspace@200, ≤ 16 KB per
row group and column for ng2000) + one row group's buffer per thread; the column data goes through the buffer
manager (evictable, bounded by `memory_limit`). Every stored row is covered (deleted rows too: a superset is safe),
and unlike ingest also the last, partial row group gets a statistic. Logged: a `load_build` record (wall, data
read, per-column totals) on stderr and in `PRUNING_STATS_TIMING`, plus the usual `ingest` record of the ATTACH
statement. Code: `RowGroup::BuildSelectiveStatsFromStorage`, `RowGroupCollection::BuildSelectiveStatsOnLoad`,
`SelectiveStats::BuildOnLoadThreads/LogLoadBuild`, hook in `data_table.cpp`. No side file was needed: rebuilding
costs minutes per process, and persisting would require format changes or a fragile side file keyed by row group.

**Harness:** `phase4.py run --attach-existing` (no ingest; the "ingest" item is `ATTACH db/<scale>/<group>.db
(READ_ONLY)`, after `SET memory_limit`) and `--build-on-load N`. `harness/step4_aggregate.py` → 
`results/<scale>/phase4/step4/` (observed pruning per setup and pass; ATTACH wall / build CPU / key extraction /
data read / bytes; lookup ms per query = selective consultation + predicate-cache lookup; per-query medians and
speedups). `harness/bol_compare.py` compares build-on-load vs. ingest-time statistics.

**Validation (small: ClickBench 1M, micro 10M; `run_bol_small.sh`, `results/small/phase4/build_on_load/`):**
results identical to ingest-time statistics and to the attach baseline for all compared queries (ClickBench
43/43 with 1 and 4 build threads; micro_unsorted/outliers 400/400 each for occupancy@200 with 4 threads and
nullspace@200 with 1 thread); min/max pruning identical; statistic pruning per query either equal or higher by
exactly the last, partial row group (ClickBench ng2000 215 vs. 211; unsorted occ 183,130 vs. 182,955; outliers
identical). Build cost per row group at load ≈ at ingest (occ 5-11 ms, nullspace ≈ 40 ms, URL+Title 3-gram
≈ 200-450 ms under load / ≈ 230 ms quiet); data read 0.1-5 s per 1M-10M rows.
**Dry run** of `run_large_step4.sh` at small scale (`SCALE=small SKIP_WAIT=1 MICRO_SAMPLE=100 SORTED_SAMPLE=100
BUILD_THREADS=4 MEM=2GB`): all 22 runs completed, summary in `results/small/phase4/step4/summary.md`
(e.g. ClickBench new version warm: 0 wasted reads, 8 threads).

**Script:** `run_large_step4.sh` (see its header). Waits for `results/raw/large/DONE6` unless `SKIP_WAIT=1`;
`SKIP_WAIT=1 STEPS=clickbench ./run_large_step4.sh` runs ClickBench only (requires `clickbench.db.json`
`load_threads == 1`). Configs: micro (`micro_unsorted/outliers/sorted`) baseline_step4 vs. occts200_step4 vs.
nsts200_step4 (`sensor_records.timestamp_ms`, @200 = the Phase 4 choice); ClickBench baseline_step4cb vs.
cbnew_step4 (ng2000 URL+Title, predicate cache, row-id range check). count (8 threads; ClickBench 2 passes) and time
(8 threads; micro 3 rounds, ClickBench 4 rounds = cold + 3 warm), one process (= one statistic build) each.

**Estimates** (12 cores, MEM=5GB, BUILD_THREADS=6, nothing else running):
* ClickBench 100M (12,207 row groups): build 3-gram URL+Title 160-240 ms CPU per row group → 33-49 min CPU,
  ≈ 6-10 min wall per process (+ 1-3 min reading URL/Title), 2 builds; statistics ≈ 380 MB in memory → peak
  ≈ 5.5-6 GB RSS. Queries: Phase 1 count pass ≈ 17 min (8 threads) → count 2 passes ≈ 35 min per config, time 4
  rounds ≈ 40-60 min per config. **Total ≈ 3-3.5 h.**
* micro 1B (122,723 row groups per DB): occupancy@200 5-18 ms per row group → 10-37 min CPU → 2-7 min wall;
  nullspace@200 40-75 ms → 1.4-2.6 h CPU → 15-27 min wall; statistics ≈ 195 MB. 3 DBs × 2 modes × (occ + ns)
  ≈ 2-2.5 h of building. Queries (MICRO_SAMPLE=50 → 20 per unsorted/outliers setup, SORTED_SAMPLE=10 → 100 per
  sorted setup): unsorted ≈ 40-50 s per query (Phase 1) → ≈ 1 h count + ≈ 2.5 h time per config ≈ 10-11 h for 3
  configs; outliers ≈ 1.5 h; sorted ≈ 0.3 h. **Total ≈ 14-16 h** (MICRO_SAMPLE=100 → ≈ 9 h; MICRO_KINDS=occupancy
  → ≈ 2/3).

Caveats: `db/large/micro_{unsorted,outliers,sorted}.db` were loaded with 6 threads (122,723 row groups incl. 653
partial ones), not single-threaded; only ClickBench and cardinality_* were reloaded single-threaded
(`MICRO_LOAD_THREADS=1` makes the script skip non-single-threaded micro DBs). Build-on-load also covers partial row
groups (slightly more pruning than ingest-time statistics). Count mode with 8 threads (comparable with the Phase 1
large count) makes top-N/join-filter counters thread-dependent. The rowid check has no separate timer (one
`CheckStatistics` per row group), so "lookup" excludes it. Timing at small scale is ±10-30 % noise.
