# End-to-End Integration Test & Instructions

## Test Scripts

### 1. `pipeline/test_integration.py`

Complete integration test that validates:
- Mock normalization with sample EC2 products
- In-memory database creation and querying
- Full pipeline with temporary files
- Optional real AWS API download (EC2 us-east-1 only)

**Usage:**
```bash
cd pipeline
python test_integration.py                    # Run mock tests only
python test_integration.py --real             # Include real AWS download test
python test_integration.py -h                 # Show help
```

**Test Coverage:**
- `test_mock_normalization()` - Tests normalize_product with mock EC2 data
- `test_in_memory_database()` - Tests SQLite schema and inserts
- `test_temp_file_database()` - Tests generate_database() end-to-end
- `test_real_download_single_service()` - Downloads real EC2 us-east-1 data

---

### 2. `pipeline/download_filtered.py`

Modified downloader for targeted small downloads (EC2 us-east-1 only).
**Use this to generate a small test database (<50MB).**

**Usage:**
```bash
cd pipeline
python download_filtered.py
```

Output: `data/raw/AmazonEC2.json` (single service, single region)

---

## Running Full Pipeline with Real Data (Small Dataset)

### Step 1: Install Dependencies

```bash
cd pipeline
pip install -r requirements.txt
```

Required packages: `boto3`, `ijson`, `click`, `tqdm`

### Step 2: Download EC2 us-east-1 Only

```bash
python download_filtered.py
```

Expected output:
```
✓ EC2 us-east-1 download complete
```

Verify file exists and size:
```bash
ls -lh data/raw/AmazonEC2.json
```

Expected: 10-50 MB (depending on data)

---

### Step 3: Generate Database

```bash
python -m pipeline generate --output data/aws_pricing_test.sqlite3
```

Or use the script directly:
```bash
python -c "from pipeline.generate_db import generate_database; generate_database('data/aws_pricing_test.sqlite3')"
```

This will:
- Read `data/raw/AmazonEC2.json`
- Normalize to `data/aws_pricing_test.sqlite3`
- Create indexes and optimize
- Run validation

Expected validation:
```
Database size: X.XX MB
Total rows in prices table: > 1000
All 4 indexes verified
Query plan indicates index usage
Database generation and validation completed successfully!
```

---

### Step 4: Validate Database

**Quick validation (CI mode):**
```bash
python -m pipeline validate --db-path data/aws_pricing_test.sqlite3
```

**Comprehensive validation:**
```bash
python -m pipeline test_db --db-path data/aws_pricing_test.sqlite3
```

Expected: All critical checks pass

---

### Step 5: Verify Queries Work

```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/aws_pricing_test.sqlite3')
cursor = conn.cursor()

print('=== Sample Queries ===')

# Query 1: EC2 instances with vcpu >= 4
cursor.execute('''
    SELECT instance_type, region, os, hourly 
    FROM prices 
    WHERE service='ec2' AND vcpu >= 4 
    LIMIT 5
''')
rows = cursor.fetchall()
print(f'EC2 vCPU>=4 (showing {len(rows)} of many):')
for row in rows:
    print(f'  {row[0]} | {row[1]} | {row[2]} | \${row[3]}/hr')

# Query 2: Count by instance family
cursor.execute('''
    SELECT instance_type, COUNT(*) as count, AVG(hourly) as avg_price
    FROM prices 
    WHERE service='ec2' 
    GROUP BY instance_type 
    ORDER BY count DESC 
    LIMIT 5
''')
rows = cursor.fetchall()
print('\nTop instance types by count:')
for row in rows:
    print(f'  {row[0]}: {row[1]} instances, avg \${row[2]:.3f}/hr')

# Query 3: Reserved vs OnDemand
cursor.execute('''
    SELECT purchase_option, COUNT(*), AVG(hourly) 
    FROM prices 
    WHERE service='ec2' AND hourly IS NOT NULL 
    GROUP BY purchase_option
''')
rows = cursor.fetchall()
print('\nPricing options:')
for row in rows:
    print(f'  {row[0]}: {row[1]} rows, avg \${row[2]:.3f}/hr')

conn.close()
print('\n✓ All queries executed successfully')
"
```

---

## Testing Frontend Database Loading

### Option A: Local Development Server (Recommended)

1. Copy test database to frontend public folder:
```bash
cp data/aws_pricing_test.sqlite3 frontend/public/data/
```

2. Set test database environment variable:
```bash
cd frontend
VITE_USE_TEST_DB=true npm run dev
```

The frontend will load `/data/aws_pricing_test.sqlite3` instead of production DB.

3. Open http://localhost:5173
   - Database should initialize
   - Console shows "Database opened, bytes read: X"
   - Filters UI should display EC2 data

4. Test sample query via browser console:
```javascript
import { database } from './src/db';

await database.init();

const results = await database.query(`
  SELECT instance_type, region, os, hourly 
  FROM prices 
  WHERE service='ec2' AND vcpu >= 4 
  LIMIT 5
`);
console.log('Query results:', results);
```

### Option B: Build and Preview Static

