import React, { useState, useCallback, memo } from 'react';
import './Filters.css';

interface RangeFilterProps {
  label: string;
  min: number | undefined;
  max: number | undefined;
  onChange: (min: number | undefined, max: number | undefined) => void;
  placeholder?: string;
}

const RangeFilter: React.FC<RangeFilterProps> = ({
  label,
  min,
  max,
  onChange,
  placeholder = 'e.g., >=4 && <=8',
}) => {
  const [expression, setExpression] = useState<string>('');

  const parseExpression = useCallback((expr: string): { min?: number; max?: number } => {
    const result: { min?: number; max?: number } = {};

    if (!expr.trim()) return result;

    // Match patterns like ">=4 && <=8" or "10..20"
    const minMatch = expr.match(/(?:>=|>)\s*(\d+(?:\.\d+)?)/);
    const maxMatch = expr.match(/(?:<=|<)\s*(\d+(?:\.\d+)?)/);
    const rangeMatch = expr.match(/(\d+(?:\.\d+)?)\s*\.\.\s*(\d+(?:\.\d+)?)/);

    if (rangeMatch) {
      result.min = parseFloat(rangeMatch[1]);
      result.max = parseFloat(rangeMatch[2]);
    } else {
      if (minMatch) {
        const value = parseFloat(minMatch[1]);
        result.min = minMatch[0].startsWith('>=') ? value : value + (value % 1 === 0 ? 1 : 0.01);
      }
      if (maxMatch) {
        const value = parseFloat(maxMatch[1]);
        result.max = maxMatch[0].startsWith('<=') ? value : value - (value % 1 === 0 ? 1 : 0.01);
      }
    }

    return result;
  }, []);

  const handleExpressionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setExpression(value);

    const { min: newMin, max: newMax } = parseExpression(value);
    onChange(newMin, newMax);
  };

  const handleManualChange = (type: 'min' | 'max', value: string) => {
    const numValue = value === '' ? undefined : parseFloat(value);
    if (type === 'min') {
      onChange(numValue, max);
    } else {
      onChange(min, numValue);
    }
  };

  return (
    <div className="filter-section range-filter">
      <h4 className="filter-title">{label}</h4>
      <div className="range-inputs">
        <div className="input-group">
          <label htmlFor={`${label}-min`}>Min:</label>
          <input
            id={`${label}-min`}
            type="number"
            value={min !== undefined ? min : ''}
            onChange={(e) => handleManualChange('min', e.target.value)}
            placeholder="Min"
            step="any"
            aria-label={`${label} minimum value`}
          />
        </div>
        <div className="input-group">
          <label htmlFor={`${label}-max`}>Max:</label>
          <input
            id={`${label}-max`}
            type="number"
            value={max !== undefined ? max : ''}
            onChange={(e) => handleManualChange('max', e.target.value)}
            placeholder="Max"
            step="any"
            aria-label={`${label} maximum value`}
          />
        </div>
      </div>
      <div className="expression-input">
        <input
          type="text"
          value={expression}
          onChange={handleExpressionChange}
          placeholder={placeholder}
          aria-label={`${label} expression`}
        />
      </div>
    </div>
  );
};

export default memo(RangeFilter);
