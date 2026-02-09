import React, { useState, useEffect } from 'react'
import '../components/dashboard/dashboard.css'
import Header from '../components/dashboard/Header'
import TopCards from '../components/dashboard/TopCards'
import AgendaTable from '../components/dashboard/AgendaTable'
import MiniCalendar from '../components/dashboard/MiniCalendar'
import BookingShareCard from '../components/dashboard/BookingShareCard'
import { useI18n } from '../i18n'
import { useNavigate } from 'react-router-dom'

const Dashboard = () => {
  const { t } = useI18n()
  const navigate = useNavigate()

  function toLocalISO(d = new Date()){
    const dt = d instanceof Date ? d : new Date(d)
    const y = dt.getFullYear()
    const m = String(dt.getMonth() + 1).padStart(2,'0')
    const day = String(dt.getDate()).padStart(2,'0')
    return `${y}-${m}-${day}`
  }

  const [selectedDate, setSelectedDate] = useState(() => toLocalISO())
  const [hoveredDate, setHoveredDate] = useState(null)
  const [config, setConfig] = useState(null)
  const [selectedProfessionalId, setSelectedProfessionalId] = useState(null)
  const [selectedDayMeta, setSelectedDayMeta] = useState(null)

  function addDaysISO(iso, deltaDays) {
    const d = iso ? new Date(iso) : new Date()
    if (Number.isNaN(d.getTime())) return toLocalISO()
    d.setDate(d.getDate() + (Number(deltaDays) || 0))
    return toLocalISO(d)
  }

  const professionals = (config && Array.isArray(config.professionals)) ? config.professionals : []
  const selectedProfessional = professionals.find((p) => String(p?.id) === String(selectedProfessionalId)) || null
  const businessSlug = config?.business?.slug || config?.business?.business_slug || ''
  const businessName = config?.business?.nome || config?.business?.name || ''

  useEffect(() => {
    let mounted = true
    async function loadCfg(){
      try{
        const res = await fetch((window.__API_URL__ || 'http://127.0.0.1:8000') + '/config')
        if(!res.ok) return
        const data = await res.json()
        if(mounted) setConfig(data)
      }catch(e){console.warn('config load failed', e)}
    }
    loadCfg()
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!config) return
    const firstProfId = config?.professionals?.[0]?.id
    if (selectedProfessionalId == null && firstProfId != null) setSelectedProfessionalId(firstProfId)
  }, [config, selectedProfessionalId])

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="dashboard-top">
          <div style={{ width: '100%' }}>
            <TopCards />
          </div>
        </div>

        <div className="dashboard-content">
            <section className="calendar-column">
            <div className="card-surface">
                <MiniCalendar
                  serviceId={config?.services?.[0]?.id}
                  professionalId={selectedProfessionalId}
                  selectedDate={selectedDate}
                  hoveredDate={hoveredDate}
                  onSelectDate={(d, meta) => {
                    setSelectedDate(d)
                    setSelectedDayMeta(meta || null)
                  }}
                  onHoverDate={(d) => setHoveredDate(d)}
                />
            </div>

            <BookingShareCard slug={businessSlug} businessName={businessName} />

            <div className="card-surface employees-list">
              <h4>{t('staff_team')}</h4>
              {professionals.length === 0 ? (
                <div style={{ color: '#6b7280', fontSize: 13, padding: 10 }}>
                  {t('staff_none')}
                </div>
              ) : (
                <div className="ea-scroll-y" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {professionals.map((p) => {
                    const active = String(p?.id) === String(selectedProfessionalId)
                    const label = p?.name || p?.nome || `#${p?.id}`
                    const initial = String(label || 'P').trim().slice(0, 1).toUpperCase()
                    return (
                      <button
                        key={p.id}
                        type="button"
                        className="employee"
                        onClick={() => setSelectedProfessionalId(p.id)}
                        style={{
                          width: '100%',
                          textAlign: 'left',
                          cursor: 'pointer',
                          background: active ? 'linear-gradient(180deg,#ffffff,#fbfdff)' : '#fff',
                          border: active ? '1px solid rgba(59,130,246,0.22)' : '1px solid #f1f5f9',
                          boxShadow: active ? '0 10px 22px rgba(2,6,23,0.06)' : 'none',
                        }}
                      >
                        <div style={{ width: 40, height: 40, borderRadius: 20, background: active ? '#dbeafe' : '#eef2ff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, color: '#1e3a8a' }}>
                          {initial}
                        </div>
                        <div style={{ marginLeft: 10 }}>
                          <div style={{ fontWeight: 900, color: '#0f1724' }}>{label}</div>
                          <div style={{ fontSize: 12, color: '#6b7280' }}>{active ? t('staff_selected') : t('staff_tap_to_view') }</div>
                        </div>
                        <div style={{ marginLeft: 'auto', color: '#6b7280', fontWeight: 900, fontSize: 12 }}>
                          {active ? '✓' : ''}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </section>

            <section className="agenda-column">
              <AgendaTable
                config={config}
                professionalId={selectedProfessionalId}
                date={selectedDate}
                hoverDate={hoveredDate}
                onHoverDate={(d) => setHoveredDate(d)}
                dayMeta={selectedDayMeta}
                onSelectDate={(d) => {
                  setSelectedDate(d)
                }}
                onOpenClient={({ name }) => {
                  const q = encodeURIComponent(String(name || '').trim())
                  navigate(`/clientes/lista?q=${q}`)
                }}
              />
          </section>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
