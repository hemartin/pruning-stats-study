#!/usr/bin/env python3
"""Compare the pruning counters of two counting runs (e.g. threads=1 vs threads=12) per query and table scan.

Scans are matched per query by (table, filter set) as a multiset, because scan order can differ. Scans with top-N
filters are reported separately (their pruning depends on the order in which row groups are processed).
Usage: compare_threads.py --scale small --a count --b count_mt12
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from aggregate import load_run, filter_set  # noqa: E402

KEYS = ["total_row_groups", "pruned", "scanned_no_rows", "scanned_with_rows", "partial_no_rows", "not_reached",
        "rows_passed", "incl_optional_with_rows", "rows_passed_incl_optional"]


def sig(scans):
    out = collections.Counter()
    for s in scans:
        stripped = [f["filter"] for f in s["filters"] if f["origin"] != "topn"]
        out[(s["table"], " AND ".join(stripped), tuple(s[k] for k in KEYS))] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", required=True)
    ap.add_argument("--a", default="count")
    ap.add_argument("--b", default="count_mt12")
    args = ap.parse_args()
    tot = collections.Counter()
    for setup in common.all_setups():
        rb = load_run(os.path.join(common.raw_dir(args.scale, args.b), setup.name))
        if not rb:
            continue
        ra = load_run(os.path.join(common.raw_dir(args.scale, args.a), setup.name))
        for tag, (qb, sb) in rb.items():
            if tag not in ra:
                continue
            sa = ra[tag][1]
            topn = any(f["origin"] == "topn" for s in sa + sb for f in s["filters"])
            key = "topn" if topn else "plain"
            tot[key + "_queries"] += 1
            if sig(sa) != sig(sb):
                tot[key + "_differ"] += 1
                if not topn:
                    print("DIFF", tag, sig(sa) - sig(sb), sig(sb) - sig(sa))
    print(dict(tot))


if __name__ == "__main__":
    main()
