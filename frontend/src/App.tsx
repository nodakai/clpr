import React, { useState, useEffect, useCallback } from 'react';
import { database } from './db';
import { buildWhereClause } from './query-builder';
import type { Filters } from './query-builder';
import env from './env';
import FiltersPanel from './filters/FiltersPanel';
import ResultsTable from './table/ResultsTable';
import './index.css';
import './App.css';

const initialFilters: Filters = {
  service: 'ec2',
  region: [],
  vcpu: '',
  memory_gb: '',
  price_hourly_min: undefined,
  price_hourly_max: undefined,
  os: [],
  purchase_option: ['OnDemand'],
};

const App: React.FC = () => {
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [data, setData] = useState<Record<string, any>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [sortColumn, setSortColumn] = useState<string>('');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [totalRows, setTotalRows] = useState<number>(0);
  const [bytesRead, setBytesRead] = useState<number>(0);
  const [queryTime, setQueryTime] = useState<number>(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('darkMode');
    if (saved !== null) {
      return JSON.parse(saved);
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  const [dbReady, setDbReady] = useState(false);

  // Handle dark mode toggle
  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode));
    if (darkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  }, [darkMode]);

  // Close mobile menu on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [mobileMenuOpen]);

  // Initialize database on mount
  useEffect(() => {
    database.init()
      .then(() => setDbReady(true))
     .catch(err => {
       if (env.DEV) {
         console.error('Database initialization failed:', err);
       }
       setError('Failed to initialize database');
     });
    return () => {
      database.close().catch(() => {});
    };
  }, []);

  // Execute query
  const executeQuery = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    const startTime = performance.now();
    try {
      const { where, params } = buildWhereClause(filters);
      const orderBy = sortColumn ? `${sortColumn} ${sortDirection}` : '';
      const sql = `SELECT * FROM prices${where ? ' WHERE ' + where : ''}${orderBy ? ' ORDER BY ' + orderBy : ''} LIMIT 1000`;

      // Debug logging in development
      if (env.DEV) {
        console.log('[DEBUG] SQL:', sql);
        console.log('[DEBUG] Params:', params);
      }

      const result = await database.query(sql, params);
      setData(result);
      setTotalRows(result.length);
      const bytes = await database.getBytesRead();
      setBytesRead(bytes);
      const endTime = performance.now();
      setQueryTime(endTime - startTime);
    } catch (err: any) {
      setError(err.message || 'Query failed');
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [filters, sortColumn, sortDirection]);

  // Debounced query execution
  useEffect(() => {
    if (!dbReady) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      if (!cancelled) {
        executeQuery();
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [dbReady, filters, sortColumn, sortDirection, executeQuery]);

  // Sort handler
  const handleSort = useCallback((column: string) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  }, [sortColumn]);

  const toggleMobileMenu = useCallback(() => {
    setMobileMenuOpen(prev => !prev);
  }, []);

  const clearAllFilters = useCallback(() => {
    setFilters(initialFilters);
    setMobileMenuOpen(false);
  }, []);

  // Notify other components when filters are cleared
  useEffect(() => {
    const handleClearAll = () => {
      clearAllFilters();
    };
    window.addEventListener('clearAllFilters', handleClearAll);
    return () => window.removeEventListener('clearAllFilters', handleClearAll);
  }, [clearAllFilters]);

  const getActiveFiltersCount = useCallback(() => {
    let count = 0;
    if (filters.service) count++;
    if (filters.region?.length) count++;
    if (filters.storage_type?.length) count++;
    if (filters.vcpu) count++;
    if (filters.memory_gb) count++;
    if (filters.os?.length) count++;
    if (filters.tenancy?.length) count++;
    if (filters.purchase_option?.length) count++;
    if (filters.price_hourly_min !== undefined || filters.price_hourly_max !== undefined) count++;
    return count;
  }, [filters]);

  return (
    <div className="app">
      {/* Hamburger menu button for mobile */}
      <button
        className={`menu-toggle ${mobileMenuOpen ? 'active' : ''}`}
        onClick={toggleMobileMenu}
        aria-label={mobileMenuOpen ? 'Close filters menu' : 'Open filters menu'}
        aria-expanded={mobileMenuOpen}
      >
        <span></span>
        <span></span>
        <span></span>
      </button>

      {/* Mobile overlay */}
      <div
        className={`mobile-overlay ${mobileMenuOpen ? 'active' : ''}`}
        onClick={() => setMobileMenuOpen(false)}
        aria-hidden="true"
      />

      <header className="app-header">
        <div className="header-content">
          <h1>AWS Pricing Calculator</h1>
          <p>Search and filter AWS service pricing data. Results update automatically as you change filters.</p>
        </div>
        <button
          className="theme-toggle"
          onClick={() => setDarkMode(!darkMode)}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
      </header>
      <main className="app-main">
        <aside className={`filters-sidebar ${mobileMenuOpen ? 'panel-open' : ''}`}>
          <FiltersPanel 
            onFiltersChanged={setFilters} 
            filters={filters}
            activeFiltersCount={getActiveFiltersCount()}
            showActiveFilters={true}
          />
        </aside>
         <section className="results">
            <ResultsTable 
              data={data}
              loading={loading}
              error={error}
              filters={filters}
              onSort={handleSort}
              sortColumn={sortColumn}
              sortDirection={sortDirection}
              queryTime={queryTime}
              totalRows={totalRows}
              activeFiltersCount={getActiveFiltersCount()}
              onClearFilters={clearAllFilters}
            />
          </section>
      </main>
      <footer className="app-footer">
        <div className="footer-content">
          {queryTime > 0 && (
            <span>Query executed in {queryTime.toFixed(0)}ms</span>
          )}
          {queryTime > 0 && (
            <span style={{ marginLeft: '16px' }}>Bytes: {bytesRead}</span>
          )}
          <div className="footer-disclaimer">
            <span>Data sourced from AWS Price List API</span>
            <span style={{ marginLeft: '12px' }}>Tool not affiliated with AWS</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
