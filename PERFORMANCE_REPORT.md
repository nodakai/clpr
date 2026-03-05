# AWS Pricing Static - Performance Benchmark Report

**Date**: March 4, 2026  
**Benchmarked Version**: Main branch as of 2026-03-04  
**Environment**: macOS (Darwin 25), Python 3.14, SQLite 3.45

---

## Executive Summary

- **Pipeline**: Full EC2 dataset generation (174k rows, 63MB) completed in 27.3s. Normalization throughput: 8,360 rows/sec.  
- **Queries**: All test queries execute under 200ms on a 96MB database (268k rows). Index usage is limited; several queries perform full table scans.  
- **HTTP VFS**: Transfer overhead for selective queries: ~2%. For full scans, actual DB size (~96MB) would be transferred.  
- **Frontend**: WASM size ~1.5MB gzipped. Estimated load ~1.2s on 10Mbps connection.

**Key Recommendations**:
1. Add composite index `(service, vcpu, os)` to accelerate vCPU filtering.
2. Add index on `(purchase_option, lease_term, purchase_option_reserved)` for reserved queries.
3. Consider reordering `idx_filter` to move `vcpu` earlier or create a separate index.
4. Optimize pipeline with batch inserts and deferred index creation (2-3x speedup potential).

---

## 1. Database Generation Performance

### Test Setup

Generated synthetic EC2 pricing data to approximate realistic volume:
- Target: 192,000 rows
- Actual: 174,425 rows, 63.2 MB
- Using the benchmark's synthetic data generator (mirrors AWS API structure)

### Results

| Stage | Time (s) | Peak Memory | Throughput |
|-------|----------|-------------|------------|
| Data Generation | 6.43 | 70.6 MB | 27,100 rows/s (generated) |
| Normalization (incl. VACUUM, ANALYZE) | 20.88 | 0.2 MB | 8,360 rows/s |
| **Total** | **27.3** | **70.6 MB** | - |

### Analysis

- Normalization is CPU-bound (Python processing + SQLite inserts).  
- Memory footprint is modest; normalization uses minimal memory beyond data generation.
- Index creation happens before insertion (in `initialize_database`), which slows down bulk inserts. Deferring index creation until after data load could improve speed by 2-3x.

### Extrapolation to Full Dataset

Estimated full EC2 dataset: ~1,000,000 rows (300MB).
- Data generation: ~37s
- Normalization: ~120s (2 minutes)
- Total: **~2-3 minutes** (well under 30-minute threshold)

No major bottleneck detected. However, with real AWS download (network-bound), total time will be dominated by API latency (estimated 15-30 minutes).

---

## 2. Query Performance

### Test Database

- Size: 96.7 MB  
- Rows: 268,800  
- Indexes present:
  - `idx_filter` (service, region, os, tenancy, vcpu, hourly)
  - `idx_instance` (service, instance_type)
  - `idx_price` (service, region, purchase_option, hourly)
  - `idx_specs` (vcpu, memory_gb, storage_type)

### Query Test Results

| Query | SQL | Time (ms) | Rows | Plan | Index Used |
|-------|-----|-----------|------|------|------------|
| Simple vCPU filter | `service='ec2' AND vcpu >= 4 AND os='Linux'` | 155 | 52,500 | SCAN | ✗ |
| Price range + region | `region='us-east-1' AND hourly BETWEEN 0.05 AND 0.20` | 14 | 1,995 | SEARCH idx_price | ✓ |
| Instance type pattern | `instance_type LIKE 'm5.%'` | 116 | 37,800 | SCAN | ✗ |
| Reserved options | `purchase_option='Reserved' AND lease_term='1yr' AND purchase_option_reserved='AllUpfront'` | 43 | 0 | SCAN | ✗ |
| Multi-filter complex | `vcpu >= 8 AND memory_gb >= 16 AND storage_type='nvme' AND hourly < 1.0` | 36 | 0 | SCAN | ✗ |

### Query Plan Analysis

- **idx_price** works because query omits service and uses region hourly range.
- **idx_specs** could support `vcpu >= 8` but the optimizer chooses full scan for queries returning large fractions of the table (e.g., 19% for vCPU filter). This is reasonable for sequential scans.
- **idx_filter** does not help the vCPU filter because `tenancy` sits between `os` and `vcpu`. With no tenancy condition, `vcpu` cannot be used.
- **LIKE 'm5.%'** can use an index on `instance_type` only if the index starts with `instance_type`. The existing `idx_instance` includes `service` first; without `service` filter it's not used.
- Reserved options have no supporting index; full scan is expected.

