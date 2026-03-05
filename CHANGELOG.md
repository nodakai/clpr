# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial project structure
- Data pipeline (download, normalize, generate)
- SQLite WASM frontend with HTTP VFS
- Filter UI with expression syntax
- Export to CSV/JSON
- Responsive design, dark mode, accessibility
- Comprehensive documentation (README, API reference, User Guide, Expression Syntax, Deployment, PROJECT.md, CONTRIBUTING.md, AGENTS.md)
- Performance benchmarks documentation (PERFORMANCE.md)

### Known Issues
- Frontend build errors need resolution
- Reserved pricing upfront costs incomplete
- Production database not yet generated
- Tests partially failing

[//]: # (When releasing, move this section to [0.1.0] - YYYY-MM-DD)

---

## Release Plan

1. Fix all BLOCKER issues listed above
2. Re-run full test suite (pipeline + frontend) with 100% pass
3. Generate production database, verify size <500MB compressed
4. Add MIT LICENSE file
5. Complete PERFORMANCE.md with benchmark results on production DB
6. Add AWS disclaimer to README
7. Fix CI/CD deployment workflow
8. Manual QA: accessibility, cross-browser, responsive
9. Create release tag v0.1.0
10. Deploy to GitHub Pages
11. Announce launch

**Estimated launch date**: TBD after blocker resolution (2-3 days intensive work)

---

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.
