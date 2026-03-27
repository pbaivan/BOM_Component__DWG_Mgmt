import React, { useState, useMemo, useCallback } from 'react';
import { Upload, FileText, Download, Eye, Loader2, Database, Search } from 'lucide-react';

// 你提供的样例数据，用于在没有后端时也能测试前端联动逻辑
const SAMPLE_CSV_DATA = [
  { "TOP_ASSY": "04-00123456", "New or Existing in Old BOM": "Existing", "Prefix": "4", "Category": "Phantom", "RFP Modules": "SYSTEM INTEGRATION", "PARENT": "02-00123456", "COMPONENT": "02-00123456", "LEVEL": 0, "RV": "C", "DESC": "FB SERIES COMMON BOM", "QTY": 1, "UM": "EA", "NetWeight": 0, "WeightUnit": "" },
  { "TOP_ASSY": "04-00123456", "New or Existing in Old BOM": "Existing", "Prefix": "1", "Category": "Mech-Assy", "RFP Modules": "COMMON BOM | NON TECH MODULES", "PARENT": "02-00123456", "COMPONENT": "01-00128434", "LEVEL": 1, "RV": "A", "DESC": "NON CORE MODULES", "QTY": 1, "UM": "EA", "NetWeight": 0, "WeightUnit": "KG" },
  { "TOP_ASSY": "04-00123456", "New or Existing in Old BOM": "Existing", "Prefix": "4", "Category": "Phantom", "RFP Modules": "NON CORE TECH | MODULES", "PARENT": "01-00128434", "COMPONENT": "04-00189123", "LEVEL": 2, "RV": "F", "DESC": "MODULES", "QTY": 1, "UM": "EA", "NetWeight": 0, "WeightUnit": "KG" },
  { "TOP_ASSY": "04-00123456", "New or Existing in Old BOM": "Existing", "Prefix": "1", "Category": "Mech-Assy", "RFP Modules": "MODULES | FB VIBRATION ISOLATION ASSY", "PARENT": "04-00189123", "COMPONENT": "01-00194645", "LEVEL": 3, "RV": "B", "DESC": "FB VIBRATION ISOLATION ASSY (WO PAD)", "QTY": 1, "UM": "EA", "NetWeight": 0, "WeightUnit": "KG" },
  { "TOP_ASSY": "04-00123456", "New or Existing in Old BOM": "Existing", "Prefix": "1", "Category": "Mech-Assy", "RFP Modules": "MODULES | FB VIBRATION ISOLATION ASSY", "PARENT": "01-00194645", "COMPONENT": "01-00114563", "LEVEL": 4, "RV": "A", "DESC": "SUB ASSY", "QTY": 1, "UM": "EA", "NetWeight": 0, "WeightUnit": "KG" }
];

