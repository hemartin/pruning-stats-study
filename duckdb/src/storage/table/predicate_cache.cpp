#include "duckdb/storage/table/predicate_cache.hpp"

#include "duckdb/common/exception.hpp"
#include "duckdb/common/string_util.hpp"
#include "duckdb/common/serializer/binary_serializer.hpp"
#include "duckdb/common/serializer/memory_stream.hpp"
#include "duckdb/execution/operator/scan/physical_table_scan.hpp"
#include "duckdb/execution/physical_operator.hpp"
#include "duckdb/planner/filter/conjunction_filter.hpp"
#include "duckdb/planner/filter/optional_filter.hpp"
#include "duckdb/planner/filter/struct_filter.hpp"
#include "duckdb/planner/table_filter.hpp"
#include "duckdb/storage/table/column_data.hpp"
#include "duckdb/storage/table/row_group.hpp"
#include "duckdb/storage/table/row_group_collection.hpp"
#include "duckdb/storage/table/selective_stats.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace duckdb {

namespace {

PredicateCacheMode PCReadMode() {
	auto env = std::getenv("PRUNING_PREDICATE_CACHE");
	if (!env || !*env) {
		return PredicateCacheMode::OFF;
	}
	string v = StringUtil::Lower(env);
	if (v == "0" || v == "off" || v == "false" || v == "no") {
		return PredicateCacheMode::OFF;
	}
	if (v == "2" || v == "subset") {
		return PredicateCacheMode::SUBSET;
	}
	return PredicateCacheMode::EXACT;
}

string PCEscape(const string &input) {
	string out = "\"";
	for (auto c : input) {
		switch (c) {
		case '"':
			out += "\\\"";
			break;
		case '\\':
			out += "\\\\";
			break;
		case '\n':
			out += "\\n";
			break;
		case '\r':
			out += "\\r";
			break;
		case '\t':
			out += "\\t";
			break;
		default:
			if (static_cast<unsigned char>(c) < 0x20) {
				char buf[8];
				snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned char>(c));
				out += buf;
			} else {
				out += c;
			}
		}
	}
	return out + "\"";
}

//! true if an OptionalFilter or a DynamicFilter occurs anywhere inside the filter
bool PCContainsOptionalOrDynamic(const TableFilter &filter) {
	switch (filter.filter_type) {
	case TableFilterType::OPTIONAL_FILTER:
	case TableFilterType::DYNAMIC_FILTER:
		return true;
	case TableFilterType::STRUCT_EXTRACT:
		return PCContainsOptionalOrDynamic(*filter.Cast<StructFilter>().child_filter);
	case TableFilterType::CONJUNCTION_AND:
	case TableFilterType::CONJUNCTION_OR:
		for (auto &child : static_cast<const ConjunctionFilter &>(filter).child_filters) {
			if (PCContainsOptionalOrDynamic(*child)) {
				return true;
			}
		}
		return false;
	default:
		return false;
	}
}

void PCFlattenAnd(const TableFilter &filter, vector<reference<const TableFilter>> &result) {
	if (filter.filter_type == TableFilterType::CONJUNCTION_AND) {
		for (auto &child : filter.Cast<ConjunctionAndFilter>().child_filters) {
			PCFlattenAnd(*child, result);
		}
		return;
	}
	result.push_back(filter);
}

string PCColumnKey(const StorageIndex &index) {
	string result = to_string(index.GetPrimaryIndex());
	for (auto &child : index.GetChildIndexes()) {
		result += "." + PCColumnKey(child);
	}
	return result;
}

struct PCLeaf {
	string key;
	string readable;
};

