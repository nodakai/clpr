import React, { useState, useMemo, useCallback } from 'react';
import { Filters } from '../filters/types';
import { exportToCSV, exportToJSON, ExportMetadata } from '../utils/export';
import './ResultsTable.css';

interface ResultsTableProps {
  data: Record<string, any>[];
  loading: boolean;
  error?: string;
  filters?: Filters;
  onSort?: (column: string) => void;
  sortColumn?: string;
  sortDirection?: 'asc' | 'desc';
  queryTime?: number;
  totalRows?: number;
  activeFiltersCount?: number;
  onClearFilters?: () => void;
}

const DEFAULT_COLUMNS = [
  { key: 'service', label: 'Service', mobile: true },
  { key: 'region', label: 'Region', mobile: true },
  { key: 'instance_type', label: 'Instance Type', mobile: true },
  { key: 'vcpu', label: 'vCPU', mobile: true },
  { key: 'memory_gb', label: 'Memory', mobile: false },
  { key: 'storage_type', label: 'Storage', mobile: false },
  { key: 'os', label: 'OS', mobile: false },
  { key: 'hourly', label: 'Hourly', mobile: true },
  { key: 'monthly', label: 'Monthly', mobile: true },
];

const ROWS_PER_PAGE_OPTIONS = [25, 50, 100];

const MOBILE_BREAKPOINT = 768;

const formatPrice = (value: number, period: string): string => {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  return `$${value.toFixed(3)}/${period}`;
};

const formatMemory = (value: number): string => {
  if (value === null || value === undefined || isNaN(value)) return 'N/A';
  return `${value.toFixed(1)} GiB`;
};

