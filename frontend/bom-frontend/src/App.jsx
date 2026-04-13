import React, { useCallback, useState } from 'react';
import { Database, FileText, Upload } from 'lucide-react';

import { DrawingPanel } from './components/DrawingPanel';
import { ExcelTable } from './components/ExcelTable';
import { HistoryModal } from './components/HistoryModal';
import { TopBar } from './components/TopBar';
import { useBomUploadSave } from './hooks/useBomUploadSave';
import { useDragAndDropUpload } from './hooks/useDragAndDropUpload';
import { useDrawingSearch } from './hooks/useDrawingSearch';
import { useHistoryRecords } from './hooks/useHistoryRecords';
import { API_BASE_CANDIDATES, fetchApiWithFallback, getPrimaryApiBaseUrl } from './services/api';
import { getCaselessValue, normalizeKey } from './utils/bomTable';

const MAX_UPLOAD_BYTES = Number(import.meta.env.VITE_MAX_UPLOAD_BYTES || (100 * 1024 * 1024));

export default function App() {
  const [columns, setColumns] = useState([]);
  const [masterData, setMasterData] = useState([]);

  const {
    showHistory,
    setShowHistory,
    historyRecords,
    loadingHistory,
    loadHistory,
    deleteHistoryRecord,
  } = useHistoryRecords({ fetchApiWithFallback });

  const drawingSearch = useDrawingSearch({
    masterData,
    fetchApiWithFallback,
    getPrimaryApiBaseUrl,
  });

  const onHydrateTable = useCallback(({ rows, columns: nextColumns }) => {
    setMasterData(rows || []);
    setColumns(nextColumns || []);
  }, []);

  const onResetDependentView = useCallback(() => {
    drawingSearch.resetDrawingView();
  }, [drawingSearch.resetDrawingView]);

  const {
    fileMeta,
    setFileMeta,
    saveRecordId,
    savingAction,
    uploading,
    canSaveBoth,
    saveStatusLabel,
    saveStatusClass,
    loadBOMTable,
    handleFileUpload,
    saveBoth,
    downloadBOMFile,
    processFile,
  } = useBomUploadSave({
    fetchApiWithFallback,
    getPrimaryApiBaseUrl,
    apiBaseCandidates: API_BASE_CANDIDATES,
    maxUploadBytes: MAX_UPLOAD_BYTES,
    onHydrateTable,
    onResetDependentView,
  });

  const {
    isDragging,
    onDragEnter,
    onDragLeave,
    onDragOver,
    onDrop,
  } = useDragAndDropUpload(processFile);

  const handleLoadFromHistory = useCallback(async (recordId, fileName, version) => {
    const loaded = await loadBOMTable(recordId, fileName, version);
    if (loaded) {
      setShowHistory(false);
    }
  }, [loadBOMTable, setShowHistory]);

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans text-sm">
      <TopBar
        uploading={uploading}
        loadingHistory={loadingHistory}
        onLoadHistory={loadHistory}
        onFileUpload={handleFileUpload}
      />

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
                      onClick={saveBoth}
                      disabled={!canSaveBoth || Boolean(savingAction)}
                      className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-blue-600 text-white font-bold hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition shadow-sm"
                    >
                      <Database size={14} />
                      <span>{savingAction === 'both' ? 'Saving...' : 'Save to SQL'}</span>
                    </button>
                    <span className={`px-2.5 py-1 rounded border font-semibold ${saveStatusClass}`}>
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
                <ExcelTable
                  key={`master-${saveRecordId || 'draft'}-${columns.length}-${masterData.length}`}
                  data={masterData}
                  columns={columns}
                  onRowClick={drawingSearch.onMasterRowClicked}
                  selectedRow={drawingSearch.selectedParent}
                />
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
                {drawingSearch.selectedParent && normalizeKey(getCaselessValue(drawingSearch.selectedParent, 'PARENT')) && (
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded border border-blue-200 shadow-sm">
                    Target Parent: <span className="font-mono font-bold">{getCaselessValue(drawingSearch.selectedParent, 'PARENT')}</span>
                  </span>
                )}
              </div>
              <span className="text-xs font-medium text-slate-500 bg-slate-200 px-2 py-1 rounded-full">Total: {drawingSearch.detailData.length} Rows</span>
            </div>
            <div className="flex-1 overflow-hidden relative">
              {drawingSearch.selectedParent ? (
                <ExcelTable
                  key={`detail-${normalizeKey(getCaselessValue(drawingSearch.selectedParent, 'PARENT'))}-${drawingSearch.detailData.length}`}
                  data={drawingSearch.detailData}
                  columns={columns}
                  onRowClick={drawingSearch.onDetailRowClicked}
                  selectedRow={drawingSearch.selectedDetail}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-slate-400 italic">
                  Select a row from the Master Table above.
                </div>
              )}
            </div>
          </div>
        </div>

        <DrawingPanel
          selectedParent={drawingSearch.selectedParent}
          directoryScopes={drawingSearch.directoryScopes}
          componentTargets={drawingSearch.componentTargets}
          loadingDrawings={drawingSearch.loadingDrawings}
          drawings={drawingSearch.drawings}
          missingComponents={drawingSearch.missingComponents}
          onPreview={drawingSearch.previewDrawingFile}
          onDownload={drawingSearch.downloadDrawingFile}
        />

      </div>

      <HistoryModal
        show={showHistory}
        onClose={() => setShowHistory(false)}
        historyRecords={historyRecords}
        onLoadBOMTable={handleLoadFromHistory}
        onDownloadBOMFile={downloadBOMFile}
        onDeleteHistoryRecord={deleteHistoryRecord}
      />

    </div>
  );
}