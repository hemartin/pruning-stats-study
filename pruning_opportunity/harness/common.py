"""Shared definitions for the pruning-opportunity harness.

Layout (all below pruning_opportunity/):
  data/<scale>/micro/<dataset>.csv            header time,data
  data/<scale>/{tpch,tpcds}/<table>.csv       with header
  data/<scale>/clickbench/hits.csv            no header (large scale: repo-root hits.csv by default)
  db/<scale>/<db_name>.db                     persistent DuckDB files (ROW_GROUP_SIZE 8192)
  queries/                                    generated query files (cardinality)
  results/raw/<scale>/<mode>/<setup>/         status.jsonl (+ pruning.jsonl in count mode)
  results/<scale>/                            aggregated tables
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PO_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(PO_DIR)
SQL_DIR = os.path.join(REPO_DIR, "experiments", "sql")
QUERY_DIR = os.path.join(PO_DIR, "queries")
DEFAULT_BINARY = os.path.join(PO_DIR, "stock", "duckdb", "build", "release", "duckdb")

MICRO_DATASETS = ["unsorted", "sorted", "outliers",
                  "cardinality_100", "cardinality_1000", "cardinality_10000", "cardinality_100000"]
CARDINALITIES = [100, 1000, 10000, 100000]


def data_dir(scale):
    return os.path.join(PO_DIR, "data", scale)


def db_dir(scale):
    return os.path.join(PO_DIR, "db", scale)


def raw_dir(scale, mode):
    return os.path.join(PO_DIR, "results", "raw", scale, mode)


def results_dir(scale):
    return os.path.join(PO_DIR, "results", scale)


def split_sql(text):
    """Split SQL text into statements on ';' outside quotes and comments. Empty statements are dropped."""
    stmts, cur, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c in ("'", '"'):
            j = i + 1
            while j < n:
                if text[j] == c:
                    if j + 1 < n and text[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            cur.append(text[i:j + 1])
            i = j + 1
        elif c == '-' and text.startswith('--', i):
            j = text.find('\n', i)
            j = n if j < 0 else j
            i = j
        elif c == '/' and text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            i = j
        elif c == ';':
            s = ''.join(cur).strip()
            if s:
                stmts.append(s)
            cur = []
            i += 1
        else:
            cur.append(c)
            i += 1
    s = ''.join(cur).strip()
    if s:
        stmts.append(s)
    return stmts


def parse_experiment_file(path):
    """Returns (create_statements, copy_statements, queries) of an experiment SQL file."""
    with open(path, encoding="utf-8") as f:
        stmts = split_sql(f.read())
    creates, copies, queries = [], [], []
    for s in stmts:
        head = s.lstrip().split(None, 1)[0].upper()
        if head in ("SET", "ATTACH", "USE", "PRAGMA"):
            continue
        if head == "CREATE":
            creates.append(s)
        elif head == "COPY":
            copies.append(s)
        else:
            queries.append(s)
    return creates, copies, queries


def rewrite_copy(copy_stmt, new_path):
    """Replace the file name in COPY <t> FROM '<file>' (...)"""
    return re.sub(r"FROM\s+'[^']*'", "FROM '" + new_path.replace("'", "''") + "'", copy_stmt, count=1,
                  flags=re.IGNORECASE)


def copy_table(copy_stmt):
    m = re.match(r"\s*COPY\s+(\w+)\s+FROM\s+'([^']*)'", copy_stmt, flags=re.IGNORECASE)
    return m.group(1), m.group(2)


# ----------------------------------------------------------------------------------------------------------------
# Benchmarks / setups
# ----------------------------------------------------------------------------------------------------------------
class Setup:
    def __init__(self, benchmark, name, db_name, query_file, query_prefix):
        self.benchmark = benchmark
        self.name = name                    # unique setup name, used for directories and tags
        self.db_name = db_name              # db/<scale>/<db_name>.db
        self.query_file = query_file
        self.query_prefix = query_prefix    # qid = prefix + index

    def queries(self):
        _, _, qs = parse_experiment_file(self.query_file)
        return qs

    def qids(self, n):
        if self.benchmark == "micro":
            return ["%04d" % i for i in range(n)]
        return ["q%02d" % (i + 1) for i in range(n)]


def micro_setups():
    setups = []
    for d in ["unsorted", "outliers", "sorted"]:
        setups.append(Setup("micro", "point_" + d, "micro_" + d,
                            os.path.join(SQL_DIR, "sortedness", "sql_queries_%s.sql" % d), ""))
    for g in ["seconds", "minutes", "hours"]:
        for d in ["unsorted", "outliers", "sorted"]:
            setups.append(Setup("micro", "range_%s_%s" % (g, d), "micro_" + d,
                                os.path.join(SQL_DIR, "range", "sql_queries_%s_range_%s.sql" % (d, g)), ""))
    for c in CARDINALITIES:
        setups.append(Setup("micro", "cardinality_%d" % c, "micro_cardinality_%d" % c,
                            os.path.join(QUERY_DIR, "sql_queries_cardinality_%d.sql" % c), ""))
    return setups


def established_setups():
    return [Setup(b, b, b, os.path.join(SQL_DIR, "established", "sql_queries_%s.sql" % b), "q")
            for b in ["tpch", "tpcds", "clickbench"]]


def all_setups():
    return micro_setups() + established_setups()


def select_setups(spec):
    """spec: comma-separated list of setup names, benchmark names (micro,tpch,tpcds,clickbench) or 'all'."""
    setups = all_setups()
    if not spec or spec == "all":
        return setups
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    result = []
    for s in setups:
        if s.name in wanted or s.benchmark in wanted:
            result.append(s)
    unknown = [w for w in wanted if w not in {s.name for s in setups} | {s.benchmark for s in setups}]
    if unknown:
        raise SystemExit("unknown setups: %s" % unknown)
    return result


# ----------------------------------------------------------------------------------------------------------------
# Databases: DDL + COPY statements taken from the experiment SQL files
# ----------------------------------------------------------------------------------------------------------------
def db_definitions(scale, clickbench_csv=None):
    """name -> (list of CREATE statements, list of (table, csv_path, copy_stmt))."""
    ddir = data_dir(scale)
    defs = {}
    for d in MICRO_DATASETS:
        if d.startswith("cardinality_"):
            f = os.path.join(SQL_DIR, "cardinality", "sql_queries_%s.sql" % d)
        else:
            f = os.path.join(SQL_DIR, "sortedness", "sql_queries_%s.sql" % d)
        creates, copies, _ = parse_experiment_file(f)
        csv = os.path.join(ddir, "micro", d + ".csv")
        defs["micro_" + d] = (creates, [(copy_table(copies[0])[0], csv, rewrite_copy(copies[0], csv))])
    for b in ["tpch", "tpcds"]:
        creates, copies, _ = parse_experiment_file(os.path.join(SQL_DIR, "established", "sql_queries_%s.sql" % b))
        loads = []
        for c in copies:
            t, _ = copy_table(c)
            csv = os.path.join(ddir, b, t + ".csv")
            loads.append((t, csv, rewrite_copy(c, csv)))
        defs[b] = (creates, loads)
    creates, copies, _ = parse_experiment_file(os.path.join(SQL_DIR, "established", "sql_queries_clickbench.sql"))
    csv = clickbench_csv or os.path.join(ddir, "clickbench", "hits.csv")
    if scale == "large" and not clickbench_csv and not os.path.exists(csv):
        csv = os.path.join(REPO_DIR, "hits.csv")
    defs["clickbench"] = (creates, [("hits", csv, rewrite_copy(copies[0], csv))])
    return defs


def sql_str(s):
    return "'" + s.replace("'", "''") + "'"
