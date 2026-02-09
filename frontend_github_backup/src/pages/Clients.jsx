import React, { useEffect, useMemo, useState } from 'react'
import Header from '../components/dashboard/Header'
import API from '../utils/api'
import '../components/dashboard/dashboard.css'
import { useI18n } from '../i18n'
import { isDemoMode, setDemoMode, demoBadgeStyle } from '../utils/demo'
import { demoAgendamentos, demoClientes, demoConfig } from '../utils/demoData'

function monthKey(d = new Date()) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

function toISODateTimeSafe(v) {
  if (!v) return null
  try {
    const dt = new Date(v)
    if (Number.isNaN(dt.getTime())) return null
    return dt
  } catch (_) {
    return null
  }
}

function inMonth(dateObj, ym) {
  if (!dateObj) return false
  const y = dateObj.getFullYear()
  const m = String(dateObj.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}` === ym
}

function normalizeSuccessData(resp) {
  if (resp && typeof resp === 'object' && 'data' in resp) return resp.data
  return resp
}

export default function Clients() {
  const { t } = useI18n()
  const demo = isDemoMode()
  const [selectedMonth, setSelectedMonth] = useState(() => monthKey())
  const [loading, setLoading] = useState(true)
  const [errorKey, setErrorKey] = useState(null)

  const [clientes, setClientes] = useState([])
  const [agendamentos, setAgendamentos] = useState([])
  const [config, setConfig] = useState(null)

  useEffect(() => {
    let mounted = true

    if (demo) {
      setErrorKey(null)
      setConfig(demoConfig())
      setClientes(demoClientes())
      setAgendamentos(demoAgendamentos())
      setLoading(false)
      return () => { mounted = false }
    }

    async function loadAll() {
      setLoading(true)
      setErrorKey(null)
      try {
        const [cfgRaw, clientesRaw, agRaw] = await Promise.all([
          API.get('/config').catch(() => null),
          API.get('/dashboard/clientes'),
          API.get('/dashboard/agendamentos'),
        ])

        if (!mounted) return

        setConfig(cfgRaw)
        setClientes(Array.isArray(normalizeSuccessData(clientesRaw)) ? normalizeSuccessData(clientesRaw) : [])
        setAgendamentos(Array.isArray(normalizeSuccessData(agRaw)) ? normalizeSuccessData(agRaw) : [])
      } catch (e) {
        if (!mounted) return
        setErrorKey('err_clients_load')
        setClientes([])
        setAgendamentos([])
      } finally {
        if (mounted) setLoading(false)
      }
    }

    loadAll()
    return () => {
      mounted = false
    }
  }, [])

  const maps = useMemo(() => {
    const clienteById = new Map()
    for (const c of clientes || []) {
      if (c && c.id != null) clienteById.set(String(c.id), c)
    }

    const profNameById = new Map()
    for (const p of (config && config.professionals) ? config.professionals : []) {
      if (p && p.id != null) profNameById.set(String(p.id), p.name)
    }

    return { clienteById, profNameById }
  }, [clientes, config])

  const monthAgs = useMemo(() => {
    const list = []
    for (const a of agendamentos || []) {
      const dt = toISODateTimeSafe(a.data_hora)
      if (inMonth(dt, selectedMonth)) list.push(a)
    }
    // stable ordering
    list.sort((a, b) => String(a.data_hora || '').localeCompare(String(b.data_hora || '')))
    return list
  }, [agendamentos, selectedMonth])

  const kpis = useMemo(() => {
    const uniqueClients = new Set()
    const byClient = new Map()
    const byProf = new Map()
    const byService = new Map()
    const byStatus = new Map()

    for (const a of monthAgs) {
      const clienteId = a.cliente_id != null ? String(a.cliente_id) : null
      if (clienteId) uniqueClients.add(clienteId)

      if (clienteId) byClient.set(clienteId, (byClient.get(clienteId) || 0) + 1)

      const profId = a.funcionario_id != null ? String(a.funcionario_id) : null
      if (profId) byProf.set(profId, (byProf.get(profId) || 0) + 1)

      const svc = (a.descricao || '').trim() || '(sem serviço)'
      byService.set(svc, (byService.get(svc) || 0) + 1)

      const st = (a.status || 'pendente').toLowerCase()
      byStatus.set(st, (byStatus.get(st) || 0) + 1)
    }

    const top = (m, limit = 6) => Array.from(m.entries()).sort((x, y) => y[1] - x[1]).slice(0, limit)

    const topClients = top(byClient, 8).map(([clienteId, count]) => {
      const c = maps.clienteById.get(clienteId)
      return {
        id: clienteId,
        nome: c?.nome || `Cliente #${clienteId}`,
        telefone: c?.telefone || '',
        count,
      }
    })

    const topProfessionals = top(byProf, 8).map(([profId, count]) => ({
      id: profId,
      nome: maps.profNameById.get(profId) || `Profissional #${profId}`,
      count,
    }))

    const topServices = top(byService, 8).map(([name, count]) => ({ name, count }))

    return {
      totalAppointments: monthAgs.length,
      uniqueClients: uniqueClients.size,
      topClients,
      topProfessionals,
      topServices,
      byStatus: Array.from(byStatus.entries()).sort((a, b) => b[1] - a[1]),
    }
  }, [monthAgs, maps])

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0 }}>{t('clients_title')}</h3>
                {demo ? (
                  <span style={demoBadgeStyle()}>
                    DEMO
                    <button type="button" onClick={() => setDemoMode(false)} style={{ border: '0', background: 'transparent', color: 'inherit', fontWeight: 900, cursor: 'pointer' }}>
                      sair
                    </button>
                  </span>
                ) : (
                  <button type="button" className="action-btn" style={{ padding: '6px 10px' }} onClick={() => setDemoMode(true)}>
                    Preview demo
                  </button>
                )}
              </div>
              <div style={{ color: '#6b7280', fontSize: 13, marginTop: 4 }}>{t('clients_sub')}</div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <label style={{ fontSize: 13, color: '#374151' }}>{t('month_label')}</label>
              <input
                data-e2e="clients-month"
                type="month"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
            </div>
          </div>

          {errorKey && <div style={{ color: 'crimson', marginTop: 10 }}>{t(errorKey)}</div>}
          {loading ? (
            <div style={{ padding: 18, color: '#6b7280' }}>{t('loading')}</div>
          ) : (
            <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
              <div className="card" style={{ background: '#fff', borderRadius: 12, padding: 14, boxShadow: '0 10px 30px rgba(15,23,42,0.04)' }}>
                <div style={{ fontSize: 13, color: '#6b7280' }}>{t('kpi_appts_month')}</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#0f1724', marginTop: 6 }}>{kpis.totalAppointments}</div>
              </div>
              <div className="card" style={{ background: '#fff', borderRadius: 12, padding: 14, boxShadow: '0 10px 30px rgba(15,23,42,0.04)' }}>
                <div style={{ fontSize: 13, color: '#6b7280' }}>{t('kpi_unique_clients')}</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#0f1724', marginTop: 6 }}>{kpis.uniqueClients}</div>
              </div>
              <div className="card" style={{ background: '#fff', borderRadius: 12, padding: 14, boxShadow: '0 10px 30px rgba(15,23,42,0.04)' }}>
                <div style={{ fontSize: 13, color: '#6b7280' }}>{t('kpi_status_top')}</div>
                <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {kpis.byStatus.slice(0, 4).map(([st, n]) => (
                    <span key={st} className="filter-pill" style={{ background: '#f8fafc' }}>{st}: <b>{n}</b></span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {!loading && !error && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
            <div className="agenda-card">
              <div className="agenda-header" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Top clientes</h3>
              </div>
              <div className="agenda-table">
                <table>
                  <thead>
                    <tr>
                      <th>Cliente</th>
                      <th>Telefone</th>
                      <th style={{ textAlign: 'right' }}>Agend.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kpis.topClients.length === 0 ? (
                      <tr><td colSpan={3} style={{ color: '#6b7280', padding: 14 }}>Sem dados no mês.</td></tr>
                    ) : kpis.topClients.map((c) => (
                      <tr key={c.id}>
                        <td>{c.nome}</td>
                        <td>{c.telefone}</td>
                        <td style={{ textAlign: 'right', fontWeight: 700 }}>{c.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="agenda-card">
              <div className="agenda-header" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Por profissional</h3>
              </div>
              <div className="agenda-table">
                <table>
                  <thead>
                    <tr>
                      <th>Profissional</th>
                      <th style={{ textAlign: 'right' }}>Agend.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kpis.topProfessionals.length === 0 ? (
                      <tr><td colSpan={2} style={{ color: '#6b7280', padding: 14 }}>Sem dados no mês.</td></tr>
                    ) : kpis.topProfessionals.map((p) => (
                      <tr key={p.id}>
                        <td>{p.nome}</td>
                        <td style={{ textAlign: 'right', fontWeight: 700 }}>{p.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="agenda-card">
              <div className="agenda-header" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Por serviço</h3>
              </div>
              <div className="agenda-table">
                <table>
                  <thead>
                    <tr>
                      <th>Serviço</th>
                      <th style={{ textAlign: 'right' }}>Agend.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kpis.topServices.length === 0 ? (
                      <tr><td colSpan={2} style={{ color: '#6b7280', padding: 14 }}>Sem dados no mês.</td></tr>
                    ) : kpis.topServices.map((s) => (
                      <tr key={s.name}>
                        <td>{s.name}</td>
                        <td style={{ textAlign: 'right', fontWeight: 700 }}>{s.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
