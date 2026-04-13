export const classifyApiFailure = ({ operation, status, payload, baseUrl, error }) => {
  const normalizedStatus = Number.isFinite(Number(status)) ? Number(status) : null;
  const requestId = payload?.request_id || payload?.requestId || '';
  const backendMessage = String(payload?.message || payload?.detail || '').trim();

  if (error) {
    return {
      kind: 'network',
      operation,
      status: null,
      requestId,
      baseUrl: baseUrl || '',
      title: `${operation} failed`,
      message: 'Network issue while calling backend API. Please verify backend availability and connectivity.',
    };
  }

  if (normalizedStatus === 401 || normalizedStatus === 403) {
    return {
      kind: 'auth',
      operation,
      status: normalizedStatus,
      requestId,
      baseUrl: baseUrl || '',
      title: `${operation} unauthorized`,
      message: backendMessage || 'Permission or authentication failed for this API call.',
    };
  }

  if (normalizedStatus === 404) {
    return {
      kind: 'not_found',
      operation,
      status: normalizedStatus,
      requestId,
      baseUrl: baseUrl || '',
      title: `${operation} not found`,
      message: backendMessage || 'Requested resource was not found.',
    };
  }

  if (normalizedStatus === 400 || normalizedStatus === 422) {
    return {
      kind: 'validation',
      operation,
      status: normalizedStatus,
      requestId,
      baseUrl: baseUrl || '',
      title: `${operation} validation error`,
      message: backendMessage || 'Request payload or parameters are invalid.',
    };
  }

  if (normalizedStatus && normalizedStatus >= 500) {
    return {
      kind: 'server',
      operation,
      status: normalizedStatus,
      requestId,
      baseUrl: baseUrl || '',
      title: `${operation} server error`,
      message: backendMessage || 'Backend service encountered an internal error.',
    };
  }

  return {
    kind: 'unknown',
    operation,
    status: normalizedStatus,
    requestId,
    baseUrl: baseUrl || '',
    title: `${operation} failed`,
    message: backendMessage || 'Unexpected API error occurred.',
  };
};
