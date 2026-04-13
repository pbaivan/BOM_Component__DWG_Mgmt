import { useCallback, useMemo, useState } from 'react';

import { classifyApiFailure } from '../utils/apiError';

export const useBomUploadSave = ({
  fetchApiWithFallback,
  getPrimaryApiBaseUrl,
  maxUploadBytes,
  onHydrateTable,
  onResetDependentView,
  onApiError,
}) => {
  const [fileMeta, setFileMeta] = useState({ name: '', date: '', version: '' });
  const [uploadedBOMFile, setUploadedBOMFile] = useState(null);
  const [saveRecordId, setSaveRecordId] = useState('');
  const [saveState, setSaveState] = useState({
    status: 'draft',
    file_saved: false,
    metadata_saved: false,
  });
  const [savingAction, setSavingAction] = useState('');
  const [uploading, setUploading] = useState(false);

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

  const loadBOMTable = useCallback(async (recordId, fileName, version) => {
    try {
      setUploading(true);
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback(`/api/save/table/${recordId}`);
      if (!ok || !payload) {
        onApiError?.(classifyApiFailure({
          operation: 'Load BOM table',
          status,
          payload,
          baseUrl,
        }));
        return false;
      }

      onHydrateTable({
        rows: payload.rows || [],
        columns: payload.columns || [],
      });

      setFileMeta({
        name: fileName || payload.table_state?.source_file_name || 'historical.xlsx',
        date: payload.table_state?.saved_at ? new Date(payload.table_state.saved_at).toLocaleString() : 'Past',
        version: version || '1.0',
      });

      applySaveState(payload);
      onResetDependentView();
      return true;
    } catch (err) {
      console.error(err);
      onApiError?.(classifyApiFailure({
        operation: 'Load BOM table',
        error: err,
      }));
      return false;
    } finally {
      setUploading(false);
    }
  }, [applySaveState, fetchApiWithFallback, onApiError, onHydrateTable, onResetDependentView]);

  const processFile = useCallback(async (file) => {
    if (!file) return;

    const extension = file.name.toLowerCase().split('.').pop();
    if (!['xlsx', 'csv'].includes(extension)) {
      alert('Invalid file type. Please upload a .xlsx or .csv file.');
      return;
    }

    if (file.size > maxUploadBytes) {
      alert(`File is too large. Max allowed size is ${Math.floor(maxUploadBytes / (1024 * 1024))} MB.`);
      return;
    }

    resetSaveState();
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const result = payload || {};

      if (ok && result.status === 'success') {
        const fetchedCols = result.columns && result.columns.length > 0
          ? result.columns
          : (result.data && result.data.length > 0 ? Object.keys(result.data[0]) : []);

        onHydrateTable({
          rows: result.data || [],
          columns: fetchedCols,
        });
        onResetDependentView();

        const now = new Date();
        const formattedDate = `${now.toLocaleDateString()} ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        setFileMeta({
          name: file.name,
          date: formattedDate,
          version: '1.0',
        });
        setUploadedBOMFile(file);

        if (result.record_id) {
          applySaveState(result);
        } else {
          alert('BOM uploaded, but backend did not return a record ID for database persistence.');
        }
      } else {
        const reason = result.message || `HTTP ${status}`;
        onApiError?.(classifyApiFailure({
          operation: 'Upload BOM file',
          status,
          payload: {
            ...result,
            message: reason,
          },
          baseUrl,
        }));
      }
    } catch (error) {
      console.error('Upload error:', error);
      onApiError?.(classifyApiFailure({
        operation: 'Upload BOM file',
        error,
      }));
    } finally {
      setUploading(false);
    }
  }, [applySaveState, fetchApiWithFallback, maxUploadBytes, onApiError, onHydrateTable, onResetDependentView, resetSaveState]);

  const handleFileUpload = useCallback((event) => {
    processFile(event.target.files[0]);
    event.target.value = '';
  }, [processFile]);

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
        onApiError?.(classifyApiFailure({
          operation: 'Save BOM + metadata',
          status,
          payload: {
            ...(payload || {}),
            message: reason,
          },
          baseUrl,
        }));
      }
    } catch (error) {
      console.error('Save both error:', error);
      onApiError?.(classifyApiFailure({
        operation: 'Save BOM + metadata',
        error,
      }));
    } finally {
      setSavingAction('');
    }
  }, [applySaveState, fetchApiWithFallback, fileMeta, onApiError, saveRecordId, uploadedBOMFile]);

  const downloadBOMFile = useCallback((recordId) => {
    try {
      const base = getPrimaryApiBaseUrl();
      window.open(`${base}/api/save/file/${recordId}/download`, '_blank');
    } catch (err) {
      console.error('Download err:', err);
      onApiError?.(classifyApiFailure({
        operation: 'Download BOM file',
        error: err,
      }));
    }
  }, [getPrimaryApiBaseUrl, onApiError]);

  const saveStatusLabel = useMemo(() => {
    if (saveState.file_saved && saveState.metadata_saved) {
      return '✔ Saved to Database';
    }
    if (saveState.file_saved || saveState.metadata_saved) {
      return 'Partial Save (Click Save to SQL)';
    }
    return '▶ Unsaved (Preview Only)';
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

  return {
    fileMeta,
    setFileMeta,
    saveRecordId,
    saveState,
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
  };
};
