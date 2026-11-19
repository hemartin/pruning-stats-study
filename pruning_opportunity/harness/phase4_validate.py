#!/usr/bin/env python3
"""Per-scan validation of a selective counting pass against the baseline counting pass (both phase4.py, mode count)
and attribution of the row groups pruned by the selective statistics.

For every query present in both passes:
  * result: row count + order-independent hash equal;
  * per scan (matched by scan_id): invariants (total = pruned + no_rows + with_rows + partial + not_reached,
    pruned = pruned_minmax + pruned_additional, pruned_additional = sum of per-leaf pruned_first_additional +
    pruned_additional_no_single_leaf), equal total_row_groups / pruned_minmax / incl_optional_with_rows
    (a row group with a row satisfying ALL pushed-down filters incl. optional join filters must never be pruned),
    scanned_with_rows equal (it may legitimately drop when an optional/join filter prunes a row group whose rows pass
    only the non-optional filters; such cases are listed separately), rows_passed_incl_optional equal;
  * attribution: pruned row groups per table.column and filter category (static equality / range / IN / OR,
    join range, join IN, top-N, combination of leaves), relative to the baseline's "scanned, no rows" and
    "incl. optional, no rows" row groups of the same scan.

  phase4_validate.py --scale small --config occ200 [--baseline baseline] [--groups tpch,tpcds,clickbench]
                     [--out-dir D]
Writes results/<scale>/phase4/validate_<config>.md (or into --out-dir D), validate_<config>_scans.csv (every scan with
a difference or
additional pruning), validate_<config>_attribution.csv (per query, table.column, category).
"""
import argparse
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aggregate  # noqa: E402
import common  # noqa: E402
import phase4  # noqa: E402
import phase4_aggregate  # noqa: E402

EQUAL_FIELDS = ["total_row_groups", "pruned_minmax", "incl_optional_with_rows", "rows_passed_incl_optional"]


def category(leaf):
    kind, origin = leaf["kind"], leaf["origin"]
    base = kind[len("optional("):-1] if kind.startswith("optional(") else kind
    if origin == "topn" or "topn" in kind:
        return "top-N"
    if base == "cmp=":
        what = "equality"
    elif base.startswith("cmp"):
        what = "range"
    elif base == "in":
        what = "IN"
    elif base == "or":
        what = "OR"
    elif base == "and":
        what = "range"
    else:
        what = base
    return "%s %s" % ("join" if origin == "join" else "static", what)


def scan_key(scan):
    """counter-independent identity of a scan (scan ids follow initialisation order, which can differ between runs
    for independent pipelines, e.g. UNION branches)"""
    return (scan["table"], scan["total_row_groups"], tuple(f.get("sql") or f.get("filter") or "" for f in
                                                          scan["filters"]), scan.get("rows_passed_incl_optional"))


def align(a_list, b_list):
    """pairs of scans: by position if the tables and filters match position by position, otherwise by sorted
    identity. Returns (pairs, realigned)"""
    if all(scan_key(a)[:3] == scan_key(b)[:3] for a, b in zip(a_list, b_list)):
        return list(zip(a_list, b_list)), False
    return list(zip(sorted(a_list, key=scan_key), sorted(b_list, key=scan_key))), True


