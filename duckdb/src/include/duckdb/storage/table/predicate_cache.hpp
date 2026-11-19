//===----------------------------------------------------------------------===//
//                         DuckDB
//
// duckdb/storage/table/predicate_cache.hpp
//
// Predicate cache (study instrumentation, not part of upstream DuckDB), after Schmidt et al., "Predicate Caching:
// Query-Driven Secondary Indexing for Cloud Data Warehouses" (SIGMOD 2024) and ClickHouse's query condition cache.
//
// Enabled only when the environment variable PRUNING_PREDICATE_CACHE is set to 1/on/exact (whole-conjunction keys)
// or 2/subset (additionally: an entry whose conjunct set is a subset of the scan's conjunct set may prune).
// In-process, in-memory, empty at process start. Per table (RowGroupCollection) a map
//   canonical static (plan-time) pushed-down filter conjunction -> per row group {known, has >= 1 qualifying row}.
// Dynamic filters (join filters, top-N) and OptionalFilters are not part of the key. A row group's bit is recorded
// only when it was decided: pruned by the static filters' zonemaps / selective statistics, or completely scanned
// with the whole conjunction evaluated on all its rows (and all rows visible, no updates). A known "no rows" bit
// lets later scans skip the row group. Any write to the table (append, delete, update, checkpoint, ...) clears the
// table's entries (epoch). When the variable is unset no state is created.
//===----------------------------------------------------------------------===//

#pragma once

#include "duckdb/common/common.hpp"
#include "duckdb/common/atomic.hpp"
#include "duckdb/common/mutex.hpp"
#include "duckdb/common/optional_ptr.hpp"
#include "duckdb/common/unordered_map.hpp"
#include "duckdb/storage/storage_index.hpp"

namespace duckdb {

class ClientContext;
class RowGroup;
class RowGroupCollection;
class TableFilter;
class TableFilterSet;
class PhysicalOperator;

enum class PredicateCacheMode : uint8_t { OFF = 0, EXACT = 1, SUBSET = 2 };

struct PredicateCache {
	//! PRUNING_PREDICATE_CACHE (evaluated once and cached)
	static PredicateCacheMode Mode();
	static bool Enabled() {
		return Mode() != PredicateCacheMode::OFF;
	}
};

struct PredicateCacheEntry {
	//! canonical key (length-prefixed serialized leaves, sorted) and readable rendering
	string key;
	string readable;
	vector<string> leaves;
	uint64_t epoch = 0;
	//! one bit per row group
	vector<uint64_t> known;
	vector<uint64_t> has_rows;
	idx_t Bytes() const {
		return key.size() + (known.size() + has_rows.size()) * sizeof(uint64_t);
	}
};

//! The cache of one table (lives in its RowGroupCollection)
class PredicateCacheTable {
public:
	~PredicateCacheTable();
	//! any write to the table: all entries become invalid
	void OnWrite();

	mutex lock;
	atomic<uint64_t> epoch {1};
	unordered_map<string, unique_ptr<PredicateCacheEntry>> entries;
};

//! One table scan (shared by the scan's threads)
class PredicateCacheScan {
public:
	static shared_ptr<PredicateCacheScan> Create(ClientContext &context, RowGroupCollection &collection,
	                                             const vector<StorageIndex> &storage_ids,
	                                             optional_ptr<TableFilterSet> filters,
	                                             optional_ptr<const PhysicalOperator> op, bool sampling,
	                                             string &info_json);
	~PredicateCacheScan();

	//! a known "no qualifying row" entry for this row group
	bool KnownEmpty(idx_t row_group_index) const {
		return row_group_index < n_row_groups && (known_empty[row_group_index / 64] >> (row_group_index % 64)) & 1;
	}
	//! cause: 1 = min/max zonemap, 3 = selective statistic, 4 = this cache
	void OnPruned(RowGroup &row_group, uint8_t cause);
	void OnEnter(RowGroup &row_group, idx_t max_row_group_row);
	void OnSegmentSkip(RowGroup &row_group, idx_t vectors);
	void OnVector(RowGroup &row_group, idx_t rows_passed, bool all_visible);

	//! JSON object for the pruning counters
	string InfoJSON() const;

private:
	struct RowGroupState {
		//! 0 untouched, 1 pruned (static filters alone prune), 2 entered, 4 pruned by the cache, 5 pruned, but not
		//! by the static filters alone (unknown)
		atomic<uint8_t> state;
		atomic<uint32_t> vectors_total;
		atomic<uint32_t> vectors_done;
		atomic<bool> any_rows;
		atomic<bool> not_all_visible;
		atomic<uint64_t> count_at_enter;
	};
	void Finish();
	bool StaticFiltersPrune(RowGroup &row_group);

	shared_ptr<PredicateCacheTable> table;
	string key;
	string readable;
	vector<string> leaves;
	uint64_t epoch = 0;
	//! the filters applied to rows are exactly the static key filters (no dynamic join filters)
	bool exact_applied = false;
	//! the scan has optional or dynamic filters: a pruned row group must be re-checked with the static filters
	bool needs_recheck = false;
	//! static non-optional filters per storage column (re-check, update check)
	vector<std::pair<StorageIndex, unique_ptr<TableFilter>>> static_filters;
	idx_t n_row_groups = 0;
	unique_ptr<uint64_t[]> known_empty;
	idx_t known_empty_at_start = 0;
	idx_t entries_used = 0;
	unique_ptr<RowGroupState[]> row_groups;

	PredicateCacheScan() = default;
};

} // namespace duckdb
