# Deployment Guide

This guide covers deploying the AWS Pricing Static app to GitHub Pages, updating pricing data, and configuring for other platforms.

## GitHub Pages Deployment

### Prerequisites

- Node.js 18+ and npm installed
- Git repository initialized
- Pricing database built (`data/aws_pricing.sqlite3`)

### One-time Setup

1. **Install dependencies and build the app:**

   ```bash
   cd frontend
   npm install
   ```

2. **Copy the pricing database:**

   The database file must be placed in `frontend/public/data/` before building:

   ```bash
   cp ../data/aws_pricing.sqlite3 frontend/public/data/
   ```

   This ensures the database is included in the build output and served from the same origin as the app.

3. **Deploy to GitHub Pages:**

   ```bash
   npm run deploy
   ```

   This command:
   - Builds the app to `dist/`
   - Pushes the `dist/` folder to the `gh-pages` branch
   - GitHub Pages will automatically serve from this branch

4. **Enable GitHub Pages in repository settings:**

   - Go to repository Settings → Pages
   - Set "Source" to "Deploy from a branch"
   - Select branch: `gh-pages`, folder: `/ (root)`
   - Save

   Your site will be available at: `https://<username>.github.io/aws-pricing-static`

### Custom Domain (Optional)

1. In repository Settings → Pages → Custom domain
2. Enter your domain (e.g., `pricing.example.com`)
3. Check "Enforce HTTPS" after DNS propagation
4. Add DNS CNAME record pointing to `<username>.github.io`

## Updating Pricing Data

The pricing database should be updated regularly (weekly) as AWS changes prices.

### Steps to Update:

1. **Regenerate the database:**

   ```bash
   cd pipeline
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m pipeline all
   ```

   This downloads the latest AWS Price List API data and generates a new `data/aws_pricing.sqlite3`.

2. **Copy new database to frontend:**

   ```bash
   cp data/aws_pricing.sqlite3 frontend/public/data/
   ```

3. **Rebuild and redeploy:**

   ```bash
   cd frontend
   npm run deploy
   ```

### Automated Updates (Optional)

Use GitHub Actions to automate weekly updates:

1. Schedule a workflow to run the pipeline and create a PR with the updated database
2. Merge the PR (or auto-merge) to trigger deployment

## Cache Headers

The `_headers` file in `frontend/public/` configures caching for Netlify (also works on some other hosts):

```
/data/aws_pricing.sqlite3
  Cache-Control: public, max-age=86400

/*
  Cache-Control: public, max-age=31536000, immutable
```

- The database (`/data/aws_pricing.sqlite3`) is cached for 1 day (86400 seconds)
- All other assets (JS, CSS, HTML) are cached for 1 year with `immutable` flag

**Note for GitHub Pages:**  
GitHub Pages does not support custom headers via `_headers` file. Use the `.nojekyll` file to disable Jekyll processing. Cache headers on GitHub Pages are managed by the platform with reasonable defaults.

For custom cache control on GitHub Pages, you would need to use a CDN or Cloudflare in front.

## SharedArrayBuffer and Cross-Origin Isolation

The app uses SQLite WASM with SharedArrayBuffer for parallel queries, which requires cross-origin isolation headers:

```
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Opener-Policy: same-origin
```

**Important:** GitHub Pages does **not** support these headers. The app automatically falls back to single-threaded mode when these headers are not present, which works fine (just slightly slower).

For shared memory support on hosts that allow custom headers (e.g., Netlify, Vercel, self-hosted):

1. Add the headers to your server/edge configuration
2. The app will use multi-threading when detected

## Netlify Deployment

1. Push code to GitHub
2. Import repository in Netlify
3. Build command: `cd frontend && npm install && npm run build`
4. Publish directory: `frontend/dist`
5. Add the `_headers` file to `frontend/public/` (already included in repo)
6. Netlify automatically applies headers from `_headers`

## Other Static Hosts

Any host that supports:
- Static file serving
- HTTP Range requests (critical for SQLite WASM HTTP VFS)
- Optional: custom headers for cross-origin isolation

Examples:
- AWS S3 + CloudFront
- Cloudflare Pages
- Vercel (Edge configuration needed for headers)
- Self-hosted Nginx/Apache

## Troubleshooting

**Database not found / 404 errors**
- Ensure `data/aws_pricing.sqlite3` exists in `frontend/public/data/` before building
- Verify the file is included in the `dist/` folder after `npm run build`

**Slow queries or high data transfer**
- Check that indexes exist in the database (`pipeline/generate_db.py` creates them)
- Ensure HTTP Range requests are supported by your host (test with browser dev tools)

**SharedArrayBuffer warnings**
- Normal on GitHub Pages; fallback mode is used
- To enable multi-threading, deploy to a host that supports cross-origin isolation headers

**Build fails with gh-pages command not found**
- Run `npm install` to install devDependencies
- Ensure `gh-pages` is in `devDependencies` in `package.json`

## Files Overview

```
frontend/
├── public/
│   ├── .nojekyll          # Disable Jekyll on GitHub Pages
│   ├── _headers           # Cache headers (Netlify)
│   ├── data/              # Place database here before build
│   └── index.html         # Entry point
├── src/
├── package.json           # Contains deploy script
└── vite.config.ts
```

## Notes

- The database is ~300MB compressed; consider using Git LFS if committing to repo, but typically you'll copy it directly during deployment without versioning.
- For CI/CD, add step to build database and copy to `public/data/` before `npm run deploy`.
