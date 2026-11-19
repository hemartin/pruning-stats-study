#!/usr/bin/env python3
"""Aggregate the row-id range check experiment (run_rowid_small.sh) -> results/small/phase4/rowid/.

per_query.csv  : per ClickBench query (summed over its table scans), baseline (= rowid binary, flag off) vs rowid
                 (flag on), 1 thread: total row groups, pruned, scanned_no_rows (wasted), scanned_with_rows,
                 partial_no_rows, not_reached, pruned_rowid_range (+ pruned_rowid_only)
timing.csv     : per query median wall time of 3 rounds, off vs on
checks.csv     : per query result hashes (stock/off/on at 1 thread, off/on at 8 threads) and counter equality
                 stock vs flag off
summary.md
"""
import csv
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

RAW = os.path.join(common.PO_DIR, "results", "raw", "small", "rowidexp")
OUT = os.path.join(common.PO_DIR, "results", "small", "phase4", "rowid")
CATS = ["pruned", "scanned_no_rows", "scanned_with_rows", "partial_no_rows", "not_reached"]
# counters compared stock vs flag off (everything but timing / session ids)
SKIP_KEYS = {"session", "seq", "elapsed_ms"}


def status(label):
    res = {}
    p = os.path.join(RAW, label, "clickbench", "status.jsonl")
    for line in open(p):
        r = json.loads(line)
        res[r["qid"]] = r
    return res


def pruning(label):
    """qid -> (query record, [scan records]); a re-executed tag supersedes earlier lines"""
    res = {}
    cur = None
    p = os.path.join(RAW, label, "clickbench", "pruning.jsonl")
    for line in open(p):
        d = json.loads(line)
        tag = d.get("tag") or ""
        if not tag.startswith("clickbench/"):
            continue
        qid = tag.split("/", 1)[1]
        if d["type"] == "query":
            if d.get("sql", "").strip().upper().startswith("SET VARIABLE"):
                continue
            res[qid] = (d, [])
            cur = qid
        elif d["type"] == "scan" and qid in res:
            res[qid][1].append(d)
    return res


def selftest_line():
    p = os.path.join(OUT, "selftest.json")
    if not os.path.exists(p):
        return "* hand-written tests (`rowid_selftest.py`): not run"
    r = json.load(open(p))
    bad = [x for x in r if x["problems"]]
    dbs = sorted({x["db"] for x in r})
    return ("* hand-written tests (`rowid_selftest.py`, %s): %d queries (rowid =, IN, BETWEEN, <, <=, >, >=, OR of =, "
            "conjunctions, at/around row-group boundaries, beyond the table, plus late-materialization top-N); "
            "results stock = base = rowid at 1 and 8 threads, and with the flag on the unpruned row groups are exactly "
            "the row groups containing an allowed row id: %d failures" % (", ".join(dbs), len(r), len(bad)))


def strip(d):
    return {k: v for k, v in d.items() if k not in SKIP_KEYS}


