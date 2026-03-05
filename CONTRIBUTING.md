# Contributing to AWS Pricing Static

Thank you for your interest in contributing! This project is a static AWS pricing calculator that uses SQLite WASM to run entirely in the browser.

## Quick Start

Get up and running in 3 steps:

1. **Clone and install**
```bash
git clone https://github.com/your-org/aws-pricing-static.git
cd aws-pricing-static
pip install -r pipeline/requirements.txt
cd frontend && npm install && cd ..
```

2. **Generate the database** (requires AWS credentials)
```bash
python -m pipeline all
```
This downloads AWS pricing data, normalizes it, and creates `data/aws_pricing.sqlite3` (~300-400MB).

3. **Start the development server**
```bash
cd frontend
npm run dev
```
Open http://localhost:5173 in your browser.

---

## Development Workflow

The project has two main components:

### Data Pipeline (`pipeline/`)

**Purpose:** Download AWS Price List API data, normalize JSON, and generate SQLite database.

**Workflow:**

1. **Download** (`download_pricing.py`)
   - Uses `boto3` client for `pricing` endpoint (us-east-1)
   - Streams JSON response with `ijson` (handles 2.8GB payload)
   - Saves raw `.json` files to `data/raw/`

2. **Normalize** (`normalize.py`)
   - Flattens nested AWS JSON into relational records
   - Maps region display names to codes (e.g., "US East (N. Virginia)" → "us-east-1")
   - Parses memory/storage strings to numeric values
   - Extracts price dimensions (hourly, monthly, upfront)
   - Emits `PriceRow` objects matching `schema.py`

3. **Generate** (`generate_db.py`)
   - Creates SQLite DB with `page_size=1024` (optimized for HTTP Range)
   - Applies indexes: `idx_filter`, `idx_instance`, `idx_price`, `idx_specs`
   - Runs `ANALYZE` and `VACUUM` for query optimization
   - Validates size (<500MB) and row count

**CLI:**
```bash
python -m pipeline download     # Step 1 only
python -m pipeline normalize    # Step 2 only
python -m pipeline generate     # Step 3 only
python -m pipeline all          # Run all steps
python -m pipeline generate --test  # Generate + validate
```

### Frontend (`frontend/`)

**Purpose:** Browser-based query interface using SQLite WASM + HTTP VFS.

**Key files:**

- `src/db.ts` - Database initialization with `sqlite-wasm-http`, handles COOP/COEP
- `src/query-builder.ts` - Expression parser and WHERE clause builder
- `src/filters/` - UI filter components
- `src/table/ResultsTable.tsx` - Results display with pagination, sorting, export
- `src/App.tsx` - Main application state and query orchestration

**Workflow:**
1. Edit code in `frontend/src/`
2. `npm run dev` for hot reload
3. Check browser console for errors
4. `npm run build` to create production bundle (`dist/`)

---

## Testing

### Pipeline Tests

Run schema validation (built into `schema.py`):
```bash
python -m pipeline.schema
# Output should show: ✓ prices table created, ✓ 4 indexes created, etc.
```

Test normalization on sample data:
```bash
# Create test data with a small JSON file
python -c "
import json
with open('data/raw/test.json', 'w') as f:
    json.dump({'products': [{...}]}, f)  # insert minimal product
"
python -m pipeline normalize
python -m pipeline generate
sqlite3 data/aws_pricing.sqlite3 "SELECT COUNT(*) FROM prices;"
```

### Frontend Tests

No automated tests currently. Manual testing checklist:

- [ ] Database loads without errors (check console)
- [ ] Simple query returns results (<2s)
- [ ] All filters work independently
- [ ] Filters combine correctly (AND logic)
- [ ] Expression syntax parses correctly (test edge cases)
- [ ] Sorting works on all columns
- [ ] Export (CSV/JSON) downloads with metadata
- [ ] Mobile view: menu toggles, table scrolls
- [ ] Dark mode toggle persists to localStorage
- [ ] Bytes read < 200KB for typical query

### Performance Testing

Check network panel for HTTP Range requests:
- `worker.bytesRead` shown in footer
- Typical query: 50-200KB
- Broad query: may exceed 1MB (indicates need for better filters)

Run `EXPLAIN QUERY PLAN` on slow queries:
```sql
EXPLAIN QUERY PLAN
SELECT * FROM prices WHERE vcpu >= 4;
```

---

## Code Style

### Python

