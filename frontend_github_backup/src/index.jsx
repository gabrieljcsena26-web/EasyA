import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import reportWebVitals from './reportWebVitals';

// Vite compatibility: prefer `import.meta.env` but fall back to `process.env`.
let _env = {};
try {
  // in ESM this will work; in other contexts it may throw and we'll fallback
  // eslint-disable-next-line no-undef
  _env = import.meta && import.meta.env ? import.meta.env : {};
} catch (e) {
  _env = (typeof process !== 'undefined' && process.env) ? process.env : {};
}

// Expose DEV token and API URL (Vite uses VITE_ prefix). Old code reads `process.env.REACT_APP_*`,
// so we populate window.__API_URL__ and provide a fallback for dev token.
try{
  // API base URL (recommended for production when frontend and API are on different subdomains)
  // Example: VITE_API_URL=https://api.easy-agenda.com
  const apiUrl = (_env && (_env.VITE_API_URL || _env.REACT_APP_API_URL)) || ((typeof process !== 'undefined' && process.env) ? (process.env.REACT_APP_API_URL || '') : '')
  if (apiUrl && !(typeof window !== 'undefined' && window.__API_URL__)) {
    try {
      const raw = String(apiUrl).trim()
      // Allow relative bases like "/api" for local dev proxy.
      if (raw.startsWith('/')) {
        const normalized = raw.replace(/\/$/, '')
        if (normalized) window.__API_URL__ = normalized
      } else {
        const normalized = String(new URL(raw)).replace(/\/$/, '')
        if (normalized) window.__API_URL__ = normalized
      }
    } catch (_) {}
  }

  const devToken = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_DEV_TOKEN) ? process.env.REACT_APP_DEV_TOKEN : (_env.VITE_DEV_TOKEN || _env.REACT_APP_DEV_TOKEN || '');
  const hostname = (typeof window !== 'undefined' && window.location && window.location.hostname) ? String(window.location.hostname) : '';
  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
  // Dev-token injection can be dangerous when the app is exposed via a public URL (tunnels).
  // Default behavior: only inject automatically on localhost. For other hosts, require an explicit flag.
  const injectFlag = (
    (_env && (_env.VITE_INJECT_DEV_TOKEN === 'true' || _env.REACT_APP_INJECT_DEV_TOKEN === 'true')) ||
    (typeof process !== 'undefined' && process.env && process.env.REACT_APP_INJECT_DEV_TOKEN === 'true')
  );
  const allowDevTokenInjection = isLocalhost || injectFlag;
  // Detect automation (Playwright/WebDriver) and avoid injecting dev tokens during E2E runs.
  const isAutomation = (typeof navigator !== 'undefined' && navigator.webdriver) || ((_env && (_env.VITE_E2E === 'true' || _env.REACT_APP_E2E === 'true')) || (typeof window !== 'undefined' && window.__E2E__ === true));
  if (devToken && allowDevTokenInjection && !isAutomation) {
    try { localStorage.setItem('DEV_JWT_TOKEN', devToken); } catch (_) { }
    window.__DEV_TOKEN__ = devToken;
  } else if (devToken && !allowDevTokenInjection) {
    // eslint-disable-next-line no-console
    console.info('Dev token present but injection disabled for non-localhost host. Set VITE_INJECT_DEV_TOKEN=true to override.');
  } else if (devToken && isAutomation) {
    // eslint-disable-next-line no-console
    console.info('Skipping dev token injection during E2E/automation run');
  } else {
    // If a generic 'token' is present (set by E2E tests), expose it as __DEV_TOKEN__ so
    // the app will pick it up during initial load without waiting for injection.
    try {
      const alt = (typeof window !== 'undefined') ? (localStorage.getItem('token') || localStorage.getItem('ea_dev_token')) : null;
      if (alt && !isAutomation) {
        window.__DEV_TOKEN__ = alt;
      }
    } catch (_){ }
  }
}catch(_){ }

// Development HMR probe: prints when this module is reloaded
try{
  // show timestamp to detect HMR/live updates
  // eslint-disable-next-line no-console
  console.info('DEV HMR probe:', new Date().toISOString());
}catch(_){ }

const root = ReactDOM.createRoot(document.getElementById('root'));
// Global safety: log and prevent uncaught errors from aborting app init
window.addEventListener('error', ev => {
  try {
    // eslint-disable-next-line no-console
    console.error('Global error captured:', ev && ev.message, (ev && ev.error && ev.error.stack) || ev);
    // Prevent default to avoid propagation that some extensions rely on
    if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
  } catch (e) {
    // ignore
  }
});

window.addEventListener('unhandledrejection', ev => {
  try {
    // eslint-disable-next-line no-console
    console.error('Unhandled Rejection captured:', ev && ev.reason);
    if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
  } catch (e) {
    // ignore
  }
});

// Guard the initial render so an unexpected exception cannot stop the whole bundle
try {
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
} catch (err) {
  // If React rendering fails, show a minimal fallback UI and log the error.
  // eslint-disable-next-line no-console
  console.error('Error during React root.render():', (err && err.stack) || err);
  try {
    root.render(
      React.createElement('div', { style: { padding: 20, fontFamily: 'sans-serif' } }, ['Application failed to initialize. See console for details.'])
    );
  } catch (ignore) {
    // final fallback: insert plain DOM node
    try {
      const el = document.getElementById('root');
      if (el) el.innerHTML = '<div style="padding:20px;font-family:sans-serif">Application failed to initialize. Check console.</div>';
    } catch (e) { /* noop */ }
  }
}

reportWebVitals();
