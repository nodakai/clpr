# Benchmark Suite

Comprehensive performance benchmarking for AWS Pricing Static application.

## Quick Start

### 1. Install Dependencies

```bash
# Python deps
cd pipeline
pip install -r requirements.txt

# Node deps for frontend benchmark
cd ../frontend
npm install puppeteer --save-dev
```

### 2. Generate Large Test Database (300MB)

```bash
# From project root
python scripts/generate_large_test_db.py --rows 1300000 --output data/benchmark_ec2.sqlite3
```

This generates ~1.3M rows (≈300MB) with realistic data distribution.

### 3. Run Pipeline Benchmark

```bash
cd benchmark
python benchmark.py --db data/benchmark_ec2.sqlite3 --output-dir ../benchmark_results
```

Options:
- `--skip-pipeline`: Skip data generation/normalization benchmark
- `--skip-queries`: Skip query performance tests
- `--skip-http`: Skip HTTP VFS analysis
- `--generate-rows N`: Generate new synthetic data with N rows

### 4. Run Frontend Benchmark

First, update `frontend/src/db.ts` to expose metrics (see below), then:

```bash
# Start dev server with test DB
cd frontend
VITE_USE_TEST_DB=true npm run dev

# In another terminal, run frontend benchmark
node benchmark/frontend-perf.js
```

## Output

Results saved to `benchmark_results/`:
- `benchmark_YYYYMMDD_HHMMSS.json` - Full JSON results
- `summary_YYYYMMDD_HHMMSS.md` - Human-readable summary

## Metrics Collected

### Pipeline Performance
- Data generation time (simulating AWS API download)
- Normalization throughput (rows/sec)
- Database generation time (VACUUM, ANALYZE)
- Peak memory usage per stage
- Final DB size and row count

### Query Performance
Each query measures:
- Execution time (ms)
- EXPLAIN QUERY PLAN output
- Index usage detection
- Rows returned
- Full table scan warnings

Test queries:
1. Simple vCPU filter
2. Price range + region
3. Instance type pattern (LIKE)
4. Reserved options
5. Multi-filter complex

### HTTP VFS Efficiency
- Estimated pages per query
- Bytes transferred per query
- Number of HTTP requests
- Transfer overhead percentage
- Recommendations for page_size tuning

### Frontend Load Performance
- WASM download + compile time
- Database open time
- Time to first query
- Total HTTP requests
- Bytes transferred
- Cache hit rate (if available)

## Optimization Recommendations

Based on benchmark results, the suite automatically generates recommendations:

- **Slow queries**: Suggest covering indexes
- **High HTTP overhead**: Suggest increasing page_size from 1024 to 4096
- **Large DB (>500MB)**: Suggest compression or splitting
- **Slow normalization**: Suggest batch transactions or multiprocessing

## Database Schema Requirements

The benchmark expects the `prices` table with columns as defined in `pipeline/schema.py`. When generating synthetic data, it uses the same normalization pipeline to ensure realistic data distribution.

## Customization

Edit `BENCHMARK_CONFIG` in `benchmark/benchmark.py` to:
- Add more test queries
- Change target database size
- Modify synthetic data distribution

## Interpreting Results

### Good Performance Targets
- Pipeline normalization: >5,000 rows/sec
- Simple queries: <100ms
- Complex queries: <500ms
- HTTP overhead: <10%
- DB size: <500MB
- Frontend load: <3s (including WASM)

### Alert Thresholds
- Any query >1s: Check indexes
- HTTP overhead >15%: Increase page_size
- DB size >500MB: Consider compression
- Pipeline >30min: Optimize generation

## Frontend Instrumentation

To enable database metrics collection, update `frontend/src/db.ts`:

```typescript
// Add at the top of the file
interface DatabaseMetrics {
  initTime?: number;
  openTime?: number;
  bytesRead: number;
  firstQueryTime?: number;
  queryCount: number;
  startTime: number;
}

// Modify Database class to expose metrics
export class Database {
  public metrics: DatabaseMetrics = {
    startTime: performance.now(),
    bytesRead: 0,
    queryCount: 0
  };
  
  async init(): Promise<void> {
    const initStart = performance.now();
    try {
      // ... existing init code ...
      this.metrics.initTime = performance.now() - initStart;
      this.metrics.openTime = this.metrics.initTime; // approx
      console.log('DB init metrics:', this.metrics);
    } catch (error) {
      // ... error handling ...
    }
  }
  
  async query(sql: string, params: any[] = []): Promise<Record<string, any>[]> {
    if (!this.metrics.firstQueryTime && this.metrics.initTime) {
      this.metrics.firstQueryTime = performance.now() - this.metrics.startTime;
    }
    this.metrics.queryCount++;
    // ... existing query code ...
  }
  
  async getMetrics(): Promise<DatabaseMetrics> {
    // Get bytesRead from worker
    if (this.db) {
      this.metrics.bytesRead = await this.db.worker.bytesRead;
    }
    return this.metrics;
  }
}
```

Then ensure metrics are accessible globally:
```typescript
// In main.tsx or App.tsx
import { database } from './db';

// Expose globally for Puppeteer
(window as any).database = database;
setInterval(async () => {
  (window as any).databaseMetrics = await database.getMetrics();
}, 1000);
```

## FAQ

**Q: Can I benchmark with real AWS data?**  
A: Yes, run the full pipeline with `python -m pipeline all` (requires AWS credentials, 15-30 min). Then benchmark against `data/aws_pricing.sqlite3`.

**Q: Why synthetic data?**  
A: Real data generation depends on AWS API, takes too long for iterative benchmarking. Synthetic data simulates volume and distribution without network latency.

**Q: How accurate are HTTP VFS estimates?**  
A: Estimates are based on typical query selectivity. For precise measurements, use Chrome DevTools Network tab or Puppeteer (see frontend benchmark).

**Q: Can I benchmark other services (RDS, Lambda)?**  
A: Yes, extend `INSTANCE_TYPES` in `generate_large_test_db.py` to include other service patterns. The normalization pipeline supports all AWS services.
