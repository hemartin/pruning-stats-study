//===----------------------------------------------------------------------===//
//                         DuckDB
//
// duckdb/storage/table/pruning_stats.hpp
//
// Pruning-opportunity counters (study instrumentation, not part of upstream DuckDB).
//
// Enabled only when the environment variable DUCKDB_PRUNING_STATS=<output file> is set. Then, for every scan of a
// base table, the row groups are classified as pruned (row-group zonemap), scanned without any row satisfying the
// pushed-down table filters, scanned with >= 1 such row, partially processed / never reached (early stop), and
// one JSON line per (query, scan) plus one per query is appended to the output file at the end of each query.
// When the variable is unset no state is created; the only cost is a null-pointer check per row group / vector.
//===----------------------------------------------------------------------===//

#pragma once

#include "duckdb/common/common.hpp"
#include "duckdb/common/atomic.hpp"
#include "duckdb/common/mutex.hpp"
#include "duckdb/common/types/selection_vector.hpp"
#include "duckdb/common/types/data_chunk.hpp"
#include "duckdb/common/column_index.hpp"

namespace duckdb {

class ClientContext;
class RowGroup;
class RowGroupCollection;
class ScanFilterInfo;
class TableFilter;
class TableFilterSet;
class TableCatalogEntry;
class PhysicalOperator;
class ExpressionExecutor;
class Expression;

struct PruningStats {
	//! Whether counting is enabled (DUCKDB_PRUNING_STATS set and non-empty); evaluated once and cached
	static bool Enabled();
	//! Registers the per-connection query state (called from the ClientContext constructor)
	static void RegisterClientContext(ClientContext &context);
	//! A base table was bound in the current query (plan-time accounting)
	static void OnBindTable(ClientContext &context, const string &table_name);
	//! The physical plan of the current query is about to be executed
	static void OnPlan(ClientContext &context, const PhysicalOperator &plan);
};

//! One leaf of a scan's pushed-down filters (column filters are flattened over AND)
struct PruningLeafFilter {
	idx_t scan_column_index;
	string column_name;
	string column_type;
	//! constant comparison (=, <, ...), in, or, is_null, optional(...), dynamic_topn, expression, ...
	string kind;
	//! static | join | topn
	string origin;
	//! false for OptionalFilter (only used for zonemap pruning, never applied to rows)
	bool applied_to_rows;
	unique_ptr<TableFilter> filter;
	//! row groups for which this leaf was the first one (in the engine's check order) proving "no match"
	atomic<idx_t> pruned_first;
	//! row groups (among the pruned ones) that this leaf alone could prune
	atomic<idx_t> prunable_alone;
	//! same for row groups pruned by selective (additional) statistics after min/max failed: the first leaf whose
	//! statistic alone proves "no match", and every such leaf
	atomic<idx_t> pruned_first_additional;
	atomic<idx_t> prunable_alone_additional;
};

struct PruningRowGroupStat {
	//! 0 = never reached, 1 = pruned by the row-group zonemap (min/max), 2 = entered (passed the zonemap check),
	//! 3 = pruned by a selective (additional) statistic, 4 = pruned by the predicate cache
	atomic<uint8_t> state;
	atomic<uint32_t> vectors_total;
	atomic<uint32_t> vectors_done;
	atomic<uint32_t> vectors_segment_skipped;
	atomic<uint64_t> rows_scanned;
	atomic<uint64_t> rows_passed;
	atomic<uint64_t> rows_passed_incl_optional;
};

class PruningScanStats {
public:
	static shared_ptr<PruningScanStats> Create(ClientContext &context, TableCatalogEntry &table,
	                                           RowGroupCollection &collection, const vector<ColumnIndex> &column_indexes,
	                                           optional_ptr<TableFilterSet> filters,
	                                           optional_ptr<const PhysicalOperator> op);

	string table_name;
	idx_t total_rows = 0;
	idx_t total_row_groups = 0;
	idx_t scan_id = 0;
	bool has_filters = false;
	bool has_optional = false;
	bool has_dynamic_optional = false;
	vector<unique_ptr<PruningLeafFilter>> leaves;
	unique_ptr<PruningRowGroupStat[]> row_groups;
	atomic<idx_t> pruned_unattributed;
	atomic<idx_t> out_of_range_row_groups;
	//! row groups pruned by selective statistics where no single leaf suffices (e.g. a range formed by two leaves)
	atomic<idx_t> pruned_additional_no_single_leaf;
	//! row-id range check (PRUNING_ROWID_SKIP=1): pruned row groups whose first proving leaf is a rowid filter
	atomic<idx_t> pruned_rowid_range;
	//! ... and pruned row groups that only rowid leaves can prune (no other leaf alone proves "no match")
	atomic<idx_t> pruned_rowid_only;
	//! per filtered column (scan column index, name): row groups for which it was the first column whose complete
	//! filter was proven unsatisfiable by its selective statistic
	vector<idx_t> filter_columns;
	vector<string> filter_column_names;
	unique_ptr<atomic<idx_t>[]> additional_first_by_column;
	//! predicate cache info of this scan (JSON object; empty if the cache is off)
	string predcache_json;

	string ToJSON(idx_t seq, const string &tag, const string &session) const;
	PruningRowGroupStat *GetRowGroup(RowGroup &row_group);
};

//! Per-thread part of a scan (lives in TableScanState); not thread-safe by design
class PruningScanLocal {
public:
	PruningScanLocal(ClientContext &context, shared_ptr<PruningScanStats> stats);
	~PruningScanLocal();

	void OnPruned(RowGroup &row_group, ScanFilterInfo &filters, bool by_additional = false);
	void OnPrunedPredicateCache(RowGroup &row_group);
	void OnEnter(RowGroup &row_group, idx_t max_row_group_row);
	void OnSegmentSkip(RowGroup &row_group, idx_t vectors);
	void OnVector(RowGroup &row_group, idx_t rows_scanned, idx_t rows_passed, idx_t rows_passed_incl_optional);
	//! Number of rows in "result" (already filtered by the non-optional filters) that also satisfy all optional filters
	idx_t CountOptional(RowGroup &row_group, DataChunk &result, idx_t count);

private:
	void BuildOptionalExecutor(DataChunk &result);

	ClientContext &context;
	shared_ptr<PruningScanStats> stats;
	unique_ptr<Expression> optional_expr;
	unique_ptr<ExpressionExecutor> optional_executor;
	DataChunk optional_chunk;
	vector<idx_t> optional_columns;
	idx_t optional_row_group = DConstants::INVALID_INDEX;
	SelectionVector optional_sel;
};

} // namespace duckdb
