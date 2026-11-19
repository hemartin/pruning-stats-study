//===----------------------------------------------------------------------===//
//                         DuckDB
//
// duckdb/storage/table/selective_stats.hpp
//
// Selective, per-column near-optimal pruning statistics (pruning study, not part of upstream DuckDB).
//
// The columns that get an additional statistic per row group are chosen at RUNTIME with the environment variable
//
//   PRUNING_STATS_COLUMNS="table.column:kind[:words],table.column:kind[:words],..."
//
// kind = occupancy | nullspace | ngram | bloom, words = size budget in 64-bit words (default 200); "table.*" selects every
// column of the table whose type is supported. ngram (VARCHAR only): "table.column:ngram[:words[:n]]" (or kind
// "ngramN"), the set of distinct byte n-grams (default n = 3) of the row group's values, for LIKE/contains pruning.
// bloom: the DBTest 2026 paper's Bloom filter (one block of `words` words, one hash function), equality and IN only.
// Names are case-insensitive. Unset/empty: no additional statistics at all (the binary then behaves like
// min/max-only DuckDB: no ingest buffering, a null check per filtered column and row group).
//
// Statistics are built in memory while rows are appended (RowGroup::Append), once a row group is full; they are not
// persisted, so data must be loaded and queried in the same process. At query time they are consulted only after the
// min/max zonemaps of ALL filtered columns failed to prune the row group (RowGroup::CheckZonemap).
//
// ec2-timing branch: no per-statement timing log (PRUNING_STATS_TIMING) and no query-side counters; only the
// build-on-load pass writes one line per table to stderr (PRUNING_STATS_BUILD_ON_LOAD ..., incl. its wall time).
//===----------------------------------------------------------------------===//

#pragma once

#include "duckdb/common/common.hpp"
#include "duckdb/common/atomic.hpp"
#include "duckdb/common/mutex.hpp"
#include "duckdb/common/types.hpp"

namespace duckdb {

class ClientContext;
class ColumnDefinition;
class TableFilter;
class Value;
class Vector;
struct DataTableInfo;

enum class SelectiveStatKind : uint8_t { OCCUPANCY = 1, NULLSPACE = 2, NGRAM = 3, BLOOM = 4 };

//! One entry of PRUNING_STATS_COLUMNS (resolved to a concrete column). Also accumulates ingest timings.
struct SelectiveColumnSpec {
	string table;
	string column;
	SelectiveStatKind kind = SelectiveStatKind::OCCUPANCY;
	idx_t words = 200;
	//! n of the n-gram statistic (kind NGRAM, 1..8)
	idx_t ngram_n = 3;
	//! ingest accumulators since the last report (reset by the timing log at the end of each statement)
	atomic<uint64_t> buffer_ns {0};
	atomic<uint64_t> build_ns {0};
	atomic<uint64_t> values {0};
	atomic<uint64_t> row_groups_built {0};
	atomic<uint64_t> row_groups_failed {0};
	atomic<uint64_t> bytes {0};
	//! NGRAM: row groups without a statistic because it would be useless (expected false-positive rate too high,
	//! encoding does not fit, or too many distinct n-grams to buffer), and row groups whose n-gram set is empty
	atomic<uint64_t> row_groups_useless {0};
	atomic<uint64_t> row_groups_empty {0};
	//! NGRAM: per finished row group (in build order): distinct n-grams, stored bytes (0 = none), expected
	//! false-positive rate per absent n-gram (1 = no statistic); reset with the other statement accumulators
	mutex detail_lock;
	vector<uint64_t> rg_distinct;
	vector<uint64_t> rg_bytes;
	vector<double> rg_eps;
	//! totals since process start (never reset)
	atomic<uint64_t> total_build_ns {0};
	atomic<uint64_t> total_buffer_ns {0};
	atomic<uint64_t> total_row_groups_built {0};
	atomic<uint64_t> total_bytes {0};

	string Name() const {
		return table + "." + column;
	}
	string KindName() const;
};

//! An immutable, finished statistic of one column in one row group
class SelectiveStat {
public:
	SelectiveStatKind kind;
	PhysicalType ptype;
	//! NGRAM: n
	uint32_t ngram_n = 0;
	//! number of stored 64-bit words (only the words the encoding needs; the budget can be larger)
	idx_t n_words = 0;
	unsafe_unique_array<uint64_t> words;

	//! Whether a value with this key may exist (no false negatives). Key domain: SelectiveKeys::PointKey.
	bool MayContainKey(uint64_t key) const;
	//! Whether a value with an ordered key in [lo, hi] may exist (occupancy; nullspace: enumerates short integer
	//! ranges, otherwise true)
	bool MayContainRange(uint64_t lo, uint64_t hi) const;
	idx_t SizeInBytes() const {
		return n_words * sizeof(uint64_t);
	}
};

//! Per (top-level) column and row group: buffer during ingest, finished statistic afterwards
class SelectiveColumnState {
public:
	SelectiveColumnState(SelectiveColumnSpec &spec, PhysicalType ptype);
	~SelectiveColumnState();

	SelectiveColumnSpec &spec;
	PhysicalType ptype;
	//! key buffer while the row group is being filled (released after the statistic is built)
	vector<uint64_t> keys;
	//! NGRAM, n <= 3: exact bitmap of the n-grams seen (2^(8n) bits) instead of the key buffer
	unsafe_unique_array<uint64_t> ngram_bitmap;
	//! NGRAM, n > 3: compact (sort + unique) the key buffer when it reaches this size
	idx_t ngram_compact_at = 0;
	//! NGRAM: too many distinct n-grams in this row group, buffering stopped, no statistic
	bool ngram_overflow = false;
	//! set once (release) when the row group is full; read (acquire) by scans
	atomic<SelectiveStat *> stat {nullptr};
	//! owner of the statistic (stays alive when the statistic is invalidated, scans may still hold the pointer)
	unique_ptr<SelectiveStat> stat_owner;
	//! no statistic will (ever again) be built: an append was reverted, or the column was updated
	bool disabled = false;

	//! Buffer the keys of the first `count` rows of `vector` (called from RowGroup::Append)
	void Append(Vector &input, idx_t count);
	//! The row group is full: build the statistic from the buffered keys
	void Finish();
	//! Values of the column changed (UPDATE) or an append was reverted
	void Invalidate(bool drop_stat);
};

struct SelectiveStats {
	//! PRUNING_STATS_COLUMNS set and at least one valid entry (evaluated once)
	static bool Enabled();
	//! Whether statistics of this kind can be built for this physical type
	static bool SupportsType(SelectiveStatKind kind, PhysicalType type);
	//! Resolve the specs of a table (index = column index; nullptr = no statistic)
	static vector<SelectiveColumnSpec *> Resolve(const string &table, const vector<ColumnDefinition> &columns);
	//! PRUNING_STATS_BUILD_ON_LOAD: 0 (unset / "0" / "off") = statistics only at ingest; N >= 1 = also build them for
	//! tables loaded from disk (database open / ATTACH), with N threads (evaluated once)
	static idx_t BuildOnLoadThreads();
	//! stderr record of one build-on-load pass
	static void LogLoadBuild(const string &table, idx_t row_groups, idx_t threads, uint64_t wall_ns, uint64_t read_ns,
	                         const string &error);

	//! true if `filter` (a column's complete pushed-down filter, or a part of it) can match no row of the row group
	//! described by `stat`
	static bool FilterCanPrune(const TableFilter &filter, const SelectiveStat &stat);

};

} // namespace duckdb
