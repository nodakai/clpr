# AWS Pricing Static - Final Launch Checklist

**Date**: 2025-03-04  
**Status**: ❌ **NOT READY FOR LAUNCH** - Multiple blocking issues identified

---

## Pre-Launch Verification Results

### 1. Tests

#### Python Tests (pytest)
- **Command**: `cd pipeline && source venv/bin/activate && python -m pytest pipeline/tests -v`
- **Status**: ❌ **FAILED** - 26 failed / 64 total
- **Issues**:
  - `parse_memory_gb()` incorrect conversion for MiB/Mb formats (4 failures)
  - `parse_storage_gb()` incorrect conversion for TB/MiB (4 failures)
  - `normalize_product()` signature mismatch - tests expect 2 args, function takes 1 (17 failures)
  - `normalize_lease_term()` returns '1year'/'3year' vs expected '1yr'/'3yr' (2 failures)
  - `PriceRow.gpu` default None vs expected 0 (1 failure)
  - `set_pragmas()` PRAGMA semicolons mismatch (1 failure)
- **Owner**: Pipeline team  
- **ETA**: Immediate - core functionality broken

#### Frontend Tests (Jest)
- **Command**: `cd frontend && npm test`
- **Status**: ❌ **FAILED** - 21 failed / 54 total
- **Issues**:
  - Query builder missing string method support (`starts_with`, `ends_with`, `has`) (6 failures)
  - Parentheses handling not implemented (2 failures)
  - Multiple AND conditions extra parentheses (1 failure)
  - Negative number parsing broken (1 failure)
  - `buildWhereClause()` combining instance_type equality with LIKE conditions (6 failures)
  - Params not stripped correctly for string methods (1 failure)
  - Range negation extra parentheses (1 failure)
- **Owner**: Frontend team  
- **ETA**: Immediate - query feature incomplete

### 2. Linting
- **Command**: `cd frontend && npm run lint`
- **Status**: ❌ **FAILED** - ESLint configuration file missing
- **Error**: "ESLint couldn't find a configuration file"
- **Owner**: Frontend team  
- **ETA**: Immediate - need to create `.eslintrc.json` or similar

### 3. Database Size
- **Test DB**: `data/aws_pricing.sqlite3` (64 KB)
- **Gzipped**: ~0.01 MB  
- **Production DB**: **NOT GENERATED** - must run full pipeline
- **Expected**: ~300 MB compressed (<500 MB target)
- **Status**: ⚠️ **NEEDS GENERATION** - full pipeline not executed
- **Owner**: Pipeline team  
- **ETA**: 15-30 minutes after pipeline runs

### 4. Database Indexes
- **Test DB indexes verified**: `idx_filter`, `idx_instance` ✓
- **Missing**: `idx_price`, `idx_specs` (not in test schema)
- **Production schema**: `schema.py` defines all 4 indexes
- **Verify with**: `SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices';`
- **Status**: ⚠️ **Partial** - test DB incomplete, production needs verification after generation
- **Owner**: Pipeline team  
- **ETA**: With full DB generation

**Query Plan Check** (test DB):
```sql
EXPLAIN QUERY PLAN SELECT * FROM prices WHERE service='ec2' AND vcpu >= 4 LIMIT 10;
-- Result: `--SEARCH prices USING INDEX idx_instance (service=?)`
-- Note: Small dataset (203 rows) may not use optimal index; acceptable for dev
```

### 5. Frontend Build
- **Command**: `cd frontend && npm run build`
- **Status**: ❌ **FAILED** - TypeScript compilation errors
- **Errors**: 15+ type errors across `App.tsx`, `db.ts`, `ResultsTable.tsx`
  - Unused variables
  - Type mismatches (null vs undefined)
  - Missing properties on SQLite result objects
  - `aria-sort` attribute type incompatibility
- **Owner**: Frontend team  
- **ETA**: Immediate - blocks production build

