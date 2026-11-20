# EC2 timing experiments: plan (decisions of 19 Nov 2026 included)

Goal: execution times (min / median / avg / max in ms over 100 runs) for the pruning strategies of the study, on a
dedicated EC2 machine, once with all data in memory and once with memory restricted so that data is read from disk.
Pruning counts are final (see the "Self-Tuning Partition Pruning" report); this run measures time only.

## 1. Machine

| | |
|---|---|
| Instance | `m8a.4xlarge`, eu-central-1, on-demand ($1.17/h) |
| CPU / RAM | 16 physical cores (AMD, 4.5 GHz, no SMT), 64 GiB |
| Storage | EBS gp3, 200 GB, provisioned at the gp3 maximum: 16,000 IOPS, 1,000 MB/s (no local NVMe on m8a) |
| OS | Ubuntu 24.04 LTS (x86_64) |
| Data | from `s3://pruning-opportunity-919341187522-eu-central-1-an/pruning_opportunity/db/large/` |

Recorded with every result: instance type, kernel, CPU model (`lscpu`), EBS settings, git commit, DuckDB version.
The instance shuts itself down after the last run.

## 2. Binaries (no counting instrumentation)

The timing binary must not carry the wasted-partition counters. Two binaries are built on the instance:

1. **`stock`**: unmodified DuckDB v1.4.4 (`git clone --branch v1.4.4`, no patch). Runs the min/max baselines only.
   It shows that the study binary with all statistics off is as fast as stock DuckDB.
2. **`timing`**: the repository's `duckdb/` tree from a new branch `ec2-timing`, branched from `pruning-opportunity`, with
   - the pruning-counter commit (`8a91c0e`, `DUCKDB_PRUNING_STATS`) reverted, so `PruningScanLocal` and the hooks in
     `table_scan.cpp`, `row_group.cpp`, `executor.cpp`, `client_context.cpp` and `duck_table_entry.cpp` are gone;
   - the per-consultation `steady_clock` calls and atomic counters in `RowGroup::CheckZonemap` and the
     `PRUNING_STATS_TIMING` statement log removed (they run on every row group check when statistics are on);
   - a new statistic kind **`bloom`** (see 3.1).

   What stays: the selective statistics (`occupancy`, `nullspace`, `ngram`, `bloom`), the predicate cache
   and the row-id check, all off unless their environment variables are set.

Both binaries are built release, with `-DOVERRIDE_GIT_DESCRIBE=v1.4.4`, without unit tests.

## 3. Experiments

### 3.1 Microbenchmark (DBTest paper dataset, unsorted only)

- Table `sensor_records`, 1,000,000,000 rows, `timestamp_ms` uniform over 30 days in random order, loaded with one
  thread: 122,071 partitions of 8,192 rows (`db/large/micro_unsorted.db`, 8.1 GB).
- Queries: the paper's `SELECT * FROM sensor_records WHERE ...`, four setups:
  point `timestamp_ms = x`; ranges of 1 s, 1 min, 1 h (`timestamp_ms >= x AND timestamp_ms <= x + w`).
- 100 runs per cell = the 100 queries per setup already used for the counts (every 10th of 1,000), each executed once.
- Statistics on `sensor_records.timestamp_ms`, all at the paper's 100× budget only (200 words = 1.6 KB per partition):

