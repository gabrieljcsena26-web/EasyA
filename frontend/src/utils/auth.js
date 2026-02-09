export function getStoredToken() {
  try {
    return (
      (typeof window !== 'undefined' && window.__DEV_TOKEN__) ||
      localStorage.getItem('token') ||
      localStorage.getItem('DEV_JWT_TOKEN') ||
      localStorage.getItem('ea_dev_token') ||
      ''
    );
  } catch (_) {
    return '';
  }
}

export function setStoredToken(token) {
  const tok = String(token || '').trim();
  if (!tok) return;
  try {
    localStorage.setItem('token', tok);
    localStorage.setItem('DEV_JWT_TOKEN', tok);
    localStorage.setItem('ea_dev_token', tok);
  } catch (_) {}
  try {
    window.__DEV_TOKEN__ = tok;
  } catch (_) {}
}

export function clearStoredToken() {
  try {
    localStorage.removeItem('token');
    localStorage.removeItem('DEV_JWT_TOKEN');
    localStorage.removeItem('ea_dev_token');
  } catch (_) {}
  try {
    window.__DEV_TOKEN__ = undefined;
  } catch (_) {}
}

export function isAuthenticated() {
  return !!getStoredToken();
}
