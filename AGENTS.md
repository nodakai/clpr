# AGENTS.md - Quick Reference

**Purpose**: Start contributing immediately. For full details, see `docs/PROJECT.md`.

---

## Project at a Glance

- **Name**: aws-pricing-static
- **Goal**: Static AWS pricing calculator (Vantage.sh style) with all services
- **Stack**: Python pipeline → SQLite DB → TypeScript/React/Vite frontend → SQLite WASM + HTTP VFS
- **Hosting**: GitHub Pages (fully static, zero backend)
- **Data**: AWS Price List API (public, no auth)

---

## Repository Structure

```
.
├── pipeline/              # Python: download → normalize → SQLite
│   ├── download_pricing.py   # boto3 client, streaming JSON
│   ├── normalize.py          # Transform AWS JSON to relational
│   ├── generate_db.py        # SQLite with indexes, page_size=1024
│   └── requirements.txt      # boto3, ijson
│
├── benchmark/             # Standalone benchmarking tool
│   └── benchmark.py          # Performance measurement suite
│
├── frontend/              # TypeScript/React/Vite app
│   ├── src/
│   │   ├── db.ts            # SQLite WASM + HTTP VFS setup
│   │   ├── query-builder.ts # Expression → SQL converter
│   │   ├── filters/         # UI filter components
│   │   ├── table/           # Results table (virtual scroll)
│   │   └── utils/           # Export, formatting
│   ├── package.json
│   └── vite.config.ts
│
├── data/                  # Generated DB (gitignored, releases only)
│   └── aws_pricing.sqlite3
│
├── docs/
│   └── PROJECT.md         # Full task tracker (Phase 1-5)
│
└── .github/workflows/     # CI/CD: build + weekly data updates
```

---

## Key Technical Decisions

### Why SQLite WASM + HTTP VFS?
- No backend (static hosting only)
- Client-side queries (privacy, no API keys)
- HTTP Range: fetch only needed 1KB pages (<1% of DB typical)

### Database Schema
Flat table (30+ columns):
```sql
CREATE TABLE prices (
    service TEXT,        -- 'ec2', 'rds', 'lambda'
    region TEXT,         -- 'us-east-1'
    instance_type TEXT,  -- 'm5.large'
    os TEXT,            -- 'Linux', 'Windows'
    tenancy TEXT,       -- 'Shared', 'Dedicated', 'Host'
    vcpu INTEGER,
    memory_gb REAL,
    storage TEXT,
    hourly REAL,        -- On-Demand price (USD/hr)
    monthly REAL,       -- hourly * 24 * 30
    purchase_option TEXT, -- 'OnDemand', 'Reserved'
    lease_term TEXT,     -- '1yr', '3yr' (Reserved only)
    upfront_cost REAL,   -- Reserved upfront fee
    -- ... more columns
);
```

**Indexes** (critical for performance):
```sql
CREATE INDEX idx_filter ON prices(service, region, os, tenancy, vcpu, hourly);
CREATE INDEX idx_instance ON prices(service, instance_type);
```

### sqlite-wasm-http (mmomtchev)
- Official SQLite WASM distribution
- SharedArrayBuffer support (concurrent queries)
- Fallback mode (works on GitHub Pages)

---

## Current Status

**Phase 0**: ✓ Research complete  
**Phase 1**: ⬜ Data pipeline (next)  
**Phase 2-5**: ⬜ Pending

See `docs/PROJECT.md` for full task list.

---

## Starting Points by Role

### Data Pipeline Engineer
Begin: `pipeline/download_pricing.py`
- Use boto3 `pricing` client (us-east-1)
- Implement pagination, streaming JSON (ijson)
- Output: normalized Python dicts/CSV

### Database Engineer
Begin: `pipeline/generate_db.py`
- Schema: flattened table with 30+ columns
- PRAGMA: `page_size=1024`, `journal_mode=WAL`
- Indexes on filter columns (region, service, vcpu, price)
- Target: <500MB compressed

### Frontend Engineer
Begin: `frontend/src/db.ts`
- Initialize `createSQLiteThread({ http: createHttpBackend() })`
- Load DB from URL: `file:${encodeURI(DB_URL)}?vfs=http`
- Test with `SELECT COUNT(*) FROM prices`

### UI Engineer
Begin: `frontend/src/filters/`
- Build filter components (Region, Service, vCPU, Memory, OS, Price)
- Expression syntax: `>=4 && <=16`, `10..20`, `starts_with("m5.")`
- Build SQL WHERE clause from UI state

---

## Quick Commands

**Environment Setup** (using uv):
```bash
# Install uv if needed: https://github.com/astral-sh/uv
uv sync  # creates .venv and installs dependencies
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
```

**Pipeline**:
```bash
cd pipeline
uv pip install -r requirements.txt -r requirements-dev.txt  # if not using uv sync
python -m pipeline download      # ~5-15 min, 2.8GB stream
python -m pipeline normalize     # Transform JSON
python -m pipeline generate      # Create SQLite DB
python -m pytest -v              # Run tests with coverage
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
npm run build                   # dist/
npm run test                    # Run unit tests
```

**Deployment**:
```bash
git add data/aws_pricing.sqlite3
git commit -m "Update pricing data"
git push origin main
# GitHub Actions auto-deploys
```

---

## Critical Constraints

- **DB size**: Must stay <500MB (HTTP Range efficiency drops beyond)
- **Page size**: 1024 bytes (optimized for HTTP Range)
- **Immutability**: DB must not change during query session
- **CORS**: Host must support Range requests (GitHub Pages OK)
- **WASM**: ~1.5MB gzipped, load with fallback message

---

## AWS Pricing API Quick Info

**Bulk vs Query**: We use Query API (`boto3.client('pricing').get_products()`)
- Services: `AmazonEC2`, `AmazonRDS`, `AmazonLambda`, `AmazonS3`, etc.
- Format: nested JSON (products[sku].attributes + terms[OnDemand/Reserved])
- Rate limits: None for bulk; Query API has 1000 req/hr (fine for daily updates)

**Key Attributes**:
- `instanceType` → "m5.large"
- `location` → "US East (N. Virginia)" (map to `us-east-1`)
- `operatingSystem` → "Linux", "Windows"
- `tenancy` → "Shared", "Dedicated", "Host"
- `vcpu`, `memory`, `storage`, `networkPerformance`
- Pricing in `terms[OnDemand/Reserved][sku][priceDimensions][rateCode].pricePerUnit.USD`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| WASM fails to load | Server must serve `.wasm` with `application/wasm` MIME |
| HTTP 416 Range errors | DB changed on server; update to latest version |
| Slow queries | Check indexes exist; run `EXPLAIN QUERY PLAN`; ensure page_size=1024 |
| Out of memory | Add `LIMIT` or stricter filters; DB too large |
| Stale prices | Re-run pipeline; check `last_updated` in DB |

---

## Useful References

- **sqlite-wasm-http**: https://github.com/mmomtchev/sqlite-wasm-http
- **SQLite WASM Docs**: https://sqlite.org/wasm/doc/trunk/index.md
- **AWS Price List API**: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html
- **Vantage Instances**: https://instances.vantage.sh/ (UI inspiration)

---

*Last updated: 2025-03-04*  
*See `docs/PROJECT.md` for complete task breakdown, milestones, and detailed specs.*
