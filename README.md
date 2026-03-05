# AWS Pricing Static

Static AWS pricing calculator using SQLite WASM with HTTP Range requests. Zero backend. Deploy to GitHub Pages.

<p align="center">
  <a href="https://yourusername.github.io/aws-pricing-static"><img src="https://img.shields.io/badge/Live%20Demo-brightgreen?style=for-the-badge" alt="Demo"></a>
  <img src="https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
</p>

## Features

- Static hosting only (GitHub Pages, Netlify, S3)
- All AWS services with On-Demand and Reserved pricing
- HTTP Range requests (<100KB per query)
- Browser-side SQLite queries (privacy-focused)
- Filter UI + advanced SQL mode
- Export CSV/JSON
- Fast, private, zero server costs

## ⚖️ Legal & Data Sources

**AWS Pricing Data**: This tool uses the [AWS Price List API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html), which is publicly available. Prices are provided by AWS and may change at any time. This tool is not affiliated with or endorsed by Amazon Web Services. For actual billing decisions, consult the official AWS Pricing Calculator or your AWS account team.

**Data Accuracy**: We strive to keep the pricing data up to date, but there may be delays between AWS price changes and updates to this database. Always verify critical pricing decisions with the official AWS pricing pages.

**No Warranty**: This software is provided "as is" without warranty of any kind. See [LICENSE](LICENSE) for full text.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Pipeline      │────▶│   SQLite DB      │────▶│   GitHub Pages      │
│   (Python)      │     │  (~300MB)        │     │   (Static Host)     │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
                                                           │
                                                           │ HTTP Range
                                                           ▼
                                                ┌──────────────────────┐
                                                │   Browser            │
                                                │   SQLite WASM        │
                                                │   + HTTP VFS         │
                                                └──────────────────────┘
```

## How It Works

1. Python pipeline downloads AWS Price List API, normalizes data, generates optimized SQLite database (~300MB).
2. Database uploaded to GitHub Pages (or any static host supporting HTTP Range requests).
3. Frontend loads SQLite WASM with HTTP VFS driver in the browser.
4. Queries fetch only needed 1KB pages via HTTP Range; full DB never downloaded.
5. Typical query transfers <100KB with latency <1 second.

## Quick Start

### Users

Visit the [live demo](https://yourusername.github.io/aws-pricing-static) – no setup needed.

### Developers

```bash
# 1. Clone repository
git clone https://github.com/yourusername/aws-pricing-static
cd aws-pricing-static

# 2. Generate test database for development (fast, ~10MB)
python scripts/create_test_db.py

# 3. Start frontend development server with test data
cd frontend
VITE_USE_TEST_DB=true npm run dev
# Open http://localhost:5173

# 4. Optional: Generate full database (required for deployment)
cd ../pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pipeline all  # download → normalize → generate (15-30 min)
cd ..

# 5. Copy full database to frontend for production testing
cp data/aws_pricing.sqlite3 frontend/public/data/
cd frontend
npm run build
```

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete instructions.

**Quick deploy to GitHub Pages:**

```bash
cd frontend
npm run deploy
```

### Important: Cross-Origin Isolation

The app uses SharedArrayBuffer for optimal performance, which requires these response headers:

```
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Opener-Policy: same-origin
```

GitHub Pages does **not** support these headers. The app automatically falls back to single-threaded mode, which works correctly but with slightly reduced performance. No action needed.

For hosts that support custom headers (Netlify, Vercel, self-hosted), adding these headers enables multi-threaded queries.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for platform-specific configuration.

## Contributing

We welcome contributions! Please review:

- [AGENTS.md](AGENTS.md) – Quick reference for automated agents
- [docs/PROJECT.md](docs/PROJECT.md) – Full task breakdown and guidelines

For questions or issues, open a GitHub issue.

## License

MIT – see [LICENSE](LICENSE) for details.
