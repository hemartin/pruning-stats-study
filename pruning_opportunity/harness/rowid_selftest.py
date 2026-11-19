#!/usr/bin/env python3
"""Hand-written correctness tests for the row-id range check (PRUNING_ROWID_SKIP=1, rowid binary).

For every test query on the small databases: result (CSV, full content) with the flag on == flag off == stock binary,
at 1 and 8 threads; with the flag on (1 thread) the number of row groups that are *not* pruned must equal the number of
row groups that contain a row id allowed by the rowid predicate (computed in Python from the predicate), i.e. the check
is exact for =, IN, OR-of-=, ranges and their conjunctions; with the flag off nothing is pruned by rowid filters.
Late-materialization (top-N) queries are only checked for equal results and for "pruned >= flag-off pruned".

  ../.venv/bin/python harness/rowid_selftest.py [--rowid-binary ...] [--stock-binary ...]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

RG = 8192


def run(binary, db, sql, threads, env_extra, stats_path=None):
    env = dict(os.environ)
    env.pop("DUCKDB_PRUNING_STATS", None)
    env.pop("PRUNING_ROWID_SKIP", None)
    env.update(env_extra)
    if stats_path:
        env["DUCKDB_PRUNING_STATS"] = stats_path
    script = ".headers on\n.mode csv\nSET threads TO %d;\n%s;\n" % (threads, sql)
    p = subprocess.run([binary, "-readonly", db], input=script.encode(), capture_output=True, env=env, timeout=600)
    out = p.stdout.decode("utf-8", "replace")
    if p.returncode != 0 or p.stderr.strip():
        out += "\nSTDERR:" + p.stderr.decode("utf-8", "replace")
    return out


def scans(stats_path):
    res = []
    if not os.path.exists(stats_path):
        return res
    for line in open(stats_path):
        d = json.loads(line)
        if d["type"] == "scan":
            res.append(d)
    return res


def cases(table, n):
    """(sql, allowed(rowid)->bool or None for 'not exactly predictable')"""
    last = n - 1
    nrg = (n + RG - 1) // RG
    mid = (nrg // 2) * RG
    c = []
    for b in [0, 1, RG - 1, RG, RG + 1, 2 * RG - 1, mid, mid - 1, last - 1, last, n, n + 5, -1]:
        c.append(("rowid = %d" % b, lambda r, b=b: r == b))
    ins = [
        [0, RG - 1],
        [RG - 1, RG],
        [5, RG, 3 * RG + 17, mid, last],
        [2 * RG - 1, 2 * RG, 2 * RG + 1, 7 * RG],
        [last, n, n + 100],
        [n, n + 1],
        [-5, 3],
        list(range(RG - 3, RG + 3)),
        [i * 3 * RG + 11 for i in range(nrg // 3)],
    ]
    for vals in ins:
        s = set(vals)
        c.append(("rowid IN (%s)" % ", ".join(map(str, vals)), lambda r, s=s: r in s))
    rngs = [(0, 0), (RG - 1, RG), (RG, 2 * RG - 1), (RG + 1, 2 * RG - 2), (RG - 2, 3 * RG + 1), (last - 1, n + 5),
            (n, n + 100), (mid - 1, mid), (-10, 3), (5, 4)]
    for a, b in rngs:
        c.append(("rowid BETWEEN %d AND %d" % (a, b), lambda r, a=a, b=b: a <= r <= b))
    for b in [RG, RG - 1, mid, last, 0]:
        c.append(("rowid < %d" % b, lambda r, b=b: r < b))
        c.append(("rowid <= %d" % b, lambda r, b=b: r <= b))
        c.append(("rowid > %d" % b, lambda r, b=b: r > b))
        c.append(("rowid >= %d" % b, lambda r, b=b: r >= b))
    c.append(("rowid = %d OR rowid = %d" % (RG - 1, mid + 3), lambda r: r in (RG - 1, mid + 3)))
    # OR of an AND-range and an equality is an expression filter in v1.4.4 (not a table filter): no pruning expected
    c.append(("(rowid BETWEEN %d AND %d) OR rowid = %d" % (RG, RG + 10, last), None))
    c.append(("rowid >= %d AND rowid < %d AND rowid IN (%d, %d, %d)" % (RG, 3 * RG, RG - 1, 2 * RG, 3 * RG),
              lambda r: r == 2 * RG))
    # not prunable by a range check (must not prune anything wrongly)
    c.append(("rowid <> %d" % RG, None))
    c.append(("rowid NOT IN (1, 2, %d)" % RG, None))
    c.append(("rowid %% %d = 0" % RG, None))
    c.append(("rowid IS NOT NULL AND rowid < %d" % (RG + 1), lambda r: r < RG + 1))
    return [("SELECT count(*), min(rowid), max(rowid), sum(rowid) FROM %s WHERE %s" % (table, w), f, w)
            for w, f in c]


def lm_cases(db_name):
    # every ORDER BY ends with a unique key (rowid) so that ties cannot make results thread-dependent
    if db_name == "clickbench":
        return [
            "SELECT * FROM hits WHERE URL LIKE '%google%' ORDER BY EventTime, rowid LIMIT 10",
            "SELECT * FROM hits ORDER BY EventTime, rowid LIMIT 10",
            "SELECT * FROM hits ORDER BY EventTime DESC, WatchID, rowid LIMIT 7 OFFSET 3",
            "SELECT * FROM hits WHERE SearchPhrase <> '' ORDER BY EventTime, WatchID, rowid LIMIT 10",
            "SELECT * FROM hits ORDER BY WatchID, rowid LIMIT 1",
            "SELECT * FROM hits ORDER BY rowid DESC LIMIT 3",
            "SELECT * FROM hits WHERE rowid BETWEEN 8190 AND 8200 ORDER BY EventTime, rowid LIMIT 5",
            "SELECT * FROM hits WHERE rowid >= 990000 ORDER BY ResolutionWidth DESC, rowid LIMIT 4",
        ]
    if db_name == "tpch":
        return ["SELECT * FROM lineitem ORDER BY l_extendedprice DESC, rowid LIMIT 10",
                "SELECT * FROM lineitem WHERE l_shipmode = 'AIR' ORDER BY l_shipdate, rowid LIMIT 10"]
    return ["SELECT * FROM sensor_records ORDER BY timestamp_ms DESC, rowid LIMIT 10",
            "SELECT * FROM sensor_records ORDER BY timestamp_ms, rowid LIMIT 10 OFFSET 20000"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rowid-binary", default=os.path.join(common.PO_DIR, "rowid", "duckdb", "build", "release", "duckdb"))
    ap.add_argument("--stock-binary", default=common.DEFAULT_BINARY)
    ap.add_argument("--dbs", default="clickbench:hits,micro_sorted:sensor_records,micro_unsorted:sensor_records,tpch:lineitem")
    ap.add_argument("--out", default=None, help="write a JSON report here")
    args = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="rowid_selftest_")
    n_fail = n_ok = 0
    report = []
    for spec in args.dbs.split(","):
        db_name, table = spec.split(":")
        db = os.path.join(common.db_dir("small"), db_name + ".db")
        n = int(run(args.stock_binary, db, "SELECT count(*) AS n FROM %s" % table, 1, {}).splitlines()[1])
        tests = [(q, f, w) for q, f, w in cases(table, n)] + [(q, "lm", q) for q in lm_cases(db_name)]
        for i, (sql, allowed, label) in enumerate(tests):
            sp_on = os.path.join(tmp, "%s_%d_on.jsonl" % (db_name, i))
            sp_off = os.path.join(tmp, "%s_%d_off.jsonl" % (db_name, i))
            r_stock = run(args.stock_binary, db, sql, 1, {})
            r_off1 = run(args.rowid_binary, db, sql, 1, {}, sp_off)
            r_on1 = run(args.rowid_binary, db, sql, 1, {"PRUNING_ROWID_SKIP": "1"}, sp_on)
            r_off8 = run(args.rowid_binary, db, sql, 8, {})
            r_on8 = run(args.rowid_binary, db, sql, 8, {"PRUNING_ROWID_SKIP": "1"})
            problems = []
            if "\nSTDERR:" in r_stock:
                problems.append("stock error: %s" % r_stock[-300:])
            for name, r in [("off1", r_off1), ("on1", r_on1), ("off8", r_off8), ("on8", r_on8)]:
                if r != r_stock:
                    problems.append("result %s != stock" % name)
            s_on = [s for s in scans(sp_on) if s["table"] == table]
            s_off = [s for s in scans(sp_off) if s["table"] == table]
            if len(s_on) != len(s_off):
                problems.append("scan count on=%d off=%d" % (len(s_on), len(s_off)))
            pr_on = sum(s["pruned"] for s in s_on)
            pr_off = sum(s["pruned"] for s in s_off)
            rr_on = sum(s.get("pruned_rowid_range", 0) for s in s_on)
            total = s_on[-1]["total_row_groups"] if s_on else 0
            for s in s_on:
                inv = s["pruned"] + s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"] + s["not_reached"]
                if inv != s["total_row_groups"]:
                    problems.append("invariant violated")
                if s["pruned_unattributed"]:
                    problems.append("unattributed")
            if any("pruned_rowid_range" in s for s in s_off):
                problems.append("flag-off output has rowid fields")
            expected_scanned = None
            if allowed == "lm":
                if pr_on < pr_off:
                    problems.append("lm: pruned on %d < off %d" % (pr_on, pr_off))
            elif allowed is not None and len(s_on) == 1:
                rgs = set()
                for g in range((n + RG - 1) // RG):
                    beg, end = g * RG, min(n, (g + 1) * RG)
                    if any(allowed(r) for r in range(beg, end)):
                        rgs.add(g)
                expected_scanned = len(rgs)
                scanned_on = total - pr_on
                if scanned_on != expected_scanned:
                    problems.append("scanned (not pruned) on=%d expected=%d" % (scanned_on, expected_scanned))
                if pr_off != 0:
                    problems.append("flag off pruned %d" % pr_off)
                if rr_on != pr_on:
                    problems.append("pruned_rowid_range %d != pruned %d" % (rr_on, pr_on))
            rec = {"db": db_name, "where": label, "total_row_groups": total, "pruned_off": pr_off, "pruned_on": pr_on,
                   "pruned_rowid_range": rr_on, "expected_unpruned": expected_scanned, "problems": problems}
            report.append(rec)
            if problems:
                n_fail += 1
                print("FAIL", db_name, label, problems, flush=True)
            else:
                n_ok += 1
        print("%s: done (%d tests so far, %d failed)" % (db_name, n_ok + n_fail, n_fail), flush=True)
    print("TOTAL ok=%d failed=%d" % (n_ok, n_fail))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=1)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
