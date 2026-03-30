import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { Upload, FileText, Download, Eye, Loader2, Database, Filter, Search, ChevronRight, HardDrive, FolderOpen } from 'lucide-react';

// Excel-like Filter Menu Component with Fixed Overlay approach to prevent closing
const ColumnFilter = ({ column, data, filters, setFilters, isOpen, toggleMenu, closeMenu }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const uniqueValues = useMemo(() => {
    const values = new Set(data.map(row => String(row[column] || '')));
    return Array.from(values).sort();
  }, [data, column]);

  const displayValues = useMemo(() => {
    if (!searchTerm) return uniqueValues;
    return uniqueValues.filter(v => v.toLowerCase().includes(searchTerm.toLowerCase()));
  }, [uniqueValues, searchTerm]);

  const selectedValues = filters[column] || new Set(uniqueValues);
  const isAllSelected = selectedValues.size === uniqueValues.length;

  const handleCheckboxChange = (val) => {
    const newSelected = new Set(selectedValues);
    if (newSelected.has(val)) {
      newSelected.delete(val);
    } else {
      newSelected.add(val);
    }
    setFilters(prev => ({ ...prev, [column]: newSelected }));
  };

  const handleSelectAll = () => {
    if (isAllSelected) {
      setFilters(prev => ({ ...prev, [column]: new Set() }));
    } else {
      setFilters(prev => ({ ...prev, [column]: new Set(uniqueValues) }));
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
        className={`p-1 rounded transition-colors hover:bg-slate-200 ${selectedValues.size < uniqueValues.length ? 'text-blue-600 bg-blue-50' : 'text-slate-400'}`}
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

  useEffect(() => {
    if (!columns) return;
    const initialFilters = {};
    columns.forEach(col => {
      initialFilters[col] = new Set(data.map(row => String(row[col] || '')));
    });
    setFilters(initialFilters);
  }, [data, columns]);

  const filteredData = useMemo(() => {
    if (!columns) return data;
    return data.filter(row => {
      return columns.every(col => {
        const allowedValues = filters[col];
        if (!allowedValues) return true;
        return allowedValues.has(String(row[col] || ''));
      });
    });
  }, [data, columns, filters]);

  if (!columns || columns.length === 0) {
    return null;
  }

  return (
    <div className="overflow-auto h-full w-full bg-white relative">
      <table className="w-full text-left border-collapse whitespace-nowrap">
        <thead className="sticky top-0 bg-slate-100 z-30 shadow-sm border-b border-slate-200">
          <tr>
            {columns.map(col => (
              <th key={col} className="px-3 py-2 border-r border-slate-200 text-xs font-semibold text-slate-700 bg-slate-50 relative align-middle">
                <div className="flex items-center justify-between">
                  <span>{col}</span>
                  <ColumnFilter 
                    column={col} 
                    data={data} 
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
          {filteredData.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick(row)}
              className={`cursor-pointer border-b border-slate-100 hover:bg-blue-50 transition-colors ${selectedRow === row ? 'bg-blue-100' : 'bg-white'}`}
            >
              {columns.map(col => (
                <td key={col} className="px-3 py-2 text-xs text-slate-700 border-r border-slate-100 last:border-r-0">
                  {row[col]}
                </td>
              ))}
            </tr>
          ))}
          {filteredData.length === 0 && (
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
  
  // File Metadata State
  const [fileMeta, setFileMeta] = useState({ name: '', date: '', version: '' });

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

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/upload", {
        method: "POST",
        body: formData,
      });
      const result = await response.json();
      
      if (result.status === "success") {
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

      } else {
        alert("Parsing failed: " + result.message);
      }
    } catch (error) {
      console.error("Upload error:", error);
      alert("Cannot connect to backend server. Please ensure Python backend is running at http://127.0.0.1:8000");
    } finally {
      setUploading(false);
    }
  };

  const handleFileUpload = (event) => {
    processFile(event.target.files[0]);
    event.target.value = ''; 
  };

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

  const onMasterRowClicked = useCallback((row) => {
    setSelectedParent(row);
    setDrawings([]);
    setSelectedDetail(null);
    setSharepointPath([]);

    const currentLevel = row.LEVEL !== undefined ? String(row.LEVEL) : null;
    let children = [];
    
    if (currentLevel === "0") {
      children = masterData.filter(d => d.COMPONENT === row.COMPONENT && String(d.LEVEL) === "0");
    } else if (currentLevel) {
      children = masterData.filter(d => 
        d.PARENT === row.COMPONENT && Number(d.LEVEL) === Number(row.LEVEL) + 1
      );
    } else {
      children = masterData.filter(d => d.PARENT === row.COMPONENT);
    }
    
    setDetailData(children);
  }, [masterData]);

  const onDetailRowClicked = useCallback(async (row) => {
    setSelectedDetail(row);
    setLoadingDrawings(true);
    setSharepointPath([]);

    const category = row.Category || 'Unknown Category';
    const component = row.COMPONENT || row.TOP_ASSY || 'Unknown Component';

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/search?category=${encodeURIComponent(category)}&component=${encodeURIComponent(component)}`);
      const data = await res.json();
      if (data.status === "success") {
        setDrawings(data.results);
        setSharepointPath(data.sharepoint_path || []);
      }
    } catch (error) {
      console.error("Fetch drawings failed:", error);
    } finally {
      setLoadingDrawings(false);
    }
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
                  <div className="flex items-center space-x-4 text-xs">
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
                {selectedParent && selectedParent.COMPONENT && (
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded border border-blue-200 shadow-sm">
                    Target Parent: <span className="font-mono font-bold">{selectedParent.COMPONENT}</span> (Level {selectedParent.LEVEL})
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
            {!selectedDetail ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <FileText size={48} className="mb-4 text-slate-300" />
                <p>Select a child component from the bottom-left table to view drawings.</p>
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