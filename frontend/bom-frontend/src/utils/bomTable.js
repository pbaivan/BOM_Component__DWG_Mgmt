export const normalizeKey = (value) => String(value ?? '').trim();

export const getCaselessValue = (obj, targetKey) => {
  if (!obj || typeof obj !== 'object') return undefined;
  const upperTarget = targetKey.toUpperCase();
  for (const k in obj) {
    if (k.toUpperCase() === upperTarget) {
      return obj[k];
    }
  }
  return undefined;
};
