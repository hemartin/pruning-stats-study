#include "duckdb/storage/table/pruning_stats.hpp"

#include "duckdb/catalog/catalog_entry/table_catalog_entry.hpp"
#include "duckdb/common/error_data.hpp"
#include "duckdb/execution/expression_executor.hpp"
#include "duckdb/execution/operator/scan/physical_table_scan.hpp"
#include "duckdb/execution/physical_operator.hpp"
#include "duckdb/function/table/table_scan.hpp"
#include "duckdb/main/client_config.hpp"
#include "duckdb/main/client_context.hpp"
#include "duckdb/main/client_context_state.hpp"
#include "duckdb/main/database.hpp"
#include "duckdb/parser/keyword_helper.hpp"
#include "duckdb/planner/expression/bound_conjunction_expression.hpp"
#include "duckdb/planner/expression/bound_reference_expression.hpp"
#include "duckdb/planner/filter/conjunction_filter.hpp"
#include "duckdb/planner/filter/constant_filter.hpp"
#include "duckdb/planner/filter/dynamic_filter.hpp"
#include "duckdb/planner/filter/in_filter.hpp"
#include "duckdb/planner/filter/optional_filter.hpp"
#include "duckdb/planner/filter/struct_filter.hpp"
#include "duckdb/planner/table_filter.hpp"
#include "duckdb/storage/table/column_data.hpp"
#include "duckdb/storage/table/row_group.hpp"
#include "duckdb/storage/table/row_group_collection.hpp"
#include "duckdb/storage/table/scan_state.hpp"
#include "duckdb/storage/table/selective_stats.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <unistd.h>

namespace duckdb {

//===--------------------------------------------------------------------===//
// Global switch and output
//===--------------------------------------------------------------------===//
static const char *PruningStatsPathRaw() {
	static const char *path = []() -> const char * {
		auto env = std::getenv("DUCKDB_PRUNING_STATS");
		if (!env || !*env) {
			return nullptr;
		}
		return env;
	}();
	return path;
}

bool PruningStats::Enabled() {
	static const bool enabled = PruningStatsPathRaw() != nullptr;
	return enabled;
}

namespace {

struct PruningStatsWriter {
	mutex lock;
	FILE *file = nullptr;
	bool failed = false;
	string session;
	atomic<idx_t> next_seq {0};

	PruningStatsWriter() {
		auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
		               std::chrono::system_clock::now().time_since_epoch())
		               .count();
		session = std::to_string(getpid()) + "-" + std::to_string(now);
	}

	static PruningStatsWriter &Get() {
		static PruningStatsWriter writer;
		return writer;
	}

	void Write(const string &lines) {
		lock_guard<mutex> guard(lock);
		if (failed) {
			return;
		}
		if (!file) {
			file = fopen(PruningStatsPathRaw(), "a");
			if (!file) {
				failed = true;
				fprintf(stderr, "DUCKDB_PRUNING_STATS: cannot open '%s' for appending\n", PruningStatsPathRaw());
				return;
			}
		}
		fwrite(lines.data(), 1, lines.size(), file);
		fflush(file);
	}
};

string JSONEscape(const string &input) {
	string result;
	result.reserve(input.size() + 2);
	result += '"';
	for (auto c : input) {
		auto uc = static_cast<unsigned char>(c);
		switch (c) {
		case '"':
			result += "\\\"";
			break;
		case '\\':
			result += "\\\\";
			break;
		case '\n':
			result += "\\n";
			break;
		case '\r':
			result += "\\r";
			break;
		case '\t':
			result += "\\t";
			break;
		default:
			if (uc < 0x20) {
				char buf[8];
				snprintf(buf, sizeof(buf), "\\u%04x", uc);
				result += buf;
			} else {
				result += c;
			}
		}
	}
	result += '"';
	return result;
}

string JSONBool(bool b) {
	return b ? "true" : "false";
}

//===--------------------------------------------------------------------===//
// Per-query state (one per ClientContext)
//===--------------------------------------------------------------------===//
class PruningQueryState : public ClientContextState {
public:
	mutex lock;
	bool active = false;
	idx_t seq = 0;
	string sql;
	std::chrono::steady_clock::time_point start;
	vector<shared_ptr<PruningScanStats>> scans;
	vector<string> bound_tables;
	vector<string> plan_scan_tables;
	idx_t plan_empty_results = 0;
	idx_t plan_count = 0;

