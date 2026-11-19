"""Shared constants and fast vectorised CSV formatting / parsing for the microbenchmark datasets."""
import numpy as np

TIME_MIN = 1767225600000
TIME_MAX = 1769817600000
TIME_DIGITS = 13          # every time value in [TIME_MIN, TIME_MAX] has exactly 13 digits
DATA_MIN, DATA_MAX = 1, 1_000_000
DATA_BITS = 20            # key = (time - TIME_MIN) << 20 | data   (data <= 1e6 < 2^20, time offset < 2^32)
HEADER = b"time,data\n"
PARTITION = 8192


def make_key(t, d):
    return ((t - np.uint64(TIME_MIN)) << np.uint64(DATA_BITS)) | d


def split_key(k):
    return (k >> np.uint64(DATA_BITS)) + np.uint64(TIME_MIN), k & np.uint64((1 << DATA_BITS) - 1)


_POW10 = np.array([10 ** i for i in range(20)], dtype=np.uint64)


def format_csv(t, d, d_digits):
    """Rows 'time,data\\n' as bytes. t: uint64 13-digit values, d: uint64 values with <= d_digits digits."""
    n = len(t)
    w = TIME_DIGITS + 1 + d_digits + 1
    buf = np.empty((n, w), dtype=np.uint8)
    x = t.astype(np.uint64, copy=True)
    for i in range(TIME_DIGITS - 1, -1, -1):
        buf[:, i] = (x % 10).astype(np.uint8) + 48
        x //= 10
    if np.any(x):
        raise ValueError("time value with more than 13 digits")
    buf[:, TIME_DIGITS] = 44  # ','
    x = d.astype(np.uint64, copy=True)
    nd = np.ones(n, dtype=np.int8)
    for k in range(1, d_digits):
        nd += (x >= _POW10[k])
    for i in range(d_digits - 1, -1, -1):
        buf[:, TIME_DIGITS + 1 + i] = (x % 10).astype(np.uint8) + 48
        x //= 10
    if np.any(x):
        raise ValueError("data value with too many digits")
    del x
    buf[:, w - 1] = 10  # '\n'
    mask = np.ones((n, w), dtype=bool)
    mask[:, TIME_DIGITS + 1:TIME_DIGITS + 1 + d_digits] = (
        np.arange(d_digits, dtype=np.int8)[None, :] >= (d_digits - nd)[:, None])
    return buf[mask].tobytes()


def iter_csv(path, block_bytes=256 << 20):
    """Yield (time, data) uint64 arrays parsed from a 'time,data' CSV, block by block, checking the format
    strictly (header, 13-digit time, comma, 1..7 digit data without leading zeros except '0', newline)."""
    with open(path, "rb") as f:
        head = f.readline()
        if head != HEADER:
            raise ValueError(f"bad header {head!r}")
        rest = b""
        while True:
            blk = f.read(block_bytes)
            if not blk:
                if rest:
                    raise ValueError("file does not end with newline")
                return
            blk = rest + blk
            cut = blk.rfind(b"\n") + 1
            rest = blk[cut:]
            a = np.frombuffer(blk, dtype=np.uint8, count=cut)
            nl = np.flatnonzero(a == 10)
            starts = np.empty(len(nl), dtype=np.int64)
            starts[0] = 0
            starts[1:] = nl[:-1] + 1
            if np.any(a[starts + TIME_DIGITS] != 44):
                raise ValueError("comma not at position 13")
            t = np.zeros(len(nl), dtype=np.uint64)
            for i in range(TIME_DIGITS):
                c = a[starts + i]
                if np.any((c < 48) | (c > 57)):
                    raise ValueError("non-digit in time")
                t = t * np.uint64(10) + (c - 48).astype(np.uint64)
            dlen = nl - starts - TIME_DIGITS - 1
            if np.any(dlen < 1) or np.any(dlen > 7):
                raise ValueError("bad data width")
            d = np.zeros(len(nl), dtype=np.uint64)
            first = a[starts + TIME_DIGITS + 1]
            if np.any((first == 48) & (dlen > 1)):
                raise ValueError("leading zero in data")
            for i in range(7):
                has = dlen > i
                if not has.any():
                    break
                pos = np.where(has, starts + TIME_DIGITS + 1 + i, 0)
                c = a[pos]
                if np.any(has & ((c < 48) | (c > 57))):
                    raise ValueError("non-digit in data")
                d = np.where(has, d * np.uint64(10) + (c.astype(np.int64) - 48).clip(0).astype(np.uint64), d)
            yield t, d


def iter_csv_duckdb(path, batch_rows=8_388_608, threads=4, mem="2GB"):
    """Same interface as iter_csv, but parsed by DuckDB (multi-threaded, row order preserved) via Arrow."""
    import duckdb
    con = duckdb.connect()
    con.execute(f"SET threads={threads}")
    con.execute(f"SET memory_limit='{mem}'")
    con.execute("SET preserve_insertion_order=true")
    con.execute("SET enable_progress_bar=false")
    with open(path, "rb") as f:
        if f.readline() != HEADER:
            raise ValueError("bad header")
    rel = con.sql(
        f"SELECT time, data FROM read_csv('{path}', header=true, delim=',', quote='', escape='', "
        f"columns={{'time': 'UBIGINT', 'data': 'UBIGINT'}}, strict_mode=true, null_padding=false, "
        f"auto_detect=false)")
    reader = rel.to_arrow_reader(batch_rows)
    for b in reader:
        t = b.column(0)
        d = b.column(1)
        if t.null_count or d.null_count:
            raise ValueError("NULL value in microbenchmark file")
        yield t.to_numpy(zero_copy_only=False), d.to_numpy(zero_copy_only=False)
