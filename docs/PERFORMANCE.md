# Performance Benchmarks & Tuning

**Last Updated**: 2025-03-04  
**Status**: ❌ **NOT BENCHMARKED** - Placeholder document  

---

## Performance Targets

| Metric | Target | Status | Notes |
|--------|--------|--------|-------|
| Query response time | <2s typical | ❌ Not measured | Depends on filter complexity |
| Bytes fetched per query | <200 KB | ❌ Not measured | HTTP Range efficiency |
| Page load (broadband) | <5s | ❌ Not measured | Includes WASM init (1.5MB) |
| Database size (compressed) | <500 MB | ⚠️ Test DB: 64 KB | Full DB ~300 MB expected |
| Index usage | Must use idx_filter or idx_instance | ⚠️ Verified on test DB | Needs full-scale validation |

---

## Tuning Parameters

### SQLite Settings (from `pipeline/schema.py`)

```python
PRAGMA_SETTINGS = [
    "PRAGMA page_size = 1024;",      # 1KB pages optimized for HTTP Range
    "PRAGMA journal_mode = WAL;",    # Write-Ahead Logging
    "PRAGMA foreign_keys = ON;",     # Enforce integrity
]
```

**Why page_size=1024?**
- HTTP Range requests fetch 1KB chunks
- Typical query touches 50-200 pages = 50-200 KB
- Smaller pages reduce over-fetch for selective queries

### Indexes (4 total)

1. **idx_filter** on `(service, region, os, tenancy, vcpu, hourly)`  
   Primary filter for common UI filters

2. **idx_instance** on `(service, instance_type)`  
   Direct instance type lookups

3. **idx_price** on `(service, region, purchase_option, hourly)`  
   Price-range queries

4. **idx_specs** on `(vcpu, memory_gb, storage_type)`  
   Hardware specification filtering

**Query Planning**:
```sql
EXPLAIN QUERY PLAN
SELECT * FROM prices
WHERE service='ec2' AND region='us-east-1' AND vcpu >= 4 AND hourly <= 0.5;
```
Expected: `USING INDEX idx_filter`

---

## Benchmark Methodology

### Tools
- Chrome DevTools Performance panel
- Lighthouse (PageSpeed Insights)
- Custom performance logger in frontend (to be added)
- `sqlite3` CLI for `EXPLAIN QUERY PLAN`
- **Benchmark scripts**:
  - `pipeline/benchmark.py`: Comprehensive pipeline and query benchmark suite
  - `frontend/benchmark/frontend-perf.js`: Puppeteer-based frontend load measurement

### Test Queries

```javascript
// Sample queries to benchmark
const testQueries = [
  { name: "Simple service filter", sql: "SELECT * FROM prices WHERE service='ec2' LIMIT 100" },
  { name: "Region + vCPU", sql: "SELECT * FROM prices WHERE region='us-east-1' AND vcpu >= 4" },
  { name: "Price range", sql: "SELECT * FROM prices WHERE hourly >= 0.1 AND hourly <= 1.0" },
  { name: "Instance prefix", sql: "SELECT * FROM prices WHERE instance_type LIKE 'm5.%'" },
  { name: "Combined filters", sql: "SELECT * FROM prices WHERE service='ec2' AND region='us-east-1' AND os='Linux' AND vcpu >= 2 AND memory_gb >= 4 AND hourly <= 0.5" },
];
```

### Measurements to Record

For each query:
1. **Time to first result** (UI perception)
2. **Total rows returned**
3. **Bytes fetched** (sum of `Content-Range` headers or WAL reads)
4. **Query plan** (verify index usage)
5. **HTTP requests count** (should be ~pages touched)

Page load:
1. **WASM load time** (sqlite-wasm-http file size ~1.5MB gzipped)
2. **Database open time** (init + first page fetch)
3. **First meaningful paint**
4. **Time to interactive**

---

## Expected Performance Characteristics

| Query Complexity | Pages Touched | Bytes Fetched | Expected Time |
|------------------|---------------|---------------|---------------|
| Simple equality (service) | 10-50 | 10-50 KB | < 500ms |
| Range + 2 filters | 50-200 | 50-200 KB | 500ms - 1.5s |
| Complex (5+ filters) | 100-500 | 100-500 KB | 1-2s |
| Full table scan (no filters) | 300,000+ | >300 MB | ❌ Not supported |

---

## Optimization Tips

1. **Always filter on indexed columns**: `service`, `region`, `vcpu`, `hourly` are covered.
2. **Avoid leading wildcards**: `LIKE '%large'` prevents index use.
3. **Use `LIMIT`**: Client-side pagination (default 25-100 rows).
4. **Combine filters**: More selective WHERE = fewer pages.
5. **Cache results**: Browser cache with proper `Cache-Control`.

---

## Monitoring in Production

Add performance telemetry to frontend:
```typescript
const start = performance.now();
const results = await database.query(sql, params);
const duration = performance.now() - start;
console.log(`Query: ${sql.substring(0, 50)}... took ${duration.toFixed(2)}ms, ${bytesFetched} bytes`);
```

Track:
- P95 query time < 2s
- P95 bytes fetched < 200KB
- Error rate < 0.1%

---

## Known Performance Risks

1. **SharedArrayBuffer unsupported** (GitHub Pages): Falls back to single-threaded, ~2-3x slower.
2. **Cold start**: First query slower due to WASM initialization (~300-500ms).
3. **Large result sets**: `SELECT *` without `LIMIT` can fetch many pages.
4. **Non-indexed filters**: `family`, `processor` not indexed → table scan.

---

## Future Improvements

- **Partial indexes** for common value combinations
- **Covering indexes** to avoid table lookups
- **Columnar compression** (SQLite extensions) if DB size grows beyond 500MB
- **CDN cache warming** for hot pages (common filters)
- **Client-side query caching** with TTL

---

**Action Items**:  
- [ ] Implement performance logging in `db.ts`  
- [ ] Run benchmark suite on production-sized database  
- [ ] Record results in this file  
- [ ] Verify all metrics meet targets
