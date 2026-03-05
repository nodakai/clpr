import React, { memo } from 'react';
import { SERVICES } from './types';
import './Filters.css';

interface ServiceFilterProps {
  selected: string[];
  onChange: (selected: string[]) => void;
}

const ServiceFilter: React.FC<ServiceFilterProps> = ({ selected, onChange }) => {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === '') {
      onChange([]);
    } else if (!selected.includes(value)) {
      onChange([value]);
    }
  };

  const handleClear = () => {
    onChange([]);
  };

  return (
    <div className="filter-section service-filter">
      <div className="filter-header">
        <h4 className="filter-title">Service</h4>
        {selected.length > 0 && (
          <button type="button" className="clear-btn" onClick={handleClear}>
            Clear
          </button>
        )}
      </div>
      <select
        value={selected[0] || ''}
        onChange={handleChange}
        className="service-select"
        aria-label="Service"
      >
        <option value="">All Services</option>
        {SERVICES.map((service) => (
          <option key={service} value={service}>
            {service.toUpperCase()}
          </option>
        ))}
      </select>
    </div>
  );
};

export default memo(ServiceFilter);
