const MOCK_APPOINTMENTS = [
  { id:101, date:'2026-01-01', time:'09:00', client:'Carla Mendes', phone:'+34 6xx xxx 111', service:'Corte feminino', prof:'ana', status:'Confirmado', channel:'WhatsApp (bot)' },
  { id:102, date:'2026-01-01', time:'10:00', client:'Fernanda Costa', phone:'+34 6xx xxx 112', service:'Escova', prof:'julia', status:'Confirmado', channel:'Landing' },
  { id:103, date:'2026-01-01', time:'11:00', client:'Rafaela Dias', phone:'+34 6xx xxx 113', service:'Manicure', prof:'julia', status:'Aguard. confirmação', channel:'Instagram' },
  { id:104, date:'2026-01-09', time:'09:00', client:'Maria Oliveira', phone:'+34 6xx xxx 601', service:'Corte feminino', prof:'ana', status:'Confirmado', channel:'WhatsApp (bot)' },
  { id:105, date:'2026-01-09', time:'10:30', client:'João Silva', phone:'+34 6xx xxx 602', service:'Manicure', prof:'julia', status:'Aguard. confirmação', channel:'Landing' }
];

const DEFAULT_CONFIG = {
  businessName: 'Ana Beleza',
  timezone: '(GMT-3) Brasília',
  slotInterval: 5,
  openingHours: {
    monday: { open: '09:00', close: '18:00', active: true },
    tuesday: { open: '09:00', close: '18:00', active: true }
  }
};

function isDemoEnabled() {
  if (typeof window === 'undefined') return false
  try {
    const params = new URLSearchParams(window.location.search || '')
    const v = String(params.get('demo') || '').toLowerCase()
    if (v === '1' || v === 'true' || v === 'yes') return true
  } catch (_) {}
  try {
    return localStorage.getItem('ea_demo') === '1'
  } catch (_) {
    return false
  }
}

function allowOfflineFallback() {
  // IMPORTANT: never silently serve mock data in production.
  // Only allow fallbacks in dev or when the user explicitly enables demo mode.
  if (isDemoEnabled()) return true
  try {
    // Vite
    if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.DEV) return true
  } catch (_) {}
  try {
    const host = String(window.location.hostname || '').toLowerCase()
    if (host === 'localhost' || host === '127.0.0.1') return true
  } catch (_) {}
  return false
}

const API = {
  async get(path){
    try{
      const token = (typeof window !== 'undefined' && window.__DEV_TOKEN__) || (() => { try { return localStorage.getItem('DEV_JWT_TOKEN') || localStorage.getItem('ea_dev_token') || localStorage.getItem('token'); } catch(_){ return null } })();
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const base = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_URL) ? process.env.REACT_APP_API_URL : (typeof window !== 'undefined' ? (window.__API_URL__ || 'http://127.0.0.1:8000') : '');
      const url = path.startsWith('http') ? path : `${base}${path}`;
      const res = await fetch(url, { credentials: 'include', headers });
      if(!res.ok) throw new Error('Network error');
      return await res.json();
    }catch(e){
      if (!allowOfflineFallback()) throw e;
      // offline deterministic fallbacks for key endpoints
      if(path && path.includes('/appointments')){
        return MOCK_APPOINTMENTS;
      }
      if(path && (path.includes('/config') || path.includes('/admin/config'))){
        try{
          const raw = localStorage.getItem('ea_admin_config');
          if(raw) return JSON.parse(raw);
        }catch(_){ }
        return DEFAULT_CONFIG;
      }
      if(path && path.includes('/admin/setup')){
        try{
          const raw = localStorage.getItem('ea_setup_profile');
          if(raw) return JSON.parse(raw);
        }catch(_){ }
        return { ok: true, exists: false, payload: null };
      }
      throw e;
    }
  },
  async put(path, body){
    try{
      const token = (typeof window !== 'undefined' && window.__DEV_TOKEN__) || (() => { try { return localStorage.getItem('DEV_JWT_TOKEN') || localStorage.getItem('ea_dev_token') || localStorage.getItem('token'); } catch(_){ return null } })();
      const headers = Object.assign({'Content-Type':'application/json'}, token ? { Authorization: `Bearer ${token}` } : {});
      const base = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_URL) ? process.env.REACT_APP_API_URL : (typeof window !== 'undefined' ? (window.__API_URL__ || 'http://127.0.0.1:8000') : '');
      const url = path.startsWith('http') ? path : `${base}${path}`;
      const res = await fetch(url, { method:'PUT', headers, body: JSON.stringify(body), credentials:'include' });
      if(!res.ok) throw new Error('Network error');
      return await res.json();
    }catch(e){
      if (!allowOfflineFallback()) throw e;
      // local fallback for admin config persistence
      if(path && path.includes('/admin/config')){
        try{
          localStorage.setItem('ea_admin_config', JSON.stringify(body));
        }catch(_){ }
        return body;
      }
      if(path && path.includes('/admin/setup')){
        try{
          localStorage.setItem('ea_setup_profile', JSON.stringify(body));
        }catch(_){ }
        return body;
      }
      throw e;
    }
  },
  async post(path, body){
    try{
      const token = (typeof window !== 'undefined' && window.__DEV_TOKEN__) || (() => { try { return localStorage.getItem('DEV_JWT_TOKEN') || localStorage.getItem('ea_dev_token') || localStorage.getItem('token'); } catch(_){ return null } })();
      const headers = Object.assign({'Content-Type':'application/json'}, token ? { Authorization: `Bearer ${token}` } : {});
      const base = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_URL) ? process.env.REACT_APP_API_URL : (typeof window !== 'undefined' ? (window.__API_URL__ || 'http://127.0.0.1:8000') : '');
      const url = path.startsWith('http') ? path : `${base}${path}`;
      const res = await fetch(url, { method:'POST', headers, body: JSON.stringify(body), credentials:'include' });
      if(!res.ok) throw new Error('Network error');
      return await res.json();
    }catch(e){
      if (!allowOfflineFallback()) throw e;
      // offline fallback: if posting appointments, queue in localStorage and attach slug if available
      if(path && path.includes('/appointments')){
        try{
          const pending = JSON.parse(localStorage.getItem('ea_pending_actions')||'[]');
          // attach slug from saved admin config if present
          try{
            const raw = localStorage.getItem('ea_admin_config');
            if(raw){
              const cfg = JSON.parse(raw);
              if(cfg && cfg.business && cfg.business.slug){
                body = Object.assign({}, body, { slug: cfg.business.slug });
              }
            }
          }catch(_){ }
          pending.push({ type:'post', path, payload: body, ts: Date.now() });
          localStorage.setItem('ea_pending_actions', JSON.stringify(pending));
        }catch(_){ }
        return { ok: false, queued: true };
      }
      throw e;
    }
    },
  async delete(path){
    try{
      const token = (typeof window !== 'undefined' && window.__DEV_TOKEN__) || (() => { try { return localStorage.getItem('DEV_JWT_TOKEN') || localStorage.getItem('ea_dev_token') || localStorage.getItem('token'); } catch(_){ return null } })();
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const base = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_URL) ? process.env.REACT_APP_API_URL : (typeof window !== 'undefined' ? (window.__API_URL__ || 'http://127.0.0.1:8000') : '');
      const url = path.startsWith('http') ? path : `${base}${path}`;
      const res = await fetch(url, { method: 'DELETE', headers, credentials: 'include' });
      if(!res.ok) throw new Error('Network error');
      // some deletes return empty body
      try{ return await res.json(); }catch(_){ return { ok: true }; }
    }catch(e){
      throw e;
    }
  }
};

export default API;
