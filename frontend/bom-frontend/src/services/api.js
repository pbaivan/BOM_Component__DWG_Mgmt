const normalizeBaseUrl = (url) => String(url || '').trim().replace(/\/+$/, '');

export const API_BASE_CANDIDATES = Array.from(new Set([
  normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
  'http://127.0.0.1:8000',
  'http://localhost:8000',
].filter(Boolean)));

export const getPrimaryApiBaseUrl = () => API_BASE_CANDIDATES[0] || 'http://localhost:8000';

const parseResponseBody = async (response) => {
  const text = await response.text();
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
};

export const fetchApiWithFallback = async (path, options = {}) => {
  let lastNetworkError = null;

  for (const baseUrl of API_BASE_CANDIDATES) {
    try {
      const response = await fetch(`${baseUrl}${path}`, options);
      const payload = await parseResponseBody(response);

      return {
        ok: response.ok,
        status: response.status,
        payload,
        baseUrl,
      };
    } catch (error) {
      lastNetworkError = error;
    }
  }

  const error = new Error('Unable to reach backend API.');
  error.cause = lastNetworkError;
  throw error;
};