	void Reset() {
		active = false;
		sql.clear();
		scans.clear();
		bound_tables.clear();
		plan_scan_tables.clear();
		plan_empty_results = 0;
		plan_count = 0;
	}

	void QueryBegin(ClientContext &context) override {
		lock_guard<mutex> guard(lock);
		Reset();
		active = true;
		seq = PruningStatsWriter::Get().next_seq++;
		sql = context.GetCurrentQuery();
		start = std::chrono::steady_clock::now();
	}

	using ClientContextState::QueryEnd;
	void QueryEnd(ClientContext &context, optional_ptr<ErrorData> error) override {
		auto end = std::chrono::steady_clock::now();
		string tag;
		auto &vars = ClientConfig::GetConfig(context).user_variables;
		auto entry = vars.find("pruning_tag");
		if (entry != vars.end() && !entry->second.IsNull()) {
			tag = entry->second.ToString();
		}
		auto &writer = PruningStatsWriter::Get();
		string out;
		{
			lock_guard<mutex> guard(lock);
			if (!active) {
				return;
			}
			double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count();
			out += "{\"type\":\"query\",\"session\":" + JSONEscape(writer.session) + ",\"seq\":" + to_string(seq) +
			       ",\"tag\":" + JSONEscape(tag) + ",\"elapsed_ms\":" + to_string(elapsed_ms) +
			       ",\"error\":" + (error && error->HasError() ? JSONEscape(error->RawMessage()) : string("null")) +
			       ",\"n_scans\":" + to_string(scans.size()) + ",\"plans\":" + to_string(plan_count) +
			       ",\"plan_empty_results\":" + to_string(plan_empty_results) + ",\"plan_scan_tables\":[";
			for (idx_t i = 0; i < plan_scan_tables.size(); i++) {
				out += (i ? "," : "") + JSONEscape(plan_scan_tables[i]);
			}
			out += "],\"bound_tables\":[";
			for (idx_t i = 0; i < bound_tables.size(); i++) {
				out += (i ? "," : "") + JSONEscape(bound_tables[i]);
			}
			out += "],\"sql\":" + JSONEscape(sql) + "}\n";
			for (auto &scan : scans) {
				out += scan->ToJSON(seq, tag, writer.session);
			}
			Reset();
		}
		writer.Write(out);
	}

