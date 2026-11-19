# Build-on-load vs. ingest-time statistics: micro_outliers (small)

load = `bol_occts200` (persistent DB attached read-only, statistics built by ATTACH), ingest = `occ200` (in-session COPY), base = `baseline_bol` (attach, no statistics).

* queries compared: 400; results identical load vs. ingest 400, load vs. base 400/400
* min/max pruning differs in 0 queries
* pruned by the statistic: load 222114, ingest 222114; per query equal 400, load = ingest + last partial row group(s) 0, other 0
* wasted reads (scanned_no_rows): load 90, ingest 90
* load_build: table sensor_records, 1221 row groups, 4 thread(s), wall 2314 ms, data read 3008 ms; timestamp_ms occupancy@200: 1221 stats, 1947896 bytes, build 6097 ms, key extraction 33 ms
* load (ATTACH statement): timestamp_ms occupancy: 1221 statistics, build 6097 ms (5.0 ms per row group), key extraction 33 ms, 1947896 bytes
* ingest (COPY): timestamp_ms occupancy: 1220 statistics, build 11552 ms (9.5 ms per row group), key extraction 51 ms, 1946296 bytes
