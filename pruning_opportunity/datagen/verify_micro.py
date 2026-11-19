#!/usr/bin/env python3
"""Verify the microbenchmark CSVs written by gen_micro.py (streaming; needs the intermediate sorted.bin).

Checks (every row, not samples):
  all files     strict format (header, 13-digit time, ',', data, '\\n'), exactly --rows data rows
  unsorted      time in [TIME_MIN, TIME_MAX], data in [1, 1e6]; multiset fingerprint == sorted.bin fingerprint
  sorted        rows equal sorted.bin, (time, data) non-decreasing across the whole file, same fingerprint
  outliers      row i == sorted[n - n/gap + i//gap] if i % gap == gap-1 else sorted[i - i//gap]
  cardinality_N time equals sorted.csv time row by row, data in [0, N), distinct ids per 8192-row
                partition <= N/2 (reports min/max/mean distinct count over all partitions)
Writes one JSON line per file to --report.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

from microlib import DATA_MAX, DATA_MIN, PARTITION, TIME_MAX, TIME_MIN, iter_csv, iter_csv_duckdb, make_key, split_key

PARSER = "duckdb"


def fingerprint(k):
    k = k.astype(np.uint64)
    with np.errstate(over="ignore"):
        return int(np.sum(k, dtype=np.uint64)), int(np.sum(k * (k | np.uint64(1)), dtype=np.uint64))


def add_fp(a, b):
    return ((a[0] + b[0]) & (2 ** 64 - 1), (a[1] + b[1]) & (2 ** 64 - 1))


class SortedBin:
    def __init__(self, path):
        self.path = path
        self.n = os.path.getsize(path) // 8

    def read(self, start, count):
        return np.fromfile(self.path, dtype=np.uint64, count=count, offset=8 * start)


def verify(path, kind, sb, n, gap):
    t0 = time.time()
    res = {"file": os.path.basename(path), "bytes": os.path.getsize(path)}
    rows = 0
    tmin, tmax, dmin, dmax = None, None, None, None
    fp = (0, 0)
    prev_key = None
    ok = True
    errors = []
    card = int(kind.split("_")[1]) if kind.startswith("cardinality") else None
    dist = {"min": None, "max": None, "sum": 0, "cnt": 0}
    pend_part, pend_ids = None, None  # trailing partition that may continue in the next block

    def account(part, ids):
        if len(part) == 0:
            return
        u = np.unique(part.astype(np.uint64) * np.uint64(card) + ids)
        cnt = np.bincount((u // np.uint64(card)).astype(np.int64) - int(part.min()))
        cnt = cnt[cnt > 0]
        dist["min"] = int(cnt.min()) if dist["min"] is None else min(dist["min"], int(cnt.min()))
        dist["max"] = int(cnt.max()) if dist["max"] is None else max(dist["max"], int(cnt.max()))
        dist["sum"] += int(cnt.sum())
        dist["cnt"] += len(cnt)

    def err(msg):
        nonlocal ok
        ok = False
        if len(errors) < 10:
            errors.append(msg)

    for t, d in (iter_csv_duckdb(path) if PARSER == "duckdb" else iter_csv(path)):
        m = len(t)
        s = rows
        rows += m
        if rows > n:
            err("too many rows")
            break
        tmin = int(t.min()) if tmin is None else min(tmin, int(t.min()))
        tmax = int(t.max()) if tmax is None else max(tmax, int(t.max()))
        dmin = int(d.min()) if dmin is None else min(dmin, int(d.min()))
        dmax = int(d.max()) if dmax is None else max(dmax, int(d.max()))
        if kind in ("unsorted", "sorted", "outliers"):
            k = make_key(t, d)
            fp = add_fp(fp, fingerprint(k))
        if kind == "sorted":
            if prev_key is not None and k[0] < prev_key:
                err(f"not sorted at row {s}")
            if np.any(k[1:] < k[:-1]):
                err(f"not sorted inside block starting at row {s}")
            prev_key = k[-1]
            if not np.array_equal(k, sb.read(s, m)):
                err(f"rows differ from sorted.bin in block starting at {s}")
        elif kind == "outliers":
            i = np.arange(s, s + m, dtype=np.int64)
            is_out = (i % gap) == gap - 1
            src = np.where(is_out, (n - n // gap) + i // gap, i - i // gap)
            exp = np.empty(m, dtype=np.uint64)
            nm = ~is_out
            lo, hi = src[nm].min(), src[nm].max()
            exp[nm] = sb.read(lo, hi - lo + 1)[src[nm] - lo]
            if is_out.any():
                lo, hi = src[is_out].min(), src[is_out].max()
                exp[is_out] = sb.read(lo, hi - lo + 1)[src[is_out] - lo]
            if not np.array_equal(k, exp):
                err(f"outlier placement mismatch in block starting at {s}")
        elif card is not None:
            st, _ = split_key(sb.read(s, m))
            if not np.array_equal(t, st):
                err(f"time differs from sorted in block starting at {s}")
            if d.max() >= card:
                err(f"id >= {card} in block starting at {s}")
            part = np.arange(s, s + m, dtype=np.int64) // PARTITION
            if pend_part is not None:
                part = np.concatenate([np.full(len(pend_ids), pend_part, dtype=np.int64), part])
                d = np.concatenate([pend_ids, d])
            last_p = part[-1]
            full = part < last_p
            account(part[full], d[full])
            pend_part, pend_ids = last_p, d[~full].copy()
    if card is not None and pend_part is not None:
        account(np.full(len(pend_ids), pend_part, dtype=np.int64), pend_ids)

    if rows != n:
        err(f"row count {rows} != {n}")
    if tmin is None or tmin < TIME_MIN or tmax > TIME_MAX:
        err(f"time range [{tmin}, {tmax}] outside [{TIME_MIN}, {TIME_MAX}]")
    if card is None:
        if dmin < DATA_MIN or dmax > DATA_MAX:
            err(f"data range [{dmin}, {dmax}] outside [{DATA_MIN}, {DATA_MAX}]")
        exp_fp = None
        res["fingerprint"] = list(fp)
    else:
        if dist["max"] is None or dist["max"] > card // 2:
            err(f"partition distinct count {dist['max']} > {card // 2}")
        exp_partitions = (n + PARTITION - 1) // PARTITION
        if dist["cnt"] != exp_partitions:
            err(f"checked {dist['cnt']} partitions, expected {exp_partitions}")
        res.update(partitions=dist["cnt"], distinct_min=dist["min"], distinct_max=dist["max"],
                   distinct_mean=round(dist["sum"] / max(dist["cnt"], 1), 1))
    res.update(kind=kind, rows=rows, time_min=tmin, time_max=tmax, data_min=dmin, data_max=dmax, ok=ok,
               errors=errors, seconds=round(time.time() - t0))
    return res


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rows", type=int, default=1_000_000_000)
    p.add_argument("--outlier-gap", type=int, default=10_000)
    p.add_argument("--dir", required=True)
    p.add_argument("--sorted-bin", required=True)
    p.add_argument("--files", default="unsorted,sorted,outliers,cardinality_100,cardinality_1000,"
                                      "cardinality_10000,cardinality_100000")
    p.add_argument("--report", required=True)
    p.add_argument("--parser", choices=["duckdb", "numpy"], default="duckdb",
                   help="duckdb: multi-threaded read_csv with fixed UBIGINT schema (strict); numpy: strict byte-level "
                        "format check, slower")
    a = p.parse_args()
    global PARSER
    PARSER = a.parser
    sb = SortedBin(a.sorted_bin)
    if sb.n != a.rows:
        print(f"sorted.bin has {sb.n} rows, expected {a.rows}")
        return 1
    # fingerprint of sorted.bin (the reference multiset)
    ref = (0, 0)
    for s in range(0, sb.n, 50_000_000):
        ref = add_fp(ref, fingerprint(sb.read(s, min(50_000_000, sb.n - s))))
    allok = True
    for kind in a.files.split(","):
        path = os.path.join(a.dir, f"{kind}.csv")
        if not os.path.exists(path):
            r = {"file": os.path.basename(path), "ok": False, "errors": ["missing"]}
        else:
            r = verify(path, kind, sb, a.rows, a.outlier_gap)
            if "fingerprint" in r:
                r["fingerprint_matches_sorted_bin"] = tuple(r["fingerprint"]) == ref
                if not r["fingerprint_matches_sorted_bin"]:
                    r["ok"] = False
        allok &= r["ok"]
        print(json.dumps(r), flush=True)
        with open(a.report, "a") as f:
            f.write(json.dumps(r) + "\n")
    print("ALL OK" if allok else "FAILURES", flush=True)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
