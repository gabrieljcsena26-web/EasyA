import React, { useEffect, useMemo, useState } from 'react'
import { useI18n } from '../../i18n'

function monthRange(year, month) {
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)
  return { first, last }
}

function buildGrid(year, month) {
  // returns array of weeks, each week is array of Date or null
  // week starts on Monday for alignment with user's preference
  const { first, last } = monthRange(year, month)
  // convert JS Sunday=0..Saturday=6 to Monday-first (Monday=0..Sunday=6)
  const startWeekDay = (first.getDay() + 6) % 7
  const daysInMonth = last.getDate()
  const cells = []
  // leading blanks
  for (let i = 0; i < startWeekDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d))
  // trailing blanks to complete last week
  while (cells.length % 7 !== 0) cells.push(null)
  const weeks = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
}

const MiniCalendar = ({ serviceId, professionalId, slug, selectedDate, hoveredDate, onSelectDate, onHoverDate }) => {
  const { t, lang } = useI18n()
  const today = selectedDate ? new Date(selectedDate) : new Date()
  function toLocalISO(d = new Date()){
    const dt = d instanceof Date ? d : new Date(d)
    const y = dt.getFullYear()
    const m = String(dt.getMonth() + 1).padStart(2,'0')
    const day = String(dt.getDate()).padStart(2,'0')
    return `${y}-${m}-${day}`
  }
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [statesByDate, setStatesByDate] = useState({})
  const cacheRef = React.useRef({})
  const apiBase = (window.__API_URL__ || 'http://127.0.0.1:8000')

  function fmt(key, vars) {
    let s = t(key)
    for (const [k, v] of Object.entries(vars || {})) {
      s = s.replaceAll(`{${k}}`, String(v))
    }
    return s
  }

  const locale = useMemo(() => {
    // Prefer lang codes that match Intl locales
    if (lang === 'pt-BR') return 'pt-BR'
    if (lang === 'en') return 'en'
    if (lang === 'es') return 'es'
    if (lang === 'fr') return 'fr'
    if (lang === 'ca') return 'ca'
    return undefined
  }, [lang])

  useEffect(() => {
    async function loadOccupancy() {
      try {
        const key = `${year}-${month}`
        if (cacheRef.current[key]) {
          setStatesByDate(cacheRef.current[key])
          return
        }
        const first = new Date(year, month, 1)
        const last = new Date(year, month + 1, 0)
        const from = toLocalISO(first)
        const to = toLocalISO(last)
        const url = new URL(apiBase + '/occupancy')
        url.searchParams.set('from', from)
        url.searchParams.set('to', to)
        url.searchParams.set('service_id', serviceId || 1)
        if (professionalId) url.searchParams.set('professional_id', professionalId)
        if (slug) url.searchParams.set('slug', slug)

        const res = await fetch(url.toString())
        if (!res.ok) return
        const data = await res.json()
        const map = {}
        // backend expected shape: days: [{ date, state, free_slots, total_slots, occupancy_percent }]
        (data.days || []).forEach((d) => {
          // normalize incoming date key to local-ISO to avoid timezone/format mismatches
          const k = toLocalISO(d.date || d)
          map[k] = {
            state: d.state,
            free_slots: Number(d.free_slots ?? d.count ?? 0),
            total_slots: Number(d.total_slots ?? 0),
            occupancy_percent: (d.occupancy_percent == null) ? null : Number(d.occupancy_percent),
          }
        })
        // cache per month
        cacheRef.current[key] = map
        setStatesByDate(map)
      } catch (e) {
        console.error('mini calendar occupancy error', e)
      }
    }
    loadOccupancy()
  }, [year, month, serviceId, professionalId])

  useEffect(() => {
    if (!selectedDate) return
    const d = new Date(selectedDate)
    if (Number.isNaN(d.getTime())) return
    const y = d.getFullYear()
    const m = d.getMonth()
    setYear(y)
    setMonth(m)
  }, [selectedDate])

  const weeks = buildGrid(year, month)

  function handleDayClick(day) {
    if (!day) return
    const iso = toLocalISO(day)
    // default behavior: select date for agenda
    if (onSelectDate) onSelectDate(iso, statesByDate[iso] || null)
  }

  function prevMonth() { setMonth((m) => { if (m === 0) { setYear((y) => y - 1); return 11 } return m - 1 }) }
  function nextMonth() { setMonth((m) => { if (m === 11) { setYear((y) => y + 1); return 0 } return m + 1 }) }

  return (
    <div className="mini-calendar">
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
        <div style={{fontWeight:700}}>{new Date(year, month).toLocaleString(locale, {month: 'long', year: 'numeric'})}</div>
        <div style={{display:'flex',gap:8}}>
          <button className="action-btn" onClick={prevMonth} aria-label={t('cal_prev_month')}>‹</button>
          <button className="action-btn" onClick={nextMonth} aria-label={t('cal_next_month')}>›</button>
        </div>
      </div>
      <div className="weekdays" style={{display:'grid',gridTemplateColumns:'repeat(7,1fr)',color:'#9ca3af',fontSize:12,marginBottom:6}}>
        {[t('weekday_mon_short'), t('weekday_tue_short'), t('weekday_wed_short'), t('weekday_thu_short'), t('weekday_fri_short'), t('weekday_sat_short'), t('weekday_sun_short')]
          .map((w) => <div key={w} style={{textAlign:'center'}}>{w}</div>)}
      </div>
      <div className="days" style={{display:'grid',gridTemplateColumns:'repeat(7,1fr)',gap:8}}>
        {weeks.flat().map((d, i) => {
          if (!d) return <div key={i} className="day empty" aria-hidden="true"></div>
          const iso = toLocalISO(d)
          const info = statesByDate[iso] || { state: 'free', free_slots: 0, total_slots: 0, occupancy_percent: null }
          const state = (info && info.state) ? info.state : 'free'
          const freeSlots = (info && typeof info.free_slots === 'number') ? info.free_slots : 0
          const totalSlots = (info && typeof info.total_slots === 'number') ? info.total_slots : 0
          const occPct = (info && typeof info.occupancy_percent === 'number') ? info.occupancy_percent : null
          const cls = state === 'closed' ? 'day-closed' : state === 'free' ? 'day-low' : state === 'mid' ? 'day-mid' : 'day-high'
          const isSelected = selectedDate === iso
          const isHovered = hoveredDate === iso

          const titleParts = [
            state === 'closed' ? t('occ_closed') : state === 'busy' ? t('occ_busy') : state === 'mid' ? t('occ_mid') : t('occ_free'),
          ]
          if (totalSlots > 0) titleParts.push(fmt('occ_slots_fmt', { free: freeSlots, total: totalSlots }))
          if (occPct != null) titleParts.push(fmt('occ_percent_fmt', { pct: occPct }))

          return (
            <button
              key={i}
              className={`day ${cls} ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''}`}
              onClick={() => handleDayClick(d)}
              onMouseEnter={() => onHoverDate && onHoverDate(iso)}
              onMouseLeave={() => onHoverDate && onHoverDate(null)}
              onTouchStart={() => onHoverDate && onHoverDate(iso)}
              onTouchEnd={() => onHoverDate && onHoverDate(null)}
              onFocus={() => onHoverDate && onHoverDate(iso)}
              onBlur={() => onHoverDate && onHoverDate(null)}
              aria-pressed={isSelected}
              title={titleParts.join('\n')}
            >
              {d.getDate()}
            </button>
          )
        })}
      </div>
      <div className="legend">
        <span><i className="dot green"></i> {t('occ_free')}</span>
        <span><i className="dot yellow"></i> {t('occ_mid')}</span>
        <span><i className="dot red"></i> {t('occ_busy')}</span>
        <span><i className="dot gray"></i> {t('occ_closed')}</span>
      </div>
    </div>
  )
}

export default MiniCalendar