const ResultsTable: React.FC<ResultsTableProps> = ({
  data,
  loading,
  error,
  filters,
  onSort,
  sortColumn,
  sortDirection,
  queryTime,
  totalRows: propTotalRows,
  activeFiltersCount = 0,
  onClearFilters,
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(
    new Set(DEFAULT_COLUMNS.map(col => col.key))
  );
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Handle responsive column visibility only when breakpoint changes
  React.useEffect(() => {
    let lastMobile = window.innerWidth < MOBILE_BREAKPOINT;
    // Apply initial mobile breakpoint
    if (lastMobile) {
      const mobileColumns = DEFAULT_COLUMNS.filter(col => col.mobile).map(col => col.key);
      setVisibleColumns(new Set(mobileColumns));
    }

    const handleResize = () => {
      const mobile = window.innerWidth < MOBILE_BREAKPOINT;
      if (mobile !== lastMobile) {
        lastMobile = mobile;
        if (mobile) {
          const mobileColumns = DEFAULT_COLUMNS.filter(col => col.mobile).map(col => col.key);
          setVisibleColumns(new Set(mobileColumns));
        } else {
          setVisibleColumns(new Set(DEFAULT_COLUMNS.map(col => col.key)));
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const totalRows = propTotalRows || data.length;

  const totalPages = useMemo(() => {
    return Math.ceil(data.length / rowsPerPage);
  }, [data.length, rowsPerPage]);

  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * rowsPerPage;
    const end = start + rowsPerPage;
    return data.slice(start, end);
  }, [data, currentPage, rowsPerPage]);

  const handleSort = useCallback((column: string) => {
    if (onSort) {
      onSort(column);
    }
  }, [onSort]);

  const toggleColumn = useCallback((columnKey: string) => {
    setVisibleColumns(prev => {
      const next = new Set(prev);
      if (next.has(columnKey)) {
        next.delete(columnKey);
      } else {
        next.add(columnKey);
      }
      return next;
    });
  }, []);

  const getVisibleColumnData = useCallback(() => {
    return DEFAULT_COLUMNS.filter(col => visibleColumns.has(col.key));
  }, [visibleColumns]);

  const getMetadata = useCallback((): ExportMetadata => {
    return {
      exportedAt: new Date().toISOString(),
      filters: filters,
      totalRows: data.length,
    };
  }, [filters, data.length]);

  const handleExportCSVPage = useCallback(() => {
    const columns = getVisibleColumnData();
    const columnKeys = columns.map(col => col.key);
    const columnLabels = columns.map(col => col.label);
    const pageData = paginatedData.map(row => {
      const newRow: Record<string, any> = {};
      columnKeys.forEach(key => {
        const value = row[key];
        if (key === 'hourly' || key === 'monthly') {
          newRow[key] = value != null ? `$${value.toFixed(3)}` : '';
        } else if (key === 'memory_gb') {
          newRow[key] = value != null ? value.toFixed(1) : '';
        } else if (key === 'vcpu') {
          newRow[key] = value != null ? value.toString() : '';
        } else {
          newRow[key] = value != null ? value.toString() : '';
        }
      });
      return newRow;
    });

    exportToCSV(
      pageData,
      columnLabels,
      'aws_pricing_page',
      { ...getMetadata(), totalRows: pageData.length }
    );
  }, [getVisibleColumnData, paginatedData, getMetadata]);

  const handleExportCSVAll = useCallback(() => {
    const columns = getVisibleColumnData();
    const columnKeys = columns.map(col => col.key);
    const columnLabels = columns.map(col => col.label);
    const allData = data.map(row => {
      const newRow: Record<string, any> = {};
      columnKeys.forEach(key => {
        const value = row[key];
        if (key === 'hourly' || key === 'monthly') {
          newRow[key] = value != null ? `$${value.toFixed(3)}` : '';
        } else if (key === 'memory_gb') {
          newRow[key] = value != null ? value.toFixed(1) : '';
        } else if (key === 'vcpu') {
          newRow[key] = value != null ? value.toString() : '';
        } else {
          newRow[key] = value != null ? value.toString() : '';
        }
      });
      return newRow;
    });

    exportToCSV(allData, columnLabels, 'aws_pricing_all', getMetadata());
  }, [data, getVisibleColumnData, getMetadata]);

  const handleExportJSONAll = useCallback(() => {
    const allData = data.map(row => {
      const newRow: Record<string, any> = {};
      DEFAULT_COLUMNS.forEach(col => {
        newRow[col.key] = row[col.key];
      });
      return newRow;
    });

    exportToJSON(allData, 'aws_pricing_all', getMetadata());
  }, [data, getMetadata]);

  const visibleColumnDefinitions = getVisibleColumnData();

  // Get sort aria attribute
  const getSortAria = (columnKey: string): 'ascending' | 'descending' | 'none' => {
    if (sortColumn === columnKey) {
      return sortDirection === 'asc' ? 'ascending' : 'descending';
    }
    return 'none';
  };

   if (loading) {
     return (
      <div className="results-table-container">
        <div className="table-wrapper loading-wrapper" aria-busy="true" aria-label="Loading results">
          <div className="loading-skeleton">
            <table className="results-table">
              <thead>
                <tr>
                  {visibleColumnDefinitions.map(col => (
                    <th key={col.key}>
                      <div className="skeleton-block header-skeleton" />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 10 }).map((_, rowIdx) => (
                  <tr key={rowIdx}>
                    {visibleColumnDefinitions.map(col => (
                      <td key={`${rowIdx}-${col.key}`}>
                        <div className="skeleton-block" />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="loading-text">Loading results...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="results-table-container">
        <div className="error-alert" role="alert">{error}</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="results-table-container">
        <div className="no-results">
          <div className="no-results-icon">🔍</div>
          <h3>No results found</h3>
          <p>Try adjusting your filters to see more results.</p>
          {activeFiltersCount > 0 && (
            <div className="active-filters-suggestion">
              <p>You have {activeFiltersCount} active filter{activeFiltersCount > 1 ? 's' : ''}:</p>
              <button 
                type="button"
                className="clear-filters-link"
                onClick={onClearFilters}
              >
                Clear all filters
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="results-table-container">
      <div className="table-controls">
        <div className="column-toggle">
          <span>Columns: </span>
          {DEFAULT_COLUMNS.map(col => (
            <label key={col.key} className="column-toggle-label">
              <input
                type="checkbox"
                checked={visibleColumns.has(col.key)}
                onChange={() => toggleColumn(col.key)}
                aria-label={`Toggle ${col.label} column`}
              />
              {col.label}
            </label>
          ))}
        </div>
        <div className="export-container">
          <button 
            className="export-button dropdown-toggle"
            onClick={() => setShowExportMenu(!showExportMenu)}
            aria-label="Export data"
            aria-haspopup="true"
            aria-expanded={showExportMenu}
          >
            Export ▼
          </button>
          {showExportMenu && (
            <div 
              className="export-menu" 
              role="menu"
              aria-label="Export options"
            >
              <button 
                role="menuitem"
                onClick={() => { handleExportCSVPage(); setShowExportMenu(false); }}
              >
                Export CSV (page)
              </button>
              <button 
                role="menuitem"
                onClick={() => { handleExportCSVAll(); setShowExportMenu(false); }}
              >
                Export CSV (all)
              </button>
              <button 
                role="menuitem"
                onClick={() => { handleExportJSONAll(); setShowExportMenu(false); }}
              >
                Export JSON (all)
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="table-wrapper">
        <table 
          className="results-table" 
          aria-label={`Results table showing ${totalRows} entries`}
        >
          <thead>
            <tr>
              {visibleColumnDefinitions.map(col => (
                <th
                  key={col.key}
                  className={`sortable ${sortColumn === col.key ? sortDirection : ''}`}
                  onClick={() => handleSort(col.key)}
                  scope="col"
                  aria-sort={sortColumn === col.key ? getSortAria(col.key) : undefined}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSort(col.key);
                    }
                  }}
                >
                  <span className="header-content">
                    {col.label}
                    {sortColumn === col.key && (
                      <span className="sort-indicator" aria-hidden="true">
                        {sortDirection === 'asc' ? '↑' : '↓'}
                      </span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((row, idx) => (
              <tr key={idx} tabIndex={0}>
                {visibleColumnDefinitions.map(col => {
                  let displayValue: string;
                  if (col.key === 'hourly') {
                    displayValue = formatPrice(row.hourly, 'hr');
                  } else if (col.key === 'monthly') {
                    displayValue = formatPrice(row.monthly, 'mo');
                  } else if (col.key === 'memory_gb') {
                    displayValue = formatMemory(row.memory_gb);
                  } else if (col.key === 'vcpu') {
                    displayValue = row.vcpu != null ? row.vcpu.toString() : 'N/A';
                  } else {
                    displayValue = row[col.key] != null ? row[col.key].toString() : 'N/A';
                  }
                  return <td key={col.key}>{displayValue}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <div className="pagination-info">
          Showing {(currentPage - 1) * rowsPerPage + 1} to{' '}
          {Math.min(currentPage * rowsPerPage, data.length)} of {totalRows.toLocaleString()} entries
          {queryTime !== undefined && queryTime > 0 && (
            <span className="query-time"> (Query: {queryTime.toFixed(0)}ms)</span>
          )}
        </div>
        <div className="pagination-controls">
          <select
            value={rowsPerPage}
            onChange={(e) => {
              setRowsPerPage(Number(e.target.value));
              setCurrentPage(1);
            }}
            aria-label="Rows per page"
          >
            {ROWS_PER_PAGE_OPTIONS.map(option => (
              <option key={option} value={option}>
                {option} per page
              </option>
            ))}
          </select>
          <button
            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
            aria-label="Previous page"
          >
            Previous
          </button>
          <span className="page-info">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
            disabled={currentPage === totalPages}
            aria-label="Next page"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default ResultsTable;
