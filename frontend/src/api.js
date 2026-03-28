const hostname = window.location.hostname || 'localhost';
const isLocalDev =
  hostname === 'localhost' ||
  hostname === '127.0.0.1' ||
  hostname === '0.0.0.0';

export const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || (isLocalDev ? 'http://localhost:5000' : '');

export function buildApiUrl(path) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  if (!API_BASE_URL) {
    return path;
  }

  if (!path.startsWith('/')) {
    return `${API_BASE_URL}/${path}`;
  }

  return `${API_BASE_URL}${path}`;
}

export async function apiFetch(path, options = {}) {
  const { headers, credentials, ...rest } = options;
  return fetch(buildApiUrl(path), {
    credentials: credentials || 'include',
    headers: headers || {},
    ...rest,
  });
}
