import React, { useEffect, useRef, useState } from 'react';
import Header from '../components/dashboard/Header';
import API from '../utils/api';
import { useI18n } from '../i18n';
import { isDemoMode, setDemoMode, demoBadgeStyle } from '../utils/demo';
import { demoNotificationsDashboard } from '../utils/demoData';
import { Card } from '../components/ui/Premium';

function safeStr(v) {
  const s = String(v == null ? '' : v).trim();
  return s || '—';
}

function statusLabelKey(k) {
  const key = String(k || '')
  if (key === 'queued') return 'Na fila'
  if (key === 'failed') return 'Falha (re-tentativa)'
  if (key === 'sending') return 'Enviando'
  if (key === 'sent') return 'Enviado'
  if (key === 'delivered') return 'Entregue'
  if (key === 'permanent_failure') return 'Falha permanente'
  if (key === 'unknown') return 'Desconhecido'
  return key
}

function orderedCounts(counts) {
  const c = counts && typeof counts === 'object' ? counts : {}
  const keys = ['queued', 'failed', 'sending', 'sent', 'delivered', 'permanent_failure', 'unknown']
  return keys
    .filter((k) => c[k] != null)
    .map((k) => ({ key: k, label: statusLabelKey(k), value: Number(c[k] || 0) }))
}

function fmtDt(s) {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString()
}

function tipoLabel(tipo) {
  const t = String(tipo || '').toLowerCase()
  if (t === 'pre_confirmacao') return 'Pré-confirmação'
  if (t === 'confirmacao_oficial') return 'Confirmação (oficial)'
  if (t === 'confirmacao_urgente') return 'Confirmação (urgente)'
  if (t === 'confirmacao') return 'Confirmação'
  if (t === 'lembrete') return 'Lembrete'
  if (t) return t
  return '—'
}

function sequenceLabel(tipo) {
  const t = String(tipo || '').toLowerCase()
  if (t === 'pre_confirmacao') return '1/2'
  if (t === 'confirmacao_oficial') return '2/2'
  if (t === 'confirmacao_urgente') return '1/1'
  if (t === 'confirmacao') return '1/2'
  if (t === 'lembrete') return '2/2'
  return '—'
}

function statusBadge(statusRaw) {
  const s = String(statusRaw || '').toLowerCase()
  const base = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 999, fontWeight: 800, fontSize: 11, border: '1px solid transparent' }
  if (s === 'delivered') return { label: 'Entregue', style: { ...base, background: 'linear-gradient(180deg,#e6ffef,#c9f7d6)', color: '#065f46', borderColor: '#dcfce7' } }
  if (s === 'sent') return { label: 'Disparado', style: { ...base, background: 'linear-gradient(180deg,#eff6ff,#dbeafe)', color: '#1e40af', borderColor: '#bfdbfe' } }
  if (s === 'sending') return { label: 'Processando', style: { ...base, background: 'linear-gradient(180deg,#fffbeb,#fef3c7)', color: '#92400e', borderColor: '#fde68a' } }
  if (s === 'queued') return { label: 'Na fila', style: { ...base, background: '#f3f4f6', color: '#111827', borderColor: '#e5e7eb' } }
  if (s === 'failed' || s === 'permanent_failure') return { label: s === 'permanent_failure' ? 'Falha (parou)' : 'Falha (vai tentar)', style: { ...base, background: 'linear-gradient(180deg,#fff5f6,#ffecec)', color: '#7f1d1d', borderColor: '#fee2e2' } }
  if (!s) return { label: '—', style: base }
  return { label: statusRaw, style: { ...base, background: '#f3f4f6', color: '#111827', borderColor: '#e5e7eb' } }
}

function apptStatusBadge(statusRaw) {
  const s = String(statusRaw || '').toLowerCase()
  const base = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 999, fontWeight: 900, fontSize: 11, border: '1px solid rgba(15,23,42,0.06)', background: '#fff' }
  if (s.includes('confirm')) return { label: 'Confirmado', style: { ...base, background: 'linear-gradient(180deg,#e6ffef,#c9f7d6)', color: '#065f46' } }
  if (s.includes('cancel')) return { label: 'Cancelado', style: { ...base, background: 'linear-gradient(180deg,#fff5f6,#ffecec)', color: '#7f1d1d' } }
  return { label: statusRaw ? 'Em espera' : '—', style: { ...base, background: 'linear-gradient(180deg,#fffbeb,#fef3c7)', color: '#92400e' } }
}

