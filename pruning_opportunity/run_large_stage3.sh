#!/usr/bin/env bash
# Runs the TPC-H/TPC-DS/ClickBench counting pass after the micro stream has finished (running both at once
# made the micro full scans ~20x slower through page-cache contention), then aggregates.
cd "$(dirname "${BASH_SOURCE[0]}")"
while pgrep -f "run_large_stage[2].sh" >/dev/null; do sleep 30; done
../.venv/bin/python harness/run.py --scale large --count --label count --timeout 7200 --batch 5 --progress --threads 8 --memory-limit 6GB --setups tpch,tpcds,clickbench > results/raw/large/run_established_mt.log 2>&1
../.venv/bin/python harness/aggregate.py --scale large > results/raw/large/aggregate.log 2>&1
echo "ALL DONE $(date)" > results/raw/large/DONE3
