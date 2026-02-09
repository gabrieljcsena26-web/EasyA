import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { DEFAULT_LANG, LANGS, normalizeLangCode, t as translate } from '../i18n/i18n'
import { buildApiUrl, fetchJson } from '../utils/apiFetch'
import './booking_premium.css'

function getApiBase() {
  try {
    if (typeof window !== 'undefined' && window.__API_URL__) return String(window.__API_URL__)
  } catch (_) {}
  // If we are running in a Cloudflare Pages preview and the build-time env var
  // wasn't injected, default to the production API so previews are testable.
  try {
    const host = (typeof window !== 'undefined' && window.location && window.location.hostname)
      ? String(window.location.hostname)
      : ''
    if (host && /(^|\.)pages\.dev$/i.test(host)) return 'https://api.easy-agenda.com'
  } catch (_) {}

  // Prefer relative paths so local dev uses Vite proxy (avoids CORS),
  // and prod can be served behind a reverse proxy on the same origin.
  return ''
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

function _dateForIsoSafe(iso) {
  const v = String(iso || '').trim()
  if (!v) return null
  // Use midday UTC to avoid DST/offset edge cases shifting the day.
  const dt = new Date(`${v}T12:00:00Z`)
  if (Number.isNaN(dt.getTime())) return null
  return dt
}

function formatDM(lang, iso, tzName) {
  const v = String(iso || '').trim()
  if (!v) return '—'
  try {
    const dt = _dateForIsoSafe(v) || new Date(v + 'T00:00:00')
    const opts = { day: '2-digit', month: 'short' }
    if (tzName) opts.timeZone = String(tzName)
    return new Intl.DateTimeFormat(lang || undefined, opts).format(dt)
  } catch (_) {
    return v
  }
}

function formatWeekday(lang, iso, tzName) {
  const v = String(iso || '').trim()
  if (!v) return '—'
  const locale = String(lang || '').trim() || undefined
  try {
    const dt = _dateForIsoSafe(v) || new Date(v + 'T00:00:00')
    const opts = { weekday: 'long' }
    if (tzName) opts.timeZone = String(tzName)
    let weekday = new Intl.DateTimeFormat(locale, opts).format(dt)
    if ((lang || '').toLowerCase().startsWith('pt')) {
      weekday = weekday.replace(/-feira\b/gi, '').trim().toLowerCase()
    }
    return weekday
  } catch (_) {
    return v
  }
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

function formatMoney(lang, cents, currency) {
  const n = Number(cents)
  if (!Number.isFinite(n)) return ''
  const value = n / 100
  try {
    if (currency) return new Intl.NumberFormat(lang || undefined, { style: 'currency', currency: String(currency) }).format(value)
    return new Intl.NumberFormat(lang || undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)
  } catch (_) {
    return String(value.toFixed(2))
  }
}

function looksLikePlaceholderSlug(v) {
  const s = String(v || '').trim().toLowerCase()
  if (!s) return false
  return s === 'seu_slug' || s === 'seu-slug' || s === 'your_slug' || s === 'your-slug'
}

function parseLocalDateTime(dateISO, timeHHMM) {
  const d = String(dateISO || '').trim()
  const t = String(timeHHMM || '').trim()
  if (!d || !t) return null
  const dt = new Date(`${d}T${t}:00`)
  if (Number.isNaN(dt.getTime())) return null
  return dt
}

function formatDateTime(lang, dt) {
  if (!(dt instanceof Date) || Number.isNaN(dt.getTime())) return '—'
  const locale = String(lang || '').trim() || undefined
  try {
    return new Intl.DateTimeFormat(locale, {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(dt)
  } catch (_) {
    return dt.toLocaleString()
  }
}

function toIcsUtcStamp(dt) {
  if (!(dt instanceof Date) || Number.isNaN(dt.getTime())) return ''
  // YYYYMMDDTHHMMSSZ
  return dt.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')
}

function getServiceDurationMin(service) {
  const v = service && (service.duration_min ?? service.duration_minutes ?? service.duration)
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return 60
  return Math.round(n)
}

function normalizeWaMeNumber(v) {
  // wa.me expects country code + number, digits only.
  const raw = String(v || '').trim()
  if (!raw) return ''
  const digits = raw.replace(/\D+/g, '')
  if (!digits) return ''
  // If user typed leading 00, normalize to international digits.
  const normalized = digits.startsWith('00') ? digits.slice(2) : digits

  // If it already looks like an international number, keep it.
  if (normalized.length >= 11 && normalized.length <= 15) return normalized

  // Heuristics when the business stored a local-format number.
  // - 9 digits is common for Spain (e.g., 6xxxxxxxx, 7xxxxxxxx, 9xxxxxxxx) -> prefix 34
  // - 10/11 digits is common for Brazil (DDD + number) -> prefix 55
  if (normalized.length === 9) return `34${normalized}`
  if (normalized.length === 10 || normalized.length === 11) return `55${normalized}`

  return normalized
}

function buildWhatsAppLink(toNumber, text) {
  const to = normalizeWaMeNumber(toNumber)
  if (!to) return ''
  const msg = String(text || '').trim()

  // iOS is occasionally picky about opening wa.me from within in-app contexts.
  // Using api.whatsapp.com/send tends to be more reliable and still lands in WhatsApp.
  let isIOS = false
  try {
    const ua = String((typeof navigator !== 'undefined' && navigator.userAgent) ? navigator.userAgent : '')
    isIOS = /iPhone|iPad|iPod/i.test(ua)
  } catch (_) {}

  if (isIOS) {
    const u = new URL('https://api.whatsapp.com/send')
    u.searchParams.set('phone', to)
    if (msg) u.searchParams.set('text', msg)
    u.searchParams.set('app_absent', '0')
    return u.toString()
  }

  const u = new URL(`https://wa.me/${to}`)
  if (msg) u.searchParams.set('text', msg)
  return u.toString()
}

function buildWhatsAppBaseLink(toNumber) {
  const to = normalizeWaMeNumber(toNumber)
  if (!to) return ''
  return `https://wa.me/${to}`
}

function normalizeUiLang(v) {
  const raw = String(v || '').trim()
  if (!raw) return DEFAULT_LANG
  const s = raw.toLowerCase()
  if (s === 'pt' || s.startsWith('pt-')) return 'pt-BR'
  if (s === 'en' || s.startsWith('en-')) return 'en'
  if (s === 'es' || s.startsWith('es-')) return 'es'
  if (s === 'fr' || s.startsWith('fr-')) return 'fr'
  if (s === 'ca' || s.startsWith('ca-')) return 'ca'
  return raw
}

function buildWhatsAppConfirmText({ uiLang, businessName, serviceName, professionalName, dateISO, timeHHMM, customerName, expiresInMinutes }) {
  const parts = []
  const lang = normalizeUiLang(uiLang)

  if (lang === 'en') {
    parts.push(`Hi! This is ${String(customerName || '').trim() || 'a customer'}.`)
    parts.push(`I’d like to confirm my appointment at ${String(businessName || '').trim() || 'your business'}.`)
    if (serviceName) parts.push(`Service: ${serviceName}.`)
    if (professionalName) parts.push(`Professional: ${professionalName}.`)
    if (dateISO && timeHHMM) parts.push(`Date/Time: ${dateISO} at ${timeHHMM}.`)
  } else if (lang === 'es') {
    parts.push(`¡Hola! Soy ${String(customerName || '').trim() || 'un cliente'}.`)
    parts.push(`Quiero confirmar mi cita en ${String(businessName || '').trim() || 'su establecimiento'}.`)
    if (serviceName) parts.push(`Servicio: ${serviceName}.`)
    if (professionalName) parts.push(`Profesional: ${professionalName}.`)
    if (dateISO && timeHHMM) parts.push(`Fecha/Hora: ${dateISO} a las ${timeHHMM}.`)
  } else if (lang === 'fr') {
    parts.push(`Bonjour ! Ici ${String(customerName || '').trim() || 'un client'}.`)
    parts.push(`Je souhaite confirmer mon rendez-vous chez ${String(businessName || '').trim() || 'votre établissement'}.`)
    if (serviceName) parts.push(`Service : ${serviceName}.`)
    if (professionalName) parts.push(`Professionnel : ${professionalName}.`)
    if (dateISO && timeHHMM) parts.push(`Date/Heure : ${dateISO} à ${timeHHMM}.`)
  } else if (lang === 'ca') {
    parts.push(`Hola! Sóc ${String(customerName || '').trim() || 'un client'}.`)
    parts.push(`Vull confirmar la meva cita a ${String(businessName || '').trim() || 'el vostre establiment'}.`)
    if (serviceName) parts.push(`Servei: ${serviceName}.`)
    if (professionalName) parts.push(`Professional: ${professionalName}.`)
    if (dateISO && timeHHMM) parts.push(`Data/Hora: ${dateISO} a les ${timeHHMM}.`)
  } else {
    parts.push(`Olá! Aqui é ${String(customerName || '').trim() || 'um cliente'}.`)
    parts.push(`Quero confirmar meu agendamento em ${String(businessName || '').trim() || 'seu estabelecimento'}.`)
    if (serviceName) parts.push(`Serviço: ${serviceName}.`)
    if (professionalName) parts.push(`Profissional: ${professionalName}.`)
    if (dateISO && timeHHMM) parts.push(`Data/Hora: ${dateISO} às ${timeHHMM}.`)
  }
  if (Number.isFinite(Number(expiresInMinutes)) && Number(expiresInMinutes) > 0) {
    const mins = Math.max(1, Math.round(Number(expiresInMinutes)))
    const h = Math.floor(mins / 60)
    const m = mins % 60
    const pretty = h > 0 ? `${h}h${m ? ` ${m}min` : ''}` : `${m}min`
    if (lang === 'en') parts.push(`(Time-limited confirmation: ${pretty})`)
    else if (lang === 'es') parts.push(`(Confirmación con tiempo limitado: ${pretty})`)
    else if (lang === 'fr') parts.push(`(Confirmation avec délai limité : ${pretty})`)
    else if (lang === 'ca') parts.push(`(Confirmació amb temps limitat: ${pretty})`)
    else parts.push(`(Confirmação com tempo limitado: ${pretty})`)
  }
  if (lang === 'en') parts.push('Thank you!')
  else if (lang === 'es') parts.push('¡Gracias!')
  else if (lang === 'fr') parts.push('Merci !')
  else if (lang === 'ca') parts.push('Gràcies!')
  else parts.push('Obrigado!')
  return parts.join('\n')
}

function parseIsoDateMaybe(v) {
  if (!v) return null
  const d = new Date(String(v))
  if (Number.isNaN(d.getTime())) return null
  return d
}

function buildReminderSchedule({ startDt, created }) {
  const now = new Date()
  const out = []
  out.push({ channel: 'WhatsApp', labelKey: 'booking_premium_timeline_confirm', when: now })

  const sendAt = parseIsoDateMaybe(created && (created.send_at || created.sendAt))
  const confirmBy = parseIsoDateMaybe(created && (created.confirm_by || created.confirmBy))

  // Prefer backend policy-driven schedule when available.
  if (sendAt) out.push({ channel: 'Calendário', label: 'Alarme para confirmar (arquivo .ics)', when: sendAt })
  if (confirmBy) out.push({ channel: 'Prazo', label: 'Confirmar até', when: confirmBy })
  if (sendAt || confirmBy) return out

  if (!(startDt instanceof Date) || Number.isNaN(startDt.getTime())) return out

  const hoursUntil = (startDt.getTime() - now.getTime()) / 36e5
  const h36 = 36 * 36e5
  const h24 = 24 * 36e5

  // Regra:
  // - Se faltam >= 36h: lembretes em -36h e -24h
  // - Se faltam 24–36h: lembrete em -24h
  // - Se faltam < 24h: lembrete imediato (porque -24h já passou)
  if (hoursUntil >= 36) {
    out.push({ channel: 'WhatsApp', labelKey: 'booking_premium_timeline_36h', when: new Date(startDt.getTime() - h36) })
    out.push({ channel: 'WhatsApp', labelKey: 'booking_premium_timeline_24h', when: new Date(startDt.getTime() - h24) })
    out.push({ channel: 'Calendário', labelKey: 'booking_premium_timeline_cal_36_24', when: new Date(startDt.getTime() - h36) })
  } else if (hoursUntil >= 24) {
    out.push({ channel: 'WhatsApp', labelKey: 'booking_premium_timeline_24h', when: new Date(startDt.getTime() - h24) })
    out.push({ channel: 'Calendário', labelKey: 'booking_premium_timeline_cal_24', when: now })
  } else {
    out.push({ channel: 'WhatsApp', labelKey: 'booking_premium_timeline_now', when: now })
    out.push({ channel: 'Calendário', labelKey: 'booking_premium_timeline_cal_1h', when: now })
  }

  return out
}

export default function BookingPremium() {
  const navigate = useNavigate()
  const params = useParams()
  const routeSlug = params && params.slug ? String(params.slug) : ''
  const [searchParams] = useSearchParams()
  const slugOverride = searchParams.get('slug')
  const langOverrideParamRaw = searchParams.get('lang')

  const apiBase = useMemo(() => String(getApiBase() || '').trim(), [])

  const effectiveSlug = useMemo(() => {
    const override = String(slugOverride || '').trim()
    if (override) return override
    if (looksLikePlaceholderSlug(routeSlug)) return ''
    return String(routeSlug || '').trim()
  }, [routeSlug, slugOverride])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [trialExpired, setTrialExpired] = useState(null)
  const [cfg, setCfg] = useState(null)

  const business = cfg && cfg.business ? cfg.business : null
  const businessName = String((business && (business.nome || business.name)) || 'EasyAgenda').trim()
  const businessSlug = String((business && (business.slug || business.business_slug)) || '').trim()
  const apiSlug = businessSlug || effectiveSlug || 'dev'
  const businessTz = String((business && (business.timezone || business.tz)) || '').trim()
  const businessToday = String((business && (business.today_local || business.today)) || '').trim() || ''
  const deviceTz = useMemo(() => {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || '' } catch (_) { return '' }
  }, [])
  const showTzHint = Boolean(businessTz && deviceTz && businessTz !== deviceTz)

  const businessPhotos = (business && Array.isArray(business.photos)) ? business.photos.map(String).filter(Boolean) : []
  const heroUrl = businessPhotos.length ? String(businessPhotos[0]) : ''

  const services = cfg && Array.isArray(cfg.services) ? cfg.services : []
  const professionals = cfg && Array.isArray(cfg.professionals) ? cfg.professionals : []
  const currency = (cfg && cfg.currency) ? String(cfg.currency) : ''

  const [bookingLang, setBookingLang] = useState(() => {
    try {
      const v = localStorage.getItem('ea_lang_booking')
      const norm = normalizeLangCode(v)
      return norm || ''
    } catch (_) {
      return ''
    }
  })

  const langOverrideParam = useMemo(() => {
    const norm = normalizeLangCode(langOverrideParamRaw)
    return norm || ''
  }, [langOverrideParamRaw])

  const setBookingLangSafe = (next) => {
    const raw = String(next ?? '').trim()
    if (!raw) {
      setBookingLang('')
      try { localStorage.removeItem('ea_lang_booking') } catch (_) {}
      return
    }

    const norm = normalizeLangCode(raw)
    if (!norm) return
    setBookingLang(norm)
    try { localStorage.setItem('ea_lang_booking', norm) } catch (_) {}
  }

  const uiLang = useMemo(() => {
    const fromBiz = business && (business.idioma_padrao || business.lang || business.language)
    return normalizeUiLang(bookingLang || langOverrideParam || fromBiz || DEFAULT_LANG)
  }, [business, bookingLang, langOverrideParam])

  const bookingLangSelectValue = useMemo(() => {
    if (bookingLang) return bookingLang
    if (langOverrideParam) return langOverrideParam
    return ''
  }, [bookingLang, langOverrideParam])

  const tt = useMemo(() => (key) => translate(uiLang, key), [uiLang])

  const _getTrialExpiredInfo = (e) => {
    try {
      const status = Number(e && e.status)
      if (status !== 402) return null
      const body = e && typeof e.body !== 'undefined' ? e.body : null
      const detail = body && typeof body === 'object' ? (body.detail || body) : null
      const code = detail && typeof detail === 'object' ? detail.code : null
      if (code !== 'TRIAL_EXPIRED') return null
      return {
        message: (detail && typeof detail === 'object' ? (detail.message || '') : '') || '',
        trial_end_utc: (detail && typeof detail === 'object' ? (detail.trial_end_utc || detail.trialEndUtc) : null) || null,
      }
    } catch (_) {
      return null
    }
  }

  const [step, setStep] = useState('service') // service | professional | date | time | contact

  const [serviceId, setServiceId] = useState('')
  const [professionalId, setProfessionalId] = useState('') // '' = any

  // Keep the search window small and automatic. UI shows only the next few available days.
  const rangeDays = 21
  const [selectedDate, setSelectedDate] = useState('')
  const [availableDatesLoading, setAvailableDatesLoading] = useState(false)
  const [availableDates, setAvailableDates] = useState(() => []) // array of YYYY-MM-DD with free slots

  const [availabilityLoading, setAvailabilityLoading] = useState(false)
  const [availability, setAvailability] = useState(null)

  const [slotTime, setSlotTime] = useState('')
  const [slotProfessionalId, setSlotProfessionalId] = useState('')

  const [customerName, setCustomerName] = useState('')
  const [customerWhatsapp, setCustomerWhatsapp] = useState('')
  const [submitLoading, setSubmitLoading] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [success, setSuccess] = useState(false)

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmData, setConfirmData] = useState(null)

  const topRef = useRef(null)

  const dateChoices = useMemo(() => {
    const base = businessToday || toLocalISO()
    const n = Math.max(6, Math.min(60, Number(rangeDays) || 21))
    return Array.from({ length: n }, (_, idx) => addDaysISO(base, idx))
  }, [rangeDays, businessToday])

  const selectedService = useMemo(() => services.find((s) => String(s?.id) === String(serviceId)) || null, [services, serviceId])
  const selectedProfessional = useMemo(
    () => professionals.find((p) => String(p?.id) === String(professionalId)) || null,
    [professionals, professionalId]
  )

  useEffect(() => {
    let cancelled = false

    setLoading(true)
    setError('')
    setTrialExpired(null)

    const controller = new AbortController()

    ;(async () => {
      try {
        const slugCandidates = []
        if (effectiveSlug) slugCandidates.push(effectiveSlug)
        slugCandidates.push('dev')
        slugCandidates.push('ana-beleza-madrid')

        let json = null
        for (const s of slugCandidates) {
          try {
            const u = new URL(buildApiUrl(apiBase, '/config'), window.location.origin)
            u.searchParams.set('slug', s)
            json = await fetchJson(u.toString(), { timeoutMs: 10000, retries: 1, signal: controller.signal })
            if (json) break
          } catch (_) {
            // keep trying
          }
        }

        if (!json) {
          // last resort: no slug
          const u = new URL(buildApiUrl(apiBase, '/config'), window.location.origin)
          json = await fetchJson(u.toString(), { timeoutMs: 10000, retries: 1, signal: controller.signal })
        }
        if (cancelled) return

        setCfg(json)
        setLoading(false)

        // keep URL clean/shareable
        try {
          const b = json && json.business ? json.business : null
          const resolved = String((b && (b.slug || b.business_slug)) || '').trim()
          if (resolved && !slugOverride && (!routeSlug || looksLikePlaceholderSlug(routeSlug))) {
            navigate(`/booking/${encodeURIComponent(resolved)}`, { replace: true })
          }
        } catch (_) {}

        // defaults
        const firstService = json && Array.isArray(json.services) && json.services.length ? String(json.services[0].id) : ''
        setServiceId(firstService)
        setProfessionalId('')
        setSlotTime('')
        setSlotProfessionalId('')
        setStep('service')
      } catch (e) {
        if (cancelled) return
        setLoading(false)
        const details = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.DEV)
          ? ` (${String(e && e.message ? e.message : e)})`
          : ''
        setError((tt('booking_error_load') || 'Não foi possível carregar o booking.') + details)
      }
    })()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [apiBase, effectiveSlug, navigate, routeSlug, slugOverride])

  // Recompute available dates whenever service/professional/range changes.
  useEffect(() => {
    let cancelled = false

    setAvailableDates([])
    setAvailableDatesLoading(false)

    const sid = String(serviceId || '').trim()
    if (!sid) return

    const prof = String(professionalId || '').trim() // empty = any

    const controller = new AbortController()

    setAvailableDatesLoading(true)

    ;(async () => {
      try {
        const fromDate = dateChoices[0]
        const toDate = dateChoices[dateChoices.length - 1]
        const occUrl = new URL(buildApiUrl(apiBase, '/occupancy'), window.location.origin)
        occUrl.searchParams.set('from', String(fromDate))
        occUrl.searchParams.set('to', String(toDate))
        occUrl.searchParams.set('service_id', sid)
        if (prof) occUrl.searchParams.set('professional_id', prof)
        if (apiSlug) occUrl.searchParams.set('slug', apiSlug)

        const body = await fetchJson(occUrl.toString(), { timeoutMs: 10000, retries: 1, signal: controller.signal })
        const days = body && Array.isArray(body.days) ? body.days : []

        // Normalize + filter
        const freeDates = days
          .map((d) => ({ date: String(d?.date || '').trim(), free: Number(d?.free_slots || 0) }))
          .filter((d) => d.date && d.free > 0)
          .map((d) => d.date)

        // Ensure order follows dateChoices (prevents “travado na terça” feel)
        const ordered = dateChoices.filter((d) => freeDates.includes(d))

        if (cancelled) return
        setAvailableDates(ordered)
        setAvailableDatesLoading(false)

        // Keep selectedDate consistent
        if (!selectedDate || !ordered.includes(String(selectedDate))) {
          const next = ordered[0] || ''
          setSelectedDate(next)
          setSlotTime('')
          setSlotProfessionalId('')
        }
      } catch (_) {
        if (cancelled) return
        setAvailableDates([])
        setAvailableDatesLoading(false)
      }
    })()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [apiBase, apiSlug, serviceId, professionalId, dateChoices, selectedDate])

  // Fetch times for selected day
  useEffect(() => {
    let cancelled = false

    setAvailability(null)
    setAvailabilityLoading(false)

    const sid = String(serviceId || '').trim()
    const d = String(selectedDate || '').trim()
    if (!sid || !d) return

    const controller = new AbortController()

    setAvailabilityLoading(true)

    ;(async () => {
      try {
        const url = new URL(buildApiUrl(apiBase, '/availability'), window.location.origin)
        url.searchParams.set('date', d)
        url.searchParams.set('service_id', sid)
        if (apiSlug) url.searchParams.set('slug', apiSlug)

        const json = await fetchJson(url.toString(), { timeoutMs: 10000, retries: 1, signal: controller.signal })
        if (cancelled) return
        setAvailability(json)
        setAvailabilityLoading(false)

        // Validate slot
        try {
          const allSlots = []
          ;(json.availability || []).forEach((it) => {
            ;(it.slots || []).forEach((s) => allSlots.push({ time: String(s), professional_id: String(it.professional_id) }))
          })
          const stillOk = allSlots.some((s) => s.time === String(slotTime) && String(s.professional_id) === String(slotProfessionalId))
          if (!stillOk) {
            setSlotTime('')
            setSlotProfessionalId('')
          }
        } catch (_) {}
      } catch (_) {
        if (cancelled) return
        const info = _getTrialExpiredInfo(_)
        if (info) {
          setTrialExpired(info)
          setError('')
          setAvailability(null)
          setAvailabilityLoading(false)
          return
        }
        setAvailability(null)
        setAvailabilityLoading(false)
      }
    })()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [apiBase, apiSlug, selectedDate, serviceId, slotProfessionalId, slotTime])

  const slotsForUI = useMemo(() => {
    const items = availability && Array.isArray(availability.availability) ? availability.availability : []
    const prof = String(professionalId || '').trim()

    const byProf = items
      .map((it) => ({
        professional_id: String(it?.professional_id || ''),
        professional_name: String(it?.professional_name || ''),
        slots: Array.isArray(it?.slots) ? it.slots.map(String) : [],
      }))
      .filter((p) => p.professional_id)

    if (!byProf.length) return []

    if (prof) {
      const row = byProf.find((p) => p.professional_id === prof)
      if (!row) return []
      return row.slots.map((time) => ({ time, professional_id: row.professional_id, professional_name: row.professional_name }))
    }

    // Any professional: show all slots grouped but flattened (premium UX: let user pick time first)
    const out = []
    byProf.forEach((p) => {
      p.slots.forEach((time) => out.push({ time, professional_id: p.professional_id, professional_name: p.professional_name }))
    })

    // Sort by time then by name
    out.sort((a, b) => {
      const at = String(a.time)
      const bt = String(b.time)
      if (at !== bt) return at.localeCompare(bt)
      return String(a.professional_name).localeCompare(String(b.professional_name))
    })

    return out
  }, [availability, professionalId])

  const visibleDates = useMemo(() => availableDates.slice(0, 6), [availableDates])

  const premiumTitle = useMemo(() => {
    // fall back if translation missing
    const v = tt('booking_form_title')
    return v && v !== 'booking_form_title' ? v : 'Agende seu horário'
  }, [tt])

  const onSelectService = (sid) => {
    setServiceId(String(sid))
    setProfessionalId('')
    setSelectedDate('')
    setSlotTime('')
    setSlotProfessionalId('')
    setSubmitError('')
    setSuccess(false)
    setStep('professional')
    try { topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) } catch (_) {}
  }

  const onSelectProfessional = (pid) => {
    setProfessionalId(String(pid || ''))
    setSelectedDate('')
    setSlotTime('')
    setSlotProfessionalId(String(pid || ''))
    setSubmitError('')
    setSuccess(false)
    setStep('date')
    try { topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) } catch (_) {}
  }

  const onSelectDate = (d) => {
    setSelectedDate(String(d))
    setSlotTime('')
    setSlotProfessionalId(String(professionalId || ''))
    setSubmitError('')
    setSuccess(false)
    setStep('time')
  }

  const onSelectSlot = ({ time, professional_id }) => {
    setSlotTime(String(time))
    setSlotProfessionalId(String(professional_id || ''))
    setStep('contact')
  }

  const canSubmit = Boolean(serviceId && selectedDate && slotTime && customerName.trim() && customerWhatsapp.trim() && slotProfessionalId)

  useEffect(() => {
    if (!confirmOpen) return
    const onKeyDown = (e) => {
      if (e && e.key === 'Escape') setConfirmOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [confirmOpen])

  const downloadIcs = (data) => {
    try {
      const start = parseLocalDateTime(data?.date, data?.time)
      if (!start) return
      const minutes = getServiceDurationMin(data?.service)
      const end = new Date(start.getTime() + minutes * 60 * 1000)

      const sendAt = parseIsoDateMaybe(data?.created && (data.created.send_at || data.created.sendAt))
      const confirmBy = parseIsoDateMaybe(data?.created && (data.created.confirm_by || data.created.confirmBy))
      const appointmentId = data?.created && data.created.appointment && data.created.appointment.id ? Number(data.created.appointment.id) : null
      const bookingCode = Number.isFinite(appointmentId) ? `EA-${appointmentId}` : ''

      const formatLocalShort = (d) => {
        if (!(d instanceof Date) || Number.isNaN(d.getTime())) return ''
        const yyyy = d.getFullYear()
        const mm = String(d.getMonth() + 1).padStart(2, '0')
        const dd = String(d.getDate()).padStart(2, '0')
        const hh = String(d.getHours()).padStart(2, '0')
        const mi = String(d.getMinutes()).padStart(2, '0')
        return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
      }

      const now = new Date()
      const hoursUntil = (start.getTime() - now.getTime()) / 36e5
      const alarmHours = hoursUntil >= 36 ? [36, 24] : hoursUntil >= 24 ? [24] : [1]

      const summary = `${String(data?.businessName || 'Agendamento')} - ${String(data?.service?.name || 'Serviço')}`
      const profName = String(data?.professionalName || '').trim()
      const waBase = String(data?.whatsappBaseLink || '') || buildWhatsAppBaseLink(data?.businessWhatsapp)
      const suggestedQuick = (() => {
        const who = String(data?.businessName || '').trim() || 'seu estabelecimento'
        const dt = (data?.date && data?.time) ? `${String(data.date)} ${String(data.time)}` : ''
        const code = bookingCode ? ` (${bookingCode})` : ''
        return `Confirmo meu agendamento em ${who}${dt ? ` para ${dt}` : ''}${code}.`
      })()
      const descLines = [
        bookingCode ? `Código do agendamento: ${bookingCode}` : null,
        `Serviço: ${String(data?.service?.name || '')}`,
        profName ? `Profissional: ${profName}` : null,
        `Cliente: ${String(data?.customerName || '')}`,
        `WhatsApp: ${String(data?.customerWhatsapp || '')}`,
        '',
        sendAt ? `Lembrete para confirmar: ${formatLocalShort(sendAt)}` : null,
        confirmBy ? `Confirmar até: ${formatLocalShort(confirmBy)}` : null,
        '',
        // Keep the URL short in iOS Calendar Notes.
        waBase ? 'Abrir WhatsApp (toque no link):' : null,
        waBase ? waBase : null,
        suggestedQuick ? 'Mensagem sugerida (copie/cole no WhatsApp):' : null,
        suggestedQuick || null,
      ]
      const desc = descLines.filter((v) => v !== null && typeof v !== 'undefined').join('\\n')

      const alarmBlocks = (() => {
        const mkAlarm = (at) => {
          const trigger = `TRIGGER;VALUE=DATE-TIME:${toIcsUtcStamp(new Date(at.getTime()))}`
          return [
            'BEGIN:VALARM',
            'ACTION:DISPLAY',
            `DESCRIPTION:Lembrete: ${summary.replace(/\r?\n/g, ' ')}`,
            trigger,
            'END:VALARM',
          ].join('\r\n')
        }

        const isValid = (d) => d instanceof Date && !Number.isNaN(d.getTime())
        const future = (d, minMs = 60 * 1000) => isValid(d) && d.getTime() > now.getTime() + minMs

        // Policy-driven: ensure the alert happens inside the confirmation window.
        if (isValid(confirmBy) && confirmBy.getTime() > now.getTime() + 2 * 60 * 1000) {
          const primaryAt = (() => {
            if (future(sendAt, 60 * 1000)) return sendAt
            // If send_at already passed, alert shortly after download so the user still confirms in time.
            return new Date(now.getTime() + 2 * 60 * 1000)
          })()

          const blocks = []
          if (primaryAt.getTime() < confirmBy.getTime()) blocks.push(mkAlarm(primaryAt))

          // Optional second alarm closer to the deadline (30 min before), when it still makes sense.
          const deadlineAt = new Date(confirmBy.getTime() - 30 * 60 * 1000)
          if (future(deadlineAt, 5 * 60 * 1000) && deadlineAt.getTime() > primaryAt.getTime() + 10 * 60 * 1000) {
            blocks.push(mkAlarm(deadlineAt))
          }

          if (blocks.length) return blocks
        }

        // If we only have send_at, use it when still in the future.
        if (future(sendAt, 60 * 1000)) {
          return [mkAlarm(sendAt)]
        }

        // Fallback to relative alarms when we don't have a policy time.
        return alarmHours.map((h) => [
          'BEGIN:VALARM',
          'ACTION:DISPLAY',
          `DESCRIPTION:Lembrete: ${summary.replace(/\r?\n/g, ' ')}`,
          `TRIGGER:-PT${Number(h)}H`,
          'END:VALARM',
        ].join('\r\n'))
      })()

      const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//EasyAgenda//Booking//PT-BR',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        `UID:${Date.now()}@easyagenda`,
        `DTSTAMP:${toIcsUtcStamp(new Date())}`,
        `DTSTART:${toIcsUtcStamp(new Date(start.getTime()))}`,
        `DTEND:${toIcsUtcStamp(new Date(end.getTime()))}`,
        `SUMMARY:${summary.replace(/\r?\n/g, ' ')}`,
        `DESCRIPTION:${desc.replace(/\r?\n/g, '\\n')}`,
        ...alarmBlocks,
        'END:VEVENT',
        'END:VCALENDAR',
      ].join('\r\n')

      const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `agendamento-${String(data?.date || '').trim() || 'data'}-${String(data?.time || '').trim() || 'hora'}.ics`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (_) {}
  }

  const openGoogleCalendar = (data) => {
    try {
      const start = parseLocalDateTime(data?.date, data?.time)
      if (!start) return
      const minutes = getServiceDurationMin(data?.service)
      const end = new Date(start.getTime() + minutes * 60 * 1000)

      const text = `${String(data?.businessName || 'Agendamento')} - ${String(data?.service?.name || 'Serviço')}`
      const details = [
        `Serviço: ${String(data?.service?.name || '')}`,
        data?.professionalName ? `Profissional: ${String(data.professionalName)}` : '',
        `Cliente: ${String(data?.customerName || '')}`,
      ].filter(Boolean).join('\n')

      const dates = `${toIcsUtcStamp(new Date(start.getTime())).replace('Z', '')}Z/${toIcsUtcStamp(new Date(end.getTime())).replace('Z', '')}Z`
      const u = new URL('https://www.google.com/calendar/render')
      u.searchParams.set('action', 'TEMPLATE')
      u.searchParams.set('text', text)
      u.searchParams.set('details', details)
      u.searchParams.set('dates', dates)
      window.open(u.toString(), '_blank', 'noopener,noreferrer')
    } catch (_) {}
  }

  const copyText = async (text) => {
    try {
      const v = String(text || '')
      if (!v) return
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(v)
      } else {
        const ta = document.createElement('textarea')
        ta.value = v
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        ta.remove()
      }
    } catch (_) {}
  }

  const submit = async () => {
    setSubmitError('')
    setSuccess(false)
    setConfirmOpen(false)

    if (!canSubmit) {
      setSubmitError(tt('booking_premium_fill_fields_error'))
      return
    }

    setSubmitLoading(true)

    try {
      const url = new URL(buildApiUrl(apiBase, '/appointments'), window.location.origin)
      if (apiSlug) url.searchParams.set('slug', apiSlug)

      const serviceIdInt = Number.parseInt(String(serviceId), 10)
      const professionalIdInt = Number.parseInt(String(slotProfessionalId), 10)
      if (!Number.isFinite(serviceIdInt) || serviceIdInt <= 0) {
        setSubmitError(tt('booking_premium_invalid_service'))
        return
      }
      if (!Number.isFinite(professionalIdInt) || professionalIdInt <= 0) {
        setSubmitError(tt('booking_premium_invalid_slot'))
        return
      }

      const payload = {
        service_id: serviceIdInt,
        date: String(selectedDate),
        start_time: String(slotTime),
        professional_id: professionalIdInt,
        channel: 'landing',
        customer_name: String(customerName).trim(),
        customer_whatsapp: String(customerWhatsapp).trim(),
        customer_lang: uiLang,
      }

      const created = await fetchJson(url.toString(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        timeoutMs: 12000,
        retries: 0,
      })

      const prof = professionals.find((p) => String(p?.id) === String(slotProfessionalId))
      const profName = String((prof && (prof.name || prof.nome)) || '').trim()
      const startDt = parseLocalDateTime(selectedDate, slotTime)

      const bizPhone = String(
        (business && (business.whatsapp_booking || business.whatsapp || business.telefone || business.phone)) ||
          (cfg && cfg.business && (cfg.business.whatsapp_booking || cfg.business.whatsapp || cfg.business.telefone || cfg.business.phone)) ||
          ''
      ).trim()

      const now = new Date()
      const minsUntil = startDt ? Math.max(0, Math.round((startDt.getTime() - now.getTime()) / 60000)) : 0
      const expiresInMinutes = minsUntil > 0 ? Math.min(240, minsUntil) : 240

      // The visitor may browse in a different language, but the message that reaches the
      // establishment should be in the establishment's primary language.
      const businessPrimaryLang = normalizeUiLang(
        (business && (business.idioma_padrao || business.lang || business.language)) || uiLang || DEFAULT_LANG
      )
      const visitorLang = normalizeUiLang(uiLang)
      let waText = buildWhatsAppConfirmText({
        uiLang: businessPrimaryLang,
        businessName,
        serviceName: String(selectedService?.name || '').trim(),
        professionalName: profName,
        dateISO: String(selectedDate),
        timeHHMM: String(slotTime),
        customerName: String(customerName).trim(),
        expiresInMinutes: minsUntil < 24 * 60 ? expiresInMinutes : 0,
      })

      if (visitorLang && businessPrimaryLang && visitorLang !== businessPrimaryLang) {
        const visitorLabel = (
          visitorLang === 'pt-BR' ? 'PT' :
          visitorLang === 'en' ? 'EN' :
          visitorLang === 'es' ? 'ES' :
          visitorLang === 'fr' ? 'FR' :
          visitorLang === 'ca' ? 'CA' :
          visitorLang
        )

        let note = ''
        if (businessPrimaryLang === 'es') note = `\n\nNota: el cliente vio el booking en ${visitorLabel}.`
        else if (businessPrimaryLang === 'en') note = `\n\nNote: customer viewed the booking in ${visitorLabel}.`
        else if (businessPrimaryLang === 'fr') note = `\n\nNote : le client a vu le booking en ${visitorLabel}.`
        else if (businessPrimaryLang === 'ca') note = `\n\nNota: el client va veure el booking en ${visitorLabel}.`
        else note = `\n\nObs: cliente viu o booking em ${visitorLabel}.`

        waText = String(waText || '') + note
      }
      const waLink = buildWhatsAppLink(bizPhone, waText)
      const waBase = buildWhatsAppBaseLink(bizPhone)

      setConfirmData({
        businessName,
        slug: apiSlug,
        service: selectedService,
        professionalName: profName,
        date: String(selectedDate),
        time: String(slotTime),
        startDt,
        schedule: buildReminderSchedule({ startDt, created }),
        customerName: String(customerName).trim(),
        customerWhatsapp: String(customerWhatsapp).trim(),
        businessWhatsapp: bizPhone,
        whatsappText: waText,
        whatsappLink: waLink,
        whatsappBaseLink: waBase,
        created,
      })
      setConfirmOpen(true)

      setSuccess(true)
      setStep('service')
    } catch (e) {
      const info = _getTrialExpiredInfo(e)
      if (info) {
        setTrialExpired(info)
        setError('')
        setSubmitError('')
        return
      }
      const status = e && typeof e.status !== 'undefined' ? ` (${e.status})` : ''
      const rawDetail = e && e.body && (e.body.detail || e.body.message) ? (e.body.detail || e.body.message) : ''

      const prettyDetail = (() => {
        if (!rawDetail) return ''
        if (typeof rawDetail === 'string') return rawDetail
        if (Array.isArray(rawDetail)) {
          // FastAPI/Pydantic 422 style: [{loc:[...], msg:"...", type:"..."}, ...]
          const parts = rawDetail
            .map((it) => {
              const loc = it && Array.isArray(it.loc) ? it.loc.join('.') : ''
              const msg = it && it.msg ? String(it.msg) : ''
              return [loc, msg].filter(Boolean).join(': ')
            })
            .filter(Boolean)
          return parts.length ? parts.join(' | ') : JSON.stringify(rawDetail)
        }
        try { return JSON.stringify(rawDetail) } catch (_) { return String(rawDetail) }
      })()

      const base = tt('booking_submit_error') || 'Não foi possível enviar o pedido.'
      setSubmitError(prettyDetail ? `${base}${status}: ${prettyDetail}` : `${base}${status}`)
    } finally {
      setSubmitLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="bp-shell" ref={topRef}>
        <div className="bp-card">{tt('booking_loading') || 'Carregando…'}</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bp-shell" ref={topRef}>
        <div className="bp-card bp-error">{error}</div>
      </div>
    )
  }

  if (trialExpired) {
    const bizPhone = String(
      (business && (business.whatsapp_booking || business.whatsapp || business.telefone || business.phone)) ||
        (cfg && cfg.business && (cfg.business.whatsapp_booking || cfg.business.whatsapp || cfg.business.telefone || cfg.business.phone)) ||
        ''
    ).trim()
    const waBase = buildWhatsAppBaseLink(bizPhone)

    return (
      <div className="bp-shell" ref={topRef}>
        <div className="bp-card bp-error">
          <div style={{ fontWeight: 950, marginBottom: 6 }}>{tt('booking_trial_expired_title') || 'Agendamento online indisponível'}</div>
          <div style={{ opacity: 0.92 }}>{tt('booking_trial_expired_body') || 'Este estabelecimento não está aceitando novos agendamentos online no momento. Fale com o salão para agendar.'}</div>
          <div className="bp-actions">
            {waBase ? (
              <a className="bp-cta" href={waBase} target="_blank" rel="noopener noreferrer">
                {tt('booking_trial_expired_cta_whatsapp') || 'Falar no WhatsApp'}
              </a>
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bp-shell" ref={topRef}>
      {confirmOpen && confirmData ? (
        <div className="bp-modal-overlay" role="dialog" aria-modal="true" aria-label={tt('booking_confirm_title') || 'Confirmar pedido'}>
          <div className="bp-modal" role="document">
            <div className="bp-modal-header">
              <div>
                <div className="bp-modal-title">{tt('booking_success_modal_title') || 'Agendamento recebido'}</div>
                <div className="bp-modal-sub">{tt('booking_success_modal_body') || ''}</div>
              </div>
              <button type="button" className="bp-modal-x" onClick={() => setConfirmOpen(false)} aria-label="Fechar">✕</button>
            </div>

            <div className="bp-modal-body">
              <div className="bp-modal-kv">
                <div><span>{tt('booking_premium_kv_business')}</span><b>{String(confirmData.businessName || '')}</b></div>
                <div><span>{tt('booking_premium_kv_service')}</span><b>{String(confirmData.service?.name || '') || '—'}</b></div>
                <div><span>{tt('booking_premium_kv_professional')}</span><b>{String(confirmData.professionalName || '') || (String(professionalId || '').trim() ? '—' : (tt('booking_prof_any') || 'Qualquer profissional'))}</b></div>
                <div><span>{tt('booking_premium_kv_datetime')}</span><b>{confirmData.startDt ? formatDateTime(uiLang, confirmData.startDt) : `${confirmData.date} ${confirmData.time}`}</b></div>
              </div>

              <div className="bp-modal-section">
                <div className="bp-modal-section-title">{tt('booking_confirm_timeline_title') || 'Linha do tempo da confirmação'}</div>
                <div className="bp-modal-hint">{tt('booking_premium_calendar_hint')}</div>
                <div className="bp-modal-timeline">
                  {Array.isArray(confirmData.schedule) ? confirmData.schedule.map((it, idx) => (
                    <div key={idx} className="bp-modal-timeline-item">
                      <div className="bp-pill">{it.channel}</div>
                      <div className="bp-modal-timeline-main">
                        <div className="bp-modal-timeline-label">{tt(it.labelKey) || it.labelKey}</div>
                        <div className="bp-modal-timeline-when">{formatDateTime(uiLang, it.when)}</div>
                      </div>
                    </div>
                  )) : null}
                </div>
              </div>

              <div className="bp-modal-actions">
                {confirmData.whatsappLink ? (
                  <a className="bp-btn" href={confirmData.whatsappLink}>{tt('booking_success_confirm_now') || 'Confirmar agora no WhatsApp'}</a>
                ) : (
                  <button type="button" className="bp-btn" onClick={() => copyText(confirmData.whatsappText)}>{tt('booking_premium_copy_whatsapp') || 'Copiar mensagem do WhatsApp'}</button>
                )}
                <button type="button" className="bp-btn" onClick={() => openGoogleCalendar(confirmData)}>{tt('booking_success_add_calendar') || 'Adicionar ao calendário'}</button>
                <button type="button" className="bp-btn" onClick={() => downloadIcs(confirmData)}>{tt('booking_premium_download_ics') || 'Baixar .ics'}</button>
                <button type="button" className="bp-cta" onClick={() => setConfirmOpen(false)}>{tt('booking_success_close') || 'Entendi'}</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <header className="bp-hero">
        <div className="bp-hero-left">
          <div className="bp-brand">{businessName}</div>
          <div className="bp-title">{premiumTitle}</div>
          <div className="bp-sub">{tt('booking_premium_sub')}</div>
          <div className="bp-badges">
            <span className="bp-badge">{tt('booking_badge_secure')}</span>
            <span className="bp-badge">{tt('booking_badge_instant')}</span>
            <span className="bp-badge">{tt('booking_badge_premium')}</span>
          </div>
        </div>
        <div className="bp-hero-right">
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(15,23,42,0.25)' }}>
              <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.88)' }}>{tt('language') || 'Language'}</span>
              <select
                aria-label={tt('language') || 'Language'}
                value={bookingLangSelectValue}
                onChange={(e) => setBookingLangSafe(e.target.value)}
                style={{
                  fontSize: 12,
                  fontWeight: 800,
                  borderRadius: 999,
                  border: '1px solid rgba(255,255,255,0.22)',
                  background: 'rgba(255,255,255,0.10)',
                  color: '#fff',
                  padding: '4px 10px',
                  outline: 'none',
                  cursor: 'pointer',
                }}
              >
                <option value="" style={{ color: '#0b1220' }}>
                  Auto ({(LANGS.find((l) => l.code === normalizeLangCode(business?.idioma_padrao))?.label) || (LANGS.find((l) => l.code === uiLang)?.label) || '—'})
                </option>
                {LANGS.map((l) => (
                  <option key={l.code} value={l.code} style={{ color: '#0b1220' }}>{l.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="bp-photo" aria-hidden="true">
            <div className="bp-photo-glow" />
            <div className="bp-photo-inner">
              {heroUrl ? (
                <img className="bp-photo-img" src={heroUrl} alt="" />
              ) : (
                <div className="bp-photo-initials">{getInitials(businessName)}</div>
              )}
            </div>
          </div>
          <div className="bp-meta">
            <div><b>{tt('booking_slug') || 'Slug'}:</b> {apiSlug}</div>
          </div>
        </div>
      </header>

      {looksLikePlaceholderSlug(routeSlug) ? (
        <div className="bp-card bp-warn">
          {tt('booking_premium_placeholder_slug')}
        </div>
      ) : null}

      {success ? (
        <div className="bp-card bp-success">{tt('booking_success_title') || 'Pedido enviado'}</div>
      ) : null}

      <div className="bp-grid">
        <section className="bp-card">
          <div className="bp-card-title">{tt('booking_step_service') || '1) Serviço'}</div>
          <div className="bp-list">
            {services.map((s) => {
              const active = String(s?.id) === String(serviceId)
              const price = (typeof s?.price_cents === 'number') ? formatMoney(uiLang, s.price_cents, currency) : ''
              const duration = s?.duration_min ? `${s.duration_min} min` : ''
              return (
                <button
                  key={String(s.id)}
                  type="button"
                  className={`bp-item ${active ? 'active' : ''}`}
                  onClick={() => onSelectService(s.id)}
                >
                  <div className="bp-item-main">
                    <div className="bp-item-title">{s.name}</div>
                    <div className="bp-item-sub">{duration}{duration && price ? ' · ' : ''}{price}</div>
                  </div>
                  <div className="bp-item-right">{active ? '✓' : '›'}</div>
                </button>
              )
            })}
          </div>
        </section>

        <section className="bp-card">
          <div className="bp-card-title">{tt('booking_step_professional') || '2) Profissional'}</div>
          <div className="bp-list">
            <button
              type="button"
              className={`bp-item ${professionalId === '' ? 'active' : ''}`}
              onClick={() => onSelectProfessional('')}
              disabled={!serviceId}
            >
              <div className="bp-item-main">
                <div className="bp-item-title">{tt('booking_prof_any') || 'Qualquer profissional'}</div>
                <div className="bp-item-sub">{tt('booking_prof_any_sub') || 'Escolhemos o melhor horário disponível.'}</div>
              </div>
              <div className="bp-item-right">{professionalId === '' ? '✓' : '›'}</div>
            </button>

            {professionals.map((p) => {
              const pid = String(p?.id)
              const active = pid === String(professionalId)
              const name = String(p?.name || p?.nome || '').trim() || '—'
              return (
                <button
                  key={pid}
                  type="button"
                  className={`bp-item ${active ? 'active' : ''}`}
                  onClick={() => onSelectProfessional(pid)}
                  disabled={!serviceId}
                >
                  <div className="bp-avatar" aria-hidden="true">{getInitials(name)}</div>
                  <div className="bp-item-main">
                    <div className="bp-item-title">{name}</div>
                    <div className="bp-item-sub">{active ? (tt('staff_selected') || 'selecionado') : (tt('booking_premium_view_days') || 'Ver dias disponíveis')}</div>
                  </div>
                  <div className="bp-item-right">{active ? '✓' : '›'}</div>
                </button>
              )
            })}
          </div>
        </section>

        <section className="bp-card">
          <div className="bp-card-title">{tt('booking_step_date') || '3) Data'}</div>

          {!serviceId ? (
            <div className="bp-muted">{tt('booking_premium_pick_service_first')}</div>
          ) : availableDatesLoading ? (
            <div className="bp-muted">{tt('booking_premium_loading_days')}</div>
          ) : availableDates.length ? (
            <>
              <div className="bp-date-row">
                {visibleDates.map((d) => {
                  const active = String(selectedDate) === String(d)
                  return (
                    <button
                      key={d}
                      type="button"
                      className={`bp-date ${active ? 'active' : ''}`}
                      onClick={() => onSelectDate(d)}
                    >
                      <div className="bp-date-wd">{formatWeekday(uiLang, d, businessTz)}</div>
                      <div className="bp-date-dm">{formatDM(uiLang, d, businessTz)}</div>
                    </button>
                  )
                })}
              </div>
            </>
          ) : (
            <>
              <div className="bp-muted">{tt('booking_premium_no_days_fmt').replace('{days}', String(dateChoices.length))}</div>
            </>
          )}
        </section>

        <section className="bp-card bp-span2">
          <div className="bp-card-title">{tt('booking_step_time') || '4) Horário'}</div>

          {showTzHint ? (
            <div className="bp-hint" style={{ marginTop: 8 }}>
              Horários no fuso do estabelecimento: <b>{businessTz}</b> (seu dispositivo: {deviceTz}).
            </div>
          ) : null}

          {!serviceId ? (
            <div className="bp-muted">{tt('booking_premium_pick_service')}</div>
          ) : !selectedDate ? (
            <div className="bp-muted">{tt('booking_premium_pick_day')}</div>
          ) : availabilityLoading ? (
            <div className="bp-muted">{tt('booking_slots_loading') || 'Carregando horários…'}</div>
          ) : slotsForUI.length ? (
            <div className="bp-slots">
              {slotsForUI.map((s) => {
                const key = `${s.professional_id}-${s.time}`
                const active = String(slotTime) === String(s.time) && String(slotProfessionalId) === String(s.professional_id)
                return (
                  <button
                    key={key}
                    type="button"
                    className={`bp-slot ${active ? 'active' : ''}`}
                    onClick={() => onSelectSlot(s)}
                  >
                    <div className="bp-slot-time">{s.time}</div>
                    <div className="bp-slot-prof">{professionalId ? '' : s.professional_name}</div>
                  </button>
                )
              })}
            </div>
          ) : (
            <div className="bp-muted">{tt('booking_slots_none') || 'Sem horários disponíveis para este dia.'}</div>
          )}
        </section>

        <section className="bp-card bp-span2">
          <div className="bp-card-title">{tt('booking_step_contact') || '5) Seus dados'}</div>

          <div className="bp-form">
            <div className="bp-field">
              <label>{tt('booking_customer_name') || 'Seu nome'}</label>
              <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder={tt('booking_customer_name_ph') || ''} />
            </div>
            <div className="bp-field">
              <label>{tt('clients_phone') || 'Telefone'}</label>
              <input value={customerWhatsapp} onChange={(e) => setCustomerWhatsapp(e.target.value)} placeholder={tt('booking_customer_whatsapp_ph') || ''} />
            </div>
          </div>

          {submitError ? <div className="bp-inline-error">{submitError}</div> : null}

          <div className="bp-actions">
            <button type="button" className="bp-cta" onClick={submit} disabled={submitLoading || !canSubmit}>
              {submitLoading ? (tt('booking_premium_confirming') || 'Confirmando…') : (tt('booking_confirm_cta') || 'Confirmar e enviar')}
            </button>
          </div>
        </section>
      </div>

      <footer className="bp-footer">
        <button type="button" className="bp-link" onClick={() => navigate('/booking/' + encodeURIComponent(apiSlug))}>
          {tt('notif_refresh') || 'Recarregar'}
        </button>
      </footer>
    </div>
  )
}
