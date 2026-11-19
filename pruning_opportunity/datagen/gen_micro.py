#!/usr/bin/env python3
"""Generate the microbenchmark datasets (header 'time,data', two unsigned integer columns) out of core.

  unsorted.csv         time uniform in [1767225600000, 1769817600000], data uniform in [1, 1000000]
  sorted.csv           unsorted rows sorted by (time, data)
  outliers.csv         sorted rows; slot s with s % GAP == GAP-1 holds one of the n//GAP largest rows (in order),
                       all other slots hold the first n - n//GAP sorted rows in order (= generate_outliers.py)
  cardinality_<N>.csv  time of sorted.csv in order; data: per partition of 8192 rows (row_index // 8192) a random
                       subset of N/2 distinct ids from [0, N) is chosen, each row's id is drawn uniformly from it

Implementation: unsorted rows are generated in chunks of CHUNK rows from per-chunk numpy generators
(default_rng([seed, 0, chunk])). Each row is packed into a 64-bit key (time - TIME_MIN) << 20 | data, which
sorts exactly like (time, data). While writing unsorted.csv the keys are distributed into NB binary bucket files
by time range; each bucket fits in memory, is sorted with np.sort and appended to sorted.bin (the sorted keys,
8 bytes/row), from which sorted.csv, outliers.csv and the cardinality files are written block-wise.
Cardinality files use one sequential generator default_rng([seed, 1, N]) consumed partition by partition.

Resumable per output file: finished files are skipped, outputs are written to *.tmp and renamed.
sorted.bin is kept (needed by verify_micro.py); remove it with --cleanup after verification.
"""
import argparse
import os
import shutil
import sys
import time

import numpy as np

from microlib import (DATA_MAX, DATA_MIN, HEADER, PARTITION, TIME_MAX, TIME_MIN, format_csv, make_key,
                      split_key)

