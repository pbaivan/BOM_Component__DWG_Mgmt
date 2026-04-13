import React, { useMemo, useState } from 'react';
import { ChevronRight, Download, Eye, FileText, FolderOpen, HardDrive, Loader2, Search } from 'lucide-react';

export const DrawingPanel = ({
  selectedParent,
  directoryScopes,
  componentTargets,
  loadingDrawings,
  drawings,
  missingComponents,
  onPreview,
  onDownload,
  onBatchDownload,
  batchDownloading,
}) => {
  const drawingKey = (drawing) => `${drawing?.id || drawing?.item_id || drawing?.name || 'drawing'}::${drawing?.sourceComponent || ''}`;
  const [selectedDrawingKeys, setSelectedDrawingKeys] = useState(() => new Set());

  const selectedDrawings = useMemo(
    () => drawings.filter((drawing) => selectedDrawingKeys.has(drawingKey(drawing))),
    [drawings, selectedDrawingKeys],
  );

  const allSelected = drawings.length > 0 && selectedDrawings.length === drawings.length;

  const onToggleAll = () => {
    if (allSelected) {
      setSelectedDrawingKeys(new Set());
      return;
    }
    setSelectedDrawingKeys(new Set(drawings.map(drawingKey)));
  };

  const onToggleDrawing = (drawing) => {
    const key = drawingKey(drawing);
    setSelectedDrawingKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const onBatchDownloadClick = () => {
    if (!onBatchDownload || selectedDrawings.length === 0) {
      return;
    }
    onBatchDownload(selectedDrawings);
  };

  return (
    <div className="w-5/12 bg-white rounded-lg shadow-sm border border-slate-200 flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b bg-slate-50">
        <h2 className="font-semibold text-slate-700">3. SharePoint Drawings</h2>
      </div>

      <div className="flex-1 p-4 overflow-auto bg-slate-50/50">
        {!selectedParent ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400">
            <FileText size={48} className="mb-4 text-slate-300" />
            <p>Select a row from the top-left table to view all related drawings.</p>
          </div>
        ) : (
          <div>
            {(directoryScopes.length > 0 || componentTargets.length > 0) && (
              <div className="mb-4 bg-white border border-slate-200 rounded-lg shadow-sm p-3">
                <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Directory Path</p>
                <div className="space-y-2 text-sm text-slate-600">
                  {directoryScopes.map((scope) => (
                    <div key={`${scope.site}-${scope.root}-${scope.category}`} className="flex flex-wrap items-center gap-y-1">
                      <HardDrive size={16} className="text-slate-400 mr-1 shrink-0" />
                      <span className="flex items-center px-2 py-1 rounded hover:bg-slate-100 cursor-pointer">{scope.site}</span>
                      <ChevronRight size={14} className="text-slate-300 shrink-0" />
                      <span className="flex items-center px-2 py-1 rounded hover:bg-slate-100 cursor-pointer">
                        <FolderOpen size={14} className="mr-1.5 text-blue-500" />
                        {scope.root}
                      </span>
                      <ChevronRight size={14} className="text-slate-300 shrink-0" />
                      <span className="flex items-center px-2 py-1 rounded bg-blue-50 text-blue-700 font-semibold border border-blue-100">
                        <FolderOpen size={14} className="mr-1.5 text-blue-500" />
                        {scope.category}
                      </span>
                      <ChevronRight size={14} className="text-slate-300 shrink-0" />
                    </div>
                  ))}

                  {componentTargets.length > 0 && (
                    <div className="pt-2 border-t border-slate-100">
                      <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">Components</p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {componentTargets.map((component) => (
                          <span key={component} className="inline-flex items-center px-2 py-1 rounded bg-blue-50 text-blue-700 font-semibold border border-blue-100">
                            <FileText size={13} className="mr-1" />
                            {component}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {loadingDrawings ? (
              <div className="flex flex-col items-center justify-center py-12 text-blue-500">
                <Loader2 className="animate-spin mb-3" size={28} />
                <span className="text-sm font-medium">Fetching drawings via API...</span>
              </div>
            ) : drawings.length > 0 ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase">Found {drawings.length} matching files</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="inline-flex items-center gap-1.5 text-xs text-slate-600">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={onToggleAll}
                        className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      Select All
                    </label>
                    <span className="text-xs text-slate-500">Selected {selectedDrawings.length}</span>
                    <button
                      type="button"
                      disabled={selectedDrawings.length === 0 || batchDownloading}
                      onClick={onBatchDownloadClick}
                      className="inline-flex items-center gap-1.5 rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {batchDownloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                      <span>{batchDownloading ? 'Downloading...' : `Batch Download (${selectedDrawings.length})`}</span>
                    </button>
                  </div>
                </div>

                {missingComponents.length > 0 && (
                  <div className="bg-orange-50 border border-orange-200 text-orange-800 p-3 rounded-lg shadow-sm text-sm">
                    <p className="font-semibold mb-1 flex items-center"><Search size={16} className="mr-1.5" /> No Drawings Found</p>
                    <p className="mb-2 opacity-90">The following components have no drawings associated with them in SharePoint:</p>
                    <div className="flex flex-wrap gap-2">
                      {missingComponents.map((component) => (
                        <span key={`draw-miss-${component}`} className="px-2 py-0.5 bg-orange-100/50 border border-orange-200 rounded text-xs font-medium">
                          {component}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  {drawings.map((drawing) => (
                    <div key={drawingKey(drawing)} className="flex flex-col sm:flex-row sm:items-center justify-between p-3 bg-white border border-slate-200 rounded-lg shadow-sm hover:border-blue-400 hover:shadow-md transition-all group gap-y-3 sm:gap-y-0">
                      <div className="flex items-center space-x-4">
                        <input
                          type="checkbox"
                          checked={selectedDrawingKeys.has(drawingKey(drawing))}
                          onChange={() => onToggleDrawing(drawing)}
                          className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                          aria-label={`Select ${drawing.name || 'drawing'} for batch download`}
                        />
                        <div className={`w-12 h-12 rounded flex shrink-0 items-center justify-center text-white font-bold text-sm shadow-inner ${String(drawing.type || '').toUpperCase() === 'PDF' ? 'bg-red-500' : 'bg-indigo-500'}`}>
                          {drawing.type}
                        </div>
                        <div className="min-w-0 pr-4">
                          <p className="text-sm font-semibold text-slate-800 group-hover:text-blue-700 transition-colors break-words">{drawing.name}</p>
                          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500 mt-1">
                            <span className="font-medium bg-slate-100 rounded px-1.5 py-0.5">Component: {drawing.sourceComponent || '-'}</span>
                            <span className="mt-1">Revision: {drawing.version}</span>
                            <span className="mt-1">{drawing.date}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex space-x-2 shrink-0">
                        <button onClick={() => onPreview(drawing)} className="p-2 inline-flex items-center justify-center bg-white text-slate-500 hover:text-blue-600 hover:bg-blue-50 border border-slate-200 rounded shadow-sm transition-colors" title="Preview Online">
                          <Eye size={18} />
                        </button>
                        <button onClick={() => onDownload(drawing)} className="p-2 inline-flex items-center justify-center bg-white text-slate-500 hover:text-blue-600 hover:bg-blue-50 border border-slate-200 rounded shadow-sm transition-colors" title="Download">
                          <Download size={18} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-10 px-4 text-slate-500 bg-white border border-dashed border-slate-300 rounded-lg mt-4">
                <p className="mb-2 font-medium text-slate-600">No drawings found in SharePoint.</p>

                {missingComponents.length > 0 && (
                  <div className="mt-4 bg-orange-50 border border-orange-200 text-orange-800 p-3 rounded-lg shadow-sm text-sm text-left">
                    <p className="font-semibold mb-1 flex items-center justify-center"><Search size={16} className="mr-1.5" /> Missing Drawings</p>
                    <p className="mb-2 opacity-90 text-center">The following components have no drawings associated with them in SharePoint:</p>
                    <div className="flex flex-wrap justify-center gap-2 mt-3">
                      {missingComponents.map((component) => (
                        <span key={`draw-miss-empty-${component}`} className="px-2 py-0.5 bg-orange-100/60 border border-orange-200 rounded text-xs font-medium">
                          {component}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