	void AddScan(shared_ptr<PruningScanStats> scan) {
		lock_guard<mutex> guard(lock);
		scan->scan_id = scans.size();
		scans.push_back(std::move(scan));
	}
};

shared_ptr<PruningQueryState> GetQueryState(ClientContext &context) {
	return context.registered_state->Get<PruningQueryState>("pruning_stats");
}

//===--------------------------------------------------------------------===//
// Filter helpers
//===--------------------------------------------------------------------===//
string FilterKind(const TableFilter &filter) {
	switch (filter.filter_type) {
	case TableFilterType::CONSTANT_COMPARISON:
		return "cmp" + ExpressionTypeToOperator(filter.Cast<ConstantFilter>().comparison_type);
	case TableFilterType::IS_NULL:
		return "is_null";
	case TableFilterType::IS_NOT_NULL:
		return "is_not_null";
	case TableFilterType::CONJUNCTION_OR:
		return "or";
	case TableFilterType::CONJUNCTION_AND:
		return "and";
	case TableFilterType::STRUCT_EXTRACT:
		return "struct(" + FilterKind(*filter.Cast<StructFilter>().child_filter) + ")";
	case TableFilterType::OPTIONAL_FILTER: {
		auto &child = filter.Cast<OptionalFilter>().child_filter;
		return "optional(" + (child ? FilterKind(*child) : string("none")) + ")";
	}
	case TableFilterType::IN_FILTER:
		return "in";
	case TableFilterType::DYNAMIC_FILTER:
		return "dynamic_topn";
	case TableFilterType::EXPRESSION_FILTER:
		return "expression";
	default:
		return "unknown";
	}
}

bool ContainsDynamic(const TableFilter &filter) {
	switch (filter.filter_type) {
	case TableFilterType::DYNAMIC_FILTER:
		return true;
	case TableFilterType::OPTIONAL_FILTER: {
		auto &child = filter.Cast<OptionalFilter>().child_filter;
		return child && ContainsDynamic(*child);
	}
	case TableFilterType::STRUCT_EXTRACT:
		return ContainsDynamic(*filter.Cast<StructFilter>().child_filter);
	case TableFilterType::CONJUNCTION_AND:
	case TableFilterType::CONJUNCTION_OR:
		for (auto &child : static_cast<const ConjunctionFilter &>(filter).child_filters) {
			if (ContainsDynamic(*child)) {
				return true;
			}
		}
		return false;
	default:
		return false;
	}
}

//! Readable rendering; "strip_wrappers" renders an optional filter as its child and a dynamic filter as its current
//! constant comparison (so that the result is executable SQL); returns "" for an uninitialized dynamic filter
string RenderFilter(const TableFilter &filter, const string &column, bool strip_wrappers) {
	switch (filter.filter_type) {
	case TableFilterType::DYNAMIC_FILTER: {
		auto &dynamic = filter.Cast<DynamicFilter>();
		if (!dynamic.filter_data) {
			return strip_wrappers ? "" : "topn(empty)";
		}
		lock_guard<mutex> l(dynamic.filter_data->lock);
		if (!dynamic.filter_data->initialized || !dynamic.filter_data->filter) {
			return strip_wrappers ? "" : "topn(uninitialized:" + column + ")";
		}
		auto inner = dynamic.filter_data->filter->ToString(column);
		return strip_wrappers ? inner : "topn:" + inner;
	}
	case TableFilterType::OPTIONAL_FILTER: {
		auto &child = filter.Cast<OptionalFilter>().child_filter;
		if (!child) {
			return strip_wrappers ? "" : "optional:none";
		}
		auto inner = RenderFilter(*child, column, strip_wrappers);
		return strip_wrappers ? inner : "optional:" + inner;
	}
	case TableFilterType::CONJUNCTION_AND:
	case TableFilterType::CONJUNCTION_OR: {
		auto &conj = static_cast<const ConjunctionFilter &>(filter);
		string sep = filter.filter_type == TableFilterType::CONJUNCTION_AND ? " AND " : " OR ";
		string result;
		for (idx_t i = 0; i < conj.child_filters.size(); i++) {
			auto child = RenderFilter(*conj.child_filters[i], column, strip_wrappers);
			if (child.empty()) {
				// an uninitialized dynamic filter inside a conjunction: true
				child = "true";
			}
			result += (i ? sep : "") + string("(") + child + ")";
		}
		return result;
	}
	default:
		return filter.ToString(column);
	}
}

void FlattenAnd(const TableFilter &filter, vector<reference<const TableFilter>> &result) {
	if (filter.filter_type == TableFilterType::CONJUNCTION_AND) {
		for (auto &child : filter.Cast<ConjunctionAndFilter>().child_filters) {
			FlattenAnd(*child, result);
		}
		return;
	}
	result.push_back(filter);
}

} // namespace

void PruningStats::RegisterClientContext(ClientContext &context) {
	if (!Enabled()) {
		return;
	}
	context.registered_state->GetOrCreate<PruningQueryState>("pruning_stats");
}

void PruningStats::OnBindTable(ClientContext &context, const string &table_name) {
	auto state = GetQueryState(context);
	if (!state) {
		return;
	}
	lock_guard<mutex> guard(state->lock);
	state->bound_tables.push_back(table_name);
}

static void WalkPlan(PruningQueryState &state, const PhysicalOperator &op) {
	if (op.type == PhysicalOperatorType::EMPTY_RESULT) {
		state.plan_empty_results++;
	} else if (op.type == PhysicalOperatorType::TABLE_SCAN) {
		auto &scan = op.Cast<PhysicalTableScan>();
		if (scan.bind_data && scan.function.name == "seq_scan") {
			auto &bind = scan.bind_data->Cast<TableScanBindData>();
			state.plan_scan_tables.push_back(bind.table.name);
		}
	}
	for (auto &child : op.GetChildren()) {
		WalkPlan(state, child.get());
	}
}

void PruningStats::OnPlan(ClientContext &context, const PhysicalOperator &plan) {
	auto state = GetQueryState(context);
	if (!state) {
		return;
	}
	lock_guard<mutex> guard(state->lock);
	state->plan_count++;
	WalkPlan(*state, plan);
}

