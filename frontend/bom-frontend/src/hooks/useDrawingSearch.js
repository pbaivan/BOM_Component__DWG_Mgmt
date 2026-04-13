import { useCallback, useMemo, useRef, useState } from 'react';

import { classifyApiFailure } from '../utils/apiError';
import { getCaselessValue, normalizeKey } from '../utils/bomTable';

export const useDrawingSearch = ({ masterData, fetchApiWithFallback, getPrimaryApiBaseUrl, onApiError }) => {
  const [detailData, setDetailData] = useState([]);
  const [selectedParent, setSelectedParent] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [drawings, setDrawings] = useState([]);
  const [missingComponents, setMissingComponents] = useState([]);
  const [loadingDrawings, setLoadingDrawings] = useState(false);
  const [batchDownloading, setBatchDownloading] = useState(false);
  const [directoryScopes, setDirectoryScopes] = useState([]);
  const [componentTargets, setComponentTargets] = useState([]);
  const drawingRequestIdRef = useRef(0);

  const rowsByParent = useMemo(() => {
    const grouped = new Map();

    for (let i = 0; i < masterData.length; i += 1) {
      const row = masterData[i];
      const parentVal = getCaselessValue(row, 'PARENT');
      const parentModel = normalizeKey(parentVal);
      if (!parentModel) continue;

      if (!grouped.has(parentModel)) {
        grouped.set(parentModel, []);
      }
      grouped.get(parentModel).push(row);
    }

    return grouped;
  }, [masterData]);

  const resetDrawingView = useCallback(() => {
    setDetailData([]);
    setSelectedParent(null);
    setSelectedDetail(null);
    setDrawings([]);
    setDirectoryScopes([]);
    setComponentTargets([]);
    setMissingComponents([]);
    setLoadingDrawings(false);
    drawingRequestIdRef.current += 1;
  }, []);

  const onMasterRowClicked = useCallback(async (row) => {
    const requestId = ++drawingRequestIdRef.current;
    setSelectedParent(row);
    setSelectedDetail(null);
    setDrawings([]);
    setDirectoryScopes([]);
    setComponentTargets([]);
    setMissingComponents([]);
    setLoadingDrawings(true);

    const parentVal = getCaselessValue(row, 'PARENT');
    const selectedParentModel = normalizeKey(parentVal);
    const children = selectedParentModel ? (rowsByParent.get(selectedParentModel) || []) : [];

    setDetailData(children);

    if (!selectedParentModel || children.length === 0) {
      if (requestId === drawingRequestIdRef.current) {
        setLoadingDrawings(false);
      }
      return;
    }

    const uniqueTargets = [];
    const seenTargets = new Set();
    children.forEach(item => {
      const compVal = getCaselessValue(item, 'COMPONENT') || getCaselessValue(item, 'TOP_ASSY');
      const component = normalizeKey(compVal);
      if (!component) return;

      const catVal = getCaselessValue(item, 'Category');
      const category = normalizeKey(catVal) || 'Unknown Category';
      const key = `${category}::${component}`;
      if (seenTargets.has(key)) return;
      seenTargets.add(key);
      uniqueTargets.push({ category, component });
    });

    if (uniqueTargets.length === 0) {
      if (requestId === drawingRequestIdRef.current) {
        setLoadingDrawings(false);
      }
      return;
    }

    try {
      let failedTargets = 0;
      let failureSnapshot = null;
      const responseList = await Promise.all(uniqueTargets.map(async ({ category, component }) => {
        const { ok, payload, status, baseUrl } = await fetchApiWithFallback(`/api/search?category=${encodeURIComponent(category)}&component=${encodeURIComponent(component)}`);
        const data = payload || {};

        if (!ok || data.status !== 'success') {
          failedTargets += 1;
          if (!failureSnapshot) {
            failureSnapshot = {
              status,
              payload,
              baseUrl,
            };
          }
          return { drawings: [], scopes: [] };
        }

        const enriched = (data.results || []).map(file => ({
          ...file,
          id: file.id || `${component}-${file.name || 'drawing'}-${file.version || ''}`,
          sourceComponent: component,
          sourceCategory: category,
        }));

        return {
          drawings: enriched,
          scopes: data.search_scopes || [],
        };
      }));

      if (requestId !== drawingRequestIdRef.current) {
        return;
      }

      const drawingMap = new Map();
      responseList.flatMap(item => item.drawings).forEach(file => {
        const key = `${file.id}::${file.sourceComponent}`;
        if (!drawingMap.has(key)) {
          drawingMap.set(key, file);
        }
      });

      const allDrawings = Array.from(drawingMap.values());
      setDrawings(allDrawings);

      const scopeMap = new Map();
      responseList.flatMap(item => item.scopes || []).forEach(scope => {
        const site = normalizeKey(scope.site);
        const root = normalizeKey(scope.root);
        const scopeCategory = normalizeKey(scope.category);
        if (!site || !root || !scopeCategory) return;

        const key = `${site}::${root}::${scopeCategory}`;
        if (!scopeMap.has(key)) {
          scopeMap.set(key, {
            site,
            root,
            category: scopeCategory,
          });
        }
      });
      setDirectoryScopes(Array.from(scopeMap.values()));

      const uniqueComponents = Array.from(new Set(uniqueTargets.map(target => target.component)));
      setComponentTargets(uniqueComponents);

      const foundComponents = new Set(allDrawings.map(d => d.sourceComponent));
      const missing = uniqueTargets.filter(t => !foundComponents.has(t.component)).map(t => t.component);
      setMissingComponents(missing);

      if (failedTargets > 0 && failedTargets === uniqueTargets.length) {
        onApiError?.(classifyApiFailure({
          operation: 'Search drawings',
          status: failureSnapshot?.status,
          payload: failureSnapshot?.payload,
          baseUrl: failureSnapshot?.baseUrl,
        }));
      }
    } catch (error) {
      if (requestId === drawingRequestIdRef.current) {
        console.error('Fetch drawings failed:', error);
        setDrawings([]);
        setDirectoryScopes([]);
        setComponentTargets([]);
        setMissingComponents([]);
        onApiError?.(classifyApiFailure({
          operation: 'Search drawings',
          error,
        }));
      }
    } finally {
      if (requestId === drawingRequestIdRef.current) {
        setLoadingDrawings(false);
      }
    }
  }, [fetchApiWithFallback, onApiError, rowsByParent]);

  const onDetailRowClicked = useCallback((row) => {
    setSelectedDetail(row);
  }, []);

  const triggerBrowserDownload = useCallback((blob, filename) => {
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(objectUrl);
  }, []);

  const fetchDrawingBlob = useCallback(async (drawing) => {
    if (!drawing?.drive_id || !drawing?.item_id) {
      const error = new Error('Missing drawing identifiers.');
      error.code = 'INVALID_DRAWING';
      throw error;
    }

    const base = getPrimaryApiBaseUrl();
    const downloadUrl = `${base}/api/sp_file?drive_id=${encodeURIComponent(drawing.drive_id)}&item_id=${encodeURIComponent(drawing.item_id)}&filename=${encodeURIComponent(drawing.name || 'drawing')}&mode=download`;
    const response = await fetch(downloadUrl);

    if (!response.ok) {
      const bodyText = await response.text();
      let payload = {};
      try {
        payload = bodyText ? JSON.parse(bodyText) : {};
      } catch {
        payload = bodyText ? { message: bodyText } : {};
      }

      const error = new Error(`Download failed (HTTP ${response.status})`);
      error.meta = {
        status: response.status,
        payload,
        baseUrl: base,
      };
      throw error;
    }

    return {
      blob: await response.blob(),
      filename: drawing.name || 'drawing',
    };
  }, [getPrimaryApiBaseUrl]);

  const previewDrawingFile = useCallback((drawing) => {
    if (!drawing?.drive_id || !drawing?.item_id) {
      return;
    }

    const base = getPrimaryApiBaseUrl();
    const previewUrl = `${base}/api/sp_file?drive_id=${encodeURIComponent(drawing.drive_id)}&item_id=${encodeURIComponent(drawing.item_id)}&filename=${encodeURIComponent(drawing.name || 'drawing')}&mode=preview`;
    window.open(previewUrl, '_blank', 'noopener,noreferrer');
  }, [getPrimaryApiBaseUrl]);

  const downloadDrawingFile = useCallback(async (drawing) => {
    if (!drawing?.drive_id || !drawing?.item_id) {
      return;
    }

    try {
      const { blob, filename } = await fetchDrawingBlob(drawing);
      triggerBrowserDownload(blob, filename);
    } catch (error) {
      console.error('Download drawing failed:', error);
      if (error?.meta) {
        onApiError?.(classifyApiFailure({
          operation: 'Download SharePoint file',
          status: error.meta.status,
          payload: error.meta.payload,
          baseUrl: error.meta.baseUrl,
        }));
        return;
      }
      onApiError?.(classifyApiFailure({
        operation: 'Download SharePoint file',
        error,
      }));
    }
  }, [fetchDrawingBlob, onApiError, triggerBrowserDownload]);

  const downloadDrawingFilesBatch = useCallback(async (drawingList) => {
    const targets = Array.isArray(drawingList) ? drawingList.filter(Boolean) : [];
    if (targets.length === 0 || batchDownloading) {
      return;
    }

    setBatchDownloading(true);
    let failureCount = 0;
    let firstFailureMeta = null;

    try {
      for (const drawing of targets) {
        try {
          const { blob, filename } = await fetchDrawingBlob(drawing);
          triggerBrowserDownload(blob, filename);
        } catch (error) {
          failureCount += 1;
          if (!firstFailureMeta) {
            firstFailureMeta = error?.meta
              ? {
                status: error.meta.status,
                payload: error.meta.payload,
                baseUrl: error.meta.baseUrl,
              }
              : { error };
          }
        }
      }

      if (failureCount > 0) {
        const operation = `Batch download drawings (${failureCount}/${targets.length} failed)`;
        if (firstFailureMeta?.status) {
          onApiError?.(classifyApiFailure({
            operation,
            status: firstFailureMeta.status,
            payload: firstFailureMeta.payload,
            baseUrl: firstFailureMeta.baseUrl,
          }));
        } else {
          onApiError?.(classifyApiFailure({
            operation,
            error: firstFailureMeta?.error || new Error('Batch download failed.'),
          }));
        }
      }
    } finally {
      setBatchDownloading(false);
    }
  }, [batchDownloading, fetchDrawingBlob, onApiError, triggerBrowserDownload]);

  return {
    detailData,
    selectedParent,
    selectedDetail,
    drawings,
    missingComponents,
    loadingDrawings,
    batchDownloading,
    directoryScopes,
    componentTargets,
    onMasterRowClicked,
    onDetailRowClicked,
    previewDrawingFile,
    downloadDrawingFile,
    downloadDrawingFilesBatch,
    resetDrawingView,
  };
};
