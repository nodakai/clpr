const { chromium } = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Configuration
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const USE_TEST_DB = process.env.USE_TEST_DB === 'true';
const DB_FILENAME = USE_TEST_DB ? 'test_aws_pricing.sqlite3' : 'aws_pricing.sqlite3';
const OUTPUT_DIR = process.env.OUTPUT_DIR || 'benchmark_results';

/**
 * Measure frontend load performance:
 * - WASM download + compilation time
 * - Database open time
 * - Time to first query
 * - Total HTTP requests and bytes transferred
 */
async function runBenchmark() {
  console.log('='.repeat(80));
  console.log('FRONTEND PERFORMANCE BENCHMARK');
  console.log('='.repeat(80));
  console.log(`URL: ${FRONTEND_URL}`);
  console.log(`Database: ${DB_FILENAME}`);
  
  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)){
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }
  
  const results = {
    timestamp: new Date().toISOString(),
    url: FRONTEND_URL,
    database: DB_FILENAME,
    metrics: {}
  };
  
  const browser = await chromium.launch({
    headless: 'new',
    args: [
      '--enable-features=SharedArrayBuffer',
      '--disable-web-security',
      '--disable-site-isolation-trials'
    ]
  });
  
  try {
    const page = await browser.newPage();
    
    // Enable request/response tracking
    const requests = [];
    const responses = [];
    const bytesTransferred = { request: 0, response: 0 };
    
    page.on('request', (req) => {
      requests.push({
        url: req.url(),
        method: req.method(),
        time: Date.now()
      });
    });
    
    page.on('response', (res) => {
      const request = requests.find(r => r.url === res.url() && !r.response);
      if (request) {
        request.response = true;
        const contentLength = res.headers()['content-length'];
        const length = contentLength ? parseInt(contentLength, 10) : 0;
        bytesTransferred.response += length;
        responses.push({
          url: res.url(),
          status: res.status(),
          size: length
        });
      }
    });
    
    // Navigate and collect timing
    const navigationStart = Date.now();
    await page.goto(FRONTEND_URL, { waitUntil: 'networkidle0' });
    const navigationEnd = Date.now();
    
    results.metrics.navigationTime_ms = navigationEnd - navigationStart;
    results.metrics.totalRequests = responses.length;
    results.metrics.totalBytesTransferred_kb = bytesTransferred.response / 1024;
    
    console.log(`\n✓ Page loaded in ${results.metrics.navigationTime_ms}ms`);
    console.log(`  Total requests: ${responses.length}`);
    console.log(`  Total transferred: ${(bytesTransferred.response / 1024 / 1024).toFixed(2)} MB`);
    
    // Extract database initialization timing from console logs
    const dbMetrics = await page.evaluate(() => {
      // Wait for database to be initialized and return metrics
      return new Promise((resolve) => {
        // Check if database object is available
        const checkInterval = setInterval(() => {
          if (window.databaseMetrics) {
            clearInterval(checkInterval);
            resolve(window.databaseMetrics);
          }
        }, 100);
        
        // Timeout after 30 seconds
        setTimeout(() => {
          clearInterval(checkInterval);
          resolve({ error: 'Timeout waiting for database metrics' });
        }, 30000);
      });
    });
    
    if (dbMetrics && !dbMetrics.error) {
      results.metrics.dbInitTime_ms = dbMetrics.initTime;
      results.metrics.dbOpenTime_ms = dbMetrics.openTime;
      results.metrics.dbBytesRead = dbMetrics.bytesRead;
      results.metrics.firstQueryTime_ms = dbMetrics.firstQueryTime;
      results.metrics.totalQueries = dbMetrics.queryCount;
      
      console.log(`\nDatabase Metrics:`);
      console.log(`  Init time: ${dbMetrics.initTime}ms`);
      console.log(`  Open time: ${dbMetrics.openTime}ms`);
      console.log(`  Bytes read: ${(dbMetrics.bytesRead / 1024).toFixed(1)} KB`);
      console.log(`  Queries executed: ${dbMetrics.queryCount}`);
      console.log(`  First query: ${dbMetrics.firstQueryTime}ms after init`);
    } else {
      console.log('\n⚠ Could not extract database metrics from page.');
      console.log('  Ensure frontend is instrumented to expose database metrics.');
    }
    
    // Run sample queries and measure
    console.log('\nRunning sample queries...');
    const queryTimes = [];
    
    const queries = [
      { name: 'vCPU filter', sql: 'SELECT * FROM prices WHERE service="ec2" AND vcpu >= 4' },
      { name: 'Price range', sql: 'SELECT * FROM prices WHERE hourly BETWEEN 0.05 AND 0.20' },
      { name: 'Instance pattern', sql: 'SELECT * FROM prices WHERE instance_type LIKE "m5.%"' }
    ];
    
    for (const query of queries) {
      const start = Date.now();
      try {
        const result = await page.evaluate(async (sql) => {
          return await window.database.query(sql);
        }, query.sql);
        const elapsed = Date.now() - start;
        queryTimes.push({ name: query.name, elapsed, rowCount: result.length });
        console.log(`  ✓ ${query.name}: ${elapsed}ms, ${result.length} rows`);
      } catch (err) {
        console.log(`  ✗ ${query.name}: ${err.message}`);
      }
    }
    
    results.metrics.sampleQueries = queryTimes;
    
    // Capture network details for DB file specifically
    const dbRequests = responses.filter(r => r.url.includes(DB_FILENAME));
    if (dbRequests.length > 0) {
      results.metrics.dbFileRequests = dbRequests.length;
      results.metrics.dbFileBytes_kb = dbRequests.reduce((sum, r) => sum + r.size, 0) / 1024;
      console.log(`\nDatabase file transfers:`);
      console.log(`  Requests: ${dbRequests.length}`);
      console.log(`  Bytes: ${results.metrics.dbFileBytes_kb.toFixed(1)} KB`);
    }
    
    // Save detailed results
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const outputFile = path.join(OUTPUT_DIR, `frontend_benchmark_${timestamp}.json`);
    fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
    console.log(`\n✓ Results saved to ${outputFile}`);
    
    // Generate summary
    console.log('\n' + '='.repeat(80));
    console.log('SUMMARY');
    console.log('='.repeat(80));
    console.log(`Navigation: ${results.metrics.navigationTime_ms}ms`);
    console.log(`Total requests: ${responses.length}`);
    console.log(`Total transferred: ${(results.metrics.totalBytesTransferred_kb / 1024).toFixed(2)} MB`);
    if (results.metrics.dbInitTime_ms) {
      console.log(`DB init: ${results.metrics.dbInitTime_ms}ms`);
      console.log(`DB open: ${results.metrics.dbOpenTime_ms}ms`);
      console.log(`Bytes read: ${(results.metrics.dbBytesRead / 1024).toFixed(1)} KB`);
      console.log(`Queries: ${results.metrics.totalQueries}`);
    }
    
  } finally {
    await browser.close();
  }
}