//===--------------------------------------------------------------------===//
// PruningScanStats
//===--------------------------------------------------------------------===//
shared_ptr<PruningScanStats> PruningScanStats::Create(ClientContext &context, TableCatalogEntry &table,
                                                      RowGroupCollection &collection,
                                                      const vector<ColumnIndex> &column_indexes,
                                                      optional_ptr<TableFilterSet> filters,
                                                      optional_ptr<const PhysicalOperator> op) {
	auto query_state = GetQueryState(context);
	if (!query_state) {
		return nullptr;
	}
	auto result = make_shared_ptr<PruningScanStats>();
	result->table_name = table.name;
	result->total_rows = collection.GetTotalRows();
	auto last = collection.GetRowGroup(-1);
	result->total_row_groups = last ? last->index + 1 : 0;
	result->row_groups = unique_ptr<PruningRowGroupStat[]>(new PruningRowGroupStat[result->total_row_groups]);
	for (idx_t i = 0; i < result->total_row_groups; i++) {
		auto &rg = result->row_groups[i];
		rg.state = 0;
		rg.vectors_total = 0;
		rg.vectors_done = 0;
		rg.vectors_segment_skipped = 0;
		rg.rows_scanned = 0;
		rg.rows_passed = 0;
		rg.rows_passed_incl_optional = 0;
	}
	result->pruned_unattributed = 0;
	result->out_of_range_row_groups = 0;
	result->pruned_additional_no_single_leaf = 0;
	result->pruned_rowid_range = 0;
	result->pruned_rowid_only = 0;

	optional_ptr<TableFilterSet> static_filters;
	bool static_known = false;
	if (op && op->type == PhysicalOperatorType::TABLE_SCAN) {
		static_filters = op->Cast<PhysicalTableScan>().table_filters.get();
		static_known = true;
	}
	result->has_filters = filters && !filters->filters.empty();
	if (result->has_filters) {
		for (auto &entry : filters->filters) {
			auto scan_col = entry.first;
			string col_name = "#" + to_string(scan_col);
			string col_type = "?";
			if (scan_col < column_indexes.size()) {
				auto &col = column_indexes[scan_col];
				if (col.IsRowIdColumn()) {
					col_name = "rowid";
					col_type = "BIGINT";
				} else if (col.GetPrimaryIndex() < table.GetColumns().LogicalColumnCount()) {
					auto &def = table.GetColumn(LogicalIndex(col.GetPrimaryIndex()));
					col_name = def.Name();
					col_type = def.Type().ToString();
				}
			}
			// number of leading children of this column's filter that come from the static (plan-time) filter set;
			// GetFinalTableFilters copies the static filter first and ANDs the dynamic (join) filters after it
			idx_t static_count = 0;
			if (!static_filters) {
				// unknown operator: label everything static; a table scan without plan-time filters: every leaf
				// was appended at runtime (join filter pushdown). Before this fix such leaves were labelled static.
				static_count = static_known ? 0 : NumericLimits<idx_t>::Maximum();
			} else {
				auto s = static_filters->filters.find(scan_col);
				if (s != static_filters->filters.end()) {
					static_count = s->second->filter_type == TableFilterType::CONJUNCTION_AND
					                   ? s->second->Cast<ConjunctionAndFilter>().child_filters.size()
					                   : 1;
				}
			}
			vector<std::pair<reference<const TableFilter>, bool>> top_level;
			if (entry.second->filter_type == TableFilterType::CONJUNCTION_AND) {
				auto &children = entry.second->Cast<ConjunctionAndFilter>().child_filters;
				for (idx_t c = 0; c < children.size(); c++) {
					top_level.emplace_back(*children[c], c >= static_count);
				}
			} else {
				top_level.emplace_back(*entry.second, static_count == 0);
			}
			result->filter_columns.push_back(scan_col);
			result->filter_column_names.push_back(col_name);
			for (auto &top : top_level) {
				vector<reference<const TableFilter>> flat;
				FlattenAnd(top.first.get(), flat);
				for (auto &leaf_ref : flat) {
					auto &leaf_filter = leaf_ref.get();
					auto leaf = make_uniq<PruningLeafFilter>();
					leaf->scan_column_index = scan_col;
					leaf->column_name = col_name;
					leaf->column_type = col_type;
					leaf->kind = FilterKind(leaf_filter);
					bool topn = ContainsDynamic(leaf_filter);
					leaf->origin = top.second ? "join" : (topn ? "topn" : "static");
					leaf->applied_to_rows = leaf_filter.filter_type != TableFilterType::OPTIONAL_FILTER;
					leaf->filter = leaf_filter.Copy();
					leaf->pruned_first = 0;
					leaf->prunable_alone = 0;
					leaf->pruned_first_additional = 0;
					leaf->prunable_alone_additional = 0;
					if (!leaf->applied_to_rows) {
						result->has_optional = true;
						if (topn) {
							result->has_dynamic_optional = true;
						}
					}
					result->leaves.push_back(std::move(leaf));
				}
			}
		}
	}
	result->additional_first_by_column =
	    unique_ptr<atomic<idx_t>[]>(new atomic<idx_t>[result->filter_columns.size() + 1]);
	for (idx_t i = 0; i <= result->filter_columns.size(); i++) {
		result->additional_first_by_column[i] = 0;
	}
	query_state->AddScan(result);
	return result;
}

