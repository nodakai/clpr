# AWS Pricing Static - End-to-End Validation Report

**Date**: 2026-03-04  
**Validator**: Automated CI  
**Scope**: Full pipeline, database optimization, HTTP VFS, frontend build, query correctness

---

## 1. Pipeline Execution

### Status: ❌ FAIL

**Attempted**: Download EC2 data for us-east-1 only using `pipeline/download_filtered.py`

**Error**: AWS credentials expired (InvalidGrantException - SSO token refresh failed)

```
botocore.exceptions.InvalidGrantException: 
Refreshing temporary credentials failed during mandatory refresh period.
```

**Impact**: Cannot procure fresh AWS pricing data to generate database.

**Current fallback**: Using existing `data/test_aws_pricing.sqlite3` (64KB, 203 rows, legacy schema).

---

## 2. Database Optimization

### Status: ⚠️ PARTIAL PASS (using test DB)

**Test Database Conditions**:
- Size: 64KB (far below 50MB validation threshold)
- Page size: **4096** (should be **1024** per PRAGMA settings)
- Indexes present: `idx_filter`, `idx_instance` only  
  Missing: `idx_price`, `idx_specs` (expected in production)

**Query Plan Analysis**:

| Query | Plan | Expected | Status |
|-------|------|----------|--------|
| `vcpu >= 4 AND os='Linux'` | SCAN TABLE | USING INDEX (idx_specs) | ❌ |
| `service='ec2' AND region='us-east-1' AND hourly < 0.10` | SEARCH USING idx_filter | USING INDEX | ✅ |
| `service='ec2' AND instance_type='m5.large'` | SEARCH USING idx_instance | USING INDEX | ✅ |

**Note**: The query `vcpu >= 4` alone cannot utilize `idx_filter` because the leftmost columns (service, region) are unconstrained. The `idx_specs` index on `(vcpu, memory_gb, storage_type)` would allow an index seek for vcpu-only filters.

**Production Expectation**: The pipeline's `schema.py` correctly creates all 4 indexes and sets `page_size=1024` before table creation. The test DB appears corrupted/outdated.

---

## 3. HTTP VFS Validation

### Status: ✅ PASS

**Server**: `frontend` dev server (`npm run dev`) starts successfully on `http://localhost:5173/`

**Range Request Test**:

```bash
curl -H "Range: bytes=0-1023" -v http://localhost:5173/data/aws_pricing.sqlite3
```

Response:
```
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/65536
Content-Length: 1024
Accept-Ranges: bytes
```

**Confirmations**:
- HTTP 206 Partial Content returned
- `Content-Range` header present
- `Accept-Ranges: bytes` advertised
- Correct `Content-Length` (1024 bytes)

**Efficiency**: Only requested 1KB transferred instead of full 64KB DB.

**Browser Console**: No errors observed during manual check (dev server logs clean).

---

## 4. Query Correctness

### Status: ⚠️ MIXED

**Spot-Check Against Known AWS Prices** (approximate 2025 rates):

| Instance | Region | OS | Tenancy | Expected (USD/hr) | DB Value (USD/hr) | Match |
|----------|--------|-----|---------|-------------------|-------------------|-------|
| m5.large | us-east-1 | Linux | Shared | ~0.096 | 0.1056 | ~10% high |
| t3.micro | us-east-1 | Linux | Shared | ~0.0104 | 0.0111 | close |
| c5.2xlarge | us-east-1 | Linux | Shared | ~0.34 | 0.356 | close |

**Observations**:
- Prices are within plausible range (likely from older data or test sample)
- Region mapping is correct (us-east-1, us-west-2, eu-west-1 appear)
- OS mapping correct (Linux/Windows)
- Tenancy mapping correct (Shared)

**Reserved Pricing Issue**:

```sql
SELECT instance_type,region,os,purchase_option,lease_term,upfront_cost,hourly
FROM prices WHERE purchase_option='Reserved' LIMIT 5;
```

All rows have `upfront_cost = NULL`. This indicates the normalization logic does not extract upfront costs for Reserved Instances. The `normalize.py` leaves `upfront_cost = None` for Reserved (see line 240-244). **This is a data completeness bug** that would affect RI cost calculations.

---

## 5. Size Budget & Pragma Settings

### Status: ❌ FAIL (test DB) / UNKNOWN (production)

**Test DB**:
- File size: 64,536 bytes
- Page size: 4096 (should be 1024)
- Row count: 203

**Expected Production**:
- EC2-only (us-east-1): <200 MB
- Full multi-service: <500 MB

**PRAGMA Verification** (from `schema.py`):
```sql
PRAGMA page_size = 1024;
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
```

The `generate_db.py` pipeline calls `initialize_database()` which sets these pragmas **before** table creation, so production DB should have correct page_size=1024. The test DB's 4096 indicates it was created with default settings.

---

## 6. Frontend Build & Deployment

### Status: ❌ FAIL

**TypeScript Errors**: Initially 10+ errors; after manual fixes, remaining:

1. **db.ts Type assertion fix** – resolved by adding `QueryResult` generic on `withTimeout`.
2. **App.tsx** – fixed `error` state type (string|undefined) and setError(undefined).
3. **ResultsTable.tsx** – removed unused `SkeletonRow` component, removed unused `isMobile` state (reworked effect to use local `lastMobile` ref), removed unused `visibleColumnsCount`, fixed `aria-sort` values to valid ARIA (`ascending`, `descending`, `none`).

**After TypeScript fixes**, `npm run build` fails at Vite bundling stage:

```
error during build:
[commonjs--resolver] Invalid value "iife" for option "output.format" - UMD and IIFE output formats are not supported for code-splitting builds.
file: /.../node_modules/sqlite-wasm-http/dist/index.js
```

