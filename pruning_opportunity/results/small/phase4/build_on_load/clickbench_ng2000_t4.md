# Build-on-load vs. ingest-time statistics: clickbench (small)

load = `bol_ng2000_t4` (persistent DB attached read-only, statistics built by ATTACH), ingest = `cmb_ng2000` (in-session COPY), base = `baseline_bol` (attach, no statistics).

* queries compared: 43; results identical load vs. ingest 43, load vs. base 43/43
* min/max pruning differs in 0 queries
* pruned by the statistic: load 215, ingest 211; per query equal 39, load = ingest + last partial row group(s) 4, other 0
* wasted reads (scanned_no_rows): load 412, ingest 416
* load_build: table hits, 123 row groups, 4 thread(s), wall 14904 ms, data read 5659 ms; title ngram@2000: 123 stats, 1891024 bytes, build 11448 ms, key extraction 548 ms; url ngram@2000: 123 stats, 1967880 bytes, build 40967 ms, key extraction 349 ms
* load (ATTACH statement): title ngram: 123 statistics, build 11448 ms (93.1 ms per row group), key extraction 548 ms, 1891024 bytes
* load (ATTACH statement): url ngram: 123 statistics, build 40967 ms (333.1 ms per row group), key extraction 349 ms, 1967880 bytes
* ingest (COPY): title ngram: 122 statistics, build 5181 ms (42.5 ms per row group), key extraction 264 ms, 1884824 bytes
* ingest (COPY): url ngram: 122 statistics, build 19988 ms (163.8 ms per row group), key extraction 217 ms, 1951880 bytes