PruningRowGroupStat *PruningScanStats::GetRowGroup(RowGroup &row_group) {
	if (row_group.index >= total_row_groups) {
		out_of_range_row_groups++;
		return nullptr;
	}
	return &row_groups[row_group.index];
}

string PruningScanStats::ToJSON(idx_t seq, const string &tag, const string &session) const {
	idx_t pruned = 0, pruned_additional = 0, pruned_predcache = 0, entered = 0, not_reached = 0;
	idx_t no_rows = 0, no_rows_all_seg_skipped = 0, no_rows_some_seg_skipped = 0;
	idx_t with_rows = 0, partial_with_rows = 0, partial_no_rows = 0;
	idx_t opt_with_rows = 0, opt_no_rows = 0, opt_partial_no_rows = 0;
	idx_t rows_scanned = 0, rows_passed = 0, rows_passed_opt = 0, vectors_seg_skipped = 0, vectors_done = 0;
	for (idx_t i = 0; i < total_row_groups; i++) {
		auto &rg = row_groups[i];
		auto state = rg.state.load();
		if (state == 0) {
			not_reached++;
			continue;
		}
		if (state == 1 || state == 3 || state == 4) {
			pruned++;
			if (state == 3) {
				pruned_additional++;
			}
			if (state == 4) {
				pruned_predcache++;
			}
			continue;
		}
		entered++;
		idx_t done = rg.vectors_done + rg.vectors_segment_skipped;
		bool complete = done >= rg.vectors_total;
		rows_scanned += rg.rows_scanned;
		rows_passed += rg.rows_passed;
		rows_passed_opt += rg.rows_passed_incl_optional;
		vectors_seg_skipped += rg.vectors_segment_skipped;
		vectors_done += rg.vectors_done;
		if (rg.rows_passed > 0) {
			with_rows++;
			if (!complete) {
				partial_with_rows++;
			}
		} else if (complete) {
			no_rows++;
			if (rg.vectors_segment_skipped >= rg.vectors_total) {
				no_rows_all_seg_skipped++;
			} else if (rg.vectors_segment_skipped > 0) {
				no_rows_some_seg_skipped++;
			}
		} else {
			partial_no_rows++;
		}
		if (rg.rows_passed_incl_optional > 0) {
			opt_with_rows++;
		} else if (complete) {
			opt_no_rows++;
		} else {
			opt_partial_no_rows++;
		}
	}
	string out = "{\"type\":\"scan\",\"session\":" + JSONEscape(session) + ",\"seq\":" + to_string(seq) +
	             ",\"tag\":" + JSONEscape(tag) + ",\"scan_id\":" + to_string(scan_id) +
	             ",\"table\":" + JSONEscape(table_name) + ",\"total_rows\":" + to_string(total_rows) +
	             ",\"total_row_groups\":" + to_string(total_row_groups) + ",\"has_filters\":" + JSONBool(has_filters) +
	             ",\"has_optional\":" + JSONBool(has_optional) + ",\"pruned\":" + to_string(pruned) +
	             ",\"pruned_minmax\":" + to_string(pruned - pruned_additional - pruned_predcache) +
	             ",\"pruned_additional\":" + to_string(pruned_additional) +
	             ",\"pruned_predicate_cache\":" + to_string(pruned_predcache) +
	             (predcache_json.empty() ? string() : ",\"predicate_cache\":" + predcache_json) +
	             ",\"pruned_additional_no_single_leaf\":" + to_string(pruned_additional_no_single_leaf.load()) +
	             ",\"scanned\":" + to_string(entered) + ",\"scanned_no_rows\":" + to_string(no_rows) +
	             ",\"scanned_no_rows_all_segments_skipped\":" + to_string(no_rows_all_seg_skipped) +
	             ",\"scanned_no_rows_some_segments_skipped\":" + to_string(no_rows_some_seg_skipped) +
	             ",\"scanned_with_rows\":" + to_string(with_rows) +
	             ",\"scanned_with_rows_partial\":" + to_string(partial_with_rows) +
	             ",\"partial_no_rows\":" + to_string(partial_no_rows) + ",\"not_reached\":" + to_string(not_reached) +
	             ",\"incl_optional_with_rows\":" + to_string(opt_with_rows) +
	             ",\"incl_optional_no_rows\":" + to_string(opt_no_rows) +
	             ",\"incl_optional_partial_no_rows\":" + to_string(opt_partial_no_rows) +
	             ",\"rows_scanned\":" + to_string(rows_scanned) + ",\"rows_passed\":" + to_string(rows_passed) +
	             ",\"rows_passed_incl_optional\":" + to_string(rows_passed_opt) +
	             ",\"vectors_scanned\":" + to_string(vectors_done) +
	             ",\"vectors_segment_skipped\":" + to_string(vectors_seg_skipped) +
	             ",\"pruned_unattributed\":" + to_string(pruned_unattributed.load()) +
	             ",\"out_of_range_row_groups\":" + to_string(out_of_range_row_groups.load());
	if (RowGroup::RowIdSkipEnabled()) {
		// only with the row-id range check on, so that the output with it off is unchanged
		out += ",\"pruned_rowid_range\":" + to_string(pruned_rowid_range.load()) +
		       ",\"pruned_rowid_only\":" + to_string(pruned_rowid_only.load());
	}
	out += ",\"additional_columns\":[";
	for (idx_t i = 0; i < filter_columns.size(); i++) {
		out += string(i ? "," : "") + "{\"col\":" + JSONEscape(filter_column_names[i]) +
		       ",\"pruned_first\":" + to_string(additional_first_by_column[i].load()) + "}";
	}
	out += "],\"additional_columns_unattributed\":" + to_string(additional_first_by_column[filter_columns.size()].load()) +
	       ",\"filters\":[";
	for (idx_t i = 0; i < leaves.size(); i++) {
		auto &leaf = *leaves[i];
		auto sql = RenderFilter(*leaf.filter, KeywordHelper::WriteOptionallyQuoted(leaf.column_name), true);
		// for (optional) constant comparisons and IN lists also emit operator and constant(s) separately
		string cmp;
		const TableFilter *base = leaf.filter.get();
		if (base->filter_type == TableFilterType::OPTIONAL_FILTER && base->Cast<OptionalFilter>().child_filter) {
			base = base->Cast<OptionalFilter>().child_filter.get();
		}
		if (base->filter_type == TableFilterType::CONSTANT_COMPARISON) {
			auto &constant = base->Cast<ConstantFilter>();
			cmp = ",\"op\":" + JSONEscape(ExpressionTypeToOperator(constant.comparison_type)) +
			      ",\"value\":" + JSONEscape(constant.constant.ToSQLString());
		} else if (base->filter_type == TableFilterType::IN_FILTER) {
			auto &in_filter = base->Cast<InFilter>();
			cmp = ",\"op\":\"IN\",\"values\":[";
			for (idx_t v = 0; v < in_filter.values.size(); v++) {
				cmp += (v ? "," : "") + JSONEscape(in_filter.values[v].ToSQLString());
			}
			cmp += "]";
		}
		out += string(i ? "," : "") + "{\"col\":" + JSONEscape(leaf.column_name) + cmp +
		       ",\"col_type\":" + JSONEscape(leaf.column_type) + ",\"kind\":" + JSONEscape(leaf.kind) +
		       ",\"origin\":" + JSONEscape(leaf.origin) + ",\"dynamic\":" + JSONBool(leaf.origin != "static") +
		       ",\"applied_to_rows\":" + JSONBool(leaf.applied_to_rows) +
		       ",\"filter\":" + JSONEscape(RenderFilter(*leaf.filter, leaf.column_name, false)) +
		       ",\"sql\":" + (sql.empty() ? string("null") : JSONEscape(sql)) +
		       ",\"pruned_first\":" + to_string(leaf.pruned_first.load()) +
		       ",\"prunable_alone\":" + to_string(leaf.prunable_alone.load()) +
		       ",\"pruned_first_additional\":" + to_string(leaf.pruned_first_additional.load()) +
		       ",\"prunable_alone_additional\":" + to_string(leaf.prunable_alone_additional.load()) + "}";
	}
	out += "]}\n";
	return out;
}

