import React from 'react';
import { Database, History, Loader2, Upload } from 'lucide-react';

export const TopBar = ({ uploading, loadingHistory, onLoadHistory, onFileUpload }) => {
  return (
    <div className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm shrink-0 z-20">
      <div className="flex items-center space-x-2">
        <Database size={22} className="text-blue-600" />
        <h1 className="text-lg font-bold text-slate-800 tracking-tight">BOM & Drawings Workspace</h1>
      </div>
      <div className="flex items-center space-x-3">
        <button
          type="button"
          onClick={onLoadHistory}
          className="flex items-center px-4 py-2 bg-slate-100 border border-slate-300 text-slate-700 font-medium rounded shadow-sm hover:bg-slate-200 transition cursor-pointer"
        >
          {loadingHistory ? <Loader2 className="animate-spin mr-2" size={16} /> : <History size={16} className="mr-2" />}
          <span>Past Records</span>
        </button>

        <label className="flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded shadow hover:bg-blue-700 transition cursor-pointer">
          {uploading ? <Loader2 className="animate-spin mr-2" size={16} /> : <Upload size={16} className="mr-2" />}
          <span>{uploading ? 'Processing...' : 'Upload New BOM'}</span>
          <input type="file" accept=".csv, .xlsx" className="hidden" onChange={onFileUpload} />
        </label>
      </div>
    </div>
  );
};