### 6. Deployment Configuration
- **Workflows**: `.github/workflows/build-deploy.yml`, `update-pricing.yml` ✓
- **Settings**: GitHub Pages from `main` branch `/docs` or custom?  
  - **Issue**: Workflow uploads artifact but deploy step missing; needs `gh-pages` action
  - `build-deploy.yml` stops at `upload-pages-artifact`; needs `pages` action to deploy
- **Owner**: DevOps  
- **ETA**: 1 hour - add deployment step

### 7. Documentation Completeness
**Required docs status**:

| Document | Status | Notes |
|----------|--------|-------|
| README.md | ✅ Exists | Well documented with badges |
| API.md | ✅ Exists | Full schema reference |
| USER_GUIDE.md | ✅ Exists | User instructions |
| EXPRESSION_SYNTAX.md | ✅ Exists | Query syntax |
| DEPLOYMENT.md | ✅ Exists | Deployment instructions |
| CONTRIBUTING.md | ✅ Exists | Contributing guidelines |
| PROJECT.md | ✅ Exists | Task breakdown |
| AGENTS.md | ✅ Exists | Agent reference |
| PERFORMANCE.md | ❌ Missing | To be created (this step) |
| CHANGELOG.md | ❌ Missing | To be created (this step) |
| LAUNCH_CHECKLIST.md | 🔄 Creating | This file |

**Issue**: README references "`docs/DEPLOYMENT.md`" but file exists at docs/DEPLOYMENT.md ✓ OK
- **Legal/Disclaimer**: Needs AWS TOS compliance statement and data usage disclaimer
- **Owner**: Docs team  
- **ETA**: Immediate for disclaimer; PERFORMANCE/CHANGELOG created now

### 8. License File
- **Status**: ❌ **MISSING** - No `LICENSE` file at repository root
- **Required**: MIT License as specified in README badge
- **Owner**: Legal/Project admin  
- **ETA**: Immediate - add MIT LICENSE file

### 9. Hardcoded Secrets
- **Check**: `grep -r "password\|secret\|api_key\|token" pipeline/ frontend/src/ --include="*.py" --include="*.ts" --include="*.tsx"`
- **Result**: No hardcoded credentials found ✅
- **Note**: AWS credentials used via boto3 config/SSO, not hardcoded ✓
- **Owner**: Security team  
- **Status**: ✅ PASS

### 10. Responsive Design
- **Viewport**: `<meta name="viewport" width=device-width, initial-scale=1.0">` ✓
- **Media queries**: Present in `App.css`, `Filters.css`, `ResultsTable.css`  
  - Breakpoints at 768px for mobile/tablet ✓
  - Dark mode, reduced motion support ✓
- **Manual test needed**: Chrome DevTools device toolbar, actual device testing
- **Owner**: UI team  
- **Status**: ✅ Implementation complete, pending manual verification
- **ETA**: 1 hour for manual testing

### 11. Accessibility Audit
- **ARIA**: Extensive use of `aria-label`, `aria-expanded`, `aria-busy`, `role`, `aria-sort`, `aria-live` ✓
- **Keyboard nav**: Need to verify `tabindex`, focus management, `onKeyDown` handlers
- **Focus visible**: Check CSS `:focus` styles
- **Screen reader**: Manual test with VoiceOver/NVDA recommended
- **Owner**: UI/UX team  
- **Status**: ⚠️ Code appears compliant, manual test pending
- **ETA**: 2 hours for thorough audit

### 12. Cross-Browser Testing
- **Browsers**: Chrome, Firefox, Safari, Edge
- **Note**: App uses modern JS (ES2020), SharedArrayBuffer requires COOP/COEP headers  
  GitHub Pages fallback to single-threaded works but may have performance differences
- **Manual test**: Install and test on each browser
- **Owner**: QA team  
- **Status**: ❌ **Not tested**
- **ETA**: 2-3 hours

### 13. Performance Benchmarks

#### Requirements:
- Query response <2s typical
- Bytes fetched <200KB per query
- Page load <5s broadband

#### Current Status: ❌ **Not benchmarked**

**Missing**:
- Performance instrumentation in frontend
- Test queries with realistic filters
- Measure HTTP Range request efficiency
- Page load timing (Lighthouse)

