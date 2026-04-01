import React, { useState, useMemo, useCallback, useEffect, useRef, useDeferredValue } from 'react';
import { Upload, FileText, Download, Eye, Loader2, Database, Filter, Search, ChevronRight, HardDrive, FolderOpen } from 'lucide-react';

const normalizeBaseUrl = (url) => String(url || '').trim().replace(/\/+$/, '');
const API_BASE_CANDIDATES = Array.from(new Set([
  normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
  'http://127.0.0.1:8000',
  'http://localhost:8000',
].filter(Boolean)));
const MAX_UPLOAD_BYTES = Number(import.meta.env.VITE_MAX_UPLOAD_BYTES || (100 * 1024 * 1024));
const TABLE_ROW_HEIGHT = 36;
const TABLE_OVERSCAN_ROWS = 12;

const parseResponseBody = async (response) => {
  const text = await response.text();
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
};

const fetchApiWithFallback = async (path, options = {}) => {
  let lastNetworkError = null;

  for (const baseUrl of API_BASE_CANDIDATES) {
    try {
      const response = await fetch(`${baseUrl}${path}`, options);
      const payload = await parseResponseBody(response);

      return {
        ok: response.ok,
        status: response.status,
        payload,
        baseUrl,
      };
    } catch (error) {
      lastNetworkError = error;
    }
  }

  const error = new Error('Unable to reach backend API.');
  error.cause = lastNetworkError;
  throw error;
};

const normalizeKey = (value) => String(value ?? '').trim();

const useDebouncedValue = (value, delay = 180) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
};

// Excel-like Filter Menu Component with Fixed Overlay approach to prevent closing
const ColumnFilter = ({ column, getUniqueValues, filters, setFilters, isOpen, toggleMenu, closeMenu }) => {
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
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleMenu(); }}
        className={`p-1 rounded transition-colors hover:bg-slate-200 ${isFiltered ? 'text-blue-600 bg-blue-50' : 'text-slate-400'}`}
        title="Filter column"
      >
        <Filter size={14} />
      </button>

      {isOpen && (
        <>
          {/* Dropdown Menu Container */}
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
                <label key={idx} className="flex items-center p-1 hover:bg-slate-50 cursor-pointer rounded">
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
        </>
      )}
    </div>
  );
};

