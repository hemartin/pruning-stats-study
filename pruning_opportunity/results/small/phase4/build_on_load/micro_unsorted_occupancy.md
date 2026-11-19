# Build-on-load vs. ingest-time statistics: micro_unsorted (small)

load = `bol_occts200` (persistent DB attached read-only, statistics built by ATTACH), ingest = `occ200` (in-session COPY), base = `baseline_bol` (attach, no statistics).

* queries compared: 400; results identical load vs. ingest 400, load vs. base 400/400
* min/max pruning differs in 0 queries
* pruned by the statistic: load 183130, ingest 182955; per query equal 225, load = ingest + last partial row group(s) 175, other 0
* wasted reads (scanned_no_rows): load 161820, ingest 161995
* load_build: table sensor_records, 1221 row groups, 4 thread(s), wall 4041 ms, data read 2280 ms; timestamp_ms occupancy@200: 1221 stats, 1943840 bytes, build 13705 ms, key extraction 41 ms
* load (ATTACH statement): timestamp_ms occupancy: 1221 statistics, build 13705 ms (11.2 ms per row group), key extraction 41 ms, 1943840 bytes
* ingest (COPY): timestamp_ms occupancy: 1220 statistics, build 18733 ms (15.4 ms per row group), key extraction 46 ms, 1942240 bytes
