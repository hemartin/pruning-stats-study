#!/usr/bin/env python3
"""Timing runs of the pruning study (plan: pruning_opportunity/ec2-experiment-plan.md).

One DuckDB shell session per (memory mode, dataset, binary, configuration). Each session attaches its database
read-only (the statistics are built during ATTACH, timed separately), optionally warms up, then runs the timed
queries one statement at a time through a pipe. Per run it records the shell's own timer (".timer on", real time),
a wall-clock time measured around the statement, and the bytes the DuckDB process read from storage
(/proc/<pid>/io read_bytes, OS-level, no DuckDB change). Results are discarded with ".mode trash".

Memory modes:
  M1  all memory: DuckDB memory_limit --m1-memory (default 50GB), no OS limit, one untimed warm-up query that
      reads every column of the table before the timed queries.
  M2  restricted: DuckDB memory_limit --m2-memory (default 2GB), the process runs in a systemd scope with
      MemoryMax=--m2-cgroup (default 3G, includes the page cache) and no swap; before the session the page cache
      is dropped (needs passwordless sudo; otherwise a warning is recorded) and the database file's pages are
      evicted with posix_fadvise(DONTNEED) (pages cached before the session are not charged to the cgroup).

Output (resumable: sessions with session.json "done": true are skipped):
  <out>/<mode>/<dataset>/<binary>_<config>/runs.csv      one row per timed run
  <out>/<mode>/<dataset>/<binary>_<config>/session.json  settings, attach/build time, warm-up, host, errors
  <out>/host.json                                        instance and software information

Examples:
  ec2_timing.py --mode M1 --db-dir ~/data/db/large --out ~/results/ec2 \\
      --stock-binary ~/duckdb-stock/build/release/duckdb --timing-binary ~/repo/duckdb/build/timing/duckdb
  ec2_timing.py --mode M2 ... --only micro          # only sessions whose name contains "micro"
  ec2_timing.py --list                              # print the session matrix
"""
import argparse
import csv
import json
import os
import platform
import queue
import re
import select
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "harness"))
import common  # noqa: E402

MICRO_SETUPS = ["point_unsorted", "range_seconds_unsorted", "range_minutes_unsorted", "range_hours_unsorted"]
CB_QIDS = ["q20", "q22", "q24"]  # 1-based harness ids = ClickBench Q19, Q21, Q23 (0-based)
CB_NAMES = {"q20": "Q19", "q22": "Q21", "q24": "Q23"}
MICRO_STAT_COLUMN = "sensor_records.timestamp_ms"
CB_STATS = "hits.UserID:nullspace:200,hits.URL:ngram:2000,hits.Title:ngram:2000"
TIMER_RE = re.compile(r"^Run Time \(s\): real ([0-9.]+)")


# ----------------------------------------------------------------------------------------------------------------
# Session matrix
# ----------------------------------------------------------------------------------------------------------------
def sessions():
    """(dataset, binary, config, env, items). items: micro -> setup names; clickbench -> qids."""
    def stats_env(columns):
        return {"PRUNING_STATS_COLUMNS": columns}
    result = []
    # microbenchmark: unsorted, statistics on timestamp_ms at the paper's 100x budget (200 words)
    result.append(("micro", "stock", "baseline", {}, MICRO_SETUPS))
    result.append(("micro", "timing", "baseline", {}, MICRO_SETUPS))
    result.append(("micro", "timing", "bloom200", stats_env(MICRO_STAT_COLUMN + ":bloom:200"), ["point_unsorted"]))
    result.append(("micro", "timing", "occupancy200", stats_env(MICRO_STAT_COLUMN + ":occupancy:200"), MICRO_SETUPS))
    result.append(("micro", "timing", "nullspace200", stats_env(MICRO_STAT_COLUMN + ":nullspace:200"),
                   ["point_unsorted"]))
    # ClickBench Q19, Q21, Q23
    result.append(("clickbench", "stock", "C1_baseline", {}, CB_QIDS))
    result.append(("clickbench", "timing", "C1_baseline", {}, CB_QIDS))
    result.append(("clickbench", "timing", "C2_statistic", stats_env(CB_STATS), CB_QIDS))
    result.append(("clickbench", "timing", "C3_all_repeat",
                   dict(stats_env(CB_STATS), PRUNING_ROWID_SKIP="1", PRUNING_PREDICATE_CACHE="1"), CB_QIDS))
    return result