//===--------------------------------------------------------------------===//
// PruningScanLocal
//===--------------------------------------------------------------------===//
PruningScanLocal::PruningScanLocal(ClientContext &context_p, shared_ptr<PruningScanStats> stats_p)
    : context(context_p), stats(std::move(stats_p)), optional_sel(STANDARD_VECTOR_SIZE) {
}

PruningScanLocal::~PruningScanLocal() {
}

void PruningScanLocal::OnPruned(RowGroup &row_group, ScanFilterInfo &filters, bool by_additional) {
	auto rg = stats->GetRowGroup(row_group);
	if (!rg) {
		return;
	}
	uint8_t expected = 0;
	if (!rg->state.compare_exchange_strong(expected, by_additional ? 3 : 1)) {
		// already accounted for (e.g. several tasks for one row group with verify_parallelism)
		return;
	}
	// map scan column index -> storage column index
	auto &filter_list = filters.GetFilterList();
	if (by_additional) {
		// the selective statistic of a column of this row group (nullptr if none); a lambda has friend access
		auto GetSelectiveStat = [](RowGroup &rg_ref, idx_t table_column) -> const SelectiveStat * {
			auto &column = rg_ref.GetColumn(table_column);
			if (!column.selective) {
				return nullptr;
			}
			return column.selective->stat.load();
		};
		// min/max could not prune: attribute to the selective statistics (per column, and per single leaf)
		bool column_attributed = false;
		for (auto &entry : filter_list) {
			auto stat = GetSelectiveStat(row_group, entry.table_column_index);
			if (!stat || !SelectiveStats::FilterCanPrune(entry.filter, *stat)) {
				continue;
			}
			for (idx_t c = 0; c < stats->filter_columns.size(); c++) {
				if (stats->filter_columns[c] == entry.scan_column_index) {
					stats->additional_first_by_column[c]++;
					column_attributed = true;
					break;
				}
			}
			break;
		}
		if (!column_attributed) {
			// e.g. a dynamic filter changed in between: count under the extra slot
			stats->additional_first_by_column[stats->filter_columns.size()]++;
		}
		bool leaf_attributed = false;
		for (auto &leaf_ptr : stats->leaves) {
			auto &leaf = *leaf_ptr;
			const SelectiveStat *stat = nullptr;
			for (auto &entry : filter_list) {
				if (entry.scan_column_index == leaf.scan_column_index) {
					stat = GetSelectiveStat(row_group, entry.table_column_index);
					break;
				}
			}
			if (!stat || !SelectiveStats::FilterCanPrune(*leaf.filter, *stat)) {
				continue;
			}
			leaf.prunable_alone_additional++;
			if (!leaf_attributed) {
				leaf.pruned_first_additional++;
				leaf_attributed = true;
			}
		}
		if (!leaf_attributed) {
			stats->pruned_additional_no_single_leaf++;
		}
		return;
	}
	bool attributed = false;
	bool rowid_prunes = false;
	bool other_prunes = false;
	for (auto &leaf_ptr : stats->leaves) {
		auto &leaf = *leaf_ptr;
		// note: the rowid column's table index COLUMN_IDENTIFIER_ROW_ID equals INVALID_INDEX, so no optional_idx here
		bool found = false;
		storage_t table_column = 0;
		for (auto &entry : filter_list) {
			if (entry.scan_column_index == leaf.scan_column_index) {
				table_column = entry.table_column_index;
				found = true;
				break;
			}
		}
		if (!found) {
			continue;
		}
		auto result = row_group.CheckColumnZonemap(table_column, *leaf.filter);
		if (result == FilterPropagateResult::FILTER_ALWAYS_FALSE) {
			bool is_rowid = table_column == COLUMN_IDENTIFIER_ROW_ID;
			if (is_rowid) {
				rowid_prunes = true;
			} else {
				other_prunes = true;
			}
			leaf.prunable_alone++;
			if (!attributed) {
				leaf.pruned_first++;
				attributed = true;
				if (is_rowid) {
					stats->pruned_rowid_range++;
				}
			}
		}
	}
	if (rowid_prunes && !other_prunes) {
		stats->pruned_rowid_only++;
	}
	if (!attributed) {
		stats->pruned_unattributed++;
	}
}

