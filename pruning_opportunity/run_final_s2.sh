#!/usr/bin/env bash
# Final step 2: stock-binary Step 1 counts, micro_unsorted (single-threaded load), 4 setups x 100 queries (every 10th).
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
../.venv/bin/python harness/run.py --scale large --count --label count_final --timeout 7200 --batch 10 --progress \
  --threads 8 --memory-limit 4GB --sample 10 \
  --setups point_unsorted,range_seconds_unsorted,range_minutes_unsorted,range_hours_unsorted > $L/run_final_s2.log 2>&1
echo "rc=$? $(date)" > $L/DONE_final_s2
