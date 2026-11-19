# 3-gram statistic, budget 2000 words (`ng2000` = `hits.URL:ngram:2000,hits.Title:ngram:2000`, n = 3): validation

Small scale (ClickBench 1M rows, 123 row groups of 8,192 rows). Only 3-gram statistics were used. Numbers in
`validation.csv`; the pruning effect of ng200/ng2000/ng20000 is in `summary.md` (same directory).

## (a) Results identical to the baseline (all 43 ClickBench queries)

| run | threads | binary | result vs. baseline |
|---|---|---|---|
| `ng2000` count vs `baseline_ng` count | 1 | pre-predicate-cache build | 43/43 identical (row count + order-independent hash); per-scan counters `total_row_groups`, `pruned_minmax`, `scanned_with_rows`, `rows_passed`, ... equal; 0 invariant violations |
| `ng2000_pc` count, cold + warm pass in one session, vs `baseline_pc` | 1 | current build (cache off) | 86/86 identical |
| `ng2000_t8` check vs `baseline_t8`, `baseline_t8b` (+ `baseline_pc_t8{,b}`, 2 passes each) | 8 | pre / current | all 32 deterministic queries identical; the 11 queries on which the 6 baseline samples disagree among themselves (q12, q18, q19, q23, q25, q31, q32, q33, q39, q40, q41: ties under `ORDER BY ... LIMIT`, `LIMIT` without `ORDER BY`) have the same row count in every run, and their content differs between baseline runs as much as from ng2000 |
| `ng2000_pc_t8` check, cold + warm pass | 8 | current | same: every deterministic query identical in both passes; differences only in the nondeterministic set |
| `ng2000` check | 3 | pre | same (34/43 equal to the first baseline run, rest in the nondeterministic set) |

## (b) Randomized LIKE / contains self-test (`phase4_selftest.py --suite ngram`)

Table of 48 full row groups with row-group-specific token vocabularies (multibyte UTF-8, `%`, `_`, `\`, `!`, `'`,
empty strings, 1-2 byte strings, NULLs, all-NULL and all-short row groups, a column with no trigram at all), global
extremes in every row group so that min/max never prunes. 3,000 random queries + UPDATE / DELETE / INSERT + 300 more,
shapes: `contains`, `LIKE '%a%'` with raw `%`/`_` inside, `LIKE ... ESCAPE`, `%a_b%`, `_a%`, prefix/suffix LIKE,
`prefix`/`starts_with`/`suffix`/`ends_with`, `NOT LIKE`, `ILIKE`, `regexp_matches`, `GLOB`, `=`, `IN`, `AND`, `OR`,
`OR col IS NULL`, ranges, and constant patterns (`contains(col, NULL)`, `LIKE NULL`, `LIKE '%'`, `LIKE ''`,
`contains(col, '')`, `LIKE '_'`, `LIKE '%_%'`, `NOT LIKE '%'`, ...). Among the 3,300 queries: 244 with an empty
literal, 1,396 whose literal has fewer than 3 bytes after removing wildcards (no trigram), 1,854 with upper-case
characters (case variants: upper / lower / swapped / capitalised literal, ILIKE), 1,712 LIKE with `_`, 5 NULL patterns.

| threads | configs (n = 3) | queries | results different from no-statistics baseline | statistics built | consultations | row groups pruned |
|---|---|---|---|---|---|---|
| 1 | ng3w20, ng3w200, ng3w2000 | 3,301 each | 0 | 196 | 147,485 | 67,379 |
| 8 | ng3w20, ng3w200, ng3w2000 | 3,301 each | 0 | 192-196 | ~149,300 | 68,334-68,499 |

Since the selftest compares complete query results (count, min/max/sum of the row id, `ORDER BY i LIMIT 5` rows)
with the run without statistics, no pruned row group contained a matching row. On ClickBench additionally every
pruned row group of q21-q24 has 0 qualifying rows in the plain-SQL ground truth (`partitions_ng2000.csv`,
column `pruned_with_rows` = 0). Logs: `results/raw/small/phase4/selftest_ng3/t{1,8}/`.

## (c) Ingest and lookup cost (ng2000)

| | value |
|---|---|
| COPY 1M rows, baseline (in-session, single-threaded load) | 8.2 / 10.8 / 13.5 s (3 sessions) |
| COPY 1M rows, ng2000 | 26.7 / 26.9 / 34.5 / 38.0 / 38.1 s (5 sessions) |
| statistic build, URL (122 row groups) | 15.0-20.3 s = 123-166 ms per row group (sort/dedup of ~14k-33k distinct trigrams + encoding) |
| statistic build, Title | 3.6-4.9 s = 30-40 ms per row group |
| key buffering (URL + Title) | 0.34-0.46 s per COPY |
| statistic size | URL 1,951,880 B, Title 1,884,824 B (≈ 16 KB per row group and column) |
| lookup (consult) per row group, single thread | 20-25 µs (q21-q24: `consult_ns / consultations`) |
| query time q21 / q22 / q23 / q24 (1 thread, counting run) | 32 / 25 / 47 / 47 ms vs. baseline 40 / 34 / 47 / 59 ms |

The build (on the loading thread) roughly triples the COPY time of this 1M-row table; the lookup cost is below the cost of scanning a row group's URL column.