- **Formatter:** Black (`black pipeline/`)
- **Import sorting:** isort (`isort pipeline/`)
- **Linting:** Ruff (if configured) or flake8
- **Types:** Use type hints (PEP 484). `mypy` recommended.

**Example:**
```python
def parse_memory_gb(memory_str: str) -> Optional[float]:
    """Parse memory string like '8 GiB' to float GB."""
    if not memory_str:
        return None
    match = re.match(r"([\d.]+)\s*(GiB|MiB|GB|MB)", memory_str, re.IGNORECASE)
    # ...
```

### TypeScript/React

- **Linting:** ESLint with `@typescript-eslint`
- **Formatting:** Prettier (`npm run format`)
- **Types:** Strict mode enabled (`strict: true` in `tsconfig.json`)

**Example:**
```typescript
interface PriceRow {
  service: string;
  region: string;
  vcpu: number;
  // ...
}

function parseExpression(field: string, expr: string): ParsedExpression {
  // ...
}
```

### React Components

- Functional components with Hooks
- Props typed with interfaces
- `useCallback` for event handlers passed to children
- Avoid inline objects in JSX props (causes re-renders)

**Example:**
```typescript
const App: React.FC = () => {
  const [filters, setFilters] = useState<Filters>(initialFilters);
  // ...
};
```

### Git Commit Messages

