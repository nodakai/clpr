# User Guide

## ⚖️ Legal & Data Sources

**AWS Pricing Data**: This tool uses the AWS Price List API, which is publicly available. Prices are provided by AWS and may change at any time. This tool is not affiliated with or endorsed by Amazon Web Services. For actual billing decisions, consult the official AWS Pricing Calculator or your AWS account team.

**Data Accuracy**: We strive to keep the pricing data up to date, but there may be delays between AWS price changes and updates to this database. Always verify critical pricing decisions with the official AWS pricing pages.

**No Warranty**: This software is provided "as is" without warranty of any kind. See the project [LICENSE](LICENSE) file for full text.

## Introduction

AWS Pricing Calculator is a free, open-source tool for searching and comparing AWS service pricing. It uses the official AWS Price List API to provide up-to-date pricing information without requiring an AWS account.

**Key Features:**
- Real-time filtering by vCPU, memory, region, OS, and more
- Expression-based filtering (e.g., `>=4 && <=8`, `starts_with("m5.")`)
- Export results to CSV or JSON
- No server-side processing - all queries run in your browser
- Optimized for large datasets using SQLite with HTTP Range requests

## How to Use

1. **Open the Application**
   - Navigate to the hosted site (e.g., GitHub Pages)
   - The database loads automatically on page load (typically 300-400MB)

2. **Set Your Filters**
   - Use the left sidebar to configure filters
   - Changes apply automatically after a short debounce
   - Filters combine with AND logic (except within expression groups using `||`)

3. **View Results**
   - Results appear in the main table
   - Click column headers to sort (ascending/descending)
   - Scroll through up to 1000 results per query

4. **Export Data**
   - Click **Export CSV** or **Export JSON** buttons
   - Exported files include metadata (filters used, row count)
   - CSV includes UTF-8 BOM for Excel compatibility

## Filter Syntax

The expression parser supports flexible range and comparison operations.

### Basic Comparisons

| Syntax | Meaning | Example |
|--------|---------|---------|
| `>=4` | Greater than or equal to 4 | `vcpu >= 4` |
| `<=16` | Less than or equal to 16 | `memory_gb <= 16` |
| `>10` | Greater than 10 | `vcpu > 10` |
| `<100` | Less than 100 | `hourly < 100` |
| `=8` | Exactly 8 | `vcpu = 8` |
| `!=2` | Not equal to 2 | `vcpu != 2` |

### Range Expressions

The `..` operator creates an inclusive range:

- `4..8` - Between 4 and 8 (inclusive)
- Equivalent to `>=4 && <=8`

Examples:
```
vcpu: 4..8
memory_gb: 16..64
```

### String Methods

Apply pattern matching to instance types and other string fields:

- `starts_with("m5.")` - Begins with "m5."
- `ends_with("large")` - Ends with "large"
- `has("xlarge")` - Contains "xlarge"

Examples:
```
instance_type: starts_with("c5.")
instance_type: ends_with("2xlarge")
```

### Logical Operators

Combine multiple conditions:

- `&&` - AND (both sides must match)
- `||` - OR (either side must match)
- `!` - NOT (negates following expression)

**Precedence:** `!` > comparison operators > `&&` > `||`

**Grouping:** Use parentheses to override precedence.

Examples:
```
# vCPU between 4 and 8 OR vCPU >= 16
(vcpu >= 4 && vcpu <= 8) || vcpu >= 16

# Not between 2 and 4
!(vcpu >= 2 && vcpu <= 4)

# Linux OR Windows with >=8 vCPU
(os = "Linux" || os = "Windows") && vcpu >= 8
```

### Field-Specific Syntax

Different filter fields support different syntax:

| Field | Supported Syntax | Notes |
|-------|------------------|-------|
| `vcpu`, `memory_gb` | Full expression language | Numbers only |
| `price_hourly_min/max` | Simple number fields | No expressions |
| `instance_type` | Expressions, wildcards (`*`), string methods | Wildcard `*` converts to `%` for LIKE |
| `service`, `region`, `os`, `tenancy`, `storage_type` | Multi-select dropdowns | Multiple values use `IN (?)` |
| `family` | Exact match | Simple equality |

## Exporting Data

### CSV Export

- **Format:** Standard CSV with UTF-8 BOM
- **Metadata:** Comment lines (`#`) at top show export timestamp, filters, total rows
- **Usage:** Opens directly in Excel, Google Sheets, or any spreadsheet tool

Example output:
```csv
# Exported: 2025-03-04T10:30:00Z
# Filters: {"service":"ec2","vcpu":"4..8"}
# Total rows in dataset: 1000

"service","region","instance_type","vcpu","memory_gb","hourly"
"ec2","us-east-1","m5.large",2,8,0.096
...
```

### JSON Export

- **Format:** Structured JSON with metadata wrapper
- **Schema:** `{ metadata: {...}, data: [...] }`
- **Usage:** Programmatic consumption, APIs, data analysis

Example structure:
```json
{
  "metadata": {
    "exportedAt": "2025-03-04T10:30:00Z",
    "totalRows": 1000,
    "filters": { "service": "ec2", "vcpu": "4..8" }
  },
  "data": [
    { "service": "ec2", "region": "us-east-1", ... },
    ...
  ]
}
```

