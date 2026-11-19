#!/usr/bin/env bash
# Final step 6: exact ceilings for q21-q24 (plain SQL, one scan of clickbench.db). Waits for steps 3-5.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
until [ -f $L/DONE_final_chain ]; do sleep 60; done
../.venv/bin/python ceilings_final.py > $L/run_final_s6.log 2>&1
echo "rc=$? $(date)" > $L/DONE_final_s6
