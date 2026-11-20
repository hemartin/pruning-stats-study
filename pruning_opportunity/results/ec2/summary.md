# EC2 timing runs: summary

Times in ms over the timed runs (warm-up runs excluded), from the DuckDB shell's timer (`.timer on`, real time, 1 ms resolution). Wall median = wall clock around each statement in the driver (µs resolution, includes the pipe round trip). Read MB = mean bytes the DuckDB process read from storage per run (`/proc/<pid>/io`). Attach s = ATTACH incl. building the statistics, not part of the query times. Failed runs are counted under Errors and left out of the times.

Note on `C2_bloom200` (Q19 with a Bloom filter on `hits.UserID`, added during the run): it was run after the main run,
Q19 only. In M2 the page cache was dropped before the session (the warm-up run read 0.85 MB from disk), but with no other
query in the session the few unpruned partitions stay in the 6 GB cgroup's page cache, so its M2 timed runs read 0 MB
and are effectively in-memory times. In `C2_statistic` and `C1_baseline`, Q21 evicts Q19's pages between runs.

## M1 · Microbenchmark, unsorted, 1B rows

| Binary | Configuration | Query | Runs | Min | Median | Avg | Max | Wall median | Read MB | Errors | Attach s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock | baseline | point | 100 | 93.0 | 99.0 | 99.8 | 110.0 | 99.34 | 0.0 | 0 | 0.0 |
| stock | baseline | 1 s | 100 | 92.0 | 103.0 | 103.7 | 120.0 | 103.14 | 0.0 | 0 | 0.0 |
| stock | baseline | 1 min | 100 | 176.0 | 187.5 | 187.7 | 199.0 | 187.75 | 0.0 | 0 | 0.0 |
| stock | baseline | 1 h | 100 | 2,065.0 | 2,090.0 | 2,093.1 | 2,138.0 | 2,090.24 | 0.0 | 0 | 0.0 |
| timing | baseline | point | 100 | 90.0 | 100.0 | 99.9 | 108.0 | 99.87 | 0.0 | 0 | 0.0 |
| timing | baseline | 1 s | 100 | 94.0 | 108.0 | 108.2 | 130.0 | 108.20 | 0.0 | 0 | 0.0 |
| timing | baseline | 1 min | 100 | 173.0 | 192.0 | 192.2 | 211.0 | 192.31 | 0.0 | 0 | 0.0 |
| timing | baseline | 1 h | 100 | 2,065.0 | 2,087.5 | 2,089.3 | 2,118.0 | 2,087.75 | 0.0 | 0 | 0.0 |
| timing | bloom200 | point | 100 | 61.0 | 78.0 | 74.6 | 85.0 | 77.69 | 0.0 | 0 | 1.3 |
| timing | occupancy200 | point | 100 | 67.0 | 122.5 | 124.9 | 192.0 | 122.38 | 0.0 | 0 | 37.0 |
| timing | occupancy200 | 1 s | 100 | 82.0 | 127.5 | 130.6 | 182.0 | 127.48 | 0.0 | 0 | 37.0 |
| timing | occupancy200 | 1 min | 100 | 154.0 | 218.5 | 219.8 | 293.0 | 218.66 | 0.0 | 0 | 37.0 |
| timing | occupancy200 | 1 h | 100 | 2,086.0 | 2,149.5 | 2,148.6 | 2,202.0 | 2,149.38 | 0.0 | 0 | 37.0 |
| timing | nullspace200 | point | 100 | 62.0 | 77.0 | 74.6 | 88.0 | 77.17 | 0.0 | 0 | 231.3 |

## M1 · ClickBench Q19, Q21, Q23

| Binary | Configuration | Query | Runs | Min | Median | Avg | Max | Wall median | Read MB | Errors | Attach s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock | C1_baseline | Q19 | 100 | 9.0 | 11.0 | 17.8 | 39.0 | 10.79 | 0.0 | 0 | 0.0 |
| stock | C1_baseline | Q21 | 100 | 209.0 | 231.0 | 230.7 | 253.0 | 230.66 | 0.0 | 0 | 0.0 |
| stock | C1_baseline | Q23 | 100 | 62.0 | 66.0 | 68.3 | 86.0 | 65.67 | 0.0 | 0 | 0.0 |
| timing | C1_baseline | Q19 | 100 | 9.0 | 12.5 | 18.1 | 32.0 | 12.46 | 0.0 | 0 | 0.0 |
| timing | C1_baseline | Q21 | 100 | 214.0 | 226.0 | 227.8 | 251.0 | 226.32 | 0.0 | 0 | 0.0 |
| timing | C1_baseline | Q23 | 100 | 61.0 | 66.0 | 68.0 | 86.0 | 65.65 | 0.0 | 0 | 0.0 |
| timing | C2_statistic | Q19 | 100 | 7.0 | 9.0 | 9.0 | 24.0 | 9.06 | 0.0 | 0 | 108.6 |
| timing | C2_statistic | Q21 | 100 | 145.0 | 159.5 | 160.4 | 186.0 | 159.38 | 0.0 | 0 | 108.6 |
| timing | C2_statistic | Q23 | 100 | 55.0 | 57.5 | 59.7 | 76.0 | 57.69 | 0.0 | 0 | 108.6 |
| timing | C2_bloom200 | Q19 | 100 | 4.0 | 5.0 | 5.0 | 7.0 | 4.67 | 0.0 | 0 | 1.7 |
| timing | C3_all_repeat | Q19 | 100 | 7.0 | 8.0 | 8.1 | 10.0 | 8.38 | 0.0 | 0 | 107.4 |
| timing | C3_all_repeat | Q21 | 100 | 20.0 | 22.0 | 21.8 | 23.0 | 21.94 | 0.0 | 0 | 107.4 |
| timing | C3_all_repeat | Q23 | 100 | 35.0 | 37.0 | 36.7 | 39.0 | 36.79 | 0.0 | 0 | 107.4 |

