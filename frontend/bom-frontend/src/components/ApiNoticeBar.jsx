import React from 'react';

const NOTICE_STYLE = {
  network: 'bg-amber-50 border-amber-200 text-amber-900',
  auth: 'bg-violet-50 border-violet-200 text-violet-900',
  not_found: 'bg-slate-100 border-slate-300 text-slate-800',
  validation: 'bg-yellow-50 border-yellow-200 text-yellow-900',
  server: 'bg-rose-50 border-rose-200 text-rose-900',
  unknown: 'bg-slate-100 border-slate-300 text-slate-800',
};

export const ApiNoticeBar = ({ notice, onDismiss }) => {
  if (!notice) {
    return null;
  }

  const style = NOTICE_STYLE[notice.kind] || NOTICE_STYLE.unknown;

  return (
    <div className={`mx-4 mt-3 rounded border px-4 py-3 shadow-sm ${style}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{notice.title}</p>
          <p className="mt-1 text-xs opacity-90 break-words">{notice.message}</p>
          {(notice.status || notice.requestId) && (
            <p className="mt-1 text-[11px] opacity-80">
              {notice.status ? `HTTP ${notice.status}` : 'HTTP n/a'}
              {notice.requestId ? ` • request_id: ${notice.requestId}` : ''}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded border border-current/20 px-2 py-1 text-xs font-medium hover:bg-white/30"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
};
