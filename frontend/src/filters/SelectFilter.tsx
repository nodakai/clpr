import React, { memo } from 'react';
import './Filters.css';

interface SelectFilterProps {
  label: string;
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  multiSelect?: boolean;
}

const SelectFilter: React.FC<SelectFilterProps> = ({
  label,
  options,
  selected,
  onChange,
  multiSelect = true,
}) => {
  const handleToggle = (option: string) => {
    if (multiSelect) {
      if (selected.includes(option)) {
        onChange(selected.filter((item) => item !== option));
      } else {
        onChange([...selected, option]);
      }
    } else {
      onChange([option]);
    }
  };

  const handleClear = () => {
    onChange([]);
  };

  return (
    <div className="filter-section select-filter">
      <div className="filter-header">
        <h4 className="filter-title">{label}</h4>
        {selected.length > 0 && (
          <button type="button" className="clear-btn" onClick={handleClear}>
            Clear
          </button>
        )}
      </div>
      <div className="select-options">
        {options.map((option) => (
          <label key={option} className="checkbox-label">
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => handleToggle(option)}
            />
            <span>{option}</span>
          </label>
        ))}
      </div>
    </div>
  );
};

export default memo(SelectFilter);
