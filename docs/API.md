# API Reference

**Data Source**: This database is generated from the [AWS Price List API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html). All pricing data is provided by AWS and may change without notice. This tool is not affiliated with Amazon Web Services.

This document describes the SQLite database schema, indexes, and usage patterns for querying AWS pricing data.

## Database Schema

### Table: `prices`

The `prices` table contains normalized AWS pricing data with one row per pricing configuration.

```sql
CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    region TEXT NOT NULL,
    instance_type TEXT,
    family TEXT,
    size TEXT,
    vcpu INTEGER,
    memory_gb REAL,
    storage TEXT,
    storage_gb INTEGER,
    storage_type TEXT,
    network_performance TEXT,
    processor TEXT,
    burst_capable BOOLEAN DEFAULT 0,
    gpu INTEGER DEFAULT 0,
    gpu_memory_gb REAL,
    os TEXT NOT NULL,
    tenancy TEXT,
    price_unit TEXT,
    purchase_option TEXT NOT NULL,
    lease_term TEXT,
    purchase_option_reserved TEXT,
    offering_class TEXT,
    hourly REAL NOT NULL,
    monthly REAL,
    upfront_cost REAL,
    effective_date TEXT,
    sku TEXT,
    rate_code TEXT,
    UNIQUE(service, region, instance_type, os, tenancy, purchase_option, lease_term, purchase_option_reserved, offering_class)
);
```

### Column Reference

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key (not used in queries) |
| `service` | TEXT | AWS service code (lowercase, e.g., "ec2", "rds", "lambda") |
| `region` | TEXT | AWS region code (e.g., "us-east-1", "eu-west-1") |
| `instance_type` | TEXT | EC2 instance type (e.g., "m5.large", "c5.2xlarge") |
| `family` | TEXT | Instance family (e.g., "m5", "c5", "t3") |
| `size` | TEXT | Size designation parsed from `instance_type` (e.g., "large", "2xlarge") |
| `vcpu` | INTEGER | Number of virtual CPUs |
| `memory_gb` | REAL | Memory in GiB |
| `storage` | TEXT | Raw storage description from AWS |
| `storage_gb` | INTEGER | Storage capacity in GB (0 for EBS-only) |
| `storage_type` | TEXT | Storage type (e.g., "gp2", "io1", "Instance Store") |
| `network_performance` | TEXT | Network performance description |
| `processor` | TEXT | Processor architecture/type |
| `burst_capable` | BOOLEAN | Whether instance supports bursting (0=false, 1=true) |
| `gpu` | INTEGER | Number of GPUs (0 if none) |
| `gpu_memory_gb` | REAL | GPU memory in GiB |
| `os` | TEXT | Operating system: "Linux", "Windows", "RHEL", "SUSE" |
| `tenancy` | TEXT | Tenancy: "Shared", "Dedicated", "Host" |
| `price_unit` | TEXT | Unit of time for pricing (usually "Hrs") |
| `purchase_option` | TEXT | "OnDemand" or "Reserved" |
| `lease_term` | TEXT | For Reserved: "1yr", "3yr", or NULL for OnDemand |
| `purchase_option_reserved` | TEXT | Reserved payment type: "AllUpfront", "PartialUpfront", "NoUpfront" |
| `offering_class` | TEXT | Usually "standard" or "convertible" for Reserved |
| `hourly` | REAL | Price per hour in USD (NOT NULL) |
| `monthly` | REAL | Price per month (hourly × 24 × 30) |
| `upfront_cost` | REAL | Upfront fee for Reserved instances |
| `effective_date` | TEXT | Date this price became effective |
| `sku` | TEXT | AWS SKU identifier |
| `rate_code` | TEXT | Full rate code for this price dimension |

### Unique Constraint

```sql
UNIQUE(service, region, instance_type, os, tenancy, purchase_option, lease_term, purchase_option_reserved, offering_class)
```

This prevents duplicate pricing entries. When updating the database, use `INSERT OR REPLACE` to update existing rows.

## Indexes

Four indexes optimize common query patterns:

### 1. `idx_filter`
```sql
CREATE INDEX idx_filter ON prices(service, region, os, tenancy, vcpu, hourly);
```

**Usage:** Filters combining service/region/os/tenancy/vcpu/hourly conditions.

**Example queries that use this index:**
```sql
SELECT * FROM prices
WHERE service = 'ec2' AND region = 'us-east-1' AND os = 'Linux'
  AND vcpu >= 4 AND vcpu <= 8
ORDER BY hourly ASC;
```

