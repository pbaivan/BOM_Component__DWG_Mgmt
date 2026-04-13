import { useCallback, useState } from 'react';

import { classifyApiFailure } from '../utils/apiError';

export const useHistoryRecords = ({ fetchApiWithFallback, onApiError }) => {
  const [showHistory, setShowHistory] = useState(false);
  const [historyRecords, setHistoryRecords] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    setShowHistory(true);
    try {
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback('/api/save/list?limit=50');
      if (ok && payload && payload.status === 'success') {
        setHistoryRecords(payload.records || []);
      } else {
        onApiError?.(classifyApiFailure({
          operation: 'Load history records',
          status,
          payload,
          baseUrl,
        }));
      }
    } catch (err) {
      console.error('List history err:', err);
      onApiError?.(classifyApiFailure({
        operation: 'Load history records',
        error: err,
      }));
    } finally {
      setLoadingHistory(false);
    }
  }, [fetchApiWithFallback, onApiError]);

  const deleteHistoryRecord = useCallback(async (recordId) => {
    if (!window.confirm('Are you sure you want to permanently delete this BOM record?')) {
      return;
    }

    try {
      setLoadingHistory(true);
      const { ok, payload, status, baseUrl } = await fetchApiWithFallback(`/api/save/record/${recordId}`, {
        method: 'DELETE',
      });
      if (ok && payload && payload.status === 'success') {
        setHistoryRecords(prev => prev.filter(r => r.record_id !== recordId));
      } else {
        onApiError?.(classifyApiFailure({
          operation: 'Delete history record',
          status,
          payload,
          baseUrl,
        }));
      }
    } catch (err) {
      console.error('Delete history err:', err);
      onApiError?.(classifyApiFailure({
        operation: 'Delete history record',
        error: err,
      }));
    } finally {
      setLoadingHistory(false);
    }
  }, [fetchApiWithFallback, onApiError]);

  return {
    showHistory,
    setShowHistory,
    historyRecords,
    loadingHistory,
    loadHistory,
    deleteHistoryRecord,
  };
};
