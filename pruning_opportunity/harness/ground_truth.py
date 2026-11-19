#!/usr/bin/env python3
"""Independent ground truth for the pruning counters, computed with plain SQL by the pip `duckdb` package
(a different engine build) on the same database files.

1. Layout: per table, pragma_storage_info must show row groups of exactly 8,192 rows (except the last one), so
   that row group k holds rowids [8192k, 8192(k+1)) and `rowid // 8192` is the row-group number; the number of
   row groups must equal the counters' total_row_groups.
2. Qualifying rows: for every sampled scan, SELECT rowid // 8192, count(*) FROM t WHERE <the scan's filters that
   are applied to rows> GROUP BY 1. The number of row groups with >= 1 match must equal scanned_with_rows (pruning
   is sound, so no matching row group can be pruned) and the number of matching rows must equal rows_passed.
   The same with the optional filters added is compared with incl_optional_with_rows (skipped when a top-N filter
   is present: its threshold changes while the scan runs).
3. Pruning: per row group min/max/count of every filter column; a row group is predicted prunable if some leaf
   filter is impossible given [min, max] (constant comparisons, IN lists, IS [NOT] NULL). The predicted count must
   equal `pruned`. VARCHAR columns are reported separately (DuckDB keeps only 8-byte string prefixes in its
   statistics, so exact min/max can predict more pruning).
Scans that stopped early (LIMIT: partial or not-reached row groups) are skipped for 2 and 3.
"""
import argparse
import collections
import csv
import json
import os
import random
import re
import sys
import time

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from aggregate import load_run  # noqa: E402

RG = 8192


def qi(name):
    return '"' + name.replace('"', '""') + '"'


def leaf_prune_condition(f, k):
    """SQL condition (over columns mn{k}, mx{k}, nn{k}, n) under which leaf f proves 'no match', or None."""
    mn, mx, nn = "mn%d" % k, "mx%d" % k, "nn%d" % k
    kind = f["kind"]
    if kind.startswith("cmp") or kind.startswith("optional(cmp"):
        op, v = f.get("op"), f.get("value")
        if v is None:
            return None
        cond = {"=": "(%s < %s OR %s > %s)" % (v, mn, v, mx), "<": "%s >= %s" % (mn, v),
                "<=": "%s > %s" % (mn, v), ">": "%s <= %s" % (mx, v), ">=": "%s < %s" % (mx, v),
                "!=": "(%s = %s AND %s = %s)" % (mn, v, mx, v)}.get(op)
        if cond is None:
            return None
        return "(%s = 0 OR %s)" % (nn, cond)
    if kind in ("optional(in)", "in"):
        vals = f.get("values")
        if not vals:
            return None
        return "(%s = 0 OR (%s))" % (nn, " AND ".join("(%s < %s OR %s > %s)" % (v, mn, v, mx) for v in vals))
    if kind == "is_null":
        return "(%s = n)" % nn
    if kind == "is_not_null":
        return "(%s = 0)" % nn
    return None


