#!/usr/bin/env python3
"""Self-test of the selective statistics: correctness on all supported types and predicate shapes.

Builds (inside one CLI process per configuration) a table of 48 full row groups whose columns have wide min/max in
every row group (two extreme rows per row group) but only ~64 distinct, row-group-specific values otherwise, with
NULLs, so that min/max never prunes while occupancy / nullspace statistics often can. Then runs a few thousand random
queries of every supported shape (=, IS NOT DISTINCT FROM, ranges with every combination of inclusive/exclusive
bounds, BETWEEN, IN lists, OR of equalities, joins -> dynamic join filters, top-N, NOT EQUAL, IS NULL) on every
column type, then UPDATEs / DELETEs rows and repeats a subset. The results of each configuration must equal the
baseline (no statistics) exactly; the timing log tells how many row groups the statistics pruned.

Suite "ngram" (n-gram statistics for LIKE/contains): a table of 48 full row groups of random strings built from
row-group-specific token vocabularies (incl. multibyte UTF-8, the LIKE wildcards '%' and '_', the escape characters
backslash and '!', empty and 1-2 byte strings, NULLs, row groups that are all NULL / all short), with global extremes
in every row group so that min/max cannot prune; random contains / prefix / suffix / starts_with / ends_with / LIKE
(general patterns, ESCAPE) / NOT LIKE / ILIKE / GLOB / regexp / equality / IN / AND / OR predicates; then
UPDATE/DELETE/INSERT and a repeat. Literals include empty strings, 1-2 character patterns (no trigram), case
variants (upper/lower/swapped/capitalised) and constant patterns ('', '%', '_', NULL). Configurations (--ngram-configs): n = 3 at 20 and 200 words, n = 2, 4, and 5
(n > 3: sorted key buffer with compaction instead of a bitmap).

  phase4_selftest.py [--binary B] [--queries N] [--threads T] [--suite types,ngram]
"""
import argparse
import collections
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phase4  # noqa: E402

RG = 8192
N_RG = 48
# column name -> (SQL type, expression of the base value v (BIGINT) / row number i, literal function)
COLUMNS = {
    "c_tinyint": "TINYINT",
    "c_smallint": "SMALLINT",
    "c_int": "INTEGER",
    "c_bigint": "BIGINT",
    "c_utinyint": "UTINYINT",
    "c_usmallint": "USMALLINT",
    "c_uint": "UINTEGER",
    "c_ubigint": "UBIGINT",
    "c_hugeint": "HUGEINT",
    "c_uhugeint": "UHUGEINT",
    "c_dec4": "DECIMAL(4,1)",
    "c_dec18": "DECIMAL(18,3)",
    "c_dec38": "DECIMAL(38,2)",
    "c_date": "DATE",
    "c_ts": "TIMESTAMP",
    "c_time": "TIME",
    "c_double": "DOUBLE",
    "c_float": "FLOAT",
    "c_varchar": "VARCHAR",
    "c_varchar_long": "VARCHAR",
    "c_bool": "BOOLEAN",
}


# column name -> SQL expression of the base value X (BIGINT); the same template generates the table (X = v) and the
# query literals (X = a number), so table values and constants are computed identically by DuckDB
TEMPLATES = {
    "c_tinyint": "((X %% 251 + 251) %% 251 - 125)::TINYINT",
    "c_smallint": "((X %% 65000 + 65000) %% 65000 - 32500)::SMALLINT",
    "c_int": "(X)::INTEGER",
    "c_bigint": "((X)::BIGINT * 1000003)::BIGINT",
    "c_utinyint": "((X %% 251 + 251) %% 251)::UTINYINT",
    "c_usmallint": "((X %% 65000 + 65000) %% 65000)::USMALLINT",
    "c_uint": "((X) + 1000000)::UINTEGER",
    "c_ubigint": "(((X)::BIGINT + 1000000) * 1000000007)::UBIGINT",
    "c_hugeint": "((X)::HUGEINT * 100000000000000000000)",
    "c_uhugeint": "(((X) + 1000000)::UHUGEINT * 100000000000000000000::UHUGEINT)",
    "c_dec4": "((((X) %% 9000 + 9000) %% 9000) / 10)::DECIMAL(4,1)",
    "c_dec18": "((X) / 1000)::DECIMAL(18,3)",
    "c_dec38": "((X)::HUGEINT * 1000000000000000000000)::DECIMAL(38,2)",
    "c_date": "(DATE '2000-01-01' + ((X) // 10)::INTEGER)",
    "c_ts": "(TIMESTAMP '2000-01-01' + to_seconds(X))",
    "c_time": "(TIME '00:00:00' + to_seconds(((X) %% 86000 + 86000) %% 86000))",
    "c_double": "((X) / 8.0)::DOUBLE",
    "c_float": "((X) / 4.0)::FLOAT",
    "c_varchar": "('k' || (X)::VARCHAR)",
    "c_varchar_long": "('same_prefix_' || (X)::VARCHAR)",
    "c_bool": "(((X) %% 2 + 2) %% 2 = 0)",
}


