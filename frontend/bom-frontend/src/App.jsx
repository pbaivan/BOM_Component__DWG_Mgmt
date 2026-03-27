import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Download, Eye, Loader2, Database, Filter, Search } from 'lucide-react';

// Custom hook to handle clicks outside the filter dropdown
const useOutsideClick = (callback) => {
  const ref = useRef();
  useEffect(() => {
    const handleClick = (event) => {
      if (ref.current && !ref.current.contains(event.target)) {
        callback();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [callback]);
  return ref;
};

// Excel-like Filter Menu Component
const ColumnFilter = ({ column, data, filters, setFilters, isOpen, toggleMenu, closeMenu }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const menuRef = useOutsideClick(closeMenu);

  // Extract unique values for this column
  const uniqueValues = useMemo(() => {
    const values = new Set(data.map(row => String(row[column] || '')));
    return Array.from(values).sort();
  }, [data, column]);

  // Filter unique values based on search input
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

  return (
    <div className="relative inline-block ml-2" ref={menuRef}>
      <button 
        onClick={(e) => { e.stopPropagation(); toggleMenu(); }}
        className={`p-1 rounded hover:bg-slate-200 transition-colors ${selectedValues.size < uniqueValues.length ? 'text-blue-600' : 'text-slate-400'}`}
      >
        <Filter size={14} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-slate-200 rounded-lg shadow-xl z-50 p-3 font-normal">
          <div className="relative mb-2">
            <Search size={14} className="absolute left-2 top-2 text-slate-400" />
            <input 
              type="text" 
              placeholder="Search..." 
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
                className="mr-2 rounded border-slate-300"
              />
              <span className="text-xs font-semibold text-slate-700">(Select All)</span>
            </label>
            {displayValues.map((val, idx) => (
              <label key={idx} className="flex items-center p-1 hover:bg-slate-50 cursor-pointer rounded">
                <input 
                  type="checkbox" 
                  checked={selectedValues.has(val)} 
                  onChange={() => handleCheckboxChange(val)}
                  className="mr-2 rounded border-slate-300"
                />
                <span className="text-xs text-slate-600 truncate">{val === '' ? '(Blank)' : val}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Main Table Component with Dynamic Columns
const ExcelTable = ({ data, columns, onRowClick, selectedRow }) => {
  const [filters, setFilters] = useState({});
  const [openMenuColumn, setOpenMenuColumn] = useState(null);

  // Initialize filters when data/columns change
  useEffect(() => {
    const initialFilters = {};
    columns.forEach(col => {
      initialFilters[col] = new Set(data.map(row => String(row[col] || '')));
    });
    setFilters(initialFilters);
  }, [data, columns]);

  // Apply filters
  const filteredData = useMemo(() => {
    return data.filter(row => {
      return columns.every(col => {
        const allowedValues = filters[col];
        if (!allowedValues) return true;
        return allowedValues.has(String(row[col] || ''));
      });
    });
  }, [data, columns, filters]);

  if (!columns || columns.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-slate-400">
        No data available to display.
      </div>
    );
  }

  return (
    <div className="overflow-auto h-full w-full bg-white">
      <table className="w-full text-left border-collapse whitespace-nowrap">
        <thead className="sticky top-0 bg-slate-100 z-10 shadow-sm border-b border-slate-200">
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
                No matching records found.
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

  // Upload Excel/CSV
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
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
        setColumns(result.columns);
        setMasterData(result.data);
        setDetailData([]);
        setSelectedParent(null);
        setDrawings([]);
      } else {
        alert("Parsing failed: " + result.message);
      }
    } catch (error) {
      console.error("Upload error:", error);
      alert("Cannot connect to backend server. Please ensure Python backend is running at http://127.0.0.1:8000");
    } finally {
      setUploading(false);
      event.target.value = ''; 
    }
  };

  // Master Table Row Click
  const onMasterRowClicked = useCallback((row) => {
    setSelectedParent(row);
    setDrawings([]);
    setSelectedDetail(null);

    // Calculate children based on PARENT and LEVEL logic
    let children = [];
    if (String(row.LEVEL) === "0") {
      children = masterData.filter(d => d.COMPONENT === row.COMPONENT && String(d.LEVEL) === "0");
    } else {
      children = masterData.filter(d => 
        d.PARENT === row.COMPONENT && Number(d.LEVEL) === Number(row.LEVEL) + 1
      );
    }
    setDetailData(children);
  }, [masterData]);

  // Detail Table Row Click (Call Mock API)
  const onDetailRowClicked = useCallback(async (row) => {
    setSelectedDetail(row);
    setLoadingDrawings(true);

    // Default parameters for search if specific columns are missing
    const category = row.Category || 'Unknown';
    const component = row.COMPONENT || row.TOP_ASSY || 'Unknown';

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/search?category=${category}&component=${component}`);
      const data = await res.json();
      if (data.status === "success") {
        setDrawings(data.results);
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
      <div className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm shrink-0">
        <div className="flex items-center space-x-2">
          <Database size={22} className="text-blue-600" />
          <h1 className="text-lg font-bold text-slate-800 tracking-tight">BOM & Drawings Workspace</h1>
        </div>
        <div>
          <label className="flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded shadow hover:bg-blue-700 transition cursor-pointer">
            {uploading ? <Loader2 className="animate-spin mr-2" size={16} /> : <Upload size={16} className="mr-2" />}
            <span>{uploading ? "Processing..." : "Upload File (.xlsx / .csv)"}</span>
            <input type="file" accept=".csv, .xlsx" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
      </div>

      {/* Main Layout */}
      <div className="flex flex-1 overflow-hidden p-4 space-x-4">
        
        {/* Left Section (Master & Detail Tables) */}
        <div className="w-7/12 flex flex-col space-y-4">
          
          {/* Master Table */}
          <div className="flex-1 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b bg-slate-50 flex justify-between items-center">
              <h2 className="font-semibold text-slate-700">1. Master BOM Table</h2>
              <span className="text-xs font-medium text-slate-500 bg-slate-200 px-2 py-1 rounded-full">Total: {masterData.length} Rows</span>
            </div>
            <div className="flex-1 overflow-hidden relative">
              {masterData.length > 0 ? (
                <ExcelTable data={masterData} columns={columns} onRowClick={onMasterRowClicked} selectedRow={selectedParent} />
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-400">
                  <FileText size={40} className="mb-3 text-slate-300" />
                  <p>Please upload a BOM file to begin.</p>
                </div>
              )}
            </div>
          </div>

          {/* Detail Table */}
          <div className="h-1/3 min-h-[250px] bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
             <div className="px-4 py-3 border-b bg-slate-50 flex items-center">
              <h2 className="font-semibold text-slate-700 mr-4">2. Required Child Components</h2>
              {selectedParent && selectedParent.COMPONENT && (
                <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded border border-blue-200 shadow-sm">
                  Target Parent: <span className="font-mono font-bold">{selectedParent.COMPONENT}</span> (Level {selectedParent.LEVEL})
                </span>
              )}
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
            <h2 className="font-semibold text-slate-700">3. SharePoint Drawings (Mock)</h2>
          </div>
          
          <div className="flex-1 p-4 overflow-auto bg-slate-50/50">
            {!selectedDetail ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <FileText size={48} className="mb-4 text-slate-300" />
                <p>Select a child component from the bottom-left table to view drawings.</p>
              </div>
            ) : (
              <div>
                <div className="mb-4 p-4 bg-white rounded-lg shadow-sm border border-slate-200">
                  <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Currently Searching</p>
                  <p className="font-mono font-bold text-xl text-blue-700">{selectedDetail.COMPONENT || 'Unknown Model'}</p>
                </div>

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