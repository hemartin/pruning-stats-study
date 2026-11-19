#!/usr/bin/env python3
"""Phase 4 runner: ingest + queries in ONE CLI process per session (the selective statistics live in memory only).

For a benchmark *group* (= one dataset/database, e.g. micro_unsorted serves point_unsorted and the three
range_*_unsorted setups; tpch; tpcds; clickbench; micro_cardinality_<N>), a *configuration* (baseline: no
PRUNING_STATS_COLUMNS; any other name: the given column spec) and a *mode*, every session

  1. attaches a fresh database file db/<scale>/phase4/<label>__<mode>__<group>__s<k>.db (ROW_GROUP_SIZE 8192),
  2. creates the tables and COPYs the CSVs (DDL/COPY verbatim from experiments/sql, load threads configurable),
     followed by CHECKPOINT (as build_db.py did for the Phase 1 databases),
  3. runs the queries of all setups of the group.

Modes
  count  threads=1, pruning counters on (DUCKDB_PRUNING_STATS), results hashed (csv), 1 round, 1 session
  check  DuckDB's default thread count, counters off, results hashed, 1 round, 1 session (result comparison)
  time   DuckDB's default thread count (or --threads), counters off, results discarded (.mode trash),
         --rounds R (default 3, round-robin over the query list), --sessions S (default 3, re-ingest each time)

In every mode PRUNING_STATS_TIMING=<session dir>/timing.jsonl is set: the binary writes one line per statement
(engine-side elapsed time with sub-ms precision, time spent consulting selective statistics, row groups they
pruned) and per selected column at the end of each COPY (time to buffer values / build statistics, bytes).

Robustness: per-query timeout (--timeout) and ingest timeout (--ingest-timeout). A hanging query is killed, recorded
as "timeout" (and skipped in later rounds), and the session is restarted (fresh DB, re-ingest) with the remaining
queries; the same for a crash. Every finished query is flushed to status.jsonl immediately, and re-running the same
command skips what is done (resume).

Output: results/raw/<scale>/phase4/<label>/<mode>/<group>/session_<k>/attempt_<a>/{status.jsonl,timing.jsonl,
pruning.jsonl,cli.log}

Examples
  phase4.py run --scale small --groups micro_unsorted --config baseline --mode count
  phase4.py run --scale small --groups tpcds --config occ200 --columns preset:broad:occupancy:200 --mode time
  phase4.py spec --preset broad --kind nullspace --words 200          # print a column spec
"""
import argparse
import collections
import csv
import hashlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SELECTIVE_BINARY = os.path.join(common.REPO_DIR, "duckdb", "build", "selective", "duckdb")
ERROR_PREFIXES = (b"Error:", b"Binder Error", b"Parser Error", b"Catalog Error", b"Conversion Error",
                  b"Invalid Input Error", b"Out of Memory Error", b"INTERNAL Error", b"Not implemented Error",
                  b"Runtime Error", b"Constraint Error", b"IO Error", b"Invalid Error", b"Serialization Error",
                  b"Interrupt Error", b"Permission Error", b"Out of Range Error", b"Type Error", b"Fatal Error",
                  b"Dependency Error", b"Sequence Error", b"Transaction Error", b"Syntax Error",
                  b"Mismatch Type Error")


# ----------------------------------------------------------------------------------------------------------------
# Groups and column specs
# ----------------------------------------------------------------------------------------------------------------
def groups():
    """group (db name) -> list of setups using that dataset"""
    result = collections.OrderedDict()
    for s in common.all_setups():
        result.setdefault(s.db_name, []).append(s)
    return result


def select_groups(spec):
    g = groups()
    if not spec or spec == "all":
        return list(g)
    wanted = [w.strip() for w in spec.split(",") if w.strip()]
    result = []
    for w in wanted:
        if w in g:
            result.append(w)
        elif w == "micro":
            result += [n for n in g if n.startswith("micro_")]
        else:
            # a setup name selects its group
            hits = [n for n, setups in g.items() if any(s.name == w for s in setups)]
            if not hits:
                raise SystemExit("unknown group/setup %s (groups: %s)" % (w, ", ".join(g)))
            result += hits
    return list(collections.OrderedDict.fromkeys(result))