def value_sql(col, v):
    """SQL expression of the column's value for base value v (int) or for the SQL expression v (str)"""
    x = v if isinstance(v, str) else "(%d)" % v
    return (TEMPLATES[col] % ()).replace("X", x)


def base_values(rg):
    """the ~64 distinct base values of row group rg (deterministic)"""
    return [rg * 1000 + k * 7 for k in range(64)]


def create_sql():
    # v: row-group specific values; rows 0 and 1 of every row group carry the global extremes; every 13th row NULL
    exprs = []
    for col in COLUMNS:
        e = value_sql(col, "v")
        exprs.append("CASE WHEN i %% 13 = 5 THEN NULL ELSE %s END AS %s" % (e, col))
    return ("CREATE TABLE base AS SELECT i, CASE WHEN i %% %d = 0 THEN -1000000 WHEN i %% %d = 1 THEN 1000000 "
            "ELSE (i // %d) * 1000 + (hash(i) %% 64)::BIGINT * 7 END AS v FROM range(%d) t(i);\n"
            "CREATE TABLE t AS SELECT i, v, %s FROM base ORDER BY i;\n"
            "CREATE TABLE probe AS SELECT * FROM t WHERE i %% 50000 = 7;\n" % (RG, RG, RG, RG * N_RG,
                                                                              ", ".join(exprs)))


def gen_queries(rng, n):
    cols = list(COLUMNS)
    qs = []
    for _ in range(n):
        col = rng.choice(cols)
        rg = rng.randrange(N_RG)
        vals = base_values(rg)
        present = rng.choice(vals)
        absent = present + rng.choice([1, 2, 3, 4, 5, 6])  # in a gap (values step by 7)
        a, b = sorted([rng.choice(vals), rng.choice(vals)])
        shape = rng.randrange(16)
        lit = lambda x: value_sql(col, x)  # noqa: E731
        if shape == 0:
            w = "%s = %s" % (col, lit(present))
        elif shape == 1:
            w = "%s = %s" % (col, lit(absent))
        elif shape == 2:
            w = "%s IS NOT DISTINCT FROM %s" % (col, lit(rng.choice([present, absent])))
        elif shape == 3:
            w = "%s >= %s AND %s <= %s" % (col, lit(a), col, lit(b))
        elif shape == 4:
            # exclusive bounds exactly on present values with nothing (or something) in between
            w = "%s > %s AND %s < %s" % (col, lit(present), col, lit(present + 7 * rng.choice([1, 2])))
        elif shape == 5:
            w = "%s > %s AND %s <= %s" % (col, lit(present - 7), col, lit(present))
        elif shape == 6:
            w = "%s >= %s AND %s < %s" % (col, lit(present), col, lit(present + 1))
        elif shape == 7:
            w = "%s BETWEEN %s AND %s" % (col, lit(absent), lit(absent + rng.choice([0, 1, 5])))
        elif shape == 8:
            w = "%s IN (%s)" % (col, ", ".join(lit(x) for x in rng.sample(vals, 3) + [absent, absent + 1]))
        elif shape == 9:
            w = "%s IN (%s)" % (col, ", ".join(lit(absent + k * 7) for k in range(rng.choice([2, 5, 20]))))
        elif shape == 10:
            w = "(%s = %s OR %s = %s)" % (col, lit(absent), col, lit(rng.choice([present, absent + 7])))
        elif shape == 11:
            w = "(%s = %s OR (%s >= %s AND %s <= %s))" % (col, lit(absent), col, lit(a), col, lit(b))
        elif shape == 12:
            w = "%s <> %s AND %s >= %s AND %s <= %s" % (col, lit(present), col, lit(present), col, lit(present))
        elif shape == 13:
            w = "%s IS NULL AND i >= %d AND i < %d" % (col, rg * RG, rg * RG + 100)
        elif shape == 14:
            # join: dynamic min/max (and possibly IN-list) join filters pushed into the scan of t
            qs.append("SELECT t.i, t.%s FROM t JOIN (SELECT %s AS x UNION ALL SELECT %s) p ON t.%s = p.x "
                      "ORDER BY ALL" % (col, lit(present), lit(absent), col))
            continue
        else:
            # top-N: dynamic filter that tightens during the scan
            qs.append("SELECT i, %s FROM t WHERE %s >= %s ORDER BY %s DESC NULLS LAST, i LIMIT 7" % (
                col, col, lit(a), col))
            continue
        qs.append("SELECT count(*), min(i), max(i), sum(i) FROM t WHERE %s" % w)
    return qs