CHUNK = 10_000_000
NB = 128


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Gen:
    def __init__(self, a):
        self.n = a.rows
        self.seed = a.seed
        self.gap = a.outlier_gap
        self.out = os.path.abspath(a.out_dir)
        self.tmp = os.path.join(os.path.abspath(a.tmp_dir), "micro")
        self.bdir = os.path.join(self.tmp, "buckets")
        self.sorted_bin = os.path.join(self.tmp, "sorted.bin")
        os.makedirs(self.out, exist_ok=True)
        os.makedirs(self.tmp, exist_ok=True)

    def path(self, name):
        return os.path.join(self.out, name)

    def chunks(self):
        for c, s in enumerate(range(0, self.n, CHUNK)):
            yield c, s, min(CHUNK, self.n - s)

    # ---- stage 1: unsorted.csv and time buckets -------------------------------------------------
    def unsorted(self):
        want_csv = not os.path.exists(self.path("unsorted.csv"))
        want_buckets = not os.path.exists(self.sorted_bin) and not os.path.exists(os.path.join(self.bdir, "DONE"))
        if not want_csv and not want_buckets:
            return
        log(f"stage unsorted: csv={want_csv} buckets={want_buckets}")
        t0 = time.time()
        f = open(self.path("unsorted.csv") + ".tmp", "wb", buffering=16 << 20) if want_csv else None
        if f:
            f.write(HEADER)
        bfiles = None
        if want_buckets:
            shutil.rmtree(self.bdir, ignore_errors=True)
            os.makedirs(self.bdir)
            bfiles = [open(os.path.join(self.bdir, f"{b:04d}.bin"), "wb") for b in range(NB)]
        span = np.uint64(TIME_MAX - TIME_MIN + 1)
        for c, s, m in self.chunks():
            rng = np.random.default_rng([self.seed, 0, c])
            t = rng.integers(TIME_MIN, TIME_MAX, size=m, dtype=np.uint64, endpoint=True)
            d = rng.integers(DATA_MIN, DATA_MAX, size=m, dtype=np.uint64, endpoint=True)
            if f:
                f.write(format_csv(t, d, 7))
            if bfiles:
                b = ((t - np.uint64(TIME_MIN)) * np.uint64(NB)) // span
                k = make_key(t, d)
                order = np.argsort(b, kind="stable")
                k = k[order]
                bounds = np.concatenate([[0], np.cumsum(np.bincount(b.astype(np.int64), minlength=NB))])
                for i in range(NB):
                    k[bounds[i]:bounds[i + 1]].tofile(bfiles[i])
            if c % 10 == 0:
                log(f"  unsorted chunk {c} ({time.time() - t0:.0f}s)")
        if f:
            f.close()
            os.rename(self.path("unsorted.csv") + ".tmp", self.path("unsorted.csv"))
        if bfiles:
            for bf in bfiles:
                bf.close()
            open(os.path.join(self.bdir, "DONE"), "w").close()
        log(f"stage unsorted done in {time.time() - t0:.0f}s")

    # ---- stage 2: sorted.bin + sorted.csv -------------------------------------------------------
    def sorted(self):
        want_bin = not os.path.exists(self.sorted_bin)
        want_csv = not os.path.exists(self.path("sorted.csv"))
        if not want_bin and not want_csv:
            return
        log(f"stage sorted: bin={want_bin} csv={want_csv}")
        t0 = time.time()
        if want_bin:
            fb = open(self.sorted_bin + ".tmp", "wb")
            for i in range(NB):
                k = np.fromfile(os.path.join(self.bdir, f"{i:04d}.bin"), dtype=np.uint64)
                k.sort()
                k.tofile(fb)
            fb.close()
            if os.path.getsize(self.sorted_bin + ".tmp") != 8 * self.n:
                raise RuntimeError("sorted.bin has wrong size")
            os.rename(self.sorted_bin + ".tmp", self.sorted_bin)
            shutil.rmtree(self.bdir)
            log(f"  sorted.bin written ({time.time() - t0:.0f}s)")
        if want_csv:
            with open(self.path("sorted.csv") + ".tmp", "wb", buffering=16 << 20) as f:
                f.write(HEADER)
                for c, s, m in self.chunks():
                    t, d = split_key(self.read_keys(s, m))
                    f.write(format_csv(t, d, 7))
            os.rename(self.path("sorted.csv") + ".tmp", self.path("sorted.csv"))
        log(f"stage sorted done in {time.time() - t0:.0f}s")

    def read_keys(self, start, count):
        return np.fromfile(self.sorted_bin, dtype=np.uint64, count=count, offset=8 * start)

    # ---- stage 3: outliers.csv -------------------------------------------------------------------
    def outliers(self):
        if os.path.exists(self.path("outliers.csv")):
            return
        log("stage outliers")
        t0 = time.time()
        n, gap = self.n, self.gap
        if n % gap:
            raise ValueError("rows must be a multiple of the outlier gap")
        k = n // gap
        normal = n - k
        outl = self.read_keys(normal, k)  # the k largest rows
        groups = max(1, CHUNK // gap)     # gap-sized slot groups per block
        with open(self.path("outliers.csv") + ".tmp", "wb", buffering=16 << 20) as f:
            f.write(HEADER)
            for g0 in range(0, k, groups):
                g = min(groups, k - g0)
                body = self.read_keys(g0 * (gap - 1), g * (gap - 1)).reshape(g, gap - 1)
                blk = np.concatenate([body, outl[g0:g0 + g, None]], axis=1).reshape(-1)
                t, d = split_key(blk)
                f.write(format_csv(t, d, 7))
        os.rename(self.path("outliers.csv") + ".tmp", self.path("outliers.csv"))
        log(f"stage outliers done in {time.time() - t0:.0f}s")

    # ---- stage 4: cardinality_<N>.csv ------------------------------------------------------------
    def cardinality(self, card):
        name = f"cardinality_{card}.csv"
        if os.path.exists(self.path(name)):
            return
        log(f"stage {name}")
        t0 = time.time()
        half = card // 2
        digits = len(str(card - 1))
        rng = np.random.default_rng([self.seed, 1, card])
        block = (CHUNK // PARTITION) * PARTITION
        with open(self.path(name) + ".tmp", "wb", buffering=16 << 20) as f:
            f.write(HEADER)
            for s in range(0, self.n, block):
                m = min(block, self.n - s)
                t, _ = split_key(self.read_keys(s, m))
                ids = np.empty(m, dtype=np.uint64)
                for p0 in range(0, m, PARTITION):
                    p1 = min(m, p0 + PARTITION)
                    sel = rng.choice(card, half, replace=False)
                    ids[p0:p1] = sel[rng.integers(0, half, size=p1 - p0)]
                f.write(format_csv(t, ids, digits))
                if (s // block) % 10 == 0:
                    log(f"  {name} row {s} ({time.time() - t0:.0f}s)")
        os.rename(self.path(name) + ".tmp", self.path(name))
        log(f"stage {name} done in {time.time() - t0:.0f}s")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rows", type=int, default=1_000_000_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--outlier-gap", type=int, default=10_000)
    p.add_argument("--cardinalities", default="100,1000,10000,100000")
    p.add_argument("--stages", default="unsorted,sorted,outliers,cardinality")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--tmp-dir", required=True)
    p.add_argument("--cleanup", action="store_true", help="only delete the intermediate sorted.bin / buckets")
    a = p.parse_args()
    g = Gen(a)
    if a.cleanup:
        shutil.rmtree(g.tmp, ignore_errors=True)
        log("intermediates removed")
        return
    st = a.stages.split(",")
    t0 = time.time()
    if "unsorted" in st:
        g.unsorted()
    if "sorted" in st:
        if not os.path.exists(g.sorted_bin):
            g.unsorted()  # regenerates buckets if needed
        g.sorted()
    if "outliers" in st:
        g.outliers()
    if "cardinality" in st:
        for c in [int(x) for x in a.cardinalities.split(",") if x]:
            g.cardinality(c)
    log(f"all requested stages done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