// Main Table Component with Dynamic Columns
const ExcelTable = ({ data, columns, onRowClick, selectedRow }) => {
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
    setFilters({});
    setOpenMenuColumn(null);
    setScrollTop(0);
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
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
                <td key={col} className="h-9 px-3 py-2 text-xs text-slate-700 border-r border-slate-100 last:border-r-0">
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

export default function App() {
  const [columns, setColumns] = useState([]);
  const [masterData, setMasterData] = useState([]);
  const [detailData, setDetailData] = useState([]);
  const [selectedParent, setSelectedParent] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [drawings, setDrawings] = useState([]);
  const [loadingDrawings, setLoadingDrawings] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [sharepointPath, setSharepointPath] = useState([]);
  const dragDepthRef = useRef(0);
  const drawingRequestIdRef = useRef(0);
  
  // File Metadata State
  const [fileMeta, setFileMeta] = useState({ name: '', date: '', version: '' });
  const [uploadedBOMFile, setUploadedBOMFile] = useState(null);
  const [saveRecordId, setSaveRecordId] = useState('');
  const [saveState, setSaveState] = useState({
    status: 'draft',
    file_saved: false,
    metadata_saved: false,
  });
  const [savingAction, setSavingAction] = useState('');

  const applySaveState = useCallback((payload) => {
    if (!payload || typeof payload !== 'object') return;

    if (payload.record_id) {
      setSaveRecordId(payload.record_id);
    }

    if (payload.save_state) {
      setSaveState({
        status: payload.save_state.status || 'draft',
        file_saved: Boolean(payload.save_state.file_saved),
        metadata_saved: Boolean(payload.save_state.metadata_saved),
      });
    }
  }, []);

  const resetSaveState = useCallback(() => {
    setSaveRecordId('');
    setSaveState({
      status: 'draft',
      file_saved: false,
      metadata_saved: false,
    });
    setSavingAction('');
  }, []);

  const saveStatusLabel = useMemo(() => {
    if (saveState.file_saved && saveState.metadata_saved) {
      return 'Paired Saved';
    }
    if (saveState.file_saved) {
      return 'File Saved';
    }
    if (saveState.metadata_saved) {
      return 'Metadata Saved';
    }
    return 'Draft';
  }, [saveState]);

  const saveStatusClass = useMemo(() => {
    if (saveState.file_saved && saveState.metadata_saved) {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }
    if (saveState.file_saved || saveState.metadata_saved) {
      return 'bg-amber-50 text-amber-700 border-amber-200';
    }
    return 'bg-slate-100 text-slate-600 border-slate-200';
  }, [saveState]);

  const canSaveFile = Boolean(saveRecordId && uploadedBOMFile);
  const canSaveMetadata = Boolean(saveRecordId && fileMeta.name && fileMeta.date && fileMeta.version);
  const canSaveBoth = canSaveFile && canSaveMetadata;

  const rowsByParent = useMemo(() => {
    const grouped = new Map();

    for (let i = 0; i < masterData.length; i += 1) {
      const row = masterData[i];
      const parentModel = normalizeKey(row.PARENT || row.TOP_ASSY || row.COMPONENT);
      if (!parentModel) continue;

      if (!grouped.has(parentModel)) {
        grouped.set(parentModel, []);
      }
      grouped.get(parentModel).push(row);
    }

    return grouped;
  }, [masterData]);

  useEffect(() => {
    // Prevent browser from opening/downloading files when dropped outside the intended drop zone.
    const preventWindowFileDrop = (event) => {
      if (event.dataTransfer?.types?.includes('Files')) {
        event.preventDefault();
      }
    };

    window.addEventListener('dragover', preventWindowFileDrop);
    window.addEventListener('drop', preventWindowFileDrop);

    return () => {
      window.removeEventListener('dragover', preventWindowFileDrop);
      window.removeEventListener('drop', preventWindowFileDrop);
    };
  }, []);

  const processFile = async (file) => {
    if (!file) return;

    const extension = file.name.toLowerCase().split('.').pop();
    if (!['xlsx', 'csv'].includes(extension)) {
      alert('Invalid file type. Please upload a .xlsx or .csv file.');
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      alert(`File is too large. Max allowed size is ${Math.floor(MAX_UPLOAD_BYTES / (1024 * 1024))} MB.`);
      return;
    }

    resetSaveState();
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback('/api/upload', {
        method: "POST",
        body: formData,
      });
      const result = payload || {};
      
      if (ok && result.status === "success") {
        const fetchedCols = result.columns && result.columns.length > 0 
          ? result.columns 
          : (result.data && result.data.length > 0 ? Object.keys(result.data[0]) : []);
          
        setColumns(fetchedCols);
        setMasterData(result.data || []);
        setDetailData([]);
        setSelectedParent(null);
        setDrawings([]);
        setSharepointPath([]);

        const now = new Date();
        const formattedDate = now.toLocaleDateString() + ' ' + now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        setFileMeta({
          name: file.name,
          date: formattedDate,
          version: '1.0'
        });
        setUploadedBOMFile(file);

        try {
          const { ok: recordOk, payload: recordPayload, status: recordStatus, baseUrl: recordBaseUrl } = await fetchApiWithFallback('/api/save/new-record', {
            method: 'POST',
          });

          if (recordOk && recordPayload?.status === 'success' && recordPayload?.record_id) {
            applySaveState(recordPayload);
          } else {
            const reason = recordPayload?.message || `HTTP ${recordStatus}`;
            alert(`BOM uploaded, but save record initialization failed: ${reason} (API: ${recordBaseUrl})`);
          }
        } catch (error) {
          console.error('Create save record error:', error);
          alert(`BOM uploaded, but save record initialization failed. Tried: ${API_BASE_CANDIDATES.join(', ')}`);
        }

      } else {
        const reason = result.message || `HTTP ${status}`;
        alert(`Upload failed: ${reason} (API: ${baseUrl})`);
      }
    } catch (error) {
      console.error("Upload error:", error);
      alert(`Cannot connect to backend server. Tried: ${API_BASE_CANDIDATES.join(', ')}`);
    } finally {
      setUploading(false);
    }
  };

  const handleFileUpload = (event) => {
    processFile(event.target.files[0]);
    event.target.value = ''; 
  };

  const saveBOMFileOnly = useCallback(async () => {
    if (!saveRecordId || !uploadedBOMFile) {
      alert('Please upload a BOM file first.');
      return;
    }

    setSavingAction('file');
    const formData = new FormData();
    formData.append('record_id', saveRecordId);
    formData.append('file', uploadedBOMFile);

    try {
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback('/api/save/file', {
        method: 'POST',
        body: formData,
      });

      if (ok && payload?.status === 'success') {
        applySaveState(payload);
      } else {
        const reason = payload?.message || `HTTP ${status}`;
        alert(`Save BOM File failed: ${reason} (API: ${baseUrl})`);
      }
    } catch (error) {
      console.error('Save BOM file error:', error);
      alert(`Cannot connect to backend server. Tried: ${API_BASE_CANDIDATES.join(', ')}`);
    } finally {
      setSavingAction('');
    }
  }, [saveRecordId, uploadedBOMFile, applySaveState]);

  const saveMetadataOnly = useCallback(async () => {
    if (!saveRecordId) {
      alert('Save record is not initialized. Please re-upload BOM file.');
      return;
    }

    const normalizedFileName = String(fileMeta.name || '').trim();
    const normalizedUploadDate = String(fileMeta.date || '').trim();
    const normalizedVersion = String(fileMeta.version || '').trim() || '1.0';

    if (!normalizedFileName || !normalizedUploadDate) {
      alert('File Name and Upload Date are required to save metadata.');
      return;
    }

    setSavingAction('metadata');
    try {
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback('/api/save/metadata', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          record_id: saveRecordId,
          file_name: normalizedFileName,
          upload_date: normalizedUploadDate,
          version: normalizedVersion,
        }),
      });

      if (ok && payload?.status === 'success') {
        applySaveState(payload);
        if (normalizedVersion !== fileMeta.version) {
          setFileMeta(prev => ({ ...prev, version: normalizedVersion }));
        }
      } else {
        const reason = payload?.message || `HTTP ${status}`;
        alert(`Save Metadata failed: ${reason} (API: ${baseUrl})`);
      }
    } catch (error) {
      console.error('Save metadata error:', error);
      alert(`Cannot connect to backend server. Tried: ${API_BASE_CANDIDATES.join(', ')}`);
    } finally {
      setSavingAction('');
    }
  }, [saveRecordId, fileMeta, applySaveState]);

  const saveBoth = useCallback(async () => {
    if (!saveRecordId || !uploadedBOMFile) {
      alert('Please upload a BOM file first.');
      return;
    }

    const normalizedFileName = String(fileMeta.name || '').trim();
    const normalizedUploadDate = String(fileMeta.date || '').trim();
    const normalizedVersion = String(fileMeta.version || '').trim() || '1.0';

    if (!normalizedFileName || !normalizedUploadDate) {
      alert('File Name and Upload Date are required to save metadata.');
      return;
    }

    setSavingAction('both');
    const formData = new FormData();
    formData.append('record_id', saveRecordId);
    formData.append('file_name', normalizedFileName);
    formData.append('upload_date', normalizedUploadDate);
    formData.append('version', normalizedVersion);
    formData.append('file', uploadedBOMFile);

    try {
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback('/api/save/both', {
        method: 'POST',
        body: formData,
      });

      if (ok && payload?.status === 'success') {
        applySaveState(payload);
        if (normalizedVersion !== fileMeta.version) {
          setFileMeta(prev => ({ ...prev, version: normalizedVersion }));
        }
      } else {
        const reason = payload?.message || `HTTP ${status}`;
        alert(`Save Both failed: ${reason} (API: ${baseUrl})`);
      }
    } catch (error) {
      console.error('Save both error:', error);
      alert(`Cannot connect to backend server. Tried: ${API_BASE_CANDIDATES.join(', ')}`);
    } finally {
      setSavingAction('');
    }
  }, [saveRecordId, uploadedBOMFile, fileMeta, applySaveState]);

  // Drag and Drop Event Handlers (Preventing default browser download)
  const onDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.dataTransfer?.types?.includes('Files')) return;
    dragDepthRef.current += 1;
    setIsDragging(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.dataTransfer?.types?.includes('Files')) return;
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsDragging(false);
    }
  };

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.dataTransfer?.types?.includes('Files')) return;
    e.dataTransfer.dropEffect = 'copy';
    setIsDragging(true);
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.dataTransfer?.types?.includes('Files')) return;
    dragDepthRef.current = 0;
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
      e.dataTransfer.clearData();
    }
  };

  const onMasterRowClicked = useCallback(async (row) => {
    const requestId = ++drawingRequestIdRef.current;
    setSelectedParent(row);
    setSelectedDetail(null);
    setDrawings([]);
    setSharepointPath([]);
    setLoadingDrawings(true);

    // BOM-Tech rule: focus key is the selected row's PARENT model, then filter all rows with the same PARENT.
    const selectedParentModel = normalizeKey(row.PARENT || row.TOP_ASSY || row.COMPONENT);
    const children = selectedParentModel ? (rowsByParent.get(selectedParentModel) || []) : [];

    setDetailData(children);

    if (!selectedParentModel || children.length === 0) {
      if (requestId === drawingRequestIdRef.current) {
        setLoadingDrawings(false);
      }
      return;
    }

    const uniqueTargets = [];
    const seenTargets = new Set();
    children.forEach(item => {
      const component = normalizeKey(item.COMPONENT || item.TOP_ASSY);
      if (!component) return;

      const category = normalizeKey(item.Category) || 'Unknown Category';
      const key = `${category}::${component}`;
      if (seenTargets.has(key)) return;
      seenTargets.add(key);
      uniqueTargets.push({ category, component });
    });

    if (uniqueTargets.length === 0) {
      if (requestId === drawingRequestIdRef.current) {
        setLoadingDrawings(false);
      }
      return;
    }

    try {
      const responseList = await Promise.all(uniqueTargets.map(async ({ category, component }) => {
        const { ok, payload } = await fetchApiWithFallback(`/api/search?category=${encodeURIComponent(category)}&component=${encodeURIComponent(component)}`);
        const data = payload || {};

        if (!ok || data.status !== 'success') {
          return { drawings: [], path: [] };
        }

        const enriched = (data.results || []).map(file => ({
          ...file,
          id: file.id || `${component}-${file.name || 'drawing'}-${file.version || ''}`,
          sourceComponent: component,
          sourceCategory: category,
        }));

        return {
          drawings: enriched,
          path: data.sharepoint_path || [],
        };
      }));

      if (requestId !== drawingRequestIdRef.current) {
        return;
      }

      const drawingMap = new Map();
      responseList.flatMap(item => item.drawings).forEach(file => {
        const key = `${file.id}::${file.sourceComponent}`;
        if (!drawingMap.has(key)) {
          drawingMap.set(key, file);
        }
      });

      setDrawings(Array.from(drawingMap.values()));
      const firstPath = responseList.find(item => Array.isArray(item.path) && item.path.length > 0)?.path || [];
      setSharepointPath(firstPath);
    } catch (error) {
      if (requestId === drawingRequestIdRef.current) {
        console.error('Fetch drawings failed:', error);
        setDrawings([]);
        setSharepointPath([]);
      }
    } finally {
      if (requestId === drawingRequestIdRef.current) {
        setLoadingDrawings(false);
      }
    }
  }, [rowsByParent]);

  const onDetailRowClicked = useCallback((row) => {
    setSelectedDetail(row);
  }, []);

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans text-sm">
      {/* Top Navigation */}
      <div className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm shrink-0 z-20">
        <div className="flex items-center space-x-2">
          <Database size={22} className="text-blue-600" />
          <h1 className="text-lg font-bold text-slate-800 tracking-tight">BOM & Drawings Workspace</h1>
        </div>
        <div>
          <label className="flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded shadow hover:bg-blue-700 transition cursor-pointer">
            {uploading ? <Loader2 className="animate-spin mr-2" size={16} /> : <Upload size={16} className="mr-2" />}
            <span>{uploading ? "Processing..." : "Upload BOM File"}</span>
            <input type="file" accept=".csv, .xlsx" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
      </div>

      {/* Main Layout */}
      <div className="flex flex-1 overflow-hidden p-4 space-x-4">
        
        {/* Left Section (Master & Detail Tables) */}
        <div className="w-7/12 flex flex-col space-y-4">
          
          <div 
            className={`flex-1 bg-white rounded-lg shadow-sm border ${isDragging ? 'border-blue-500 bg-blue-50/50' : 'border-slate-200'} flex flex-col overflow-hidden relative transition-colors`}
            onDragEnter={onDragEnter}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            {isDragging && (
              <div className="absolute inset-0 z-50 flex items-center justify-center bg-blue-50/90 border-2 border-dashed border-blue-400 rounded-lg">
                <div className="text-center">
                  <Upload size={48} className="mx-auto text-blue-500 mb-2" />
                  <p className="text-xl font-bold text-blue-600">Drop your file here to upload</p>
                </div>
              </div>
            )}

            <div className="px-4 py-3 border-b bg-slate-50 flex justify-between items-center z-10">
              <div className="flex items-center space-x-6">
                <h2 className="font-semibold text-slate-700">1. Master BOM Table</h2>
                {fileMeta.name && (
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="text-slate-500">File: <span className="font-semibold text-slate-700">{fileMeta.name}</span></span>
                    <span className="text-slate-500">Upload Date: <span className="text-slate-700">{fileMeta.date}</span></span>
                    <div className="flex items-center">
                      <span className="text-slate-500 mr-2">Version:</span>
                      <input 
                        type="text" 
                        value={fileMeta.version} 
                        onChange={(e) => setFileMeta({...fileMeta, version: e.target.value})}
                        className="border border-slate-300 rounded px-2 py-0.5 w-16 text-center text-slate-700 font-medium focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={saveBOMFileOnly}
                      disabled={!canSaveFile || Boolean(savingAction)}
                      className="px-2.5 py-1 rounded border border-blue-200 bg-blue-50 text-blue-700 font-semibold hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                    >
                      {savingAction === 'file' ? 'Saving...' : 'Save BOM File'}
                    </button>
                    <button
                      type="button"
                      onClick={saveMetadataOnly}
                      disabled={!canSaveMetadata || Boolean(savingAction)}
                      className="px-2.5 py-1 rounded border border-amber-200 bg-amber-50 text-amber-700 font-semibold hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                    >
                      {savingAction === 'metadata' ? 'Saving...' : 'Save Metadata'}
                    </button>
                    <button
                      type="button"
                      onClick={saveBoth}
                      disabled={!canSaveBoth || Boolean(savingAction)}
                      className="px-2.5 py-1 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 font-semibold hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                    >
                      {savingAction === 'both' ? 'Saving...' : 'Save Both'}
                    </button>
                    <span className={`px-2 py-1 rounded border font-semibold ${saveStatusClass}`}>
                      {saveStatusLabel}
                    </span>
                    {saveRecordId && (
                      <span className="px-2 py-1 rounded border border-slate-200 bg-white text-slate-500">
                        Record: <span className="font-mono text-slate-700">{saveRecordId.slice(0, 8)}...</span>
                      </span>
                    )}
                  </div>
                )}
              </div>
              <span className="text-xs font-medium text-slate-500 bg-slate-200 px-2 py-1 rounded-full">Total: {masterData.length} Rows</span>
            </div>

            <div className="flex-1 overflow-hidden relative">
              {masterData.length > 0 ? (
                <ExcelTable data={masterData} columns={columns} onRowClick={onMasterRowClicked} selectedRow={selectedParent} />
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-400">
                  <FileText size={40} className="mb-3 text-slate-300" />
                  <p>Drag & Drop a <b>.xlsx</b> or <b>.csv</b> file here</p>
                  <p className="text-xs mt-2 text-slate-300">or use the upload button at the top right</p>
                </div>
              )}
            </div>
          </div>

          <div className="h-1/3 min-h-[250px] bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
             <div className="px-4 py-3 border-b bg-slate-50 flex items-center justify-between">
              <div className="flex items-center">
                <h2 className="font-semibold text-slate-700 mr-4">2. Required Child Components</h2>
                {selectedParent && normalizeKey(selectedParent.PARENT || selectedParent.TOP_ASSY || selectedParent.COMPONENT) && (
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded border border-blue-200 shadow-sm">
                    Target Parent: <span className="font-mono font-bold">{selectedParent.PARENT || selectedParent.TOP_ASSY || selectedParent.COMPONENT}</span>
                  </span>
                )}
              </div>
              <span className="text-xs font-medium text-slate-500 bg-slate-200 px-2 py-1 rounded-full">Total: {detailData.length} Rows</span>
            </div>
            <div className="flex-1 overflow-hidden relative">
              {selectedParent ? (
                <ExcelTable data={detailData} columns={columns} onRowClick={onDetailRowClicked} selectedRow={selectedDetail} />
              ) : (
                <div className="h-full flex items-center justify-center text-slate-400 italic">
                  Select a row from the Master Table above.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Section (Drawings) */}
        <div className="w-5/12 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b bg-slate-50">
            <h2 className="font-semibold text-slate-700">3. SharePoint Drawings (Mock API)</h2>
          </div>
          
          <div className="flex-1 p-4 overflow-auto bg-slate-50/50">
            {!selectedParent ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <FileText size={48} className="mb-4 text-slate-300" />
                <p>Select a row from the top-left table to view all related drawings.</p>
              </div>
            ) : (
              <div>
                {/* Beautiful Mock SharePoint Breadcrumb Path */}
                {sharepointPath.length > 0 && (
                  <div className="mb-4 bg-white border border-slate-200 rounded-lg shadow-sm p-3">
                    <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Directory Path</p>
                    <div className="flex flex-wrap items-center text-sm text-slate-600 gap-y-2">
                      <HardDrive size={16} className="text-slate-400 mr-1 shrink-0" />
                      {sharepointPath.map((segment, index) => (
                        <React.Fragment key={index}>
                          <span className={`flex items-center px-2 py-1 rounded ${index === sharepointPath.length - 1 ? 'bg-blue-50 text-blue-700 font-bold border border-blue-100' : 'hover:bg-slate-100 cursor-pointer'}`}>
                            {index > 0 && index < sharepointPath.length - 1 && <FolderOpen size={14} className="mr-1.5 text-blue-500" />}
                            {index === sharepointPath.length - 1 && <FileText size={14} className="mr-1.5 text-blue-600" />}
                            {segment}
                          </span>
                          {index < sharepointPath.length - 1 && (
                            <ChevronRight size={14} className="text-slate-300 shrink-0" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                )}

                {loadingDrawings ? (
                   <div className="flex flex-col items-center justify-center py-12 text-blue-500">
                     <Loader2 className="animate-spin mb-3" size={28} />
                     <span className="text-sm font-medium">Fetching drawings via API...</span>
                   </div>
                ) : drawings.length > 0 ? (
                  <div className="space-y-3">
                    <p className="text-xs font-semibold text-slate-500 mb-2 uppercase">Found {drawings.length} matching files</p>
                    {drawings.map(drawing => (
                      <div key={drawing.id} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg shadow-sm hover:border-blue-400 hover:shadow-md transition-all group">
                         <div className="flex items-center space-x-4">
                            <div className={`w-12 h-12 rounded flex items-center justify-center text-white font-bold text-sm shadow-inner ${drawing.type === 'PDF' ? 'bg-red-500' : 'bg-indigo-500'}`}>
                              {drawing.type}
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-slate-800 group-hover:text-blue-700 transition-colors">{drawing.name}</p>
                              <div className="flex space-x-3 text-xs text-slate-500 mt-1">
                                <span>Component: {drawing.sourceComponent || '-'}</span>
                                <span>Revision: {drawing.version}</span>
                                <span>{drawing.date}</span>
                              </div>
                            </div>
                         </div>
                         <div className="flex space-x-2">
                            <button className="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 border border-slate-200 rounded shadow-sm transition-colors" title="Preview">
                              <Eye size={18} />
                            </button>
                            <button className="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 border border-slate-200 rounded shadow-sm transition-colors" title="Download">
                              <Download size={18} />
                            </button>
                         </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 bg-white border border-dashed border-slate-300 rounded-lg mt-4">
                    No drawings found in SharePoint for this component.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}