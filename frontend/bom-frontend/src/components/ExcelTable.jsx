import React, { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';

import { ColumnFilter } from './ColumnFilter';

const TABLE_ROW_HEIGHT = 36;
const TABLE_OVERSCAN_ROWS = 12;

export const ExcelTable = ({ data, columns, onRowClick, selectedRow }) => {
  const [filters, setFilters] = useState({});
  const [openMenuColumn, setOpenMenuColumn] = useState(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const scrollContainerRef = useRef(null);
  const scrollRafRef = useRef(null);
  const uniqueValuesCacheRef = useRef(new Map());
  const deferredFilters = useDeferredValue(filters);

  const getUniqueValues = useCallback((column) => {
    const cache = uniqueValuesCacheRef.current;
    if (cache.has(column)) {
      return cache.get(column);
    }

    const valueSet = new Set();
    for (let i = 0; i < data.length; i += 1) {
      valueSet.add(String(data[i][column] || ''));
    }

    const computedValues = Array.from(valueSet).sort();
    cache.set(column, computedValues);
    return computedValues;
  }, [data]);

  useEffect(() => {
    uniqueValuesCacheRef.current = new Map();
  }, [data, columns]);

  useEffect(() => {
    const updateViewport = () => {
      if (scrollContainerRef.current) {
        setViewportHeight(scrollContainerRef.current.clientHeight);
      }
    };

    updateViewport();
    window.addEventListener('resize', updateViewport);
    return () => window.removeEventListener('resize', updateViewport);
  }, []);

  const activeFilters = useMemo(() => {
    return Object.entries(deferredFilters).filter(([, allowedValues]) => allowedValues instanceof Set);
  }, [deferredFilters]);

  const filteredData = useMemo(() => {
    if (!columns || activeFilters.length === 0) return data;
    return data.filter(row => {
      for (let i = 0; i < activeFilters.length; i += 1) {
        const [col, allowedValues] = activeFilters[i];
        if (!allowedValues.has(String(row[col] || ''))) {
          return false;
        }
      }
      return true;
    });
  }, [data, columns, activeFilters]);

  const totalRows = filteredData.length;
  const visibleRowCount = Math.max(1, Math.ceil((viewportHeight || TABLE_ROW_HEIGHT) / TABLE_ROW_HEIGHT) + (TABLE_OVERSCAN_ROWS * 2));
  const startIndex = Math.max(0, Math.floor(scrollTop / TABLE_ROW_HEIGHT) - TABLE_OVERSCAN_ROWS);
  const endIndex = Math.min(totalRows, startIndex + visibleRowCount);

  const topPaddingHeight = startIndex * TABLE_ROW_HEIGHT;
  const bottomPaddingHeight = Math.max(0, (totalRows - endIndex) * TABLE_ROW_HEIGHT);

  const visibleRows = useMemo(() => {
    return filteredData.slice(startIndex, endIndex);
  }, [filteredData, startIndex, endIndex]);

  const handleScroll = useCallback((event) => {
    const nextScrollTop = event.currentTarget.scrollTop;

    if (scrollRafRef.current) {
      cancelAnimationFrame(scrollRafRef.current);
    }

    scrollRafRef.current = requestAnimationFrame(() => {
      setScrollTop(nextScrollTop);
      scrollRafRef.current = null;
    });
  }, []);

  useEffect(() => {
    return () => {
      if (scrollRafRef.current) {
        cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, []);

  if (!columns || columns.length === 0) {
    return null;
  }

  return (
    <div
      ref={scrollContainerRef}
      onScroll={handleScroll}
      className="overflow-auto h-full w-full bg-white relative"
    >
      <table className="w-full text-left border-collapse whitespace-nowrap">
        <thead className="sticky top-0 bg-slate-100 z-30 shadow-sm border-b border-slate-200">
          <tr>
            {columns.map(col => (
              <th key={col} className="px-3 py-2 border-r border-slate-200 text-xs font-semibold text-slate-700 bg-slate-50 relative align-middle">
                <div className="flex items-center justify-between">
                  <span>{col}</span>
                  <ColumnFilter
                    column={col}
                    getUniqueValues={getUniqueValues}
                    filters={filters}
                    setFilters={setFilters}
                    isOpen={openMenuColumn === col}
                    toggleMenu={() => setOpenMenuColumn(openMenuColumn === col ? null : col)}
                    closeMenu={() => setOpenMenuColumn(null)}
                  />
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {topPaddingHeight > 0 && (
            <tr>
              <td colSpan={columns.length} style={{ height: `${topPaddingHeight}px` }} />
            </tr>
          )}
          {visibleRows.map((row, i) => {
            const rowIndex = startIndex + i;
            return (
              <tr
                key={rowIndex}
                onClick={() => onRowClick(row)}
                className={`h-9 cursor-pointer border-b border-slate-100 hover:bg-blue-50 transition-colors ${selectedRow === row ? 'bg-blue-100' : 'bg-white'}`}
              >
                {columns.map(col => (
                  <td key={`${rowIndex}-${col}`} className="h-9 px-3 py-2 text-xs text-slate-700 border-r border-slate-100 last:border-r-0">
                    {row[col]}
                  </td>
                ))}
              </tr>
            );
          })}
          {bottomPaddingHeight > 0 && (
            <tr>
              <td colSpan={columns.length} style={{ height: `${bottomPaddingHeight}px` }} />
            </tr>
          )}
          {totalRows === 0 && (
            <tr>
              <td colSpan={columns.length} className="p-6 text-center text-slate-400 text-sm">
                No matching records found based on the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};
