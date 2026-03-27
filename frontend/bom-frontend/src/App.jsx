import React, { useState, useMemo, useCallback } from 'react';
import { Upload, FileText, Download, Eye, Loader2, Database } from 'lucide-react';

const CustomTable = ({ data, columns, onRowClick, selectedRow }) => {
  const [filters, setFilters] = useState({});

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({ ...prev, [field]: value }));
  };

  const filteredData = data.filter(row => {
    return columns.every(col => {
      if (!filters[col.field]) return true;
      return String(row[col.field]).toLowerCase().includes(filters[col.field].toLowerCase());
    });
  });

  return (
    <div className="overflow-auto h-full w-full bg-white relative">
      <table className="w-full text-left border-collapse min-w-max">
        <thead className="sticky top-0 bg-slate-100 z-10 shadow-sm">
          <tr>
            {columns.map(col => (
              <th key={col.field} className="p-2 border border-slate-200 text-xs font-semibold text-slate-700 align-top bg-slate-50">
                <div className="mb-1">{col.field}</div>
                <input
                  type="text"
                  className="w-full border border-gray-300 rounded px-1.5 py-1 font-normal text-xs focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="筛选..."
                  value={filters[col.field] || ''}
                  onChange={e => handleFilterChange(col.field, e.target.value)}
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filteredData.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick(row)}
              className={`cursor-pointer border-b border-slate-200 hover:bg-blue-50 transition-colors ${selectedRow === row ? 'bg-blue-100' : 'bg-white'}`}
            >
              {columns.map(col => (
                <td key={col.field} className={`p-2 text-xs text-gray-800 ${col.cellClass || ''}`}>
                  {row[col.field]}
                </td>
              ))}
            </tr>
          ))}
          {filteredData.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="p-6 text-center text-gray-400 text-sm">
                没有找到匹配的数据
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default function App() {
  const [masterData, setMasterData] = useState([]);
  const [detailData, setDetailData] = useState([]);
  const [selectedParent, setSelectedParent] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [drawings, setDrawings] = useState([]);
  const [loadingDrawings, setLoadingDrawings] = useState(false);
  const [uploading, setUploading] = useState(false);

  const columnDefs = useMemo(() => [
    { field: 'Prefix' },
    { field: 'Category' },
    { field: 'PARENT', cellClass: 'font-mono text-blue-600' },
    { field: 'COMPONENT', cellClass: 'font-mono font-bold' },
    { field: 'LEVEL' },
    { field: 'RV' },
    { field: 'DESC' },
    { field: 'QTY' },
    { field: 'UM' }
  ], []);

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
        setMasterData(result.data);
        setDetailData([]);
        setSelectedParent(null);
        setDrawings([]);
      } else {
        alert("解析失败: " + result.message);
      }
    } catch (error) {
      console.error("上传错误:", error);
      alert("无法连接到后端，请确保 PyCharm 中的 Python 后端正在运行！");
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const onMasterRowClicked = useCallback((row) => {
    setSelectedParent(row);
    setDrawings([]);
    setSelectedDetail(null);

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

  const onDetailRowClicked = useCallback(async (row) => {
    setSelectedDetail(row);
    setLoadingDrawings(true);

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/search?category=${row.Category}&component=${row.COMPONENT}`);
      const data = await res.json();
      if (data.status === "success") {
        setDrawings(data.results);
      }
    } catch (error) {
      console.error("获取图纸失败:", error);
    } finally {
      setLoadingDrawings(false);
    }
  }, []);

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans text-sm">
      <div className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm shrink-0">
        <div className="flex items-center space-x-2">
          <Database size={22} className="text-blue-600" />
          <h1 className="text-lg font-bold text-slate-800 tracking-tight">BOM & Drawings Workspace (Mock Phase)</h1>
        </div>
        <div>
          <label className="flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded shadow hover:bg-blue-700 transition cursor-pointer">
            {uploading ? <Loader2 className="animate-spin mr-2" size={16} /> : <Upload size={16} className="mr-2" />}
            <span>{uploading ? "正在解析..." : "上传 Excel/CSV BOM"}</span>
            <input type="file" accept=".csv, .xlsx" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden p-4 space-x-4">
        <div className="w-7/12 flex flex-col space-y-4">
          <div className="flex-1 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b bg-slate-50 flex justify-between items-center">
              <h2 className="font-semibold text-slate-700">1. 全量 BOM 筛查区</h2>
              <span className="text-xs font-medium text-slate-500 bg-slate-200 px-2 py-1 rounded-full">共 {masterData.length} 行记录</span>
            </div>
            <div className="flex-1 overflow-hidden relative">
              {masterData.length > 0 ? (
                <CustomTable data={masterData} columns={columnDefs} onRowClick={onMasterRowClicked} selectedRow={selectedParent} />
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-400">
                  <FileText size={40} className="mb-3 text-slate-300" />
                  <p>请点击右上角按钮上传您的 BOM 文件</p>
                </div>
              )}
            </div>
          </div>

          <div className="h-1/3 min-h-[250px] bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
             <div className="px-4 py-3 border-b bg-slate-50 flex items-center">
              <h2 className="font-semibold text-slate-700 mr-4">2. 所需子组件清单</h2>
              {selectedParent && (
                <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded border border-blue-200 shadow-sm">
                  目标 Parent: <span className="font-mono font-bold">{selectedParent.COMPONENT}</span> (Level {selectedParent.LEVEL})
                </span>
              )}
            </div>
            <div className="flex-1 overflow-hidden relative">
              {selectedParent ? (
                <CustomTable data={detailData} columns={columnDefs} onRowClick={onDetailRowClicked} selectedRow={selectedDetail} />
              ) : (
                <div className="h-full flex items-center justify-center text-slate-400 italic">
                  请先在上方表格选中一行作为目标 Parent
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="w-5/12 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b bg-slate-50">
            <h2 className="font-semibold text-slate-700">3. SharePoint 模拟关联图纸</h2>
          </div>
          <div className="flex-1 p-4 overflow-auto bg-slate-50/50">
            {!selectedDetail ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <FileText size={48} className="mb-4 text-slate-300" />
                <p>请在左下方的子组件清单中，选择一个具体的组件型号</p>
              </div>
            ) : (
              <div>
                <div className="mb-4 p-4 bg-white rounded-lg shadow-sm border border-slate-200">
                  <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">正在检索组件</p>
                  <p className="font-mono font-bold text-xl text-blue-700">{selectedDetail.COMPONENT}</p>
                </div>
                {loadingDrawings ? (
                   <div className="flex flex-col items-center justify-center py-12 text-blue-500">
                     <Loader2 className="animate-spin mb-3" size={28} />
                     <span className="text-sm font-medium">正在通过 Graph API 获取图纸 (Mock)...</span>
                   </div>
                ) : drawings.length > 0 ? (
                  <div className="space-y-3">
                    {drawings.map(drawing => (
                      <div key={drawing.id} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg shadow-sm hover:border-blue-400 hover:shadow-md transition-all">
                         <div className="flex items-center space-x-4">
                            <div className={`w-12 h-12 rounded flex items-center justify-center text-white font-bold text-sm shadow-inner ${drawing.type === 'PDF' ? 'bg-red-500' : 'bg-indigo-500'}`}>
                              {drawing.type}
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-slate-800">{drawing.name}</p>
                            </div>
                         </div>
                         <div className="flex space-x-2">
                            <button className="p-2 text-slate-500 hover:text-blue-600 border rounded shadow-sm"><Eye size={18} /></button>
                            <button className="p-2 text-slate-500 hover:text-blue-600 border rounded shadow-sm"><Download size={18} /></button>
                         </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500">未在 SharePoint 中搜索到该组件的图纸。</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}