**Why it works:** Leading columns (`service`, `region`, `os`) allow index seek; `tenancy`, `vcpu`, `hourly` can also be used for filtering/sorting.

### 2. `idx_instance`
```sql
CREATE INDEX idx_instance ON prices(service, instance_type);
```

**Usage:** Lookup by specific instance type.

**Example:**
```sql
SELECT * FROM prices
WHERE service = 'ec2' AND instance_type = 'm5.large';
```

### 3. `idx_price`
```sql
CREATE INDEX idx_price ON prices(service, region, purchase_option, hourly);
```

**Usage:** Price-based sorting and filtering across services/regions.

**Example:**
```sql
SELECT service, region, instance_type, hourly
FROM prices
WHERE service = 'ec2' AND region = 'us-east-1'
  AND purchase_option = 'OnDemand'
  AND hourly <= 0.1
ORDER BY hourly ASC;
```

**Note:** This index is similar to `idx_filter` but without `os`/`tenancy`/`vcpu`. Use `idx_filter` for most queries; `idx_price` may be chosen for pure price scans.

### 4. `idx_specs`
```sql
CREATE INDEX idx_specs ON prices(vcpu, memory_gb, storage_type);
```

**Usage:** Hardware specification searches when not filtering by `service`/`region`.

**Example:**
```sql
SELECT service, region, instance_type, vcpu, memory_gb, hourly
FROM prices
WHERE vcpu >= 4 AND vcpu <= 8
  AND memory_gb >= 16
  AND storage_type = 'ebs';
```

**Note:** This index doesn't include `service` or `region`, so it may require scanning many rows if those aren't also filtered.

## Query Planning

Check if your query uses indexes:
```sql
EXPLAIN QUERY PLAN
SELECT * FROM prices
WHERE service = 'ec2' AND vcpu >= 4;
```

**Good output:**
```
SEARCH TABLE prices USING INDEX idx_filter (service=? AND vcpu>=?)
```

**Bad output:**
```
SCAN TABLE prices
```

If you see `SCAN TABLE`, your query isn't using an index. Add more restrictive filters or create a new index.

## Sample Queries

### Basic Filtering

```sql
-- Find cheapest EC2 instances with >=4 vCPUs, Linux
SELECT service, region, instance_type, vcpu, memory_gb, hourly
FROM prices
WHERE service = 'ec2'
  AND vcpu >= 4
  AND os = 'Linux'
  AND purchase_option = 'OnDemand'
ORDER BY hourly ASC
LIMIT 10;
```

```sql
-- Find all RDS instances in us-east-1
SELECT instance_type, os, storage_type, hourly
FROM prices
WHERE service = 'rds'
  AND region = 'us-east-1'
  AND purchase_option = 'OnDemand';
```

### Price Ranges

```sql
-- Find instances between $0.05 and $0.20 per hour
SELECT service, region, instance_type, vcpu, memory_gb, hourly
FROM prices
WHERE hourly >= 0.05 AND hourly <= 0.20
  AND purchase_option = 'OnDemand';
```

### Instance Type Patterns

```sql
-- Find all M5 family instances
SELECT instance_type, vcpu, memory_gb, hourly
FROM prices
WHERE instance_type LIKE 'm5.%'
  AND os = 'Linux'
LIMIT 20;
```

```sql
-- Find all xlarge instances (any family)
SELECT service, region, instance_type, vcpu, memory_gb, hourly
FROM prices
WHERE instance_type LIKE '%xlarge'
ORDER BY vcpu DESC;
```

### Aggregation

```sql
-- Count instances by region
SELECT region, COUNT(*) as instance_count
FROM prices
WHERE service = 'ec2'
GROUP BY region
ORDER BY instance_count DESC;
```

```sql
-- Average price by instance family
SELECT family, AVG(hourly) as avg_hourly, COUNT(*) as count
FROM prices
WHERE service = 'ec2' AND vcpu > 0
GROUP BY family
HAVING count > 10
ORDER BY avg_hourly DESC;
```

### Reserved vs On-Demand Comparison