// Instrument the frontend to expose database metrics
function injectMetricsInstrumentation() {
  return `
    <script>
      // Instrument Database class to collect metrics
      (function() {
        const originalInit = window.Database.prototype.init;
        const originalQuery = window.Database.prototype.query;
        const originalClose = window.Database.prototype.close;
        
        window.databaseMetrics = {
          initStart: null,
          initTime: null,
          openTime: null,
          bytesRead: 0,
          firstQueryTime: null,
          queryCount: 0,
          startTime: performance.now()
        };
        
        window.Database.prototype.init = async function() {
          window.databaseMetrics.initStart = performance.now();
          try {
            await originalInit.apply(this, arguments);
            window.databaseMetrics.initTime = Math.round(performance.now() - window.databaseMetrics.initStart);
            window.databaseMetrics.bytesRead = this.db ? this.db.worker.bytesRead : 0;
          } catch (err) {
            console.error('Init error:', err);
            throw err;
          }
        };
        
        window.Database.prototype.query = async function(sql, params) {
          if (!window.databaseMetrics.firstQueryTime && window.databaseMetrics.initTime) {
            window.databaseMetrics.firstQueryTime = Math.round(performance.now() - window.databaseMetrics.initStart);
          }
          window.databaseMetrics.queryCount++;
          return await originalQuery.apply(this, arguments);
        };
        
        // Poll for bytes read update
        setInterval(() => {
          if (window.database && window.database.db && window.database.db.worker) {
            window.databaseMetrics.bytesRead = window.database.db.worker.bytesRead;
          }
        }, 1000);
      })();
    </script>
  `;
}

runBenchmark().catch(err => {
  console.error('Benchmark failed:', err);
  process.exit(1);
});