# ------------------------------------------------------------------------------------------------------------------
# n-gram suite
# ------------------------------------------------------------------------------------------------------------------
NG_COLUMNS = ["s_mix", "s_short", "s_long", "s_tiny"]
NG_SPECIAL = ["%", "_", "\\", "!", "%_", "a%b", "x_y", "!%", "\\_", "'q"]
NG_UNICODE = ["ä", "ß", "日本", "\U0001F600", "été", "фото",
              "naïve"]


def ng_tokens(rng):
    """global pool of tokens: ascii words, unicode, LIKE special characters"""
    pool = set()
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456789"
    while len(pool) < 300:
        pool.add("".join(rng.choice(letters) for _ in range(rng.randint(2, 7))))
    return sorted(pool) + NG_SPECIAL + NG_UNICODE


def ng_rows(seed):
    """rows (i, s_mix, s_short, s_long, s_tiny) of N_RG full row groups, the per-row-group vocabularies and the token
    pool. s_tiny: only values of <= 2 bytes (max U+00FF, 2 bytes) and NULLs: no trigram at all (empty n-gram set)"""
    rng = random.Random(seed)
    pool = ng_tokens(rng)
    seps = ["", "/", ".", "-", "%", "_", "!", "\\", " "]
    rows, vocab = [], []
    for rg in range(N_RG):
        words = rng.sample(pool, 25)
        vocab.append(words)
        all_null = rg % 11 == 5    # s_mix and s_short all NULL (except the 2 extreme rows)
        all_short = rg % 11 == 7   # s_short only strings of <= 2 characters
        for k in range(RG):
            i = rg * RG + k
            if k == 0:
                mix, short, long_, tiny = "", "", "", ""  # global minimum
            elif k == 1:
                mix = short = long_ = "\U0010FFFF\U0010FFFF"  # global maximum
                tiny = "\u00ff"
            else:
                tiny = None if (all_null or k % 5 == 1) else rng.choice(["a", "b", "ab", "zz", "\u00e4", "%", "_", ""])
                if k % 13 == 5 or all_null:
                    mix = None
                elif k % 17 == 3:
                    mix = rng.choice(["", "a", "ab", "ä", "%", "_"])
                else:
                    mix = "".join(rng.choice(words) + rng.choice(seps) for _ in range(rng.randint(1, 4)))
                if all_null or k % 7 == 2:
                    short = None
                elif all_short or k % 3:
                    short = rng.choice(words)[:2]
                else:
                    short = rng.choice(words)
                long_ = "".join(rng.choice(words) for _ in range(12)) + str(i % 97)
            rows.append((i, mix, short, long_, tiny))
    return rows, vocab, pool