void PruningScanLocal::OnPrunedPredicateCache(RowGroup &row_group) {
	auto rg = stats->GetRowGroup(row_group);
	if (!rg) {
		return;
	}
	uint8_t expected = 0;
	rg->state.compare_exchange_strong(expected, 4);
}

void PruningScanLocal::OnEnter(RowGroup &row_group, idx_t max_row_group_row) {
	auto rg = stats->GetRowGroup(row_group);
	if (!rg) {
		return;
	}
	uint8_t expected = 0;
	rg->state.compare_exchange_strong(expected, 2);
	auto vectors = static_cast<uint32_t>((max_row_group_row + STANDARD_VECTOR_SIZE - 1) / STANDARD_VECTOR_SIZE);
	auto current = rg->vectors_total.load();
	while (current < vectors && !rg->vectors_total.compare_exchange_weak(current, vectors)) {
	}
}

void PruningScanLocal::OnSegmentSkip(RowGroup &row_group, idx_t vectors) {
	auto rg = stats->GetRowGroup(row_group);
	if (!rg) {
		return;
	}
	rg->vectors_segment_skipped += static_cast<uint32_t>(vectors);
}

void PruningScanLocal::OnVector(RowGroup &row_group, idx_t rows_scanned, idx_t rows_passed,
                                idx_t rows_passed_incl_optional) {
	auto rg = stats->GetRowGroup(row_group);
	if (!rg) {
		return;
	}
	rg->vectors_done++;
	rg->rows_scanned += rows_scanned;
	rg->rows_passed += rows_passed;
	rg->rows_passed_incl_optional += rows_passed_incl_optional;
}

