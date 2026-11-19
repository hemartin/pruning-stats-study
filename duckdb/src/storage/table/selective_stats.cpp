#include "duckdb/storage/table/selective_stats.hpp"

#include "duckdb/common/error_data.hpp"
#include "duckdb/common/types/hash.hpp"
#include "duckdb/common/types/value.hpp"
#include "duckdb/common/types/vector.hpp"
#include "duckdb/common/string_util.hpp"
#include "duckdb/main/client_config.hpp"
#include "duckdb/main/client_context.hpp"
#include "duckdb/main/client_context_state.hpp"
#include "duckdb/parser/column_definition.hpp"
#include "duckdb/planner/filter/conjunction_filter.hpp"
#include "duckdb/planner/filter/constant_filter.hpp"
#include "duckdb/planner/expression/bound_conjunction_expression.hpp"
#include "duckdb/planner/expression/bound_constant_expression.hpp"
#include "duckdb/planner/expression/bound_function_expression.hpp"
#include "duckdb/planner/expression/bound_reference_expression.hpp"
#include "duckdb/planner/filter/dynamic_filter.hpp"
#include "duckdb/planner/filter/expression_filter.hpp"
#include "duckdb/planner/filter/in_filter.hpp"
#include "duckdb/planner/filter/optional_filter.hpp"
#include "duckdb/planner/table_filter.hpp"
#include "duckdb/storage/statistics/additional/pruning_codec.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>