// 手写一个支持独立列搜索的高性能数据表格组件，替代外部依赖避免编译失败
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
              <th key={col.field} className="p-2 border border-slate-200 text-xs font-semibold text-slate-700 align-top">
                <div className="mb-1">{col.field}</div>
                <input
                  type="text"
                  className="w-full border border-gray-300 rounded px-1.5 py-1 font-normal text-xs focus:outline-none focus:border-blue-500"
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
              <td colSpan={columns.length} className="p-4 text-center text-gray-400 text-sm">
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
  // 核心状态管理
  const [masterData, setMasterData] = useState([]);
  const [detailData, setDetailData] = useState([]);
  const [selectedParent, setSelectedParent] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [drawings, setDrawings] = useState([]);
  const [loadingDrawings, setLoadingDrawings] = useState(false);

  // 简化后的列定义
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

  // 【核心交互1】左上方主表：点击某一行作为 PARENT，计算它的子级组件
  const onMasterRowClicked = useCallback((row) => {
    setSelectedParent(row);
    setDrawings([]); // 清空图纸
    setSelectedDetail(null);

    // 联动逻辑：找出当前被点击行的直属子级
    let children = [];
    if (row.LEVEL === 0) {
      // Level 0 特例：展示它自己
      children = masterData.filter(d => d.COMPONENT === row.COMPONENT && d.LEVEL === 0);
    } else {
      // Level N 递进：找 PARENT = 选中行的 COMPONENT，且 LEVEL = 选中行 LEVEL + 1
      children = masterData.filter(d => 
        d.PARENT === row.COMPONENT && d.LEVEL === row.LEVEL + 1
      );
    }
    setDetailData(children);
  }, [masterData]);

  // 【核心交互2】左下方子表：点击某一行 COMPONENT，去 SharePoint (后端) 查图纸
  const onDetailRowClicked = useCallback(async (row) => {
    setSelectedDetail(row);
    setLoadingDrawings(true);

    try {
      // 真实后端调用 (如果你运行了 Python 后端)
      // const res = await fetch(`http://localhost:8000/api/search?category=${row.Category}&component=${row.COMPONENT}`);
      // const data = await res.json();
      // setDrawings(data.results);
      
      // 这里为了 Canvas 纯前端演示，模拟了后端的延迟和返回
      setTimeout(() => {
        setDrawings([
          { id: "1", name: `${row.COMPONENT}A01_Assy.pdf`, version: "A01", type: "PDF" },
          { id: "2", name: `${row.COMPONENT}B01_Part.pdf`, version: "B01", type: "PDF" },
          { id: "3", name: `${row.COMPONENT}_Model.step`, version: "-", type: "CAD" }
        ]);
        setLoadingDrawings(false);
      }, 600);
    } catch (error) {
      console.error("搜索图纸失败:", error);
      setLoadingDrawings(false);
    }
  }, []);

  // 模拟文件上传读取
  const handleLoadSample = () => {
    setMasterData(SAMPLE_CSV_DATA);
    setDetailData([]);
    setSelectedParent(null);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans text-sm">
      {/* 顶部导航 */}
      <div className="h-14 bg-white border-b flex items-center justify-between px-6 shadow-sm shrink-0">
        <div className="flex items-center space-x-2">
          <Database size={20} className="text-blue-600" />
          <h1 className="text-lg font-bold text-slate-800">Phase 1: BOM 解析与图纸联动引擎</h1>
        </div>
        <div className="flex space-x-3">
          <button 
            onClick={handleLoadSample}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
          >
            <Upload size={16} className="mr-2" /> 载入并解析示例 BOM
          </button>
        </div>
      </div>

      {/* 主体布局 */}
      <div className="flex flex-1 overflow-hidden p-4 space-x-4">
        
        {/* 左侧区域：分为上下两个 ag-Grid 表格 */}
        <div className="w-7/12 flex flex-col space-y-4">
          
          {/* 左上：全量数据区 */}
          <div className="flex-1 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
            <div className="px-4 py-2 border-b bg-slate-50 flex justify-between items-center">
              <h2 className="font-semibold text-slate-700">1. 全量 BOM 筛查区 (Master Table)</h2>
              <span className="text-xs text-gray-500">共 {masterData.length} 行记录 (支持表头高级筛选)</span>
            </div>
            <div className="flex-1 overflow-hidden relative">
              {masterData.length > 0 ? (
                <CustomTable
                  data={masterData}
                  columns={columnDefs}
                  onRowClick={onMasterRowClicked}
                  selectedRow={selectedParent}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-400">请点击右上角按钮载入 BOM 数据</div>
              )}
            </div>
          </div>

          {/* 左下：子组件清单区 */}
          <div className="h-1/3 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
             <div className="px-4 py-2 border-b bg-slate-50 flex items-center">
              <h2 className="font-semibold text-slate-700 mr-4">2. 所需子组件清单 (Detail Table)</h2>
              {selectedParent && (
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
                  当前生产目标: {selectedParent.COMPONENT} (Level: {selectedParent.LEVEL})
                </span>
              )}
            </div>
            <div className="flex-1 overflow-hidden relative">
              <CustomTable
                  data={detailData}
                  columns={columnDefs}
                  onRowClick={onDetailRowClicked}
                  selectedRow={selectedDetail}
              />
            </div>
          </div>
        </div>

        {/* 右侧区域：SharePoint 图纸结果 */}
        <div className="w-5/12 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
          <div className="px-4 py-2 border-b bg-slate-50">
            <h2 className="font-semibold text-slate-700">3. SharePoint 关联图纸区</h2>
          </div>
          
          <div className="flex-1 p-4 overflow-auto">
            {!selectedDetail ? (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <FileText size={48} className="mb-4 text-gray-300" />
                <p>请在左下方的子组件清单中，选择一个具体的组件型号</p>
              </div>
            ) : (
              <div>
                <div className="mb-4 p-3 bg-slate-50 rounded border border-slate-200">
                  <p className="text-sm text-gray-600 mb-1">正在 SharePoint 中检索：</p>
                  <p className="font-mono font-bold text-lg text-slate-800">{selectedDetail.COMPONENT}</p>
                  <p className="text-xs text-gray-500 mt-1">限定目录范围: Category = [{selectedDetail.Category}]</p>
                </div>

                {loadingDrawings ? (
                   <div className="flex items-center justify-center py-10 text-blue-500">
                     <Loader2 className="animate-spin mr-2" size={20} />
                     <span>正在调用 Graph API...</span>
                   </div>
                ) : drawings.length > 0 ? (
                  <div className="space-y-3">
                    {drawings.map(drawing => (
                      <div key={drawing.id} className="flex items-center justify-between p-3 border border-slate-200 rounded hover:border-blue-400 hover:shadow-sm transition">
                         <div className="flex items-center space-x-3">
                            <div className={`w-10 h-10 rounded flex items-center justify-center text-white font-bold text-xs ${drawing.type === 'PDF' ? 'bg-red-500' : 'bg-indigo-500'}`}>
                              {drawing.type}
                            </div>
                            <div>
                              <p className="text-sm font-medium text-slate-800">{drawing.name}</p>
                              <p className="text-xs text-gray-500 mt-0.5">版本: {drawing.version}</p>
                            </div>
                         </div>
                         <div className="flex space-x-2">
                            <button className="p-1.5 text-gray-500 hover:text-blue-600 bg-gray-50 hover:bg-blue-50 rounded transition border">
                              <Eye size={16} />
                            </button>
                            <button className="p-1.5 text-gray-500 hover:text-blue-600 bg-gray-50 hover:bg-blue-50 rounded transition border">
                              <Download size={16} />
                            </button>
                         </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-10 text-gray-500">
                    在当前 Category 下未搜索到该组件的图纸。
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