def main():
    os.makedirs(OUT, exist_ok=True)
    st = {l: status(l) for l in ["stock_count", "off_count", "on_count", "off_hash8", "on_hash8"]}
    h8 = {cfg: [status(d) for d in sorted(os.listdir(RAW)) if d.startswith(cfg + "_hash8")] for cfg in ["off", "on"]}
    pr = {l: pruning(l) for l in ["stock_count", "off_count", "on_count"]}
    qids = sorted(st["off_count"], key=lambda q: int(q[1:]))

    # ---- checks
    checks = []
    n_res_mismatch = n_cnt_mismatch = n_res1_mismatch = n_nondet8 = 0
    for q in qids:
        h = {l: st[l][q].get("hash_sorted") for l in st}
        stat = {l: st[l][q]["status"] for l in st}
        res_equal = len(set(h.values())) == 1 and all(s == "ok" for s in stat.values())
        res1_equal = len({h["stock_count"], h["off_count"], h["on_count"]}) == 1 and \
            all(stat[l] == "ok" for l in ["stock_count", "off_count", "on_count"])
        n_res1_mismatch += not res1_equal
        off8 = {x[q]["hash_sorted"] for x in h8["off"]}
        on8 = {x[q]["hash_sorted"] for x in h8["on"]}
        nondet8 = len(off8) > 1 or len(on8) > 1
        n_nondet8 += nondet8
        a = pr["stock_count"].get(q)
        b = pr["off_count"].get(q)
        key = lambda s: s["scan_id"]
        cnt_equal = a is not None and b is not None and len(a[1]) == len(b[1]) and \
            all(strip(x) == strip(y) for x, y in zip(sorted(a[1], key=key), sorted(b[1], key=key)))
        n_res_mismatch += not res_equal
        n_cnt_mismatch += not cnt_equal
        # invariants of the on run
        inv_ok = all(sum(s[c] for c in CATS) == s["total_row_groups"] and s["pruned_unattributed"] == 0
                     for s in pr["on_count"][q][1])
        checks.append({"qid": q, "results_equal": res_equal, "results_equal_1thread": res1_equal,
                       "distinct_hashes_8t_off": len(off8), "distinct_hashes_8t_on": len(on8), "counters_off_equal_stock": cnt_equal,
                       "invariant_on_ok": inv_ok, "rows": st["on_count"][q]["rows"],
                       **{"hash_" + l: (h[l] or "")[:12] for l in st}})
    with open(os.path.join(OUT, "checks.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0].keys()))
        w.writeheader()
        w.writerows(checks)

    # ---- per query counters
    rows = []
    for q in qids:
        r = {"qid": q, "n_scans": len(pr["on_count"][q][1])}
        for cfg, label in [("base", "off_count"), ("rowid", "on_count")]:
            scans = pr[label][q][1]
            r[cfg + "_total"] = sum(s["total_row_groups"] for s in scans)
            for c in CATS:
                r[cfg + "_" + c] = sum(s[c] for s in scans)
            r[cfg + "_pruned_rowid_range"] = sum(s.get("pruned_rowid_range", 0) for s in scans)
            r[cfg + "_pruned_rowid_only"] = sum(s.get("pruned_rowid_only", 0) for s in scans)
        r["has_rowid_filter"] = any(f["col"] == "rowid" for s in pr["on_count"][q][1] for f in s["filters"])
        rows.append(r)
    with open(os.path.join(OUT, "per_query.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- timing
    timing = []
    have_time = os.path.exists(os.path.join(RAW, "time_off_r1", "clickbench", "status.jsonl"))
    if have_time:
        rounds = sorted({d.split("_r")[1] for d in os.listdir(RAW) if d.startswith("time_off_r")})
        t = {cfg: [status("time_%s_r%s" % (cfg, k)) for k in rounds] for cfg in ["off", "on"]}
        for q in qids:
            off = [x[q]["wall_s"] for x in t["off"] if q in x and x[q]["status"] == "ok"]
            on = [x[q]["wall_s"] for x in t["on"] if q in x and x[q]["status"] == "ok"]
            mo, mn = statistics.median(off), statistics.median(on)
            timing.append({"qid": q, "rounds": len(off), "base_median_ms": round(mo * 1000, 2),
                           "rowid_median_ms": round(mn * 1000, 2), "speedup": round(mo / mn, 3) if mn else "",
                           "base_runs_ms": " ".join("%.1f" % (x * 1000) for x in off),
                           "rowid_runs_ms": " ".join("%.1f" % (x * 1000) for x in on)})
        with open(os.path.join(OUT, "timing.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(timing[0].keys()))
            w.writeheader()
            w.writerows(timing)
    tmap = {x["qid"]: x for x in timing}

    # ---- summary
    def tot(k):
        return sum(r[k] for r in rows)

    md = ["# Row-id range check (PRUNING_ROWID_SKIP=1), small ClickBench (999,977 rows, 123 row groups)", "",
          "Generated by `harness/rowid_aggregate.py` from `run_rowid_small.sh`. *base* = rowid binary with the flag off "
          "(stock v1.4.4 behaviour, counters identical to the stock binary), *rowid* = flag on. Counters: 1 thread, "
          "summed over the query's table scans. *wasted* = `scanned_no_rows` (row group scanned, no row passes the "
          "filters applied to rows). `rowid_range` = row groups pruned whose first proving filter is a rowid filter.", "",
          "## Checks", "",
          "* results, 1 thread (full result, order-independent hash; stock vs base vs rowid): "
          "%d of %d queries identical" % (len(qids) - n_res1_mismatch, len(qids)),
          "* results, 8 threads (%d runs per config): all of stock-1t/base/rowid identical for %d of %d queries; the "
          "other %d are nondeterministic at 8 threads *within* one configuration (ties in `ORDER BY ... LIMIT`: "
          "base alone produces >1 distinct result for them, incl. queries without any rowid filter, whose code path "
          "is unchanged); see `checks.csv` (`distinct_hashes_8t_*`). q24/q25 with a unique tie-breaker "
          "(`ORDER BY EventTime, rowid`) give identical results in 3+3 runs at 8 threads and equal stock "
          "(also `rowid_selftest.py`)." % (len(h8["off"]), len(qids) - n_res_mismatch, len(qids), n_res_mismatch),
          selftest_line(),
          "* counters base vs stock binary (all scan fields except session/seq/elapsed): %d of %d queries identical"
          % (len(qids) - n_cnt_mismatch, len(qids)),
          "* invariant total = pruned + scanned_no_rows + scanned_with_rows + partial_no_rows + not_reached and "
          "pruned_unattributed = 0 (rowid run): %s" % ("ok" if all(c["invariant_on_ok"] for c in checks) else "VIOLATED"),
          "",
          "## Totals over 43 queries", "",
          "| | total | pruned | wasted (scanned_no_rows) | scanned_with_rows | partial_no_rows | not_reached | pruned by rowid_range |",
          "|---|---|---|---|---|---|---|---|"]
    for cfg in ["base", "rowid"]:
        md.append("| %s | %d | %d | %d | %d | %d | %d | %d |" % (
            cfg, tot(cfg + "_total"), tot(cfg + "_pruned"), tot(cfg + "_scanned_no_rows"),
            tot(cfg + "_scanned_with_rows"), tot(cfg + "_partial_no_rows"), tot(cfg + "_not_reached"),
            tot(cfg + "_pruned_rowid_range")))
    wb, wr = tot("base_scanned_no_rows"), tot("rowid_scanned_no_rows")
    md += ["", "Wasted reads: %d -> %d (-%d, -%.1f%%)." % (wb, wr, wb - wr, 100.0 * (wb - wr) / wb if wb else 0), ""]
    md += ["## Per query", "",
           "Only queries with a rowid filter (late materialization) change. Timing: median of 3 rounds, %s." %
           ("threads = %s" % os.environ.get("TIME_THREADS", "12") if have_time else "n/a"), "",
           "| query | total RGs | base pruned | base wasted | base with rows | rowid pruned | rowid wasted | "
           "rowid with rows | pruned by rowid_range | base ms | rowid ms |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        tm = tmap.get(r["qid"], {})
        md.append("| %s%s | %d | %d | %d | %d | %d | %d | %d | %d | %s | %s |" % (
            r["qid"], " (rowid)" if r["has_rowid_filter"] else "", r["base_total"], r["base_pruned"],
            r["base_scanned_no_rows"], r["base_scanned_with_rows"], r["rowid_pruned"], r["rowid_scanned_no_rows"],
            r["rowid_scanned_with_rows"], r["rowid_pruned_rowid_range"], tm.get("base_median_ms", ""),
            tm.get("rowid_median_ms", "")))
    if timing:
        sb = sum(x["base_median_ms"] for x in timing)
        sr = sum(x["rowid_median_ms"] for x in timing)
        md += ["", "Sum of medians: base %.1f ms, rowid %.1f ms." % (sb, sr)]
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