def ng_literal(rng, vocab, pool):
    """a literal that occurs in some row groups, in none, or a random fragment"""
    r = rng.random()
    words = rng.choice(vocab)
    if r < 0.35:
        w = rng.choice(words)
    elif r < 0.55:
        w = rng.choice(words) + rng.choice(words)
    elif r < 0.75:
        w = rng.choice(pool)
    elif r < 0.85:
        w = rng.choice(pool) + rng.choice(pool)
    else:
        w = "".join(rng.choice("abcxyz%_!\\ä") for _ in range(rng.randint(1, 6)))
    if len(w) > 2 and rng.random() < 0.4:
        a = rng.randrange(len(w) - 1)
        w = w[a:a + rng.randint(2, len(w) - a)]
    r = rng.random()
    if r < 0.05:
        w = ""  # empty pattern
    elif r < 0.12:
        w = w[:rng.randint(1, 2)]  # 1-2 characters: no trigram
    elif r < 0.22:
        w = rng.choice([w.upper(), w.lower(), w.swapcase(), w[:1].upper() + w[1:]])  # case variants
    return w


def sql_str(s):
    return "'" + s.replace("'", "''") + "'"


def like_escape_lit(s, esc):
    """LIKE pattern part matching the literal s exactly, with escape character esc"""
    return "".join(esc + c if c in ("%", "_", esc) else c for c in s)


def regex_escape(s):
    return "".join("\\" + c if c in ".^$*+?()[]{}|\\" else c for c in s)


def ng_gen_queries(rng, n, vocab, pool):
    qs = []
    for _ in range(n):
        col = rng.choice(NG_COLUMNS)
        a = ng_literal(rng, vocab, pool)
        b = ng_literal(rng, vocab, pool)
        shape = rng.randrange(23)
        if shape == 0:
            w = "contains(%s, %s)" % (col, sql_str(a))
        elif shape == 1:
            w = "%s LIKE %s" % (col, sql_str("%" + a + "%"))  # raw: '%' / '_' inside a stay wildcards
        elif shape == 2:
            w = "%s LIKE %s ESCAPE '!'" % (col, sql_str("%" + like_escape_lit(a, "!") + "%"))
        elif shape == 3:
            w = "%s LIKE %s ESCAPE '\\'" % (col, sql_str("%" + like_escape_lit(a, "\\") + "%" +
                                                       like_escape_lit(b, "\\") + "%"))
        elif shape == 4:
            w = "%s LIKE %s" % (col, sql_str("%" + a + rng.choice(["_", "%", "__"]) + b + "%"))
        elif shape == 5:
            w = "%s LIKE %s" % (col, sql_str(rng.choice(["_", "%_", "_%"]) + a + rng.choice(["", "%", "_"])))
        elif shape == 6:
            w = "%s LIKE %s" % (col, sql_str(a + "%"))  # prefix: range pushdown
        elif shape == 7:
            w = "%s LIKE %s" % (col, sql_str("%" + a))  # suffix
        elif shape == 8:
            f = rng.choice(["prefix", "starts_with", "suffix", "ends_with"])
            w = "%s(%s, %s)" % (f, col, sql_str(a))
        elif shape == 9:
            w = "%s NOT LIKE %s" % (col, sql_str("%" + a + "%"))
        elif shape == 10:
            w = "%s ILIKE %s" % (col, sql_str("%" + a.upper() + "%"))
        elif shape == 11:
            w = "regexp_matches(%s, %s)" % (col, sql_str(regex_escape(a)))
        elif shape == 12:
            w = "%s GLOB %s" % (col, sql_str("*" + "".join(c for c in a if c not in "[]*?") + "*"))
        elif shape == 13:
            w = "%s = %s" % (col, sql_str(a))
        elif shape == 14:
            w = "%s IN (%s, %s, %s)" % (col, sql_str(a), sql_str(b), sql_str(a + b))
        elif shape == 15:
            w = "(contains(%s, %s) OR %s LIKE %s)" % (col, sql_str(a), col, sql_str("%" + b + "%"))
        elif shape == 16:
            w = "contains(%s, %s) AND %s LIKE %s" % (col, sql_str(a), col, sql_str("%" + b + "%"))
        elif shape == 17:
            w = "(contains(%s, %s) OR %s IS NULL)" % (col, sql_str(a), col)
        elif shape == 18:
            w = "contains(%s, %s) AND i %% 3 = 0" % (col, sql_str(a))
        elif shape == 19:
            w = "%s LIKE %s ESCAPE ''" % (col, sql_str("%" + a + "%"))
        elif shape == 20:
            w = "(contains(%s, %s) OR NOT contains(%s, %s))" % (col, sql_str(a), col, sql_str(b))
        elif shape == 21 and rng.random() < 0.15:
            w = rng.choice(["contains(%s, NULL)", "%s LIKE NULL", "%s LIKE '%'", "%s LIKE ''", "contains(%s, '')",
                            "%s LIKE '_'", "%s LIKE '%_%'", "%s LIKE '__%'", "%s NOT LIKE '%'",
                            "%s ILIKE '%' || NULL"]).replace("%s", col)
        elif shape == 21:
            w = "%s >= %s AND %s < %s" % (col, sql_str(a), col, sql_str(a + "\U0010FFFF"))
        else:
            w = "%s LIKE %s" % (col, sql_str(a))  # no wildcard (if a has none): equality pushdown
        if rng.random() < 0.1:
            qs.append("SELECT i, %s FROM ng WHERE %s ORDER BY i LIMIT 5" % (col, w))
        else:
            qs.append("SELECT count(*), min(i), max(i), sum(i), count(%s) FROM ng WHERE %s" % (col, w))
    return qs