```sql
-- Compare On-Demand vs 1yr AllUpfront Reserved pricing
WITH ondemand AS (
  SELECT instance_type, region, os, hourly as ondemand_hourly
  FROM prices
  WHERE service = 'ec2'
    AND purchase_option = 'OnDemand'
    AND os = 'Linux'
),
reserved AS (
  SELECT instance_type, region, os, hourly as reserved_hourly,
         upfront_cost, lease_term, purchase_option_reserved
  FROM prices
  WHERE service = 'ec2'
    AND purchase_option = 'Reserved'
    AND lease_term = '1yr'
    AND purchase_option_reserved = 'AllUpfront'
    AND os = 'Linux'
)
SELECT r.instance_type, r.region,
       o.ondemand_hourly, r.reserved_hourly,
       r.upfront_cost,
       ((o.ondemand_hourly - r.reserved_hourly) / o.ondemand_hourly * 100) as hourly_savings_pct,
       (r.upfront_cost / (o.ondemand_hourly - r.reserved_hourly)) as break_even_months
FROM reserved r
JOIN ondemand o USING (instance_type, region, os)
WHERE o.ondemand_hourly IS NOT NULL AND r.reserved_hourly IS NOT NULL
ORDER BY hourly_savings_pct DESC
LIMIT 20;
```

### Multi-Service Overview

```sql
-- Count of On-Demand instances by service and OS
SELECT service, os, COUNT(*) as count, MIN(hourly) as min_hourly, MAX(hourly) as max_hourly
FROM prices
WHERE purchase_option = 'OnDemand'
GROUP BY service, os
ORDER BY service, count DESC;
```

```sql
-- Find GPU instances with hourly pricing
SELECT service, region, instance_type, gpu, gpu_memory_gb, hourly
FROM prices
WHERE gpu > 0
  AND hourly IS NOT NULL
ORDER BY gpu DESC, hourly ASC;
```

### Regional Price Differences

```sql
-- Price variation for m5.large across regions
SELECT region, hourly
FROM prices
WHERE service = 'ec2'
  AND instance_type = 'm5.large'
  AND os = 'Linux'
  AND purchase_option = 'OnDemand'
ORDER BY hourly DESC;
```

### Storage Options

```sql
-- Find instances with instance store (ephemeral) storage
SELECT service, region, instance_type, storage, storage_gb, storage_type
FROM prices
WHERE storage_type = 'Instance Store'
  AND storage_gb > 0
ORDER BY storage_gb DESC;
```

## Performance Tips

1. **Use covering indexes:** If you only need specific columns, the index can satisfy the query without table lookup. The `idx_filter` covers queries for `(service, region, os, tenancy, vcpu, hourly)`.

2. **Filter early and often:** Add `WHERE` conditions that match index columns. More selective filters → fewer rows scanned.

3. **Avoid `SELECT *` in production:** Enumerate required columns to enable index-only scans:
   ```sql
   SELECT service, region, instance_type, vcpu, memory_gb, hourly
   FROM prices
   WHERE ...
   ```

4. **Order by indexed columns:** Sorting by `hourly` works efficiently if the query includes `service` and `region` (via `idx_filter` or `idx_price`). Sorting by random columns forces a filesort.

5. **Use `LIMIT`:** The app enforces `LIMIT 1000`. This stops scanning after enough rows are found, using index ordering if available.

6. **Check `EXPLAIN QUERY PLAN`:** Test complex queries to verify index usage.

7. **Parameter binding:** Always use `?` placeholders (done automatically by `buildWhereClause`). This enables SQLite to cache query plans.

## Limitations

- **Parameter count:** SQLite has a hard limit of 999 bound parameters per query. The UI's multi-select filters with many values could theoretically exceed this if combined with many range expressions. Practically unlikely (e.g., 50 regions × 3 range clauses = 150 parameters).

- **No full-text search:** The `LIKE` operator with leading wildcard (`%prefix`) cannot use indexes. `starts_with()` is efficient (`prefix%`), but `has()` and `ends_with()` require full scans. Use sparingly.

- **Static data:** Prices are snapshots from AWS Price List API. Query results reflect data at time of database generation, not real-time.

- **No JOINs:** All data is denormalized into single table. Relationships (e.g., service → region availability) are implicit.

## Schema Evolution

When updating the schema:

1. Add new columns as `NULL` or with `DEFAULT` to preserve existing rows
2. Update `PriceRow` dataclass and `CREATE_TABLE_SQL`
3. Update `normalize_product()` to populate new columns
4. Add new indexes as needed (separate from existing ones)
5. Document changes in this API reference

**Migration:** Since the database is regenerated entirely from raw data, schema changes are breaking but straightforward: delete old DB and recreate.

---

*Schema definition source:* `pipeline/schema.py`  
*Data generation:* `pipeline/normalize.py`, `pipeline/generate_db.py`