def load_scans(gdir):
    by_tag = {}
    for adir in phase4_aggregate.attempts(gdir):
        by_tag.update(aggregate.load_run(adir))
    return by_tag


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--baseline", default="baseline")
    ap.add_argument("--groups", default="all")
    ap.add_argument("--out-dir", default=None, help="output directory (default results/<scale>/phase4)")
    args = ap.parse_args()
    root = common.raw_dir(args.scale, "phase4")
    out_dir = args.out_dir or os.path.join(common.results_dir(args.scale), "phase4")
    os.makedirs(out_dir, exist_ok=True)
    scan_rows, attr_rows = [], []
    per_setup = collections.OrderedDict()
    per_cat = collections.defaultdict(collections.Counter)    # setup -> category -> pruned
    per_col = collections.defaultdict(collections.Counter)    # setup -> table.column -> pruned
    for group in phase4.select_groups(args.groups):
        bdir = os.path.join(root, args.baseline, "count", group)
        sdir = os.path.join(root, args.config, "count", group)
        if not (os.path.isdir(bdir) and os.path.isdir(sdir)):
            continue
        b_scans, s_scans = load_scans(bdir), load_scans(sdir)
        b_status, s_status = phase4_aggregate.load_status(bdir), phase4_aggregate.load_status(sdir)
        for tag in sorted(s_scans):
            if tag not in b_scans or "/ingest/" in tag:
                continue
            setup, qid = tag.split("/", 1)
            t = per_setup.setdefault(setup, collections.Counter())
            t["queries"] += 1
            bs, ss = b_status.get(tag), s_status.get(tag)
            res_eq = bool(phase4.results_equal(bs, ss))
            t["result_equal"] += res_eq
            if not res_eq:
                scan_rows.append([setup, qid, "", "", "RESULT DIFFERENT", "", "", "", "", "", ""])
            (_, b_list), (_, s_list) = b_scans[tag], s_scans[tag]
            if len(b_list) != len(s_list):
                t["scan_count_diff"] += 1
                scan_rows.append([setup, qid, "", "", "n_scans %d vs %d" % (len(b_list), len(s_list)),
                                  "", "", "", "", "", ""])
            q_pruned = 0
            pairs, realigned = align(b_list, s_list)
            t["queries_realigned"] += realigned
            for b, s in pairs:
                t["scans"] += 1
                notes = []
                if b["table"] != s["table"]:
                    notes.append("table %s vs %s" % (b["table"], s["table"]))
                parts = s["pruned"] + s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"] + \
                    s["not_reached"]
                leaf_sum = sum(f.get("pruned_first_additional", 0) for f in s["filters"]) + \
                    s.get("pruned_additional_no_single_leaf", 0)
                col_sum = sum(c["pruned_first"] for c in s.get("additional_columns", [])) + \
                    s.get("additional_columns_unattributed", 0)
                if parts != s["total_row_groups"] or s["pruned"] != s["pruned_minmax"] + s["pruned_additional"]:
                    notes.append("INVARIANT")
                    t["invariant_violations"] += 1
                if leaf_sum != s["pruned_additional"] or col_sum != s["pruned_additional"]:
                    notes.append("attribution sum leaves %d columns %d vs %d" % (leaf_sum, col_sum,
                                                                                s["pruned_additional"]))
                    t["attribution_mismatch"] += 1
                for f in EQUAL_FIELDS:
                    if b.get(f) != s.get(f):
                        notes.append("%s %s vs %s" % (f, b.get(f), s.get(f)))
                        t["diff_" + f] += 1
                if b["scanned_with_rows"] != s["scanned_with_rows"]:
                    t["diff_scanned_with_rows"] += 1
                    notes.append("scanned_with_rows %d vs %d" % (b["scanned_with_rows"], s["scanned_with_rows"]))
                pa = s["pruned_additional"]
                q_pruned += pa
                t["pruned_additional"] += pa
                t["base_no_rows"] += b["scanned_no_rows"]
                t["base_incl_opt_no_rows"] += b["incl_optional_no_rows"]
                t["sel_no_rows"] += s["scanned_no_rows"]
                t["sel_incl_opt_no_rows"] += s["incl_optional_no_rows"]
                t["base_with_rows"] += b["scanned_with_rows"]
                t["sel_with_rows"] += s["scanned_with_rows"]
                # pruned row groups that were "scanned, no rows" in the baseline vs. pruned via optional filters
                # from the baseline's "with rows (non-optional filters)" class
                t["pruned_from_no_rows"] += b["scanned_no_rows"] - s["scanned_no_rows"]
                t["pruned_from_with_rows"] += b["scanned_with_rows"] - s["scanned_with_rows"]
                if pa:
                    t["scans_with_additional"] += 1
                    cats = collections.Counter()
                    for f in s["filters"]:
                        n = f.get("pruned_first_additional", 0)
                        if n:
                            cats[(f["col"], category(f))] += n
                    if s.get("pruned_additional_no_single_leaf", 0):
                        # a range etc. formed by several leaves: attribute to the columns that pruned first, the
                        # category being the set of leaf categories on those columns
                        cols = [c["col"] for c in s.get("additional_columns", []) if c["pruned_first"]]
                        kinds = sorted({category(f) for f in s["filters"] if f["col"] in cols})
                        cats[("+".join(cols) or "?", "combination: " + " + ".join(kinds))] += \
                            s["pruned_additional_no_single_leaf"]
                    for (col, cat), n in cats.items():
                        per_cat[setup][cat] += n
                        attr_rows.append([setup, qid, b["scan_id"], s["table"], col, cat, n, b["scanned_no_rows"],
                                          b["incl_optional_no_rows"], b["total_row_groups"]])
                    for c in s.get("additional_columns", []):
                        per_col[setup]["%s.%s" % (s["table"], c["col"])] += c["pruned_first"]
                if notes or pa:
                    scan_rows.append([setup, qid, b["scan_id"], s["table"], "; ".join(notes), pa,
                                      b["scanned_no_rows"], b["incl_optional_no_rows"], b["scanned_with_rows"],
                                      s["scanned_with_rows"], b["total_row_groups"]])
            t["queries_with_additional"] += 1 if q_pruned else 0
    with open(os.path.join(out_dir, "validate_%s_scans.csv" % args.config), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["setup", "qid", "scan_id", "table", "notes", "pruned_additional", "base_scanned_no_rows",
                    "base_incl_optional_no_rows", "base_scanned_with_rows", "sel_scanned_with_rows",
                    "total_row_groups"])
        w.writerows(scan_rows)
    with open(os.path.join(out_dir, "validate_%s_attribution.csv" % args.config), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["setup", "qid", "scan_id", "table", "column", "category", "pruned_additional",
                    "base_scanned_no_rows", "base_incl_optional_no_rows", "total_row_groups"])
        w.writerows(attr_rows)
    md = ["# Validation: `%s` vs. `%s` (counting passes, per scan)" % (args.config, args.baseline), "",
          "| setup | queries | result equal | scans | invariant viol. | attribution mismatch | diff total/minmax/"
          "incl-opt-with-rows/rows-passed-incl-opt | diff scanned_with_rows | base no-rows | base incl-opt no-rows "
          "| pruned additional | of which from base no-rows | from base with-rows (optional filters) "
          "| % of base no-rows | % of base incl-opt no-rows | queries with additional pruning |",
          "|" + "---|" * 16]
    for setup, t in per_setup.items():
        diffs = "/".join(str(t["diff_" + f]) for f in EQUAL_FIELDS)
        pct = lambda a, b: "%.2f" % (100.0 * a / b) if b else ""  # noqa: E731
        md.append("| %s | %d | %d | %d | %d | %d | %s | %d | %d | %d | %d | %d | %d | %s | %s | %d |" % (
            setup, t["queries"], t["result_equal"], t["scans"], t["invariant_violations"], t["attribution_mismatch"],
            diffs, t["diff_scanned_with_rows"], t["base_no_rows"], t["base_incl_opt_no_rows"],
            t["pruned_additional"], t["pruned_from_no_rows"], t["pruned_from_with_rows"],
            pct(t["pruned_from_no_rows"], t["base_no_rows"]), pct(t["pruned_additional"], t["base_incl_opt_no_rows"]),
            t["queries_with_additional"]))
    md.append("")
    md.append("Queries whose scans had to be matched by (table, row groups, filters, rows passed) instead of scan id: "
              + ", ".join("%s %d" % (k, t["queries_realigned"]) for k, t in per_setup.items()))
    md.append("")
    md.append("## Pruned row groups by filter category (first leaf whose statistic proves no match)")
    md.append("")
    for setup, c in per_cat.items():
        md.append("* %s: %s" % (setup, ", ".join("%s %d" % kv for kv in c.most_common())))
    md.append("")
    md.append("## Pruned row groups by column (first column whose complete filter is proven unsatisfiable)")
    md.append("")
    for setup, c in per_col.items():
        md.append("* %s: %s" % (setup, ", ".join("%s %d" % kv for kv in c.most_common())))
    md.append("")
    with open(os.path.join(out_dir, "validate_%s.md" % args.config), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