//! Canonical leaves of a filter set: (storage column, serialized non-optional leaf). Optional leaves are skipped and
//! reported via has_optional. Returns false (with a reason) if the set cannot be cached.
bool PCCanonicalLeaves(const TableFilterSet &filters, const vector<StorageIndex> &storage_ids, idx_t column_count,
                     vector<PCLeaf> &leaves, bool &has_optional, string &reason,
                     vector<std::pair<StorageIndex, unique_ptr<TableFilter>>> *per_column) {
	for (auto &entry : filters.filters) {
		auto scan_col = entry.first;
		if (scan_col >= storage_ids.size()) {
			reason = "unknown_column";
			return false;
		}
		auto &storage = storage_ids[scan_col];
		if (storage.IsRowIdColumn() || storage.GetPrimaryIndex() >= column_count) {
			reason = "rowid_or_virtual_column";
			return false;
		}
		vector<reference<const TableFilter>> flat;
		PCFlattenAnd(*entry.second, flat);
		vector<unique_ptr<TableFilter>> kept;
		for (auto &leaf_ref : flat) {
			auto &leaf = leaf_ref.get();
			if (leaf.filter_type == TableFilterType::OPTIONAL_FILTER) {
				has_optional = true;
				continue;
			}
			if (PCContainsOptionalOrDynamic(leaf)) {
				reason = "nested_optional_or_dynamic";
				return false;
			}
			MemoryStream stream;
			try {
				BinarySerializer::Serialize(leaf, stream);
			} catch (std::exception &) {
				reason = "not_serializable";
				return false;
			}
			auto col = PCColumnKey(storage);
			PCLeaf l;
			l.key = col + ":" + string(const_char_ptr_cast(stream.GetData()), stream.GetPosition());
			l.key = to_string(l.key.size()) + "#" + l.key;
			l.readable = leaf.ToString("#" + col);
			leaves.push_back(std::move(l));
			if (per_column) {
				kept.push_back(leaf.Copy());
			}
		}
		if (per_column && !kept.empty()) {
			unique_ptr<TableFilter> filter;
			if (kept.size() == 1) {
				filter = std::move(kept[0]);
			} else {
				auto conj = make_uniq<ConjunctionAndFilter>();
				conj->child_filters = std::move(kept);
				filter = std::move(conj);
			}
			per_column->emplace_back(storage, std::move(filter));
		}
	}
	std::sort(leaves.begin(), leaves.end(), [](const PCLeaf &a, const PCLeaf &b) { return a.key < b.key; });
	// duplicates are harmless for a conjunction: remove them so that the key is canonical
	leaves.erase(std::unique(leaves.begin(), leaves.end(), [](const PCLeaf &a, const PCLeaf &b) { return a.key == b.key; }),
	             leaves.end());
	return true;
}

} // namespace

//===--------------------------------------------------------------------===//
// PredicateCache
//===--------------------------------------------------------------------===//
PredicateCacheMode PredicateCache::Mode() {
	static const PredicateCacheMode mode = PCReadMode();
	return mode;
}

//===--------------------------------------------------------------------===//
// PredicateCacheTable
//===--------------------------------------------------------------------===//
PredicateCacheTable::~PredicateCacheTable() {
}

void PredicateCacheTable::OnWrite() {
	lock_guard<mutex> guard(lock);
	epoch++;
	entries.clear();
}