**Action needed**: Implement performance logging, run test suite, document results in PERFORMANCE.md

**Owner**: Performance team  
**ETA**: 2-4 hours (including PERFORMANCE.md creation)

### 14. CI/CD Testing
- **Workflows exist**: Build-deploy, update-pricing ✓
- **Manual test**: Need to trigger workflows via GitHub Actions UI
- **Verify**: 
  - Build succeeds on clean checkout
  - Tests run in CI
  - Artifact upload works
  - Deploy step exists and functions
- **Issue**: Build-deploy.yml lacks deploy action; only builds and uploads artifact
- **Owner**: DevOps  
- **ETA**: 1 hour to fix + manual test

### 15. Database Update Workflow
- **Workflow**: `update-pricing.yml` exists with cron (weekly) and manual dispatch ✓
- **Validation**: Workflow runs `python -m pipeline` steps with size check ✓
- **Test**: Need to trigger manually with `workflow_dispatch` to verify end-to-end
- **Owner**: Pipeline/DevOps  
- **ETA**: 30 min to test manually

### 16. AWS TOS Compliance & Legal Disclaimer
- **Status**: ❌ **Missing**
- **Required**:
  - Add disclaimer: "Prices are for informational purposes only. Not affiliated with AWS. Data retrieved from AWS Price List API."
  - Verify AWS TOS allows redistribution (Yes, price list data is public)
  - Cite AWS as data source in README
- **Owner**: Legal/PM  
- **ETA**: Immediate

---

## Summary of Blocking Issues

| # | Issue | Severity | Owner | ETA |
|---|-------|----------|-------|-----|
| 1 | Python tests failing (26/64) | **BLOCKER** | Pipeline team | 4 hours |
| 2 | Frontend tests failing (21/54) | **BLOCKER** | Frontend team | 4 hours |
| 3 | ESLint config missing | **BLOCKER** | Frontend team | 30 min |
| 4 | Frontend build failing (15 TS errors) | **BLOCKER** | Frontend team | 2 hours |
| 5 | Production database not generated | **BLOCKER** | Pipeline team | 30 min (after fixes) |
| 6 | Missing LICENSE file | **BLOCKER** | Legal/Admin | 15 min |
| 7 | Build-deploy workflow incomplete | **BLOCKER** | DevOps | 1 hour |
| 8 | Missing PERFORMANCE.md | **HIGH** | DevOps/Perf | 2 hours |
| 9 | Missing CHANGELOG.md | **HIGH** | DevRel | 30 min |
| 10 | Missing AWS disclaimer | **HIGH** | Legal/PM | 30 min |
| 11 | Performance benchmarks not run | **HIGH** | Perf team | 2 hours |
| 12 | Manual cross-browser testing | **MEDIUM** | QA | 2 hours |
| 13 | Manual accessibility audit | **MEDIUM** | UX | 2 hours |
| 14 | Responsive design manual test | **MEDIUM** | UI | 1 hour |

**Total estimated work to address blockers**: 15-20 hours

---

## Recommendations

1. **Prioritize fixes in order**:
   - Fix core pipeline bugs (normalize functions, PRAGMA formatting, PriceRow defaults)
   - Implement missing query builder features (string methods, parentheses, negative numbers)
   - Fix TypeScript type errors and lint config
   - Generate production database and verify size/indexes
   - Add LICENSE, CHANGELOG, PERFORMANCE.md
   - Fix CI/CD deployment step
   - Add AWS disclaimer
   - Run performance benchmarks and document

2. **Create sub-issues** for each blocking item with clear acceptance criteria.

3. **Consider staging environment**: Deploy to test GitHub Pages after blockers fixed, before production.

4. **Launch decision**: ❌ **DO NOT LAUNCH** until all BLOCKER items resolved and regression tests pass.

---

## Next Steps

- [ ] Create GitHub issues for all blocking items
- [ ] Assign owners and ETAs
- [ ] Set target launch date after all ✅
- [ ] Schedule final re-check after fixes complete

---

**Checklist maintained by**: Kilo (Automated Agent)  
**Last updated**: 2025-03-04