MICRO_COLUMNS = [("sensor_records", "timestamp_ms"), ("sensor_records", "user_id")]
NON_NUMERIC = ("VARCHAR", "BLOB", "BOOLEAN")


def preset_columns(preset, include_varchar):
    """(table, column) pairs. preset 'broad': every column of TPC-H/TPC-DS/ClickBench with a pushed-down filter in
    results/small/filter_detail.csv (rowid excluded; VARCHAR only with include_varchar) + the micro columns;
    'micro': the micro columns only."""
    cols = list(MICRO_COLUMNS)
    if preset == "micro":
        return cols
    if preset != "broad":
        raise SystemExit("unknown preset %s (broad|micro)" % preset)
    path = os.path.join(common.results_dir("small"), "filter_detail.csv")
    seen = set(cols)
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["benchmark"] == "micro" or r["col"] == "rowid":
                continue
            if r["col_type"] in NON_NUMERIC and not include_varchar:
                continue
            key = (r["table"], r["col"])
            if key not in seen:
                seen.add(key)
                cols.append(key)
    return cols


def resolve_columns(text):
    """--columns value: literal spec, 'preset:<broad|micro>:<kind>:<words>[:varchar]', or '@file'."""
    if not text:
        return ""
    if text.startswith("@"):
        with open(text[1:]) as f:
            return ",".join(line.strip() for line in f if line.strip() and not line.startswith("#"))
    if text.startswith("preset:"):
        parts = text.split(":")
        if len(parts) < 4:
            raise SystemExit("preset spec: preset:<broad|micro>:<kind>:<words>[:varchar]")
        include_varchar = len(parts) > 4 and parts[4] == "varchar"
        return ",".join("%s.%s:%s:%s" % (t, c, parts[2], parts[3])
                        for t, c in preset_columns(parts[1], include_varchar))
    return text