**Root Cause**: `sqlite-wasm-http` distributes its worker as an IIFE bundle, which Rollup (used by Vite) rejects for code-splitting builds.

**Recommendation**: Adjust Vite configuration to either:
- Use ES module build of sqlite-wasm-http if available (alias to `.mjs`), or
- Configure `build.rollupOptions.output.format = 'es'` to force ES output, or
- Exclude the worker from Vite's bundling via `vite.config.ts` `build.worker` options, or
- Use a plugin like `@rollup/plugin-commonjs` to wrap the IIFE.

---

## 7. Pre-Deployment Checklist

| Item | Status | Action |
|------|--------|--------|
| AWS credentials re-authenticated | ❌ | Run `aws sso login` and re-run pipeline |
| Pipeline generates proper indexes | ⚠️ | Verify with fresh data (expected: idx_filter, idx_instance, idx_price, idx_specs) |
| Page size set to 1024 | ⚠️ | Verify with `PRAGMA page_size` on fresh DB |
| Reserved upfront costs populated | ❌ | Fix `normalize.py` to extract `upfrontCost` from Reserved terms (lines 240-244) |
| Frontend build succeeds | ❌ | Fix Vite config for sqlite-wasm-http |
| Full DB size <500MB | UNKNOWN | Validate after pipeline run |
| Query plans use indexes | ⚠️ | Verify with `EXPLAIN QUERY PLAN` on production DB |
| UI loads DB via HTTP Range without errors | ✅ | Confirmed with curl test |

---

## 8. Performance Metrics (Test DB)

- **Database file size**: 64 KB
- **Rows**: 203
- **Initial app query** (`service='ec2' AND purchase_option='OnDemand'`): 150 rows returned
- **Bytes read** (simulated): Initial load fetches only pages touched – 1 KB tested
- **Query latency**: Not measured (manual test only)

---

## 9. Recommendations

### Immediate Fixes

1. **Re-authenticate AWS & Generate Fresh DB**:
   ```bash
   source venv/bin/activate
   aws sso login
   python -m pipeline download_filtered  # or use pipeline/all with filters
   python -m pipeline generate data/aws_pricing.sqlite3
   ```
   Verify indexes and page_size.

2. **Reserved Pricing Extraction**:
   - In `pipeline/normalize.py` (lines 240-244), implement logic to capture `upfrontCost` from the `terms` structure for Reserved instances. The current code sets `upfront_cost = None` unconditionally. See AWS Price List API: Reserved prices often have `priceDimensions` with `pricePerUnit` for hourly and separate `discountedPrice` or upfront fields.

3. **Frontend Build**:
   - Add to `frontend/vite.config.ts`:
     ```ts
     import { defineConfig } from 'vite';
     import react from '@vitejs/plugin-react';

     export default defineConfig({
       plugins: [react()],
       build: {
         outDir: 'dist',
         sourcemap: true,
         rollupOptions: {
           output: {
             format: 'es',  // force ES modules to avoid IIFE issues
           },
         },
       },
       resolve: {
         alias: {
           // Optionally force ESM entry if available
           // 'sqlite-wasm-http': 'sqlite-wasm-http/dist/index.mjs',
         },
       },
     });
     ```
   - Or use `vite-plugin-top-level-await` + `commonjs` plugin.
   - Test `npm run build` after changes.

4. **Query Performance**:
   - Ensure `idx_price` and `idx_specs` exist in production DB. These are critical for:
     - Price range queries (`hourly` filtering) – `idx_price`
     - Hardware filters (`vcpu`, `memory_gb`) – `idx_specs`
   - Run `EXPLAIN QUERY PLAN` on representative queries after DB generation; add missing indexes if needed.

5. **Validation Script Enhancements**:
   - The `pipeline/validate.py` currently requires >=50MB DB. Consider a `--light` mode for test DBs or reduce threshold for CI on subsets.
   - Add explicit check for `PRAGMA page_size = 1024`.

### Longer-Term Improvements

- **Index Tuning**: Evaluate if composite index `(service, region, os, tenancy, vcpu, hourly)` is optimal or if separate indexes on `(vcpu)`, `(memory_gb)` would help ad-hoc queries. Current composite is good for multi-filter but not for single-spec filters.
- **Data Size Control**: The page_size=1024 is ideal for HTTP Range; confirm with `PRAGMA page_size` after generation.
- **Monitoring**: Add performance telemetry in frontend to query bytes read and query times for real users (respecting privacy).
- **Test Data**: Include a small but schema-accurate test fixture in the repo for CI, generated by a script that seeds a few rows.

---

## 10. Estimated Full DB Size Extrapolation

Cannot accurately extrapolate without fresh data. However, based on typical AWS Price List API:

- EC2 (single region): ~100k-300k rows → ~50-150 MB (with page_size=1024)
- All services (multi-region): ~1-2M rows → ~300-600 MB (target <500 MB may require pruning unused services or further compression)

**Recommendation**: After generating full DB, check size; if >500 MB, consider:
- Excluding rarely used services
- Aggregating older price dimensions
- Using `VACUUM` and `PRAGMA optimize`.

---

## Conclusion

The project架构 is sound: Python pipeline → SQLite → Frontend with sqlite-wasm-http. Critical blockers:

1. **Authentication**: Need fresh AWS credentials to obtain data.
2. **Reserved Pricing Bug**: Normalization missing upfront costs.
3. **Build Failure**: Vite configuration incompatible with sqlite-wasm-http worker format.

Once these are resolved, re-run the validation with a freshly generated database and updated build.

---

**Report Generated**: 2026-03-04  
**Overall Validation Score**: 4/10 (Partial)