void PruningScanLocal::BuildOptionalExecutor(DataChunk &result) {
	optional_columns.clear();
	vector<LogicalType> types;
	unique_ptr<Expression> conjunction;
	for (auto &leaf_ptr : stats->leaves) {
		auto &leaf = *leaf_ptr;
		if (leaf.applied_to_rows) {
			continue;
		}
		auto &optional = leaf.filter->Cast<OptionalFilter>();
		if (!optional.child_filter) {
			continue;
		}
		idx_t chunk_index = optional_columns.size();
		auto &type = result.data[leaf.scan_column_index].GetType();
		optional_columns.push_back(leaf.scan_column_index);
		types.push_back(type);
		BoundReferenceExpression column_ref(leaf.column_name, type, chunk_index);
		auto expr = optional.child_filter->ToExpression(column_ref);
		if (!conjunction) {
			conjunction = std::move(expr);
		} else {
			conjunction = make_uniq<BoundConjunctionExpression>(ExpressionType::CONJUNCTION_AND,
			                                                    std::move(conjunction), std::move(expr));
		}
	}
	optional_expr = std::move(conjunction);
	optional_executor.reset();
	optional_chunk.Destroy();
	if (optional_expr) {
		optional_executor = make_uniq<ExpressionExecutor>(context, *optional_expr);
		optional_chunk.InitializeEmpty(types);
	}
}

idx_t PruningScanLocal::CountOptional(RowGroup &row_group, DataChunk &result, idx_t count) {
	if (!stats->has_optional || count == 0) {
		return count;
	}
	if (!optional_executor || (stats->has_dynamic_optional && optional_row_group != row_group.index)) {
		// top-N filters change during execution: rebuild the expression once per row group
		BuildOptionalExecutor(result);
		optional_row_group = row_group.index;
	}
	if (!optional_executor) {
		return count;
	}
	optional_chunk.Reset();
	for (idx_t i = 0; i < optional_columns.size(); i++) {
		optional_chunk.data[i].Reference(result.data[optional_columns[i]]);
	}
	optional_chunk.SetCardinality(count);
	return optional_executor->SelectExpression(optional_chunk, optional_sel);
}

} // namespace duckdb
