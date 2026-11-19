#!/usr/bin/env python3
"""Run benchmark queries against a DuckDB CLI binary, one query after the other, with
per-query timeout, crash isolation and resumability.

For every setup, queries are fed to the CLI in batches (one process per batch). Each query is wrapped as

    SET VARIABLE pruning_tag = '<setup>/<qid>';      -- picked up by the pruning counters
    .print @@PQB <i>
    <query>;
    .print @@PQE <i>

The runner reads the merged stdout/stderr, measures the wall time between the markers, hashes the result lines
(optional) and writes one line per query to status.jsonl. If a query exceeds the timeout, the process is killed,
the query is recorded as "timeout" and a new process continues with the next query; a process that dies inside a
query records "crash". Queries that already have a status line are skipped, so an interrupted run resumes.

With --count, DUCKDB_PRUNING_STATS=<out>/pruning.jsonl is set (the instrumented binary appends one JSON line per
query and per table scan).
"""
import argparse
import hashlib
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def load_status(path):
    done = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                done[r["qid"]] = r
    return done


class Batch:
    def __init__(self, args, db_path, env, items):
        self.items = items
        script = [".bail off", ".headers off", ".mode %s" % ("csv" if args.hash else "trash"),
                  "SET threads TO %d;" % args.threads,
                  "SET memory_limit = '%s';" % args.memory_limit,
                  "SET temp_directory = %s;" % common.sql_str(os.path.join(common.PO_DIR, "db", "tmp")),
                  ]
        for extra in args.setting:
            script.append(extra if extra.rstrip().endswith(";") else extra + ";")
        for i, (qid, tag, sql) in enumerate(items):
            script.append("SET VARIABLE pruning_tag = %s;" % common.sql_str(tag))
            script.append(".print @@PQB %d" % i)
            script.append(sql.rstrip().rstrip(";") + ";")
            script.append(".print @@PQE %d" % i)
        self.script = "\n".join(script) + "\n"
        cmd = [args.binary, "-readonly", db_path] if args.readonly else [args.binary, db_path]
        if args.stdbuf:
            cmd = ["stdbuf", "-oL", "-eL"] + cmd
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     env=env, start_new_session=True)
        self.lines = queue.Queue()
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


ERROR_PREFIXES = (b"Error:", b"Binder Error", b"Parser Error", b"Catalog Error", b"Conversion Error",
                  b"Invalid Input Error", b"Out of Memory Error", b"INTERNAL Error", b"Not implemented Error",
                  b"Runtime Error", b"Constraint Error", b"IO Error", b"Invalid Error", b"Serialization Error",
                  b"Interrupt Error", b"Permission Error", b"Out of Range Error", b"Type Error", b"Fatal Error",
                  b"Dependency Error", b"Sequence Error", b"Transaction Error", b"Syntax Error", b"Mismatch Type Error")


