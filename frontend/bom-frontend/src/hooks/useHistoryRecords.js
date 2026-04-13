import { useCallback, useState } from 'react';

export const useHistoryRecords = ({ fetchApiWithFallback }) => {
  const [showHistory, setShowHistory] = useState(false);
  const [historyRecords, setHistoryRecords] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    setShowHistory(true);
    try {
      const { ok, payload } = await fetchApiWithFallback('/api/save/list?limit=50');
      if (ok && payload && payload.status === 'success') {
        setHistoryRecords(payload.records || []);
      }
    } catch (err) {
      console.error('List history err:', err);
    } finally {
      setLoadingHistory(false);
    }
  }, [fetchApiWithFallback]);

  const deleteHistoryRecord = useCallback(async (recordId) => {
    if (!window.confirm('Are you sure you want to permanently delete this BOM record?')) {
      return;
    }

    try {
      setLoadingHistory(true);
      const { ok, payload } = await fetchApiWithFallback(`/api/save/record/${recordId}`, {
        method: 'DELETE',
      });
      if (ok && payload && payload.status === 'success') {
        setHistoryRecords(prev => prev.filter(r => r.record_id !== recordId));
      } else {
        alert('Failed to delete the record.');
      }
    } catch (err) {
      console.error('Delete history err:', err);
      alert('Could not connect to the server to delete the record.');
    } finally {
      setLoadingHistory(false);
    }
  }, [fetchApiWithFallback]);

  return {
    showHistory,
    setShowHistory,
    historyRecords,
    loadingHistory,
    loadHistory,
    deleteHistoryRecord,
  };
};
