#!/usr/bin/env bash
# Timing, ClickBench Q19, Q21, Q23 (0-based; harness ids q20, q22, q24). 8 threads, counters off, 1 session per config,
# 11 rounds round-robin (round 1 = warm-up, discarded; rounds 2-11 = the 10 timed runs). Run one config at a time.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
P="../.venv/bin/python harness/phase4.py run --scale large --attach-existing --memory-limit 5GB --binary ../duckdb/build/selective/duckdb --timeout 7200 --ingest-timeout 28800 --max-restarts 2 --groups clickbench --qids q20,q22,q24 --mode time --threads 8 --rounds 11 --sessions 1"
rc=0
$P --config baseline_time_cb >> $L/run_time_cb.log 2>&1 || rc=1
$P --config time_cb_all2 --columns "hits.URL:ngram:2000,hits.Title:ngram:2000,hits.UserID:nullspace:200" --build-on-load 6 --predicate-cache 1 --rowid-skip >> $L/run_time_cb.log 2>&1 || rc=1
echo "rc=$rc $(date)" > $L/DONE_time_cb