def session_name(dataset, binary, config):
    return "%s/%s_%s" % (dataset, binary, config)


def micro_queries(setup_name, sample):
    setup = [s for s in common.micro_setups() if s.name == setup_name][0]
    qs = setup.queries()
    items = list(zip(setup.qids(len(qs)), qs))
    return items[::sample] if sample > 1 else items


def clickbench_queries():
    setup = [s for s in common.established_setups() if s.name == "clickbench"][0]
    qs = setup.queries()
    by_id = dict(zip(setup.qids(len(qs)), qs))
    return [(qid, by_id[qid]) for qid in CB_QIDS]


# ----------------------------------------------------------------------------------------------------------------
# Host information
# ----------------------------------------------------------------------------------------------------------------
def imds(path):
    """EC2 instance metadata (IMDSv2); None outside EC2."""
    try:
        req = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
        token = urllib.request.urlopen(req, timeout=1).read().decode()
        req = urllib.request.Request("http://169.254.169.254/latest/meta-data/" + path,
                                     headers={"X-aws-ec2-metadata-token": token})
        return urllib.request.urlopen(req, timeout=1).read().decode()
    except Exception:
        return None


def run_text(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:
        return "error: %s" % e


def binary_version(binary):
    return run_text([binary, "-noheader", "-list", "-c", "SELECT library_version, source_id FROM pragma_version();"])


def host_info(args):
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "instance_type": imds("instance-type"),
        "availability_zone": imds("placement/availability-zone"),
        "instance_id": imds("instance-id"),
        "uname": " ".join(platform.uname()),
        "lscpu": run_text(["lscpu"]),
        "memory": run_text(["free", "-b"]),
        "block_devices": run_text(["lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL"]),
        "git_commit": run_text(["git", "-C", HERE, "rev-parse", "HEAD"]),
        "git_branch": run_text(["git", "-C", HERE, "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_status": run_text(["git", "-C", HERE, "status", "--short"]),
        "binaries": {"stock": {"path": args.stock_binary, "version": binary_version(args.stock_binary)},
                     "timing": {"path": args.timing_binary, "version": binary_version(args.timing_binary)}},
    }


# ----------------------------------------------------------------------------------------------------------------
# A DuckDB shell driven through a pipe
# ----------------------------------------------------------------------------------------------------------------
class ShellError(Exception):
    pass


class Shell:
    def __init__(self, argv, env, stderr_path):
        self.stderr_file = open(stderr_path, "w")
        # binary pipes, stdout read with os.read: a buffered reader would hide complete lines from select()
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env, bufsize=0)
        self.stdout_fd = self.proc.stdout.fileno()
        self.stdout_buf = b""
        self.stderr_lines = queue.Queue()
        self._stderr_thread = threading.Thread(target=self._pump_stderr, daemon=True)
        self._stderr_thread.start()
        self.marker = 0
        self.pid = None

    def _pump_stderr(self):
        for raw in iter(self.proc.stderr.readline, b""):
            line = raw.decode("utf-8", "replace")
            self.stderr_file.write(line)
            self.stderr_file.flush()
            self.stderr_lines.put(line.rstrip("\n"))

    def drain_stderr(self):
        lines = []
        while True:
            try:
                lines.append(self.stderr_lines.get_nowait())
            except queue.Empty:
                return lines

    def find_duckdb_pid(self, binary):
        """The DuckDB process: the child itself or a descendant (sudo forks, systemd-run --scope exec's)."""
        real = os.path.realpath(binary)

        def parent(pid):
            try:
                with open("/proc/%d/stat" % pid) as f:
                    return int(f.read().rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                return None

        for _ in range(200):
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                pid = int(entry)
                try:
                    if os.path.realpath("/proc/%d/exe" % pid) != real:
                        continue
                except OSError:
                    continue
                p = pid
                while p and p > 1:
                    if p == self.proc.pid:
                        self.pid = pid
                        return pid
                    p = parent(p)
            time.sleep(0.05)
        raise ShellError("cannot find the DuckDB process below pid %d" % self.proc.pid)

    def read_bytes(self):
        try:
            with open("/proc/%d/io" % self.pid) as f:
                for line in f:
                    if line.startswith("read_bytes:"):
                        return int(line.split()[1])
        except OSError:
            return None
        return None

    def execute(self, sql, timeout):
        """Runs one statement; returns (real_s from the shell timer or None, wall_s, stdout lines, stderr lines)."""
        self.marker += 1
        marker = "__END_%d__" % self.marker
        self.drain_stderr()
        text = sql.strip()
        if not text.startswith("."):
            text = text.rstrip(";") + ";"
        t0 = time.perf_counter()
        try:
            self.proc.stdin.write((text + "\n.print " + marker + "\n").encode())
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise ShellError("shell exited")
        lines, real = [], None
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ShellError("timeout after %.0f s" % timeout)
            if b"\n" not in self.stdout_buf:
                ready, _, _ = select.select([self.stdout_fd], [], [], remaining)
                if not ready:
                    continue
                chunk = os.read(self.stdout_fd, 65536)
                if not chunk:
                    raise ShellError("shell exited (rc=%s)" % self.proc.poll())
                self.stdout_buf += chunk
                continue
            raw, self.stdout_buf = self.stdout_buf.split(b"\n", 1)
            line = raw.decode("utf-8", "replace")
            if line == marker:
                wall = time.perf_counter() - t0
                break
            m = TIMER_RE.match(line)
            if m:
                real = float(m.group(1))
            else:
                lines.append(line)
        time.sleep(0.01)  # let the stderr pump catch up with an error message of this statement
        return real, wall, lines, self.drain_stderr()

    def close(self):
        try:
            self.proc.stdin.write(b".quit\n")
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self._stderr_thread.join(timeout=5)
        self.stderr_file.close()

    def kill(self):
        try:
            self.proc.kill()
            self.proc.wait(timeout=30)
        except Exception:
            pass
        try:
            self.stderr_file.close()
        except Exception:
            pass


# ----------------------------------------------------------------------------------------------------------------
# Memory restriction
# ----------------------------------------------------------------------------------------------------------------
def drop_caches():
    r = subprocess.run(["sudo", "-n", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def evict_file(path):
    """Drops the file's clean pages from the page cache (posix_fadvise DONTNEED, no root needed)."""
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)
        return True
    except OSError as e:
        print("  WARNING: cannot evict %s from the page cache: %s" % (path, e), flush=True)
        return False


def cgroup_limits(pid):
    """memory.max and memory.swap.max of the cgroup the process runs in (cgroup v2)."""
    try:
        with open("/proc/%d/cgroup" % pid) as f:
            path = f.read().strip().split("::", 1)[1]
        base = "/sys/fs/cgroup" + path
        result = {"cgroup": path}
        for name in ("memory.max", "memory.swap.max"):
            try:
                with open(os.path.join(base, name)) as f:
                    result[name] = f.read().strip()
            except OSError:
                result[name] = None
        return result
    except Exception as e:
        return {"error": str(e)}


def cgroup_memory(pid):
    """Memory charged to the process's cgroup: total, anonymous (DuckDB heap incl. statistics), page cache, peak."""
    try:
        with open("/proc/%d/cgroup" % pid) as f:
            base = "/sys/fs/cgroup" + f.read().strip().split("::", 1)[1]
        with open(os.path.join(base, "memory.stat")) as f:
            stat = dict(line.split() for line in f)
        result = {"current": int(open(os.path.join(base, "memory.current")).read()),
                  "anon": int(stat.get("anon", 0)), "file": int(stat.get("file", 0))}
        try:
            result["peak"] = int(open(os.path.join(base, "memory.peak")).read())
        except OSError:
            result["peak"] = None
        return result
    except Exception as e:
        return {"error": str(e)}


def parse_size(text):
    m = re.match(r"^\s*([0-9.]+)\s*([KMGT]?)i?B?\s*$", text, re.IGNORECASE)
    if not m:
        raise SystemExit("cannot parse size '%s'" % text)
    return int(float(m.group(1)) * 1024 ** "_KMGT".index(m.group(2).upper() or "_"))


# ----------------------------------------------------------------------------------------------------------------
# One session
# ----------------------------------------------------------------------------------------------------------------
def run_session(args, mode, dataset, binary_key, config, env_extra, items):
    name = session_name(dataset, binary_key, config)
    sdir = os.path.join(args.out, mode, dataset, "%s_%s" % (binary_key, config))
    info_path = os.path.join(sdir, "session.json")
    if os.path.exists(info_path):
        with open(info_path) as f:
            if json.load(f).get("done"):
                print("[%s] %s %s: done, skipped" % (time.strftime("%H:%M:%S"), mode, name), flush=True)
                return True
    os.makedirs(sdir, exist_ok=True)
    binary = args.stock_binary if binary_key == "stock" else args.timing_binary
    db_file = os.path.join(args.db_dir, args.micro_db if dataset == "micro" else args.cb_db)
    table = "sensor_records" if dataset == "micro" else "hits"
    memory_limit = args.m1_memory if mode == "M1" else args.m2_memory

    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PRUNING_") and k != "DUCKDB_PRUNING_STATS"}
    if binary_key == "timing":
        env.update(env_extra)
        if env_extra.get("PRUNING_STATS_COLUMNS"):
            env["PRUNING_STATS_BUILD_ON_LOAD"] = str(args.build_threads)
    elif env_extra:
        raise SystemExit("stock sessions take no statistics: %s" % name)

    info = {"mode": mode, "dataset": dataset, "binary": binary_key, "binary_path": binary, "config": config,
            "env": {k: v for k, v in env.items() if k.startswith("PRUNING_")}, "db": db_file,
            "threads": args.threads, "memory_limit": memory_limit, "runs": args.runs, "sample": args.sample,
            "start": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "done": False, "errors": []}

    argv = [binary]
    if mode == "M2":
        ok, msg = drop_caches()
        info["drop_caches"] = {"ok": ok, "message": msg}
        info["evict_db_file"] = evict_file(db_file)
        if not ok:
            print("  WARNING: could not drop the page cache (%s)" % msg, flush=True)
            if args.require_drop_caches:
                raise SystemExit("--require-drop-caches: cannot drop the page cache")
        scope = ["systemd-run", "--scope", "--quiet", "--collect", "-p", "MemoryMax=" + args.m2_cgroup,
                 "-p", "MemorySwapMax=0"]
        if args.cgroup_runner == "user":
            scope.insert(1, "--user")
        else:
            scope = ["sudo", "-n", "--preserve-env"] + scope + ["--uid=%d" % os.getuid(), "--gid=%d" % os.getgid()]
        argv = scope + argv

    tmp_dir = os.path.join(args.tmp_dir, mode, dataset, "%s_%s" % (binary_key, config))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    os.makedirs(tmp_dir, exist_ok=True)
    print("[%s] %s %s: start (%s)" % (time.strftime("%H:%M:%S"), mode, name,
                                       " ".join("%s=%s" % kv for kv in info["env"].items()) or "no statistics"),
          flush=True)
    shell = Shell(argv, env, os.path.join(sdir, "stderr.log"))
    rows = []
    ok_session = True
    try:
        shell.find_duckdb_pid(binary)
        if mode == "M2":
            info["cgroup"] = cgroup_limits(shell.pid)
            expected = str(parse_size(args.m2_cgroup))
            if info["cgroup"].get("memory.max") != expected:
                raise ShellError("cgroup memory.max is %s, expected %s" % (info["cgroup"].get("memory.max"), expected))
        setup_sql = [".timer on", ".mode trash", "SET threads = %d;" % args.threads,
                     "SET memory_limit = '%s';" % memory_limit,
                     "SET temp_directory = '%s';" % tmp_dir.replace("'", "''")]
        for stmt in setup_sql:
            _, _, out, err = shell.execute(stmt, 60)
            if err:
                raise ShellError("%s: %s" % (stmt, " | ".join(err)))
        read0 = shell.read_bytes()
        real, wall, out, err = shell.execute("ATTACH '%s' AS db (READ_ONLY);" % db_file.replace("'", "''"),
                                             args.attach_timeout)
        if any(l.startswith(("Error", "IO Error", "Binder Error", "Catalog Error")) for l in err):
            raise ShellError("ATTACH: %s" % " | ".join(err))
        info["attach"] = {"real_s": real, "wall_s": wall, "read_bytes": (shell.read_bytes() or 0) - (read0 or 0),
                          "build_on_load": [l for l in err if l.startswith("PRUNING_STATS_BUILD_ON_LOAD")]}
        for line in info["attach"]["build_on_load"]:
            try:
                rec = json.loads(line.split(" ", 1)[1])
                if rec.get("error"):
                    raise ShellError("build-on-load failed: %s" % rec["error"])
            except ValueError:
                pass
        if env.get("PRUNING_STATS_COLUMNS") and not info["attach"]["build_on_load"]:
            raise ShellError("statistics configured but no build-on-load record after ATTACH")
        if mode == "M2":
            info["cgroup_memory"] = {"after_attach": cgroup_memory(shell.pid)}
        print("  attach + statistics build: %.1f s" % wall, flush=True)
        shell.execute("USE db;", 60)

        if mode == "M1":
            sql = "SELECT max(hash(COLUMNS(*))) FROM %s;" % table
            r0 = shell.read_bytes()
            real, wall, out, err = shell.execute(sql, args.timeout)
            if err:
                raise ShellError("warm-up: %s" % " | ".join(err))
            info["warmup"] = {"sql": sql, "real_s": real, "wall_s": wall,
                              "read_bytes": (shell.read_bytes() or 0) - (r0 or 0)}
            print("  warm-up: %.1f s" % wall, flush=True)

        def timed(setup, run, qid, sql, warm):
            r0 = shell.read_bytes()
            real, wall, out, err = shell.execute(sql, args.timeout)
            r1 = shell.read_bytes()
            errors = [l for l in err if l and not l.startswith("PRUNING_STATS_BUILD_ON_LOAD")]
            if errors:
                info["errors"].append({"setup": setup, "qid": qid, "run": run, "stderr": errors[:5]})
            row = {"setup": setup, "run": run, "qid": qid, "warmup": int(warm),
                   "real_ms": None if real is None else round(real * 1000, 3), "wall_ms": round(wall * 1000, 3),
                   "read_bytes": None if r0 is None or r1 is None else r1 - r0, "error": int(bool(errors))}
            rows.append(row)
            return row

        if dataset == "micro":
            for setup in items:
                queries = micro_queries(setup, args.sample)[:args.runs]
                t_setup = time.time()
                for run, (qid, sql) in enumerate(queries):
                    timed(setup, run, qid, sql, False)
                done = [r for r in rows if r["setup"] == setup]
                print("  %s: %d runs in %.1f s, median %.1f ms" % (
                    setup, len(done), time.time() - t_setup,
                    statistics.median([r["wall_ms"] for r in done]) if done else float("nan")), flush=True)
        else:
            queries = clickbench_queries()
            for qid, sql in queries:  # round 0: untimed warm-up run of every query (fills the predicate cache)
                timed(CB_NAMES[qid], -1, qid, sql, True)
            t_all = time.time()
            for run in range(args.runs):
                for qid, sql in queries:
                    timed(CB_NAMES[qid], run, qid, sql, False)
            for qid, _ in queries:
                done = [r for r in rows if r["qid"] == qid and not r["warmup"]]
                print("  %s: %d runs, median %.1f ms" % (CB_NAMES[qid], len(done),
                                                         statistics.median([r["wall_ms"] for r in done])),
                      flush=True)
            print("  %d rounds in %.1f s" % (args.runs, time.time() - t_all), flush=True)
        if mode == "M2":
            info["cgroup_memory"]["end"] = cgroup_memory(shell.pid)
        info["done"] = not info["errors"]
        ok_session = info["done"]
        shell.close()
    except ShellError as e:
        info["errors"].append({"fatal": str(e)})
        print("  FAILED: %s" % e, flush=True)
        ok_session = False
        shell.kill()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    info["end"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(os.path.join(sdir, "runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["setup", "run", "qid", "warmup", "real_ms", "wall_ms", "read_bytes",
                                          "error"])
        w.writeheader()
        w.writerows(rows)
    with open(info_path, "w") as f:
        json.dump(info, f, indent=1)
    return ok_session


def s3_sync(args):
    if not args.s3:
        return
    r = subprocess.run(["aws", "s3", "sync", "--only-show-errors", args.out, args.s3], capture_output=True, text=True)
    if r.returncode != 0:
        print("  WARNING: s3 sync failed: %s" % r.stderr.strip(), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["M1", "M2"], help="memory mode")
    ap.add_argument("--list", action="store_true", help="print the session matrix and exit")
    ap.add_argument("--db-dir", help="directory with the database files")
    ap.add_argument("--micro-db", default="micro_unsorted.db")
    ap.add_argument("--cb-db", default="clickbench.db")
    ap.add_argument("--out", help="output directory (e.g. pruning_opportunity/results/ec2)")
    ap.add_argument("--tmp-dir", default="/tmp/ec2_timing_tmp", help="DuckDB temp_directory base")
    ap.add_argument("--stock-binary")
    ap.add_argument("--timing-binary")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--build-threads", type=int, default=16, help="PRUNING_STATS_BUILD_ON_LOAD threads")
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--sample", type=int, default=10, help="micro: every k-th query of 1,000 (default 10)")
    ap.add_argument("--m1-memory", default="50GB")
    ap.add_argument("--m2-memory", default="2GB")
    ap.add_argument("--m2-cgroup", default="3G")
    ap.add_argument("--cgroup-runner", choices=["user", "sudo"], default="sudo",
                    help="M2: systemd-run --user (local) or sudo systemd-run --uid (EC2)")
    ap.add_argument("--require-drop-caches", action="store_true", help="M2: abort if the page cache cannot be dropped")
    ap.add_argument("--timeout", type=float, default=1800, help="per statement (s)")
    ap.add_argument("--attach-timeout", type=float, default=7200, help="ATTACH incl. statistics build (s)")
    ap.add_argument("--only", default="", help="comma-separated substrings of session names to run")
    ap.add_argument("--s3", default="", help="s3://... prefix: sync --out there after each session")
    args = ap.parse_args()

    matrix = sessions()
    if args.only:
        wanted = [w for w in args.only.split(",") if w]
        matrix = [s for s in matrix if any(w in session_name(*s[:3]) for w in wanted)]
    if args.list:
        for dataset, binary, config, env, items in matrix:
            print("%-38s %-60s %s" % (session_name(dataset, binary, config),
                                      " ".join("%s=%s" % kv for kv in env.items()) or "-", ",".join(items)))
        return 0
    for name in ("mode", "db_dir", "out", "stock_binary", "timing_binary"):
        if not getattr(args, name):
            raise SystemExit("--%s is required" % name.replace("_", "-"))
    for b in (args.stock_binary, args.timing_binary):
        if not os.access(b, os.X_OK):
            raise SystemExit("binary not found: %s" % b)
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    host_path = os.path.join(args.out, "host_%s.json" % args.mode)
    with open(host_path, "w") as f:
        json.dump(host_info(args), f, indent=1)
    failed = []
    for dataset, binary, config, env, items in matrix:
        if not run_session(args, args.mode, dataset, binary, config, env, items):
            failed.append(session_name(dataset, binary, config))
        s3_sync(args)
    print("[%s] %s finished, %d failed session(s)%s" % (time.strftime("%H:%M:%S"), args.mode, len(failed),
                                                        (": " + ", ".join(failed)) if failed else ""), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