We follow **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>
```

**Types:**
- `feat:` New feature (user-visible change)
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Formatting changes (no code change)
- `refactor:` Code restructuring (no feature change)
- `perf:` Performance improvement
- `test:` Test additions/changes
- `chore:` Build/CI changes, dependency updates

**Examples:**
```
feat(query-builder): add starts_with() string method
fix(db): handle null values in memory_gb column
docs(USER_GUIDE): add troubleshooting section
perf(indexes): add idx_specs for vcpu/memory queries
```

---

## Pull Request Process

1. **Fork and branch**
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make changes**
   - Follow code style guidelines
   - Update documentation if needed
   - Test locally

3. **Commit with Conventional Commit message**
   ```bash
   git add .
   git commit -m "feat: add support for RDS pricing"
   ```

4. **Push and open PR**
   ```bash
   git push origin feat/my-feature
   ```
   - Open PR against `main` branch
   - Fill PR template with:
     - What changed
     - Why (user impact)
     - How to test
     - Screenshots (if UI change)

5. **Review process**
   - Maintainer will review within 2-3 days
   - Address feedback (push additional commits to same branch)
   - CI checks must pass:
     - Lint (`npm run lint`)
     - Type check (`npm run typecheck`)
     - Build succeeds

6. **Merge**
   - Squash and merge to maintain clean history
   - Delete feature branch

---

## Adding New AWS Services

To support additional AWS services beyond EC2, RDS, Lambda, S3, etc.:

1. **Update `TARGET_SERVICES`** in `pipeline/download_pricing.py` (if not already downloading all)
2. **Check normalization** in `normalize.py`:
   - `REGION_MAP` may need new region mappings
   - `OS_MAP` may need new OS values
   - `normalize_product()` extracts generic attributes - most services should "just work"
   - If service has special attributes (e.g., RDS engine type), extend `PriceRow` schema
3. **Update frontend** filters if new useful columns appear:
   - Add to `Filters` interface in `query-builder.ts`
   - Add UI component in `filters/` if needed
4. **Test coverage**:
   - Download sample data for new service
   - Verify rows appear in DB
   - Check frontend displays correctly

**Example:** Adding ElastiCache (already in `SERVICES`):
- Already in SERVICES list, so UI shows it
- Pipeline already includes it in default services (check `download_pricing.py`)
- Just ensure `service` field normalizes to "elasticache" (lowercase, no "Amazon")

---

## Performance Considerations

### Database Size

**Target:** <500MB compressed (GitHub Releases limit)

**Why matters:**
- Initial download: users wait for ~300MB
- HTTP Range efficiency: smaller pages = more predictable fetching
- WASM memory: SQLite needs to load partially into memory

**If DB grows too large:**
- Drop less-used services (`lambda`, `s3` may be small)
- Remove rarely-queried columns (e.g., `sku`, `rate_code`)
- Consider partitioning by region or service (multiple DB files)

### Page Size

**Current:** `page_size = 1024` (1KB)

**Impact:**
- Smaller pages → fewer bytes fetched per query → better HTTP Range utilization
- But more page reads for large result sets
- 1KB is sweet spot for typical queries returning 10-100 rows

**Do not change** without testing:
```bash
# Compare bytes read for same query with different page_sizes
# Must be set BEFORE table creation
```

### Indexes

**Existing indexes cover common patterns:**
- `idx_filter`: Filter by service/region/os/tenancy/vcpu
- `idx_instance`: Instance type lookup
- `idx_price`: Price-based sorting
- `idx_specs`: Hardware specs (vcpu/memory/storage)

**When to add new index:**
- `EXPLAIN QUERY PLAN` shows `SCAN TABLE` for common query
- Index fits within 3-4 columns (index B-tree efficiency)
- Index size doesn't bloat DB excessively

**When NOT to add:**
- Low-cardinality columns alone (e.g., `burst_capable` boolean)
- Columns already covered by composite index
- Write-heavy workload (indexes slow inserts) - but this is read-only DB

---

## Releasing New Data Version

The database is static data that needs periodic updates (AWS changes prices weekly).

1. **Update pipeline** (if AWS API changed)
   - Test `download_pricing.py` and `normalize.py` with latest AWS data
   - Fix any breaking changes

2. **Generate new database**
```bash
python -m pipeline all
```

3. **Validate**
```bash
sqlite3 data/aws_pricing.sqlite3 "SELECT COUNT(*), MIN(effective_date), MAX(effective_date) FROM prices;"
# Should be >10k rows, recent dates
ls -lh data/aws_pricing.sqlite3  # Should be <500MB
```

4. **Commit and tag**
```bash
git add data/aws_pricing.sqlite3
git commit -m "chore(data): update AWS pricing data - 2025-03-04"
git tag -a v2025.03.04 -m "AWS pricing data for March 4, 2025"
git push origin main --tags
```

5. **GitHub Actions** automatically:
   - Builds frontend
   - Deploys to GitHub Pages
   - Creates GitHub Release with database asset (if configured)

**Note:** The DB file is tracked in git (not gitignored) to enable simple static hosting. This is acceptable because the DB is binary and changes infrequently.

---

## Architecture Deep Dive

### Why SQLite WASM + HTTP VFS?

- **No backend:** Fully static hosting (GitHub Pages, S3, Cloudflare Pages)
- **Privacy:** Queries run client-side, no server logs
- **Cost:** Zero hosting cost
- **Performance:** HTTP Range fetches only needed 1KB pages (typical query < 200KB)
- **Trade-offs:** Requires `SharedArrayBuffer` (COOP+COEP headers) or fallback to slower single-threaded mode

### Why Flat Table?

AWS pricing JSON is deeply nested (products → terms → priceDimensions). Flattening to single table:
- Simplifies queries (no JOINs)
- Indexing is straightforward
- Denormalization acceptable for static, read-only data
- Drawback: redundancy (e.g., region repeated per instance type) but disk space is cheap

### Query Flow

1. User adjusts filter
2. `buildWhereClause()` converts `Filters` object to `{ where, params }`
3. `db.query(sql, params)` executes via `sqlite-wasm-http`
4. WASM thread opens DB via HTTP VFS
5. HTTP VFS issues `Range` requests for 1KB pages as SQLite reads
6. Results streamed back to main thread
7. Table renders, `worker.bytesRead` displays network usage

---

## Common Pitfalls

### "Import could not be resolved" in IDE

LSP errors in pipeline files mean `pip install -r requirements.txt` not run or virtual environment not activated. Run:
```bash
cd pipeline
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Database changes not reflected

`generate_db.py` overwrites `data/aws_pricing.sqlite3`. If you see stale data:
- Did you run `normalize.py` first?
- Are you looking at the right DB file?
- Browser cache may serve old DB - hard refresh (`Cmd+Shift+R`) or clear cache

### CORS errors when loading DB

If hosting yourself, ensure server:
- Supports `Range` requests (returns `206 Partial Content`)
- Sets `Accept-Ranges: bytes`
- For SharedArrayBuffer: `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`

GitHub Pages: Range requests work, but COOP/COEP may not → falls back to single-threaded mode (still functional, slower).

### Expression parsing fails

Parser is strict:
- No spaces in range operator: `4..8` not `4 .. 8`
- Parentheses must close
- String methods require quoted argument: `starts_with("m5.")`

See `docs/EXPRESSION_SYNTAX.md` for full grammar.

---

## Getting Help

- **Documentation:** See `/docs` folder
- **Code questions:** Comment inline or open discussion
- **Bugs:** Open issue with replication steps, browser/OS info, console errors
- **Feature requests:** Open issue with use case and proposed API

---

*Last updated: 2025-03-04*
