#!/usr/bin/env bash
# Runs steps 3-5 one after another once step 2 has written its DONE file.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
until [ -f $L/DONE_final_s2 ]; do sleep 60; done
./run_final_s3.sh; ./run_final_s4.sh; ./run_final_s5.sh
echo "done $(date)" > $L/DONE_final_chain
