import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Filter, Search } from 'lucide-react';

const useDebouncedValue = (value, delay = 180) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
};

export const ColumnFilter = ({
  column,
  getUniqueValues,
  filters,
  setFilters,
  isOpen,
  toggleMenu,
  closeMenu,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const debouncedSearchTerm = useDebouncedValue(searchTerm, 180);

  const uniqueValues = useMemo(() => {
    if (!isOpen) return [];
    return getUniqueValues(column);
  }, [isOpen, getUniqueValues, column]);

  const displayValues = useMemo(() => {
    if (!debouncedSearchTerm) return uniqueValues;
    const normalized = debouncedSearchTerm.toLowerCase();
    return uniqueValues.filter(v => v.toLowerCase().includes(normalized));
  }, [uniqueValues, debouncedSearchTerm]);

  const isFiltered = Object.prototype.hasOwnProperty.call(filters, column);
  const selectedValues = filters[column] || new Set(uniqueValues);
  const isAllSelected = !isFiltered || selectedValues.size === uniqueValues.length;

  const updateFilterForColumn = (nextSet) => {
    setFilters(prev => {
      const next = { ...prev };
      if (nextSet.size === uniqueValues.length) {
        delete next[column];
      } else {
        next[column] = nextSet;
      }
      return next;
    });
  };

  const handleCheckboxChange = (val) => {
    const baseSelection = filters[column] ? new Set(filters[column]) : new Set(uniqueValues);
    const newSelected = new Set(baseSelection);
    if (newSelected.has(val)) {
      newSelected.delete(val);
    } else {
      newSelected.add(val);
    }
    updateFilterForColumn(newSelected);
  };

  const handleSelectAll = () => {
    if (isAllSelected) {
      setFilters(prev => ({ ...prev, [column]: new Set() }));
    } else {
      setFilters(prev => {
        const next = { ...prev };
        delete next[column];
        return next;
      });
    }
  };

  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (event) => {
      const target = event.target;
      if (
        (menuRef.current && menuRef.current.contains(target)) ||
        (triggerRef.current && triggerRef.current.contains(target))
      ) {
        return;
      }
      closeMenu();
    };

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        closeMenu();
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, closeMenu]);

  return (
    <div className="relative inline-block ml-2">
      <button
        ref={triggerRef}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleMenu();
        }}
        className={`p-1 rounded transition-colors hover:bg-slate-200 ${isFiltered ? 'text-blue-600 bg-blue-50' : 'text-slate-400'}`}
        title="Filter column"
      >
        <Filter size={14} />
      </button>

      {isOpen && (
        <div
          ref={menuRef}
          className="absolute top-full left-0 mt-1 w-64 bg-white border border-slate-200 rounded-lg shadow-xl z-50 p-3 font-normal"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="relative mb-2">
            <Search size={14} className="absolute left-2 top-2 text-slate-400" />
            <input
              type="text"
              placeholder="Search values..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-7 pr-2 py-1.5 text-xs border border-slate-300 rounded focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="max-h-48 overflow-y-auto space-y-1 border border-slate-100 p-1">
            <label className="flex items-center p-1 hover:bg-slate-50 cursor-pointer rounded">
              <input
                type="checkbox"
                checked={isAllSelected}
                onChange={handleSelectAll}
                className="mr-2 rounded border-slate-300 cursor-pointer"
              />
              <span className="text-xs font-semibold text-slate-700">(Select All)</span>
            </label>
            {displayValues.map((val, idx) => (
              <label key={`${column}-${val}-${idx}`} className="flex items-center p-1 hover:bg-slate-50 cursor-pointer rounded">
                <input
                  type="checkbox"
                  checked={selectedValues.has(val)}
                  onChange={() => handleCheckboxChange(val)}
                  className="mr-2 rounded border-slate-300 cursor-pointer"
                />
                <span className="text-xs text-slate-600 truncate" title={val}>{val === '' ? '(Blanks)' : val}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
