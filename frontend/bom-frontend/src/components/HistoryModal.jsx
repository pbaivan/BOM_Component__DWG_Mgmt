import React from 'react';
import { Database } from 'lucide-react';

export const HistoryModal = ({
  show,
  onClose,
  historyRecords,
  onLoadBOMTable,
  onDownloadBOMFile,
  onDeleteHistoryRecord,
}) => {
  if (!show) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white w-3/4 max-w-5xl rounded-lg shadow-xl overflow-hidden flex flex-col h-4/5 max-h-[800px]">
        <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-slate-50">
          <h2 className="text-lg font-bold text-slate-800">Historical BOM Workspace</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition"
          >
            ✕ Close
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4 bg-white">
          {historyRecords.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-slate-400 h-full">
              <Database size={48} className="mb-4 text-slate-300" />
              <p>No historical BOMs discovered in the central database.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded border border-slate-200">
              <table className="w-full text-left border-collapse text-sm">
                <thead className="bg-slate-100 border-b border-slate-200">
                  <tr>
                    <th className="py-3 justify-center px-4 font-semibold text-slate-700 whitespace-nowrap">Status</th>
                    <th className="py-3 px-4 font-semibold text-slate-700">Identified BOM Title</th>
                    <th className="py-3 px-4 font-semibold text-slate-700">Lines</th>
                    <th className="py-3 px-4 font-semibold text-slate-700">Uploaded timestamp</th>
                    <th className="py-3 px-4 font-semibold text-slate-700 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {historyRecords.map((record) => (
                    <tr key={record.record_id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        {record.status === 'paired'
                          ? <span className="text-xs bg-emerald-100 border border-emerald-200 text-emerald-800 font-bold px-2 py-0.5 rounded-full">Paired</span>
                          : <span className="text-xs bg-slate-200 border border-slate-300 text-slate-700 px-2 py-0.5 rounded-full">{record.status}</span>}
                      </td>
                      <td className="py-2.5 px-4 font-medium text-slate-800">
                        {record.file_name || record.original_file_name || 'Legacy Data File'}
                      </td>
                      <td className="py-2.5 px-4 text-slate-600 tabular-nums">
                        {record.bom_row_count || '?'}
                      </td>
                      <td className="py-2.5 px-4 text-slate-500 text-xs tabular-nums">
                        {new Date(record.updated_at).toLocaleString()}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap text-right space-x-2">
                        <button
                          onClick={() => onLoadBOMTable(record.record_id, record.file_name, record.version)}
                          className="px-3 py-1.5 text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 rounded hover:bg-blue-100 transition shadow-sm"
                        >
                          Load SQL Data Table
                        </button>
                        {record.file_saved && (
                          <button
                            onClick={() => onDownloadBOMFile(record.record_id)}
                            className="px-3 py-1.5 text-xs font-semibold bg-slate-50 text-slate-700 border border-slate-300 rounded hover:bg-slate-100 transition shadow-sm"
                          >
                            ⬇ Raw Excel .xlsx
                          </button>
                        )}
                        <button
                          onClick={() => onDeleteHistoryRecord(record.record_id)}
                          className="px-3 py-1.5 text-xs font-semibold bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition shadow-sm"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
