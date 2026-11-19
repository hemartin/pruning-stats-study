#!/usr/bin/env bash
# Build-on-load validation at small scale (ClickBench 1M rows, micro 10M rows): statistics built while ATTACH loads
# the persistent db/small/*.db (PRUNING_STATS_BUILD_ON_LOAD, phase4.py --attach-existing --build-on-load N) vs. the
# statistics built at in-session ingest (earlier runs cmb_ng2000, occ200, ns200), counting passes with 1 thread.
# -> results/small/phase4/build_on_load/*.md (harness/bol_compare.py)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY=../.venv/bin/python
SEL=../duckdb/build/selective/duckdb
CLEAN="env -u PRUNING_STATS_COLUMNS -u PRUNING_PREDICATE_CACHE -u PRUNING_ROWID_SKIP -u PRUNING_STATS_BUILD_ON_LOAD -u PRUNING_STATS_TIMING"
P="harness/phase4.py run --scale small --attach-existing --memory-limit 1500MB --binary $SEL --mode count"
NG="hits.URL:ngram:2000,hits.Title:ngram:2000"
O=results/small/phase4/build_on_load

$CLEAN $PY $P --groups clickbench --config baseline_bol
$CLEAN $PY $P --groups clickbench --config bol_ng2000 --columns "$NG" --build-on-load 1
$CLEAN $PY $P --groups clickbench --config bol_ng2000_t4 --columns "$NG" --build-on-load 4
for g in micro_unsorted micro_outliers; do
  $CLEAN $PY $P --groups $g --limit 100 --config baseline_bol
  $CLEAN $PY $P --groups $g --limit 100 --config bol_occts200 --columns sensor_records.timestamp_ms:occupancy:200 --build-on-load 4
  $CLEAN $PY $P --groups $g --limit 100 --config bol_nsts200 --columns sensor_records.timestamp_ms:nullspace:200 --build-on-load 1
done

$PY harness/bol_compare.py --group clickbench --load-config bol_ng2000 --ingest-config cmb_ng2000 --base-config baseline_bol --out $O/clickbench_ng2000.md
$PY harness/bol_compare.py --group clickbench --load-config bol_ng2000_t4 --ingest-config cmb_ng2000 --base-config baseline_bol --out $O/clickbench_ng2000_t4.md
for g in micro_unsorted micro_outliers; do
  $PY harness/bol_compare.py --group $g --load-config bol_occts200 --ingest-config occ200 --base-config baseline_bol --out $O/${g}_occupancy.md
  $PY harness/bol_compare.py --group $g --load-config bol_nsts200 --ingest-config ns200 --base-config baseline_bol --out $O/${g}_nullspace.md
done