def verify_layout(con, table, cache):
    if table in cache:
        return cache[table]
    rows = con.execute("SELECT row_group_id, sum(count) FROM pragma_storage_info(?) WHERE column_id = 0 AND "
                       "column_path = '[0]' GROUP BY 1 ORDER BY 1", [table]).fetchall()
    n = len(rows)
    irregular = [r for i, r in enumerate(rows) if r[1] != RG and i != n - 1]
    total = con.execute("SELECT count(*) FROM %s" % qi(table)).fetchone()[0]
    res = {"row_groups": n, "irregular": len(irregular), "rows": total,
           "ok": not irregular and n == (total + RG - 1) // RG}
    cache[table] = res
    return res


OR_CHILD = re.compile(r'^\((?:"([^"]+)"|(\w+))(<=|>=|!=|=|<|>)(.+)\)$')


def or_prune_condition(f, k):
    """optional(or) of constant comparisons on one column: prunable iff every child is impossible."""
    parts = f.get("sql", "").split(") OR (")
    conds = []
    for i, part in enumerate(parts):
        part = ("(" if i else "") + part + (")" if i < len(parts) - 1 else "")
        m = OR_CHILD.match(part)
        if not m:
            return None
        c = leaf_prune_condition({"kind": "cmp", "op": m.group(3), "value": m.group(4)}, k)
        if c is None:
            return None
        conds.append(c)
    return "(" + " AND ".join(conds) + ")"


def prune_predicate(scan):
    """(SQL select list, SQL predicate) predicting the row groups DuckDB prunes from per-row-group min/max, or a
    string explaining why no prediction is possible."""
    leaves = scan["filters"]
    if not leaves:
        return "", "false"
    if any(f["origin"] == "topn" for f in leaves):
        return "skipped_topn"
    cols = sorted({f["col"] for f in leaves if f["col"] != "rowid"})
    colidx = {c: i for i, c in enumerate(cols)}
    conds = []
    for f in leaves:
        if f["col"] == "rowid":
            # RowGroup::CheckZonemap never prunes on rowid (no row-group statistics for the rowid column);
            # rowid filters only skip vectors inside RowIdColumnData::Filter
            continue
        k = colidx[f["col"]]
        c = or_prune_condition(f, k) if f["kind"] == "optional(or)" else leaf_prune_condition(f, k)
        if c is None:
            return "unsupported_filter"
        conds.append(c)
    sel = "".join(", min(%s) AS mn%d, max(%s) AS mx%d, count(%s) AS nn%d" % (qi(c), i, qi(c), i, qi(c), i)
                  for c, i in colidx.items())
    return sel, (" OR ".join(conds) if conds else "false")


def check_scan(con, scan, layout):
    r = {"table": scan["table"], "total_row_groups": scan["total_row_groups"], "pruned": scan["pruned"],
         "scanned_with_rows": scan["scanned_with_rows"], "rows_passed": scan["rows_passed"],
         "layout_ok": layout["ok"] and layout["row_groups"] == scan["total_row_groups"]}
    if scan["partial_no_rows"] or scan["not_reached"] or scan["scanned_with_rows_partial"]:
        r["status"] = "skipped_early_stop"
        return r
    t = qi(scan["table"])
    applied = [f for f in scan["filters"] if f["applied_to_rows"]]
    optional = [f for f in scan["filters"] if not f["applied_to_rows"]]
    has_topn = any(f["origin"] == "topn" for f in scan["filters"])
    has_rowid_optional = any(f["col"] == "rowid" for f in optional)
    match = " AND ".join("(%s)" % f["sql"] for f in applied if f.get("sql")) or "true"
    match_opt = " AND ".join("(%s)" % f["sql"] for f in applied + optional if f.get("sql")) or "true"
    pp = prune_predicate(scan)
    r["pruned_check"] = pp if isinstance(pp, str) else (
        "approx_varchar" if any(f["col_type"].startswith("VARCHAR") for f in scan["filters"]) else "exact")
    sel, pred = ("", "NULL") if isinstance(pp, str) else pp
    # the prune predicate refers to aggregates: compute them in an inner aggregation
    q = ("WITH g AS (SELECT rowid // %d AS rg, count(*) AS n, count(*) FILTER (WHERE %s) AS c, "
         "count(*) FILTER (WHERE %s) AS co%s FROM %s GROUP BY rg), h AS (SELECT c, co, (%s) AS p FROM g) "
         "SELECT count(*) FILTER (WHERE p), count(*) FILTER (WHERE c > 0), sum(c), "
         "count(*) FILTER (WHERE c > 0 AND p IS NOT TRUE), sum(c) FILTER (WHERE p IS NOT TRUE), "
         "count(*) FILTER (WHERE co > 0), sum(co) FROM h") % (RG, match, match_opt, sel, t, pred)
    res = con.execute(q).fetchone()
    gt_pruned, all_rg, all_rows, np_rg, np_rows, opt_rg, opt_rows = res
    if not isinstance(pp, str):
        r["gt_pruned"] = gt_pruned
        r["pruned_match"] = gt_pruned == scan["pruned"]
    # qualifying (applied-filter) rows outside pruned row groups; pruning by applied filters is sound, so only
    # optional filters can prune row groups that contain such rows
    if not optional or scan["pruned"] == 0:
        r["gt_with_rows"], r["gt_rows"] = all_rg, int(all_rows or 0)
        r["with_rows_basis"] = "all_row_groups"
    elif not isinstance(pp, str):
        r["gt_with_rows"], r["gt_rows"] = np_rg, int(np_rows or 0)
        r["with_rows_basis"] = "excluding_predicted_pruned"
    else:
        r["with_rows_basis"] = "n/a_optional_pruning_" + pp
    if "gt_with_rows" in r:
        r["with_rows_match"] = r["gt_with_rows"] == scan["scanned_with_rows"]
        r["rows_match"] = r["gt_rows"] == scan["rows_passed"]
    if has_rowid_optional:
        # RowIdColumnData::Filter evaluates the whole rowid filter incl. the optional IN list on the per-vector
        # rowid range, so rows_passed counts rows of 2,048-row vectors containing a listed rowid
        r["with_rows_basis"] = "n/a_rowid_vector_level_optional"
        r.pop("with_rows_match", None)
        r.pop("rows_match", None)
    if optional and not has_topn:
        r["gt_incl_optional_with_rows"], r["gt_incl_optional_rows"] = opt_rg, int(opt_rows or 0)
        r["incl_optional_match"] = (opt_rg == scan["incl_optional_with_rows"] and
                                    r["gt_incl_optional_rows"] == scan["rows_passed_incl_optional"])
    r["status"] = "checked"
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--label", default="count")
    ap.add_argument("--setups", default="all")
    ap.add_argument("--micro-sample", type=int, default=100, help="queries per microbenchmark setup")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--memory-limit", default="6GB")
    args = ap.parse_args()
    raw = common.raw_dir(args.scale, args.label)
    out_dir = common.results_dir(args.scale)
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    layouts = []
    rng = random.Random(args.seed)
    for setup in common.select_setups(args.setups):
        runs = load_run(os.path.join(raw, setup.name))
        if not runs:
            continue
        db = os.path.join(common.db_dir(args.scale), setup.db_name + ".db")
        con = duckdb.connect(db, read_only=True)
        con.execute("SET memory_limit = '%s'" % args.memory_limit)
        con.execute("SET threads TO 4")
        tags = sorted(runs)
        if setup.benchmark == "micro" and args.micro_sample and len(tags) > args.micro_sample:
            tags = sorted(rng.sample(tags, args.micro_sample))
        cache = {}
        t0 = time.time()
        for tag in tags:
            q, scans = runs[tag]
            for s in scans:
                lay = verify_layout(con, s["table"], cache)
                try:
                    r = check_scan(con, s, lay)
                except Exception as e:  # noqa: BLE001
                    r = {"table": s["table"], "status": "gt_error", "error": str(e)[:300]}
                r.update({"benchmark": setup.benchmark, "setup": setup.name, "tag": tag, "scan_id": s["scan_id"],
                          "filters": " AND ".join(f["filter"] + ("" if f["origin"] == "static" else
                                                                 " [%s]" % f["origin"]) for f in s["filters"])})
                rows.append(r)
        for t, lay in cache.items():
            layouts.append(dict(lay, setup=setup.name, table=t))
        con.close()
        sub = [r for r in rows if r["setup"] == setup.name]
        print("%s: %d scans, %.1f s" % (setup.name, len(sub), time.time() - t0), flush=True)

    cols = ["benchmark", "setup", "tag", "scan_id", "table", "status", "layout_ok", "total_row_groups", "pruned",
            "gt_pruned", "pruned_match", "pruned_check", "scanned_with_rows", "gt_with_rows", "with_rows_basis",
            "with_rows_match",
            "rows_passed", "gt_rows", "rows_match", "gt_incl_optional_with_rows", "gt_incl_optional_rows",
            "incl_optional_match", "filters", "error"]
    with open(os.path.join(out_dir, "ground_truth.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(os.path.join(out_dir, "ground_truth_layout.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["setup", "table", "rows", "row_groups", "irregular", "ok"])
        w.writeheader()
        for r in layouts:
            w.writerow(r)
    # summary per setup
    summ = collections.OrderedDict()
    for r in rows:
        s = summ.setdefault(r["setup"], collections.Counter())
        s["scans"] += 1
        s[r["status"]] += 1
        if r["status"] != "checked":
            continue
        s["layout_bad"] += 0 if r["layout_ok"] else 1
        if "with_rows_match" in r:
            s["with_rows_checked"] += 1
            s["with_rows_mismatch"] += 0 if r["with_rows_match"] else 1
            s["rows_mismatch"] += 0 if r["rows_match"] else 1
        else:
            s["with_rows_not_checkable"] += 1
        if "incl_optional_match" in r:
            s["incl_optional_checked"] += 1
            s["incl_optional_mismatch"] += 0 if r["incl_optional_match"] else 1
        pc = r.get("pruned_check")
        if pc in ("exact", "approx_varchar"):
            s["pruned_checked_" + pc] += 1
            s["pruned_mismatch_" + pc] += 0 if r["pruned_match"] else 1
        else:
            s["pruned_" + str(pc)] += 1
    keys = ["scans", "checked", "skipped_early_stop", "gt_error", "layout_bad", "with_rows_checked",
            "with_rows_mismatch", "with_rows_not_checkable",
            "rows_mismatch", "incl_optional_checked", "incl_optional_mismatch", "pruned_checked_exact",
            "pruned_mismatch_exact", "pruned_checked_approx_varchar", "pruned_mismatch_approx_varchar",
            "pruned_unsupported_filter", "pruned_skipped_topn"]
    lines = ["# Ground-truth check (scale %s)\n" % args.scale,
             "| setup | " + " | ".join(keys) + " |", "|---|" + "|".join("---" for _ in keys) + "|"]
    for name, s in summ.items():
        lines.append("| %s | %s |" % (name, " | ".join(str(s.get(k, 0)) for k in keys)))
    lines.append("\nLayout (pragma_storage_info): %d tables, %d with irregular row groups or count mismatch\n" % (
        len(layouts), sum(1 for x in layouts if not x["ok"])))
    mism = [r for r in rows if r["status"] == "checked" and (
        not r.get("with_rows_match", True) or not r.get("rows_match", True) or
        not r.get("incl_optional_match", True) or
        (r.get("pruned_check") == "exact" and not r["pruned_match"]))]
    lines.append("\nMismatches (exact checks): %d\n" % len(mism))
    for r in mism[:200]:
        lines.append("- %s scan %s (%s): pruned %s/gt %s, with_rows %s/gt %s, rows %s/gt %s, "
                     "incl_opt gt %s/%s; filters: %s" % (
                         r["tag"], r["scan_id"], r["table"], r["pruned"], r.get("gt_pruned"),
                         r["scanned_with_rows"], r.get("gt_with_rows"), r["rows_passed"], r.get("gt_rows"),
                         r.get("gt_incl_optional_with_rows"), r.get("gt_incl_optional_rows"), r["filters"][:300]))
    approx = [r for r in rows if r.get("pruned_check") == "approx_varchar" and not r["pruned_match"]]
    lines.append("\nVARCHAR pruning differences (expected: 8-byte string statistics): %d\n" % len(approx))
    for r in approx[:50]:
        lines.append("- %s scan %s (%s): pruned %s, exact-min/max prediction %s; filters: %s" % (
            r["tag"], r["scan_id"], r["table"], r["pruned"], r["gt_pruned"], r["filters"][:200]))
    with open(os.path.join(out_dir, "ground_truth.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:len(summ) + 6]))


if __name__ == "__main__":
    main()
