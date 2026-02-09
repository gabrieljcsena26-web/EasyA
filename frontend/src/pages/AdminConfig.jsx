import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Header from '../components/dashboard/Header'
import BookingShareCard from '../components/dashboard/BookingShareCard'
import API from '../utils/api'
import '../components/dashboard/dashboard.css'

export default function AdminConfig(){
  const [loading,setLoading] = useState(false);
  const [raw,setRaw] = useState(() => {
    try{
      const saved = localStorage.getItem('ea_admin_config');
      if(saved) return JSON.stringify(JSON.parse(saved), null, 2);
    }catch(_){ }
    return '';
  });
  const [error,setError] = useState(null);
  const [token,setToken] = useState(() => {
    try{ return localStorage.getItem('ea_dev_token') || ''; }catch(_){ return ''; }
  });

  const parsed = useMemo(() => {
    try{ return raw ? JSON.parse(raw) : null }catch(_){ return null }
  }, [raw])

  const business = parsed && parsed.business && typeof parsed.business === 'object' ? parsed.business : {}

  const browserTz = useMemo(() => {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Madrid' } catch (_) { return 'Europe/Madrid' }
  }, [])

  function patchBusiness(nextPatch){
    setRaw((prev) => {
      let obj
      try{ obj = prev ? JSON.parse(prev) : {} }catch(_){ obj = {} }
      obj.business = { ...(obj.business || {}), ...(nextPatch || {}) }
      if(!Array.isArray(obj.services)) obj.services = obj.services || []
      if(!Array.isArray(obj.professionals)) obj.professionals = obj.professionals || []
      return JSON.stringify(obj, null, 2)
    })
  }

  useEffect(()=>{ fetchCfg(); },[]);

  async function fetchCfg(){
    setLoading(true); setError(null);
    try{
      const data = await API.get('/admin/config');
      setRaw(JSON.stringify(data,null,2));
    }catch(e){
      const saved = localStorage.getItem('ea_admin_config');
      if(saved){ setRaw(JSON.stringify(JSON.parse(saved),null,2)); setError('Loaded from localStorage (offline)'); }
      else setRaw(JSON.stringify({ business:{}, services:[], professionals:[] },null,2));
    }finally{ setLoading(false); }
  }

  async function handleSave(){
    setError(null);
    let parsed;
    try{ parsed = JSON.parse(raw); }catch(e){ setError('Invalid JSON: '+e.message); return; }
    setLoading(true);
    try{
      const updated = await API.put('/admin/config', parsed);
      setRaw(JSON.stringify(updated,null,2));
      localStorage.removeItem('ea_admin_config');
      alert('Saved to backend');
    }catch(e){
      localStorage.setItem('ea_admin_config', JSON.stringify(parsed));
      setError('Failed to save to backend — saved locally');
    }finally{ setLoading(false); }
  }

  function handleTokenSave(){
    try{ localStorage.setItem('ea_dev_token', token || ''); alert('Token saved to localStorage (ea_dev_token)'); }catch(e){ alert('Failed to save token'); }
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0 }} data-e2e="admin-config-title">Config avançada</h3>
                <Link to="/config" style={{ fontSize: 13, fontWeight: 900, color: '#1e3a8a', textDecoration: 'none' }}>
                  Voltar ao setup
                </Link>
              </div>
              <div style={{ color: '#6b7280', fontSize: 13, marginTop: 4 }}>
                Ajustes rápidos do negócio. (O JSON completo fica abaixo.)
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="action-btn" data-e2e="admin-config-reload" onClick={fetchCfg} disabled={loading} style={{ padding: '6px 10px' }}>
                {loading ? 'Carregando…' : 'Recarregar'}
              </button>
              <button className="action-btn" data-e2e="admin-config-save" onClick={handleSave} disabled={loading} style={{ padding: '6px 10px' }}>
                Salvar
              </button>
            </div>
          </div>

          {error && <div style={{ color: 'crimson', marginTop: 10 }}>{error}</div>}

          <div style={{ marginTop: 12 }}>
            <BookingShareCard slug={business?.slug} businessName={business?.nome} />
          </div>

          <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
              <div style={{ fontWeight: 900, color: '#0f1724' }}>Horário padrão do estabelecimento</div>
              <div style={{ color: '#6b7280', fontSize: 12, marginTop: 6 }}>
                Usado como fallback quando não há horários por dia configurados.
              </div>

              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Início (hora)</label>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={Number.isFinite(business?.horario_inicio) ? business.horario_inicio : 9}
                    onChange={(e) => patchBusiness({ horario_inicio: Number(e.target.value) })}
                    style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Fim (hora)</label>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={Number.isFinite(business?.horario_fim) ? business.horario_fim : 18}
                    onChange={(e) => patchBusiness({ horario_fim: Number(e.target.value) })}
                    style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                  />
                </div>
              </div>

              <div style={{ marginTop: 10, padding: 12, borderRadius: 12, background: '#f8fafc', border: '1px solid rgba(15,23,42,0.08)', color: '#0f1724', fontSize: 13 }}>
                Preview: <b>{String(Number.isFinite(business?.horario_inicio) ? business.horario_inicio : 9).padStart(2,'0')}:00</b>
                {' '}–{' '}
                <b>{String(Number.isFinite(business?.horario_fim) ? business.horario_fim : 18).padStart(2,'0')}:00</b>
              </div>
            </div>

            <div className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
              <div style={{ fontWeight: 900, color: '#0f1724' }}>Idioma e timezone</div>
              <div style={{ color: '#6b7280', fontSize: 12, marginTop: 6 }}>
                Controla o idioma default do salão e o fuso horário para lembretes/agenda.
              </div>

              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Idioma padrão</label>
                  <select
                    value={business?.idioma_padrao || 'es-ES'}
                    onChange={(e) => patchBusiness({ idioma_padrao: e.target.value })}
                    style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb', background: 'white' }}
                  >
                    <option value="es-ES">Español — es-ES</option>
                    <option value="pt-PT">Português (Portugal) — pt-PT</option>
                    <option value="en-US">English (US) — en-US</option>
                    <option value="fr-FR">Français — fr-FR</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Timezone</label>
                  <input
                    value={business?.timezone || browserTz}
                    onChange={(e) => patchBusiness({ timezone: e.target.value })}
                    style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                    placeholder={browserTz}
                  />
                </div>
              </div>

              <div style={{ marginTop: 10, padding: 12, borderRadius: 12, background: '#f8fafc', border: '1px solid rgba(15,23,42,0.08)', color: '#0f1724', fontSize: 13 }}>
                Usando: <b>{business?.idioma_padrao || 'es-ES'}</b> · <b>{business?.timezone || browserTz}</b>
              </div>
            </div>

            <div className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
              <div style={{ fontWeight: 900, color: '#0f1724' }}>Dev token</div>
              <div style={{ color: '#6b7280', fontSize: 12, marginTop: 6 }}>Cole aqui para chamadas admin no browser.</div>

              <div style={{ marginTop: 12 }}>
                <input
                  data-e2e="admin-config-devtoken"
                  value={token}
                  onChange={e=>setToken(e.target.value)}
                  style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                  placeholder="eyJhbGciOi..."
                />
                <div style={{ marginTop: 10 }}>
                  <button className="action-btn" data-e2e="admin-config-save-token" onClick={handleTokenSave} style={{ padding: '6px 10px' }}>
                    Salvar token
                  </button>
                </div>
              </div>
            </div>
          </div>

          <details style={{ marginTop: 12, border: '1px solid rgba(15,23,42,0.08)', borderRadius: 12, padding: 12, background: 'linear-gradient(180deg,#ffffff,#fbfdff)' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 900, color: '#111827', fontSize: 13 }}>JSON completo (avançado)</summary>
            <div style={{ marginTop: 12 }}>
              <textarea
                data-e2e="admin-config-textarea"
                value={raw}
                onChange={e=>setRaw(e.target.value)}
                style={{ width: '100%', minHeight: 360, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace', padding: 12, borderRadius: 12, border: '1px solid #e5e7eb' }}
              />
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  className="action-btn"
                  data-e2e="admin-config-save-local"
                  onClick={()=>{
                    try{ const p=JSON.parse(raw); localStorage.setItem('ea_admin_config', JSON.stringify(p)); alert('Saved locally'); }
                    catch(e){ alert('Invalid JSON'); }
                  }}
                  style={{ padding: '6px 10px' }}
                >
                  Salvar local
                </button>
              </div>
            </div>
          </details>
        </div>
      </div>
    </div>
  )
}
