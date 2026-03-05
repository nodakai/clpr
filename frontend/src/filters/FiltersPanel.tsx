import React, { useState, useCallback, memo, useMemo } from 'react';
import type { Filters as ExternalFilters } from './types';
import { OS_OPTIONS, TENANCY_OPTIONS, PURCHASE_OPTIONS, STORAGE_OPTIONS } from './types';
import RegionFilter from './RegionFilter';
import ServiceFilter from './ServiceFilter';
import RangeFilter from './RangeFilter';
import SelectFilter from './SelectFilter';
import './Filters.css';

interface InternalFilters {
  service: string[];
  region: string[];
  storage: string[];
  vcpu: { min?: number; max?: number };
  memory_gb: { min?: number; max?: number };
  os: string[];
  tenancy: string[];
  purchase_option: string[];
  hourly: { min?: number; max?: number };
}

const internalEmptyFilters: InternalFilters = {
  service: [],
  region: [],
  storage: [],
  vcpu: {},
  memory_gb: {},
  os: [],
  tenancy: [],
  purchase_option: [],
  hourly: {},
};

interface FiltersPanelProps {
  onFiltersChanged: (filters: ExternalFilters) => void;
  filters: ExternalFilters;
  activeFiltersCount?: number;
  showActiveFilters?: boolean;
}

type AccordionSection = 
  | 'region' 
  | 'service'
  | 'storage'
  | 'vcpu' 
  | 'memory' 
  | 'os' 
  | 'tenancy' 
  | 'purchase'
  | 'price';

const convertToExternal = (filters: InternalFilters): ExternalFilters => {
  const rangeToString = (r: { min?: number; max?: number }): string => {
    if (r.min !== undefined && r.max !== undefined) return `${r.min}..${r.max}`;
    if (r.min !== undefined) return `>=${r.min}`;
    if (r.max !== undefined) return `<=${r.max}`;
    return '';
  };

  return {
    service: filters.service[0] || '',
    region: filters.region,
    storage_type: filters.storage,
    vcpu: rangeToString(filters.vcpu),
    memory_gb: rangeToString(filters.memory_gb),
    os: filters.os,
    tenancy: filters.tenancy,
    purchase_option: filters.purchase_option,
    price_hourly_min: filters.hourly.min,
    price_hourly_max: filters.hourly.max,
  };
};

const stringToRange = (s: string): { min?: number; max?: number } => {
  if (!s) return {};
  if (s.includes('..')) {
    const [minStr, maxStr] = s.split('..');
    return { min: parseFloat(minStr), max: parseFloat(maxStr) };
  }
  const minMatch = s.match(/(?:>=|>)\s*(\d+(?:\.\d+)?)/);
  const maxMatch = s.match(/(?:<=|<)\s*(\d+(?:\.\d+)?)/);
  const result: { min?: number; max?: number } = {};
  if (minMatch) result.min = parseFloat(minMatch[1]);
  if (maxMatch) result.max = parseFloat(maxMatch[1]);
  return result;
};

const convertExternalToInternal = (ext: ExternalFilters): InternalFilters => {
  return {
    service: ext.service ? [ext.service] : [],
    region: Array.isArray(ext.region) ? ext.region : (ext.region ? [ext.region] : []),
    storage: Array.isArray(ext.storage_type) ? ext.storage_type : (ext.storage_type ? [ext.storage_type] : []),
    vcpu: stringToRange(ext.vcpu || ''),
    memory_gb: stringToRange(ext.memory_gb || ''),
    os: Array.isArray(ext.os) ? ext.os : (ext.os ? [ext.os] : []),
    tenancy: Array.isArray(ext.tenancy) ? ext.tenancy : (ext.tenancy ? [ext.tenancy] : []),
    purchase_option: Array.isArray(ext.purchase_option) ? ext.purchase_option : (ext.purchase_option ? [ext.purchase_option] : []),
    hourly: {
      min: ext.price_hourly_min,
      max: ext.price_hourly_max,
    },
  };
};