//===--------------------------------------------------------------------===//
// PredicateCacheScan
//===--------------------------------------------------------------------===//
shared_ptr<PredicateCacheScan> PredicateCacheScan::Create(ClientContext &context, RowGroupCollection &collection,
                                                          const vector<StorageIndex> &storage_ids,
                                                          optional_ptr<TableFilterSet> filters,
                                                          optional_ptr<const PhysicalOperator> op, bool sampling,
                                                          string &info_json) {
	auto uncacheable = [&](const string &reason) -> shared_ptr<PredicateCacheScan> {
		info_json = "{\"cacheable\":false,\"reason\":" + PCEscape(reason) + "}";
		return nullptr;
	};
	auto table = collection.predicate_cache;
	if (!table) {
		return uncacheable("no_table_cache");
	}
	if (sampling) {
		return uncacheable("sampling");
	}
	if (!op || op->type != PhysicalOperatorType::TABLE_SCAN) {
		return uncacheable("unknown_operator");
	}
	auto static_set = op->Cast<PhysicalTableScan>().table_filters.get();
	if (!static_set || static_set->filters.empty()) {
		return uncacheable("no_static_filters");
	}
	auto column_count = collection.GetTypes().size();
	auto result = shared_ptr<PredicateCacheScan>(new PredicateCacheScan());
	vector<PCLeaf> leaves;
	bool static_optional = false;
	string reason;
	if (!PCCanonicalLeaves(*static_set, storage_ids, column_count, leaves, static_optional, reason,
	                     &result->static_filters)) {
		return uncacheable(reason);
	}
	if (leaves.empty()) {
		return uncacheable("only_optional_static_filters");
	}
	// the filters the scan applies (static + dynamic join filters merged at runtime)
	vector<PCLeaf> applied;
	bool applied_optional = false;
	string applied_reason;
	bool applied_ok = !filters || PCCanonicalLeaves(*filters, storage_ids, column_count, applied, applied_optional,
	                                              applied_reason, nullptr);
	if (!applied_ok) {
		// e.g. a dynamic filter on rowid (late materialization) or nested dynamic filters: the static leaves are
		// still a superset condition for "has rows", but a pruned / empty row group is never recorded
		applied.clear();
		applied_optional = true;
	}
	result->exact_applied = applied_ok && filters && applied.size() == leaves.size();
	if (result->exact_applied) {
		for (idx_t i = 0; i < leaves.size(); i++) {
			if (applied[i].key != leaves[i].key) {
				result->exact_applied = false;
				break;
			}
		}
	}
	result->needs_recheck = static_optional || applied_optional || !result->exact_applied;
	for (auto &l : leaves) {
		result->key += l.key;
		result->readable += (result->readable.empty() ? "" : " AND ") + l.readable;
		result->leaves.push_back(l.key);
	}
	result->table = table;
	auto last = collection.GetRowGroup(-1);
	result->n_row_groups = last ? last->index + 1 : 0;
	idx_t words = (result->n_row_groups + 63) / 64;
	result->known_empty = unique_ptr<uint64_t[]>(new uint64_t[MaxValue<idx_t>(words, 1)]);
	memset(result->known_empty.get(), 0, sizeof(uint64_t) * MaxValue<idx_t>(words, 1));
	result->row_groups = unique_ptr<RowGroupState[]>(new RowGroupState[MaxValue<idx_t>(result->n_row_groups, 1)]);
	for (idx_t i = 0; i < result->n_row_groups; i++) {
		auto &rg = result->row_groups[i];
		rg.state = 0;
		rg.vectors_total = 0;
		rg.vectors_done = 0;
		rg.any_rows = false;
		rg.not_all_visible = false;
		rg.count_at_enter = 0;
	}
	{
		lock_guard<mutex> guard(table->lock);
		result->epoch = table->epoch.load();
		auto use = [&](const PredicateCacheEntry &entry) {
			if (entry.epoch != result->epoch) {
				return;
			}
			result->entries_used++;
			idx_t n = MinValue<idx_t>(words, entry.known.size());
			for (idx_t w = 0; w < n; w++) {
				result->known_empty[w] |= entry.known[w] & ~entry.has_rows[w];
			}
		};
		if (PredicateCache::Mode() == PredicateCacheMode::SUBSET) {
			for (auto &e : table->entries) {
				auto &entry = *e.second;
				if (std::includes(result->leaves.begin(), result->leaves.end(), entry.leaves.begin(),
				                  entry.leaves.end())) {
					use(entry);
				}
			}
		} else {
			auto e = table->entries.find(result->key);
			if (e != table->entries.end()) {
				use(*e->second);
			}
		}
	}
	for (idx_t w = 0; w < words; w++) {
		result->known_empty_at_start += static_cast<idx_t>(__builtin_popcountll(result->known_empty[w]));
	}
	info_json = result->InfoJSON();
	return result;
}

string PredicateCacheScan::InfoJSON() const {
	return "{\"cacheable\":true,\"key\":" + PCEscape(readable) + ",\"leaves\":" + to_string(leaves.size()) +
	       ",\"exact_applied\":" + (exact_applied ? "true" : "false") +
	       ",\"needs_recheck\":" + (needs_recheck ? "true" : "false") +
	       ",\"entries_used\":" + to_string(entries_used) +
	       ",\"known_empty_at_start\":" + to_string(known_empty_at_start) + "}";
}

PredicateCacheScan::~PredicateCacheScan() {
	try {
		Finish();
	} catch (...) { // NOLINT
	}
}

bool PredicateCacheScan::StaticFiltersPrune(RowGroup &row_group) {
	for (auto &entry : static_filters) {
		auto &column = row_group.GetColumn(entry.first.GetPrimaryIndex());
		if (column.CheckZonemap(*entry.second) == FilterPropagateResult::FILTER_ALWAYS_FALSE) {
			return true;
		}
	}
	for (auto &entry : static_filters) {
		auto &column = row_group.GetColumn(entry.first.GetPrimaryIndex());
		if (!column.selective) {
			continue;
		}
		auto stat = column.selective->stat.load(std::memory_order_acquire);
		if (stat && SelectiveStats::FilterCanPrune(*entry.second, *stat)) {
			return true;
		}
	}
	return false;
}

void PredicateCacheScan::OnPruned(RowGroup &row_group, uint8_t cause) {
	if (row_group.index >= n_row_groups) {
		return;
	}
	auto &rg = row_groups[row_group.index];
	uint8_t new_state;
	if (cause == 4) {
		new_state = 4;
	} else if (!needs_recheck) {
		// the scan's filters are exactly the static non-optional filters: their zonemap / statistic pruned it
		new_state = 1;
	} else {
		new_state = StaticFiltersPrune(row_group) ? 1 : 5;
	}
	uint8_t expected = 0;
	rg.state.compare_exchange_strong(expected, new_state);
}

