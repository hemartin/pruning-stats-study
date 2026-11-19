#!/usr/bin/env python3
"""Aggregate the pruning counters of a counting run into result tables (CSV + Markdown).

Input : results/raw/<scale>/<label>/<setup>/{pruning.jsonl,status.jsonl}
Output: results/<scale>/
   micro_summary.{csv,md}        one row per microbenchmark setup (counters summed and averaged over queries)
   established_queries.{csv,md}  one row per TPC-H / TPC-DS / ClickBench query (summed over its table scans)
   benchmark_totals.{csv,md}     one row per benchmark
   scan_detail.csv               one row per (query, table scan), incl. the scan's pushed-down filter set
   filter_detail.csv             one row per (query, table scan, pushed-down filter leaf) with pruned counts
   pruned_by_predicate.csv       pruned row groups per (setup or query, table.column, filter kind, origin)
   wasted_by_filterset.csv       per (benchmark, table, filter set): row groups scanned without a qualifying row
   runtimes.csv                  per setup: query wall times of the runs found under results/raw/<scale>/
   invariants.txt                per-scan invariant check

Row-group categories per scan (see README): total = pruned + scanned_no_rows + scanned_with_rows
+ partial_no_rows + not_reached; scanned = scanned_no_rows + scanned_with_rows + partial_no_rows.
"""
import argparse
import collections
import csv
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SCAN_COUNTERS = ["total_row_groups", "pruned", "scanned", "scanned_no_rows", "scanned_no_rows_all_segments_skipped",
                 "scanned_no_rows_some_segments_skipped", "scanned_with_rows", "scanned_with_rows_partial",
                 "partial_no_rows", "not_reached", "incl_optional_with_rows", "incl_optional_no_rows",
                 "incl_optional_partial_no_rows", "rows_scanned", "rows_passed", "rows_passed_incl_optional",
                 "pruned_unattributed"]


def load_run(setup_dir):
    """Returns {tag: (query_record, [scan_records])} keeping the last execution of every tag."""
    path = os.path.join(setup_dir, "pruning.jsonl")
    queries, scans = {}, collections.defaultdict(list)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (r.get("session"), r.get("seq"))
            if r["type"] == "query":
                queries[key] = r
            elif r["type"] == "scan":
                scans[key].append(r)
    by_tag = {}
    for key, q in queries.items():  # insertion order = file order, later executions overwrite earlier ones
        tag = q.get("tag") or ""
        if not tag or q.get("sql", "").lstrip().upper().startswith("SET VARIABLE"):
            continue
        by_tag[tag] = (q, sorted(scans.get(key, []), key=lambda s: s["scan_id"]))
    return by_tag


def load_status(setup_dir):
    path = os.path.join(setup_dir, "status.jsonl")
    res = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    res[r["tag"]] = r
    return res


def filter_set(scan, applied_only=False):
    fs = [f["filter"] if f["origin"] == "static" else "%s [%s]" % (f["filter"], f["origin"])
          for f in scan["filters"] if f["applied_to_rows"] or not applied_only]
    return " AND ".join(fs) if fs else "(no filters)"


def query_metrics(q, scans, status):
    m = {c: sum(s.get(c, 0) for s in scans) for c in SCAN_COUNTERS}
    m["n_scans"] = len(scans)
    m["n_scans_with_filters"] = sum(1 for s in scans if s["has_filters"])
    m["plan_empty_results"] = q.get("plan_empty_results", 0)
    m["bound_table_refs"] = len(q.get("bound_tables", []))
    m["plan_table_scans"] = len(q.get("plan_scan_tables", []))
    m["executed_scans"] = len(scans)
    m["elapsed_ms"] = q.get("elapsed_ms")
    m["error"] = q.get("error") or (status or {}).get("error")
    m["status"] = (status or {}).get("status", "ok" if not q.get("error") else "error")
    return m


def pct(a, b):
    return round(100.0 * a / b, 2) if b else None