# ----------------------------------------------------------------------------------------------------------------
# One CLI process
# ----------------------------------------------------------------------------------------------------------------
class Process:
    def __init__(self, binary, script, env, log_path):
        self.log = open(log_path, "ab")
        cmd = [binary, ":memory:"]
        if shutil.which("stdbuf"):
            cmd = ["stdbuf", "-oL", "-eL"] + cmd  # line-buffered output: markers arrive when they are printed
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, env=env, start_new_session=True)
        self.script = script
        # bounded: if the consumer (hashing) is slower than the CLI, the reader blocks and the CLI blocks on the
        # pipe, instead of queueing whole query results in memory
        self.lines = queue.Queue(maxsize=4096)
        threading.Thread(target=self._writer, daemon=True).start()
        threading.Thread(target=self._reader, daemon=True).start()

    def _writer(self):
        try:
            self.proc.stdin.write(self.script.encode("utf-8"))
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    def _reader(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def kill(self):
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.proc.wait()


def load_jsonl(path):
    res = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        res.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return res


def session_done_items(session_dir):
    """item keys with a final status in any attempt of this session"""
    done = {}
    if not os.path.isdir(session_dir):
        return done
    for a in sorted(os.listdir(session_dir)):
        for r in load_jsonl(os.path.join(session_dir, a, "status.jsonl")):
            if r.get("kind") == "query":
                done[r["item"]] = r
    return done


def existing_db_path(args, group):
    """--attach-existing: the persistent database of the group (db/<scale>/<group>.db, e.g. the Phase 1 DBs)"""
    return os.path.join(common.db_dir(args.scale), group + ".db")


def build_script(args, group, db_path, query_items, threads_for_queries):
    tmp = os.path.join(common.PO_DIR, "db", "tmp")
    hashing = args.mode in ("count", "check")
    script = [".bail off", ".headers off", ".mode %s" % ("csv" if hashing else "trash"),
              "SET memory_limit = '%s';" % args.memory_limit,
              "SET temp_directory = %s;" % common.sql_str(tmp),
              "SET preserve_insertion_order = true;",
              "SET threads TO %d;" % args.load_threads]
    items = []
    if args.attach_existing:
        # no ingest: attach the existing database read-only; with PRUNING_STATS_BUILD_ON_LOAD the selective
        # statistics are built while ATTACH loads the tables (the "ingest" item measures that)
        items.append(("ingest", "ingest:attach", "%s/ingest/attach" % group,
                      "ATTACH %s AS db (READ_ONLY); USE db" % common.sql_str(db_path)))
    else:
        creates, loads = common.db_definitions(args.scale, args.clickbench_csv)[group]
        script += ["ATTACH %s AS db (ROW_GROUP_SIZE 8192);" % common.sql_str(db_path), "USE db;"]
        script += [c.rstrip().rstrip(";").rstrip(";") + ";" for c in creates]
        for table, csv_path, copy_stmt in loads:
            items.append(("ingest", "ingest:" + table, "%s/ingest/%s" % (group, table), copy_stmt))
        if not args.no_checkpoint:
            items.append(("ingest", "ingest:checkpoint", "%s/ingest/checkpoint" % group, "CHECKPOINT"))
    lines = []
    for i, (kind, item, tag, sql) in enumerate(items):
        lines += ["SET VARIABLE pruning_tag = %s;" % common.sql_str(tag), ".print @@PQB %d" % i,
                  sql.rstrip().rstrip(";") + ";", ".print @@PQE %d" % i]
    script += lines
    script.append("SET VARIABLE pruning_tag = %s;" % common.sql_str("%s/ingest/done" % group))
    if threads_for_queries:
        script.append("SET threads TO %d;" % threads_for_queries)
    else:
        script.append("RESET threads;")
    for extra in args.setting:
        script.append(extra if extra.rstrip().endswith(";") else extra + ";")
    base = len(items)
    for j, (item, tag, sql) in enumerate(query_items):
        i = base + j
        items.append(("query", item, tag, sql))
        script += ["SET VARIABLE pruning_tag = %s;" % common.sql_str(tag), ".print @@PQB %d" % i,
                   sql.rstrip().rstrip(";") + ";", ".print @@PQE %d" % i]
    script.append("SET VARIABLE pruning_tag = '';")
    return "\n".join(script) + "\n", items


def run_attempt(args, group, session_dir, attempt, query_items, threads_for_queries, env_base):
    """Runs one CLI process. Returns (list of finished query item keys, aborted item key or None, ingest_ok)."""
    adir = os.path.join(session_dir, "attempt_%d" % attempt)
    os.makedirs(adir, exist_ok=True)
    db_dir = os.path.join(common.db_dir(args.scale), "phase4")
    os.makedirs(db_dir, exist_ok=True)
    os.makedirs(os.path.join(common.PO_DIR, "db", "tmp"), exist_ok=True)
    db_name = "%s__%s__%s__%s.db" % (args.config, args.mode, group, os.path.basename(session_dir))
    db_path = os.path.join(db_dir, db_name)
    if args.attach_existing:
        db_path = existing_db_path(args, group)
        if not os.path.exists(db_path):
            raise SystemExit("--attach-existing: %s not found" % db_path)
    else:
        for f in (db_path, db_path + ".wal"):
            if os.path.exists(f):
                os.remove(f)
    script, items = build_script(args, group, db_path, query_items, threads_for_queries)
    with open(os.path.join(adir, "script.sql"), "w") as f:
        f.write(script)
    env = dict(env_base)
    env["PRUNING_STATS_TIMING"] = os.path.join(adir, "timing.jsonl")
    if args.mode == "count":
        env["DUCKDB_PRUNING_STATS"] = os.path.join(adir, "pruning.jsonl")
    status_f = open(os.path.join(adir, "status.jsonl"), "a")
    proc = Process(args.binary, script, env, os.path.join(adir, "cli.log"))
    finished, aborted, ingest_ok = [], None, True
    current, t_start, hasher, sorted_lines, nlines, errors = None, None, None, None, 0, []
    multiset = 0
    out_of_query_errors = []
    while True:
        timeout = None
        if current is not None:
            limit = args.ingest_timeout if items[current][0] == "ingest" else args.timeout
            timeout = max(0.0, limit - (time.time() - t_start))
        try:
            line = proc.lines.get(timeout=timeout if timeout is not None else 3600)
        except queue.Empty:
            if current is not None:
                aborted = "timeout"
                proc.kill()
                break
            continue
        if line is None:
            aborted = "crash" if current is not None else None
            break
        if current is None or line.startswith(b"@@PQ") or any(line.startswith(p) for p in ERROR_PREFIXES):
            proc.log.write(line)  # result rows are not logged (they can be huge)
        if line.startswith(b"@@PQB "):
            current = int(line.split()[1])
            t_start = time.time()
            hasher, sorted_lines, nlines, errors = hashlib.sha1(), [], 0, []
            multiset = 0
            continue
        if line.startswith(b"@@PQE "):
            idx = int(line.split()[1])
            kind, item, tag, _ = items[idx]
            rec = {"kind": kind, "item": item, "tag": tag, "attempt": attempt,
                   "status": "error" if errors else "ok", "wall_s": round(time.time() - t_start, 6),
                   "rows": nlines}
            if args.mode in ("count", "check") and kind == "query":
                rec["hash"] = hasher.hexdigest()
                # sha1 of the sorted lines (comparable with run.py / Phase 1) while the result is small enough to
                # keep in memory; always: an order-independent streaming hash (sum of per-line sha1 mod 2^160)
                rec["hash_sorted"] = (hashlib.sha1(b"".join(sorted(sorted_lines))).hexdigest()
                                      if sorted_lines is not None else None)
                rec["hash_multiset"] = "%040x" % multiset
            if errors:
                rec["error"] = b" | ".join(errors).decode("utf-8", "replace")[:2000]
                if kind == "ingest":
                    ingest_ok = False
            status_f.write(json.dumps(rec) + "\n")
            status_f.flush()
            if kind == "query":
                finished.append(item)
            current = None
            if kind == "ingest" and not ingest_ok:
                proc.kill()
                break
            continue
        if current is None:
            if any(line.startswith(p) for p in ERROR_PREFIXES):
                out_of_query_errors.append(line.decode("utf-8", "replace").rstrip())
            continue
        if any(line.startswith(p) for p in ERROR_PREFIXES):
            errors.append(line.rstrip())
            continue
        nlines += 1
        if hasher is not None and args.mode in ("count", "check"):
            hasher.update(line)
            multiset = (multiset + int.from_bytes(hashlib.sha1(line).digest(), "big")) % (1 << 160)
            if sorted_lines is not None:
                if nlines > args.sorted_hash_max_lines:
                    sorted_lines = None  # too large to keep: only the streaming hashes
                else:
                    sorted_lines.append(line)
    if aborted is None and ingest_ok:
        proc.proc.wait()
    proc.log.close()
    if out_of_query_errors:
        sys.stderr.write("[%s] errors outside of statements: %s\n" % (group, out_of_query_errors[:3]))
    aborted_item = None
    if aborted is not None and current is not None:
        kind, item, tag, _ = items[current]
        rec = {"kind": kind, "item": item, "tag": tag, "attempt": attempt, "status": aborted,
               "wall_s": round(time.time() - t_start, 3), "rows": nlines}
        status_f.write(json.dumps(rec) + "\n")
        status_f.flush()
        if kind == "ingest":
            ingest_ok = False
        else:
            aborted_item = item
        print("  [%s] %s %s after %.1f s" % (group, tag, aborted, rec["wall_s"]), flush=True)
    status_f.close()
    if not args.keep_db and not args.attach_existing:
        for f in (db_path, db_path + ".wal"):
            if os.path.exists(f):
                os.remove(f)
    return finished, aborted_item, ingest_ok


def sample_applies(args, setup):
    """--sample applies to every setup, or with --sample-setups only to setups whose name contains one of the
    given substrings (e.g. 'unsorted,outliers,cardinality' = the large-scale micro runs of Phase 1)"""
    if not args.sample_setups:
        return True
    return any(p and p in setup.name for p in args.sample_setups.split(","))


def check_run_json(path, info):
    """refuses to resume a group directory that was started with another configuration"""
    if not os.path.exists(path):
        return
    with open(path) as f:
        old = json.load(f)
    for k in ("columns", "mode", "threads", "rounds", "binary", "scale", "load_threads", "memory_limit",
              "checkpoint", "predicate_cache", "passes"):
        if k in old and old[k] != info[k]:
            raise SystemExit("%s: existing run has %s=%r, this run %r (use another --config name or delete the "
                             "directory)" % (path, k, old[k], info[k]))


def run_group(args, group, env_base):
    setups = groups()[group]
    if args.setups:
        wanted = set(args.setups.split(","))
        setups = [s for s in setups if s.name in wanted or s.benchmark in wanted]
    base_items = []  # (qid key, tag, sql)
    for s in setups:
        qs = s.queries()
        qids = s.qids(len(qs))
        todo = list(zip(qids, qs))
        if args.limit:
            todo = todo[:args.limit]
        if args.sample and sample_applies(args, s):
            todo = todo[::args.sample]
        if args.qids:
            keep = set(args.qids.split(","))
            todo = [(qid, q) for qid, q in todo if qid in keep]
        for qid, q in todo:
            base_items.append(("%s/%s" % (s.name, qid), q))
    if args.mode == "time":
        rounds, sessions = args.rounds, args.sessions
    else:
        rounds, sessions = 1, 1
    passes = max(1, args.passes) if args.mode != "time" else 1
    threads_for_queries = (args.threads or 1) if args.mode == "count" else args.threads
    gdir = os.path.join(common.raw_dir(args.scale, "phase4"), args.config, args.mode, group)
    os.makedirs(gdir, exist_ok=True)
    info = {"config": args.config, "columns": env_base.get("PRUNING_STATS_COLUMNS", ""), "mode": args.mode,
            "group": group, "setups": [s.name for s in setups], "rounds": rounds, "sessions": sessions,
            "load_threads": args.load_threads, "threads": threads_for_queries or "default",
            "memory_limit": args.memory_limit, "binary": os.path.abspath(args.binary), "scale": args.scale,
            "checkpoint": not args.no_checkpoint, "limit": args.limit, "sample": args.sample,
            "sample_setups": args.sample_setups, "qids": args.qids,
            "predicate_cache": env_base.get("PRUNING_PREDICATE_CACHE", ""), "passes": passes}
    if env_base.get("PRUNING_ROWID_SKIP"):
        info["rowid_skip"] = env_base["PRUNING_ROWID_SKIP"]
    if args.attach_existing:
        info["attach_existing"] = existing_db_path(args, group)
        info["build_on_load"] = env_base.get("PRUNING_STATS_BUILD_ON_LOAD", "")
    run_json = os.path.join(gdir, "run.json")
    if not args.force_resume:
        check_run_json(run_json, info)
    with open(run_json, "w") as f:
        json.dump(info, f, indent=1)
    for k in range(sessions):
        sdir = os.path.join(gdir, "session_%d" % k)
        os.makedirs(sdir, exist_ok=True)
        done = session_done_items(sdir)
        skipped = {r["item"].split("#")[0] for r in done.values() if r["status"] in ("timeout", "crash")}
        query_items = []
        for r in range(rounds * passes):
            for key, sql in base_items:
                if passes > 1:
                    item = key if r == 0 else "%s#p%d" % (key, r + 1)
                else:
                    item = key if rounds == 1 else "%s#r%d" % (key, r + 1)
                if item in done or key in skipped:
                    continue
                query_items.append((item, item, sql))
        if not query_items:
            print("[%s] %s/%s/%s session %d: complete" % (time.strftime("%H:%M:%S"), args.config, args.mode,
                                                          group, k), flush=True)
            continue
        attempt = len([d for d in os.listdir(sdir) if d.startswith("attempt_")])
        restarts = 0
        while query_items:
            t0 = time.time()
            print("[%s] %s/%s/%s session %d attempt %d: ingest + %d queries" % (
                time.strftime("%H:%M:%S"), args.config, args.mode, group, k, attempt, len(query_items)), flush=True)
            finished, aborted_item, ingest_ok = run_attempt(args, group, sdir, attempt, query_items,
                                                            threads_for_queries, env_base)
            attempt += 1
            print("[%s]   done %d queries in %.1f s%s" % (time.strftime("%H:%M:%S"), len(finished), time.time() - t0,
                                                         "" if ingest_ok else " (INGEST FAILED)"), flush=True)
            if not ingest_ok:
                break
            fin = set(finished)
            skip_key = aborted_item.split("#")[0] if aborted_item else None
            query_items = [q for q in query_items if q[0] not in fin and q[0] != aborted_item and
                           (skip_key is None or q[0].split("#")[0] != skip_key)]
            if query_items:
                restarts += 1
                if restarts > args.max_restarts:
                    print("  [%s] giving up after %d restarts" % (group, restarts - 1), flush=True)
                    break


def cmd_run(args):
    if not os.path.exists(args.binary):
        raise SystemExit("binary %s not found (run build_selective.sh)" % args.binary)
    columns = resolve_columns(args.columns)
    no_stats = args.config.startswith(("baseline", "stock"))
    if no_stats and columns:
        raise SystemExit("config '%s' (baseline*/stock*) must not have --columns" % args.config)
    if not no_stats and not columns and not args.predicate_cache and not args.rowid_skip:
        raise SystemExit("config %s needs --columns, --predicate-cache or --rowid-skip (or name it baseline*/stock*)"
                         % args.config)
    if no_stats and (args.predicate_cache or args.rowid_skip):
        raise SystemExit("config '%s' (baseline*/stock*) must not have --predicate-cache/--rowid-skip" % args.config)
    env = dict(os.environ)
    for v in ("DUCKDB_PRUNING_STATS", "PRUNING_STATS_TIMING", "PRUNING_STATS_COLUMNS", "PRUNING_PREDICATE_CACHE",
              "PRUNING_ROWID_SKIP", "PRUNING_STATS_BUILD_ON_LOAD"):
        env.pop(v, None)
    if args.rowid_skip:
        env["PRUNING_ROWID_SKIP"] = "1"
    if args.build_on_load and not args.attach_existing:
        raise SystemExit("--build-on-load needs --attach-existing")
    if args.attach_existing and columns and not args.build_on_load:
        raise SystemExit("--attach-existing with --columns needs --build-on-load N (statistics are not persisted)")
    if args.build_on_load:
        env["PRUNING_STATS_BUILD_ON_LOAD"] = str(args.build_on_load)
    if columns:
        env["PRUNING_STATS_COLUMNS"] = columns
    if args.predicate_cache:
        env["PRUNING_PREDICATE_CACHE"] = args.predicate_cache
    for group in select_groups(args.groups):
        run_group(args, group, env)


def results_equal(a, b):
    """same result: row count and order-independent hash (hash_sorted where both have it, else hash_multiset);
    None if not comparable"""
    if a is None or b is None or a.get("status") != "ok" or b.get("status") != "ok":
        return None if a is None or b is None else False
    if a.get("rows") != b.get("rows"):
        return False
    if a.get("hash_sorted") and b.get("hash_sorted"):
        return a["hash_sorted"] == b["hash_sorted"]
    if a.get("hash_multiset") and b.get("hash_multiset"):
        return a["hash_multiset"] == b["hash_multiset"]
    return None


def cmd_spec(args):
    print(resolve_columns("preset:%s:%s:%s%s" % (args.preset, args.kind, args.words,
                                                 ":varchar" if args.varchar else "")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a group/config/mode")
    r.add_argument("--scale", required=True, help="small | large (data/<scale>/, db/<scale>/phase4/)")
    r.add_argument("--groups", default="all",
                   help="comma-separated groups (db names: micro_unsorted, ..., tpch, tpcds, clickbench), 'micro', "
                        "or setup names (select their group); default all")
    r.add_argument("--setups", default=None, help="restrict the queries to these setups of the group(s)")
    r.add_argument("--config", required=True,
                   help="'baseline*' or 'stock*' (no selective statistics; use --binary for the stock binary) or a "
                        "name for the --columns configuration")
    r.add_argument("--columns", default="",
                   help="PRUNING_STATS_COLUMNS: literal spec 't.c:kind:words,...', '@file' or "
                        "'preset:<broad|micro>:<kind>:<words>[:varchar]'")
    r.add_argument("--mode", required=True, choices=["count", "check", "time"])
    r.add_argument("--binary", default=SELECTIVE_BINARY)
    r.add_argument("--rounds", type=int, default=3, help="time mode: executions of every query per session")
    r.add_argument("--sessions", type=int, default=3, help="time mode: sessions (each with its own ingest)")
    r.add_argument("--threads", type=int, default=0,
                   help="query threads (count: default 1; check/time: 0 = DuckDB default)")
    r.add_argument("--load-threads", type=int, default=1)
    r.add_argument("--memory-limit", default="6GB")
    r.add_argument("--timeout", type=float, default=1800, help="per-query timeout (s)")
    r.add_argument("--ingest-timeout", type=float, default=6 * 3600, help="per-COPY timeout (s)")
    r.add_argument("--max-restarts", type=int, default=20)
    r.add_argument("--limit", type=int, default=0, help="only the first N queries of each setup")
    r.add_argument("--sample", type=int, default=0, help="only every k-th query of each setup (index 0, k, 2k, ...)")
    r.add_argument("--qids", default="", help="only these query ids, e.g. q11,q12 (applied after --limit/--sample)")
    r.add_argument("--sample-setups", default="",
                   help="apply --sample only to setups whose name contains one of these comma-separated substrings")
    r.add_argument("--force-resume", action="store_true",
                   help="resume even if run.json records different settings")
    r.add_argument("--sorted-hash-max-lines", type=int, default=500000,
                   help="keep at most this many result lines per query for hash_sorted (memory); larger results "
                        "get only hash_multiset")
    r.add_argument("--setting", action="append", default=[], help="extra SQL run before the queries")
    r.add_argument("--passes", type=int, default=1,
                   help="count/check: run the query list N times in the same session (items of pass p > 1 get the "
                        "suffix #p<p>; e.g. cold + warm predicate cache)")
    r.add_argument("--predicate-cache", default="",
                   help="PRUNING_PREDICATE_CACHE for the binary: 1 (whole-conjunction keys) or subset")
    r.add_argument("--rowid-skip", action="store_true",
                   help="PRUNING_ROWID_SKIP=1: row-id range check (prune row groups on rowid filters)")
    r.add_argument("--attach-existing", action="store_true",
                   help="no ingest: attach db/<scale>/<group>.db read-only (e.g. the Phase 1 databases)")
    r.add_argument("--build-on-load", type=int, default=0,
                   help="PRUNING_STATS_BUILD_ON_LOAD=N: build the selective statistics while ATTACH loads the "
                        "tables, with N threads (needs --attach-existing)")
    r.add_argument("--clickbench-csv", default=None)
    r.add_argument("--no-checkpoint", action="store_true", help="skip CHECKPOINT after loading")
    r.add_argument("--keep-db", action="store_true", help="keep the database files")
    r.set_defaults(func=cmd_run)
    s = sub.add_parser("spec", help="print a column spec from a preset")
    s.add_argument("--preset", default="broad", choices=["broad", "micro"])
    s.add_argument("--kind", default="occupancy", choices=["occupancy", "nullspace"])
    s.add_argument("--words", type=int, default=200)
    s.add_argument("--varchar", action="store_true", help="include VARCHAR columns")
    s.set_defaults(func=cmd_spec)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
