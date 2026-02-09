import React, { useEffect, useMemo, useState } from 'react'
import Header from '../components/dashboard/Header'
import API from '../utils/api'
import '../components/dashboard/dashboard.css'
import { useI18n } from '../i18n'
import { useLocation } from 'react-router-dom'
import { isDemoMode, setDemoMode, demoBadgeStyle } from '../utils/demo'
import { demoAgendamentos, demoClientes, demoConfig } from '../utils/demoData'
import { Callout, KpiCard } from '../components/ui/Premium'

function normalizeSuccessData(resp) {
  if (resp && typeof resp === 'object' && 'data' in resp) return resp.data
  return resp
}

function toDateSafe(v) {
  if (!v) return null
  try {
    const d = new Date(v)
    if (Number.isNaN(d.getTime())) return null
    return d
  } catch (_) {
    return null
  }
}

function fmtDateTime(dt) {
  if (!dt) return '—'
  try {
    return dt.toLocaleString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch (_) {
    return String(dt)
  }
}

function fmtDateOnly(dt) {
  if (!dt) return '—'
  try {
    return dt.toLocaleDateString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
  } catch (_) {
    return String(dt)
  }
}

function fmtTimeOnly(dt) {
  if (!dt) return '—'
  try {
    return dt.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch (_) {
    return '—'
  }
}

function fmtShortMonthDay(d) {
  try {
    return d.toLocaleDateString(undefined, { month: 'short', day: '2-digit' })
  } catch (_) {
    return ''
  }
}

function fmtMonthLabel(d) {
  try {
    return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  } catch (_) {
    return ''
  }
}

function fmtPhone(p) {
  const s = String(p || '').trim()
  if (!s) return '—'
  return s
}

function startOfWeekLocal(d = new Date()) {
  const dt = new Date(d)
  const day = dt.getDay() // 0=Sun..6=Sat
  const diff = (day + 6) % 7 // back to Monday
  dt.setDate(dt.getDate() - diff)
  dt.setHours(0, 0, 0, 0)
  return dt
}

function startOfMonthLocal(d = new Date()) {
  const dt = new Date(d)
  dt.setDate(1)
  dt.setHours(0, 0, 0, 0)
  return dt
}

function monthKey(d = new Date()) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

function startOfMonthKeyLocal(ym) {
  const [yRaw, mRaw] = String(ym || '').split('-')
  const y = Number(yRaw)
  const m = Number(mRaw)
  if (!Number.isFinite(y) || !Number.isFinite(m) || m < 1 || m > 12) return startOfMonthLocal(new Date())
  const dt = new Date(y, m - 1, 1)
  dt.setHours(0, 0, 0, 0)
  return dt
}

function isCanceledStatus(status) {
  const s = String(status || '').toLowerCase()
  return s.includes('cancel') || s.includes('no-show') || s.includes('noshow')
}

export default function ClientsDirectory() {
  const { t } = useI18n()
  const location = useLocation()
  const demo = isDemoMode()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [clientes, setClientes] = useState([])
  const [agendamentos, setAgendamentos] = useState([])
  const [config, setConfig] = useState(null)

  const [q, setQ] = useState('')

  useEffect(() => {
    try {
      const params = new URLSearchParams(location?.search || '')
      const v = String(params.get('q') || '').trim()
      if (v) setQ(v)
    } catch (_) {
      // ignore
    }
  }, [location?.search])

  const [periodMode, setPeriodMode] = useState('month') // month | week
  const [selectedMonth, setSelectedMonth] = useState(() => monthKey())
  const [weekAnchor, setWeekAnchor] = useState(() => {
    const d = new Date()
    return d.toISOString().slice(0, 10)
  })

  const [serviceFilter, setServiceFilter] = useState('')
  const [profFilter, setProfFilter] = useState('')

  useEffect(() => {
    let mounted = true

    if (demo) {
      setError(null)
      setConfig(demoConfig())
      setClientes(demoClientes())
      setAgendamentos(demoAgendamentos())
      setLoading(false)
      return () => {
        mounted = false
      }
    }

    async function loadAll() {
      setLoading(true)
      setError(null)
      try {
        const [cfgRaw, clientesRaw, agRaw] = await Promise.all([
          API.get('/config').catch(() => null),
          API.get('/dashboard/clientes'),
          API.get('/dashboard/agendamentos'),
        ])

        if (!mounted) return
        setConfig(normalizeSuccessData(cfgRaw))
        setClientes(Array.isArray(normalizeSuccessData(clientesRaw)) ? normalizeSuccessData(clientesRaw) : [])
        setAgendamentos(Array.isArray(normalizeSuccessData(agRaw)) ? normalizeSuccessData(agRaw) : [])
      } catch (_) {
        if (!mounted) return
        setError(t('clients_list_error'))
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
  }, [t, demo])

  async function reload() {
    setLoading(true)
    setError(null)
    try {
      const [cfgRaw, clientesRaw, agRaw] = await Promise.all([
        API.get('/config').catch(() => null),
        API.get('/dashboard/clientes'),
        API.get('/dashboard/agendamentos'),
      ])
      setConfig(normalizeSuccessData(cfgRaw))
      setClientes(Array.isArray(normalizeSuccessData(clientesRaw)) ? normalizeSuccessData(clientesRaw) : [])
      setAgendamentos(Array.isArray(normalizeSuccessData(agRaw)) ? normalizeSuccessData(agRaw) : [])
    } catch (_) {
      setError(t('clients_list_error'))
      setClientes([])
      setAgendamentos([])
    } finally {
      setLoading(false)
    }
  }

  const profNameById = useMemo(() => {
    const map = new Map()
    const list = config && config.professionals ? config.professionals : []
    for (const p of list) {
      if (p && p.id != null) map.set(String(p.id), p.name || p.nome || `#${p.id}`)
    }
    return map
  }, [config])

  const clienteById = useMemo(() => {
    const map = new Map()
    for (const c of clientes || []) {
      if (c && c.id != null) map.set(String(c.id), c)
    }
    return map
  }, [clientes])

  const range = useMemo(() => {
    if (periodMode === 'week') {
      const anchor = toDateSafe(weekAnchor) || new Date()
      const start = startOfWeekLocal(anchor)
      const end = new Date(start)
      end.setDate(end.getDate() + 7)
      return { start, end }
    }

    const start = startOfMonthKeyLocal(selectedMonth)
    const end = new Date(start)
    end.setMonth(end.getMonth() + 1)
    return { start, end }
  }, [periodMode, selectedMonth, weekAnchor])

  const periodLabel = useMemo(() => {
    if (!range?.start || !range?.end) return ''

    if (periodMode === 'week') {
      const endInclusive = new Date(range.end)
      endInclusive.setDate(endInclusive.getDate() - 1)
      return `Semana: ${fmtShortMonthDay(range.start)} – ${fmtShortMonthDay(endInclusive)}`
    }

    return `Mês: ${fmtMonthLabel(range.start)}`
  }, [periodMode, range])

  const apptRows = useMemo(() => {
    const startMs = range.start.getTime()
    const endMs = range.end.getTime()

    const qn = String(q || '').trim().toLowerCase()
    const svcNeedle = String(serviceFilter || '').trim().toLowerCase()
    const profNeedle = String(profFilter || '').trim().toLowerCase()

    const out = []
    for (const a of agendamentos || []) {
      const dt = toDateSafe(a?.data_hora)
      if (!dt) continue
      const tms = dt.getTime()
      if (tms < startMs || tms >= endMs) continue
      if (isCanceledStatus(a?.status)) continue

      const clienteId = a?.cliente_id != null ? String(a.cliente_id) : ''
      const c = clienteId ? (clienteById.get(clienteId) || null) : null

      const profId = a?.funcionario_id != null ? String(a.funcionario_id) : ''
      const profName = profId ? (profNameById.get(profId) || profId) : ''

      const serviceName = String(a?.descricao || '').trim()

      if (svcNeedle && String(serviceName).toLowerCase() !== svcNeedle) continue
      if (profNeedle && String(profName).toLowerCase() !== profNeedle) continue

      if (qn) {
        const blob = [
          c?.nome,
          c?.telefone,
          profName,
          serviceName,
        ].map((x) => String(x || '').toLowerCase()).join(' | ')
        if (!blob.includes(qn)) continue
      }

      out.push({
        id: String(a?.id ?? `${clienteId}-${String(a?.data_hora || '')}`),
        clienteNome: String(c?.nome || '—'),
        clienteTelefone: fmtPhone(c?.telefone),
        dt,
        profNome: profName || '—',
        serviceName: serviceName || '—',
      })
    }

    out.sort((x, y) => y.dt.getTime() - x.dt.getTime())
    return out
  }, [agendamentos, clienteById, profNameById, q, range, serviceFilter, profFilter])

  const cards = useMemo(() => {
    const uniqueClients = new Set()
    const countsByProf = new Map()
    const countsByService = new Map()

    for (const r of apptRows) {
      if (r.clienteNome && r.clienteNome !== '—') uniqueClients.add(r.clienteNome)
      const p = String(r.profNome || '').trim()
      if (p) countsByProf.set(p, (countsByProf.get(p) || 0) + 1)
      const s = String(r.serviceName || '').trim()
      if (s) countsByService.set(s, (countsByService.get(s) || 0) + 1)
    }

    const cfgProfs = Array.isArray(config?.professionals) ? config.professionals : []
    const cfgSvcs = Array.isArray(config?.services) ? config.services : []

    const professionalsCatalog = cfgProfs
      .map((p) => (p && (p.name || p.nome)) ? String(p.name || p.nome).trim() : '')
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))

    const servicesCatalog = cfgSvcs
      .map((s) => (s && s.name) ? String(s.name).trim() : '')
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))

    // Fallback seguro (caso /config falhe ou venha vazio)
    const fallbackProfs = Array.from(countsByProf.entries()).sort((a, b) => b[1] - a[1]).map(([name]) => name)
    const fallbackSvcs = Array.from(countsByService.entries()).sort((a, b) => b[1] - a[1]).map(([name]) => name)

    return {
      uniqueClients: uniqueClients.size,
      totalAppointments: apptRows.length,
      countsByProf,
      countsByService,
      professionalsCatalog: professionalsCatalog.length ? professionalsCatalog : fallbackProfs,
      servicesCatalog: servicesCatalog.length ? servicesCatalog : fallbackSvcs,
    }
  }, [apptRows, config])

  function Chip({ active, children, onClick, title }) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={title}
        style={{
          border: '1px solid rgba(15,23,42,0.10)',
          background: active ? '#111827' : '#ffffff',
          color: active ? '#ffffff' : '#0f1724',
          fontWeight: 900,
          fontSize: 12,
          padding: '6px 10px',
          borderRadius: 999,
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        {children}
      </button>
    )
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0 }}>{t('clients_list_title')}</h3>

                {demo ? (
                  <span style={demoBadgeStyle()}>
                    DEMO
                    <button
                      type="button"
                      onClick={() => setDemoMode(false)}
                      style={{ border: '0', background: 'transparent', color: 'inherit', fontWeight: 900, cursor: 'pointer' }}
                    >
                      sair
                    </button>
                  </span>
                ) : (
                  <button type="button" className="action-btn" style={{ padding: '6px 10px' }} onClick={() => setDemoMode(true)}>
                    Preview demo
                  </button>
                )}

                <button className="action-btn" onClick={reload} disabled={loading} style={{ padding: '6px 10px' }}>
                  {loading ? t('loading') : 'Atualizar'}
                </button>
              </div>
              <div style={{ color: '#6b7280', fontSize: 13, marginTop: 4 }}>
                Visão limpa por período (mês/semana). Mostra cliente, telefone, data e quem atendeu.
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                data-e2e="clients-search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t('clients_search')}
                style={{ padding: '10px 12px', borderRadius: 12, border: '1px solid #e5e7eb', minWidth: 260 }}
              />

              <div
                data-e2e="clients-count"
                style={{ color: '#6b7280', fontSize: 12, padding: '0 6px' }}
                aria-label="clients count"
              >
                {loading ? 'Carregando…' : `${cards.uniqueClients} clientes no período`}
              </div>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <Chip active={periodMode === 'week'} onClick={() => setPeriodMode('week')}>Semana</Chip>
                <Chip active={periodMode === 'month'} onClick={() => setPeriodMode('month')}>Mês</Chip>
              </div>

              {periodMode === 'month' ? (
                <input
                  type="month"
                  value={selectedMonth}
                  onChange={(e) => setSelectedMonth(e.target.value)}
                  style={{ padding: '10px 12px', borderRadius: 12, border: '1px solid #e5e7eb' }}
                />
              ) : (
                <input
                  type="date"
                  value={weekAnchor}
                  onChange={(e) => setWeekAnchor(e.target.value)}
                  style={{ padding: '10px 12px', borderRadius: 12, border: '1px solid #e5e7eb' }}
                />
              )}

              <div style={{ color: '#6b7280', fontSize: 12, padding: '0 6px', fontWeight: 800 }}>
                {periodLabel}
              </div>

              {(serviceFilter || profFilter) ? (
                <button
                  type="button"
                  className="action-btn"
                  style={{ padding: '10px 12px' }}
                  onClick={() => { setServiceFilter(''); setProfFilter('') }}
                >
                  Limpar filtros
                </button>
              ) : null}
            </div>
          </div>

          {error ? (
            <div style={{ marginTop: 12 }}>
              <Callout tone="warn" title={t('clients_list_error')}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                  <div>{error}</div>
                  <button type="button" className="action-btn" onClick={reload} style={{ padding: '8px 12px' }}>
                    {t('retry')}
                  </button>
                </div>
              </Callout>
            </div>
          ) : null}

          {loading ? (
            <div style={{ padding: 18, color: '#6b7280' }}>{t('loading')}</div>
          ) : !error ? (
            <>
              <div style={{ marginTop: 12, display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 4 }}>
                <div style={{ minWidth: 280, flex: '0 0 auto' }}>
                  <KpiCard label="Clientes no período" value={cards.uniqueClients} hint={periodMode === 'week' ? 'Semana selecionada.' : 'Mês selecionado.'} />
                </div>

                <div className="card-surface" style={{ minWidth: 320, flex: '0 0 auto', padding: 14, border: '1px solid rgba(15,23,42,0.06)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
                    <div style={{ fontSize: 13, color: '#6b7280' }}>Funcionários</div>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>toque para filtrar</div>
                  </div>
                  <div style={{ marginTop: 10, display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                    <Chip active={!profFilter} onClick={() => setProfFilter('')}>Todos</Chip>
                    {cards.professionalsCatalog.map((name) => (
                      <Chip
                        key={name}
                        active={String(profFilter).toLowerCase() === String(name).toLowerCase()}
                        onClick={() => setProfFilter(String(name))}
                        title={`${cards.countsByProf.get(name) || 0} atendimentos no período`}
                      >
                        {name}
                      </Chip>
                    ))}
                  </div>
                </div>

                <div className="card-surface" style={{ minWidth: 320, flex: '0 0 auto', padding: 14, border: '1px solid rgba(15,23,42,0.06)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
                    <div style={{ fontSize: 13, color: '#6b7280' }}>Serviços</div>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>scroll se tiver muitos</div>
                  </div>
                  <div style={{ marginTop: 10, display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                    <Chip active={!serviceFilter} onClick={() => setServiceFilter('')}>Todos</Chip>
                    {cards.servicesCatalog.map((name) => (
                      <Chip
                        key={name}
                        active={String(serviceFilter).toLowerCase() === String(name).toLowerCase()}
                        onClick={() => setServiceFilter(String(name))}
                        title={`${cards.countsByService.get(name) || 0} atendimentos no período`}
                      >
                        {name}
                      </Chip>
                    ))}
                  </div>
                </div>
              </div>

              <div className="agenda-card" style={{ padding: 0, overflow: 'hidden', marginTop: 12 }}>
                <div className="agenda-table">
                  <table style={{ borderCollapse: 'separate', borderSpacing: 0 }}>
                    <thead>
                      <tr>
                        <th style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb', padding: '12px 14px' }}>Cliente</th>
                        <th style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb', padding: '12px 14px' }}>Telefone</th>
                        <th style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb', padding: '12px 14px' }}>Data</th>
                        <th style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb', padding: '12px 14px' }}>Hora</th>
                        <th style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb', padding: '12px 14px' }}>Funcionário</th>
                      </tr>
                    </thead>
                    <tbody>
                      {apptRows.length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ color: '#6b7280', padding: 16 }}>
                            <div style={{ fontWeight: 900, color: '#111827', marginBottom: 6 }}>Sem resultados</div>
                            <div style={{ fontSize: 13 }}>
                              Ajuste o período (mês/semana) ou a busca.
                            </div>
                          </td>
                        </tr>
                      ) : (
                        apptRows.map((r, idx) => (
                          <tr key={r.id}>
                            <td style={{ fontWeight: 900, color: '#0f1724', padding: '12px 14px', borderBottom: '1px solid #f1f5f9', background: idx % 2 === 0 ? '#ffffff' : '#fbfdff' }}>{r.clienteNome}</td>
                            <td style={{ color: '#0f1724', padding: '12px 14px', borderBottom: '1px solid #f1f5f9', background: idx % 2 === 0 ? '#ffffff' : '#fbfdff' }}>{r.clienteTelefone}</td>
                            <td style={{ color: '#0f1724', padding: '12px 14px', borderBottom: '1px solid #f1f5f9', background: idx % 2 === 0 ? '#ffffff' : '#fbfdff' }}>
                              <div style={{ fontWeight: 900 }}>{fmtDateOnly(r.dt)}</div>
                              <div style={{ fontSize: 12, color: '#6b7280' }}>{r.serviceName}</div>
                            </td>
                            <td style={{ color: '#0f1724', padding: '12px 14px', borderBottom: '1px solid #f1f5f9', background: idx % 2 === 0 ? '#ffffff' : '#fbfdff' }}>
                              <span style={{ display: 'inline-flex', alignItems: 'center', padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(15,23,42,0.10)', background: '#ffffff', fontWeight: 900 }}>
                                {fmtTimeOnly(r.dt)}
                              </span>
                            </td>
                            <td style={{ color: '#0f1724', padding: '12px 14px', borderBottom: '1px solid #f1f5f9', background: idx % 2 === 0 ? '#ffffff' : '#fbfdff' }}>{r.profNome}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
