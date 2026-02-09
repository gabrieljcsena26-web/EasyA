import React, { useCallback, useEffect, useMemo, useState } from 'react'
import Header from '../components/dashboard/Header'
import API from '../utils/api'
import '../components/dashboard/dashboard.css'
import { useI18n } from '../i18n'

function readLocalQueue() {
  try {
    const raw = localStorage.getItem('ea_pending_actions')
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (_) {
    return []
  }
}

function writeLocalQueue(items) {
  try {
    localStorage.setItem('ea_pending_actions', JSON.stringify(items || []))
  } catch (_) {}
}

export default function PendingActions() {
  const { t } = useI18n()
  const [localQueue, setLocalQueue] = useState(() => readLocalQueue())
  const [remoteQueue, setRemoteQueue] = useState([])
  const [loadingRemote, setLoadingRemote] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState(null)

  const localCount = localQueue.length

  const refreshLocal = useCallback(() => {
    setLocalQueue(readLocalQueue())
  }, [])

  const refreshRemote = useCallback(async () => {
    setLoadingRemote(true)
    setError(null)
    try {
      const res = await API.get('/admin/pending-actions')
      setRemoteQueue(res && Array.isArray(res.items) ? res.items : [])
    } catch (e) {
      setRemoteQueue([])
      setError('Não consegui carregar pendências do backend. (Token admin?)')
    } finally {
      setLoadingRemote(false)
    }
  }, [])

  useEffect(() => {
    refreshRemote()
  }, [refreshRemote])

  const localPreview = useMemo(() => localQueue.slice(0, 50), [localQueue])

  const clearLocal = () => {
    if (!window.confirm('Apagar pendências locais deste browser?')) return
    writeLocalQueue([])
    setLocalQueue([])
  }

  const syncLocalToBackend = async () => {
    if (localQueue.length === 0) return
    setSyncing(true)
    setError(null)

    try {
      const next = [...localQueue]
      const toRemove = new Set()

      for (let i = 0; i < next.length; i++) {
        const item = next[i]
        const ts = item && item.ts ? item.ts : Date.now()
        const path = item && item.path ? String(item.path) : 'unknown'
        const idem = (item && item.idempotency_key) ? String(item.idempotency_key) : `offline:${ts}:${path}`

        await API.post('/admin/pending-actions', {
          tipo: 'offline_action',
          idempotency_key: idem,
          payload: item,
        })

        toRemove.add(i)
      }

      const remaining = next.filter((_, idx) => !toRemove.has(idx))
      writeLocalQueue(remaining)
      setLocalQueue(remaining)
      await refreshRemote()
    } catch (e) {
      setError('Falha ao sincronizar. Verifique token/conexão.')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ padding: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ margin: 0 }} data-e2e="pending-actions-title">{t('nav_pending')}</h3>
              <div style={{ marginTop: 4, color: '#6b7280', fontSize: 13 }}>
                Pendências locais (offline) + fila do backend.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button className="action-btn" onClick={() => { refreshLocal(); refreshRemote(); }} disabled={loadingRemote || syncing}>
                Recarregar
              </button>
            </div>
          </div>

          {error ? (
            <div style={{ marginTop: 10, background: '#fef2f2', color: '#991b1b', padding: 10, borderRadius: 10, border: '1px solid #fecaca' }}>
              {error}
            </div>
          ) : null}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12, marginTop: 12 }}>
            <div className="card-surface" style={{ padding: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
                <div style={{ fontWeight: 600 }}>Local (este browser)</div>
                <div style={{ color: '#6b7280', fontSize: 13 }}>{localCount} item(s)</div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
                <button className="action-btn" onClick={syncLocalToBackend} disabled={syncing || localCount === 0}>
                  {syncing ? 'Sincronizando…' : 'Enviar para backend'}
                </button>
                <button className="action-btn secondary" onClick={clearLocal} disabled={syncing || localCount === 0}>
                  Limpar local
                </button>
              </div>

              <pre style={{ marginTop: 10, padding: 10, background: '#0b1220', color: '#e5e7eb', borderRadius: 10, overflowX: 'auto', fontSize: 12 }}>
{JSON.stringify(localPreview, null, 2)}
              </pre>
              {localCount > 50 ? (
                <div style={{ color: '#6b7280', fontSize: 12, marginTop: 6 }}>Mostrando apenas os primeiros 50 itens.</div>
              ) : null}
            </div>

            <div className="card-surface" style={{ padding: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
                <div style={{ fontWeight: 600 }}>Backend</div>
                <div style={{ color: '#6b7280', fontSize: 13 }}>{loadingRemote ? 'Carregando…' : `${remoteQueue.length} item(s)`}</div>
              </div>

              <pre style={{ marginTop: 10, padding: 10, background: '#0b1220', color: '#e5e7eb', borderRadius: 10, overflowX: 'auto', fontSize: 12 }}>
{JSON.stringify(remoteQueue, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