function apptOutcomeKey(statusRaw) {
  const s = String(statusRaw || '').toLowerCase()
  if (!s) return 'unknown'
  if (s.includes('confirm')) return 'confirmed'
  if (s.includes('cancel')) return 'canceled'
  return 'pending'
}

function apptOutcomeBadge(statusRaw) {
  const k = apptOutcomeKey(statusRaw)
  const base = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 999, fontWeight: 950, fontSize: 11, border: '1px solid rgba(15,23,42,0.06)', background: '#fff' }
  if (k === 'confirmed') return { label: 'Confirmado', style: { ...base, background: 'linear-gradient(180deg,#e6ffef,#c9f7d6)', color: '#065f46' } }
  if (k === 'canceled') return { label: 'Cancelado', style: { ...base, background: 'linear-gradient(180deg,#fff5f6,#ffecec)', color: '#7f1d1d' } }
  if (k === 'pending') return { label: 'Sem resposta', style: { ...base, background: 'linear-gradient(180deg,#fffbeb,#fef3c7)', color: '#92400e' } }
  return { label: '—', style: { ...base, background: '#f3f4f6', color: '#111827', borderColor: '#e5e7eb' } }
}

function computeAppointmentOutcomeCounts(items) {
  const list = Array.isArray(items) ? items : []
  const seen = new Set()
  const counts = { confirmed: 0, canceled: 0, pending: 0, unknown: 0 }
  for (const n of list) {
    const id = n && n.agendamento_id
    if (!id) continue
    if (seen.has(id)) continue
    seen.add(id)
    const k = apptOutcomeKey(n.agendamento_status)
    if (counts[k] == null) counts[k] = 0
    counts[k] += 1
  }
  return counts
}

function headerPill(label, tone = 'neutral') {
  const base = { display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 999, fontWeight: 900, fontSize: 11, border: '1px solid rgba(15,23,42,0.08)', background: '#fff', color: '#111827' }
  if (tone === 'success') return { ...base, background: 'linear-gradient(180deg,#e6ffef,#c9f7d6)', color: '#065f46', borderColor: '#dcfce7' }
  if (tone === 'warn') return { ...base, background: 'linear-gradient(180deg,#fffbeb,#fef3c7)', color: '#92400e', borderColor: '#fde68a' }
  if (tone === 'info') return { ...base, background: 'linear-gradient(180deg,#eff6ff,#dbeafe)', color: '#1e40af', borderColor: '#bfdbfe' }
  return base
}

function countChip(label, value, tone = 'neutral') {
  const pill = headerPill(label, tone)
  return (
    <span style={pill}>
      <span style={{ opacity: 0.9 }}>{label}</span>
      <span style={{ fontWeight: 950 }}>{String(value)}</span>
    </span>
  )
}