def run_setup(args, setup, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    status_path = os.path.join(out_dir, "status.jsonl")
    done = load_status(status_path)
    queries = setup.queries()
    qids = setup.qids(len(queries))
    todo = [(qid, "%s/%s" % (setup.name, qid), q) for qid, q in zip(qids, queries)]
    if args.limit:
        todo = todo[:args.limit]
    if args.sample:
        todo = todo[::args.sample]
    todo = [t for t in todo if t[0] not in done]
    db_path = os.path.join(common.db_dir(args.scale), setup.db_name + ".db")
    if not os.path.exists(db_path):
        raise SystemExit("missing database %s (run build_db.py first)" % db_path)
    env = dict(os.environ)
    env.pop("DUCKDB_PRUNING_STATS", None)
    if args.count:
        env["DUCKDB_PRUNING_STATS"] = os.path.join(out_dir, "pruning.jsonl")
    print("[%s] %s: %d queries to run (%d already done) -> %s" % (time.strftime("%H:%M:%S"), setup.name,
                                                                   len(todo), len(done), out_dir), flush=True)
    status_f = open(status_path, "a")
    n_ok = n_fail = 0
    t_setup = time.time()
    while todo:
        batch_items = todo[:args.batch]
        batch = Batch(args, db_path, env, batch_items)
        finished = 0          # number of items of this batch that got a status
        current = None        # index of the query in progress
        t_start = None
        hasher = sorted_lines = None
        nlines = 0
        errors = []
        aborted = None
        while True:
            timeout_left = None
            if current is not None:
                timeout_left = max(0.0, args.timeout - (time.time() - t_start))
            try:
                line = batch.lines.get(timeout=timeout_left if timeout_left is not None else 3600)
            except queue.Empty:
                if current is not None and time.time() - t_start >= args.timeout:
                    aborted = "timeout"
                    batch.kill()
                    break
                continue
            if line is None:
                aborted = "crash" if current is not None else None
                break
            if line.startswith(b"@@PQB "):
                current = int(line.split()[1])
                t_start = time.time()
                hasher = hashlib.sha1()
                sorted_lines = []
                nlines = 0
                errors = []
                continue
            if line.startswith(b"@@PQE "):
                idx = int(line.split()[1])
                wall = time.time() - t_start
                qid, tag, _ = batch_items[idx]
                rec = {"qid": qid, "tag": tag, "status": "error" if errors else "ok", "wall_s": round(wall, 6),
                       "rows": nlines}
                if args.hash:
                    rec["hash"] = hasher.hexdigest()
                    rec["hash_sorted"] = hashlib.sha1(b"".join(sorted(sorted_lines))).hexdigest()
                if errors:
                    rec["error"] = b" | ".join(errors).decode("utf-8", "replace")[:2000]
                status_f.write(json.dumps(rec) + "\n")
                status_f.flush()
                finished = idx + 1
                current = None
                if errors:
                    n_fail += 1
                else:
                    n_ok += 1
                continue
            if current is None:
                # output outside of a query (settings); report errors
                if any(line.startswith(p) for p in ERROR_PREFIXES):
                    sys.stderr.write("[%s] %s" % (setup.name, line.decode("utf-8", "replace")))
                continue
            if any(line.startswith(p) for p in ERROR_PREFIXES):
                errors.append(line.rstrip())
                continue
            nlines += 1
            if args.hash:
                hasher.update(line)
                sorted_lines.append(line)
        if aborted is None:
            batch.proc.wait()
        if aborted is not None:
            idx = current
            qid, tag, _ = batch_items[idx]
            rec = {"qid": qid, "tag": tag, "status": aborted, "wall_s": round(time.time() - t_start, 3),
                   "rows": nlines}
            if errors:
                rec["error"] = b" | ".join(errors).decode("utf-8", "replace")[:2000]
            status_f.write(json.dumps(rec) + "\n")
            status_f.flush()
            n_fail += 1
            finished = idx + 1
            print("  %s %s after %.1f s" % (tag, aborted, rec["wall_s"]), flush=True)
        elif finished < len(batch_items):
            # process exited between queries (should not happen): record the next one as crash
            qid, tag, _ = batch_items[finished]
            status_f.write(json.dumps({"qid": qid, "tag": tag, "status": "crash", "wall_s": 0, "rows": 0}) + "\n")
            status_f.flush()
            n_fail += 1
            finished += 1
        todo = todo[finished:]
        if args.progress and todo:
            print("  ... %d left (%.0f s)" % (len(todo), time.time() - t_setup), flush=True)
    status_f.close()
    print("[%s] %s: ok=%d failed=%d in %.1f s" % (time.strftime("%H:%M:%S"), setup.name, n_ok, n_fail,
                                                   time.time() - t_setup), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True, help="small | large (selects db/<scale>/)")
    ap.add_argument("--setups", default="all", help="comma-separated setup or benchmark names (default all)")
    ap.add_argument("--binary", default=common.DEFAULT_BINARY)
    ap.add_argument("--count", action="store_true", help="enable the pruning counters (DUCKDB_PRUNING_STATS)")
    ap.add_argument("--hash", action="store_true", help="hash query results (csv output); otherwise .mode trash")
    ap.add_argument("--label", default=None, help="results/raw/<scale>/<label>/ (default: count|nocount)")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--memory-limit", default="6GB")
    ap.add_argument("--timeout", type=float, default=1800, help="per-query timeout in seconds")
    ap.add_argument("--batch", type=int, default=100, help="queries per CLI process")
    ap.add_argument("--limit", type=int, default=0, help="only the first N queries of each setup")
    ap.add_argument("--sample", type=int, default=0, help="only every k-th query")
    ap.add_argument("--setting", action="append", default=[], help="extra SQL statement run before the queries")
    ap.add_argument("--no-readonly", dest="readonly", action="store_false")
    ap.add_argument("--no-stdbuf", dest="stdbuf", action="store_false")
    ap.add_argument("--progress", action="store_true")
    args = ap.parse_args()
    label = args.label or ("count" if args.count else "nocount")
    for setup in common.select_setups(args.setups):
        run_setup(args, setup, os.path.join(common.raw_dir(args.scale, label), setup.name))


if __name__ == "__main__":
    main()
