import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useI18n } from '../i18n'
import './booking.css'

function getApiBase() {
  try {
    if (typeof window !== 'undefined' && window.__API_URL__) return String(window.__API_URL__)
  } catch (_) {}
  // Cloudflare Pages previews sometimes miss build-time env injection.
  // Default to prod API so previews remain functional.
  try {
    const host = (typeof window !== 'undefined' && window.location && window.location.hostname)
      ? String(window.location.hostname)
      : ''
    if (host && /(^|\.)pages\.dev$/i.test(host)) return 'https://api.easy-agenda.com'
  } catch (_) {}

  return 'http://127.0.0.1:8000'
}

function resolveApiHref(apiBase, pathOrUrl) {
  const v = String(pathOrUrl || '').trim()
  if (!v) return ''
  if (/^https?:\/\//i.test(v)) return v
  const base = String(apiBase || '').replace(/\/$/, '')
  if (!base) return v
  if (v.startsWith('/')) return base + v
  return base + '/' + v
}

function toWhatsAppDigits(phone) {
  const raw = String(phone || '')
  const digits = raw.replace(/\D+/g, '')
  return digits
}

function buildWhatsAppLink(phone, message) {
  const digits = toWhatsAppDigits(phone)
  if (!digits) return ''
  const text = String(message || '').trim()
  const qs = text ? `?text=${encodeURIComponent(text)}` : ''
  return `https://wa.me/${digits}${qs}`
}

function safeJsonParse(text) {
  try {
    return JSON.parse(String(text || ''))
  } catch (_) {
    return null
  }
}

function formatCountdown(ms) {
  const v = Number(ms)
  if (!Number.isFinite(v)) return ''
  if (v <= 0) return '00:00:00'
  const totalSeconds = Math.floor(v / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const hh = String(hours).padStart(2, '0')
  const mm = String(minutes).padStart(2, '0')
  const ss = String(seconds).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

function toLocalISO(d = new Date()) {
  const dt = d instanceof Date ? d : new Date(d)
  const y = dt.getFullYear()
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const day = String(dt.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function addDaysISO(iso, days) {
  const base = String(iso || '').trim()
  if (!base) return toLocalISO()
  const dt = new Date(base + 'T00:00:00')
  if (Number.isNaN(dt.getTime())) return base
  dt.setDate(dt.getDate() + Number(days || 0))
  return toLocalISO(dt)
}

function formatDateHuman(lang, iso) {
  const v = String(iso || '').trim()
  if (!v) return '—'
  try {
    return new Intl.DateTimeFormat(lang || undefined, { weekday: 'short', day: '2-digit', month: 'short' }).format(new Date(v + 'T00:00:00'))
  } catch (_) {
    return v
  }
}

function formatDateDM(lang, iso) {
  const v = String(iso || '').trim()
  if (!v) return '—'
  try {
    return new Intl.DateTimeFormat(lang || undefined, { day: '2-digit', month: '2-digit' }).format(new Date(v + 'T00:00:00'))
  } catch (_) {
    return v
  }
}

function formatWeekdayLabel(lang, iso) {
  const v = String(iso || '').trim()
  if (!v) return '—'
  const locale = String(lang || '').trim() || undefined
  try {
    const dt = new Date(v + 'T00:00:00')
    let weekday = new Intl.DateTimeFormat(locale, { weekday: 'long' }).format(dt)
    if ((lang || '').toLowerCase().startsWith('pt')) {
      weekday = weekday.replace(/-feira\b/gi, '').trim()
      weekday = weekday.toLowerCase()
    }
    return weekday
  } catch (_) {
    return v
  }
}

function formatDateCompact(lang, iso) {
  const wd = formatWeekdayLabel(lang, iso)
  const dm = formatDateDM(lang, iso)
  if (!wd || wd === '—') return dm
  return `${wd}, ${dm}`
}

function getInitials(name) {
  const parts = String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  if (!parts.length) return 'EA'
  const first = parts[0]?.[0] || ''
  const last = (parts.length > 1 ? parts[parts.length - 1]?.[0] : '') || ''
  return (first + last).toUpperCase() || 'EA'
}

function Modal({ open, title, children, onClose, footer, maxWidth }) {
  if (!open) return null
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="ea-modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        zIndex: 9999,
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="ea-modal-card"
        style={{
          width: '100%',
          maxWidth: Number.isFinite(Number(maxWidth)) ? Number(maxWidth) : 560,
          borderRadius: 16,
          boxShadow: '0 20px 60px rgba(0,0,0,0.28)',
          overflow: 'hidden',
        }}
      >
        <div className="ea-modal-header" style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <div className="ea-modal-title" style={{ fontWeight: 950 }}>{title}</div>
          <button
            type="button"
            onClick={onClose}
            className="ea-pill ea-pill--ghost"
          >
            ✕
          </button>
        </div>
        <div className="ea-modal-body" style={{ padding: 16, lineHeight: 1.55 }}>{children}</div>
        {footer ? (
          <div className="ea-modal-footer" style={{ padding: 16, display: 'flex', justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function AccordionSection({ sectionKey, title, summary, disabled, children, refEl, openSection, setOpenSection }) {
  const open = openSection === sectionKey
  const bodyId = `booking2-acc-${String(sectionKey)}`
  return (
    <section className={`booking2-acc ${open ? 'open' : ''} ${disabled ? 'disabled' : ''}`} ref={refEl || undefined}>
      <button
        type="button"
        className="booking2-acc-head"
        onClick={() => {
          if (disabled) return
          setOpenSection(sectionKey)
        }}
        aria-expanded={open}
        aria-controls={bodyId}
        disabled={disabled}
      >
        <div style={{ minWidth: 0 }}>
          <div className="booking2-acc-title">{title}</div>
          {summary ? <div className="booking2-acc-summary">{summary}</div> : null}
        </div>
        <div className="booking2-acc-chev" aria-hidden="true">{open ? '▾' : '▸'}</div>
      </button>
      <div id={bodyId} className="booking2-acc-body" aria-hidden={!open}>
        <div className="booking2-acc-inner">{children}</div>
      </div>
    </section>
  )
}

function formatMoney(lang, cents, currency) {
  const n = Number(cents)
  if (!Number.isFinite(n)) return ''
  const value = n / 100
  try {
    if (currency) {
      return new Intl.NumberFormat(lang || undefined, { style: 'currency', currency: String(currency) }).format(value)
    }
    return new Intl.NumberFormat(lang || undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)
  } catch (_) {
    return value.toFixed(2)
  }
}

function normalizePhotoUrls(text) {
  const raw = String(text || '')
  return raw
    .split(/\r?\n/)
    .map((s) => String(s || '').trim())
    .filter(Boolean)
}

const FALLBACK_BOOKING_CONFIG = {
  services: [
    { id: 1, name: 'Corte feminino', duration_min: 60, buffer_min: 15, price_cents: 4500, display_interval_min: 30 },
    { id: 2, name: 'Coloração', duration_min: 90, buffer_min: 15, price_cents: 7500, display_interval_min: 30 },
    { id: 3, name: 'Manicure', duration_min: 45, buffer_min: 15, price_cents: 3000, display_interval_min: 30 },
  ],
  professionals: [
    { id: 2, name: 'Ana' },
    { id: 3, name: 'Júlia' },
    { id: 4, name: 'Pedro' },
  ],
  business: {
    id: 0,
    nome: 'Ana Beleza · Madrid',
    telefone: '+34 600 000 000',
    slug: 'ana-beleza-madrid',
    email: 'ana@example.com',
    idioma_padrao: 'pt-BR',
    horario_inicio: 9,
    horario_fim: 18,
    photos: [],
    reviews: [],
  },
}

function ensureMinimumBookingConfig(raw) {
  const cfg = (raw && typeof raw === 'object') ? raw : {}
  const servicesIn = Array.isArray(cfg.services) ? cfg.services : []
  const prosIn = Array.isArray(cfg.professionals) ? cfg.professionals : []

  const mergeById = (primary, fallback, minCount) => {
    const out = []
    const seen = new Set()
    ;(primary || []).forEach((it) => {
      const id = String(it?.id ?? '').trim()
      out.push(it)
      if (id) seen.add(id)
    })
    ;(fallback || []).forEach((it) => {
      if (out.length >= minCount) return
      const id = String(it?.id ?? '').trim()
      if (id && seen.has(id)) return
      out.push(it)
      if (id) seen.add(id)
    })
    return out
  }

  const services = mergeById(servicesIn, FALLBACK_BOOKING_CONFIG.services, 3)
  const professionals = mergeById(prosIn, FALLBACK_BOOKING_CONFIG.professionals, 3)

  return {
    ...FALLBACK_BOOKING_CONFIG,
    ...cfg,
    services,
    professionals,
    business: (cfg.business && typeof cfg.business === 'object')
      ? { ...FALLBACK_BOOKING_CONFIG.business, ...cfg.business }
      : FALLBACK_BOOKING_CONFIG.business,
  }
}

export default function Booking() {
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const params = useParams()
  const routeSlug = params && params.slug ? String(params.slug) : ''
  const [searchParams] = useSearchParams()
  const slugOverride = searchParams.get('slug')
  const timeSectionRef = useRef(null)
  const serviceSectionRef = useRef(null)
  const professionalSectionRef = useRef(null)
  const dateSectionRef = useRef(null)
  const contactSectionRef = useRef(null)

  const routeSlugLooksLikePlaceholder = useMemo(() => {
    const v = String(routeSlug || '').trim().toLowerCase()
    if (!v) return false
    return v === 'seu_slug' || v === 'seu-slug' || v === 'your_slug' || v === 'your-slug'
  }, [routeSlug])

  const effectiveSlug = useMemo(() => {
    const fromOverride = String(slugOverride || '').trim()
    if (fromOverride) return fromOverride
    const fromRoute = routeSlugLooksLikePlaceholder ? '' : String(routeSlug || '').trim()
    return fromRoute
  }, [routeSlug, slugOverride, routeSlugLooksLikePlaceholder])

  const apiBase = useMemo(() => getApiBase().replace(/\/$/, ''), [])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [cfg, setCfg] = useState(null)

  // If the route doesn't provide a slug (e.g. user opens /booking), fall back to the loaded config slug.
  // This keeps the public booking page working in local dev without requiring the slug in the URL.
  const apiSlug = useMemo(() => {
    const bslug = cfg && cfg.business && (cfg.business.slug || cfg.business.business_slug) ? String(cfg.business.slug || cfg.business.business_slug) : ''
    const resolved = String(bslug || '').trim()
    if (resolved) return resolved
    return String(effectiveSlug || '').trim()
  }, [effectiveSlug, cfg])

  const slugLooksLikePlaceholder = routeSlugLooksLikePlaceholder

  useEffect(() => {
    // When user opens /booking (no slug) or /booking/SEU_SLUG, rewrite to the resolved slug.
    // This makes the URL shareable and avoids future slug mismatches.
    if (!apiSlug) return
    if (slugOverride) return
    const current = String(routeSlug || '').trim()
    if (current && !routeSlugLooksLikePlaceholder) return
    navigate(`/booking/${encodeURIComponent(apiSlug)}`, { replace: true })
  }, [apiSlug, navigate, routeSlug, slugOverride, routeSlugLooksLikePlaceholder])

  const services = (cfg && Array.isArray(cfg.services)) ? cfg.services : []
  const professionals = (cfg && Array.isArray(cfg.professionals)) ? cfg.professionals : []
  const business = (cfg && cfg.business) ? cfg.business : null

  const [serviceId, setServiceId] = useState('')
  const [professionalId, setProfessionalId] = useState('') // empty = any
  const [selectedDate, setSelectedDate] = useState(() => toLocalISO())
  // Default: today + 5 days (6-day window). Keep it small to avoid excessive requests.
  const [dateRangeDays, setDateRangeDays] = useState(6)
  const [showAllAvailableDates, setShowAllAvailableDates] = useState(false)
  const [professionalPreviewDays] = useState(5)
  const [professionalDaysLoading, setProfessionalDaysLoading] = useState(false)
  const [professionalDaysById, setProfessionalDaysById] = useState(() => ({}))
  const [availableDatesLoading, setAvailableDatesLoading] = useState(false)
  const [availableDates, setAvailableDates] = useState(() => ({}))
  const [availability, setAvailability] = useState(null)
  const [availabilityLoading, setAvailabilityLoading] = useState(false)
  const [slot, setSlot] = useState('')
  const [slotProfessionalId, setSlotProfessionalId] = useState('')

  const [successModalOpen, setSuccessModalOpen] = useState(false)
  const [successCopied, setSuccessCopied] = useState(false)
  const [countdownNow, setCountdownNow] = useState(() => Date.now())

  const SECTION = useMemo(() => {
    return {
      SERVICE: 'service',
      PROFESSIONAL: 'professional',
      DATE: 'date',
      TIME: 'time',
      CONTACT: 'contact',
    }
  }, [])
  const [openSection, setOpenSection] = useState('service')

  useEffect(() => {
    const order = {
      service: 0,
      professional: 1,
      date: 2,
      time: 3,
      contact: 4,
    }
    const prev = (window.__ea_prev_open_section__ || 'service')
    const prevIdx = Number.isFinite(order[prev]) ? order[prev] : 0
    const nextIdx = Number.isFinite(order[openSection]) ? order[openSection] : 0
    window.__ea_prev_open_section__ = openSection

    // Only auto-scroll when moving forward in the flow.
    if (nextIdx <= prevIdx) return

    const getTarget = () => {
      if (openSection === 'service') return serviceSectionRef.current
      if (openSection === 'professional') return professionalSectionRef.current
      if (openSection === 'date') return dateSectionRef.current
      if (openSection === 'time') return timeSectionRef.current
      if (openSection === 'contact') return contactSectionRef.current
      return null
    }
    try {
      window.setTimeout(() => getTarget()?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }), 60)
    } catch (_) {}
  }, [openSection])

  const [showAllServices, setShowAllServices] = useState(false)
  const [showAllProfessionals, setShowAllProfessionals] = useState(false)

  const [customerName, setCustomerName] = useState('')
  const [customerWhatsapp, setCustomerWhatsapp] = useState('')

  useEffect(() => {
    if (!effectiveSlug) return
    try {
      const keyName = `ea_customer_name_${effectiveSlug}`
      const keyPhone = `ea_customer_whatsapp_${effectiveSlug}`
      const storedName = String(window.localStorage.getItem(keyName) || '').trim()
      const storedPhone = String(window.localStorage.getItem(keyPhone) || '').trim()
      if (!String(customerName || '').trim() && storedName) setCustomerName(storedName)
      if (!String(customerWhatsapp || '').trim() && storedPhone) setCustomerWhatsapp(storedPhone)
    } catch (_) {}
    // Only when slug changes; don't re-apply over user typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveSlug])

  useEffect(() => {
    if (!effectiveSlug) return
    try {
      const keyName = `ea_customer_name_${effectiveSlug}`
      const keyPhone = `ea_customer_whatsapp_${effectiveSlug}`
      const name = String(customerName || '').trim()
      const phone = String(customerWhatsapp || '').trim()
      if (name) window.localStorage.setItem(keyName, name)
      if (phone) window.localStorage.setItem(keyPhone, phone)
    } catch (_) {}
  }, [effectiveSlug, customerName, customerWhatsapp])

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [success, setSuccess] = useState(null)

  const [confirmOpen, setConfirmOpen] = useState(false)

  const depositRule = cfg && cfg.deposit_rule ? cfg.deposit_rule : null
  const policyText = depositRule && depositRule.enabled ? String(depositRule.popup_text || '').trim() : ''

  const photos = (business && Array.isArray(business.photos)) ? business.photos : []
  const [heroIdx, setHeroIdx] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setCfg(null)
    setSuccess(null)
    setSubmitError(null)

    const trySlugs = []
    if (effectiveSlug) trySlugs.push(effectiveSlug)
    // Common local dev slugs
    trySlugs.push('dev')
    trySlugs.push(String(FALLBACK_BOOKING_CONFIG?.business?.slug || '').trim())
    const uniqueSlugs = Array.from(new Set(trySlugs.filter(Boolean)))

    ;(async () => {
      try {
        let res = null
        // If we have a slug (or a fallback), try it first; backend requires a configured estabelecimento.
        for (const s of uniqueSlugs) {
          const u = new URL(apiBase + '/config')
          u.searchParams.set('slug', s)
          // eslint-disable-next-line no-await-in-loop
          const r = await fetch(u.toString(), { method: 'GET' })
          if (r.ok) {
            res = r
            break
          }
        }
        if (!res) {
          // Last resort: old behavior (may return 400 if no establishment exists)
          const u = new URL(apiBase + '/config')
          res = await fetch(u.toString(), { method: 'GET' })
        }

        if (!res.ok) throw new Error('HTTP ' + res.status)
        const json = ensureMinimumBookingConfig(await res.json())
        if (cancelled) return
        setCfg(json)

        const firstService = json && Array.isArray(json.services) && json.services.length ? String(json.services[0].id) : ''
        const firstProf = json && Array.isArray(json.professionals) && json.professionals.length ? String(json.professionals[0].id) : ''
        setServiceId(firstService)
        setProfessionalId('')
        setSlot('')
        setSlotProfessionalId(firstProf)
        setShowAllServices(false)
        setShowAllProfessionals(false)

        const ph = (json && json.business && Array.isArray(json.business.photos)) ? json.business.photos : []
        setHeroIdx(0)
        void ph

        setLoading(false)
      } catch (e) {
        if (cancelled) return
        const json = ensureMinimumBookingConfig(null)
        setCfg(json)
        const firstService = json && Array.isArray(json.services) && json.services.length ? String(json.services[0].id) : ''
        const firstProf = json && Array.isArray(json.professionals) && json.professionals.length ? String(json.professionals[0].id) : ''
        setServiceId(firstService)
        setProfessionalId('')
        setSlot('')
        setSlotProfessionalId(firstProf)
        setShowAllServices(false)
        setShowAllProfessionals(false)
        setHeroIdx(0)
        setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [apiBase, effectiveSlug])

  useEffect(() => {
    let cancelled = false
    setAvailability(null)
    setSubmitError(null)

    const sid = String(serviceId || '').trim()
    if (!sid) return
    if (!selectedDate) return

    setAvailabilityLoading(true)

    const url = new URL(apiBase + '/availability')
    url.searchParams.set('date', selectedDate)
    url.searchParams.set('service_id', sid)
    if (apiSlug) url.searchParams.set('slug', apiSlug)
    // Always fetch full availability so we can show professionals + slots together.

    ;(async () => {
      try {
        const res = await fetch(url.toString(), { method: 'GET' })
        if (!res.ok) throw new Error('HTTP ' + res.status)
        const json = await res.json()
        if (cancelled) return
        setAvailability(json)

        // if slot is no longer valid, clear it
        try {
          const allSlots = []
          ;(json.availability || []).forEach((it) => {
            ;(it.slots || []).forEach((s) => allSlots.push({ time: String(s), professional_id: String(it.professional_id) }))
          })
          const stillOk = allSlots.some((s) => s.time === String(slot) && String(s.professional_id) === String(slotProfessionalId))
          if (!stillOk) {
            setSlot('')
          }
        } catch (_) {}

        setAvailabilityLoading(false)
      } catch (e) {
        if (cancelled) return
        setAvailability(null)
        setAvailabilityLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [apiBase, apiSlug, selectedDate, serviceId])

  const availabilityByProfessional = useMemo(() => {
    const map = new Map()
    if (!availability || !Array.isArray(availability.availability)) return map
    availability.availability.forEach((it) => {
      const pid = String(it?.professional_id || '')
      if (!pid) return
      const slots = Array.isArray(it.slots) ? it.slots.map(String) : []
      map.set(pid, {
        professional_id: pid,
        professional_name: String(it?.professional_name || ''),
        slots,
      })
    })
    return map
  }, [availability])

  const professionalsForSelectedDay = useMemo(() => {
    const fromAvailability = availabilityByProfessional.size
      ? Array.from(availabilityByProfessional.values())
          .map((it) => ({ id: it.professional_id, name: it.professional_name, slots: it.slots }))
          .filter((p) => p.id)
          .sort((a, b) => (b.slots?.length || 0) - (a.slots?.length || 0))
      : []

    const seen = new Set(fromAvailability.map((p) => String(p.id)))
    const extras = (professionals || [])
      .map((p) => ({ id: String(p?.id || ''), name: String(p?.name || p?.nome || ''), slots: [] }))
      .filter((p) => p.id && !seen.has(String(p.id)))

    // If we have availability, show available first then extras (disabled).
    // If we don't, just show all from config.
    return fromAvailability.length ? [...fromAvailability, ...extras] : extras
  }, [availabilityByProfessional, professionals])

  const selectedProfSlots = useMemo(() => {
    if (!professionalId) return null
    const it = availabilityByProfessional.get(String(professionalId))
    return it ? it.slots : []
  }, [availabilityByProfessional, professionalId])

  const selectedService = services.find((s) => String(s?.id) === String(serviceId)) || null
  const selectedProfessional = professionals.find((p) => String(p?.id) === String(professionalId)) || null
  const selectedSlotProfessional = professionals.find((p) => String(p?.id) === String(slotProfessionalId)) || null

  const allowedProfessionalIdsForService = useMemo(() => {
    const sid = String(serviceId || '').trim()
    if (!sid) return null

    const svc = selectedService
    const set = new Set()
    const addFromArray = (arr) => {
      ;(Array.isArray(arr) ? arr : []).forEach((v) => {
        if (v == null) return
        if (typeof v === 'string' || typeof v === 'number') {
          const s = String(v).trim()
          if (s) set.add(s)
          return
        }
        if (typeof v === 'object' && v) {
          const id = String(v.id || v.professional_id || v.profissional_id || '').trim()
          if (id) set.add(id)
        }
      })
    }

    if (svc && typeof svc === 'object') {
      addFromArray(svc.professional_ids)
      addFromArray(svc.professionalIds)
      addFromArray(svc.profissionais)
      addFromArray(svc.professionals)
      addFromArray(svc.staff_ids)
      addFromArray(svc.staffIds)
    }

    if (set.size) return set

    // Reverse mapping: check professionals for declared service ids.
    ;(professionals || []).forEach((p) => {
      if (!p || typeof p !== 'object') return
      const pid = String(p.id || p.professional_id || p.profissional_id || '').trim()
      if (!pid) return
      const serviceIds = []
      const arrCandidates = [p.service_ids, p.serviceIds, p.services, p.servicos]
      arrCandidates.forEach((arr) => {
        ;(Array.isArray(arr) ? arr : []).forEach((v) => {
          if (v == null) return
          if (typeof v === 'string' || typeof v === 'number') {
            const s = String(v).trim()
            if (s) serviceIds.push(s)
            return
          }
          if (typeof v === 'object' && v) {
            const id = String(v.id || v.service_id || v.servico_id || '').trim()
            if (id) serviceIds.push(id)
          }
        })
      })
      if (serviceIds.some((x) => String(x) === sid)) set.add(pid)
    })

    return set.size ? set : null
  }, [professionals, selectedService, serviceId])

  const eligibleProfessionalsForService = useMemo(() => {
    const base = Array.isArray(professionals) ? professionals : []
    const filtered = !allowedProfessionalIdsForService
      ? base
      : base.filter((p) => allowedProfessionalIdsForService.has(String(p?.id)))

    return filtered
  }, [professionals, allowedProfessionalIdsForService])

  useEffect(() => {
    let cancelled = false

    const sid = String(serviceId || '').trim()
    if (!sid) {
      setProfessionalDaysLoading(false)
      setProfessionalDaysById({})
      return () => {
        cancelled = true
      }
    }

    // Only compute preview for a small set unless user expands the list.
    const profs = showAllProfessionals
      ? eligibleProfessionalsForService
      : eligibleProfessionalsForService.slice(0, 6)
    if (!profs.length) {
      setProfessionalDaysLoading(false)
      setProfessionalDaysById({})
      return () => {
        cancelled = true
      }
    }

    const fetchWithTimeout = async (url, ms) => {
      const controller = new AbortController()
      const t = window.setTimeout(() => controller.abort(), Math.max(1000, Number(ms) || 8000))
      try {
        return await fetch(url, { method: 'GET', signal: controller.signal })
      } finally {
        window.clearTimeout(t)
      }
    }

    const fromDate = toLocalISO()
    const toDate = addDaysISO(fromDate, Math.max(1, Number(professionalPreviewDays) || 5) - 1)

    setProfessionalDaysLoading(true)
    setProfessionalDaysById({})

    ;(async () => {
      try {
        const results = {}
        const pids = profs.map((p) => String(p?.id)).filter(Boolean)
        let cursor = 0
        const workerCount = 4
        const workers = Array.from({ length: Math.min(workerCount, pids.length) }, () => (async () => {
          while (cursor < pids.length) {
            const idx = cursor
            cursor += 1
            const pid = pids[idx]
            try {
              const url = new URL(apiBase + '/occupancy')
              url.searchParams.set('from', fromDate)
              url.searchParams.set('to', toDate)
              url.searchParams.set('service_id', sid)
              url.searchParams.set('professional_id', pid)
              if (apiSlug) url.searchParams.set('slug', apiSlug)

              const res = await fetchWithTimeout(url.toString(), 8000)
              if (!res.ok) throw new Error('HTTP ' + res.status)
              const json = await res.json().catch(() => null)
              const days = (json && Array.isArray(json.days)) ? json.days : []
              const freeDays = days.filter((d) => Number(d?.free_slots || 0) > 0).length
              const next = (days.find((d) => Number(d?.free_slots || 0) > 0)?.date) || ''
              results[pid] = { freeDays, nextDate: next }
            } catch (_) {
              // Unknown => don't disable the professional, just omit the info.
              results[pid] = null
            }
          }
        })())

        await Promise.all(workers)
        if (cancelled) return
        setProfessionalDaysById(results)
        setProfessionalDaysLoading(false)
      } catch (_) {
        if (cancelled) return
        setProfessionalDaysById({})
        setProfessionalDaysLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [apiBase, apiSlug, serviceId, eligibleProfessionalsForService, professionalPreviewDays, showAllProfessionals])

  useEffect(() => {
    // Keep the selected professional even if they aren't available on the currently selected day.
    // The Date step will show the professional-specific available days and auto-pick the first one.
    if (!professionalId) return
    const stillExists = (professionals || []).some((p) => String(p?.id) === String(professionalId))
    if (stillExists) return
    setProfessionalId('')
    setSlot('')
  }, [professionals, professionalId])

  const heroUrl = photos && photos.length ? String(photos[Math.min(heroIdx, photos.length - 1)] || '') : ''
  const currency = business && (business.currency || business.moeda) ? (business.currency || business.moeda) : null

  const businessName = (business && (business.nome || business.name)) ? String(business.nome || business.name) : t('booking_title')
  const businessPhone = (business && business.telefone) ? String(business.telefone) : ''
  const businessEmail = (business && business.email) ? String(business.email) : ''
  const startHour = (business && Number.isFinite(Number(business.horario_inicio))) ? Number(business.horario_inicio) : null
  const endHour = (business && Number.isFinite(Number(business.horario_fim))) ? Number(business.horario_fim) : null
  const hoursLabel = (startHour !== null && endHour !== null) ? `${String(startHour).padStart(2, '0')}:00–${String(endHour).padStart(2, '0')}:00` : ''

  const canSubmit = Boolean(serviceId && selectedDate && slot && slotProfessionalId && customerName.trim() && customerWhatsapp.trim()) && !submitting

  const successAppointment = success && success.appointment ? success.appointment : null

  const successSummaryText = useMemo(() => {
    if (!success) return ''
    const serviceName = selectedService ? String(selectedService.name || '').trim() : ''
    const professionalName = selectedSlotProfessional
      ? String(selectedSlotProfessional.name || selectedSlotProfessional.nome || '').trim()
      : (selectedProfessional ? String(selectedProfessional.name || selectedProfessional.nome || '').trim() : '')
    const apptDate = successAppointment && successAppointment.date ? String(successAppointment.date) : ''
    const apptTime = successAppointment && successAppointment.start_time ? String(successAppointment.start_time) : ''
    const when = (apptDate && apptTime)
      ? `${formatDateCompact(lang, apptDate)} ${apptTime}`.trim()
      : (selectedDate ? `${formatDateCompact(lang, selectedDate)} ${slot || ''}`.trim() : '')
    const phone = businessPhone ? `\n${t('booking_contact_label')}: ${businessPhone}` : ''
    return [
      businessName,
      serviceName ? `${t('booking_summary_service')}: ${serviceName}` : '',
      professionalName ? `${t('booking_summary_professional')}: ${professionalName}` : '',
      when ? `${t('booking_summary_date')}: ${when}` : '',
      `${t('booking_customer_name')}: ${String(customerName || '').trim()}`,
      `${t('booking_customer_whatsapp')}: ${String(customerWhatsapp || '').trim()}`,
    ]
      .filter(Boolean)
      .join('\n')
      .trim() + phone
  }, [
    success,
    successAppointment,
    selectedService,
    selectedSlotProfessional,
    selectedProfessional,
    selectedDate,
    slot,
    lang,
    businessName,
    businessPhone,
    customerName,
    customerWhatsapp,
    t,
  ])

  async function createAppointment() {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const url = new URL(apiBase + '/appointments')
      if (apiSlug) url.searchParams.set('slug', apiSlug)

      const payload = {
        service_id: Number(serviceId),
        professional_id: Number(slotProfessionalId || professionalId),
        date: selectedDate,
        start_time: slot,
        channel: 'booking_public',
        customer_name: String(customerName || '').trim(),
        customer_whatsapp: String(customerWhatsapp || '').trim(),
      }

      const res = await fetch(url.toString(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const json = await res.json().catch(() => null)
      if (!res.ok) {
        const detail = (json && (json.detail || json.message)) ? String(json.detail || json.message) : 'HTTP ' + res.status
        throw new Error(detail)
      }

      const nextSuccess = {
        ok: true,
        appointment: json && json.appointment ? json.appointment : null,
        calendar_url: json && (json.calendar_url || json.calendarUrl) ? (json.calendar_url || json.calendarUrl) : null,
        send_at: json && (json.send_at || json.sendAt) ? (json.send_at || json.sendAt) : null,
        confirm_by: json && (json.confirm_by || json.confirmBy) ? (json.confirm_by || json.confirmBy) : null,
      }

      setSuccess(nextSuccess)
      setConfirmOpen(false)
      setSuccessCopied(false)
      setSuccessModalOpen(true)

      try {
        if (apiSlug) {
          const key = `ea_last_booking_${apiSlug}`
          window.localStorage.setItem(key, JSON.stringify({ ...nextSuccess, saved_at: new Date().toISOString() }))
        }
      } catch (_) {}
    } catch (e) {
      setSubmitError(String(e && e.message ? e.message : t('booking_submit_error')))
    } finally {
      setSubmitting(false)
    }
  }

  // Restore last pending booking (same device/browser) if user leaves and returns.
  useEffect(() => {
    if (!apiSlug) return
    if (success) return
    try {
      const key = `ea_last_booking_${apiSlug}`
      const raw = window.localStorage.getItem(key)
      const parsed = safeJsonParse(raw)
      if (!parsed || typeof parsed !== 'object') return

      const confirmBy = parsed.confirm_by ? new Date(String(parsed.confirm_by)) : null
      if (!confirmBy || Number.isNaN(confirmBy.getTime())) return
      if (confirmBy.getTime() <= Date.now()) return

      setSuccess(parsed)
    } catch (_) {}
  }, [apiSlug, success])

  useEffect(() => {
    if (!successModalOpen) return
    const id = window.setInterval(() => setCountdownNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [successModalOpen])

  const confirmByLocal = useMemo(() => {
    const v = success && success.confirm_by ? String(success.confirm_by) : ''
    if (!v) return null
    const dt = new Date(v)
    if (Number.isNaN(dt.getTime())) return null
    return dt
  }, [success])

  const sendAtLocal = useMemo(() => {
    const v = success && success.send_at ? String(success.send_at) : ''
    if (!v) return null
    const dt = new Date(v)
    if (Number.isNaN(dt.getTime())) return null
    return dt
  }, [success])

  const countdownMs = useMemo(() => {
    if (!confirmByLocal) return null
    return confirmByLocal.getTime() - countdownNow
  }, [confirmByLocal, countdownNow])

  const confirmDeadlineSoon = useMemo(() => {
    if (!confirmByLocal) return false
    const diff = confirmByLocal.getTime() - Date.now()
    return Number.isFinite(diff) && diff > 0 && diff <= 6 * 60 * 60 * 1000
  }, [confirmByLocal])

  const appointmentStartLocal = useMemo(() => {
    const dateStr = successAppointment && successAppointment.date ? String(successAppointment.date) : ''
    const timeStr = successAppointment && successAppointment.start_time ? String(successAppointment.start_time) : ''
    if (!dateStr || !timeStr) return null
    const dt = new Date(`${dateStr}T${timeStr}:00`)
    if (Number.isNaN(dt.getTime())) return null
    return dt
  }, [successAppointment])

  const isImmediateConfirmWindow = useMemo(() => {
    if (!appointmentStartLocal) return false
    const now = new Date()
    const diffMs = appointmentStartLocal.getTime() - now.getTime()
    if (!Number.isFinite(diffMs)) return false
    // <= 24h
    return diffMs > 0 && diffMs <= 24 * 60 * 60 * 1000
  }, [appointmentStartLocal])

  const appointmentWhenText = useMemo(() => {
    const dateStr = successAppointment && successAppointment.date ? String(successAppointment.date) : ''
    const timeStr = successAppointment && successAppointment.start_time ? String(successAppointment.start_time) : ''
    if (!dateStr || !timeStr) return ''
    return `${formatDateCompact(lang, dateStr)} ${timeStr}`.trim()
  }, [successAppointment, lang])

  const successPrimaryMessage = useMemo(() => {
    if (!appointmentWhenText) return ''
    // Assertive message (no "if") tuned by confirmation urgency.
    if (confirmDeadlineSoon && confirmByLocal) {
      return `Seu horário está marcado para ${appointmentWhenText}. Confirme pelo WhatsApp até ${confirmByLocal.toLocaleTimeString(lang || undefined, { hour: '2-digit', minute: '2-digit' })} para garantir.`
    }
    if (isImmediateConfirmWindow) {
      return `Seu horário está marcado para ${appointmentWhenText}. Confirme agora no WhatsApp para garantir.`
    }
    return `Seu horário está marcado para ${appointmentWhenText}. Clique em “Adicionar ao calendário” para receber um lembrete e não esquecer de confirmar.`
  }, [appointmentWhenText, isImmediateConfirmWindow, confirmDeadlineSoon, confirmByLocal, lang])

  const bookingCode = useMemo(() => {
    const id = successAppointment && (successAppointment.id ?? null)
    if (id === null || id === undefined) return ''
    const n = Number(id)
    if (!Number.isFinite(n)) return ''
    return `EA-${Math.trunc(n)}`
  }, [successAppointment])

  const whatsAppConfirmLink = useMemo(() => {
    if (!businessPhone || !successAppointment) return ''
    const serviceName = selectedService ? String(selectedService.name || '').trim() : ''
    const professionalName = selectedSlotProfessional
      ? String(selectedSlotProfessional.name || selectedSlotProfessional.nome || '').trim()
      : (selectedProfessional ? String(selectedProfessional.name || selectedProfessional.nome || '').trim() : '')
    const when = (successAppointment.date && successAppointment.start_time)
      ? `${formatDateCompact(lang, String(successAppointment.date))} ${String(successAppointment.start_time)}`
      : (selectedDate && slot ? `${formatDateCompact(lang, selectedDate)} ${slot}`.trim() : '')

    const lines = [
      t('booking_whatsapp_msg_hi'),
      bookingCode ? `${t('booking_whatsapp_msg_code')}: ${bookingCode}` : '',
      serviceName ? `${t('booking_summary_service')}: ${serviceName}` : '',
      professionalName ? `${t('booking_summary_professional')}: ${professionalName}` : '',
      when ? `${t('booking_summary_date')}: ${when}` : '',
      customerName ? `${t('booking_customer_name')}: ${String(customerName).trim()}` : '',
      customerWhatsapp ? `${t('booking_customer_whatsapp')}: ${String(customerWhatsapp).trim()}` : '',
      '',
      t('booking_whatsapp_msg_actions'),
    ]
      .filter(Boolean)
      .join('\n')

    return buildWhatsAppLink(businessPhone, lines)
  }, [
    businessPhone,
    successAppointment,
    selectedService,
    selectedSlotProfessional,
    selectedProfessional,
    selectedDate,
    slot,
    lang,
    customerName,
    customerWhatsapp,
    bookingCode,
    t,
  ])

  const whatsAppPreConfirmLink = useMemo(() => {
    if (!businessPhone) return ''
    if (!serviceId || !selectedDate || !slot) return ''
    const serviceName = selectedService ? String(selectedService.name || '').trim() : ''
    const professionalName = selectedSlotProfessional
      ? String(selectedSlotProfessional.name || selectedSlotProfessional.nome || '').trim()
      : (selectedProfessional ? String(selectedProfessional.name || selectedProfessional.nome || '').trim() : '')
    const when = `${formatDateCompact(lang, selectedDate)} ${slot}`.trim()
    const lines = [
      t('booking_whatsapp_msg_hi'),
      serviceName ? `${t('booking_summary_service')}: ${serviceName}` : '',
      professionalName ? `${t('booking_summary_professional')}: ${professionalName}` : '',
      when ? `${t('booking_summary_date')}: ${when}` : '',
      customerName ? `${t('booking_customer_name')}: ${String(customerName).trim()}` : '',
      customerWhatsapp ? `${t('booking_customer_whatsapp')}: ${String(customerWhatsapp).trim()}` : '',
      '',
      t('booking_whatsapp_msg_actions'),
    ]
      .filter(Boolean)
      .join('\n')
    return buildWhatsAppLink(businessPhone, lines)
  }, [
    businessPhone,
    serviceId,
    selectedDate,
    slot,
    selectedService,
    selectedSlotProfessional,
    selectedProfessional,
    lang,
    customerName,
    customerWhatsapp,
    t,
  ])

  const dateChoices = useMemo(() => {
    const base = toLocalISO()
    const n = Math.max(6, Math.min(60, Number(dateRangeDays) || 6))
    return Array.from({ length: n }, (_, idx) => addDaysISO(base, idx))
  }, [dateRangeDays])

  useEffect(() => {
    let cancelled = false

    const sid = String(serviceId || '').trim()
    if (!sid) {
      setAvailableDates({})
      setAvailableDatesLoading(false)
      return () => {
        cancelled = true
      }
    }

    const profFilter = String(professionalId || '').trim() // empty = any
    setAvailableDatesLoading(true)
    setAvailableDates({})

    const fetchWithTimeout = async (url, ms) => {
      const controller = new AbortController()
      const t = window.setTimeout(() => controller.abort(), Math.max(1000, Number(ms) || 8000))
      try {
        return await fetch(url, { method: 'GET', signal: controller.signal })
      } finally {
        window.clearTimeout(t)
      }
    }

    const computeHasSlots = (json) => {
      if (!json || typeof json !== 'object') return false
      if (json.closed) return false
      const items = Array.isArray(json.availability) ? json.availability : []
      if (!items.length) return false
      if (profFilter) {
        const it = items.find((x) => String(x?.professional_id) === String(profFilter))
        const slots = it && Array.isArray(it.slots) ? it.slots : []
        return slots.length > 0
      }
      return items.some((x) => Array.isArray(x?.slots) && x.slots.length > 0)
    }

    ;(async () => {
      try {
        const dates = dateChoices
        const results = {}

        // Preferred: one request to /occupancy for the whole range.
        try {
          const fromDate = dates[0]
          const toDate = dates[dates.length - 1]
          if (fromDate && toDate) {
            const occUrl = new URL(apiBase + '/occupancy')
            occUrl.searchParams.set('from', String(fromDate))
            occUrl.searchParams.set('to', String(toDate))
            occUrl.searchParams.set('service_id', sid)
            if (profFilter) occUrl.searchParams.set('professional_id', profFilter)
            if (apiSlug) occUrl.searchParams.set('slug', apiSlug)

            const occRes = await fetchWithTimeout(occUrl.toString(), 8000)
            if (occRes.ok) {
              const occJson = await occRes.json().catch(() => null)
              const days = (occJson && Array.isArray(occJson.days)) ? occJson.days : []
              if (days.length) {
                const freeByDate = new Map(days.map((d) => [String(d?.date || ''), Number(d?.free_slots || 0)]))
                dates.forEach((d) => {
                  results[d] = (freeByDate.get(String(d)) || 0) > 0
                })
                if (!cancelled) {
                  setAvailableDates(results)
                  setAvailableDatesLoading(false)
                }
                return
              }
            }
          }
        } catch (_) {
          // fall back to per-day /availability checks
        }

        let cursor = 0
        const workerCount = 4
        const workers = Array.from({ length: Math.min(workerCount, dates.length) }, () => (async () => {
          while (cursor < dates.length) {
            const idx = cursor
            cursor += 1
            const d = dates[idx]
            try {
              const url = new URL(apiBase + '/availability')
              url.searchParams.set('date', d)
              url.searchParams.set('service_id', sid)
              if (profFilter) url.searchParams.set('professional_id', profFilter)
              if (apiSlug) url.searchParams.set('slug', apiSlug)

              const res = await fetchWithTimeout(url.toString(), 8000)
              if (!res.ok) throw new Error('HTTP ' + res.status)
              const json = await res.json()
              results[d] = computeHasSlots(json)
            } catch (_) {
              results[d] = false
            }
          }
        })())

        await Promise.all(workers)
        if (cancelled) return
        setAvailableDates(results)
        setAvailableDatesLoading(false)
      } catch (_) {
        if (cancelled) return
        setAvailableDates({})
        setAvailableDatesLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [apiBase, apiSlug, serviceId, professionalId, dateChoices])

  useEffect(() => {
    if (!serviceId) return
    if (availableDatesLoading) return

    const filtered = dateChoices.filter((d) => Boolean(availableDates[d]))
    if (!filtered.length) return
    if (!selectedDate || !availableDates[selectedDate]) {
      setSelectedDate(filtered[0])
      setSlot('')
    }
  }, [availableDatesLoading, availableDates, dateChoices, selectedDate, serviceId])

  return (
    <div className="booking2-shell">
      {loading ? (
        <div className="card-surface" style={{ padding: 14, color: '#6b7280' }}>{t('booking_loading')}</div>
      ) : error ? (
        <div className="card-surface" style={{ padding: 14, border: '1px solid #fecaca', background: '#fef2f2', color: '#7f1d1d' }}>{error}</div>
      ) : success ? (
        <div className="card-surface" style={{ padding: 16, border: '1px solid #bbf7d0', background: '#f0fdf4', color: '#14532d' }}>
          <div style={{ fontWeight: 950, fontSize: 16 }}>{t('booking_success_title')}</div>
          <div style={{ marginTop: 6 }}>{t('booking_success_sub')}</div>
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="ea-pill"
              onClick={() => setSuccessModalOpen(true)}
              style={{ border: '1px solid rgba(20,83,45,0.25)', background: '#ffffff', color: '#14532d', fontWeight: 900 }}
            >
              {t('booking_success_open_popup')}
            </button>
          </div>
        </div>
      ) : (
        <div className="booking2-layout">
          {slugLooksLikePlaceholder ? (
            <div
              className="card-surface"
              style={{
                gridColumn: '1 / -1',
                padding: 14,
                border: '1px solid #fed7aa',
                background: '#fff7ed',
                color: '#7c2d12',
                marginBottom: 12,
              }}
            >
              <div style={{ fontWeight: 950, marginBottom: 6 }}>Slug inválido na URL</div>
              <div>
                Você abriu <b>/booking/SEU_SLUG</b> (placeholder). Troque por um slug real, por exemplo:{' '}
                <b>/booking/dev</b> ou <b>/booking/ana-beleza-madrid</b>.
              </div>
            </div>
          ) : null}
          <aside className="booking2-media">
            <div className="booking2-media-head">
              <div className="booking2-media-kicker">{businessName}</div>
              <div className="booking2-media-title">{t('booking_hero_kicker')}</div>
              <div className="booking2-media-meta">
                {businessPhone ? <div><b>{t('booking_contact_label')}:</b> {businessPhone}</div> : null}
                {hoursLabel ? <div><b>{t('booking_hours_label')}:</b> {hoursLabel}</div> : null}
              </div>
            </div>

            <div className="booking2-media-photo">
              {heroUrl ? <img src={heroUrl} alt="" /> : <div className="booking2-media-empty">{t('booking_photos_empty')}</div>}
            </div>

            {photos && photos.length ? (
              <div className="booking2-thumbs" style={{ marginTop: 12 }}>
                {photos.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className={`booking2-thumb ${idx === heroIdx ? 'active' : ''}`}
                    onClick={() => setHeroIdx(idx)}
                    aria-label={t('booking_photos_thumb')}
                  >
                    <img src={String(p)} alt="" />
                  </button>
                ))}
              </div>
            ) : null}

            <div className="booking2-media-panels">
              {(professionals || []).length ? (
                <div className="booking2-media-panel">
                  <div className="booking2-media-panel-title">{t('booking_team_title')}</div>
                  <div className="booking2-media-team">
                    {(professionals || []).slice(0, 10).map((p) => {
                      const n = String(p?.name || p?.nome || '').trim()
                      return (
                        <div key={String(p.id)} className="booking2-media-chip">
                          <span className="a" aria-hidden="true">{getInitials(n || '—')}</span>
                          <span className="n">{n || '—'}</span>
                        </div>
                      )
                    })}
                    {(professionals || []).length > 10 ? (
                      <div className="booking2-media-chip">
                        <span className="a" aria-hidden="true">+</span>
                        <span className="n">{(professionals || []).length - 10}</span>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          </aside>

          <main className="booking2-flow">
            <div className="card-surface booking2-card">
              <div className="booking2-card-head">
                <div>
                  <div className="booking2-card-title">{businessName}</div>
                  <div className="booking2-card-meta">
                    {businessPhone ? <span><b>{t('booking_contact_label')}:</b> {businessPhone}</span> : null}
                    {hoursLabel ? <span><b>{t('booking_hours_label')}:</b> {hoursLabel}</span> : null}
                  </div>
                  <div className="booking2-card-sub booking2-card-sub2">{t('booking_form_title')}</div>
                  <div className="booking2-note">{t('booking_form_sub')}</div>
                </div>
              </div>

              <div className="booking2-sections">
                <AccordionSection
                      sectionKey={SECTION.SERVICE}
                      title={t('booking_step_service')}
                      summary={selectedService ? selectedService.name : ''}
                      openSection={openSection}
                      setOpenSection={setOpenSection}
                      refEl={serviceSectionRef}
                    >
                      {services.length ? (
                        <div
                          className="booking2-acc-scroll"
                          style={showAllServices && services.length <= 6 ? { maxHeight: 'none' } : undefined}
                        >
                          <div className="booking2-list">
                            {(showAllServices ? services : services.slice(0, 3)).map((s) => {
                            const active = String(serviceId) === String(s.id)
                            const price = (typeof s.price_cents === 'number') ? formatMoney(lang, s.price_cents, currency) : ''
                            const durationLabel = s.duration_min ? `${s.duration_min} min` : t('booking_duration_unknown')
                            return (
                              <button
                                key={String(s.id)}
                                type="button"
                                className={`booking2-item ${active ? 'active' : ''}`}
                                onClick={() => {
                                  setServiceId(String(s.id))
                                  setProfessionalId('')
                                  setSlot('')
                                  setSelectedDate(toLocalISO())
                                  setDateRangeDays(6)
                                  setShowAllAvailableDates(false)
                                  setShowAllProfessionals(false)
                                  setOpenSection(SECTION.PROFESSIONAL)
                                }}
                              >
                                <div className="booking2-item-main">
                                  <div className="booking2-item-title">{s.name}</div>
                                  <div className="booking2-item-sub">
                                    <span className="booking2-smeta">{durationLabel}</span>
                                    {price ? <span className="booking2-smeta strong">{price}</span> : null}
                                  </div>
                                </div>
                                <div className="booking2-item-chev" aria-hidden="true">{active ? '✓' : '›'}</div>
                              </button>
                            )
                            })}

                            {services.length > 3 ? (
                              <button
                                type="button"
                                className="booking2-more"
                                onClick={() => setShowAllServices((v) => !v)}
                              >
                                {showAllServices ? t('booking_show_less') : t('booking_show_more_fmt').replace('{count}', String(services.length - 3))}
                              </button>
                            ) : null}
                          </div>
                        </div>
                      ) : (
                        <div className="booking2-note">{t('booking_service_none')}</div>
                      )}
                    </AccordionSection>

                    <AccordionSection
                      sectionKey={SECTION.PROFESSIONAL}
                      title={t('booking_step_professional')}
                      summary={professionalId ? (selectedProfessional ? (selectedProfessional.name || selectedProfessional.nome) : (availabilityByProfessional.get(String(professionalId))?.professional_name || '—')) : t('booking_prof_any')}
                      openSection={openSection}
                      setOpenSection={setOpenSection}
                      disabled={!serviceId}
                      refEl={professionalSectionRef}
                    >
                      {!serviceId ? (
                        <div className="booking2-note">{t('booking_service_none')}</div>
                      ) : (
                        <div
                          className="booking2-acc-scroll"
                          style={showAllProfessionals && eligibleProfessionalsForService.length <= 6 ? { maxHeight: 'none' } : undefined}
                        >
                          <div className="booking2-list">
                            <button
                              type="button"
                              className={`booking2-item ${professionalId === '' ? 'active' : ''}`}
                              onClick={() => {
                                setProfessionalId('')
                                setSlot('')
                                setSelectedDate(toLocalISO())
                                setDateRangeDays(6)
                                setShowAllAvailableDates(false)
                                setOpenSection(SECTION.DATE)
                              }}
                            >
                              <div className="booking2-item-avatar" aria-hidden="true">★</div>
                              <div className="booking2-item-main">
                                <div className="booking2-item-title">{t('booking_prof_any')}</div>
                                <div className="booking2-item-sub">{t('booking_prof_any_sub')}</div>
                              </div>
                              <div className="booking2-item-chev" aria-hidden="true">{professionalId === '' ? '✓' : '›'}</div>
                            </button>

                            {(showAllProfessionals ? eligibleProfessionalsForService : eligibleProfessionalsForService.slice(0, 3)).map((p) => {
                              const pid = String(p.id)
                              const active = String(professionalId) === pid
                              const n = String(p.name || p.nome || '').trim()
                              const info = professionalDaysById ? professionalDaysById[pid] : null
                              const disabled = info ? (Number(info.freeDays || 0) <= 0) : false
                              const nextLabel = (info && info.nextDate)
                                ? t('booking_prof_next_fmt').replace('{date}', formatDateDM(lang, String(info.nextDate)))
                                : ''
                              const meta = info
                                ? (Number(info.freeDays || 0) > 0
                                  ? `${t('booking_prof_days_fmt').replace('{count}', String(info.freeDays))}${nextLabel ? ` · ${nextLabel}` : ''}`
                                  : t('booking_prof_no_days_fmt').replace('{days}', String(professionalPreviewDays)))
                                : (professionalDaysLoading ? t('booking_prof_loading') : '—')
                              return (
                                <button
                                  key={pid}
                                  type="button"
                                  className={`booking2-item ${active ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
                                  onClick={() => {
                                    setProfessionalId(pid)
                                    setSlotProfessionalId(pid)
                                    setSlot('')
                                    setSelectedDate(toLocalISO())
                                    setDateRangeDays(6)
                                    setShowAllAvailableDates(false)
                                    setOpenSection(SECTION.DATE)
                                  }}
                                  disabled={disabled}
                                >
                                  <div className="booking2-item-avatar" aria-hidden="true">{getInitials(n || '—')}</div>
                                  <div className="booking2-item-main">
                                    <div className="booking2-item-title">{n || '—'}</div>
                                    <div className="booking2-item-sub">{meta}</div>
                                  </div>
                                  <div className="booking2-item-chev" aria-hidden="true">{active ? '✓' : '›'}</div>
                                </button>
                              )
                            })}

                            {eligibleProfessionalsForService.length > 3 ? (
                              <button
                                type="button"
                                className="booking2-more"
                                onClick={() => setShowAllProfessionals((v) => !v)}
                              >
                                {showAllProfessionals
                                  ? t('booking_show_less')
                                  : t('booking_show_more_fmt').replace('{count}', String(eligibleProfessionalsForService.length - 3))}
                              </button>
                            ) : null}
                          </div>
                        </div>
                      )}
                    </AccordionSection>

                    <AccordionSection
                      sectionKey={SECTION.DATE}
                      title={t('booking_step_date')}
                      summary={selectedDate ? formatDateCompact(lang, selectedDate) : ''}
                      openSection={openSection}
                      setOpenSection={setOpenSection}
                      disabled={!serviceId}
                      refEl={dateSectionRef}
                    >
                      {availableDatesLoading ? (
                        <div className="booking2-note">{t('booking_slots_loading')}</div>
                      ) : (
                        (() => {
                          const filtered = dateChoices.filter((d) => Boolean(availableDates[d]))
                          const visible = showAllAvailableDates ? filtered : filtered.slice(0, 4)
                          if (!filtered.length) {
                            return (
                              <div style={{ display: 'grid', gap: 10 }}>
                                <div className="booking2-note">
                                  {t('booking_slots_none_range').replace('{days}', String(dateChoices.length))}
                                </div>
                                {dateChoices.length < 60 ? (
                                  <button
                                    type="button"
                                    className="booking2-more"
                                    onClick={() => setDateRangeDays((d) => Math.min(60, (Number(d) || 5) + 7))}
                                  >
                                    {t('booking_dates_load_more')}
                                  </button>
                                ) : null}
                              </div>
                            )
                          }
                          return (
                            <div style={{ display: 'grid', gap: 10 }}>
                              <div className="booking2-date-grid">
                                {visible.map((d) => {
                                  const active = String(selectedDate) === String(d)
                                  return (
                                    <button
                                      key={d}
                                      type="button"
                                      className={`booking2-date ${active ? 'active' : ''}`}
                                      onClick={() => {
                                        setSelectedDate(d)
                                        setSlot('')
                                        setOpenSection(SECTION.TIME)
                                      }}
                                    >
                                      <div className="booking2-date-dow">{formatWeekdayLabel(lang, d)}</div>
                                      <div className="booking2-date-dm">{formatDateDM(lang, d)}</div>
                                    </button>
                                  )
                                })}
                              </div>

                              {filtered.length > 4 ? (
                                <button
                                  type="button"
                                  className="booking2-more"
                                  onClick={() => setShowAllAvailableDates((v) => !v)}
                                >
                                  {showAllAvailableDates
                                    ? t('booking_show_less')
                                    : t('booking_show_more_fmt').replace('{count}', String(filtered.length - 4))}
                                </button>
                              ) : null}

                              {dateChoices.length < 60 ? (
                                <button
                                  type="button"
                                  className="booking2-more"
                                  onClick={() => setDateRangeDays((d) => Math.min(60, (Number(d) || 5) + 7))}
                                >
                                  {t('booking_dates_load_more')}
                                </button>
                              ) : null}
                            </div>
                          )
                        })()
                      )}
                    </AccordionSection>

                    <AccordionSection
                      sectionKey={SECTION.TIME}
                      title={t('booking_step_time')}
                      summary={slot ? String(slot) : ''}
                      openSection={openSection}
                      setOpenSection={setOpenSection}
                      disabled={!serviceId}
                      refEl={timeSectionRef}
                    >
                      {!serviceId ? (
                        <div className="booking2-note">{t('booking_service_none')}</div>
                      ) : availabilityLoading ? (
                        <div className="booking2-note">{t('booking_slots_loading')}</div>
                      ) : availability && availability.closed ? (
                        <div className="booking2-muted">
                          <div style={{ fontWeight: 950 }}>{t('booking_closed')}</div>
                          <div style={{ marginTop: 6, color: '#475569' }}>{availability.closed_reason || '—'}</div>
                        </div>
                      ) : availability && Array.isArray(availability.availability) ? (
                        professionalId ? (
                          (selectedProfSlots && selectedProfSlots.length) ? (
                            <div className="booking2-slots">
                              {selectedProfSlots.map((time) => {
                                const pid = String(professionalId)
                                const active = (String(time) === slot) && (pid === String(slotProfessionalId))
                                return (
                                  <button
                                    key={String(time)}
                                    type="button"
                                    className={`booking2-slot ${active ? 'active' : ''}`}
                                    onClick={() => {
                                      setSlot(String(time))
                                      setSlotProfessionalId(pid)
                                      setOpenSection(SECTION.CONTACT)
                                    }}
                                  >
                                    {String(time)}
                                  </button>
                                )
                              })}
                            </div>
                          ) : (
                            <div className="booking2-note">{t('booking_slots_none')}</div>
                          )
                        ) : (
                          <div className="booking2-slots-wrap">
                            {(availability.availability || []).map((it) => {
                              const slots = Array.isArray(it.slots) ? it.slots : []
                              const pName = String(it.professional_name || '')
                              if (!slots.length) return null
                              return (
                                <div key={String(it.professional_id)} className="booking2-slot-group">
                                  <div className="booking2-slot-group-title">{pName}</div>
                                  <div className="booking2-slots">
                                    {slots.map((s) => {
                                      const time = String(s)
                                      const pid = String(it.professional_id)
                                      const active = (time === slot) && (pid === String(slotProfessionalId))
                                      return (
                                        <button
                                          key={time + '-' + pid}
                                          type="button"
                                          className={`booking2-slot ${active ? 'active' : ''}`}
                                          onClick={() => {
                                            setSlot(time)
                                            setSlotProfessionalId(pid)
                                            setOpenSection(SECTION.CONTACT)
                                          }}
                                        >
                                          {time}
                                        </button>
                                      )
                                    })}
                                  </div>
                                </div>
                              )
                            })}
                            {(availability.availability || []).every((it) => !it.slots || it.slots.length === 0) ? (
                              <div className="booking2-note">{t('booking_slots_none')}</div>
                            ) : null}
                          </div>
                        )
                      ) : (
                        <div className="booking2-note">{t('booking_slots_none')}</div>
                      )}
                    </AccordionSection>

                    <AccordionSection
                      sectionKey={SECTION.CONTACT}
                      title={t('booking_step_contact')}
                      summary={customerName || customerWhatsapp ? `${customerName || ''}${customerName && customerWhatsapp ? ' · ' : ''}${customerWhatsapp || ''}` : ''}
                      openSection={openSection}
                      setOpenSection={setOpenSection}
                      disabled={!serviceId || !selectedDate || !slot}
                      refEl={contactSectionRef}
                    >
                      <div className="booking2-summary" style={{ marginBottom: 12 }}>
                        <div className="r"><span className="k">{t('booking_summary_service')}</span><span className="v">{selectedService ? selectedService.name : '—'}</span></div>
                        <div className="r"><span className="k">{t('booking_summary_professional')}</span><span className="v">{professionalId ? (selectedProfessional ? (selectedProfessional.name || selectedProfessional.nome) : (availabilityByProfessional.get(String(professionalId))?.professional_name || '—')) : t('booking_prof_any')}</span></div>
                        <div className="r"><span className="k">{t('booking_summary_date')}</span><span className="v">{selectedDate ? formatDateCompact(lang, selectedDate) : '—'}</span></div>
                        <div className="r"><span className="k">{t('booking_summary_time')}</span><span className="v">{slot || '—'}</span></div>
                      </div>

                      <div className="booking2-form">
                        <div>
                          <label>{t('booking_customer_name')}</label>
                          <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder={t('booking_customer_name_ph')} />
                        </div>
                        <div>
                          <label>{t('booking_customer_whatsapp')}</label>
                          <input value={customerWhatsapp} onChange={(e) => setCustomerWhatsapp(e.target.value)} placeholder={t('booking_customer_whatsapp_ph')} />
                        </div>
                      </div>

                      {submitError ? <div className="booking2-error">{submitError}</div> : null}

                      <div className="booking2-cta-row">
                        {whatsAppPreConfirmLink ? (
                          <a
                            className="booking2-cta booking2-cta--whatsapp"
                            href={whatsAppPreConfirmLink}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {t('booking_success_whatsapp')}
                          </a>
                        ) : null}
                        <button type="button" className="booking2-cta booking2-cta--primary" disabled={!canSubmit} onClick={() => setConfirmOpen(true)}>
                          {submitting ? t('booking_submitting') : t('booking_submit')}
                        </button>
                      </div>
                      <div className="booking2-note" style={{ marginTop: 10 }}>{t('booking_note')}</div>
                    </AccordionSection>
              </div>
            </div>
          </main>
        </div>
      )}
      <Modal
        open={confirmOpen}
        title={t('booking_confirm_title')}
        onClose={() => setConfirmOpen(false)}
        footer={
          <>
            {whatsAppPreConfirmLink ? (
              <a
                className="ea-pill ea-pill--whatsapp"
                href={whatsAppPreConfirmLink}
                target="_blank"
                rel="noreferrer"
              >
                {t('booking_success_whatsapp')}
              </a>
            ) : null}
            <button type="button" className="ea-pill ea-pill--ghost" onClick={() => setConfirmOpen(false)}>
              {t('booking_confirm_cancel')}
            </button>
            <button
              type="button"
              className="ea-pill ea-pill--primary"
              disabled={!canSubmit}
              onClick={createAppointment}
            >
              {t('booking_confirm_cta')}
            </button>
          </>
        }
      >
        <div style={{ display: 'grid', gap: 10 }}>
          <div className="ea-modal-panel">
            <div style={{ fontWeight: 950 }}>{t('booking_summary_title')}</div>
            <div style={{ marginTop: 6 }}>
              <div><b>{t('booking_summary_service')}:</b> {selectedService ? selectedService.name : '—'}</div>
              <div><b>{t('booking_summary_professional')}:</b> {selectedSlotProfessional ? (selectedSlotProfessional.name || selectedSlotProfessional.nome) : (selectedProfessional ? (selectedProfessional.name || selectedProfessional.nome) : '—')}</div>
              <div><b>{t('booking_summary_date')}:</b> {selectedDate ? formatDateCompact(lang, selectedDate) : '—'}</div>
              <div><b>{t('booking_summary_time')}:</b> {slot || '—'}</div>
            </div>
          </div>

          <div className="ea-modal-panel">
            <div style={{ fontWeight: 950 }}>{t('booking_confirm_how_title')}</div>
            <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{t('booking_confirm_how_body')}</div>
          </div>

          <div>
            {t('booking_confirm_body')}
          </div>

          <div className="ea-modal-panel ea-modal-panel--neutral">
            <div style={{ fontWeight: 950, marginBottom: 6 }}>{t('booking_confirm_deadline_title')}</div>
            <div>{t('booking_confirm_deadline_body')}</div>
            <div style={{ marginTop: 6, color: 'rgba(226,232,240,0.88)' }}>{t('booking_confirm_reply_hint')}</div>
          </div>

          {policyText ? (
            <div className="ea-modal-panel ea-modal-panel--warn">
              <div style={{ fontWeight: 950, marginBottom: 6 }}>{t('booking_policy_title')}</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{policyText}</div>
              <div style={{ marginTop: 8 }}>{t('booking_policy_footer')}</div>
            </div>
          ) : (
            <div className="booking-note">{t('booking_policy_none')}</div>
          )}
        </div>
      </Modal>

      <Modal
        open={successModalOpen}
        title={t('booking_success_modal_title')}
        onClose={() => setSuccessModalOpen(false)}
        maxWidth={880}
        footer={
          <>
            {whatsAppConfirmLink ? (
              <a
                className="ea-pill ea-pill--whatsapp"
                href={whatsAppConfirmLink}
                target="_blank"
                rel="noreferrer"
                data-urgent={(isImmediateConfirmWindow || confirmDeadlineSoon) ? '1' : '0'}
              >
                {isImmediateConfirmWindow ? t('booking_success_confirm_now') : t('booking_success_whatsapp')}
              </a>
            ) : null}
            {success && success.calendar_url ? (
              <a
                className="ea-pill ea-pill--soft"
                href={resolveApiHref(apiBase, success.calendar_url)}
                target="_blank"
                rel="noreferrer"
              >
                {t('booking_success_add_calendar')}
              </a>
            ) : null}
            <button
              type="button"
              className="ea-pill ea-pill--ghost"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(successSummaryText)
                  setSuccessCopied(true)
                  window.setTimeout(() => setSuccessCopied(false), 1500)
                } catch (_) {}
              }}
            >
              {successCopied ? t('copied') : t('booking_success_copy_summary')}
            </button>
            <button
              type="button"
              className="ea-pill ea-pill--primary"
              onClick={() => setSuccessModalOpen(false)}
            >
              {t('booking_success_close')}
            </button>
          </>
        }
      >
        <div className="ea-success-grid">
          <div className="ea-success-left">
            {successPrimaryMessage ? (
              <div className="ea-success-headline">{successPrimaryMessage}</div>
            ) : (
              <div className="ea-success-headline">{t('booking_success_modal_body')}</div>
            )}

            {(isImmediateConfirmWindow || confirmDeadlineSoon) ? (
              <div className="ea-success-card ea-success-card--ok">
                <div className="ea-success-card-title">{t('booking_success_immediate_title')}</div>
                <div className="ea-success-card-body">{t('booking_success_immediate_body')}</div>
                {confirmByLocal ? (
                  <div className="ea-success-inline">
                    <div><b>{t('booking_confirm_deadline_title')}:</b> {confirmByLocal.toLocaleString(lang || undefined)}</div>
                    {countdownMs !== null ? (
                      <div className="ea-countdown" style={{ fontWeight: 1000, fontSize: 22, lineHeight: 1.1 }}>
                        {formatCountdown(countdownMs)}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {bookingCode ? <div style={{ marginTop: 6 }}><b>{t('booking_success_code_label')}:</b> {bookingCode}</div> : null}
              </div>
            ) : sendAtLocal || confirmByLocal ? (
              <div className="ea-success-card ea-success-card--warn">
                <div className="ea-success-card-title">{t('booking_confirm_timeline_title')}</div>
                {sendAtLocal ? <div><b>{t('booking_confirm_send_at_title')}:</b> {sendAtLocal.toLocaleString(lang || undefined)}</div> : null}
                {confirmByLocal ? <div style={{ marginTop: sendAtLocal ? 4 : 0 }}><b>{t('booking_confirm_deadline_title')}:</b> {confirmByLocal.toLocaleString(lang || undefined)}</div> : null}
                {bookingCode ? <div style={{ marginTop: 6 }}><b>{t('booking_success_code_label')}:</b> {bookingCode}</div> : null}
              </div>
            ) : bookingCode ? (
              <div className="ea-success-card ea-success-card--neutral">
                <b>{t('booking_success_code_label')}:</b> {bookingCode}
              </div>
            ) : null}
          </div>

          <div className="ea-success-right">
            <div className="ea-success-card ea-success-card--neutral">
              <div className="ea-success-card-title">{t('booking_success_modal_summary_title')}</div>
              <div className="ea-success-summary" style={{ whiteSpace: 'pre-wrap' }}>{successSummaryText}</div>
            </div>

            <div className="ea-success-card ea-success-card--tip">
              <div className="ea-success-card-title">{t('booking_success_modal_tip_title')}</div>
              <div className="ea-success-card-body">{t('booking_success_modal_tip_body')}</div>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