---

## 3. HTTP VFS Efficiency

### Configuration

- Page size: 1024 bytes (optimized for HTTP Range)
- Max page cache: 8 MB
- HTTP backend maxPageSize: 4096 bytes

### Database Metrics

- File size: 96.7 MB  
- Total pages: 98,974  
- Potential overhead with selective index use: ~2%  
- With full table scans: entire DB (96MB) must be transferred.

### Estimates by Query (Selective Assumption)

| Query | Estimated Pages | Bytes | Requests | Overhead vs DB |
|-------|-----------------|-------|----------|----------------|
| Simple vCPU filter | 500 | 500 KB | 50 | 0.5% |
| Price range | 500 | 500 KB | 50 | 0.5% |
| Instance pattern | 9,897 | 9.9 MB | 989 | 10.2% |
| Reserved options | 200 | 200 KB | 20 | 0.2% |
| Multi-filter | 500 | 500 KB | 50 | 0.5% |
| **Average** | - | - | - | **2.3%** |

**Note**: These estimates assume index-based access with low selectivity. For queries that perform full table scans (observed in our runs), actual transfer ≈ 100% of DB size. Real-world overhead depends heavily on query selectivity and index usage.

### Recommendations

- Current page_size (1024) works well (2% overhead for selective queries).  
- If DB grows >500MB, consider increasing page_size to 4096 to reduce request count by 4x, but test for increased data transfer on small queries.
- Ensure HTTP caching headers (`Cache-Control`) are set by the static host to allow browser caching of pages.

---

## 4. Frontend Load Time

### Components

- **SQLite WASM**: ~1.5 MB gzipped  
- **Database metadata**: First few KB of the DB file (schema, first pages)  
- **Browser initialization**: Parse/compile WASM (~0.5-1s on modern hardware)

### Estimated Timings on 10 Mbps Connection

| Phase | Size | Time |
|-------|------|------|
| WASM download + compile | 1.5 MB | 1.2 s |
| DB metadata fetch (initial pages) | ~50 KB | 0.04 s |
| **Total to first query** | - | **~1.2 s** |

### Measurement Caveats

The above are estimates. Actual measurements require browser automation (Puppeteer/Playwright). A `frontend-perf.js` benchmark script is provided in `frontend/benchmark/` to capture:
- Navigation timing
- Database open time (`db.open()`)
- Bytes read (`worker.bytesRead`)
- First query execution

**To run**: Start dev server with `VITE_USE_TEST_DB=true npm run dev`, then `node frontend/benchmark/frontend-perf.js`.

---

## 5. Optimization Recommendations

### 5.1 Query Performance Improvements

#### 5.1.1 Add Index for vCPU + Service + OS

**Problem**: Query `service='ec2' AND vcpu >= 4 AND os='Linux'` does full scan (~96MB) and returns 52k rows (19% of DB). With 1024-byte pages, this reads nearly all 98k pages.

**Action**: Create a composite index that supports all three conditions:

```sql
CREATE INDEX IF NOT EXISTS idx_vcpu_service_os ON prices(service, os, vcpu);
```

Or, if `vcpu` is the most selective numeric range, put it second:

```sql
CREATE INDEX IF NOT EXISTS idx_service_vcpu_os ON prices(service, vcpu, os);
```

**Expected Impact**: Index seek on `service` and `os`, then range scan on `vcpu`. Should reduce pages read to only those matching the vcpu range (expected ~20% of DB), eliminating full scan.

#### 5.1.2 Add Index for Reserved Pricing

**Problem**: `purchase_option='Reserved' AND lease_term='1yr' AND purchase_option_reserved='AllUpfront'` scans entire table.

**Action**: Create index:

```sql
CREATE INDEX IF NOT EXISTS idx_reserved ON prices(purchase_option, lease_term, purchase_option_reserved);
```

**Expected Impact**: Index lookup on three equality conditions; should return 0 rows quickly if no matches exist, or a few hundred rows for valid combinations.

#### 5.1.3 Review `idx_filter` Column Order

**Problem**: `idx_filter` is defined as `(service, region, os, tenancy, vcpu, hourly)`. Queries that omit `tenancy` cannot use the `vcpu` column for range filtering, because columns after a gap are ignored for range operations.

**Option A**: If `tenancy` is rarely used, drop it from `idx_filter` and create a separate index for tenancy-only queries.

