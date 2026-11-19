# Build-on-load vs. ingest-time statistics: micro_unsorted (small)

load = `bol_nsts200` (persistent DB attached read-only, statistics built by ATTACH), ingest = `ns200` (in-session COPY), base = `baseline_bol` (attach, no statistics).

* queries compared: 400; results identical load vs. ingest 400, load vs. base 400/400
* min/max pruning differs in 0 queries
* pruned by the statistic: load 79130, ingest 79055; per query equal 325, load = ingest + last partial row group(s) 75, other 0
* wasted reads (scanned_no_rows): load 265820, ingest 265895
* load_build: table sensor_records, 1221 row groups, 1 thread(s), wall 48623 ms, data read 672 ms; timestamp_ms nullspace@200: 1221 stats, 1945120 bytes, build 47876 ms, key extraction 16 ms
* load (ATTACH statement): timestamp_ms nullspace: 1221 statistics, build 47876 ms (39.2 ms per row group), key extraction 16 ms, 1945120 bytes
* ingest (COPY): timestamp_ms nullspace: 1220 statistics, build 90667 ms (74.3 ms per row group), key extraction 44 ms, 1943520 bytes