void PredicateCacheScan::OnEnter(RowGroup &row_group, idx_t max_row_group_row) {
	if (row_group.index >= n_row_groups) {
		return;
	}
	auto &rg = row_groups[row_group.index];
	uint8_t expected = 0;
	rg.state.compare_exchange_strong(expected, 2);
	auto vectors = static_cast<uint32_t>((max_row_group_row + STANDARD_VECTOR_SIZE - 1) / STANDARD_VECTOR_SIZE);
	auto current = rg.vectors_total.load();
	while (current < vectors && !rg.vectors_total.compare_exchange_weak(current, vectors)) {
	}
	if (max_row_group_row != row_group.count) {
		// the scan does not cover the whole row group (rows appended after the scan started)
		rg.not_all_visible = true;
	}
	rg.count_at_enter = row_group.count.load();
	// "no rows" must not rest on values with pending update information (they may differ between transactions or be
	// rolled back); any update / delete / append also clears the whole table cache via the epoch
	for (auto &entry : static_filters) {
		if (row_group.GetColumn(entry.first.GetPrimaryIndex()).HasUpdates()) {
			rg.not_all_visible = true;
			break;
		}
	}
}

void PredicateCacheScan::OnSegmentSkip(RowGroup &row_group, idx_t vectors) {
	if (row_group.index >= n_row_groups) {
		return;
	}
	auto &rg = row_groups[row_group.index];
	rg.vectors_done += static_cast<uint32_t>(vectors);
	if (needs_recheck) {
		// segment-level zonemap skips use the scan's complete filters, including optional ones (e.g. a top-N
		// threshold inside an AND with the static filter of the same column) and dynamic join filters: the skipped
		// vectors may contain rows that pass the static conjunction -> the row group cannot be recorded as empty
		rg.not_all_visible = true;
	}
}

void PredicateCacheScan::OnVector(RowGroup &row_group, idx_t rows_passed, bool all_visible) {
	if (row_group.index >= n_row_groups) {
		return;
	}
	auto &rg = row_groups[row_group.index];
	rg.vectors_done++;
	if (rows_passed > 0) {
		rg.any_rows = true;
	}
	if (!all_visible) {
		rg.not_all_visible = true;
	}
}

void PredicateCacheScan::Finish() {
	if (!table || n_row_groups == 0) {
		return;
	}
	idx_t words = (n_row_groups + 63) / 64;
	vector<uint64_t> known(words, 0), has_rows(words, 0);
	idx_t n_empty = 0, n_rows = 0;
	for (idx_t i = 0; i < n_row_groups; i++) {
		auto &rg = row_groups[i];
		auto state = rg.state.load();
		bool k = false, h = false;
		if (state == 1 || state == 4) {
			k = true;
		} else if (state == 2) {
			if (rg.any_rows) {
				// >= 1 row passed static AND dynamic filters -> >= 1 row passes the static conjunction
				k = h = true;
			} else if (exact_applied && !rg.not_all_visible && rg.vectors_total > 0 &&
			           rg.vectors_done >= rg.vectors_total) {
				k = true;
			}
		}
		if (!k) {
			continue;
		}
		known[i / 64] |= 1ULL << (i % 64);
		if (h) {
			has_rows[i / 64] |= 1ULL << (i % 64);
			n_rows++;
		} else {
			n_empty++;
		}
	}
	if (n_empty == 0 && n_rows == 0) {
		return;
	}
	lock_guard<mutex> guard(table->lock);
	if (table->epoch.load() != epoch) {
		return;
	}
	auto &slot = table->entries[key];
	if (!slot) {
		slot = make_uniq<PredicateCacheEntry>();
		slot->key = key;
		slot->readable = readable;
		slot->leaves = leaves;
		slot->epoch = epoch;
	}
	auto &entry = *slot;
	if (entry.epoch != epoch) {
		entry.known.clear();
		entry.has_rows.clear();
		entry.epoch = epoch;
	}
	if (entry.known.size() < words) {
		entry.known.resize(words, 0);
		entry.has_rows.resize(words, 0);
	}
	for (idx_t w = 0; w < words; w++) {
		uint64_t both = entry.known[w] & known[w];
		uint64_t conflict = both & (entry.has_rows[w] ^ has_rows[w]);
		if (conflict) {
			// keep "has rows" (the safe direction)
			has_rows[w] |= conflict;
		}
		entry.known[w] |= known[w];
		entry.has_rows[w] |= has_rows[w];
	}
}

} // namespace duckdb