namespace duckdb {

namespace selective_impl {

using pruning_codec::BitReader;
using pruning_codec::BitWriter;
using pruning_codec::NullspaceCodec;
using pruning_codec::OccupancyCodec;

//! Stream layout (as on branch near-optimal-pruning-stats): 2 bits of kind, then the codec stream
static constexpr uint64_t KIND_BITS = 2;
static constexpr uint64_t STREAM_OCCUPANCY = 1;
static constexpr uint64_t STREAM_NULLSPACE = 2;
//! NGRAM only: the row group has no n-gram at all (all values NULL or shorter than n)
static constexpr uint64_t STREAM_EMPTY = 3;
//! NGRAM: no statistic is stored if the expected false-positive rate per absent n-gram is at least this
static constexpr double NGRAM_USELESS_EPS = 0.99;
//! NGRAM: at most this many distinct n-grams are buffered per row group (n > 3); more = no statistic
static constexpr idx_t NGRAM_MAX_DISTINCT = idx_t(1) << 22;
static constexpr uint64_t HASH_SEED = 0x2545F4914F6CDD1DULL;

static inline uint64_t NowNs() {
	return (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(
	           std::chrono::steady_clock::now().time_since_epoch())
	    .count();
}

static inline uint64_t MixHash(uint64_t key) {
	return pruning_codec::Mix64(key ^ HASH_SEED);
}

//===--------------------------------------------------------------------===//
// Bloom filter (kind BLOOM)
//===--------------------------------------------------------------------===//
// Port of the DBTest 2026 paper's Bloom filter (statistics/additional/bloom_additional_stats.hpp, scale level 1 =
// 100x): K = 1 hash function, one block (BLOCK_COUNT = 1) of `words` 64-bit words, hash = the first 64 bits of
// MurmurHash3_x64_128 (seed 1) over the 8 bytes of std::hash(value), bit = (h1 + h2) mod (64 * words) in 32-bit
// arithmetic, with h1/h2 the low/high halves of the hash. For integer columns the hash input is exactly the paper's
// (std::hash of an integer is the integer, sign-extended to 64 bits): the point key with the sign bit flip undone.
static inline uint64_t BloomInput(uint64_t point_key, PhysicalType ptype) {
	switch (ptype) {
	case PhysicalType::INT8:
	case PhysicalType::INT16:
	case PhysicalType::INT32:
	case PhysicalType::INT64:
		return point_key ^ (1ULL << 63); // undo SignedKey
	default:
		return point_key;
	}
}

static inline uint64_t BloomRotl64(uint64_t x, int8_t r) {
	return (x << r) | (x >> (64 - r));
}

static inline uint64_t BloomFmix64(uint64_t k) {
	k ^= k >> 33;
	k *= 0xff51afd7ed558ccdULL;
	k ^= k >> 33;
	k *= 0xc4ceb9fe1a85ec53ULL;
	k ^= k >> 33;
	return k;
}

//! MurmurHash3_x64_128 of an 8-byte little-endian input with seed 1, first 64 bits (as in the paper's BloomUtil)
static inline uint64_t BloomHash(uint64_t input) {
	const uint64_t c1 = 0x87c37b91114253d5ULL;
	const uint64_t c2 = 0x4cf5ad432745937fULL;
	uint64_t h1 = 1;
	uint64_t h2 = 1;
	// len = 8: no 16-byte block, the tail is k1 = the 8 input bytes
	uint64_t k1 = input;
	k1 *= c1;
	k1 = BloomRotl64(k1, 31);
	k1 *= c2;
	h1 ^= k1;
	// finalization
	h1 ^= 8;
	h2 ^= 8;
	h1 += h2;
	h2 += h1;
	h1 = BloomFmix64(h1);
	h2 = BloomFmix64(h2);
	h1 += h2;
	return h1;
}

static inline uint32_t BloomBit(uint64_t point_key, PhysicalType ptype, idx_t words) {
	auto h = BloomHash(BloomInput(point_key, ptype));
	uint32_t h1 = (uint32_t)(h & 0xFFFFFFFFULL);
	uint32_t h2 = (uint32_t)(h >> 32);
	return (uint32_t)(h1 + 1u * h2) % (uint32_t)(64 * words);
}

//===--------------------------------------------------------------------===//
// Keys
//===--------------------------------------------------------------------===//
// Ordered key: monotone non-decreasing map of the column's values (in DuckDB's comparison order) to uint64_t;
// strictly monotone ("exact", so that x > c <=> key(x) >= key(c) + 1) for integers and booleans.
// Point key: the key used for equality; equal values have equal point keys (collisions only cause false positives).
// For occupancy the point key is the ordered key; for nullspace it is the ordered key for types up to 64 bits and
// a hash for 128-bit integers and strings.
static inline uint64_t SignedKey(int64_t v) {
	return (uint64_t)v ^ (1ULL << 63);
}
static inline uint64_t DoubleKey(double value) {
	if (value != value) {
		return ~0ULL; // NaN sorts last (DuckDB: NaN is the largest value, NaN = NaN)
	}
	double normalised = value == 0 ? 0.0 : value; // -0.0 == 0.0
	uint64_t bits;
	memcpy(&bits, &normalised, sizeof(bits));
	return (bits >> 63) ? ~bits : bits | (1ULL << 63);
}
static inline uint64_t HugeintKey(hugeint_t v) {
	// saturating: monotone non-decreasing, exact within the int64 range
	if (v.upper == 0 && (int64_t)v.lower >= 0) {
		return SignedKey((int64_t)v.lower);
	}
	if (v.upper == -1 && (int64_t)v.lower < 0) {
		return SignedKey((int64_t)v.lower);
	}
	return v.upper < 0 ? 0 : ~0ULL;
}
static inline uint64_t UhugeintKey(uhugeint_t v) {
	return v.upper == 0 ? v.lower : ~0ULL;
}
static inline uint64_t StringPrefixKey(const char *data, idx_t size) {
	// big-endian 8-byte prefix, zero padded: monotone non-decreasing under DuckDB's byte-wise string comparison
	uint64_t key = 0;
	for (idx_t i = 0; i < 8; i++) {
		key <<= 8;
		if (i < size) {
			key |= (uint8_t)data[i];
		}
	}
	return key;
}

template <class T>
struct KeyOf {};
#define SELECTIVE_SIGNED(T)                                                                                            \
	template <>                                                                                                        \
	struct KeyOf<T> {                                                                                                  \
		static inline uint64_t Order(const T &v) {                                                                     \
			return SignedKey((int64_t)v);                                                                              \
		}                                                                                                              \
		static inline uint64_t Point(const T &v) {                                                                     \
			return Order(v);                                                                                           \
		}                                                                                                              \
	};
#define SELECTIVE_UNSIGNED(T)                                                                                          \
	template <>                                                                                                        \
	struct KeyOf<T> {                                                                                                  \
		static inline uint64_t Order(const T &v) {                                                                     \
			return (uint64_t)v;                                                                                        \
		}                                                                                                              \
		static inline uint64_t Point(const T &v) {                                                                     \
			return Order(v);                                                                                           \
		}                                                                                                              \
	};
SELECTIVE_SIGNED(int8_t)
SELECTIVE_SIGNED(int16_t)
SELECTIVE_SIGNED(int32_t)
SELECTIVE_SIGNED(int64_t)
SELECTIVE_UNSIGNED(uint8_t)
SELECTIVE_UNSIGNED(uint16_t)
SELECTIVE_UNSIGNED(uint32_t)
SELECTIVE_UNSIGNED(uint64_t)
#undef SELECTIVE_SIGNED
#undef SELECTIVE_UNSIGNED
template <>
struct KeyOf<bool> {
	static inline uint64_t Order(const bool &v) {
		return v ? 1 : 0;
	}
	static inline uint64_t Point(const bool &v) {
		return Order(v);
	}
};
template <>
struct KeyOf<double> {
	static inline uint64_t Order(const double &v) {
		return DoubleKey(v);
	}
	static inline uint64_t Point(const double &v) {
		return Order(v);
	}
};
template <>
struct KeyOf<float> {
	static inline uint64_t Order(const float &v) {
		return DoubleKey((double)v);
	}
	static inline uint64_t Point(const float &v) {
		return Order(v);
	}
};
template <>
struct KeyOf<hugeint_t> {
	static inline uint64_t Order(const hugeint_t &v) {
		return HugeintKey(v);
	}
	static inline uint64_t Point(const hugeint_t &v) {
		return Hash(v);
	}
};
template <>
struct KeyOf<uhugeint_t> {
	static inline uint64_t Order(const uhugeint_t &v) {
		return UhugeintKey(v);
	}
	static inline uint64_t Point(const uhugeint_t &v) {
		return Hash(v);
	}
};
template <>
struct KeyOf<string_t> {
	static inline uint64_t Order(const string_t &v) {
		return StringPrefixKey(v.GetData(), v.GetSize());
	}
	static inline uint64_t Point(const string_t &v) {
		return Hash(v.GetData(), v.GetSize());
	}
};

static bool IsExactType(PhysicalType type) {
	switch (type) {
	case PhysicalType::BOOL:
	case PhysicalType::INT8:
	case PhysicalType::INT16:
	case PhysicalType::INT32:
	case PhysicalType::INT64:
	case PhysicalType::UINT8:
	case PhysicalType::UINT16:
	case PhysicalType::UINT32:
	case PhysicalType::UINT64:
		return true;
	default:
		return false;
	}
}

//! Keys of a (non-null) constant of the column's physical type; false if NULL or of another physical type
static bool ValueKeys(const Value &value, PhysicalType ptype, uint64_t &order_key, uint64_t &point_key) {
	if (value.IsNull() || value.type().InternalType() != ptype) {
		return false;
	}
	switch (ptype) {
	case PhysicalType::BOOL: {
		auto v = value.GetValueUnsafe<bool>();
		order_key = KeyOf<bool>::Order(v);
		point_key = KeyOf<bool>::Point(v);
		return true;
	}
#define SELECTIVE_VALUE_CASE(PT, T)                                                                                    \
	case PT: {                                                                                                         \
		auto v = value.GetValueUnsafe<T>();                                                                            \
		order_key = KeyOf<T>::Order(v);                                                                                \
		point_key = KeyOf<T>::Point(v);                                                                                \
		return true;                                                                                                   \
	}
		SELECTIVE_VALUE_CASE(PhysicalType::INT8, int8_t)
		SELECTIVE_VALUE_CASE(PhysicalType::INT16, int16_t)
		SELECTIVE_VALUE_CASE(PhysicalType::INT32, int32_t)
		SELECTIVE_VALUE_CASE(PhysicalType::INT64, int64_t)
		SELECTIVE_VALUE_CASE(PhysicalType::UINT8, uint8_t)
		SELECTIVE_VALUE_CASE(PhysicalType::UINT16, uint16_t)
		SELECTIVE_VALUE_CASE(PhysicalType::UINT32, uint32_t)
		SELECTIVE_VALUE_CASE(PhysicalType::UINT64, uint64_t)
		SELECTIVE_VALUE_CASE(PhysicalType::INT128, hugeint_t)
		SELECTIVE_VALUE_CASE(PhysicalType::UINT128, uhugeint_t)
		SELECTIVE_VALUE_CASE(PhysicalType::FLOAT, float)
		SELECTIVE_VALUE_CASE(PhysicalType::DOUBLE, double)
#undef SELECTIVE_VALUE_CASE
	case PhysicalType::VARCHAR: {
		auto &str = StringValue::Get(value);
		order_key = StringPrefixKey(str.c_str(), str.size());
		point_key = Hash(str.c_str(), str.size());
		return true;
	}
	default:
		return false;
	}
}

template <class T>
static void AppendKeys(UnifiedVectorFormat &format, idx_t count, bool point, vector<uint64_t> &keys) {
	auto data = UnifiedVectorFormat::GetData<T>(format);
	if (format.validity.AllValid()) {
		for (idx_t i = 0; i < count; i++) {
			auto idx = format.sel->get_index(i);
			keys.push_back(point ? KeyOf<T>::Point(data[idx]) : KeyOf<T>::Order(data[idx]));
		}
	} else {
		for (idx_t i = 0; i < count; i++) {
			auto idx = format.sel->get_index(i);
			if (!format.validity.RowIsValid(idx)) {
				continue;
			}
			keys.push_back(point ? KeyOf<T>::Point(data[idx]) : KeyOf<T>::Order(data[idx]));
		}
	}
}

//===--------------------------------------------------------------------===//
// Configuration (PRUNING_STATS_COLUMNS)
//===--------------------------------------------------------------------===//
struct ConfigEntry {
	string table;
	string column; // "*" = all supported columns
	SelectiveStatKind kind;
	idx_t words;
	idx_t ngram_n = 3;
};

struct Config {
	vector<ConfigEntry> entries;
	vector<string> errors;
	mutex lock;
	//! resolved specs by "table.column" (stable pointers)
	map<string, unique_ptr<SelectiveColumnSpec>> resolved;
	vector<string> warned;

	Config() {
		auto env = std::getenv("PRUNING_STATS_COLUMNS");
		if (!env || !*env) {
			return;
		}
		string text(env);
		for (auto &c : text) {
			if (c == ';' || c == ' ' || c == '\t' || c == '\n') {
				c = ',';
			}
		}
		for (auto &item : StringUtil::Split(text, ',')) {
			auto entry_text = StringUtil::Lower(item);
			StringUtil::Trim(entry_text);
			if (entry_text.empty()) {
				continue;
			}
			auto parts = StringUtil::Split(entry_text, ':');
			auto dot = parts.empty() ? string::npos : parts[0].rfind('.');
			if (parts.size() < 2 || parts.size() > 4 || dot == string::npos || dot == 0 ||
			    dot + 1 >= parts[0].size()) {
				errors.push_back("cannot parse '" + item + "' (expected table.column:kind[:words[:n]])");
				continue;
			}
			ConfigEntry entry;
			entry.table = parts[0].substr(0, dot);
			entry.column = parts[0].substr(dot + 1);
			if (parts[1] == "occupancy") {
				entry.kind = SelectiveStatKind::OCCUPANCY;
			} else if (parts[1] == "nullspace") {
				entry.kind = SelectiveStatKind::NULLSPACE;
			} else if (parts[1] == "bloom") {
				entry.kind = SelectiveStatKind::BLOOM;
			} else if (parts[1] == "ngram" ||
			           (parts[1].size() == 6 && parts[1].compare(0, 5, "ngram") == 0 && parts[1][5] >= '1' &&
			            parts[1][5] <= '8')) {
				entry.kind = SelectiveStatKind::NGRAM;
				if (parts[1].size() == 6) {
					entry.ngram_n = (idx_t)(parts[1][5] - '0');
				}
			} else {
				errors.push_back("unknown kind '" + parts[1] + "' in '" + item + "' (occupancy|nullspace|ngram|bloom)");
				continue;
			}
			if (parts.size() == 4) {
				char *end = nullptr;
				auto n = strtoull(parts[3].c_str(), &end, 10);
				if (entry.kind != SelectiveStatKind::NGRAM || !end || *end || n < 1 || n > 8) {
					errors.push_back("invalid n '" + parts[3] + "' in '" + item + "' (ngram only, 1..8)");
					continue;
				}
				entry.ngram_n = n;
			}
			entry.words = 200;
			if (parts.size() == 3) {
				char *end = nullptr;
				auto words = strtoull(parts[2].c_str(), &end, 10);
				if (!end || *end || words < 2 || words > (1ULL << 20)) {
					errors.push_back("invalid size '" + parts[2] + "' in '" + item + "' (64-bit words, >= 2)");
					continue;
				}
				entry.words = words;
			}
			entries.push_back(entry);
		}
		for (auto &error : errors) {
			fprintf(stderr, "PRUNING_STATS_COLUMNS: %s\n", error.c_str());
		}
	}

	static Config &Get() {
		static Config config;
		return config;
	}
};

//===--------------------------------------------------------------------===//
// Building
//===--------------------------------------------------------------------===//
//! Encodes the sorted, distinct keys; returns false if the encoding does not fit into budget_words. NGRAM keys are
//! encoded exactly like NULLSPACE keys (hashed membership). eps_out (nullspace/ngram): expected false-positive rate.
static bool Encode(SelectiveStatKind kind, vector<uint64_t> &keys, idx_t budget_words, BitWriter &out,
                   double *eps_out = nullptr) {
	const uint64_t budget_bits = budget_words * 64 - KIND_BITS;
	if (kind == SelectiveStatKind::OCCUPANCY) {
		std::sort(keys.begin(), keys.end());
		keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
		auto plan = OccupancyCodec::BestPlan(keys, budget_bits);
		out.Write(STREAM_OCCUPANCY, KIND_BITS);
		OccupancyCodec::Write(out, plan);
	} else {
		for (auto &key : keys) {
			key = MixHash(key);
		}
		std::sort(keys.begin(), keys.end());
		keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
		// candidate 1: empty cells of a hashed bitmap (good below one bit per key)
		auto occupancy = OccupancyCodec::BestPlan(keys, budget_bits);
		long double occupied_cells = (long double)(occupancy.span_cells - occupancy.empty_cells);
		long double occupancy_eps = std::min<long double>(
		    1.0L, occupied_cells * OccupancyCodec::Width(occupancy.code) / 18446744073709551616.0L);
		// candidate 2: GF(2)/GF(3) null-space vectors (near the bound from one bit per key)
		auto nullspace = NullspaceCodec::MakePlan(keys, budget_bits);
		if (nullspace.bits <= budget_bits && nullspace.expected_eps < occupancy_eps) {
			out.Write(STREAM_NULLSPACE, KIND_BITS);
			NullspaceCodec::Write(out, nullspace);
			if (eps_out) {
				*eps_out = nullspace.expected_eps;
			}
		} else {
			out.Write(STREAM_OCCUPANCY, KIND_BITS);
			OccupancyCodec::Write(out, occupancy);
			if (eps_out) {
				*eps_out = (double)occupancy_eps;
			}
		}
	}
	return out.bits <= budget_words * 64;
}

//===--------------------------------------------------------------------===//
// Filter evaluation
//===--------------------------------------------------------------------===//
struct Bounds {
	bool has_lo = false;
	bool has_hi = false;
	uint64_t lo = 0;
	uint64_t hi = ~0ULL;
	bool empty = false;
	//! equality constants (point keys) that must all hold
	vector<uint64_t> points;
	bool any_constraint = false;

	void SetLo(uint64_t v) {
		if (!has_lo || v > lo) {
			lo = v;
		}
		has_lo = true;
	}
	void SetHi(uint64_t v) {
		if (!has_hi || v < hi) {
			hi = v;
		}
		has_hi = true;
	}
};

//! Adds the constraint "column <cmp> constant" to the bounds; false if it is not usable
static bool AddComparison(ExpressionType cmp, const Value &constant, const SelectiveStat &stat, Bounds &bounds) {
	uint64_t order_key, point_key;
	if (!ValueKeys(constant, stat.ptype, order_key, point_key)) {
		return false;
	}
	const bool exact = IsExactType(stat.ptype);
	switch (cmp) {
	case ExpressionType::COMPARE_EQUAL:
	case ExpressionType::COMPARE_NOT_DISTINCT_FROM:
		bounds.SetLo(order_key);
		bounds.SetHi(order_key);
		// occupancy statistics are built over ordered keys, nullspace statistics over point keys
		bounds.points.push_back(stat.kind == SelectiveStatKind::OCCUPANCY ? order_key : point_key);
		break;
	case ExpressionType::COMPARE_GREATERTHANOREQUALTO:
		bounds.SetLo(order_key);
		break;
	case ExpressionType::COMPARE_GREATERTHAN:
		if (exact) {
			if (order_key == ~0ULL) {
				bounds.empty = true; // nothing is larger than the maximum (min/max prunes this anyway)
			} else {
				bounds.SetLo(order_key + 1);
			}
		} else {
			bounds.SetLo(order_key); // conservative: treated as >=
		}
		break;
	case ExpressionType::COMPARE_LESSTHANOREQUALTO:
		bounds.SetHi(order_key);
		break;
	case ExpressionType::COMPARE_LESSTHAN:
		if (exact) {
			if (order_key == 0) {
				bounds.empty = true;
			} else {
				bounds.SetHi(order_key - 1);
			}
		} else {
			bounds.SetHi(order_key); // conservative: treated as <=
		}
		break;
	default:
		return false; // <>, IS DISTINCT FROM: no constraint
	}
	bounds.any_constraint = true;
	return true;
}

static bool CanPrune(const TableFilter &filter, const SelectiveStat &stat);

//! For a constant comparison, possibly wrapped in optional/dynamic filters: adds it to the bounds and returns true;
//! returns false if the filter is of another kind
static bool CollectComparison(const TableFilter &filter, const SelectiveStat &stat, Bounds &bounds) {
	switch (filter.filter_type) {
	case TableFilterType::CONSTANT_COMPARISON: {
		auto &cf = filter.Cast<ConstantFilter>();
		AddComparison(cf.comparison_type, cf.constant, stat, bounds);
		return true;
	}
	case TableFilterType::OPTIONAL_FILTER: {
		auto &child = filter.Cast<OptionalFilter>().child_filter;
		return child && CollectComparison(*child, stat, bounds);
	}
	case TableFilterType::DYNAMIC_FILTER: {
		auto &dynamic = filter.Cast<DynamicFilter>();
		if (!dynamic.filter_data) {
			return true; // no constraint
		}
		ExpressionType cmp;
		Value constant;
		{
			lock_guard<mutex> l(dynamic.filter_data->lock);
			if (!dynamic.filter_data->initialized || !dynamic.filter_data->filter) {
				return true; // no constraint (yet)
			}
			cmp = dynamic.filter_data->filter->comparison_type;
			constant = dynamic.filter_data->filter->constant;
		}
		AddComparison(cmp, constant, stat, bounds);
		return true;
	}
	default:
		return false;
	}
}

//! Adds all comparisons of an AND (incl. nested ANDs, also inside optional filters, which are implied by the query)
//! to the bounds; returns true if some other conjunct alone proves that no row matches
static bool CollectConjunction(const ConjunctionAndFilter &conj, const SelectiveStat &stat, Bounds &bounds) {
	for (auto &child : conj.child_filters) {
		const TableFilter *inner = child.get();
		if (inner->filter_type == TableFilterType::OPTIONAL_FILTER && inner->Cast<OptionalFilter>().child_filter &&
		    inner->Cast<OptionalFilter>().child_filter->filter_type == TableFilterType::CONJUNCTION_AND) {
			inner = inner->Cast<OptionalFilter>().child_filter.get();
		}
		if (inner->filter_type == TableFilterType::CONJUNCTION_AND) {
			if (CollectConjunction(inner->Cast<ConjunctionAndFilter>(), stat, bounds)) {
				return true;
			}
			continue;
		}
		if (CollectComparison(*inner, stat, bounds)) {
			continue;
		}
		if (CanPrune(*inner, stat)) {
			return true;
		}
	}
	return false;
}

static bool BoundsCanPrune(const Bounds &bounds, const SelectiveStat &stat) {
	if (bounds.empty || (bounds.has_lo && bounds.has_hi && bounds.lo > bounds.hi)) {
		return true; // contradictory constraints: no value satisfies them
	}
	for (auto point : bounds.points) {
		if (!stat.MayContainKey(point)) {
			return true;
		}
	}
	if (bounds.has_lo && bounds.has_hi && bounds.points.empty()) {
		return !stat.MayContainRange(bounds.lo, bounds.hi);
	}
	return false;
}

static bool CanPrune(const TableFilter &filter, const SelectiveStat &stat) {
	switch (filter.filter_type) {
	case TableFilterType::CONSTANT_COMPARISON:
	case TableFilterType::DYNAMIC_FILTER: {
		Bounds bounds;
		CollectComparison(filter, stat, bounds);
		return bounds.any_constraint && BoundsCanPrune(bounds, stat);
	}
	case TableFilterType::OPTIONAL_FILTER: {
		auto &child = filter.Cast<OptionalFilter>().child_filter;
		return child && CanPrune(*child, stat);
	}
	case TableFilterType::IN_FILTER: {
		auto &in_filter = filter.Cast<InFilter>();
		if (in_filter.values.empty()) {
			return false;
		}
		for (auto &value : in_filter.values) {
			uint64_t order_key, point_key;
			if (value.IsNull()) {
				continue; // never equal to anything
			}
			if (!ValueKeys(value, stat.ptype, order_key, point_key)) {
				return false;
			}
			if (stat.MayContainKey(stat.kind == SelectiveStatKind::OCCUPANCY ? order_key : point_key)) {
				return false;
			}
		}
		return true;
	}
	case TableFilterType::CONJUNCTION_AND: {
		Bounds bounds;
		if (CollectConjunction(filter.Cast<ConjunctionAndFilter>(), stat, bounds)) {
			return true;
		}
		return bounds.any_constraint && BoundsCanPrune(bounds, stat);
	}
	case TableFilterType::CONJUNCTION_OR: {
		auto &conj = filter.Cast<ConjunctionOrFilter>();
		if (conj.child_filters.empty()) {
			return false;
		}
		for (auto &child : conj.child_filters) {
			if (!CanPrune(*child, stat)) {
				return false;
			}
		}
		return true;
	}
	default:
		// IS NULL / IS NOT NULL / expressions / struct extracts: no help from these statistics
		return false;
	}
}

//===--------------------------------------------------------------------===//
// N-gram statistics (kind NGRAM): pruning of substring predicates
//===--------------------------------------------------------------------===//
// The statistic holds (a superset of) the distinct byte n-grams of all non-NULL values of the row group. A predicate
// that can only be true for a value containing the literal byte string L (|L| >= n) cannot be true for any row if one
// of L's n-grams is absent; NULL values make every such predicate NULL (= not true). Values shorter than n contain no
// n-gram and no literal of length >= n, so they need not be represented.

//! n-gram key: the n bytes packed big-endian into the low 8n bits (n <= 8); the same function at build and query time
static inline uint64_t NgramMask(uint32_t n) {
	return n >= 8 ? ~0ULL : (1ULL << (8 * n)) - 1;
}

//! true if the literal byte string definitely does not occur in any value of the row group
static bool NgramLiteralAbsent(const char *data, idx_t size, const SelectiveStat &stat) {
	const uint32_t n = stat.ngram_n;
	if (n == 0 || size < n) {
		return false;
	}
	const uint64_t mask = NgramMask(n);
	uint64_t key = 0;
	for (idx_t i = 0; i < size; i++) {
		key = ((key << 8) | (uint8_t)data[i]) & mask;
		if (i + 1 >= n && !stat.MayContainKey(key)) {
			return true;
		}
	}
	return false;
}

static bool NgramLiteralAbsent(const string &literal, const SelectiveStat &stat) {
	return NgramLiteralAbsent(literal.data(), literal.size(), stat);
}

//! The maximal literal runs of a LIKE pattern (each must occur, as a contiguous byte string, in every matching value).
//! DuckDB semantics (TemplatedLikeOperator): the escape character is checked first and makes the next byte literal;
//! '%' and '_' are wildcards; every other byte matches itself. Returns false for invalid patterns (trailing escape:
//! DuckDB raises an error, which pruning must not hide).
static bool LikeLiteralRuns(const string &pattern, char escape, vector<string> &runs) {
	string current;
	for (idx_t i = 0; i < pattern.size(); i++) {
		char c = pattern[i];
		if (c == escape) {
			if (++i == pattern.size()) {
				return false;
			}
			current += pattern[i];
		} else if (c == '%' || c == '_') {
			if (!current.empty()) {
				runs.push_back(std::move(current));
				current.clear();
			}
		} else {
			current += c;
		}
	}
	if (!current.empty()) {
		runs.push_back(std::move(current));
	}
	return true;
}

//! A non-NULL VARCHAR constant
static bool StringConstant(const Expression &expr, string &result) {
	if (expr.GetExpressionClass() != ExpressionClass::BOUND_CONSTANT) {
		return false;
	}
	auto &value = expr.Cast<BoundConstantExpression>().value;
	if (value.IsNull() || value.type().id() != LogicalTypeId::VARCHAR) {
		return false;
	}
	result = StringValue::Get(value);
	return true;
}

//! The filtered column itself (an ExpressionFilter refers to its column as BoundReference #0), of type VARCHAR
static bool IsFilteredColumn(const Expression &expr) {
	return expr.GetExpressionClass() == ExpressionClass::BOUND_REF &&
	       expr.Cast<BoundReferenceExpression>().index == 0 && expr.return_type.id() == LogicalTypeId::VARCHAR;
}

//! true if the boolean expression (of an ExpressionFilter) is not TRUE for any row of the row group
static bool NgramExpressionCanPrune(const Expression &expr, const SelectiveStat &stat) {
	switch (expr.GetExpressionClass()) {
	case ExpressionClass::BOUND_CONJUNCTION: {
		auto &conj = expr.Cast<BoundConjunctionExpression>();
		if (conj.children.empty()) {
			return false;
		}
		if (expr.GetExpressionType() == ExpressionType::CONJUNCTION_AND) {
			// FALSE or NULL for every row as soon as one conjunct is
			for (auto &child : conj.children) {
				if (NgramExpressionCanPrune(*child, stat)) {
					return true;
				}
			}
			return false;
		}
		if (expr.GetExpressionType() == ExpressionType::CONJUNCTION_OR) {
			for (auto &child : conj.children) {
				if (!NgramExpressionCanPrune(*child, stat)) {
					return false;
				}
			}
			return true;
		}
		return false;
	}
	case ExpressionClass::BOUND_FUNCTION: {
		auto &func = expr.Cast<BoundFunctionExpression>();
		auto &name = func.function.name;
		if (func.children.size() < 2 || !IsFilteredColumn(*func.children[0]) ||
		    func.children[1]->return_type.id() != LogicalTypeId::VARCHAR) {
			return false;
		}
		string literal;
		if (!StringConstant(*func.children[1], literal)) {
			return false;
		}
		if (func.children.size() == 2 && (name == "contains" || name == "prefix" || name == "starts_with" ||
		                                  name == "suffix" || name == "ends_with")) {
			// the literal is a substring of every value for which the function is true
			return NgramLiteralAbsent(literal, stat);
		}
		char escape;
		if (func.children.size() == 2 && name == "~~") {
			escape = '\0'; // LIKE without ESCAPE: DuckDB evaluates it with escape character '\0'
		} else if (func.children.size() == 3 && name == "like_escape") {
			string escape_string;
			if (!StringConstant(*func.children[2], escape_string) || escape_string.size() > 1) {
				return false; // NULL escape (NULL result, not pruned here) or invalid escape (error)
			}
			escape = escape_string.empty() ? '\0' : escape_string[0];
		} else {
			// NOT LIKE, ILIKE, GLOB, regular expressions, ...: never
			return false;
		}
		vector<string> runs;
		if (!LikeLiteralRuns(literal, escape, runs)) {
			return false;
		}
		for (auto &run : runs) {
			if (NgramLiteralAbsent(run, stat)) {
				return true;
			}
		}
		return false;
	}
	default:
		// NOT, comparisons, CASE, casts, functions of the column, ...: never
		return false;
	}
}

static bool NgramCanPrune(const TableFilter &filter, const SelectiveStat &stat);

//! Constant VARCHAR comparison of the column, possibly wrapped in an optional filter
static const ConstantFilter *NgramComparison(const TableFilter &filter) {
	const TableFilter *inner = &filter;
	if (inner->filter_type == TableFilterType::OPTIONAL_FILTER) {
		inner = inner->Cast<OptionalFilter>().child_filter.get();
	}
	if (!inner || inner->filter_type != TableFilterType::CONSTANT_COMPARISON) {
		return nullptr;
	}
	auto &cf = inner->Cast<ConstantFilter>();
	if (cf.constant.IsNull() || cf.constant.type().id() != LogicalTypeId::VARCHAR) {
		return nullptr;
	}
	return &cf;
}

//! lo <= x <= hi (bounds inclusive or exclusive, byte-wise comparison) implies that x starts with the longest common
//! prefix of lo and hi. This covers prefix(col, 'lit') and LIKE 'lit%', which DuckDB pushes down as such a range.
static bool NgramRangeCanPrune(const ConjunctionAndFilter &conj, const SelectiveStat &stat) {
	vector<const string *> lows, highs;
	for (auto &child : conj.child_filters) {
		auto cf = NgramComparison(*child);
		if (!cf) {
			continue;
		}
		switch (cf->comparison_type) {
		case ExpressionType::COMPARE_GREATERTHAN:
		case ExpressionType::COMPARE_GREATERTHANOREQUALTO:
			lows.push_back(&StringValue::Get(cf->constant));
			break;
		case ExpressionType::COMPARE_LESSTHAN:
		case ExpressionType::COMPARE_LESSTHANOREQUALTO:
			highs.push_back(&StringValue::Get(cf->constant));
			break;
		default:
			break;
		}
	}
	for (auto lo : lows) {
		for (auto hi : highs) {
			idx_t common = 0;
			while (common < lo->size() && common < hi->size() && (*lo)[common] == (*hi)[common]) {
				common++;
			}
			if (NgramLiteralAbsent(lo->data(), common, stat)) {
				return true;
			}
		}
	}
	return false;
}

static bool NgramCanPrune(const TableFilter &filter, const SelectiveStat &stat) {
	switch (filter.filter_type) {
	case TableFilterType::EXPRESSION_FILTER:
		return NgramExpressionCanPrune(*filter.Cast<ExpressionFilter>().expr, stat);
	case TableFilterType::CONSTANT_COMPARISON: {
		auto cf = NgramComparison(filter);
		if (!cf || (cf->comparison_type != ExpressionType::COMPARE_EQUAL &&
		            cf->comparison_type != ExpressionType::COMPARE_NOT_DISTINCT_FROM)) {
			return false;
		}
		return NgramLiteralAbsent(StringValue::Get(cf->constant), stat);
	}
	case TableFilterType::IN_FILTER: {
		auto &in_filter = filter.Cast<InFilter>();
		if (in_filter.values.empty()) {
			return false;
		}
		bool any = false;
		for (auto &value : in_filter.values) {
			if (value.IsNull()) {
				continue;
			}
			if (value.type().id() != LogicalTypeId::VARCHAR || !NgramLiteralAbsent(StringValue::Get(value), stat)) {
				return false;
			}
			any = true;
		}
		return any;
	}
	case TableFilterType::OPTIONAL_FILTER: {
		auto &child = filter.Cast<OptionalFilter>().child_filter;
		return child && NgramCanPrune(*child, stat);
	}
	case TableFilterType::CONJUNCTION_AND: {
		auto &conj = filter.Cast<ConjunctionAndFilter>();
		for (auto &child : conj.child_filters) {
			if (NgramCanPrune(*child, stat)) {
				return true;
			}
		}
		return NgramRangeCanPrune(conj, stat);
	}
	case TableFilterType::CONJUNCTION_OR: {
		auto &conj = filter.Cast<ConjunctionOrFilter>();
		if (conj.child_filters.empty()) {
			return false;
		}
		for (auto &child : conj.child_filters) {
			if (!NgramCanPrune(*child, stat)) {
				return false;
			}
		}
		return true;
	}
	default:
		// IS [NOT] NULL, other comparisons, dynamic (top-N / join range) filters, struct extracts: never
		return false;
	}
}

//===--------------------------------------------------------------------===//
// JSON escaping (build-on-load stderr record)
//===--------------------------------------------------------------------===//
static string Escape(const string &input) {
	string result = "\"";
	for (auto c : input) {
		auto uc = static_cast<unsigned char>(c);
		if (c == '"' || c == '\\') {
			result += '\\';
			result += c;
		} else if (c == '\n') {
			result += "\\n";
		} else if (c == '\r') {
			result += "\\r";
		} else if (c == '\t') {
			result += "\\t";
		} else if (uc < 0x20) {
			char buf[8];
			snprintf(buf, sizeof(buf), "\\u%04x", uc);
			result += buf;
		} else {
			result += c;
		}
	}
	return result + "\"";
}

} // namespace selective_impl


//===--------------------------------------------------------------------===//
// SelectiveColumnSpec / SelectiveStat
//===--------------------------------------------------------------------===//
string SelectiveColumnSpec::KindName() const {
	switch (kind) {
	case SelectiveStatKind::OCCUPANCY:
		return "occupancy";
	case SelectiveStatKind::NULLSPACE:
		return "nullspace";
	case SelectiveStatKind::BLOOM:
		return "bloom";
	default:
		return "ngram";
	}
}

bool SelectiveStat::MayContainKey(uint64_t key) const {
	if (kind == SelectiveStatKind::BLOOM) {
		auto bit = selective_impl::BloomBit(key, ptype, n_words);
		return (words[bit / 64] >> (bit % 64)) & 1;
	}
	selective_impl::BitReader in(words.get());
	auto stream = in.Read(selective_impl::KIND_BITS);
	if (kind == SelectiveStatKind::OCCUPANCY) {
		return stream == selective_impl::STREAM_OCCUPANCY ? selective_impl::OccupancyCodec::MayContain(in, key, key) : true;
	}
	if (stream == selective_impl::STREAM_EMPTY) {
		return kind != SelectiveStatKind::NGRAM; // NGRAM: the row group has no n-gram at all
	}
	// NULLSPACE and NGRAM: hashed membership
	auto hash = selective_impl::MixHash(key);
	if (stream == selective_impl::STREAM_NULLSPACE) {
		return selective_impl::NullspaceCodec::MayContain(in, hash);
	}
	if (stream == selective_impl::STREAM_OCCUPANCY) {
		return selective_impl::OccupancyCodec::MayContain(in, hash, hash);
	}
	return true;
}

bool SelectiveStat::MayContainRange(uint64_t lo, uint64_t hi) const {
	if (lo > hi) {
		return false;
	}
	if (kind == SelectiveStatKind::OCCUPANCY) {
		selective_impl::BitReader in(words.get());
		if (in.Read(selective_impl::KIND_BITS) != selective_impl::STREAM_OCCUPANCY) {
			return true;
		}
		return selective_impl::OccupancyCodec::MayContain(in, lo, hi);
	}
	// nullspace: short ranges of integers can be enumerated (for these types point key == ordered key)
	if (kind == SelectiveStatKind::NULLSPACE && selective_impl::IsExactType(ptype) && hi - lo < 64) {
		for (uint64_t key = lo;; key++) {
			if (MayContainKey(key)) {
				return true;
			}
			if (key == hi) {
				return false;
			}
		}
	}
	return true;
}

//===--------------------------------------------------------------------===//
// SelectiveColumnState
//===--------------------------------------------------------------------===//
SelectiveColumnState::SelectiveColumnState(SelectiveColumnSpec &spec_p, PhysicalType ptype_p)
    : spec(spec_p), ptype(ptype_p) {
}

SelectiveColumnState::~SelectiveColumnState() {
}

namespace selective_impl {

//! sort + unique the n-gram key buffer; stop buffering if there are too many distinct n-grams
static void NgramCompact(SelectiveColumnState &state) {
	auto &keys = state.keys;
	std::sort(keys.begin(), keys.end());
	keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
	if (keys.size() > NGRAM_MAX_DISTINCT) {
		state.ngram_overflow = true;
		keys = vector<uint64_t>();
		return;
	}
	// amortised: the buffer holds at most max(2^18, 2 x distinct) keys
	state.ngram_compact_at = MaxValue<idx_t>(idx_t(1) << 18, 2 * keys.size());
}

//! buffer the n-grams of the valid strings of a chunk; returns the number of non-NULL values
static idx_t NgramAppend(SelectiveColumnState &state, UnifiedVectorFormat &format, idx_t count) {
	const uint32_t n = (uint32_t)state.spec.ngram_n;
	const uint64_t mask = NgramMask(n);
	const bool bitmap = n <= 3;
	if (bitmap && !state.ngram_bitmap) {
		idx_t words = MaxValue<idx_t>(1, (idx_t(1) << (8 * n)) / 64);
		state.ngram_bitmap = make_unsafe_uniq_array<uint64_t>(words);
		memset(state.ngram_bitmap.get(), 0, words * sizeof(uint64_t));
	}
	if (!bitmap && state.ngram_compact_at == 0) {
		state.ngram_compact_at = idx_t(1) << 18;
	}
	auto data = UnifiedVectorFormat::GetData<string_t>(format);
	idx_t non_null = 0;
	for (idx_t i = 0; i < count; i++) {
		auto idx = format.sel->get_index(i);
		if (!format.validity.RowIsValid(idx)) {
			continue;
		}
		non_null++;
		if (state.ngram_overflow) {
			continue;
		}
		auto size = data[idx].GetSize();
		if (size < n) {
			continue; // contains no n-gram, and no literal of length >= n
		}
		auto ptr = data[idx].GetData();
		uint64_t key = 0;
		if (bitmap) {
			auto bits = state.ngram_bitmap.get();
			for (idx_t j = 0; j < size; j++) {
				key = ((key << 8) | (uint8_t)ptr[j]) & mask;
				if (j + 1 >= n) {
					bits[key >> 6] |= 1ULL << (key & 63);
				}
			}
		} else {
			for (idx_t j = 0; j < size; j++) {
				key = ((key << 8) | (uint8_t)ptr[j]) & mask;
				if (j + 1 >= n) {
					state.keys.push_back(key);
				}
			}
			if (state.keys.size() >= state.ngram_compact_at) {
				NgramCompact(state);
			}
		}
	}
	return non_null;
}

} // namespace selective_impl

void SelectiveColumnState::Append(Vector &input, idx_t count) {
	if (disabled || count == 0) {
		return;
	}
	auto start = selective_impl::NowNs();
	if (spec.kind == SelectiveStatKind::NGRAM) {
		UnifiedVectorFormat format;
		input.ToUnifiedFormat(count, format);
		if (ptype != PhysicalType::VARCHAR) {
			disabled = true;
			return;
		}
		auto non_null = selective_impl::NgramAppend(*this, format, count);
		spec.values.fetch_add(non_null, std::memory_order_relaxed);
		auto elapsed = selective_impl::NowNs() - start;
		spec.buffer_ns.fetch_add(elapsed, std::memory_order_relaxed);
		spec.total_buffer_ns.fetch_add(elapsed, std::memory_order_relaxed);
		return;
	}
	if (keys.capacity() == 0) {
		keys.reserve(DEFAULT_ROW_GROUP_SIZE);
	}
	auto before = keys.size();
	UnifiedVectorFormat format;
	input.ToUnifiedFormat(count, format);
	const bool point = spec.kind == SelectiveStatKind::NULLSPACE || spec.kind == SelectiveStatKind::BLOOM;
	switch (ptype) {
	case PhysicalType::BOOL:
		selective_impl::AppendKeys<bool>(format, count, point, keys);
		break;
	case PhysicalType::INT8:
		selective_impl::AppendKeys<int8_t>(format, count, point, keys);
		break;
	case PhysicalType::INT16:
		selective_impl::AppendKeys<int16_t>(format, count, point, keys);
		break;
	case PhysicalType::INT32:
		selective_impl::AppendKeys<int32_t>(format, count, point, keys);
		break;
	case PhysicalType::INT64:
		selective_impl::AppendKeys<int64_t>(format, count, point, keys);
		break;
	case PhysicalType::UINT8:
		selective_impl::AppendKeys<uint8_t>(format, count, point, keys);
		break;
	case PhysicalType::UINT16:
		selective_impl::AppendKeys<uint16_t>(format, count, point, keys);
		break;
	case PhysicalType::UINT32:
		selective_impl::AppendKeys<uint32_t>(format, count, point, keys);
		break;
	case PhysicalType::UINT64:
		selective_impl::AppendKeys<uint64_t>(format, count, point, keys);
		break;
	case PhysicalType::INT128:
		selective_impl::AppendKeys<hugeint_t>(format, count, point, keys);
		break;
	case PhysicalType::UINT128:
		selective_impl::AppendKeys<uhugeint_t>(format, count, point, keys);
		break;
	case PhysicalType::FLOAT:
		selective_impl::AppendKeys<float>(format, count, point, keys);
		break;
	case PhysicalType::DOUBLE:
		selective_impl::AppendKeys<double>(format, count, point, keys);
		break;
	case PhysicalType::VARCHAR:
		selective_impl::AppendKeys<string_t>(format, count, point, keys);
		break;
	default:
		disabled = true;
		keys = vector<uint64_t>();
		return;
	}
	spec.values.fetch_add(keys.size() - before, std::memory_order_relaxed);
	auto elapsed = selective_impl::NowNs() - start;
	spec.buffer_ns.fetch_add(elapsed, std::memory_order_relaxed);
	spec.total_buffer_ns.fetch_add(elapsed, std::memory_order_relaxed);
}

static void NgramRecord(SelectiveColumnSpec &spec, uint64_t distinct, uint64_t bytes, double eps) {
	lock_guard<mutex> guard(spec.detail_lock);
	spec.rg_distinct.push_back(distinct);
	spec.rg_bytes.push_back(bytes);
	spec.rg_eps.push_back(eps);
}

void SelectiveColumnState::Finish() {
	if (disabled || stat.load(std::memory_order_acquire)) {
		keys = vector<uint64_t>();
		ngram_bitmap.reset();
		return;
	}
	if (spec.kind == SelectiveStatKind::NGRAM) {
		auto start = selective_impl::NowNs();
		const idx_t n = spec.ngram_n;
		if (ngram_bitmap) {
			// bitmap -> sorted distinct keys
			keys.clear();
			idx_t words = MaxValue<idx_t>(1, (idx_t(1) << (8 * n)) / 64);
			for (idx_t w = 0; w < words; w++) {
				uint64_t bits = ngram_bitmap[w];
				while (bits) {
					keys.push_back(w * 64 + (uint64_t)__builtin_ctzll(bits));
					bits &= bits - 1;
				}
			}
			ngram_bitmap.reset();
		} else if (!ngram_overflow) {
			selective_impl::NgramCompact(*this);
		}
		const uint64_t distinct = ngram_overflow ? 0 : keys.size();
		unique_ptr<SelectiveStat> result;
		double eps = 1.0;
		if (ngram_overflow) {
			spec.row_groups_useless.fetch_add(1, std::memory_order_relaxed);
		} else if (keys.empty()) {
			// no n-gram at all (only NULLs / values shorter than n): no literal of length >= n can match
			result = make_uniq<SelectiveStat>();
			result->n_words = 1;
			result->words = make_unsafe_uniq_array<uint64_t>(2);
			selective_impl::BitWriter out;
			out.Write(selective_impl::STREAM_EMPTY, selective_impl::KIND_BITS);
			result->words[0] = out.words[0];
			result->words[1] = 0;
			eps = 0;
			spec.row_groups_empty.fetch_add(1, std::memory_order_relaxed);
		} else {
			selective_impl::BitWriter out;
			bool fits = selective_impl::Encode(SelectiveStatKind::NGRAM, keys, spec.words, out, &eps);
			if (fits && !out.words.empty() && eps < selective_impl::NGRAM_USELESS_EPS) {
				result = make_uniq<SelectiveStat>();
				result->n_words = out.words.size();
				result->words = make_unsafe_uniq_array<uint64_t>(result->n_words + 1);
				memcpy(result->words.get(), out.words.data(), result->n_words * sizeof(uint64_t));
				result->words[result->n_words] = 0;
			} else {
				if (!fits) {
					eps = 1.0;
				}
				spec.row_groups_useless.fetch_add(1, std::memory_order_relaxed);
			}
		}
		keys = vector<uint64_t>();
		uint64_t bytes = 0;
		if (result) {
			result->kind = SelectiveStatKind::NGRAM;
			result->ptype = ptype;
			result->ngram_n = (uint32_t)n;
			bytes = result->SizeInBytes();
			stat_owner = std::move(result);
			stat.store(stat_owner.get(), std::memory_order_release);
			spec.row_groups_built.fetch_add(1, std::memory_order_relaxed);
			spec.total_row_groups_built.fetch_add(1, std::memory_order_relaxed);
			spec.bytes.fetch_add(bytes, std::memory_order_relaxed);
			spec.total_bytes.fetch_add(bytes, std::memory_order_relaxed);
		}
		NgramRecord(spec, distinct, bytes, ngram_overflow ? 1.0 : eps);
		auto elapsed = selective_impl::NowNs() - start;
		spec.build_ns.fetch_add(elapsed, std::memory_order_relaxed);
		spec.total_build_ns.fetch_add(elapsed, std::memory_order_relaxed);
		return;
	}
	if (keys.empty()) {
		// only NULLs: min/max already proves that no comparison can match
		return;
	}
	auto start = selective_impl::NowNs();
	if (spec.kind == SelectiveStatKind::BLOOM) {
		auto result = make_uniq<SelectiveStat>();
		result->kind = spec.kind;
		result->ptype = ptype;
		result->n_words = spec.words;
		result->words = make_unsafe_uniq_array<uint64_t>(result->n_words + 1);
		memset(result->words.get(), 0, (result->n_words + 1) * sizeof(uint64_t));
		for (auto key : keys) {
			auto bit = selective_impl::BloomBit(key, ptype, result->n_words);
			result->words[bit / 64] |= 1ULL << (bit % 64);
		}
		keys = vector<uint64_t>();
		auto bytes = result->SizeInBytes();
		stat_owner = std::move(result);
		stat.store(stat_owner.get(), std::memory_order_release);
		spec.row_groups_built.fetch_add(1, std::memory_order_relaxed);
		spec.total_row_groups_built.fetch_add(1, std::memory_order_relaxed);
		spec.bytes.fetch_add(bytes, std::memory_order_relaxed);
		spec.total_bytes.fetch_add(bytes, std::memory_order_relaxed);
		auto elapsed = selective_impl::NowNs() - start;
		spec.build_ns.fetch_add(elapsed, std::memory_order_relaxed);
		spec.total_build_ns.fetch_add(elapsed, std::memory_order_relaxed);
		return;
	}
	selective_impl::BitWriter out;
	bool fits = selective_impl::Encode(spec.kind, keys, spec.words, out);
	keys = vector<uint64_t>();
	if (fits && !out.words.empty()) {
		auto result = make_uniq<SelectiveStat>();
		result->kind = spec.kind;
		result->ptype = ptype;
		result->n_words = out.words.size();
		// one zero word of padding: readers never need it for a valid stream, but it keeps reads in bounds
		result->words = make_unsafe_uniq_array<uint64_t>(result->n_words + 1);
		memcpy(result->words.get(), out.words.data(), result->n_words * sizeof(uint64_t));
		result->words[result->n_words] = 0;
		auto bytes = result->SizeInBytes();
		stat_owner = std::move(result);
		stat.store(stat_owner.get(), std::memory_order_release);
		spec.row_groups_built.fetch_add(1, std::memory_order_relaxed);
		spec.total_row_groups_built.fetch_add(1, std::memory_order_relaxed);
		spec.bytes.fetch_add(bytes, std::memory_order_relaxed);
		spec.total_bytes.fetch_add(bytes, std::memory_order_relaxed);
	} else {
		spec.row_groups_failed.fetch_add(1, std::memory_order_relaxed);
	}
	auto elapsed = selective_impl::NowNs() - start;
	spec.build_ns.fetch_add(elapsed, std::memory_order_relaxed);
	spec.total_build_ns.fetch_add(elapsed, std::memory_order_relaxed);
}

void SelectiveColumnState::Invalidate(bool drop_stat) {
	disabled = true;
	keys = vector<uint64_t>();
	ngram_bitmap.reset();
	if (drop_stat) {
		// keep stat_owner alive: a concurrent scan may still use the old pointer
		stat.store(nullptr, std::memory_order_release);
	}
}

//===--------------------------------------------------------------------===//
// SelectiveStats
//===--------------------------------------------------------------------===//
bool SelectiveStats::Enabled() {
	static const bool enabled = !selective_impl::Config::Get().entries.empty();
	return enabled;
}

idx_t SelectiveStats::BuildOnLoadThreads() {
	static const idx_t threads = []() -> idx_t {
		auto env = std::getenv("PRUNING_STATS_BUILD_ON_LOAD");
		if (!env || !*env || string(env) == "0" || StringUtil::Lower(env) == "off") {
			return 0;
		}
		char *end = nullptr;
		auto n = strtoll(env, &end, 10);
		if (!end || *end != '\0' || n < 1) {
			fprintf(stderr, "PRUNING_STATS_BUILD_ON_LOAD: invalid value '%s' (expected a thread count >= 1), using 1\n",
			        env);
			return 1;
		}
		return (idx_t)MinValue<long long>(n, 64);
	}();
	return threads;
}

void SelectiveStats::LogLoadBuild(const string &table, idx_t row_groups, idx_t threads, uint64_t wall_ns,
                                  uint64_t read_ns, const string &error) {
	// per-column build totals since process start (the statement-level "ingest" record of the statement that
	// loaded the table, e.g. ATTACH, has the per-statement numbers)
	string columns = "[";
	{
		auto &config = selective_impl::Config::Get();
		lock_guard<mutex> config_guard(config.lock);
		idx_t k = 0;
		for (auto &resolved : config.resolved) {
			auto &spec = *resolved.second;
			if (!StringUtil::CIEquals(spec.table, table)) {
				continue;
			}
			columns += string(k++ ? "," : "") + "{\"column\":" + selective_impl::Escape(spec.column) +
			           ",\"kind\":" + selective_impl::Escape(spec.KindName()) + ",\"words\":" + to_string(spec.words) +
			           ",\"row_groups_built_total\":" + to_string(spec.total_row_groups_built.load()) +
			           ",\"bytes_total\":" + to_string(spec.total_bytes.load()) +
			           ",\"build_ns_total\":" + to_string(spec.total_build_ns.load()) +
			           ",\"buffer_ns_total\":" + to_string(spec.total_buffer_ns.load()) + "}";
		}
	}
	columns += "]";
	string line = "{\"type\":\"load_build\",\"table\":" + selective_impl::Escape(table) +
	              ",\"row_groups\":" + to_string(row_groups) + ",\"threads\":" + to_string(threads) +
	              ",\"wall_ms\":" + to_string(wall_ns / 1e6) + ",\"read_ms\":" + to_string(read_ns / 1e6) +
	              ",\"columns\":" + columns +
	              ",\"error\":" + (error.empty() ? string("null") : selective_impl::Escape(error)) + "}\n";
	fprintf(stderr, "PRUNING_STATS_BUILD_ON_LOAD %s", line.c_str());
}

bool SelectiveStats::SupportsType(SelectiveStatKind kind, PhysicalType type) {
	if (kind == SelectiveStatKind::NGRAM) {
		return type == PhysicalType::VARCHAR;
	}
	switch (type) {
	case PhysicalType::BOOL:
	case PhysicalType::INT8:
	case PhysicalType::INT16:
	case PhysicalType::INT32:
	case PhysicalType::INT64:
	case PhysicalType::UINT8:
	case PhysicalType::UINT16:
	case PhysicalType::UINT32:
	case PhysicalType::UINT64:
	case PhysicalType::INT128:
	case PhysicalType::UINT128:
	case PhysicalType::FLOAT:
	case PhysicalType::DOUBLE:
	case PhysicalType::VARCHAR:
		return true;
	default:
		return false;
	}
}

static bool SupportsLogicalType(SelectiveStatKind kind, const LogicalType &type) {
	if (kind == SelectiveStatKind::NGRAM) {
		// byte-wise substring semantics (contains / LIKE) hold for VARCHAR without collation
		return type.id() == LogicalTypeId::VARCHAR && StringType::GetCollation(type).empty();
	}
	switch (type.id()) {
	case LogicalTypeId::TIME_TZ:  // compared via a normalised sort key, not the raw bits
	case LogicalTypeId::BIGNUM:   // variable-size encoding
	case LogicalTypeId::BIT:      // padding semantics
	case LogicalTypeId::INTERVAL: // not a simple physical type
		return false;
	case LogicalTypeId::VARCHAR:
		return StringType::GetCollation(type).empty();
	default:
		break;
	}
	if (type.InternalType() == PhysicalType::VARCHAR && type.id() != LogicalTypeId::VARCHAR &&
	    type.id() != LogicalTypeId::BLOB) {
		return false;
	}
	return SelectiveStats::SupportsType(kind, type.InternalType());
}

vector<SelectiveColumnSpec *> SelectiveStats::Resolve(const string &table, const vector<ColumnDefinition> &columns) {
	vector<SelectiveColumnSpec *> result;
	if (!Enabled()) {
		return result;
	}
	auto &config = selective_impl::Config::Get();
	auto table_name = StringUtil::Lower(table);
	result.resize(columns.size(), nullptr);
	bool any = false;
	lock_guard<mutex> guard(config.lock);
	for (idx_t i = 0; i < columns.size(); i++) {
		auto column_name = StringUtil::Lower(columns[i].Name());
		const selective_impl::ConfigEntry *match = nullptr;
		bool exact = false;
		for (auto &entry : config.entries) {
			if (entry.table != table_name) {
				continue;
			}
			if (entry.column == column_name) {
				match = &entry; // exact entries take precedence (the last one wins)
				exact = true;
			} else if (entry.column == "*" && !exact) {
				match = &entry;
			}
		}
		if (!match) {
			continue;
		}
		auto &type = columns[i].Type();
		if (!SupportsLogicalType(match->kind, type)) {
			auto name = table_name + "." + column_name;
			if (exact && std::find(config.warned.begin(), config.warned.end(), name) == config.warned.end()) {
				config.warned.push_back(name);
				fprintf(stderr, "PRUNING_STATS_COLUMNS: type %s of %s is not supported, no statistic\n",
				        type.ToString().c_str(), name.c_str());
			}
			continue;
		}
		auto key = table_name + "." + column_name;
		auto &spec = config.resolved[key];
		if (!spec) {
			spec = make_uniq<SelectiveColumnSpec>();
		}
		// (re-)resolving a table, e.g. after DROP TABLE + CREATE TABLE: keep the accumulators, update the config
		spec->table = table_name;
		spec->column = column_name;
		spec->kind = match->kind;
		spec->words = match->words;
		spec->ngram_n = match->ngram_n;
		result[i] = spec.get();
		any = true;
	}
	if (!any) {
		result.clear();
	}
	return result;
}

bool SelectiveStats::FilterCanPrune(const TableFilter &filter, const SelectiveStat &stat) {
	if (stat.kind == SelectiveStatKind::NGRAM) {
		return selective_impl::NgramCanPrune(filter, stat);
	}
	return selective_impl::CanPrune(filter, stat);
}

} // namespace duckdb