def predicate_key(scan, f):
    return "%s.%s %s [%s]" % (scan["table"], f["col"], f["kind"], f["origin"])


def write_csv(path, rows, cols):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return ("%.2f" % v).rstrip("0").rstrip(".") if abs(v) < 1e6 else "%.0f" % v
    return str(v)


def md_table(rows, cols, headers=None):
    headers = headers or cols
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(fmt(r.get(c)).replace("|", "\\|") for c in cols) + " |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--label", default="count")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    raw = common.raw_dir(args.scale, args.label)
    out_dir = args.out or common.results_dir(args.scale)
    os.makedirs(out_dir, exist_ok=True)

    micro_rows, est_rows, scan_rows, filter_rows, pred_rows, inv_lines = [], [], [], [], [], []
    wasted = collections.Counter()
    wasted_scans = collections.Counter()
    wasted_shape = collections.Counter()
    bench_tot = collections.OrderedDict()
    for setup in common.all_setups():
        sdir = os.path.join(raw, setup.name)
        runs = load_run(sdir)
        status = load_status(sdir)
        if not runs and not status:
            continue
        n_expected = len(setup.queries())
        per_query = []
        pred_counter = collections.Counter()
        for qid in setup.qids(n_expected):
            tag = "%s/%s" % (setup.name, qid)
            st = status.get(tag)
            if tag not in runs:
                if st is not None:
                    per_query.append((qid, None, [], {"status": st["status"], "error": st.get("error")}))
                continue
            q, scans = runs[tag]
            m = query_metrics(q, scans, st)
            per_query.append((qid, q, scans, m))
            qpred = collections.Counter()
            for s in scans:
                tot = s["pruned"] + s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"] + \
                    s["not_reached"]
                sc = s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"]
                if tot != s["total_row_groups"] or sc != s["scanned"] or s.get("out_of_range_row_groups", 0):
                    inv_lines.append("VIOLATION %s scan %d: %s" % (tag, s["scan_id"], json.dumps(s)[:400]))
                srow = {"benchmark": setup.benchmark, "setup": setup.name, "qid": qid, "scan_id": s["scan_id"],
                        "table": s["table"], "has_filters": s["has_filters"], "has_optional": s["has_optional"],
                        "filter_set": filter_set(s), "applied_filter_set": filter_set(s, True)}
                for c in SCAN_COUNTERS + ["vectors_scanned", "vectors_segment_skipped"]:
                    srow[c] = s.get(c, 0)
                scan_rows.append(srow)
                if s["scanned_no_rows"]:
                    shape = " AND ".join("%s %s%s" % (f["col"], f["kind"], "" if f["origin"] == "static" else
                                                      " [%s]" % f["origin"]) for f in s["filters"]) or "(none)"
                    wasted_shape[(setup.benchmark, setup.name, s["table"], shape)] += s["scanned_no_rows"]
                    wasted[(setup.benchmark, s["table"], filter_set(s))] += s["scanned_no_rows"]
                    wasted_scans[(setup.benchmark, s["table"], filter_set(s))] += 1
                for i, f in enumerate(s["filters"]):
                    filter_rows.append({"benchmark": setup.benchmark, "setup": setup.name, "qid": qid,
                                        "scan_id": s["scan_id"], "table": s["table"], "filter_idx": i,
                                        "col": f["col"], "col_type": f["col_type"], "kind": f["kind"],
                                        "origin": f["origin"], "applied_to_rows": f["applied_to_rows"],
                                        "filter": f["filter"], "pruned_first": f["pruned_first"],
                                        "prunable_alone": f["prunable_alone"],
                                        "scan_total_row_groups": s["total_row_groups"],
                                        "scan_pruned": s["pruned"], "scan_scanned_no_rows": s["scanned_no_rows"],
                                        "scan_scanned_with_rows": s["scanned_with_rows"]})
                    if f["pruned_first"]:
                        qpred[predicate_key(s, f)] += f["pruned_first"]
                if s["pruned_unattributed"]:
                    qpred["%s (unattributed)" % s["table"]] += s["pruned_unattributed"]
            m["pruned_by_predicate"] = "; ".join("%s: %d" % kv for kv in qpred.most_common())
            pred_counter.update(qpred)
            for k, v in qpred.items():
                pred_rows.append({"benchmark": setup.benchmark, "setup": setup.name, "qid": qid, "predicate": k,
                                  "pruned_row_groups": v})
        ok = [x for x in per_query if x[1] is not None and x[3]["status"] == "ok"]
        failed = [x for x in per_query if x[1] is None or x[3]["status"] != "ok"]
        if setup.benchmark == "micro":
            row = {"benchmark": "micro", "setup": setup.name, "queries": n_expected, "queries_ok": len(ok),
                   "queries_failed": len(failed)}
            for c in SCAN_COUNTERS + ["n_scans", "plan_empty_results"]:
                tot = sum(x[3][c] for x in ok)
                row["sum_" + c] = tot
                row["avg_" + c] = round(tot / len(ok), 3) if ok else None
            row["pct_pruned"] = pct(row["sum_pruned"], row["sum_total_row_groups"])
            row["pct_scanned_no_rows_of_total"] = pct(row["sum_scanned_no_rows"], row["sum_total_row_groups"])
            row["pct_scanned_no_rows_of_scanned"] = pct(row["sum_scanned_no_rows"], row["sum_scanned"])
            row["pruned_by_predicate"] = "; ".join("%s: %d" % kv for kv in pred_counter.most_common())
            el = [x[3]["elapsed_ms"] for x in ok if x[3]["elapsed_ms"] is not None]
            row["avg_elapsed_ms"] = round(statistics.mean(el), 3) if el else None
            micro_rows.append(row)
        else:
            for qid, q, scans, m in per_query:
                row = {"benchmark": setup.benchmark, "query": qid, "status": m["status"]}
                if q is not None:
                    row.update({k: m[k] for k in m})
                    row["pct_pruned"] = pct(m["pruned"], m["total_row_groups"])
                    row["pct_scanned_no_rows_of_scanned"] = pct(m["scanned_no_rows"], m["scanned"])
                    # table references bound but without a scan in the physical plan (optimizer removed them,
                    # e.g. EMPTY_RESULT from statistics) and plan scans that never initialised
                    row["removed_scans"] = m["bound_table_refs"] - m["plan_table_scans"]
                    row["unexecuted_plan_scans"] = m["plan_table_scans"] - m["executed_scans"]
                else:
                    row["error"] = m.get("error")
                est_rows.append(row)
        bt = bench_tot.setdefault(setup.benchmark, collections.Counter())
        bt["queries"] += n_expected
        bt["queries_ok"] += len(ok)
        for x in ok:
            for c in SCAN_COUNTERS + ["n_scans", "plan_empty_results"]:
                bt[c] += x[3][c]

    # ---------------------------------------------------------------- write tables
    mcols = ["benchmark", "setup", "queries", "queries_ok", "queries_failed"]
    for c in SCAN_COUNTERS + ["n_scans", "plan_empty_results"]:
        mcols += ["sum_" + c, "avg_" + c]
    mcols += ["pct_pruned", "pct_scanned_no_rows_of_total", "pct_scanned_no_rows_of_scanned", "avg_elapsed_ms",
              "pruned_by_predicate"]
    write_csv(os.path.join(out_dir, "micro_summary.csv"), micro_rows, mcols)
    ecols = ["benchmark", "query", "status", "n_scans", "n_scans_with_filters"] + SCAN_COUNTERS + \
        ["pct_pruned", "pct_scanned_no_rows_of_scanned", "plan_empty_results", "bound_table_refs",
         "plan_table_scans", "executed_scans", "removed_scans", "unexecuted_plan_scans", "elapsed_ms",
         "pruned_by_predicate", "error"]
    write_csv(os.path.join(out_dir, "established_queries.csv"), est_rows, ecols)
    scols = ["benchmark", "setup", "qid", "scan_id", "table", "has_filters", "has_optional"] + SCAN_COUNTERS + \
        ["vectors_scanned", "vectors_segment_skipped", "filter_set", "applied_filter_set"]
    write_csv(os.path.join(out_dir, "scan_detail.csv"), scan_rows, scols)
    fcols = list(filter_rows[0].keys()) if filter_rows else ["benchmark"]
    write_csv(os.path.join(out_dir, "filter_detail.csv"), filter_rows, fcols)
    write_csv(os.path.join(out_dir, "pruned_by_predicate.csv"), pred_rows,
              ["benchmark", "setup", "qid", "predicate", "pruned_row_groups"])
    wrows = [{"benchmark": b, "table": t, "filter_set": fs, "scans": wasted_scans[(b, t, fs)],
              "scanned_no_rows": n} for (b, t, fs), n in wasted.most_common()]
    write_csv(os.path.join(out_dir, "wasted_by_filterset.csv"), wrows,
              ["benchmark", "table", "filter_set", "scans", "scanned_no_rows"])
    shape_rows = [{"benchmark": b, "setup": st, "table": t, "filter_columns_and_kinds": sh, "scanned_no_rows": n}
                  for (b, st, t, sh), n in wasted_shape.most_common()]
    write_csv(os.path.join(out_dir, "wasted_by_filter_shape.csv"), shape_rows,
              ["benchmark", "setup", "table", "filter_columns_and_kinds", "scanned_no_rows"])
    trows = []
    for b, c in bench_tot.items():
        r = {"benchmark": b}
        r.update(c)
        r["pct_pruned"] = pct(c["pruned"], c["total_row_groups"])
        r["pct_scanned_no_rows_of_scanned"] = pct(c["scanned_no_rows"], c["scanned"])
        trows.append(r)
    tcols = ["benchmark", "queries", "queries_ok", "n_scans", "total_row_groups", "pruned", "scanned",
             "scanned_no_rows", "scanned_no_rows_all_segments_skipped", "scanned_with_rows", "partial_no_rows",
             "not_reached", "incl_optional_no_rows", "plan_empty_results", "pct_pruned",
             "pct_scanned_no_rows_of_scanned"]
    write_csv(os.path.join(out_dir, "benchmark_totals.csv"), trows, tcols)

    # runtimes of all runs found
    rt_rows = []
    rbase = os.path.join(common.PO_DIR, "results", "raw", args.scale)
    for label in sorted(os.listdir(rbase)) if os.path.isdir(rbase) else []:
        for setup in common.all_setups():
            st = load_status(os.path.join(rbase, label, setup.name))
            walls = [r["wall_s"] for r in st.values() if r["status"] == "ok"]
            if not st:
                continue
            rt_rows.append({"run": label, "setup": setup.name, "queries": len(st), "ok": len(walls),
                            "failed": len(st) - len(walls),
                            "total_s": round(sum(walls), 3),
                            "mean_s": round(statistics.mean(walls), 4) if walls else None,
                            "median_s": round(statistics.median(walls), 4) if walls else None,
                            "max_s": round(max(walls), 4) if walls else None})
    write_csv(os.path.join(out_dir, "runtimes.csv"), rt_rows,
              ["run", "setup", "queries", "ok", "failed", "total_s", "mean_s", "median_s", "max_s"])
    with open(os.path.join(out_dir, "invariants.txt"), "w") as f:
        f.write("scans checked: %d, violations: %d\n" % (len(scan_rows), len(inv_lines)))
        f.write("\n".join(inv_lines) + "\n")

    # ---------------------------------------------------------------- markdown
    md = ["# Pruning opportunity, scale `%s`\n" % args.scale,
          "Partition = row group of 8,192 rows. *pruned*: skipped by the row-group min/max zonemap. "
          "*scanned, no rows* (3a): fully scanned, no row satisfied all pushed-down filters that are applied to "
          "rows (could have been pruned). *scanned, with rows* (3b): at least one such row. *partial/not reached*: "
          "query stopped early (LIMIT). *incl. optional, no rows*: like 3a but also requiring the optional "
          "(zonemap-only) filters, i.e. IN lists / OR clauses / join IN lists / top-N thresholds. "
          "See ../../README.md for the exact semantics.\n",
          "Scans checked against the invariant: %d, violations: %d\n" % (len(scan_rows), len(inv_lines)),
          "## Benchmark totals\n",
          md_table(trows, tcols[:13] + ["pct_pruned", "pct_scanned_no_rows_of_scanned"]),
          "## Microbenchmarks (per setup; sums over all queries, avg = per query)\n",
          md_table(micro_rows, ["setup", "queries_ok", "avg_total_row_groups", "avg_pruned", "avg_scanned",
                                "avg_scanned_no_rows", "avg_scanned_no_rows_all_segments_skipped",
                                "avg_scanned_with_rows", "avg_rows_passed", "pct_pruned",
                                "pct_scanned_no_rows_of_scanned", "avg_elapsed_ms"],
                   ["setup", "queries ok", "avg total", "avg pruned", "avg scanned", "avg scanned no rows (3a)",
                    "of which seg-skipped", "avg scanned with rows (3b)", "avg qualifying rows", "% pruned",
                    "% of scanned w/o rows", "avg ms (counting)"]),
          "\nSums over the 1,000 queries of each setup:\n\n",
          md_table(micro_rows, ["setup", "sum_total_row_groups", "sum_pruned", "sum_scanned", "sum_scanned_no_rows",
                                "sum_scanned_with_rows", "sum_partial_no_rows", "sum_not_reached",
                                "pruned_by_predicate"],
                   ["setup", "total", "pruned", "scanned", "scanned no rows (3a)", "scanned with rows (3b)",
                    "partial, no rows", "not reached", "pruned by predicate"])]
    for b in ["tpch", "tpcds", "clickbench"]:
        rows = [r for r in est_rows if r["benchmark"] == b]
        if not rows:
            continue
        md.append("\n## %s (per query, summed over its table scans)\n\n" % b)
        md.append(md_table(rows, ["query", "status", "n_scans", "total_row_groups", "pruned", "scanned",
                                  "scanned_no_rows", "scanned_no_rows_all_segments_skipped", "scanned_with_rows",
                                  "partial_no_rows", "not_reached", "incl_optional_no_rows",
                                  "plan_empty_results", "removed_scans", "unexecuted_plan_scans", "elapsed_ms",
                                  "pruned_by_predicate"],
                           ["query", "status", "scans", "total", "pruned", "scanned", "scanned no rows (3a)",
                            "of which seg-skipped", "scanned with rows (3b)", "partial, no rows", "not reached",
                            "3a incl. optional", "EMPTY_RESULT ops", "bound refs - plan scans",
                            "plan scans not executed", "ms",
                            "pruned by predicate"]))
    md.append("\n## Row groups scanned without qualifying rows (3a) by filter shape (columns, kinds)\n\n")
    md.append(md_table(shape_rows[:40], ["benchmark", "setup", "table", "filter_columns_and_kinds",
                                         "scanned_no_rows"]))
    md.append("\n## TPC-H / TPC-DS / ClickBench: filter sets responsible for 3a row groups (top 40)\n\n")
    md.append(md_table([w for w in wrows if w["benchmark"] != "micro"][:40],
                       ["benchmark", "table", "filter_set", "scans", "scanned_no_rows"]))
    md.append("\n## Query runtimes\n\n")
    md.append(md_table(rt_rows, ["run", "setup", "queries", "ok", "failed", "total_s", "mean_s", "median_s",
                                 "max_s"]))
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(md))
    print("wrote %s (%d micro setups, %d established queries, %d scans, %d invariant violations)" %
          (out_dir, len(micro_rows), len(est_rows), len(scan_rows), len(inv_lines)))


if __name__ == "__main__":
    main()