def ng_write_csv(rows, path):
    def field(v):
        if v is None:
            return "\\N"
        return '"' + v.replace('"', '""') + '"'
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write("%d,%s\n" % (row[0], ",".join(field(v) for v in row[1:])))


def ng_script(args, csv_path, queries, after):
    script = [".bail on", ".mode csv", ".headers off", "SET threads TO 1;", "SET memory_limit='1500MB';",
              "SET preserve_insertion_order = true;",
              "ATTACH '%s' AS db (ROW_GROUP_SIZE 8192); USE db;",
              "CREATE TABLE ng (i BIGINT, s_mix VARCHAR, s_short VARCHAR, s_long VARCHAR, s_tiny VARCHAR);",
              "COPY ng FROM '%s' (FORMAT csv, HEADER false, NULLSTR '\\N', QUOTE '\"', ESCAPE '\"');" % csv_path,
              ".print @@B load",
              "SELECT count(*), count(s_mix), count(s_short), count(s_long), count(s_tiny), sum(strlen(s_mix)) FROM ng;",
              ".print @@E load",
              ".bail off", "SET threads TO %d;" % args.threads]
    for i, q in enumerate(queries):
        script += [".print @@B q%d" % i, q + ";", ".print @@E q%d" % i]
    script += ["UPDATE ng SET s_mix = s_mix || 'zq' WHERE i % 1000 = 3;",
               "DELETE FROM ng WHERE i % 777 = 1;",
               "INSERT INTO ng SELECT * FROM ng WHERE i < 9000;"]
    for i, q in enumerate(after):
        script += [".print @@B a%d" % i, q + ";", ".print @@E a%d" % i]
    return script


def run(binary, env_columns, sql, timing_path, threads, extra_env=None):
    env = dict(os.environ)
    for v in ("DUCKDB_PRUNING_STATS", "PRUNING_STATS_TIMING", "PRUNING_STATS_COLUMNS", "PRUNING_PREDICATE_CACHE"):
        env.pop(v, None)
    if env_columns:
        env["PRUNING_STATS_COLUMNS"] = env_columns
    env.update(extra_env or {})
    env["PRUNING_STATS_TIMING"] = timing_path
    p = subprocess.run([binary, ":memory:"], input=sql.encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       env=env)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def split_results(out):
    res, cur, key = {}, [], None
    for line in out.splitlines():
        if line.startswith("@@B "):
            key, cur = line.split()[1], []
        elif line.startswith("@@E "):
            res[key] = cur
            key = None
        elif key is not None:
            cur.append(line)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--binary", default=phase4.SELECTIVE_BINARY)
    ap.add_argument("--queries", type=int, default=3000)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--words", default="20,200")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None, help="directory for logs (default: a temp dir)")
    ap.add_argument("--suite", default="types,ngram", help="types, ngram or both (comma separated)")
    ap.add_argument("--ngram-configs", default="ng3w20:20:3,ng3w200:200:3,ng2w200:200:2,ng4w200:200:4,ng5w50:50:5",
                    help="name:words:n,... of the ngram suite")
    args = ap.parse_args()
    out_dir = args.out or tempfile.mkdtemp(prefix="phase4_selftest_")
    os.makedirs(out_dir, exist_ok=True)
    ok = True
    for suite in args.suite.split(","):
        if suite == "types":
            ok = run_types(args, out_dir) and ok
        elif suite == "ngram":
            ok = run_ngram(args, out_dir) and ok
        elif suite == "predcache":
            ok = run_predcache(args, out_dir) and ok
        else:
            raise SystemExit("unknown suite " + suite)
    print("SELFTEST %s (logs in %s)" % ("PASSED" if ok else "FAILED", out_dir))
    sys.exit(0 if ok else 1)