| Configuration | Point | 1 s | 1 min | 1 h |
|---|---|---|---|---|
| min/max baseline (`stock` and `timing` without statistics) | ✓ | ✓ | ✓ | ✓ |
| Bloom filter@200 | ✓ | – | – | – |
| Occupancy@200 | ✓ | ✓ | ✓ | ✓ |
| Nullspace@200 | ✓ | – | – | – |

  Bloom filter and nullspace answer equality only, so they get no range runs (as in the paper's Figure 2).
- **Bloom filter**: a port of the paper's `BloomAdditionalStats`
  (`additional/bloom_additional_stats.hpp`: `std::hash` → MurmurHash3, blocked, k bits per value) into the
  selective-statistics framework as kind `bloom`, at 200 words. Check before EC2 (locally, with the counting
  binary on 20 point queries): it prunes about the paper's 64,365 partitions per query.

### 3.2 ClickBench (DBTest paper dataset)

- `hits`, 99,997,497 rows, loaded with one thread: 12,207 partitions (`db/large/clickbench.db`, 25.9 GB).
- Queries Q19, Q21, Q23 (0-based ClickBench numbering), each run 100 times after 1 untimed warm-up run.

| Configuration | Q19 | Q21 | Q23 |
|---|---|---|---|
| C1: min/max baseline (`stock` and `timing` without statistics) | ✓ | ✓ | ✓ |
| C2: + statistic: nullspace@200 on `hits.UserID`, trigram@2000 on `hits.URL` and `hits.Title` | ✓ | ✓ | ✓ |
| C3: C2 + row-id check + predicate cache (repeat) | ✓ | ✓ | ✓ |

  In C3 the warm-up run fills the predicate cache, so all 100 timed runs are repeat runs.

  Added during the run (20 Nov): **C2b, Q19 only: Bloom filter@200 on `hits.UserID`**, the configuration of the
  paper's Table 3 (local check with the counting binary: 9,458 + 2,291 = 11,749 pruned partitions; paper: 11,748). It
  runs in M1 and M2 after the main run.

### 3.3 Memory configurations

Every cell above runs in both configurations:

| | M1: all memory | M2: restricted memory, reads from disk |
|---|---|---|
| DuckDB `memory_limit` | 50 GB (DuckDB default: 80% of RAM) | 2 GB |
| OS limit | none | cgroup `MemoryMax=6G`, `MemorySwapMax=0`, which also limits the page cache |
| Before a session | warm-up: one query that reads every column of the table | `sync; echo 3 > /proc/sys/vm/drop_caches`, and the database file's pages evicted (`posix_fadvise DONTNEED`) |
| Check | disk reads during the timed runs ≈ 0 | disk reads per run > 0 for the baseline |

Disk reads are taken from `/proc/<pid>/io` (`read_bytes`) before and after each run. That is OS-level, with no DuckDB
change. They are reported next to the times, so the table shows which runs really went to disk.

Why 6 GB in total: DuckDB's `memory_limit` only caps the memory its buffer manager tracks. In the dry run on the
full-size databases, the DuckDB process used up to 4.3 GB at a 2 GB limit (16 threads), so a 3 GB cgroup killed it
(out of memory) during Q21, Q23 and the 1 h range. At 6 GB the peak was 4.3 GB and every query still read from
disk on every run: 7.8–8.1 GB per micro query, about 0.4 GB (Q19), 9.8 GB (Q21) and 0.2 GB (Q23) per ClickBench
query. The statistics' memory (up to ~0.2 GB) counts against the 6 GB. Each M2 session records the cgroup's memory
split (DuckDB memory, page cache, peak).

Known limitation of M2: the columns of Q19 and Q23 are small enough to be partly cached between runs; the disk
bytes per run show how much was cached.

## 4. Measurement protocol

- One DuckDB shell session per (dataset, configuration, memory mode, binary): `ATTACH` the database read-only,
  build the statistics (build-on-load with 16 threads; build time is reported separately and is **not** part of
  the query times), warm-up, then the 100 timed runs.
- Query time = the shell's `.timer on` "real" time. Results are discarded with `.mode trash`, so
  printing 1.4 M rows of a 1 h range does not count.
- Threads: `SET threads = 16`, all physical cores of the m8a.4xlarge (the local runs used 8). Query order is fixed.
- Per cell: min, median, avg, max (ms), plus mean disk read bytes per run; per-run CSV
  `results/ec2/<mode>/<dataset>/<binary>_<config>_<setup>.csv`, summary `results/ec2/summary.md`.
- Results stay on the instance's EBS volume and are copied to S3 (`.../results/ec2/`) after each session, so a
  crash loses at most one session.

## 5. Order of work

1. **Local, no EC2 cost:**
   - branch `ec2-timing`: revert the counters, remove the consultation timing, add `bloom`; build; check that results and
     the 20-query Bloom count match (with the counting binary);
   - scripts: `ec2_setup.sh` (packages, EBS mount, S3 copy, both builds, venv), `ec2_run.sh` (all sessions,
     resumable, copies results to S3, shuts down at the end), `ec2_aggregate.py` (summary tables);
   - dry run at small scale (`db/small`) in both memory modes.
2. **EC2:** launch, run `ec2_setup.sh`, then `ec2_run.sh` in `tmux`; first M1, then M2.
3. **Local:** download the results from S3, aggregate them, commit the per-run CSVs, `summary.md` and the run
   metadata to the `ec2-timing` branch (under `pruning_opportunity/results/ec2/`), then add them to the report.

## 6. Time and cost estimate

| Phase | Time |
|---|---|
| Setup (packages, S3 copy of 34 GB, two DuckDB builds on 16 cores) | ~0.75 h |
| Statistics builds at ATTACH (per session: occupancy ~1 min, nullspace ~8 min, Bloom ~1–2 min, trigrams ~4 min; once per memory mode) | ~0.75 h |
| M1, all memory (queries well under 1 s each) | ~0.5 h |
| M2, restricted memory (micro baseline ~8 s per query from EBS at 1 GB/s; ClickBench Q21 baseline ~10 s) | ~2.5 h |
| Slack for problems | ~1.5 h |
| **Total** | **~6 h** |

Cost: ~6 h × $1.17 ≈ **$7** instance + ~$1.50 EBS (200 GB gp3 with 16,000 IOPS and 1,000 MB/s: $139/month, i.e.
$4.60 per day while the volume exists, also when the instance is stopped; terminate it after the run) + S3 ~$1.30/month.
A full repeat roughly doubles the instance part.

## 7. Decisions

1. **Microbenchmark runs:** the 100 queries per setup used for the counts (every 10th of 1,000), each once.
2. **Threads:** all 16 cores.
3. **M2 memory:** DuckDB `memory_limit` 2 GB, cgroup `MemoryMax` 6 GB in total (3 GB was approved first; the dry run
   showed DuckDB needs more than 3 GB at a 2 GB limit, see 3.3).
4. **Stock v1.4.4 baseline:** included (min/max baselines in M1 and M2).
5. **Bloom filter:** 100× only (200 words).
