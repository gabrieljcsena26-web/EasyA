import React, { useEffect, useMemo, useState } from 'react'
import { useI18n } from '../../i18n'


const AgendaTable = ({ config, professionalId, date: propDate, hoverDate, onHoverDate, dayMeta, onSelectDate, onOpenClient }) => {
  const { t, lang } = useI18n()

  const locale = useMemo(() => {
    if (lang === 'pt-BR') return 'pt-BR'
    if (lang === 'en') return 'en'
    if (lang === 'es') return 'es'
    if (lang === 'fr') return 'fr'
    if (lang === 'ca') return 'ca'
    return undefined
  }, [lang])

  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all') // all | pending | confirmed | cancelled | noshow

  const professionalNameById = useMemo(() => {
    const map = new Map()
    const list = (config && Array.isArray(config.professionals)) ? config.professionals : []
    for (const p of list) {
      const id = p?.id
      const name = p?.name || p?.nome
      if (id != null && name) map.set(String(id), String(name))
    }
    return map
  }, [config])

  const serviceNameById = useMemo(() => {
    const map = new Map()
    const list = (config && Array.isArray(config.services)) ? config.services : []
    for (const s of list) {
      const id = s?.id
      const name = s?.name || s?.nome
      if (id != null && name) map.set(String(id), String(name))
    }
    return map
  }, [config])

  function fmt(key, vars) {
    let s = t(key)
    for (const [k, v] of Object.entries(vars || {})) {
      s = s.replaceAll(`{${k}}`, String(v))
    }
    return s
  }

  function toLocalISO(d = new Date()){
    const dt = d instanceof Date ? d : new Date(d)
    const y = dt.getFullYear()
    const m = String(dt.getMonth() + 1).padStart(2,'0')
    const day = String(dt.getDate()).padStart(2,'0')
    return `${y}-${m}-${day}`
  }

  function addDaysISO(iso, deltaDays) {
    const d = iso ? new Date(iso) : new Date()
    if (Number.isNaN(d.getTime())) return toLocalISO()
    d.setDate(d.getDate() + (Number(deltaDays) || 0))
    return toLocalISO(d)
  }

  function toggleFilter(nextKey) {
    setStatusFilter((cur) => (cur === nextKey ? 'all' : nextKey))
  }

  function statusClass(s){
    if(!s) return 'status-created'
    const m = String(s).toLowerCase()
    if(m.includes('confirm')) return 'status-confirmado'
    if(m.includes('pend') || m.includes('aguard')) return 'status-pending'
    if(
      m.includes('no-show') ||
      m.includes('no show') ||
      m.includes('noshow') ||
      m.includes('não compareceu') ||
      m.includes('nao compareceu') ||
      m.includes('faltou')
    ) return 'status-noshow'
    if(m.includes('cancel') || m.includes('desmarc')) return 'status-cancelado'
    if(m.includes('criado') || m.includes('created')) return 'status-created'
    return 'status-created'
  }

  function statusLabel(s) {
    if (!s) return ''
    const m = String(s).toLowerCase()
    if (m.includes('confirm')) return t('status_confirmed')
    if (m.includes('pend') || m.includes('aguard') || m.includes('waiting')) return t('status_pending')
    if (
      m.includes('no-show') ||
      m.includes('no show') ||
      m.includes('noshow') ||
      m.includes('não compareceu') ||
      m.includes('nao compareceu') ||
      m.includes('faltou')
    ) return t('status_no_show')
    if (m.includes('cancel') || m.includes('desmarc')) return t('status_cancelled')
    if (m.includes('criado') || m.includes('created')) return t('status_created')
    return String(s)
  }

  function statusKey(s) {
    const cls = statusClass(s)
    if (cls === 'status-confirmado') return 'confirmed'
    if (cls === 'status-pending') return 'pending'
    if (cls === 'status-noshow') return 'noshow'
    if (cls === 'status-cancelado') return 'cancelled'
    return 'other'
  }

  const displayAppointments = useMemo(() => {
    const list = Array.isArray(appointments) ? appointments : []
    return list.map((a) => {
      const profId = a?.professionalId
      const svcId = a?.serviceId
      const profNameFromCfg = profId != null ? professionalNameById.get(String(profId)) : null
      const svcNameFromCfg = svcId != null ? serviceNameById.get(String(svcId)) : null

      const profLabel = a?.professionalName || profNameFromCfg || (profId != null ? `#${profId}` : (a?.prof || ''))
      const serviceLabel = a?.serviceName || svcNameFromCfg || (svcId != null ? `#${svcId}` : (a?.service || ''))

      return {
        ...a,
        profLabel,
        serviceLabel,
      }
    })
  }, [appointments, professionalNameById, serviceNameById])

  const filteredAppointments = useMemo(() => {
    const list = Array.isArray(displayAppointments) ? displayAppointments : []
    if (statusFilter === 'all') return list
    return list.filter((a) => statusKey(a?.status) === statusFilter)
  }, [displayAppointments, statusFilter])

  const statusCounts = useMemo(() => {
    const base = { pending: 0, confirmed: 0, cancelled: 0, noshow: 0 }
    for (const a of (Array.isArray(appointments) ? appointments : [])) {
      const k = statusKey(a?.status)
      if (k in base) base[k] += 1
    }
    return base
  }, [appointments])

  function formatLocalDate(iso){
    if(!iso) return ''
    const parts = String(iso).split('-')
    if(parts.length !== 3) return iso
    const y = parseInt(parts[0],10)
    const m = parseInt(parts[1],10) - 1
    const d = parseInt(parts[2],10)
    return new Date(y,m,d).toLocaleDateString(locale)
  }

  const occupancyLabel = useMemo(() => {
    if (!dayMeta || !dayMeta.state) return null
    const state = dayMeta.state
    const free = (typeof dayMeta.free_slots === 'number') ? dayMeta.free_slots : null
    const total = (typeof dayMeta.total_slots === 'number') ? dayMeta.total_slots : null
    const pct = (typeof dayMeta.occupancy_percent === 'number') ? dayMeta.occupancy_percent : null

    const title = state === 'closed' ? t('occ_closed') : state === 'busy' ? t('occ_busy') : state === 'mid' ? t('occ_mid') : t('occ_free')
    const parts = []
    if (free != null && total != null && total > 0) parts.push(fmt('occ_slots_fmt', { free, total }))
    if (pct != null) parts.push(fmt('occ_percent_fmt', { pct }))
    return { state, title, detail: parts.join(' · ') }
  }, [dayMeta, t])

  useEffect(() => {
    let mounted = true
    const TOKEN = (typeof window !== 'undefined' && (localStorage.getItem('DEV_JWT_TOKEN') || window.__DEV_TOKEN__)) || ''



    async function load() {
      setLoading(true)
      try {
        let profId = professionalId
        if (profId == null) {
          // fallback: tentar pegar config público para obter professional id
          const cfgRes = await fetch((window.__API_URL__ || 'http://127.0.0.1:8000') + '/config')
          let fallback = 1
          if (cfgRes.ok) {
            const cfg = await cfgRes.json()
            if (cfg.professionals && cfg.professionals.length) fallback = cfg.professionals[0].id
          }
          profId = fallback
        }

        const date = propDate || toLocalISO()

        // check for demo appointments injected by the mini-calendar scenario
        let demoMap = null
        if (typeof window !== 'undefined') {
          const raw = localStorage.getItem('DEMO_APPTS')
          if (raw) {
            try { demoMap = JSON.parse(raw) } catch (e) { demoMap = null }
          }
        }
        if (demoMap && demoMap[date]) {
          const data = demoMap[date]
          const mapped = (Array.isArray(data) ? data : []).map(a => ({
            id: a.id,
            time: a.start_time || a.startTime || '',
            client: a.customer_name || a.customerName || a.customer || '',
            phone: a.customer_whatsapp || a.customer_phone || '',
            serviceId: a.service_id ?? a.serviceId ?? null,
            serviceName: a.service_name || a.serviceName || a.service || '',
            professionalId: a.professional_id ?? a.professionalId ?? a.professional ?? profId,
            professionalName: a.professional_name || a.professionalName || a.professional_nome || '',
            status: a.status || 'pendente',
            date: a.date || date
          }))
          if (mounted) setAppointments(mapped)
          if (mounted) setLoading(false)
          // notify calendar about loaded appointments so it can mark the day
          try { window.dispatchEvent(new CustomEvent('appointmentsLoaded', { detail: { date, count: mapped.length } })) } catch (e) {}
          return
        }

        const url = new URL((window.__API_URL__ || 'http://127.0.0.1:8000') + '/appointments')
        url.searchParams.set('professional_id', profId)
        url.searchParams.set('date', date)

        const apptsRes = await fetch(url.toString(), {
          headers: TOKEN ? { Authorization: 'Bearer ' + TOKEN } : {}
        })

        if (!apptsRes.ok) {
          console.warn('appointments fetch failed', apptsRes.status)
          if(mounted) setAppointments([])
        } else {
          const data = await apptsRes.json()
          // map backend shape to display shape
          const mapped = (Array.isArray(data) ? data : []).map(a => ({
            id: a.id,
            time: a.start_time || a.startTime || '',
            client: a.customer_name || a.customerName || a.customer || '',
            phone: a.customer_whatsapp || a.customer_phone || '',
            serviceId: a.service_id ?? a.serviceId ?? null,
            serviceName: a.service_name || a.serviceName || a.service || '',
            professionalId: a.professional_id ?? a.professionalId ?? a.professional ?? profId,
            professionalName: a.professional_name || a.professionalName || a.professional_nome || '',
            status: a.status || 'pendente',
            date: a.date || date
          }))
          if(mounted) setAppointments(mapped)
          // notify calendar about loaded appointments so it can mark the day
          try { window.dispatchEvent(new CustomEvent('appointmentsLoaded', { detail: { date, count: mapped.length } })) } catch (e) {}
        }
      } catch (e) {
        console.error('failed to load appointments', e)
        if(mounted) setAppointments([])
      } finally {
        if(mounted) setLoading(false)
      }
    }

    load()
    return () => { mounted = false }
  }, [propDate, professionalId])

  function handleAction(action, appt){
    console.log('action', action, 'on', appt)
    // aqui você pode chamar endpoints para confirmar/cancelar, etc.
    const label = action === 'confirm' ? t('agenda_action_confirm') : action === 'info' ? t('agenda_action_info') : t('agenda_action_cancel')
    alert(`${label} - id ${appt.id}`)
  }

  function ClientButton({ name, phone }) {
    return (
      <button
        type="button"
        className="ea-link-plain"
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          if (onOpenClient) onOpenClient({ name, phone: phone || '' })
        }}
        title={t('th_client')}
      >
        {name}
      </button>
    )
  }

  // demo rows when backend returns none
  const demoRows = () => {
    const demo = [
      { id: 'd1', time: '09:00', client: 'Ana Silva', service: 'Corte', prof: 'Marcos', status: 'confirmed' },
      { id: 'd2', time: '10:30', client: 'João Pedro', service: 'Escova', prof: 'Lúcia', status: 'pending' },
      { id: 'd3', time: '11:15', client: 'Maria Fernanda', service: 'Coloração', prof: 'Rafael', status: 'cancelled' },
      { id: 'd4', time: '14:00', client: 'Paulo Costa', service: 'Design de sobrancelha', prof: 'Marcos', status: 'confirmed' }
    ]
    return demo.map((r, i) => {
                    const rowDate = propDate || toLocalISO()
      const isHover = hoverDate && rowDate === hoverDate
      const isSelected = propDate && rowDate === propDate
      return (
        <tr
          key={r.id}
          className={`${i % 2 === 0 ? 'row-even' : 'row-odd'} ${isHover ? 'row-highlight' : ''} ${isSelected ? 'row-selected' : ''}`}
          onMouseEnter={() => onHoverDate && onHoverDate(rowDate)}
          onMouseLeave={() => onHoverDate && onHoverDate(null)}
          onTouchStart={() => onHoverDate && onHoverDate(rowDate)}
          onTouchEnd={() => onHoverDate && onHoverDate(null)}
          onClick={() => onSelectDate && onSelectDate(rowDate)}
        >
          <td>{r.time}</td>
          <td><ClientButton name={r.client} phone={r.phone} /></td>
          <td>{r.serviceLabel || r.service}</td>
          <td>{r.profLabel || r.prof}</td>
          <td><span className={`status-badge ${statusClass(r.status)}`}>{statusLabel(r.status)}</span></td>
        </tr>
      )
    })
  }

  return (
    <div className="agenda-card">
      <div className="agenda-header">
        <div style={{display:'flex',alignItems:'baseline',gap:12,flexWrap:'wrap'}}>
          <h3>{t('agenda')}</h3>
          <div className="ea-agenda-nav" aria-label={t('agenda_day_navigation')}>
            <button
              type="button"
              className="ea-icon-btn"
              onClick={() => onSelectDate && onSelectDate(addDaysISO(propDate || toLocalISO(), -1))}
              title={t('agenda_prev_day')}
              aria-label={t('agenda_prev_day')}
            >
              ‹
            </button>
            <div className="ea-agenda-date" title={propDate ? String(propDate) : ''}>
              {propDate ? formatLocalDate(propDate) : ''}
            </div>
            <button
              type="button"
              className="ea-icon-btn"
              onClick={() => onSelectDate && onSelectDate(addDaysISO(propDate || toLocalISO(), +1))}
              title={t('agenda_next_day')}
              aria-label={t('agenda_next_day')}
            >
              ›
            </button>
          </div>
          {occupancyLabel && (
            <span className={`occ-badge occ-${occupancyLabel.state}`} title={occupancyLabel.detail || occupancyLabel.title}>
              {occupancyLabel.title}{occupancyLabel.detail ? ` · ${occupancyLabel.detail}` : ''}
            </span>
          )}
        </div>
        <div className="ea-status-pills" aria-label="Agenda status filters">
          <button
            type="button"
            className={`ea-status-pill pending ${statusFilter === 'pending' ? 'active' : ''}`}
            onClick={() => toggleFilter('pending')}
            title={`${statusCounts.pending} ${t('status_pending')}`}
          >
            <span className="ea-pill-num">{statusCounts.pending}</span>
            <span className="ea-pill-label">{t('agenda_filter_pending')}</span>
          </button>
          <button
            type="button"
            className={`ea-status-pill confirmed ${statusFilter === 'confirmed' ? 'active' : ''}`}
            onClick={() => toggleFilter('confirmed')}
            title={`${statusCounts.confirmed} ${t('status_confirmed')}`}
          >
            <span className="ea-pill-num">{statusCounts.confirmed}</span>
            <span className="ea-pill-label">{t('agenda_filter_confirmed')}</span>
          </button>
          <button
            type="button"
            className={`ea-status-pill cancelled ${statusFilter === 'cancelled' ? 'active' : ''}`}
            onClick={() => toggleFilter('cancelled')}
            title={`${statusCounts.cancelled} ${t('status_cancelled')}`}
          >
            <span className="ea-pill-num">{statusCounts.cancelled}</span>
            <span className="ea-pill-label">{t('agenda_filter_cancelled')}</span>
          </button>
          <button
            type="button"
            className={`ea-status-pill noshow ${statusFilter === 'noshow' ? 'active' : ''}`}
            onClick={() => toggleFilter('noshow')}
            title={`${statusCounts.noshow} ${t('status_no_show')}`}
          >
            <span className="ea-pill-num">{statusCounts.noshow}</span>
            <span className="ea-pill-label">{t('agenda_filter_no_show')}</span>
          </button>

          <button
            type="button"
            className={`ea-status-pill all ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
            title={t('agenda_filter_all')}
          >
            <span className="ea-pill-label">{t('agenda_filter_all')}</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
          <div className="spinner" aria-hidden="true"></div>
          <div style={{marginLeft:12,color:'#6b7280'}}>{t('agenda_loading')}</div>
        </div>
      ) : (
        <div className="agenda-table agenda-table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('th_time')}</th>
                <th>{t('th_client')}</th>
                <th>{t('th_service')}</th>
                <th>{t('th_prof')}</th>
                <th>{t('th_status')}</th>
              </tr>
            </thead>
            <tbody>
              {appointments.length === 0 && demoRows()}
              {filteredAppointments.map((r, i) => {
                const dateVal = r.date || propDate
                const isHover = hoverDate && dateVal === hoverDate
                const isSelected = propDate && dateVal === propDate
                return (
                  <tr
                    key={r.id || i}
                    className={`${i % 2 === 0 ? 'row-even' : 'row-odd'} ${isHover ? 'row-highlight' : ''} ${isSelected ? 'row-selected' : ''}`}
                    onMouseEnter={() => onHoverDate && onHoverDate(dateVal)}
                    onMouseLeave={() => onHoverDate && onHoverDate(null)}
                    onTouchStart={() => onHoverDate && onHoverDate(dateVal)}
                    onTouchEnd={() => onHoverDate && onHoverDate(null)}
                    onClick={() => onSelectDate && onSelectDate(dateVal)}
                  >
                    <td>{r.time}</td>
                    <td><ClientButton name={r.client} phone={r.phone} /></td>
                    <td>{r.serviceLabel || r.service || ''}</td>
                    <td>{r.profLabel || r.prof || ''}</td>
                    <td><span className={`status-badge ${statusClass(r.status)}`}>{statusLabel(r.status)}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default AgendaTable