def run_types(args, out_dir):
    rng = random.Random(args.seed)
    queries = gen_queries(rng, args.queries)
    after = gen_queries(random.Random(args.seed + 1), max(200, args.queries // 10))
    script = [".bail on", ".mode csv", ".headers off", "SET threads TO 1;", "SET memory_limit='1500MB';",
              "SET preserve_insertion_order = true;",
              "ATTACH '%s' AS db (ROW_GROUP_SIZE 8192); USE db;", create_sql(), ".bail off",
              "SET threads TO %d;" % args.threads]
    for i, q in enumerate(queries):
        script += [".print @@B q%d" % i, q + ";", ".print @@E q%d" % i]
    # modifications: UPDATE (invalidates statistics of the updated column), DELETE, INSERT, then repeat
    script += ["UPDATE t SET c_int = c_int + 3, c_varchar = c_varchar || 'x', c_double = c_double + 0.125 "
               "WHERE i % 1000 = 3;",
               "DELETE FROM t WHERE i % 777 = 1;",
               "INSERT INTO t SELECT * FROM t WHERE i < 9000;"]
    for i, q in enumerate(after):
        script += [".print @@B a%d" % i, q + ";", ".print @@E a%d" % i]
    configs = [("baseline", "")]
    for w in args.words.split(","):
        for kind in ("occupancy", "nullspace"):
            configs.append(("%s%s" % (kind[:3], w), ",".join("t.%s:%s:%s" % (c, kind, w) for c in COLUMNS)))
    return run_configs(args, out_dir, script, configs, queries, after, "baseline")


NG_FORMS = [  # (label, regex on the WHERE clause), first match wins
    ("NOT LIKE / NOT contains", r"NOT LIKE|NOT contains"),
    ("ILIKE", r"ILIKE"),
    ("GLOB", r"GLOB"),
    ("regexp_matches", r"regexp_matches"),
    ("IS NULL disjunct", r"IS NULL"),
    ("OR", r" OR "),
    ("AND", r" AND contains|\) AND |AND [a-z_]+ LIKE| AND i "),
    ("LIKE ESCAPE", r"ESCAPE"),
    ("prefix/starts_with/suffix/ends_with", r"^(prefix|starts_with|suffix|ends_with)\("),
    ("contains", r"^contains\("),
    ("range (>= AND <)", r">= .* AND .* <"),
    ("IN", r" IN \("),
    ("=", r" = "),
    ("LIKE", r"LIKE"),
]


def ng_form(sql):
    import re
    m = re.search(r" WHERE (.*?)( ORDER BY i LIMIT 5)?;?$", sql, re.S)
    where = m.group(1) if m else sql
    for label, rx in NG_FORMS:
        if re.search(rx, where):
            return label
    return "other"


def run_ngram(args, out_dir):
    rows, vocab, pool = ng_rows(args.seed)
    csv_path = os.path.join(out_dir, "ng.csv")
    ng_write_csv(rows, csv_path)
    rng = random.Random(args.seed + 100)
    queries = ng_gen_queries(rng, args.queries, vocab, pool)
    after = ng_gen_queries(random.Random(args.seed + 101), max(200, args.queries // 10), vocab, pool)
    script = ng_script(args, csv_path, queries, after)
    configs = [("ng_baseline", "")]
    for item in args.ngram_configs.split(","):
        name, words, n = item.split(":")
        configs.append((name, ",".join("ng.%s:ngram:%s:%s" % (c, words, n) for c in NG_COLUMNS)))
    ok = run_configs(args, out_dir, script, configs, queries, after, "ng_baseline")
    # row groups pruned by the n-gram statistics per predicate form
    for name, _ in configs[1:]:
        per_form = {}
        for r in phase4.load_jsonl(os.path.join(out_dir, name + ".timing.jsonl")):
            if r["type"] != "query_timing" or " FROM ng WHERE " not in r["sql"]:
                continue
            f = per_form.setdefault(ng_form(r["sql"]), [0, 0, 0])
            f[0] += 1
            f[1] += r["pruned_additional"]
            f[2] += 1 if r["pruned_additional"] else 0
        print("%-10s pruned row groups per form (queries / row groups pruned / queries with pruning): %s" % (
            name, "; ".join("%s %d/%d/%d" % (k, v[0], v[1], v[2]) for k, v in sorted(per_form.items()))))
    os.remove(csv_path)
    return ok


def run_configs(args, out_dir, script, configs, queries, after, base_name):
    results = {}
    for cfg in configs:
        name, columns = cfg[0], cfg[1]
        extra_env = cfg[2] if len(cfg) > 2 else None
        db = os.path.join(out_dir, name + ".db")
        for f in (db, db + ".wal"):
            if os.path.exists(f):
                os.remove(f)
        sql = "\n".join(script).replace("ATTACH '%s'", "ATTACH '%s'" % db) + "\n"
        timing = os.path.join(out_dir, name + ".timing.jsonl")
        if os.path.exists(timing):
            os.remove(timing)
        rc, out = run(args.binary, columns, sql, timing, args.threads, extra_env)
        with open(os.path.join(out_dir, name + ".out"), "w") as f:
            f.write(out)
        res = split_results(out)
        pruned = consult = built = 0
        failed = useless = empty = 0
        pc = collections.Counter()
        for r in phase4.load_jsonl(timing):
            if r["type"] == "query_timing":
                pruned += r["pruned_additional"]
                consult += r["consultations"]
                for k in ("pc_pruned", "pc_recorded_empty", "pc_recorded_rows", "pc_conflicts", "pc_invalidations",
                          "pc_scans_cacheable", "pc_scans_uncacheable"):
                    pc[k] += r.get(k, 0)
            elif r["type"] == "ingest":
                built += r["row_groups_built"]
                failed += r["row_groups_failed"]
                useless += r.get("row_groups_useless", 0)
                empty += r.get("row_groups_empty", 0)
        errors = sum(1 for v in res.values() for line in v if "Error" in line)
        results[name] = res
        print("%-11s rc=%d results=%d errors=%d row_groups_built=%d failed=%d useless=%d empty=%d "
              "consultations=%d pruned_by_additional=%d" % (name, rc, len(res), errors, built, failed, useless,
                                                            empty, consult, pruned), flush=True)
        if pc:
            print("            predicate cache: %s" % ", ".join("%s=%d" % (k[3:], v) for k, v in sorted(pc.items())),
                  flush=True)
        for f in (db, db + ".wal"):
            if os.path.exists(f):
                os.remove(f)
    base = results[base_name]
    ok = True
    for name, res in results.items():
        if name == base_name:
            continue
        diffs = [k for k in base if res.get(k) != base[k]]
        missing = len(base) - len(res)
        print("%-11s vs %s: %d queries, %d different, %d missing" % (name, base_name, len(base), len(diffs),
                                                                   missing))
        for k in diffs[:5]:
            q = "load" if k == "load" else (queries[int(k[1:])] if k[0] == "q" else after[int(k[1:])])
            print("   DIFF %s: %s\n     base=%s\n     got =%s" % (k, q[:300], base[k][:3], res.get(k, [])[:3]))
        ok = ok and not diffs and not missing
    return ok


# ------------------------------------------------------------------------------------------------------------------
# predicate cache suite
# ------------------------------------------------------------------------------------------------------------------
def pc_queries(rng, n):
    """queries of the types suite + string expression filters + LIMIT (early stop) + conjunctions that extend
    other queries' conjunctions (subset lookups)"""
    base = gen_queries(rng, n)
    extra = []
    for _ in range(n // 4):
        rg = rng.randrange(N_RG)
        val = rng.choice(base_values(rg))
        lit = value_sql("c_varchar", val)
        shape = rng.randrange(4)
        if shape == 0:
            w = "contains(c_varchar, %s)" % lit
        elif shape == 1:
            w = "c_varchar LIKE '%%' || %s || '%%'" % lit
        elif shape == 2:
            w = "c_varchar_long LIKE 'same_prefix_%d%%'" % (val // 10)
        else:
            w = "(c_varchar = %s OR c_int = %s)" % (lit, value_sql("c_int", val + 7))
        extra.append("SELECT count(*), min(i), max(i), sum(i) FROM t WHERE %s" % w)
    # the static part of top-N queries again without top-N (a top-N threshold must never be recorded as "no rows")
    for q in base:
        m = re.match(r"SELECT i, \w+ FROM t WHERE (.*) ORDER BY ", q)
        if m:
            extra.append("SELECT count(*), min(i), max(i), sum(i) FROM t WHERE %s" % m.group(1))
    simple = [q for q in base + extra if q.startswith("SELECT count(*), min(i), max(i), sum(i) FROM t WHERE ")]
    derived = []
    for _ in range(n // 3):
        a = rng.choice(simple).split(" WHERE ", 1)[1]
        b = rng.choice(simple).split(" WHERE ", 1)[1]
        derived.append("SELECT count(*), min(i), max(i), sum(i) FROM t WHERE (%s) AND (%s)" % (a, b) if
                       rng.random() < 0.3 else "SELECT count(*), min(i), max(i), sum(i) FROM t WHERE %s AND %s" %
                       (a, b))
    limits = []
    for _ in range(n // 10):
        a = rng.choice(simple).split(" WHERE ", 1)[1]
        limits.append("SELECT count(*) FROM (SELECT i FROM t WHERE %s LIMIT %d)" % (a, rng.choice([1, 3, 100])))
    return base + extra, derived, limits


def run_predcache(args, out_dir):
    rng = random.Random(args.seed + 200)
    first, derived, limits = pc_queries(rng, args.queries)
    # LIMIT queries first (partial scans must not record unknown row groups), then everything twice
    phase_a = limits + first + derived + limits + first + derived
    repeat = rng.sample(first + derived, min(len(first + derived), max(100, args.queries // 5))) + limits
    script = [".bail on", ".mode csv", ".headers off", "SET threads TO 1;", "SET memory_limit='1500MB';",
              "SET preserve_insertion_order = true;",
              "ATTACH '%s' AS db (ROW_GROUP_SIZE 8192); USE db;", create_sql(), "CHECKPOINT;", ".bail off",
              "SET threads TO %d;" % args.threads]
    labels = []

    def block(qs):
        for q in qs:
            k = "q%d" % len(labels)
            labels.append(q)
            script.extend([".print @@B %s" % k, q + ";", ".print @@E %s" % k])

    block(phase_a)
    steps = [
        ["UPDATE t SET c_int = c_int + 3, c_varchar = c_varchar || 'x' WHERE i % 1000 = 3;"],
        ["BEGIN;", "DELETE FROM t WHERE i % 5 = 0;"], ["ROLLBACK;"],
        ["BEGIN;", "UPDATE t SET c_bigint = c_bigint + 1, c_varchar = 'zz' || c_varchar, c_int = c_int + 1 "
                   "WHERE i % 3 = 0;"], ["ROLLBACK;"],
        ["BEGIN;", "INSERT INTO t SELECT * FROM t WHERE i < 9000;"], ["ROLLBACK;"],
        ["INSERT INTO t SELECT * FROM t WHERE i < 9000;"],
        ["DELETE FROM t WHERE i % 777 = 1;"],
        ["UPDATE t SET c_double = c_double + 0.125, c_varchar = c_varchar || 'y' WHERE i % 501 = 2;"],
        ["CHECKPOINT;"],
    ]
    for st in steps:
        script.extend(st)
        block(repeat)
        block(repeat)
    queries = labels
    configs = [("pc_off", ""), ("pc_exact", "", {"PRUNING_PREDICATE_CACHE": "1"}),
               ("pc_subset", "", {"PRUNING_PREDICATE_CACHE": "subset"}),
               ("pc_subset_occ200", ",".join("t.%s:occupancy:200" % c for c in COLUMNS),
                {"PRUNING_PREDICATE_CACHE": "subset"})]
    return run_configs(args, out_dir, script, configs, queries, [], "pc_off")


if __name__ == "__main__":
    main()
