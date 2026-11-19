#!/usr/bin/env bash
# Final step 5: ClickBench counts, 1 thread (deterministic), the queries with wasted reads under min/max
# (q11-q15, q20-q25, q27, q29, q31, q32; plus q30 as listed by the user), in query order.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
Q=q11,q12,q13,q14,q15,q20,q21,q22,q23,q24,q25,q27,q29,q30,q31,q32
NG="hits.URL:ngram:2000,hits.Title:ngram:2000"
P="../.venv/bin/python harness/phase4.py run --scale large --attach-existing --memory-limit 4GB --binary ../duckdb/build/selective/duckdb --timeout 7200 --ingest-timeout 28800 --max-restarts 2 --groups clickbench --qids $Q --mode count --threads 1"
rc=0
$P --config baseline_finalcb >> $L/run_final_s5.log 2>&1 || rc=1
$P --config finalcb_trigram --columns "$NG" --build-on-load 6 >> $L/run_final_s5.log 2>&1 || rc=1
$P --config finalcb_predcache --predicate-cache 1 --passes 2 >> $L/run_final_s5.log 2>&1 || rc=1
$P --config finalcb_rowid --rowid-skip >> $L/run_final_s5.log 2>&1 || rc=1
$P --config finalcb_all --columns "$NG" --build-on-load 6 --predicate-cache 1 --rowid-skip --passes 2 >> $L/run_final_s5.log 2>&1 || rc=1
echo "rc=$rc $(date)" > $L/DONE_final_s5
