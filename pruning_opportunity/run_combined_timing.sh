#!/usr/bin/env bash
# Timing of the combined small-scale ClickBench configs: 3 repetitions ("", _b, _c), interleaved by config,
# each one session (ingest + 4 rounds: round 1 cold, rounds 2-4 warm), 8 threads; then combined_aggregate.py.
cd "$(dirname "${BASH_SOURCE[0]}")"
PY=../.venv/bin/python
SEL=../duckdb/build/selective/duckdb
CLEAN="env -u PRUNING_STATS_COLUMNS -u PRUNING_PREDICATE_CACHE -u PRUNING_ROWID_SKIP -u PRUNING_STATS_BUILD_ON_LOAD -u PRUNING_STATS_TIMING"
NG="--columns hits.URL:ngram:2000,hits.Title:ngram:2000"
T="harness/phase4.py run --scale small --groups clickbench --memory-limit 1500MB --binary $SEL --mode time --threads 8 --rounds 4 --sessions 1"
for s in "" _b _c; do
  $CLEAN $PY $T --config baseline_cmb_time$s
  $CLEAN $PY $T --config cmb_ng2000_time$s $NG
  $CLEAN $PY $T --config cmb_predcache_time$s --predicate-cache 1
  $CLEAN $PY $T --config cmb_rowid_time$s --rowid-skip
  $CLEAN $PY $T --config cmb_ng2000_rowid_time$s $NG --rowid-skip
  $CLEAN $PY $T --config cmb_all_time$s $NG --predicate-cache 1 --rowid-skip
done
$PY harness/combined_aggregate.py > /dev/null