const FiltersPanel: React.FC<FiltersPanelProps> = ({ 
  onFiltersChanged, 
  filters,
  activeFiltersCount = 0,
  showActiveFilters = false 
}) => {
  const internalFilters = useMemo<InternalFilters>(() => 
    convertExternalToInternal(filters),
    [filters]
  );
  
  const [expandedSections, setExpandedSections] = useState<AccordionSection[]>([
    'region',
    'service',
    'storage',
    'vcpu',
    'memory',
    'os',
    'tenancy',
    'purchase',
    'price',
  ]);

  const updateFilter = useCallback(<K extends keyof InternalFilters>(
    key: K,
    value: InternalFilters[K]
  ) => {
    const newInternal = { ...internalFilters, [key]: value };
    const external = convertToExternal(newInternal);
    onFiltersChanged(external);
  }, [internalFilters, onFiltersChanged]);

  const toggleSection = (section: AccordionSection) => {
    setExpandedSections((prev) =>
      prev.includes(section)
        ? prev.filter((s) => s !== section)
        : [...prev, section]
    );
  };

  const clearAll = useCallback(() => {
    onFiltersChanged(convertToExternal(internalEmptyFilters));
  }, [onFiltersChanged]);

  // Get active filter labels for summary
  const getActiveFilterLabels = () => {
    const labels: string[] = [];
    if (internalFilters.service.length) labels.push(`Service: ${internalFilters.service.join(', ')}`);
    if (internalFilters.region.length) labels.push(`Region: ${internalFilters.region.join(', ')}`);
    if (internalFilters.storage.length) labels.push(`Storage: ${internalFilters.storage.join(', ')}`);
    if (internalFilters.vcpu.min !== undefined || internalFilters.vcpu.max !== undefined) {
      labels.push(`vCPU: ${internalFilters.vcpu.min ?? 'any'} - ${internalFilters.vcpu.max ?? 'any'}`);
    }
    if (internalFilters.memory_gb.min !== undefined || internalFilters.memory_gb.max !== undefined) {
      labels.push(`Memory: ${internalFilters.memory_gb.min ?? 'any'} - ${internalFilters.memory_gb.max ?? 'any'} GB`);
    }
    if (internalFilters.os.length) labels.push(`OS: ${internalFilters.os.join(', ')}`);
    if (internalFilters.tenancy.length) labels.push(`Tenancy: ${internalFilters.tenancy.join(', ')}`);
    if (internalFilters.purchase_option.length) labels.push(`Purchase: ${internalFilters.purchase_option.join(', ')}`);
    if (internalFilters.hourly.min !== undefined || internalFilters.hourly.max !== undefined) {
      labels.push(`Price: $${internalFilters.hourly.min ?? '0'} - ${internalFilters.hourly.max ?? '∞'}/hr`);
    }
    return labels;
  };

  const handleVcpuChange = (min?: number, max?: number) => {
    updateFilter('vcpu', { min, max });
  };

  const handleMemoryChange = (min?: number, max?: number) => {
    updateFilter('memory_gb', { min, max });
  };

  const handleHourlyChange = (min?: number, max?: number) => {
    updateFilter('hourly', { min, max });
  };

  return (
    <div className="filters-panel" role="region" aria-label="Filters">
      <div className="filters-header">
        <h2>Filters</h2>
        <button 
          type="button" 
          className="clear-all-btn" 
          onClick={clearAll}
          aria-label="Clear all filters"
          disabled={activeFiltersCount === 0}
        >
          Clear All
        </button>
      </div>

      {/* Active filters summary */}
      {showActiveFilters && activeFiltersCount > 0 && (
        <div className="active-filters-summary" aria-live="polite">
          <div className="summary-header">
            <span className="summary-count">{activeFiltersCount} active</span>
            <button 
              type="button"
              className="summary-clear"
              onClick={clearAll}
              aria-label="Clear all filters"
            >
              Clear all
            </button>
          </div>
          <div className="summary-list">
            {getActiveFilterLabels().map((label, idx) => (
              <span key={idx} className="filter-tag">
                {label}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="filters-sections">
        {/* Region Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('region') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('region')}
          >
            <span className="toggle-icon">{expandedSections.includes('region') ? '▼' : '▶'}</span>
            <span>Region</span>
            {internalFilters.region.length > 0 && (
              <span className="filter-count">{internalFilters.region.length}</span>
            )}
          </button>
          {expandedSections.includes('region') && (
            <RegionFilter
              selected={internalFilters.region}
              onChange={(region) => updateFilter('region', region)}
            />
          )}
        </div>

        {/* Service Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('service') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('service')}
          >
            <span className="toggle-icon">{expandedSections.includes('service') ? '▼' : '▶'}</span>
            <span>Service</span>
            {internalFilters.service.length > 0 && (
              <span className="filter-count">{internalFilters.service.length}</span>
            )}
          </button>
          {expandedSections.includes('service') && (
            <ServiceFilter
              selected={internalFilters.service}
              onChange={(service) => updateFilter('service', service)}
            />
          )}
         </div>

         {/* Storage Section */}
         <div className={`filter-section-wrapper ${expandedSections.includes('storage') ? 'expanded' : ''}`}>
           <button
             type="button"
             className="section-toggle"
             onClick={() => toggleSection('storage')}
           >
             <span className="toggle-icon">{expandedSections.includes('storage') ? '▼' : '▶'}</span>
             <span>Storage</span>
             {internalFilters.storage.length > 0 && (
               <span className="filter-count">{internalFilters.storage.length}</span>
             )}
           </button>
           {expandedSections.includes('storage') && (
             <SelectFilter
               label="Storage Type"
               options={STORAGE_OPTIONS}
               selected={internalFilters.storage}
               onChange={(storage) => updateFilter('storage', storage)}
             />
           )}
         </div>

         {/* vCPU Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('vcpu') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('vcpu')}
          >
            <span className="toggle-icon">{expandedSections.includes('vcpu') ? '▼' : '▶'}</span>
            <span>vCPUs</span>
            {(internalFilters.vcpu.min !== undefined || internalFilters.vcpu.max !== undefined) && (
              <span className="filter-count">active</span>
            )}
          </button>
          {expandedSections.includes('vcpu') && (
            <RangeFilter
              label="vCPUs"
              min={internalFilters.vcpu.min}
              max={internalFilters.vcpu.max}
              onChange={handleVcpuChange}
            />
          )}
        </div>

        {/* Memory Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('memory') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('memory')}
          >
            <span className="toggle-icon">{expandedSections.includes('memory') ? '▼' : '▶'}</span>
            <span>Memory (GB)</span>
            {(internalFilters.memory_gb.min !== undefined || internalFilters.memory_gb.max !== undefined) && (
              <span className="filter-count">active</span>
            )}
          </button>
          {expandedSections.includes('memory') && (
            <RangeFilter
              label="Memory (GB)"
              min={internalFilters.memory_gb.min}
              max={internalFilters.memory_gb.max}
              onChange={handleMemoryChange}
            />
          )}
        </div>

        {/* Price Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('price') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('price')}
          >
            <span className="toggle-icon">{expandedSections.includes('price') ? '▼' : '▶'}</span>
            <span>Price (USD/hr)</span>
            {(internalFilters.hourly.min !== undefined || internalFilters.hourly.max !== undefined) && (
              <span className="filter-count">active</span>
            )}
          </button>
          {expandedSections.includes('price') && (
            <RangeFilter
              label="Price (USD/hr)"
              min={internalFilters.hourly.min}
              max={internalFilters.hourly.max}
              onChange={handleHourlyChange}
            />
          )}
        </div>

        {/* OS Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('os') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('os')}
          >
            <span className="toggle-icon">{expandedSections.includes('os') ? '▼' : '▶'}</span>
            <span>Operating System</span>
            {internalFilters.os.length > 0 && (
              <span className="filter-count">{internalFilters.os.length}</span>
            )}
          </button>
          {expandedSections.includes('os') && (
            <SelectFilter
              label="OS"
              options={OS_OPTIONS}
              selected={internalFilters.os}
              onChange={(os) => updateFilter('os', os)}
            />
          )}
        </div>

        {/* Tenancy Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('tenancy') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('tenancy')}
          >
            <span className="toggle-icon">{expandedSections.includes('tenancy') ? '▼' : '▶'}</span>
            <span>Tenancy</span>
            {internalFilters.tenancy.length > 0 && (
              <span className="filter-count">{internalFilters.tenancy.length}</span>
            )}
          </button>
          {expandedSections.includes('tenancy') && (
            <SelectFilter
              label="Tenancy"
              options={TENANCY_OPTIONS}
              selected={internalFilters.tenancy}
              onChange={(tenancy) => updateFilter('tenancy', tenancy)}
            />
          )}
        </div>

        {/* Purchase Option Section */}
        <div className={`filter-section-wrapper ${expandedSections.includes('purchase') ? 'expanded' : ''}`}>
          <button
            type="button"
            className="section-toggle"
            onClick={() => toggleSection('purchase')}
          >
            <span className="toggle-icon">{expandedSections.includes('purchase') ? '▼' : '▶'}</span>
            <span>Purchase Option</span>
            {internalFilters.purchase_option.length > 0 && (
              <span className="filter-count">{internalFilters.purchase_option.length}</span>
            )}
          </button>
          {expandedSections.includes('purchase') && (
            <SelectFilter
              label="Purchase Option"
              options={PURCHASE_OPTIONS}
              selected={internalFilters.purchase_option}
              onChange={(purchase_option) => updateFilter('purchase_option', purchase_option)}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default memo(FiltersPanel);