## M2 · Microbenchmark, unsorted, 1B rows

| Binary | Configuration | Query | Runs | Min | Median | Avg | Max | Wall median | Read MB | Errors | Attach s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock | baseline | point | 100 | 8,949.0 | 9,913.5 | 9,937.5 | 11,887.0 | 9,913.74 | 6,711.9 | 0 | 0.0 |
| stock | baseline | 1 s | 100 | 8,930.0 | 9,811.0 | 9,835.9 | 11,066.0 | 9,811.17 | 6,631.5 | 0 | 0.0 |
| stock | baseline | 1 min | 100 | 9,007.0 | 9,699.5 | 9,723.4 | 11,192.0 | 9,699.47 | 6,498.5 | 0 | 0.0 |
| stock | baseline | 1 h | 100 | 10,894.0 | 11,516.5 | 11,590.6 | 12,734.0 | 11,516.89 | 6,486.7 | 0 | 0.0 |
| timing | baseline | point | 100 | 8,914.0 | 9,679.0 | 9,735.2 | 11,967.0 | 9,679.10 | 6,523.9 | 0 | 0.0 |
| timing | baseline | 1 s | 100 | 8,999.0 | 9,910.0 | 9,833.9 | 11,003.0 | 9,909.80 | 6,579.3 | 0 | 0.0 |
| timing | baseline | 1 min | 100 | 9,081.0 | 10,033.0 | 10,012.1 | 11,074.0 | 10,032.87 | 6,648.3 | 0 | 0.0 |
| timing | baseline | 1 h | 100 | 10,976.0 | 11,761.0 | 11,767.7 | 12,892.0 | 11,760.88 | 6,558.1 | 0 | 0.0 |
| timing | bloom200 | point | 100 | 4,375.0 | 5,963.0 | 5,856.6 | 6,525.0 | 5,963.45 | 6,165.4 | 0 | 12.3 |
| timing | occupancy200 | point | 100 | 4,346.0 | 5,934.5 | 5,862.8 | 6,583.0 | 5,935.19 | 6,171.6 | 0 | 38.4 |
| timing | occupancy200 | 1 s | 100 | 5,289.0 | 5,881.0 | 5,860.4 | 6,570.0 | 5,881.28 | 6,159.4 | 0 | 38.4 |
| timing | occupancy200 | 1 min | 100 | 4,573.0 | 6,031.0 | 6,155.6 | 7,826.0 | 6,031.17 | 6,428.5 | 0 | 38.4 |
| timing | occupancy200 | 1 h | 100 | 11,025.0 | 11,947.0 | 11,940.4 | 13,019.0 | 11,947.08 | 6,641.5 | 0 | 38.4 |
| timing | nullspace200 | point | 100 | 3,781.0 | 5,303.5 | 5,284.0 | 5,917.0 | 5,303.73 | 5,564.6 | 0 | 234.6 |

## M2 · ClickBench Q19, Q21, Q23

| Binary | Configuration | Query | Runs | Min | Median | Avg | Max | Wall median | Read MB | Errors | Attach s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock | C1_baseline | Q19 | 100 | 200.0 | 759.5 | 735.1 | 831.0 | 759.98 | 498.0 | 0 | 0.0 |
| stock | C1_baseline | Q21 | 100 | 6,558.0 | 12,304.0 | 12,170.7 | 13,921.0 | 12,303.59 | 7,835.9 | 0 | 0.0 |
| stock | C1_baseline | Q23 | 100 | 641.0 | 1,124.0 | 1,102.8 | 1,272.0 | 1,124.59 | 704.2 | 0 | 0.0 |
| timing | C1_baseline | Q19 | 100 | 172.0 | 756.5 | 753.2 | 829.0 | 756.88 | 494.4 | 0 | 0.0 |
| timing | C1_baseline | Q21 | 100 | 11,646.0 | 12,428.0 | 12,521.9 | 13,705.0 | 12,427.93 | 7,832.4 | 0 | 0.0 |
| timing | C1_baseline | Q23 | 100 | 960.0 | 1,080.0 | 1,083.2 | 1,224.0 | 1,079.79 | 672.8 | 0 | 0.0 |
| timing | C2_statistic | Q19 | 100 | 8.0 | 10.0 | 9.8 | 12.0 | 9.77 | 18.0 | 0 | 110.7 |
| timing | C2_statistic | Q21 | 100 | 3,686.0 | 6,375.0 | 6,133.4 | 7,923.0 | 6,374.81 | 4,361.2 | 0 | 110.7 |
| timing | C2_statistic | Q23 | 100 | 217.0 | 393.5 | 387.0 | 538.0 | 393.23 | 265.3 | 0 | 110.7 |
| timing | C2_bloom200 | Q19 | 100 | 7.0 | 8.0 | 8.3 | 9.0 | 8.54 | 0.0 | 0 | 2.4 |
| timing | C3_all_repeat | Q19 | 100 | 7.0 | 9.0 | 8.5 | 10.0 | 8.69 | 0.0 | 0 | 111.0 |
| timing | C3_all_repeat | Q21 | 100 | 20.0 | 26.5 | 27.2 | 179.0 | 26.82 | 3.5 | 0 | 111.0 |
| timing | C3_all_repeat | Q23 | 100 | 35.0 | 39.0 | 38.5 | 47.0 | 39.05 | 0.4 | 0 | 111.0 |

