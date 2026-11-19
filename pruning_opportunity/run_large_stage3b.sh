#!/usr/bin/env bash
# ClickBench counting only (TPC-H done; TPC-DS stopped at the user's request, finished queries kept), then lets
# run_large_stage4.sh (cardinality rebuild) proceed by writing DONE3.
cd "$(dirname "${BASH_SOURCE[0]}")"
../.venv/bin/python harness/run.py --scale large --count --label count --timeout 7200 --batch 5 --progress --threads 8 --memory-limit 6GB --setups clickbench > results/raw/large/run_clickbench_mt.log 2>&1
echo "ALL DONE $(date)" > results/raw/large/DONE3
