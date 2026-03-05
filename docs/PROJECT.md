# Project Tracker - AWS Pricing Static

Lightweight task list for implementation. For context, see `AGENTS.md`.

---

## Current Status (Ready for Contributors)

**Overall**: Core architecture in place. Pipeline and frontend infrastructure complete, but key components need implementation.

**Completed**:
- Database schema, indexes, and generation pipeline structure
- SQLite WASM integration with HTTP VFS
- Query builder with expression parsing
- GitHub Actions workflows for deployment

**Blockers / Next Actions**:
- `pipeline/normalize.py` – Transform AWS JSON to relational format (critical path)
- `pipeline/download_pricing.py` – AWS API integration
- Frontend UI components and application logic

Jump in: Implement `normalize.py` or build the filter UI components.

---

## Pre-Implementation Checklist

- [x] Python 3.9+ with pip/venv
- [x] Node.js 18+ with npm
- [x] Git repository initialized
- [x] GitHub repo created (for deployment later)
- [ ] AWS credentials configured (`aws configure` or env vars) – *needed for data pipeline*

---

## Phase 1: Data Pipeline (Week 1)

**Deliverable**: `pipeline/` produces `data/aws_pricing.sqlite3`

### Tasks

| ID | Task | Status | Files to Create | Notes |
|----|------|--------|-----------------|-------|
| P1.1 | Python project setup | ✅ Done | `pipeline/requirements.txt` | `boto3`, `ijson`, `sqlite3` |
| P1.2 | Download AWS pricing | 🟡 Stub | `pipeline/download_pricing.py` | `boto3.client('pricing')`. Stream JSON with `ijson`. |
| P1.3 | Database schema design | ✅ Done | `pipeline/schema.py` | Flattened table `prices` with 30+ columns. Indexes defined. |
| P1.4 | Normalization logic | 🔴 Missing | `pipeline/normalize.py` | **Critical path**: Parse nested AWS JSON, map regions, extract price dimensions. |
| P1.5 | SQLite generation & optimization | ✅ Done | `pipeline/generate_db.py` | `PRAGMA page_size=1024`, `journal_mode=WAL`, VACUUM, ANALYZE. |
| P1.6 | Manual test script | 🟡 Partial | `pipeline/__main__.py` | CLI exists but `download`/`normalize` stubs need implementation. |
| P1.7 | Validation & size check | ✅ Done | In `generate_db.py` | Size <500MB, row count, EXPLAIN plan checks. |
| P1.8 | Automation script | 🔴 Missing | `scripts/update_pricing.sh` | Full pipeline runner with logging. |

### Success Criteria
```bash
# After running pipeline
ls -lh data/aws_pricing.sqlite3  # Should be 300-400MB
sqlite3 data/aws_pricing.sqlite3 "SELECT COUNT(*) FROM prices;"  # Should be > 10k rows
sqlite3 data/aws_pricing.sqlite3 "SELECT service, region, COUNT(*) FROM prices GROUP BY service, region;"  # Show coverage
```

---

## Phase 2: Frontend (Weeks 2-3)

**Deliverable**: Browser app that loads DB and queries via HTTP Range

### Tasks

| ID | Task | Status | Files to Create/Modify | Notes |
|----|------|--------|------------------------|-------|
| P2.1 | Frontend scaffolding | ✅ Done | `frontend/package.json`, `tsconfig.json`, `vite.config.ts` | Vite + TypeScript + React configured. |
| P2.2 | SQLite WASM connection | ✅ Done | `frontend/src/db.ts` | `createSQLiteThread` + `createHttpBackend`. Error handling, timeout. |
| P2.3 | Query builder/parser | ✅ Done | `frontend/src/query-builder.ts` | Expression syntax: `>=4 && <=8`, `10..20`, `starts_with("m5.")`. |
| P2.4 | Basic query UI | 🟡 Partial | `frontend/src/App.tsx` | UI exists but **not wired to DB**. Needs to call `database.query()` and pass results to ResultsTable. |
| P2.5 | Filter components | ✅ Done | `frontend/src/filters/*` | FiltersPanel, ServiceFilter, RegionFilter, RangeFilter, SelectFilter. Types defined. |
| P2.6 | Results table | ✅ Done | `frontend/src/table/ResultsTable.tsx` | Pagination, sorting, column toggle, export buttons. |
| P2.7 | Export functionality | ✅ Done | `frontend/src/utils/export.ts` | CSV/JSON export with metadata. |
| P2.8 | Responsive design | 🟡 Partial | `frontend/src/styles/*.css` | Basic CSS present; needs mobile testing and polish. |

### Minimal Viable Query Flow
```typescript
// src/db.ts
export async function initDB() {
  const httpBackend = createHttpBackend({ cacheSize: 4096 });
  const db = await createSQLiteThread({ http: httpBackend });
  await db('open', { 
    filename: 'file:' + encodeURI(DB_URL), 
    vfs: 'http' 
  });
  return db;
}

// src/query-builder.ts
export function buildWhereClause(filters: Filters): string {
  // Convert filter state to SQL WHERE
  // e.g., { vcpu: '>=4 && <=8', os: ['Linux'] } → "vcpu >= 4 AND vcpu <= 8 AND os IN ('Linux')"
}

// App
const db = await initDB();
const where = buildWhereClause(filters);
const result = await db('exec', { 
  sql: `SELECT * FROM prices WHERE ${where} LIMIT 100`,
  callback: (msg) => console.log(msg.row)
});
```

