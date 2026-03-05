import React, { memo } from 'react';
import { AWS_REGIONS } from './types';
import './Filters.css';

interface RegionFilterProps {
  selected: string[];
  onChange: (selected: string[]) => void;
}

const RegionFilter: React.FC<RegionFilterProps> = ({ selected, onChange }) => {
  const handleToggle = (region: string) => {
    if (selected.includes(region)) {
      onChange(selected.filter((r) => r !== region));
    } else {
      onChange([...selected, region]);
    }
  };

  const handleGroupToggle = (regions: string[]) => {
    const allSelected = regions.every((r) => selected.includes(r));
    if (allSelected) {
      onChange(selected.filter((r) => !regions.includes(r)));
    } else {
      const newSelected = [...selected];
      regions.forEach((r) => {
        if (!newSelected.includes(r)) {
          newSelected.push(r);
        }
      });
      onChange(newSelected);
    }
  };

  const handleClear = () => {
    onChange([]);
  };

  return (
    <div className="filter-section region-filter">
      <div className="filter-header">
        <h4 className="filter-title">Region</h4>
        {selected.length > 0 && (
          <button type="button" className="clear-btn" onClick={handleClear}>
            Clear
          </button>
        )}
      </div>
      <div className="region-groups">
        {Object.entries(AWS_REGIONS).map(([group, regions]) => (
          <div key={group} className="region-group">
            <div className="region-group-header">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={regions.every((r) => selected.includes(r))}
                  onChange={() => handleGroupToggle(regions)}
                />
                <span className="group-name">{group}</span>
              </label>
            </div>
            <div className="region-group-items">
              {regions.map((region) => (
                <label key={region} className="checkbox-label sub">
                  <input
                    type="checkbox"
                    checked={selected.includes(region)}
                    onChange={() => handleToggle(region)}
                  />
                  <span>{region}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default memo(RegionFilter);