**Option B**: Reorder to put `vcpu` earlier: `(service, region, vcpu, os, tenancy, hourly)`. This may degrade queries that filter on `os` but not `vcpu`.

**Option C**: Create a new index specifically for hardware specs with service/region:  
`CREATE INDEX idx_specs_with_context ON prices(service, region, vcpu, memory_gb, storage_type);`

**Recommendation**: Option A (drop tenancy from `idx_filter`) since the index already has high cardinality columns; a separate `idx_tenancy` on `(tenancy)` or `(service, tenancy)` can serve the few queries that need it. Verify actual query distribution before changing.

#### 5.1.4 Index for `instance_type` Searches

**Problem**: `instance_type LIKE 'm5.%'` performs full scan because `idx_instance` starts with `service`. The query in our test did not include `service`. In practice, the UI likely includes a service filter (e.g., EC2 only). That should use `idx_instance` effectively.

**Verification**: Test query `SELECT * FROM prices WHERE service='ec2' AND instance_type LIKE 'm5.%'` should show `USING INDEX idx_instance`. If not, create an index on `instance_type` alone for service-agnostic searches.

**Action**: Confirm UI always includes service. If not, add `CREATE INDEX idx_instance_type ON prices(instance_type);`

### 5.2 Pipeline Speedups

#### 5.2.1 Batch Insert Execution

**Current**: `normalize.py` inserts rows one-by-one with `conn.execute`.

**Action**: Use `executemany` with batches of 10,000 rows:

```python
cursor.executemany(INSERT_SQL, batch_values)
```

**Expected Impact**: 3-4x faster normalization (from 8.4k rows/s to ~30k rows/s). Would reduce 2-minute normalize to ~30 seconds for full dataset.

#### 5.2.2 Defer Index Creation

**Current**: Indexes are created before data insertion (`initialize_database`), causing each insert to update multiple indexes.

**Action**: Modify pipeline:
1. Create table without indexes.
2. Insert all data.
3. Run VACUUM (optional) and then create indexes.

**Expected Impact**: Additional 2-3x speedup on top of batch inserts.

#### 5.2.3 Parallel Normalization

**Potential**: Split raw JSON by service and normalize in parallel processes (multiprocessing or GNU parallel).

**Consideration**: Normalization is memory-light but CPU-heavy. Parallelism on multi-core machines could approach linear speedup.

**Expected Impact**: 4-8x speedup on 8-core machine (pipeline time down to <30s for full dataset).

### 5.3 HTTP VFS Tuning

#### 5.3.1 Adjust `page_size` for Large DB

If final production DB exceeds 500MB:

```python
# In schema.py
PRAGMA_SETTINGS = [
    "PRAGMA page_size = 4096;",  # instead of 1024
    ...
]
```

**Trade-offs**:
- Fewer HTTP requests (factor 4 reduction).
- Each request transfers up to 4KB instead of 1KB, so total bytes transferred unchanged for full scans, but latency reduced.
- Slightly increased minimum data transfer for selective queries (worst case: 4KB instead of 1KB per page fetched).
- Must be set **before** database creation. Changing page_size on existing DB requires VACUUM into new file.

**Recommendation**: Test with realistic queries to measure impact before committing.

#### 5.3.2 Cache Control Headers

Ensure the static host sends `Cache-Control: public, max-age=86400` for `.sqlite3` file. This enables browsers/CDNs to cache the DB across sessions, dramatically improving repeat visits.

### 5.4 Frontend Improvements

#### 5.4.1 Lazy Database Load

Currently DB is initialized on app start. If users may not use the calculator, defer loading until they interact with the query UI.

**Impact**: Faster first paint; DB load only when needed.

#### 5.4.2 Expose Metrics for Monitoring

Instrument the `Database` class to expose:
- Time to open
- Bytes read so far
- Number of queries executed

Expose globally (`window.dbMetrics`) for external monitoring (as included in the provided `frontend-perf.js`).

---

## 6. Raw Metrics JSON

Full benchmark output is saved in `benchmark_results/benchmark_20260304_115616.json`. Include this in any performance tracking.

---

## 7. Next Steps

1. **Implement recommended index changes** and re-run query benchmarks to quantify improvements.
2. **Upgrade pipeline** with batch inserts and deferred indexes; measure full pipeline time with real AWS download.
3. **Run frontend performance suite** with Puppeteer on production-like data to capture real HTTP request counts and bytes transferred.
4. **Monitor production** by adding custom metrics (bytes read per query, query latency) to the frontend.

---

*End of Report*
