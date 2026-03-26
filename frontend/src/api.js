const hostname = window.location.hostname || 'localhost';

export const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || `http://${hostname}:5000`;

export function buildApiUrl(path) {
  if (!path.startsWith('/')) {
    return `${API_BASE_URL}/${path}`;
  }

  return `${API_BASE_URL}${path}`;
}