```bash
cd frontend
VITE_USE_TEST_DB=true npm run build
npm run preview
```

---

## Test Results File

After running tests, document results in `INTEGRATION_TEST_RESULTS.md`:

```markdown
# Integration Test Results

## Date
2025-03-04

## Environment
- OS: darwin
- Python: (version)
- AWS credentials: (configured / not configured)

## Test Summary

### Mock Tests
- [x] test_mock_normalization
- [x] test_in_memory_database
- [x] test_temp_file_database

### Real Data Tests (if run)
- [ ] Real EC2 download (us-east-1)
- [ ] Full pipeline generation
- [ ] Validation passed
- [ ] Sample queries executed

## Database Stats
- File size: XX MB
- Total rows: X,XXX
- Services: (list)
- Indexes: all present

## Queries Verified
- [ ] Filter by service/region/vcpu
- [ ] Aggregation queries
- [ ] Index usage (EXPLAIN QUERY PLAN)

## Frontend
- [ ] Database loads in dev mode
- [ ] Sample query from browser console
- [ ] UI filters work

## Issues / Notes
(Any problems encountered)
```

---

## Quick Reference Commands

```bash
# Setup
cd pipeline
pip install -r requirements.txt

# Run mock integration test
python test_integration.py

# Run full test with real AWS data (EC2 only)
python test_integration.py --real

# Manual small pipeline
python download_filtered.py
python -m pipeline generate --output data/aws_pricing_test.sqlite3

# Validate
python -m pipeline validate --db-path data/aws_pricing_test.sqlite3
python -m pipeline test_db --db-path data/aws_pricing_test.sqlite3

# Frontend test
cd frontend
cp ../data/aws_pricing_test.sqlite3 public/data/
VITE_USE_TEST_DB=true npm run dev
```

---

## Expected Test Database Size

- With EC2 us-east-1 only: ~10-50 MB
- Full pipeline (all services, all regions): ~200-500 MB (production target)

If test DB exceeds 50 MB, truncate or filter more aggressively.

---

## Troubleshooting

**boto3 import errors:**
```bash
pip install boto3 botocore ijson tqdm
```

**Database validation fails:**
- Check `data/raw/` contains at least one JSON file
- Ensure `schema.py` indexes are created
- Run `python -m pipeline normalize` manually

**Frontend fails to load DB:**
- Ensure CORS headers allow Range requests (GitHub Pages OK)
- Check browser console for SharedArrayBuffer errors (need cross-origin isolation)
- Verify DB file is in `frontend/public/data/` or served at correct URL
- Check MIME type: SQLite files must be served as `application/octet-stream`

**SharedArrayBuffer errors:**
The browser requires cross-origin isolation. For local testing, you may need:
- Chrome: `--cross-origin-isolated` flag
- Or use a proxy that sets `Cross-Origin-Embedder-Policy: require-corp`

For GitHub Pages, use a fallback message or test with generated data only.

---

## Automated Test Script

Create `run_all_tests.sh`:

```bash
#!/bin/bash
set -e

echo "=== Integration Test Runner ==="

# 1. Install dependencies
echo "[1/6] Installing dependencies..."
cd pipeline
pip install -q boto3 ijson click tqdm

# 2. Run mock tests
echo "[2/6] Running mock integration tests..."
python test_integration.py

# 3. Optional real download (if AWS credentials exist)
if [ "$1" = "--with-real" ]; then
    echo "[3/6] Downloading real EC2 data (us-east-1)..."
    python download_filtered.py
    
    echo "[4/6] Generating database..."
    rm -f data/aws_pricing_test.sqlite3
    python -c "from pipeline.generate_db import generate_database; generate_database('data/aws_pricing_test.sqlite3')"
    
    echo "[5/6] Validating database..."
    python -m pipeline validate --db-path data/aws_pricing_test.sqlite3
    python -m pipeline test_db --db-path data/aws_pricing_test.sqlite3
fi

# 6. Frontend prep
echo "[6/6] Preparing frontend test..."
cd ../frontend
if [ -f "../data/aws_pricing_test.sqlite3" ]; then
    mkdir -p public/data
    cp ../data/aws_pricing_test.sqlite3 public/data/
    echo "Test database copied to frontend/public/data/"
    echo "Run: cd frontend && VITE_USE_TEST_DB=true npm run dev"
fi

echo "=== All tests complete ==="
```

Make executable: `chmod +x run_all_tests.sh`

---

## Test Success Criteria

- [x] All mock tests pass without errors
- [ ] Real download completes (optional, if AWS creds available)
- [ ] Database file created with size 10-50 MB
- [ ] Validation passes: all indexes present, no NULLs in critical columns
- [ ] Sample queries return results (verified manually or via script)
- [ ] Frontend can load database (optional UI test)

---

## Notes

- The test script uses **mock data** to avoid AWS API rate limits and costs
- Real download test is **optional** and requires valid AWS credentials
- All tests should work without AWS credentials (using mocks)
- The small dataset (EC2 us-east-1) is sufficient to validate the entire pipeline
- Frontend testing can be done entirely offline with the generated SQLite file
