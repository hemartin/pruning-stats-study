#!/usr/bin/env bash
# Final step 1b: chunked single-threaded load of micro_unsorted. A single 1B-row COPY exceeded RAM (OOM kill at 11.5 GB RSS).
# The CSV is split into chunks of 12,207*8,192 rows; each chunk is loaded by a fresh CLI process with 1 thread and committed,
# so the partitions stay aligned at exactly 8,192 rows.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large; D=db/large; S=db/tmp/split_unsorted
B=stock/duckdb/build/release/duckdb
CSV=data/large/micro/unsorted.csv
DB=$D/micro_unsorted.db.building
rm -f $DB $DB.wal; rm -rf $S; mkdir -p $S
t0=$(date +%s)
tail -n +2 $CSV | split -l 99999744 -d -a 2 - $S/part_ || { echo "rc=split $(date)" > $L/DONE_final_s1b; exit 1; }
echo "CREATE TABLE sensor_records(timestamp_ms UBIGINT NOT NULL, sensor_id UBIGINT NOT NULL);" > $S/create.sql
first=1
for p in $S/part_*; do
  { echo "SET threads TO 1; SET memory_limit='4GB'; SET temp_directory='db/tmp'; SET preserve_insertion_order=true;"
    echo "ATTACH '$DB' AS db (ROW_GROUP_SIZE 8192); USE db;"
    [ $first = 1 ] && cat $S/create.sql
    echo "COPY sensor_records FROM '$p' (FORMAT 'csv', header 0, delimiter ',', force_not_null ('timestamp_ms','sensor_id'));"
    echo "CHECKPOINT;"; } | $B -bail :memory: >> $L/db_unsorted_chunked.log 2>&1 || { echo "rc=fail $p $(date)" > $L/DONE_final_s1b; exit 1; }
  first=0; echo "loaded $p $(date)" >> $L/db_unsorted_chunked.log; rm -f $p
done
mv $DB $D/micro_unsorted.db; [ -f $DB.wal ] && mv $DB.wal $D/micro_unsorted.db.wal
t1=$(date +%s)
cat > $D/micro_unsorted.db.json <<J
{"db": "micro_unsorted", "scale": "large", "load_threads": 1, "load_method": "11 committed chunks of 99,999,744 rows, 1 thread each",
 "csv": {"sensor_records": "$(pwd)/$CSV"}, "load_seconds": $((t1-t0)), "binary": "$(pwd)/$B"}
J
echo "rc=0 $(date)" > $L/DONE_final_s1b