export default function NotificationsOps() {
  const { t } = useI18n();
  const demo = isDemoMode();
  const [dashboard, setDashboard] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');
  const upcomingScrollRef = useRef(null)
  const recentScrollRef = useRef(null)
  const syncLockRef = useRef(false)

  async function refresh() {
    setError(null);
    try {
      if (demo) {
        setDashboard(demoNotificationsDashboard());
        return;
      }
      const d = await API.get('/admin/notifications-dashboard');
      setDashboard(d);
    } catch (e) {
      setError(t('notif_load_error'));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function retryQueue() {
    setError(null);
    setBusy(true);
    try {
      if (demo) {
        await refresh();
        return;
      }
      await API.post('/admin/notifications-retry?limit=50', {});
      await refresh();
    } catch (e) {
      setError(t('notif_retry_error'));
    } finally {
      setBusy(false);
    }
  }

  const counts = (dashboard && dashboard.counts) || {}
  const queued = Number(counts.queued || 0)
  const failed = Number(counts.failed || 0)
  const pending = queued + failed
  const nextIn = dashboard && (dashboard.next_in_minutes != null ? Number(dashboard.next_in_minutes) : null)
  const provider = (dashboard && dashboard.provider) || {}
  const providerOk = !!provider.twilio_configured
  const delivered = Number(counts.delivered || 0)
  const sent = Number(counts.sent || 0)
  const permanentFailure = Number(counts.permanent_failure || 0)
  const sending = Number(counts.sending || 0)
  const totalFailures = failed + permanentFailure

  const upcomingItemsAll = (dashboard && Array.isArray(dashboard.upcoming) ? dashboard.upcoming : [])
  const recentItemsAll = (dashboard && Array.isArray(dashboard.recent) ? dashboard.recent : [])
  const q = String(filter || '').trim().toLowerCase()
  const match = (n) => {
    if (!q) return true
    const hay = [n?.cliente_nome, n?.destinatario, n?.canal, n?.tipo, n?.agendamento_status, n?.agendamento_id, n?.id]
      .map((v) => String(v == null ? '' : v).toLowerCase())
      .join(' ')
    return hay.includes(q)
  }
  const upcomingItems = upcomingItemsAll.filter(match)
  const recentItems = recentItemsAll.filter(match)
  const outcomeCounts = computeAppointmentOutcomeCounts([...upcomingItems, ...recentItems])

  function syncScroll(from) {
    if (syncLockRef.current) return
    const a = upcomingScrollRef.current
    const b = recentScrollRef.current
    if (!a || !b) return
    syncLockRef.current = true
    try {
      const source = from === 'upcoming' ? a : b
      const target = from === 'upcoming' ? b : a
      target.scrollTop = source.scrollTop
    } finally {
      // next frame unlock to avoid ping-pong
      requestAnimationFrame(() => { syncLockRef.current = false })
    }
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ margin: 14, padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0 }}>{t('notif_title')}</h3>
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
              <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={headerPill(providerOk ? 'Operação ativa' : 'Mensagens indisponíveis', providerOk ? 'success' : 'warn')}>{providerOk ? 'Operação ativa' : 'Mensagens indisponíveis'}</span>
                <span style={headerPill('WhatsApp + SMS', 'info')}>WhatsApp + SMS</span>
                <span style={headerPill('2 etapas', 'neutral')}>2 etapas</span>
                <span style={headerPill('Re-tentativa automática', 'neutral')}>Re-tentativa automática</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filtrar (cliente, id, status...)"
                style={{
                  height: 36,
                  padding: '0 12px',
                  borderRadius: 999,
                  border: '1px solid rgba(15,23,42,0.10)',
                  background: '#fff',
                  minWidth: 260,
                  outline: 'none',
                }}
              />
              <button className="action-btn" onClick={refresh} disabled={busy} data-e2e="notif-refresh">{t('notif_refresh')}</button>
              <button className="action-btn" onClick={retryQueue} disabled={busy} data-e2e="notif-retry">Processar fila</button>
            </div>
          </div>

          {error ? (
            <div style={{ marginTop: 12, color: '#b91c1c', fontSize: 13 }} data-e2e="notif-error">{error}</div>
          ) : null}

          {q ? (
            <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={headerPill(`Filtro: ${filter}`, 'neutral')}>Filtro: {filter}</span>
              <button type="button" className="action-btn" onClick={() => setFilter('')} style={{ padding: '6px 10px' }}>Limpar</button>
              <span style={{ color: '#6b7280', fontSize: 12 }}>Mostrando {upcomingItems.length} na fila e {recentItems.length} recentes.</span>
            </div>
          ) : null}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(520px, 1fr))', gap: 12, marginTop: 12, alignItems: 'start' }}>
            <div className="agenda-card" style={{ margin: 0 }}>
              <div className="agenda-header" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Próximos envios</h3>
                <div style={{ color: '#6b7280', fontSize: 12 }}>Fila e re-tentativas agendadas</div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
                {countChip('Pendentes', dashboard ? pending : '—', pending > 0 ? 'warn' : 'neutral')}
                {countChip('Na fila', dashboard ? queued : '—', 'neutral')}
                {countChip('Falhas', dashboard ? totalFailures : '—', totalFailures > 0 ? 'warn' : 'neutral')}
                <span style={headerPill(nextIn == null ? 'Próximo: —' : nextIn <= 0 ? 'Próximo: agora' : `Próximo: ${nextIn} min`, 'neutral')}>
                  {nextIn == null ? 'Próximo: —' : nextIn <= 0 ? 'Próximo: agora' : `Próximo: ${nextIn} min`}
                </span>
              </div>
              <div
                className="agenda-table"
                ref={upcomingScrollRef}
                onScroll={() => syncScroll('upcoming')}
                style={{ maxHeight: 520, overflowY: 'auto', overscrollBehavior: 'contain' }}
                title="Role com o mouse para ver mais (sincroniza com a outra tabela)"
              >
                <table>
                  <thead>
                    <tr>
                      <th>Cliente</th>
                      <th>Envio</th>
                      <th>Etapa</th>
                      <th>Fila (operação)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {upcomingItems.slice(0, 50).map((n) => {
                      const b = statusBadge(n.status)
                      const when = n.next_attempt_at ? fmtDt(n.next_attempt_at) : 'Agora'
                      const inMin = (n.next_in_minutes == null) ? null : Number(n.next_in_minutes)
                      const retryInfo = (String(n.status || '').toLowerCase() === 'failed' || String(n.status || '').toLowerCase() === 'permanent_failure')
                        ? `Re-tentativa: ${safeStr(n.attempts)} / ${safeStr(n.max_attempts)}`
                        : ''
                      return (
                        <tr key={n.id}>
                          <td>
                            <div style={{ fontWeight: 800 }}>{safeStr(n.cliente_nome)}</div>
                            <div style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>{n.agendamento_data_hora ? fmtDt(n.agendamento_data_hora) : '—'} • #{safeStr(n.agendamento_id)}</div>
                          </td>
                          <td style={{ color: '#374151' }}>
                            <div style={{ fontWeight: 800 }}>{when}</div>
                            <div style={{ color: '#6b7280', fontSize: 12 }}>{inMin == null ? '' : (inMin <= 0 ? 'em instantes' : `em ${inMin} min`)}</div>
                            <div style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>{String(n.canal || '—').toUpperCase()} • {safeStr(n.destinatario)}</div>
                          </td>
                          <td style={{ fontWeight: 900 }}>
                            <div style={{ fontWeight: 950 }}>{sequenceLabel(n.tipo)}</div>
                            <div style={{ color: '#6b7280', fontSize: 12 }}>{tipoLabel(n.tipo)}</div>
                          </td>
                          <td>
                            <span style={b.style} title={retryInfo || undefined}>{b.label}</span>
                            {n.last_error ? (
                              <div style={{ color: '#b91c1c', fontSize: 12, marginTop: 6, maxWidth: 360, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={String(n.last_error)}>
                                {String(n.last_error)}
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      )
                    })}
                    {(!dashboard || !Array.isArray(dashboard.upcoming) || dashboard.upcoming.length === 0) && (
                      <tr><td colSpan={4} style={{ color: '#6b7280', padding: 14 }}>Nada na fila agora.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="agenda-card" style={{ margin: 0 }}>
              <div className="agenda-header" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Resultado do agendamento</h3>
                <div style={{ color: '#6b7280', fontSize: 12 }}>Fonte da verdade: confirmado, cancelado ou sem resposta</div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
                {countChip('Confirmados', dashboard ? outcomeCounts.confirmed : '—', outcomeCounts.confirmed > 0 ? 'success' : 'neutral')}
                {countChip('Cancelados', dashboard ? outcomeCounts.canceled : '—', outcomeCounts.canceled > 0 ? 'warn' : 'neutral')}
                {countChip('Sem resposta', dashboard ? outcomeCounts.pending : '—', 'neutral')}
              </div>
              <div
                className="agenda-table"
                ref={recentScrollRef}
                onScroll={() => syncScroll('recent')}
                style={{ maxHeight: 520, overflowY: 'auto', overscrollBehavior: 'contain' }}
                title="Role com o mouse para ver mais (sincroniza com a outra tabela)"
              >
                <table>
                  <thead>
                    <tr>
                      <th>Agendamento</th>
                      <th>Cliente</th>
                      <th>Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentItems.slice(0, 50).map((n) => {
                      const out = apptOutcomeBadge(n.agendamento_status)
                      return (
                        <tr key={n.id}>
                          <td style={{ color: '#374151' }}>
                            <div style={{ fontWeight: 800 }}>{n.agendamento_data_hora ? fmtDt(n.agendamento_data_hora) : '—'}</div>
                            <div style={{ color: '#6b7280', fontSize: 12 }}>#{safeStr(n.agendamento_id)}</div>
                          </td>
                          <td>
                            <div style={{ fontWeight: 800 }}>{safeStr(n.cliente_nome)}</div>
                            <div style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>{safeStr(n.destinatario)}</div>
                          </td>
                          <td>
                            <span style={out.style}>{out.label}</span>
                            <div style={{ color: '#6b7280', fontSize: 12, marginTop: 6 }}>
                              Último contato: {tipoLabel(n.tipo)} ({sequenceLabel(n.tipo)}) • {String(n.canal || '—').toUpperCase()}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                    {(!dashboard || !Array.isArray(dashboard.recent) || dashboard.recent.length === 0) && (
                      <tr><td colSpan={4} style={{ color: '#6b7280', padding: 14 }}>Sem eventos recentes.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
