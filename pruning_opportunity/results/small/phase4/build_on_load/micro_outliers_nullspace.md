# Build-on-load vs. ingest-time statistics: micro_outliers (small)

load = `bol_nsts200` (persistent DB attached read-only, statistics built by ATTACH), ingest = `ns200` (in-session COPY), base = `baseline_bol` (attach, no statistics).

* queries compared: 400; results identical load vs. ingest 400, load vs. base 400/400
* min/max pruning differs in 0 queries
* pruned by the statistic: load 36139, ingest 36139; per query equal 400, load = ingest + last partial row group(s) 0, other 0
* wasted reads (scanned_no_rows): load 186065, ingest 186065
* load_build: table sensor_records, 1221 row groups, 1 thread(s), wall 50031 ms, data read 967 ms; timestamp_ms nullspace@200: 1221 stats, 1953152 bytes, build 48988 ms, key extraction 16 ms
* load (ATTACH statement): timestamp_ms nullspace: 1221 statistics, build 48988 ms (40.1 ms per row group), key extraction 16 ms, 1953152 bytes
* ingest (COPY): timestamp_ms nullspace: 1220 statistics, build 92088 ms (75.5 ms per row group), key extraction 39 ms, 1951552 bytes