### Success Criteria
- [ ] DB loads without errors (check `worker.bytesRead` for fetches)
- [ ] Simple query returns results in <2s
- [ ] Filters for service, region, vCPU, price work
- [ ] Bytes fetched shown to user (<100KB typical)

---

## Phase 3: Deployment (Week 4)

**Deliverable**: Automated GitHub Pages deployment

### Tasks

| ID | Task | Status | Files to Create/Modify | Notes |
|----|------|--------|------------------------|-------|
| P3.1 | GitHub repo setup | ✅ Manual | GitHub UI | Create repo, enable Pages from `gh-pages` branch. |
| P3.2 | Frontend CI/CD | ✅ Done | `.github/workflows/build-deploy.yml` | Node setup → npm ci → npm run build → `upload-pages-artifact`. Deploy step may need addition. |
| P3.3 | Data update CI/CD | ✅ Done | `.github/workflows/update-pricing.yml` | Weekly schedule. Runs pipeline, commits DB. Missing `normalize` step will fail currently. |
| P3.4 | CDN caching config | 🔴 Missing | `.nojekyll`, `_headers` | Add to repo root to control caching headers on GitHub Pages. |
| P3.5 | Domain (optional) | ⚪ Optional | `CNAME` | Custom domain if desired. |

### Quick Deploy Script
```bash
# After building frontend
cd frontend
npm run build
npm run deploy  # Assumes gh-pages branch configured
```

---

## Phase 4: Polish & Docs (Week 5)

### Tasks

| ID | Task | Notes |
|----|------|-------|
| P4.1 | User guide | `docs/USER_GUIDE.md` - How to use, filter examples, troubleshooting |
| P4.2 | Expression syntax spec | `docs/EXPRESSION_SYNTAX.md` - Formal grammar, edge cases |
| P4.3 | API reference | `docs/API.md` - SQLite schema, column descriptions |
| P4.4 | Performance tuning | Profile queries, add missing indexes, adjust page_size |
| P4.5 | Mobile responsive | Tailwind CSS or manual media queries |
| P4.6 | Error handling | Graceful WASM load failures, network errors, query timeouts |
| P4.7 | Accessibility | Keyboard nav, ARIA labels, screen reader testing |

---

## Phase 5: Enhancements (Weeks 6-7)

### Tasks (Pick based on interest)

| ID | Feature | Complexity | Value |
|----|---------|-------------|-------|
| P5.1 | Comparison mode | Medium | High |
| P5.2 | Query sharing (URL hash) | Low | Medium |
| P5.3 | Saved presets (localStorage) | Low | Low |
| P5.4 | Advanced SQL tab | Low | Medium |
| P5.5 | Visualizations (charts) | High | Medium |
| P5.6 | Offline mode (IndexedDB cache) | Medium | Low |
| P5.7 | Additional services (Lambda, S3) | Medium | High |
| P5.8 | TCO calculator (add EBS, transfer) | High | Medium |
| P5.9 | PWA support | Low | Low |
| P5.10 | Multi-currency support | Medium | Low |

---

## Common Commands

```bash
# Data pipeline
python -m pipeline generate                # Generate DB (requires normalize.py to exist)
python -m pipeline generate --test        # Generate and validate (same as above)

# Frontend
npm run dev                              # Dev server (http://localhost:5173)
npm run build                            # Production build
npm run preview                          # Preview build
npm run lint                             # TypeScript/ESLint
```

**Note**: The `download` and `normalize` subcommands need implementation before full pipeline (`python -m pipeline all`) works.

---

## Testing Checklist

- [ ] DB loads successfully in browser (console shows no errors)
- [ ] Sample queries return correct results (spot-check 5+)
- [ ] All filters work independently and combined
- [ ] Export produces valid CSV/JSON
- [ ] Mobile view: filter panel collapses, table scrolls
- [ ] Network tab: requests are `Range` headers, total bytes < 200KB for typical query
- [ ] Page works in Chrome, Firefox, Safari, Edge
- [ ] No console errors/warnings in production build

---

## Debugging Tips

### Query too slow?
```sql
EXPLAIN QUERY PLAN SELECT * FROM prices WHERE service='ec2' AND vcpu>=4;
-- Look for "USING INDEX" vs "SCAN TABLE"
-- If SCAN TABLE, add appropriate index
```

### Too many HTTP requests?
Check `worker.bytesRead` and look at network panel. If fetching >1MB:
- Reduce page_size? (currently 1024)
- Add covering indexes
- Query is too broad (add more filters)

### DB not loading?
```bash
# Test Range support on your host
curl -I -H "Range: bytes=0-99" https://yourdomain.com/data/aws_pricing.sqlite3
# Should return: HTTP/2 206  and Content-Range: bytes 0-99/total
```

---

## Milestone Gates

**M1**: Pipeline produces valid DB (<500MB, correct schema) → **Begin Phase 2**
**M2**: App loads DB and executes simple query → **Begin UI development**
**M3**: All filters functional, results accurate → **Begin Phase 3**
**M4**: Deployed to GitHub Pages, working on mobile → **Begin polish**
**M5**: Docs complete, performance optimized → **Launch!**

---

## Need Help?

- Full task details: `docs/PROJECT.md`
- Agent quick reference: `AGENTS.md`
- User guide: `docs/USER_GUIDE.md` (when created)
- Issues: GitHub Issues (use templates)

---

*Last updated: 2025-03-04*