## Performance Tips

### Why Some Queries Are Slow

1. **Broad Queries**
   - `SELECT * FROM prices` without filters triggers full table scan
   - Database is 300-400MB - scanning entire dataset is expensive
   - **Fix:** Always use restrictive filters (service + at least one other)

2. **Missing Indexes**
   - The database includes indexes on common filter combinations:
     - `idx_filter (service, region, os, tenancy, vcpu, hourly)`
     - `idx_instance (service, instance_type)`
     - `idx_price (service, region, purchase_option, hourly)`
     - `idx_specs (vcpu, memory_gb, storage_type)`
   - **Fix:** Ensure filters align with index columns

3. **Complex Expressions**
   - Expression `!(vcpu >= 2 && vcpu <= 4)` may require table scan
   - Range expressions (`..`) translate to `>= ? AND <= ?` which can use indexes
   - **Fix:** Prefer simple range queries over negated ranges

4. **Client-Side Limitations**
   - SQLite WASM runs in browser memory (typically 2-4GB limit)
   - Complex queries still execute locally, but JavaScript overhead exists
   - **Fix:** Use `LIMIT` (hardcoded to 1000), avoid `SELECT *` when not needed

### Best Practices for Fast Queries

- Always filter by `service` (e.g., "ec2")
- Add `region` filter if you only need specific regions
- Use price ranges instead of broad minimum/maximum
- Combine `vcpu` and `memory_gb` filters to leverage `idx_specs`
- Check the footer "Bytes" value - if >1MB, your query is too broad

## Comparison Mode

*Note: Comparison mode is planned but not yet implemented (see P5.1 in PROJECT.md).*

When available, you'll be able to:
- Select two sets of filters for side-by-side comparison
- View percentage differences in pricing
- Compare purchase options (On-Demand vs Reserved) or regions
- Export comparison reports

## Troubleshooting

### "Database failed to load"

**Symptom:** Error dialog or console shows database initialization failure.

**Causes:**
1. Browser doesn't support SharedArrayBuffer (required for SQLite WASM)
2. CORS headers not configured correctly on server
3. HTTP Range requests not supported
4. Network connectivity issues

**Solutions:**
- Use a modern browser (Chrome 91+, Firefox 90+, Safari 15+, Edge 91+)
- Ensure hosting provider supports `SharedArrayBuffer` (requires `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`)
- Check browser console for specific errors:
  ```
  SharedArrayBuffer: SharedArrayBuffer requires cross-origin isolation
  ```
  - This means the server lacks proper COOP/COEP headers
  - GitHub Pages may not support this; alternative hosts may be needed
- If using GitHub Pages, the app falls back to single-threaded mode (slower but functional)

### "Query returns no results"

**Symptom:** Table shows "No results found."

**Causes:**
1. Filters are too restrictive (too many AND conditions)
2. No data matches the combination (especially with `region`, `os`, `tenancy`)
3. Typo in expression syntax
4. Missing required combination (e.g., certain instance types only available with specific OS/tenancy)

**Solutions:**
- Clear filters and add them back one by one
- Check expression syntax (no spaces, proper operators)
- Try broader ranges (e.g., `vcpu >= 2` instead of `vcpu >= 4 && vcpu <= 8`)
- Remove `tenancy` filter - many instances only available with "Shared"
- Verify region selection - some services not available in all regions

### "Slow queries" or "High bytes fetched"

**Symptom:** Query takes >5 seconds or footer shows Bytes > 1MB.

**Causes:**
1. Query is too broad (few filters)
2. Missing appropriate indexes
3. Complex expressions prevent index usage

**Solutions:**
- Add more filters: always include `service`, add `region`, add `os`
- Use simpler expressions: `4..8` instead of `!(vcpu < 4 || vcpu > 8)`
- Check query in footer - if bytes > 1MB, the database is fetching many pages
- If persistent, may indicate missing index: report with your query details

### "Data seems stale"

**Symptom:** Prices don't match AWS Console or seem outdated.

**Causes:**
1. Database hasn't been updated recently
2. AWS recently changed prices but pipeline hasn't run

**Solutions:**
- Check footer for "Data last updated" timestamp
- If >1 week old, the automated updates may have failed
- View repository releases for newer database versions
- File an issue if data appears consistently stale

### "Expression parsing error"

**Symptom:** Console shows error parsing vcpu or memory_gb expression.

**Causes:**
1. Invalid syntax (missing operator, unmatched parentheses)
2. Mixing number and string incorrectly
3. Using unsupported operator

**Solutions:**
- Ensure expression uses supported operators: `>`, `<`, `>=`, `<=`, `=`, `!=`, `..`
- No spaces within numbers: `4..8` not `4 .. 8`
- For string fields (instance_type), use methods: `starts_with("m5.")`
- Parentheses must close: `(>=4 && <=8)`

## Screenshots

*(Screenshots will be added once UI is finalized)*

- **Main View:** Filters sidebar on left, results table on right
- **Mobile View:** hamburger menu toggles filter panel
- **Export Modal:** Choose CSV or JSON format
- **Dark Mode:** Toggle theme with moon/sun icon

---

*Need help? Report issues at [GitHub Issues](https://github.com/your-repo/issues).*
