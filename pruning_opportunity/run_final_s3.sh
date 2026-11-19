#!/usr/bin/env bash
# Final step 3: ground truth for the step-2 counts (20 queries per unsorted setup, one SQL scan per setup).
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
../.venv/bin/python validate_final.py --label count_final --per-setup 20 > $L/run_final_s3.log 2>&1
echo "rc=$? $(date)" > $L/DONE_final_s3
