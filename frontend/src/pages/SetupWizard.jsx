import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Header from '../components/dashboard/Header'
import BookingShareCard from '../components/dashboard/BookingShareCard'
import API from '../utils/api'
import '../components/dashboard/dashboard.css'
import { Card, Callout, KpiCard } from '../components/ui/Premium'

function slugify(input) {
  return String(input || '')
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

function defaultAdminConfig() {
  return {
    business: {
      nome: '',
      telefone: '',
      slug: '',
      email: '',
      idioma_padrao: 'es-ES',
      lembrete_horas_antes: [24, 3],
      horario_inicio: 9,
      horario_fim: 18,
      photos: [],
      reviews: [],
    },
    services: [
      { name: 'Corte', duration_min: 30, buffer_min: 0, price_cents: 3000, display_interval_min: 30 },
    ],
    professionals: [
      { name: 'Ana', telefone: '000000000', },
    ],
  }
}

function defaultSetupPayload() {
  return {
    version: 1,
    business: {
      country: 'ES',
      timezone: 'Europe/Madrid',
      currency: 'EUR',
      address: '',
      instagram: '',
      website: '',
      whatsapp_booking: '',
      breakStartHour: 12,
      breakEndHour: 13,
      openDays: {
        monday: true,
        tuesday: true,
        wednesday: true,
        thursday: true,
        friday: true,
        saturday: true,
        sunday: false,
      },
      // Horários por dia (permite sábado/domingo diferentes)
      openingHours: {
        monday: { active: true, open: '09:00', close: '18:00' },
        tuesday: { active: true, open: '09:00', close: '18:00' },
        wednesday: { active: true, open: '09:00', close: '18:00' },
        thursday: { active: true, open: '09:00', close: '18:00' },
        friday: { active: true, open: '09:00', close: '18:00' },
        saturday: { active: true, open: '09:00', close: '18:00' },
        sunday: { active: false, open: '09:00', close: '18:00' },
      },
      holidays: [],
    },
    booking: {
      leadTimeMinutes: 60,
      slotIntervalMinutes: 30,
      globalBufferMinutes: 0,
      allowSameDay: true,
      allowReschedule: true,
      allowCancel: true,
    },
    policies: {
      depositEnabled: true,
      depositPercent: 50,
      cancellationWindowHours: 24,
      // Regra fixa: depósito 50% do valor do serviço.
      // Em no-show: reter 15% (do valor do serviço) e reembolsar 35% (do valor do serviço).
      // Split interno do retido: 7% plataforma / 8% estabelecimento.
      noShowPolicy: 'Depósito ativo (50%): em caso de no-show, será retido 15% do valor do serviço e reembolsado 35% do valor do serviço.',
      noShowRetainPercentOfService: 15,
      noShowRefundPercentOfService: 35,
      platformSharePercentOfService: 7,
      establishmentSharePercentOfService: 8,
      latePolicy: 'Tolerância 10 minutos',
    },
    notifications: {
      channels: { whatsapp: true, sms: false, email: false },
      // fixo: profissional, humano, educado (sem emojis)
      tone: 'profissional',
      // Regra operacional: só 24h ou 36h
      confirmationRuleHours: 24,
      reminderHours: [24, 3],
    },
    capacity: {
      // usado para classificar dias como Livre/Moderado/Cheio no dashboard
      appointmentsPerDayDefault: 8,
      // chave por nome do profissional (case-insensitive no backend)
      perProfessional: {},
    },
    team: {
      // preferências por profissional (nome como chave)
      perProfessional: {},
    },
    mapping: {
      // future: serviceId -> professionalIds
      serviceToProfessionals: {},
    },
  }
}

function mergeDeep(base, patch) {
  if (!patch || typeof patch !== 'object') return base
  const out = Array.isArray(base) ? [...base] : { ...(base || {}) }
  for (const [k, v] of Object.entries(patch)) {
    if (v && typeof v === 'object' && !Array.isArray(v) && base && typeof base[k] === 'object' && !Array.isArray(base[k])) {
      out[k] = mergeDeep(base[k], v)
    } else {
      out[k] = v
    }
  }
  return out
}

export default function SetupWizard() {
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  const [holidayToAdd, setHolidayToAdd] = useState('')

  const [token, setToken] = useState(() => {
    try { return localStorage.getItem('ea_dev_token') || '' } catch (_) { return '' }
  })

  const [adminConfig, setAdminConfig] = useState(() => defaultAdminConfig())
  const [setupPayload, setSetupPayload] = useState(() => defaultSetupPayload())

  const COUNTRY_OPTIONS = useMemo(() => (
    [
      { code: 'BR', label: 'Brasil', currency: 'BRL', timezones: ['America/Sao_Paulo', 'America/Fortaleza', 'America/Recife'] },
      { code: 'PT', label: 'Portugal', currency: 'EUR', timezones: ['Europe/Lisbon'] },
      { code: 'ES', label: 'Espanha', currency: 'EUR', timezones: ['Europe/Madrid'] },
      { code: 'FR', label: 'França', currency: 'EUR', timezones: ['Europe/Paris'] },
      { code: 'GB', label: 'Reino Unido', currency: 'GBP', timezones: ['Europe/London'] },
      { code: 'AR', label: 'Argentina', currency: 'ARS', timezones: ['America/Argentina/Buenos_Aires'] },
      { code: 'CL', label: 'Chile', currency: 'CLP', timezones: ['America/Santiago'] },
      { code: 'CO', label: 'Colômbia', currency: 'COP', timezones: ['America/Bogota'] },
      { code: 'PE', label: 'Peru', currency: 'PEN', timezones: ['America/Lima'] },
    ]
  ), [])

  const currencyOptions = useMemo(() => {
    const base = ['BRL', 'EUR', 'USD', 'GBP', 'ARS', 'CLP', 'COP', 'PEN']
    const system = Array.from(new Set([
      ...((COUNTRY_OPTIONS || []).map((c) => c.currency).filter(Boolean)),
      ...base,
    ]))

    const country = setupPayload?.business?.country || 'BR'
    const recommended = (COUNTRY_OPTIONS || []).find((x) => x.code === country)?.currency
    if (recommended) return [recommended, ...system.filter((c) => c !== recommended)]
    return system
  }, [COUNTRY_OPTIONS, setupPayload?.business?.country])

  function currencyLabel(code) {
    const c = String(code || '').toUpperCase()
    const map = {
      BRL: 'R$',
      EUR: '€',
      USD: '$',
      GBP: '£',
      ARS: '$',
      CLP: '$',
      COP: '$',
      PEN: 'S/',
    }
    const sym = map[c]
    return sym ? `${c} (${sym})` : c
  }

  const steps = useMemo(() => ([
    { key: 'business', title: 'Negócio' },
    { key: 'hours', title: 'Horários' },
    { key: 'services', title: 'Serviços' },
    { key: 'team', title: 'Equipe' },
    { key: 'policies', title: 'Políticas' },
    { key: 'notifications', title: 'Notificações' },
    { key: 'import', title: 'Integrar agenda' },
    { key: 'review', title: 'Revisão & Salvar' },
  ]), [])

  // ----------------------------
  // Import agenda (.ics) helpers
  // ----------------------------
  const [importProfessionalId, setImportProfessionalId] = useState(null)
  const [importServiceId, setImportServiceId] = useState('')
  const [importFile, setImportFile] = useState(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importErr, setImportErr] = useState(null)
  const [importPreview, setImportPreview] = useState(null)
  const [importEdits, setImportEdits] = useState({})
  const [importCommitting, setImportCommitting] = useState(false)
  const [importCommitResult, setImportCommitResult] = useState(null)

  const [importIcalUrl, setImportIcalUrl] = useState('')
  const [importIcalLoading, setImportIcalLoading] = useState(false)
  const [importIcalErr, setImportIcalErr] = useState(null)
  const [importIcalPreview, setImportIcalPreview] = useState(null)

  const [clientsCsvFile, setClientsCsvFile] = useState(null)
  const [clientsCsvLoading, setClientsCsvLoading] = useState(false)
  const [clientsCsvErr, setClientsCsvErr] = useState(null)
  const [clientsCsvPreview, setClientsCsvPreview] = useState(null)
  const [clientsCsvCommitting, setClientsCsvCommitting] = useState(false)
  const [clientsCsvCommitResult, setClientsCsvCommitResult] = useState(null)

  function downloadClientsCsvTemplate() {
    const content = 'nome;whatsapp;idioma;observacoes\nMaria;+34123456789;es-ES;Cliente VIP\nJoão;+5511999999999;pt-BR;Prefere manhã\n'
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'easyagenda_clientes_modelo.csv'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 500)
  }

  function getAuthToken() {
    try {
      return token || localStorage.getItem('ea_dev_token') || localStorage.getItem('DEV_JWT_TOKEN') || localStorage.getItem('token') || ''
    } catch (_) {
      return token || ''
    }
  }

  async function previewIcs() {
    setImportCommitResult(null)
    setImportErr(null)
    setImportPreview(null)
    setImportEdits({})

    if (!importFile) {
      setImportErr('Selecione um arquivo .ics para analisar.')
      return
    }
    if (!importProfessionalId) {
      setImportErr('Selecione um profissional para vincular esta importação.')
      return
    }

    const apiBase = (typeof window !== 'undefined' && window.__API_URL__) ? window.__API_URL__ : 'http://127.0.0.1:8000'
    const url = apiBase.replace(/\/$/, '') + '/admin/import/ics/preview'

    const fd = new FormData()
    fd.append('file', importFile)
    fd.append('professional_id', String(importProfessionalId))
    if (importServiceId) fd.append('service_id', String(importServiceId))

    setImportLoading(true)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          Authorization: 'Bearer ' + getAuthToken(),
        },
        body: fd,
      })

      let body = null
      try { body = await res.json() } catch (_) { body = null }
      if (!res.ok) {
        const detail = body && (body.detail || body.message) ? (body.detail || body.message) : ('HTTP ' + res.status)
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }
      setImportPreview(body)
    } catch (e) {
      setImportErr(String(e?.message || e))
    } finally {
      setImportLoading(false)
    }
  }

  function editImportItem(idx, patch) {
    setImportEdits((prev) => {
      const next = { ...(prev || {}) }
      next[String(idx)] = { ...(next[String(idx)] || {}), ...(patch || {}) }
      return next
    })
  }

  async function commitIcs() {
    setImportErr(null)
    setImportCommitResult(null)
    if (!importPreview || !Array.isArray(importPreview.items)) {
      setImportErr('Nenhuma prévia carregada.')
      return
    }
    if (!importProfessionalId) {
      setImportErr('Selecione um profissional.')
      return
    }

    const items = (importPreview.items || []).map((it, idx) => {
      const ed = importEdits[String(idx)] || {}
      return {
        uid: it.uid,
        summary: it.summary,
        start_local: it.start_local,
        end_local: it.end_local,
        customer_name: (ed.customer_name != null ? ed.customer_name : it.customer_name) || '',
        customer_whatsapp: (ed.customer_whatsapp != null ? ed.customer_whatsapp : it.customer_whatsapp) || '',
      }
    })

    const apiBase = (typeof window !== 'undefined' && window.__API_URL__) ? window.__API_URL__ : 'http://127.0.0.1:8000'
    const url = apiBase.replace(/\/$/, '') + '/admin/import/ics/commit'

    setImportCommitting(true)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + getAuthToken(),
        },
        body: JSON.stringify({
          professional_id: Number(importProfessionalId),
          service_id: importServiceId ? Number(importServiceId) : null,
          items,
        }),
      })

      let body = null
      try { body = await res.json() } catch (_) { body = null }
      if (!res.ok) {
        const detail = body && (body.detail || body.message) ? (body.detail || body.message) : ('HTTP ' + res.status)
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }
      setImportCommitResult(body)
    } catch (e) {
      setImportErr(String(e?.message || e))
    } finally {
      setImportCommitting(false)
    }
  }

  async function previewIcalUrl() {
    setImportIcalErr(null)
    setImportIcalPreview(null)

    if (!importIcalUrl || !String(importIcalUrl).trim()) {
      setImportIcalErr('Cole o link iCal (https://...) para analisar.')
      return
    }
    if (!importProfessionalId) {
      setImportIcalErr('Selecione um profissional para vincular esta importação.')
      return
    }

    const apiBase = (typeof window !== 'undefined' && window.__API_URL__) ? window.__API_URL__ : 'http://127.0.0.1:8000'
    const url = apiBase.replace(/\/$/, '') + '/admin/import/ics/preview-url'

    setImportIcalLoading(true)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + getAuthToken(),
        },
        body: JSON.stringify({
          url: String(importIcalUrl).trim(),
          professional_id: Number(importProfessionalId),
          service_id: importServiceId ? Number(importServiceId) : null,
        }),
      })

      let body = null
      try { body = await res.json() } catch (_) { body = null }
      if (!res.ok) {
        const detail = body && (body.detail || body.message) ? (body.detail || body.message) : ('HTTP ' + res.status)
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }
      setImportIcalPreview(body)
    } catch (e) {
      setImportIcalErr(String(e?.message || e))
    } finally {
      setImportIcalLoading(false)
    }
  }

  async function previewClientsCsv() {
    setClientsCsvErr(null)
    setClientsCsvPreview(null)
    setClientsCsvCommitResult(null)

    if (!clientsCsvFile) {
      setClientsCsvErr('Selecione um arquivo CSV para analisar.')
      return
    }

    const apiBase = (typeof window !== 'undefined' && window.__API_URL__) ? window.__API_URL__ : 'http://127.0.0.1:8000'
    const url = apiBase.replace(/\/$/, '') + '/admin/import/clients-csv/preview'

    const fd = new FormData()
    fd.append('file', clientsCsvFile)

    setClientsCsvLoading(true)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          Authorization: 'Bearer ' + getAuthToken(),
        },
        body: fd,
      })

      let body = null
      try { body = await res.json() } catch (_) { body = null }
      if (!res.ok) {
        const detail = body && (body.detail || body.message) ? (body.detail || body.message) : ('HTTP ' + res.status)
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }
      setClientsCsvPreview(body)
    } catch (e) {
      setClientsCsvErr(String(e?.message || e))
    } finally {
      setClientsCsvLoading(false)
    }
  }

  async function commitClientsCsv() {
    setClientsCsvErr(null)
    setClientsCsvCommitResult(null)
    if (!clientsCsvPreview || !Array.isArray(clientsCsvPreview.items) || !clientsCsvPreview.items.length) {
      setClientsCsvErr('Nenhuma prévia de CSV carregada.')
      return
    }

    const apiBase = (typeof window !== 'undefined' && window.__API_URL__) ? window.__API_URL__ : 'http://127.0.0.1:8000'
    const url = apiBase.replace(/\/$/, '') + '/admin/import/clients-csv/commit'

    setClientsCsvCommitting(true)
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + getAuthToken(),
        },
        body: JSON.stringify({ items: clientsCsvPreview.items }),
      })

      let body = null
      try { body = await res.json() } catch (_) { body = null }
      if (!res.ok) {
        const detail = body && (body.detail || body.message) ? (body.detail || body.message) : ('HTTP ' + res.status)
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }
      setClientsCsvCommitResult(body)
    } catch (e) {
      setClientsCsvErr(String(e?.message || e))
    } finally {
      setClientsCsvCommitting(false)
    }
  }

  const weekdayOptions = useMemo(() => ([
    { key: 'monday', label: 'Seg' },
    { key: 'tuesday', label: 'Ter' },
    { key: 'wednesday', label: 'Qua' },
    { key: 'thursday', label: 'Qui' },
    { key: 'friday', label: 'Sex' },
    { key: 'saturday', label: 'Sáb' },
    { key: 'sunday', label: 'Dom' },
  ]), [])

  function WeekdayToggle({ valueMap, onToggle, ariaLabel }) {
    return (
      <div className="weekday-toggle" role="group" aria-label={ariaLabel || 'Dias da semana'}>
        {weekdayOptions.map((w) => {
          const active = !!(valueMap && valueMap[w.key])
          return (
            <button
              key={w.key}
              type="button"
              className={`weekday-pill ${active ? 'active' : ''}`}
              aria-pressed={active}
              onClick={() => onToggle && onToggle(w.key, !active)}
              title={w.label}
            >
              {w.label}
            </button>
          )
        })}
      </div>
    )
  }

  async function loadAll(mountedRef) {
      setLoading(true)
      setError(null)
      try {
        const [cfg, setup] = await Promise.all([
          API.get('/admin/config'),
          API.get('/admin/setup').catch(() => ({ ok: true, exists: false, payload: null })),
        ])

        if (mountedRef && !mountedRef.current) return

        const normalizedCfg = (cfg && cfg.business) ? cfg : defaultAdminConfig()
        setAdminConfig(normalizedCfg)

        const mergedSetup = mergeDeep(defaultSetupPayload(), setup && setup.payload ? setup.payload : {})

        // Normalizar horários por dia (openingHours) e openDays
        try {
          const biz = (mergedSetup && mergedSetup.business && typeof mergedSetup.business === 'object') ? { ...mergedSetup.business } : {}
          const weekdays = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
          const defaultOpen = `${String(normalizedCfg?.business?.horario_inicio ?? 9).padStart(2,'0')}:00`
          const defaultClose = `${String(normalizedCfg?.business?.horario_fim ?? 18).padStart(2,'0')}:00`

          function normTime(v, fallback) {
            const s = String(v || '').trim()
            if (/^\d{2}:\d{2}$/.test(s)) return s
            // accept "9:00" style
            if (/^\d{1,2}:\d{2}$/.test(s)) {
              const [hh, mm] = s.split(':')
              return `${String(hh).padStart(2,'0')}:${mm}`
            }
            return fallback
          }

          const incomingOH = (biz.openingHours && typeof biz.openingHours === 'object') ? biz.openingHours : null
          const incomingOD = (biz.openDays && typeof biz.openDays === 'object') ? biz.openDays : null

          const nextOH = {}
          for (const day of weekdays) {
            const fromOH = incomingOH && incomingOH[day] && typeof incomingOH[day] === 'object' ? incomingOH[day] : null
            const active = (fromOH && typeof fromOH.active === 'boolean')
              ? fromOH.active
              : (incomingOD && typeof incomingOD[day] === 'boolean')
                ? incomingOD[day]
                : (day !== 'sunday')
            nextOH[day] = {
              active,
              open: normTime(fromOH ? fromOH.open : null, defaultOpen),
              close: normTime(fromOH ? fromOH.close : null, defaultClose),
            }
          }

          const nextOD = {}
          for (const day of weekdays) nextOD[day] = !!(nextOH[day] && nextOH[day].active)

          mergedSetup.business = { ...biz, openingHours: nextOH, openDays: nextOD }
        } catch (_) {}

        // Forçar canal e-mail desativado (não enviaremos lembretes via e-mail)
        try {
          const ch = (mergedSetup.notifications && mergedSetup.notifications.channels) ? { ...mergedSetup.notifications.channels } : {}
          ch.email = false
          mergedSetup.notifications = { ...(mergedSetup.notifications || {}), channels: ch }
        } catch (_) {}

        // Depósito é fixo em 50% quando ativo
        try {
          const pol = mergedSetup.policies ? { ...mergedSetup.policies } : {}
          if (pol.depositEnabled) pol.depositPercent = 50
          mergedSetup.policies = pol
        } catch (_) {}
        setSetupPayload(mergedSetup)

        // ensure business slug derived if missing
        if (!normalizedCfg.business.slug && normalizedCfg.business.nome) {
          setAdminConfig((prev) => ({
            ...prev,
            business: { ...prev.business, slug: slugify(prev.business.nome) },
          }))
        }
      } catch (e) {
        if (mountedRef && !mountedRef.current) return
        setError('Não consegui carregar /admin/config. Cole um token admin (JWT) e clique em Recarregar.')
      } finally {
        if (!mountedRef || mountedRef.current) setLoading(false)
      }
    }
  useEffect(() => {
    const mountedRef = { current: true }
    loadAll(mountedRef)
    return () => { mountedRef.current = false }
  }, [])

  function updateBusiness(patch) {
    setAdminConfig((prev) => ({ ...prev, business: { ...prev.business, ...patch } }))
  }

  function updateSetup(path, value) {
    setSetupPayload((prev) => {
      const next = { ...prev }
      const parts = path.split('.')
      let cur = next
      for (let i = 0; i < parts.length - 1; i++) {
        const k = parts[i]
        cur[k] = (cur[k] && typeof cur[k] === 'object') ? { ...cur[k] } : {}
        cur = cur[k]
      }
      cur[parts[parts.length - 1]] = value
      return next
    })
  }

  function addService() {
    setAdminConfig((prev) => ({
      ...prev,
      services: [
        ...(prev.services || []),
        { name: '', duration_min: 30, buffer_min: 0, price_cents: 0, display_interval_min: 30 },
      ],
    }))
  }

  function updateService(idx, patch) {
    setAdminConfig((prev) => {
      const next = [...(prev.services || [])]
      next[idx] = { ...next[idx], ...patch }
      return { ...prev, services: next }
    })
  }

  function removeService(idx) {
    setAdminConfig((prev) => {
      const next = [...(prev.services || [])]
      next.splice(idx, 1)
      return { ...prev, services: next }
    })
  }

  function addProfessional() {
    setAdminConfig((prev) => ({
      ...prev,
      professionals: [
        ...(prev.professionals || []),
        { name: '', telefone: '' },
      ],
    }))
  }

  function removeProfessional(idx) {
    setAdminConfig((prev) => {
      const list = [...(prev.professionals || [])]
      const removed = list[idx] || {}
      const removedName = String(removed.name || '').trim()
      list.splice(idx, 1)

      if (removedName) {
        setSetupPayload((sp) => {
          const cap = (sp && sp.capacity) ? sp.capacity : {}
          const per = (cap && cap.perProfessional && typeof cap.perProfessional === 'object') ? { ...cap.perProfessional } : {}
          if (Object.prototype.hasOwnProperty.call(per, removedName)) {
            delete per[removedName]
          }
          return { ...sp, capacity: { ...cap, perProfessional: per } }
        })

        setSetupPayload((sp) => {
          const team = (sp && sp.team) ? sp.team : {}
          const perT = (team && team.perProfessional && typeof team.perProfessional === 'object') ? { ...team.perProfessional } : {}
          if (Object.prototype.hasOwnProperty.call(perT, removedName)) {
            delete perT[removedName]
          }
          return { ...sp, team: { ...team, perProfessional: perT } }
        })
      }

      return { ...prev, professionals: list }
    })
  }

  function updateProfessional(idx, patch) {
    // se renomear profissional, carregar a capacidade junto
    setAdminConfig((prev) => {
      const next = [...(prev.professionals || [])]
      const before = next[idx] || {}
      const after = { ...before, ...patch }
      next[idx] = after

      if (patch && Object.prototype.hasOwnProperty.call(patch, 'name')) {
        const oldName = String(before.name || '').trim()
        const newName = String(after.name || '').trim()
        if (oldName && newName && oldName !== newName) {
          setSetupPayload((sp) => {
            const cap = (sp && sp.capacity) ? sp.capacity : {}
            const per = (cap && cap.perProfessional && typeof cap.perProfessional === 'object') ? { ...cap.perProfessional } : {}
            if (Object.prototype.hasOwnProperty.call(per, oldName) && !Object.prototype.hasOwnProperty.call(per, newName)) {
              per[newName] = per[oldName]
              delete per[oldName]
            }
            return { ...sp, capacity: { ...cap, perProfessional: per } }
          })

          setSetupPayload((sp) => {
            const team = (sp && sp.team) ? sp.team : {}
            const perT = (team && team.perProfessional && typeof team.perProfessional === 'object') ? { ...team.perProfessional } : {}
            if (Object.prototype.hasOwnProperty.call(perT, oldName) && !Object.prototype.hasOwnProperty.call(perT, newName)) {
              perT[newName] = perT[oldName]
              delete perT[oldName]
            }
            return { ...sp, team: { ...team, perProfessional: perT } }
          })
        }
      }

      return { ...prev, professionals: next }
    })
  }

  function updateTeamPerProfessional(profName, patch) {
    const nm = String(profName || '').trim()
    if (!nm) return
    setSetupPayload((sp) => {
      const team = (sp && sp.team) ? sp.team : {}
      const per = (team && team.perProfessional && typeof team.perProfessional === 'object') ? { ...team.perProfessional } : {}
      const cur = (per[nm] && typeof per[nm] === 'object') ? { ...per[nm] } : {}
      per[nm] = { ...cur, ...patch }
      return { ...sp, team: { ...team, perProfessional: per } }
    })
  }

  function getTeamPerProfessional(profName) {
    const nm = String(profName || '').trim()
    if (!nm) return null
    const per = setupPayload?.team?.perProfessional
    if (!per || typeof per !== 'object') return null
    const v = per[nm]
    return (v && typeof v === 'object') ? v : null
  }

  function normalizeHourToHHMM(h) {
    const n = Number(h)
    if (!Number.isFinite(n)) return ''
    const hh = Math.max(0, Math.min(23, Math.floor(n)))
    return String(hh).padStart(2, '0') + ':00'
  }

  function getGlobalBreakWindow() {
    const biz = setupPayload?.business || {}
    const bs = String(biz.breakStart || biz.break_start || '').trim()
    const be = String(biz.breakEnd || biz.break_end || '').trim()
    if (bs && be) return { start: bs, end: be }
    const bsH = biz.breakStartHour
    const beH = biz.breakEndHour
    const s = normalizeHourToHHMM(bsH)
    const e = normalizeHourToHHMM(beH)
    if (s && e && !(s === '00:00' && e === '00:00')) return { start: s, end: e }
    return null
  }

  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result || ''))
      reader.onerror = () => reject(new Error('file_read_failed'))
      reader.readAsDataURL(file)
    })
  }

  async function imageFileToSquareJpegDataUrl(file, { maxSize = 256, quality = 0.86 } = {}) {
    if (!file) return null
    if (file.size > 2 * 1024 * 1024) throw new Error('image_too_large')

    const src = await fileToDataUrl(file)
    const img = new Image()
    img.src = src
    try {
      await img.decode()
    } catch (_) {
      // ignore; some browsers may not support decode
    }

    const w = img.naturalWidth || img.width
    const h = img.naturalHeight || img.height
    if (!w || !h) throw new Error('invalid_image')

    const side = Math.min(w, h)
    const sx = Math.floor((w - side) / 2)
    const sy = Math.floor((h - side) / 2)

    const canvas = document.createElement('canvas')
    canvas.width = maxSize
    canvas.height = maxSize
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('no_canvas')
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'
    ctx.drawImage(img, sx, sy, side, side, 0, 0, maxSize, maxSize)

    return canvas.toDataURL('image/jpeg', quality)
  }

  async function setProfessionalPhoto(profName, file) {
    const nm = String(profName || '').trim()
    if (!nm) return
    if (!file) return
    const dataUrl = await imageFileToSquareJpegDataUrl(file, { maxSize: 256, quality: 0.86 })
    updateTeamPerProfessional(nm, { photoDataUrl: dataUrl })
  }

  function validate() {
    const b = adminConfig.business || {}
    if (!b.nome || !String(b.nome).trim()) return 'Informe o nome do negócio.'
    if (!b.slug || !String(b.slug).trim()) return 'Informe o slug (usado no link do booking).'
    if (!b.telefone || !String(b.telefone).trim()) return 'Informe um telefone/WhatsApp do negócio.'
    if (!adminConfig.services || adminConfig.services.length === 0) return 'Cadastre pelo menos 1 serviço.'
    if (!adminConfig.professionals || adminConfig.professionals.length === 0) return 'Cadastre pelo menos 1 profissional.'
    return null
  }

  async function handleSaveAll() {
    setSuccessMsg(null)
    const err = validate()
    if (err) {
      setError(err)
      return
    }

    setSaving(true)
    setError(null)
    try {
      // Normalizar horários por dia e derivar openDays (para o booking)
      const weekdays = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
      const ohRaw = (setupPayload?.business?.openingHours && typeof setupPayload.business.openingHours === 'object') ? setupPayload.business.openingHours : null
      const odRaw = (setupPayload?.business?.openDays && typeof setupPayload.business.openDays === 'object') ? setupPayload.business.openDays : null
      const defaultOpen = `${String(adminConfig?.business?.horario_inicio ?? 9).padStart(2,'0')}:00`
      const defaultClose = `${String(adminConfig?.business?.horario_fim ?? 18).padStart(2,'0')}:00`

      function normTime(v, fallback) {
        const s = String(v || '').trim()
        if (/^\d{2}:\d{2}$/.test(s)) return s
        if (/^\d{1,2}:\d{2}$/.test(s)) {
          const [hh, mm] = s.split(':')
          return `${String(hh).padStart(2,'0')}:${mm}`
        }
        return fallback
      }

      const openingHours = {}
      const openDays = {}
      for (const day of weekdays) {
        const cur = (ohRaw && ohRaw[day] && typeof ohRaw[day] === 'object') ? ohRaw[day] : null
        const active = (cur && typeof cur.active === 'boolean')
          ? cur.active
          : (odRaw && typeof odRaw[day] === 'boolean')
            ? odRaw[day]
            : (day !== 'sunday')
        openingHours[day] = {
          active,
          open: normTime(cur ? cur.open : null, defaultOpen),
          close: normTime(cur ? cur.close : null, defaultClose),
        }
        openDays[day] = !!active
      }

      // Horário global (fallback) = min/max entre dias ativos
      let horarioInicioFallback = adminConfig?.business?.horario_inicio ?? 9
      let horarioFimFallback = adminConfig?.business?.horario_fim ?? 18
      try {
        let minH = null
        let maxH = null
        for (const day of weekdays) {
          if (!openingHours[day].active) continue
          const [ohh] = String(openingHours[day].open || defaultOpen).split(':')
          const [chh] = String(openingHours[day].close || defaultClose).split(':')
          const o = Number(ohh)
          const c = Number(chh)
          if (Number.isFinite(o)) minH = (minH == null) ? o : Math.min(minH, o)
          if (Number.isFinite(c)) maxH = (maxH == null) ? c : Math.max(maxH, c)
        }
        if (minH != null && maxH != null) {
          horarioInicioFallback = minH
          horarioFimFallback = maxH
        }
      } catch (_) {}

      // Keep reminders aligned
      const reminderHours = setupPayload?.notifications?.reminderHours
      const mergedAdmin = {
        ...adminConfig,
        business: {
          ...adminConfig.business,
          lembrete_horas_antes: Array.isArray(reminderHours) ? reminderHours : (adminConfig.business.lembrete_horas_antes || []),
          horario_inicio: horarioInicioFallback,
          horario_fim: horarioFimFallback,
        },
      }

      await API.put('/admin/config', mergedAdmin)

      // sanitize capacity map (by professional name)
      const capDefaultRaw = setupPayload?.capacity?.appointmentsPerDayDefault
      const capDefault = Number.isFinite(Number(capDefaultRaw)) ? Math.max(0, Math.floor(Number(capDefaultRaw))) : 8
      const per = {}
      const perRaw = setupPayload?.capacity?.perProfessional || {}
      ;(adminConfig.professionals || []).forEach((p) => {
        const name = String(p?.name || '').trim()
        if (!name) return
        const v = perRaw[name]
        if (v == null || v === '') return
        const n = Math.max(0, Math.floor(Number(v)))
        if (Number.isFinite(n)) per[name] = n
      })

      const payloadToSave = {
        ...setupPayload,
        business: {
          ...(setupPayload.business || {}),
          openingHours,
          openDays,
        },
        notifications: {
          ...(setupPayload.notifications || {}),
          // fixo: profissional/humano/educado (sem emojis)
          tone: 'profissional',
          // garantir somente 24h/36h
          confirmationRuleHours: (Number(setupPayload?.notifications?.confirmationRuleHours) === 36) ? 36 : 24,
          channels: {
            ...((setupPayload.notifications && setupPayload.notifications.channels) ? setupPayload.notifications.channels : {}),
            whatsapp: true,
            sms: true,
            email: false,
          },
        },
        policies: {
          ...(setupPayload.policies || {}),
          depositPercent: setupPayload?.policies?.depositEnabled ? 50 : 50,
          noShowRetainPercentOfService: setupPayload?.policies?.depositEnabled ? 15 : 0,
          noShowRefundPercentOfService: setupPayload?.policies?.depositEnabled ? 35 : 0,
          platformSharePercentOfService: setupPayload?.policies?.depositEnabled ? 7 : 0,
          establishmentSharePercentOfService: setupPayload?.policies?.depositEnabled ? 8 : 0,
        },
        capacity: {
          ...(setupPayload.capacity || {}),
          appointmentsPerDayDefault: capDefault,
          perProfessional: per,
        },
      }

      await API.put('/admin/setup', { payload: payloadToSave })

      setSuccessMsg('Setup salvo com sucesso. O link de booking vai usar os serviços/profissionais atualizados.')
    } catch (e) {
      setError('Falha ao salvar. Confirme o token admin e tente novamente.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="dashboard-root">
        <div className="dashboard-main">
          <Header />
          <div className="card-surface" style={{ padding: 14 }}>
            <div style={{ color: '#6b7280' }}>Carregando Setup Inteligente…</div>
          </div>
        </div>
      </div>
    )
  }

  const b = adminConfig.business || {}

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ margin: 0 }}>Configurações — Setup Inteligente</h3>
              <div style={{ marginTop: 4, color: '#6b7280', fontSize: 13 }}>
                Responda uma vez e nós preparamos serviços, equipe e políticas para o booking.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button
                className="action-btn"
                onClick={() => {
                  try {
                    localStorage.setItem('ea_dev_token', token || '')
                    localStorage.setItem('DEV_JWT_TOKEN', token || '')
                  } catch (_) {}
                  const mountedRef = { current: true }
                  loadAll(mountedRef)
                }}
              >
                Recarregar
              </button>
              <Link to="/config/avancado" style={{ fontSize: 13, color: '#2563eb', textDecoration: 'underline' }}>
                Config avançada (JSON)
              </Link>
            </div>
          </div>

          <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 420px' }}>
              <label style={{ fontSize: 13, color: '#374151' }}>Token admin (JWT) — necessário para salvar</label>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                placeholder="Cole aqui o token do /auth/login"
              />
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                Dica: o token fica salvo em <b>localStorage</b> (chave <b>ea_dev_token</b>).
              </div>
            </div>
            <div style={{ flex: '0 0 auto', display: 'flex', gap: 8 }}>
              <button
                className="action-btn"
                onClick={() => {
                  try {
                    localStorage.setItem('ea_dev_token', token || '')
                    localStorage.setItem('DEV_JWT_TOKEN', token || '')
                  } catch (_) {}
                  setSuccessMsg('Token salvo. Agora clique em Recarregar.')
                }}
              >
                Salvar token
              </button>
            </div>
          </div>

          <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {steps.map((s, i) => (
              <button
                key={s.key}
                className={`filter-pill ${i === step ? 'active' : ''}`}
                onClick={() => setStep(i)}
                style={{ cursor: 'pointer' }}
              >
                {i + 1}. {s.title}
              </button>
            ))}
          </div>

          {error && <div style={{ color: 'crimson', marginTop: 10 }}>{error}</div>}
          {successMsg && <div style={{ color: '#065f46', marginTop: 10 }}>{successMsg}</div>}
        </div>

        {step === 0 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>1) Negócio</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Essas informações aparecem no painel e no booking.</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, color: '#374151' }}>Nome do negócio *</label>
                <input
                  value={b.nome || ''}
                  onChange={(e) => {
                    const nome = e.target.value
                    updateBusiness({ nome, slug: b.slug ? b.slug : slugify(nome) })
                  }}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  placeholder="Ex: Studio Ana Beleza"
                />
              </div>
              <div>
                <label style={{ fontSize: 13, color: '#374151' }}>Slug do booking *</label>
                <input
                  value={b.slug || ''}
                  onChange={(e) => updateBusiness({ slug: slugify(e.target.value) })}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  placeholder="Ex: ana-beleza-madrid"
                />
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                  Link sugerido: <b>/booking/{b.slug || 'seu-slug'}</b> (vamos plugar isso no futuro)
                </div>
              </div>
              <div>
                <label style={{ fontSize: 13, color: '#374151' }}>Telefone/WhatsApp *</label>
                <input
                  value={b.telefone || ''}
                  onChange={(e) => updateBusiness({ telefone: e.target.value })}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  placeholder="+55 11 99999-9999"
                />
              </div>
              <div>
                <label style={{ fontSize: 13, color: '#374151' }}>Email</label>
                <input
                  value={b.email || ''}
                  onChange={(e) => updateBusiness({ email: e.target.value })}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  placeholder="contato@seunegocio.com"
                />
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                  Usamos e-mail apenas para conta e comunicados (não para lembretes de agenda).
                </div>
              </div>
              <div>
                <label style={{ fontSize: 13, color: '#374151' }}>País</label>
                <select
                  value={setupPayload?.business?.country || 'BR'}
                  onChange={(e) => {
                    const code = e.target.value
                    const opt = (COUNTRY_OPTIONS || []).find((x) => x.code === code)
                    updateSetup('business.country', code)
                    if (opt && opt.currency) updateSetup('business.currency', opt.currency)
                    if (opt && opt.timezones && opt.timezones.length) updateSetup('business.timezone', opt.timezones[0])
                  }}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                >
                  {(COUNTRY_OPTIONS || []).map((c) => (
                    <option key={c.code} value={c.code}>{c.label}</option>
                  ))}
                </select>
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                  Define timezone e moeda recomendados automaticamente.
                </div>
              </div>
              <div>
                <label style={{ fontSize: 13, color: '#374151' }}>Timezone</label>
                <select
                  value={setupPayload.business.timezone}
                  onChange={(e) => updateSetup('business.timezone', e.target.value)}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                >
                  {(() => {
                    const country = setupPayload?.business?.country || 'BR'
                    const opt = (COUNTRY_OPTIONS || []).find((x) => x.code === country)
                    const list = (opt && Array.isArray(opt.timezones) && opt.timezones.length) ? opt.timezones : ['Europe/Madrid']
                    return list.map((tz) => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))
                  })()}
                </select>
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                  Importante para horários de agenda, relatórios e lembretes.
                </div>
              </div>
              <div>
                <label style={{ fontSize: 13, color: '#374151' }}>Moeda</label>
                <select
                  value={setupPayload.business.currency}
                  onChange={(e) => updateSetup('business.currency', e.target.value)}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                >
                  {currencyOptions.map((c) => (
                    <option key={c} value={c}>{currencyLabel(c)}</option>
                  ))}
                </select>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <label style={{ fontSize: 13, color: '#374151' }}>Endereço (opcional)</label>
                <input
                  value={setupPayload.business.address}
                  onChange={(e) => updateSetup('business.address', e.target.value)}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  placeholder="Rua, número, cidade"
                />
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>2) Horários</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Organize dias e horários de funcionamento. Sábado/domingo podem ter horários diferentes — o booking respeita isso.</div>
            </div>

            <div className="card-surface" style={{ padding: 12, marginTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 800 }}>Dias e horários de funcionamento</div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>Ative o dia e defina o intervalo. Dias desligados ficam como <b>Fechado</b> no booking.</div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    className="action-btn"
                    type="button"
                    onClick={() => {
                      const oh = (setupPayload?.business?.openingHours && typeof setupPayload.business.openingHours === 'object') ? setupPayload.business.openingHours : {}
                      const base = oh.monday || { active: true, open: '09:00', close: '18:00' }
                      const patch = {}
                      ;['monday','tuesday','wednesday','thursday','friday'].forEach((d) => {
                        patch[d] = { ...(oh[d] || {}), active: true, open: base.open || '09:00', close: base.close || '18:00' }
                      })
                      updateSetup('business.openingHours', { ...oh, ...patch })
                      // keep openDays in sync
                      ;['monday','tuesday','wednesday','thursday','friday'].forEach((d) => updateSetup(`business.openDays.${d}`, true))
                    }}
                  >
                    Aplicar Seg–Sex
                  </button>
                  <button
                    className="action-btn"
                    type="button"
                    onClick={() => {
                      const oh = (setupPayload?.business?.openingHours && typeof setupPayload.business.openingHours === 'object') ? setupPayload.business.openingHours : {}
                      const base = oh.monday || { active: true, open: '09:00', close: '18:00' }
                      const patch = {}
                      ;['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].forEach((d) => {
                        const cur = oh[d] || {}
                        if (!cur.active) return
                        patch[d] = { ...cur, open: base.open || cur.open || '09:00', close: base.close || cur.close || '18:00' }
                      })
                      updateSetup('business.openingHours', { ...oh, ...patch })
                    }}
                  >
                    Copiar horários da Seg
                  </button>
                </div>
              </div>

              <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
                {weekdayOptions.map((w) => {
                  const oh = (setupPayload?.business?.openingHours && typeof setupPayload.business.openingHours === 'object') ? setupPayload.business.openingHours : {}
                  const cur = (oh && oh[w.key] && typeof oh[w.key] === 'object') ? oh[w.key] : { active: !!(setupPayload?.business?.openDays && setupPayload.business.openDays[w.key]), open: '09:00', close: '18:00' }
                  const active = !!cur.active

                  return (
                    <div key={w.key} style={{ display: 'grid', gridTemplateColumns: '120px 110px 1fr 1fr', gap: 10, alignItems: 'center', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb', background: active ? '#ffffff' : '#f9fafb' }}>
                      <div style={{ fontWeight: 700, color: '#111827' }}>{w.label}</div>

                      <button
                        type="button"
                        className={`weekday-pill ${active ? 'active' : ''}`}
                        aria-pressed={active}
                        onClick={() => {
                          const next = !active
                          updateSetup(`business.openingHours.${w.key}.active`, next)
                          updateSetup(`business.openDays.${w.key}`, next)
                        }}
                        title={active ? 'Aberto' : 'Fechado'}
                      >
                        {active ? 'Aberto' : 'Fechado'}
                      </button>

                      <div>
                        <label style={{ display: 'block', fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Abre</label>
                        <input
                          type="time"
                          value={cur.open || '09:00'}
                          disabled={!active}
                          step={900}
                          onChange={(e) => {
                            updateSetup(`business.openingHours.${w.key}.open`, e.target.value)
                            updateSetup(`business.openDays.${w.key}`, true)
                            updateSetup(`business.openingHours.${w.key}.active`, true)
                          }}
                          style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb', background: active ? '#fff' : '#f3f4f6' }}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Fecha</label>
                        <input
                          type="time"
                          value={cur.close || '18:00'}
                          disabled={!active}
                          step={900}
                          onChange={(e) => {
                            updateSetup(`business.openingHours.${w.key}.close`, e.target.value)
                            updateSetup(`business.openDays.${w.key}`, true)
                            updateSetup(`business.openingHours.${w.key}.active`, true)
                          }}
                          style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb', background: active ? '#fff' : '#f3f4f6' }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="card-surface" style={{ padding: 12, marginTop: 12 }}>
              {(() => {
                const bs = setupPayload?.business?.breakStart
                const be = setupPayload?.business?.breakEnd
                const bsh = Number(setupPayload?.business?.breakStartHour ?? 0)
                const beh = Number(setupPayload?.business?.breakEndHour ?? 0)
                const enabled = (!!String(bs || '').trim() && !!String(be || '').trim()) || (bsh > 0 || beh > 0)
                const bsVal = String(bs || '').trim() || (bsh ? String(bsh).padStart(2, '0') + ':00' : '12:00')
                const beVal = String(be || '').trim() || (beh ? String(beh).padStart(2, '0') + ':00' : '13:00')

                return (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                      <div>
                        <div style={{ fontWeight: 900, fontSize: 16 }}>Pausa (almoço/fechado)</div>
                        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                          Quando ativo, o booking não oferece horários dentro desse intervalo.
                        </div>
                      </div>
                      <button
                        type="button"
                        className={`weekday-pill ${enabled ? 'active' : ''}`}
                        aria-pressed={enabled}
                        onClick={() => {
                          const next = !enabled
                          if (!next) {
                            updateSetup('business.breakStart', null)
                            updateSetup('business.breakEnd', null)
                            updateSetup('business.breakStartHour', 0)
                            updateSetup('business.breakEndHour', 0)
                          } else {
                            updateSetup('business.breakStart', '12:00')
                            updateSetup('business.breakEnd', '13:00')
                            updateSetup('business.breakStartHour', 12)
                            updateSetup('business.breakEndHour', 13)
                          }
                        }}
                      >
                        {enabled ? 'Ativa' : 'Desativada'}
                      </button>
                    </div>

                    <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                      <div>
                        <label style={{ fontSize: 13, color: '#374151' }}>Início</label>
                        <input
                          type="time"
                          step={900}
                          value={bsVal}
                          disabled={!enabled}
                          onChange={(e) => {
                            const v = e.target.value
                            updateSetup('business.breakStart', v)
                            const h = Number(String(v || '').split(':')[0] || 0)
                            updateSetup('business.breakStartHour', Number.isFinite(h) ? h : 0)
                          }}
                          style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb', background: enabled ? '#fff' : '#f3f4f6' }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: 13, color: '#374151' }}>Fim</label>
                        <input
                          type="time"
                          step={900}
                          value={beVal}
                          disabled={!enabled}
                          onChange={(e) => {
                            const v = e.target.value
                            updateSetup('business.breakEnd', v)
                            const h = Number(String(v || '').split(':')[0] || 0)
                            updateSetup('business.breakEndHour', Number.isFinite(h) ? h : 0)
                          }}
                          style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb', background: enabled ? '#fff' : '#f3f4f6' }}
                        />
                      </div>
                    </div>

                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 8 }}>
                      Dica: use 12:00–13:00 para almoço. Se não tiver pausa, deixe desativado.
                    </div>
                  </>
                )
              })()}
            </div>

            <div className="card-surface" style={{ padding: 12, marginTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 800 }}>Datas fechadas</div>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>Use para feriados, folgas e dias sem atendimento (o booking bloqueia automaticamente).</div>
                </div>
              </div>

              <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, alignItems: 'end' }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Adicionar data</label>
                  <input
                    type="date"
                    value={holidayToAdd}
                    onChange={(e) => setHolidayToAdd(e.target.value)}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  />
                </div>
                <button
                  className="action-btn"
                  onClick={() => {
                    const v = String(holidayToAdd || '').trim()
                    if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return
                    const list = Array.isArray(setupPayload?.business?.holidays) ? setupPayload.business.holidays : []
                    if (list.includes(v)) return
                    updateSetup('business.holidays', [...list, v].sort())
                    setHolidayToAdd('')
                  }}
                  disabled={!holidayToAdd}
                >
                  Adicionar
                </button>
              </div>

              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(Array.isArray(setupPayload?.business?.holidays) ? setupPayload.business.holidays : []).length === 0 && (
                  <div style={{ fontSize: 13, color: '#6b7280' }}>Nenhuma data cadastrada.</div>
                )}
                {(Array.isArray(setupPayload?.business?.holidays) ? setupPayload.business.holidays : []).map((h) => (
                  <span key={h} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 999, background: '#f3f4f6', color: '#111827', fontSize: 13 }}>
                    {h}
                    <button
                      className="action-btn"
                      style={{ padding: '2px 6px', marginLeft: 0 }}
                      onClick={() => {
                        const list = Array.isArray(setupPayload?.business?.holidays) ? setupPayload.business.holidays : []
                        updateSetup('business.holidays', list.filter((x) => x !== h))
                      }}
                      aria-label={`Remover ${h}`}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>3) Serviços</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Cadastre serviços com preço, duração e buffer (organizado e pronto para o booking).</div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ color: '#6b7280', fontSize: 13 }}>Dica: coloque buffer para limpeza/preparação.</div>
                <div style={{ minWidth: 220 }}>
                  <label style={{ fontSize: 13, color: '#374151' }}>Moeda dos preços</label>
                  <select
                    value={setupPayload?.business?.currency || 'BRL'}
                    onChange={(e) => updateSetup('business.currency', e.target.value)}
                    style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                  >
                    {currencyOptions.map((c) => (
                      <option key={c} value={c}>{currencyLabel(c)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button className="action-btn" onClick={addService}>+ Adicionar serviço</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(adminConfig.services || []).map((s, idx) => (
                <div key={idx} className="card-surface" style={{ padding: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ minWidth: 260 }}>
                      <div style={{ fontWeight: 900, color: '#0f1724' }}>{s.name ? String(s.name) : `Serviço #${idx + 1}`}</div>
                      <div style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>
                        {(s.duration_min ?? 0) + (s.buffer_min ?? 0)} min no total • intervalo {s.display_interval_min ?? 30} min
                      </div>
                    </div>
                    <button
                      type="button"
                      className="action-btn"
                      onClick={() => removeService(idx)}
                      title="Remover serviço"
                      style={{ borderColor: 'rgba(239,68,68,0.18)' }}
                    >
                      Remover
                    </button>
                  </div>

                  <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
                    <div className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)', background: 'linear-gradient(180deg,#ffffff,#fbfdff)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 10 }}>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Nome *</label>
                          <input value={s.name || ''} onChange={(e) => updateService(idx, { name: e.target.value })} style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }} placeholder="Ex: Corte feminino" />
                        </div>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Preço ({currencyLabel(setupPayload?.business?.currency || 'BRL')})</label>
                          <input
                            type="number"
                            min={0}
                            step={1}
                            value={Number.isFinite((s.price_cents ?? 0) / 100) ? ((s.price_cents ?? 0) / 100) : 0}
                            onChange={(e) => {
                              const v = Number(e.target.value)
                              const cents = Number.isFinite(v) ? Math.max(0, Math.round(v * 100)) : 0
                              updateService(idx, { price_cents: cents })
                            }}
                            style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                            placeholder="0"
                          />
                          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                            Salvo em centavos no sistema.
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
                      <div style={{ fontWeight: 900, fontSize: 13, color: '#111827' }}>Organização</div>
                      <div style={{ marginTop: 10, display: 'grid', gap: 10 }}>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Duração (min) *</label>
                          <input type="number" min={5} step={5} value={s.duration_min ?? 30} onChange={(e) => updateService(idx, { duration_min: Number(e.target.value) })} style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }} />
                        </div>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Buffer (min)</label>
                          <input type="number" min={0} step={5} value={s.buffer_min ?? 0} onChange={(e) => updateService(idx, { buffer_min: Number(e.target.value) })} style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }} />
                          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>Preparação/limpeza após o atendimento.</div>
                        </div>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Intervalo de exibição (min)</label>
                          <input type="number" min={5} step={5} value={s.display_interval_min ?? 30} onChange={(e) => updateService(idx, { display_interval_min: Number(e.target.value) })} style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }} />
                          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>De quanto em quanto tempo o cliente vê opções.</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>4) Equipe</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Quem atende e quem aparece no booking.</div>
            </div>

            <div className="card-surface" style={{ padding: 12, marginBottom: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 900, fontSize: 16 }}>Capacidade do dia (indicador)</div>
                  <div style={{ color: '#6b7280', fontSize: 13 }}>
                    Quantos clientes, em média, cada profissional atende por dia? Usamos isso para marcar dias <b>Cheio</b>, <b>Moderado</b> e <b>Livre</b> sem erros.
                  </div>
                </div>
                <div style={{ minWidth: 220 }}>
                  <label style={{ fontSize: 13, color: '#374151' }}>Capacidade padrão</label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={setupPayload?.capacity?.appointmentsPerDayDefault ?? 8}
                    onChange={(e) => updateSetup('capacity.appointmentsPerDayDefault', Number(e.target.value))}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  />
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Planejado: vincular quais serviços cada profissional faz.</div>
              <button className="action-btn" onClick={addProfessional}>+ Adicionar profissional</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(adminConfig.professionals || []).map((p, idx) => {
                const initials = String(p.name || 'P').trim().split(/\s+/).slice(0, 2).map((x) => x[0]).join('').toUpperCase() || 'P'
                const name = String(p.name || '').trim()
                const hasName = !!name
                const perProf = hasName ? getTeamPerProfessional(name) : null
                const photoDataUrl = perProf && perProf.photoDataUrl ? String(perProf.photoDataUrl) : ''

                const globalBreak = getGlobalBreakWindow()
                const breakStart = perProf && perProf.breakStart ? String(perProf.breakStart) : ''
                const breakEnd = perProf && perProf.breakEnd ? String(perProf.breakEnd) : ''
                const effectiveBreakStart = breakStart || (globalBreak ? globalBreak.start : '')
                const effectiveBreakEnd = breakEnd || (globalBreak ? globalBreak.end : '')

                return (
                  <div key={idx} className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 240 }}>
                        <div style={{ width: 44, height: 44, borderRadius: 999, background: 'linear-gradient(180deg,#1f2937,#111827)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, fontSize: 13, flex: '0 0 44px', overflow: 'hidden' }}>
                          {photoDataUrl ? (
                            <img src={photoDataUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                          ) : (
                            initials
                          )}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 900, color: '#0f1724', fontSize: 14 }}>{hasName ? name : `Profissional #${idx + 1}`}</div>
                          <div style={{ color: '#6b7280', fontSize: 12 }}>Quem aparece no booking e recebe agenda.</div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        <input
                          type="file"
                          accept="image/*"
                          id={`prof-photo-${idx}`}
                          style={{ display: 'none' }}
                          onChange={async (e) => {
                            const nm = String(p.name || '').trim()
                            const file = e.target.files && e.target.files[0] ? e.target.files[0] : null
                            e.target.value = ''
                            if (!nm || !file) return
                            try {
                              await setProfessionalPhoto(nm, file)
                            } catch (err) {
                              setError('Não foi possível carregar a foto. Use uma imagem menor (até 2MB).')
                            }
                          }}
                        />

                        <button
                          type="button"
                          className="action-btn"
                          onClick={() => {
                            const nm = String(p.name || '').trim()
                            if (!nm) return
                            const el = document.getElementById(`prof-photo-${idx}`)
                            if (el) el.click()
                          }}
                          disabled={!hasName}
                          title={hasName ? 'Enviar foto do profissional' : 'Preencha o nome para habilitar'}
                          style={{ padding: '6px 10px' }}
                        >
                          {photoDataUrl ? 'Trocar foto' : 'Adicionar foto'}
                        </button>

                        {photoDataUrl ? (
                          <button
                            type="button"
                            className="action-btn"
                            onClick={() => updateTeamPerProfessional(name, { photoDataUrl: null })}
                            style={{ padding: '6px 10px' }}
                          >
                            Remover foto
                          </button>
                        ) : null}

                        <button
                          type="button"
                          className="action-btn"
                          onClick={() => removeProfessional(idx)}
                          title="Remover profissional"
                          style={{ borderColor: 'rgba(239,68,68,0.18)' }}
                        >
                          Remover
                        </button>
                      </div>
                    </div>

                    <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
                      <div>
                        <label style={{ fontSize: 13, color: '#374151' }}>Nome *</label>
                        <input value={p.name || ''} onChange={(e) => updateProfessional(idx, { name: e.target.value })} style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }} />
                      </div>
                      <div>
                        <label style={{ fontSize: 13, color: '#374151' }}>Telefone</label>
                        <input value={p.telefone || ''} onChange={(e) => updateProfessional(idx, { telefone: e.target.value })} style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }} placeholder="Ex: +55 11 99999-9999" />
                      </div>
                      <div>
                        <label style={{ fontSize: 13, color: '#374151' }}>Clientes/dia</label>
                        <input
                          type="number"
                          min={0}
                          step={1}
                          value={(setupPayload?.capacity?.perProfessional && p.name) ? (setupPayload.capacity.perProfessional[p.name] ?? '') : ''}
                          onChange={(e) => {
                            const nm = String(p.name || '').trim()
                            if (!nm) return
                            const raw = e.target.value
                            setSetupPayload((sp) => {
                              const cap = (sp && sp.capacity) ? sp.capacity : {}
                              const per = (cap && cap.perProfessional && typeof cap.perProfessional === 'object') ? { ...cap.perProfessional } : {}
                              if (raw === '' || raw == null) {
                                delete per[nm]
                              } else {
                                per[nm] = Number(raw)
                              }
                              return { ...sp, capacity: { ...cap, perProfessional: per } }
                            })
                          }}
                          style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                          placeholder="(opcional)"
                        />
                        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>Usado para indicar dias Cheio/Moderado/Livre.</div>
                      </div>
                    </div>

                    <div className="card-surface" style={{ padding: 10, marginTop: 12, border: '1px solid rgba(15,23,42,0.06)', background: 'linear-gradient(180deg,#ffffff,#fbfdff)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
                        <div>
                          <div style={{ fontWeight: 900, fontSize: 13, color: '#111827' }}>Pausa/Almoço do profissional</div>
                          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                            {breakStart && breakEnd
                              ? 'Personalizado para este profissional.'
                              : (effectiveBreakStart && effectiveBreakEnd)
                                ? `Usando padrão do negócio: ${effectiveBreakStart}–${effectiveBreakEnd}.`
                                : 'Sem pausa global definida. (Opcional)'}
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <button
                            type="button"
                            className="action-btn"
                            style={{ padding: '6px 10px' }}
                            onClick={() => {
                              if (!hasName) return
                              updateTeamPerProfessional(name, { breakStart: '', breakEnd: '' })
                            }}
                            disabled={!hasName || (!breakStart && !breakEnd)}
                            title="Voltar a usar o padrão do negócio"
                          >
                            Usar padrão
                          </button>
                        </div>
                      </div>

                      <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Início</label>
                          <input
                            type="time"
                            value={breakStart}
                            onChange={(e) => {
                              if (!hasName) return
                              updateTeamPerProfessional(name, { breakStart: e.target.value })
                            }}
                            style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                            disabled={!hasName}
                          />
                        </div>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Fim</label>
                          <input
                            type="time"
                            value={breakEnd}
                            onChange={(e) => {
                              if (!hasName) return
                              updateTeamPerProfessional(name, { breakEnd: e.target.value })
                            }}
                            style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                            disabled={!hasName}
                          />
                        </div>
                      </div>
                      <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>
                        Dica: se você deixar vazio, o sistema usa a pausa do negócio (se existir). Se preencher, vira pausa exclusiva deste profissional.
                      </div>
                    </div>

                    <div style={{ marginTop: 12, border: '1px solid rgba(15,23,42,0.08)', borderRadius: 12, padding: 10, background: 'linear-gradient(180deg,#ffffff,#fbfdff)' }}>
                      <div style={{ fontWeight: 900, color: '#111827', fontSize: 13 }}>Jornada e dias de trabalho</div>
                      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                        Define início/fim e dias de trabalho por profissional (o booking respeita isso).
                      </div>

                      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Início do trabalho</label>
                          <input
                            type="time"
                            value={(() => {
                              const nm = String(p.name || '').trim()
                              const cur = (setupPayload?.team?.perProfessional && nm) ? setupPayload.team.perProfessional[nm] : null
                              if (cur && cur.startTime) return String(cur.startTime)
                              const h = (cur && Number.isFinite(cur.startHour)) ? cur.startHour : (adminConfig.business?.horario_inicio ?? 9)
                              return `${String(h).padStart(2,'0')}:00`
                            })()}
                            onChange={(e) => {
                              const nm = String(p.name || '').trim()
                              if (!nm) return
                              const v = String(e.target.value || '')
                              const hh = Number(String(v).split(':')[0] || '')
                              setSetupPayload((sp) => {
                                const team = (sp && sp.team) ? sp.team : {}
                                const per = (team && team.perProfessional && typeof team.perProfessional === 'object') ? { ...team.perProfessional } : {}
                                const cur = (per[nm] && typeof per[nm] === 'object') ? { ...per[nm] } : {}
                                cur.startTime = v
                                if (Number.isFinite(hh)) cur.startHour = hh
                                per[nm] = cur
                                return { ...sp, team: { ...team, perProfessional: per } }
                              })
                            }}
                            style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                          />
                        </div>
                        <div>
                          <label style={{ fontSize: 13, color: '#374151' }}>Fim do trabalho</label>
                          <input
                            type="time"
                            value={(() => {
                              const nm = String(p.name || '').trim()
                              const cur = (setupPayload?.team?.perProfessional && nm) ? setupPayload.team.perProfessional[nm] : null
                              if (cur && cur.endTime) return String(cur.endTime)
                              const h = (cur && Number.isFinite(cur.endHour)) ? cur.endHour : (adminConfig.business?.horario_fim ?? 18)
                              return `${String(h).padStart(2,'0')}:00`
                            })()}
                            onChange={(e) => {
                              const nm = String(p.name || '').trim()
                              if (!nm) return
                              const v = String(e.target.value || '')
                              const hh = Number(String(v).split(':')[0] || '')
                              setSetupPayload((sp) => {
                                const team = (sp && sp.team) ? sp.team : {}
                                const per = (team && team.perProfessional && typeof team.perProfessional === 'object') ? { ...team.perProfessional } : {}
                                const cur = (per[nm] && typeof per[nm] === 'object') ? { ...per[nm] } : {}
                                cur.endTime = v
                                if (Number.isFinite(hh)) cur.endHour = hh
                                per[nm] = cur
                                return { ...sp, team: { ...team, perProfessional: per } }
                              })
                            }}
                            style={{ width: '100%', padding: 10, borderRadius: 10, border: '1px solid #e5e7eb' }}
                          />
                        </div>
                      </div>

                      <div style={{ marginTop: 12, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                        <div style={{ fontSize: 13, color: '#374151', fontWeight: 900 }}>Dias de trabalho</div>
                        {(() => {
                          const nm = String(p.name || '').trim()
                          const cur = (setupPayload?.team?.perProfessional && nm) ? setupPayload.team.perProfessional[nm] : null
                          const fallback = setupPayload?.business?.openDays || {}
                          const valueMap = {}
                          weekdayOptions.forEach((w) => {
                            const hasExplicit = !!(cur && cur.workDays && Object.prototype.hasOwnProperty.call(cur.workDays, w.key))
                            valueMap[w.key] = hasExplicit ? !!cur.workDays[w.key] : !!fallback[w.key]
                          })
                          return (
                            <WeekdayToggle
                              ariaLabel={`Dias de trabalho de ${nm || 'profissional'}`}
                              valueMap={valueMap}
                              onToggle={(key, next) => {
                                if (!nm) return
                                setSetupPayload((sp) => {
                                  const team = (sp && sp.team) ? sp.team : {}
                                  const per = (team && team.perProfessional && typeof team.perProfessional === 'object') ? { ...team.perProfessional } : {}
                                  const cur2 = (per[nm] && typeof per[nm] === 'object') ? { ...per[nm] } : {}
                                  const wd = (cur2.workDays && typeof cur2.workDays === 'object') ? { ...cur2.workDays } : {}
                                  wd[key] = next
                                  cur2.workDays = wd
                                  per[nm] = cur2
                                  return { ...sp, team: { ...team, perProfessional: per } }
                                })
                              }}
                            />
                          )
                        })()}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>5) Políticas</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Defina se você quer trabalhar com depósito e como isso afeta no-show.</div>
            </div>

            <div className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12, alignItems: 'start' }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Depósito</label>
                  <select
                    value={setupPayload.policies.depositEnabled ? 'yes' : 'no'}
                    onChange={(e) => {
                      const enabled = e.target.value === 'yes'
                      updateSetup('policies.depositEnabled', enabled)
                      updateSetup('policies.depositPercent', 50)
                      updateSetup('policies.noShowRetainPercentOfService', enabled ? 15 : 0)
                      updateSetup('policies.noShowRefundPercentOfService', enabled ? 35 : 0)
                      updateSetup('policies.platformSharePercentOfService', enabled ? 7 : 0)
                      updateSetup('policies.establishmentSharePercentOfService', enabled ? 8 : 0)
                      updateSetup(
                        'policies.noShowPolicy',
                        enabled
                          ? 'Depósito ativo (50%): em caso de no-show, será retido 15% do valor do serviço e reembolsado 35% do valor do serviço.'
                          : 'Sem depósito: no-show não gera cobrança automática.'
                      )
                    }}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  >
                    <option value="yes">Ativo (50%)</option>
                    <option value="no">Desativado</option>
                  </select>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Simples: se ativar, sempre será <b>50%</b>. Sem ajustar para cima/baixo.
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: 13, color: '#374151', fontWeight: 700 }}>Política de no-show</div>
                  <div style={{ marginTop: 8, padding: 12, borderRadius: 12, background: '#f8fafc', border: '1px solid rgba(15,23,42,0.08)', color: '#0f1724', fontSize: 13, lineHeight: 1.45 }}>
                    {setupPayload.policies.depositEnabled ? (
                      <>
                        <div style={{ fontWeight: 800, marginBottom: 6 }}>Regra quando depósito está ativo</div>
                        <div>
                          O cliente paga <b>50%</b> para reservar.
                          Em caso de <b>no-show</b> (cliente não comparece), retemos <b>15%</b> do valor do serviço e reembolsamos <b>35%</b> do valor do serviço.
                        </div>
                        <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                          <div style={{ color: '#6b7280', fontSize: 12 }}>
                            Isso reduz faltas e protege sua agenda.
                          </div>
                          <div style={{ color: '#6b7280', fontSize: 12 }}>
                            <b>Interno (não aparece no booking):</b> dos <b>15%</b> retidos, <b>7%</b> ficam com a plataforma e <b>8%</b> com o estabelecimento.
                          </div>
                          <div style={{ color: '#6b7280', fontSize: 12 }}>
                            Você decide como aplicar na prática (remarcação, exceções, casos especiais).
                          </div>
                        </div>
                      </>
                    ) : (
                      <>
                        <div style={{ fontWeight: 800, marginBottom: 6 }}>Regra quando depósito está desativado</div>
                        <div>
                          Não haverá cobrança automática em no-show.
                        </div>
                        <div style={{ marginTop: 8, color: '#6b7280', fontSize: 12 }}>
                          Se quiser proteção contra faltas, ative o depósito (50%).
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 5 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>6) Notificações</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Notificações automáticas (sem e-mail).</div>
            </div>

            <div className="card-surface" style={{ padding: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Canais</label>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Lembretes automáticos (sem e-mail). O sistema decide o melhor canal.
                  </div>
                  <div style={{ marginTop: 10, padding: 10, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: '#fbfdff' }}>
                    <div style={{ fontWeight: 900, color: '#111827' }}>Automático (recomendado)</div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                      Enviamos via <b>WhatsApp</b> e, quando fizer sentido, usamos <b>SMS</b> como fallback.
                      Isso evita configurações erradas e melhora a taxa de comparecimento.
                    </div>
                    <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>
                      Você só precisa escolher a regra (24h/36h). O resto o sistema otimiza.
                    </div>
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Regra de confirmação (24h / 36h)</label>
                  <select
                    value={(Number(setupPayload?.notifications?.confirmationRuleHours) === 36) ? 36 : 24}
                    onChange={(e) => updateSetup('notifications.confirmationRuleHours', Number(e.target.value) === 36 ? 36 : 24)}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  >
                    <option value={24}>24h (recomendado)</option>
                    <option value={36}>36h (mais cedo)</option>
                  </select>

                  <div style={{ marginTop: 10, padding: 10, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: 'linear-gradient(180deg,#ffffff,#fbfdff)' }}>
                    <div style={{ fontWeight: 900, color: '#111827' }}>Como funciona na prática</div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6, lineHeight: 1.45 }}>
                      Regra: o sistema respeita <b>{(Number(setupPayload?.notifications?.confirmationRuleHours) === 36) ? 36 : 24}h</b> ou <b>36h</b> (conforme sua escolha).
                      O cliente recebe um aviso de <b>pré-agendamento</b> e fica no aguardo do <b>2º lembrete</b> (confirmação oficial).
                    </div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 8, lineHeight: 1.45 }}>
                      No <b>2º lembrete</b> (confirmação oficial), o cliente pode <b>confirmar</b>, <b>reagendar</b> ou <b>cancelar</b>.
                      Ele tem <b>6 horas</b> para responder. Se não responder, o sistema <b>cancela automaticamente</b> e oferece a opção de <b>reagendar</b>.
                    </div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 8 }}>
                      A confirmação final é enviada em horário fixo (17:30 no dia anterior ou 08:30 no mesmo dia). Tom do texto é <b>fixo</b>: profissional, humano, educado e sem emojis.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 6 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>7) Integrar agenda</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>
                Importação premium para trazer sua agenda atual para o EasyAgenda e ativar lembretes.
              </div>
            </div>

            <Card
              title="Plano recomendado (10 minutos)"
              subtitle="A forma mais rápida e com menos erros para transferir tudo e começar a enviar lembretes."
            >
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
                <div style={{ padding: 12, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: '#fff' }}>
                  <div style={{ fontWeight: 950, color: '#111827' }}>1) Clientes (CSV)</div>
                  <div style={{ marginTop: 6, fontSize: 13, color: '#6b7280', lineHeight: 1.45 }}>
                    Importa nome + WhatsApp (+ idioma opcional). Ajuda os lembretes ficarem automáticos.
                  </div>
                </div>
                <div style={{ padding: 12, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: '#fff' }}>
                  <div style={{ fontWeight: 950, color: '#111827' }}>2) Agenda (.ics / iCal)</div>
                  <div style={{ marginTop: 6, fontSize: 13, color: '#6b7280', lineHeight: 1.45 }}>
                    Importa agendamentos por profissional, detecta conflitos e permite ajustar WhatsApp antes do commit.
                  </div>
                </div>
                <div style={{ padding: 12, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: '#fff' }}>
                  <div style={{ fontWeight: 950, color: '#111827' }}>3) Conferir e operar</div>
                  <div style={{ marginTop: 6, fontSize: 13, color: '#6b7280', lineHeight: 1.45 }}>
                    Depois disso, o EasyAgenda vira a agenda oficial e os lembretes já ficam ativos.
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 10 }}>
                <Callout tone="info" title="Dica para zero dor de cabeça">
                  <div style={{ fontSize: 13, lineHeight: 1.45 }}>
                    Se a sua agenda antiga não tem WhatsApp no evento, use o CSV para clientes e, na importação da agenda, ajuste os itens “AJUSTAR” antes de confirmar.
                  </div>
                </Callout>
              </div>
            </Card>

            <Card
              title="Importar clientes (CSV)"
              subtitle="Importe sua lista de clientes (nome + WhatsApp). Não cria agendamentos."
              right={(
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <button type="button" className="action-btn" onClick={downloadClientsCsvTemplate}>
                    Baixar modelo
                  </button>
                  <button
                    type="button"
                    className="action-btn"
                    onClick={previewClientsCsv}
                    disabled={clientsCsvLoading || !clientsCsvFile}
                  >
                    {clientsCsvLoading ? 'Analisando…' : 'Analisar CSV'}
                  </button>
                </div>
              )}
            >
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Arquivo CSV *</label>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => {
                      const f = e?.target?.files?.[0] || null
                      setClientsCsvFile(f)
                      setClientsCsvPreview(null)
                      setClientsCsvErr(null)
                      setClientsCsvCommitResult(null)
                    }}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff' }}
                  />
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Colunas aceitas: <b>nome/name</b>, <b>telefone/whatsapp/phone</b>, <b>idioma/lang</b> (opcional), <b>observacoes/notes</b> (opcional).
                  </div>
                </div>

                <Callout tone="info" title="Formato recomendado">
                  <div style={{ fontSize: 13, lineHeight: 1.45 }}>
                    Exemplo: <b>nome;whatsapp</b> (ou <b>name,phone</b>). Usamos autodetecção de separador (<b>;</b>, <b>,</b>, tab).
                  </div>
                </Callout>
              </div>

              {clientsCsvErr ? (
                <div style={{ marginTop: 12, color: '#b91c1c', fontSize: 13 }}>{clientsCsvErr}</div>
              ) : null}

              {clientsCsvPreview && clientsCsvPreview.ok ? (
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                    <KpiCard label="Linhas" value={clientsCsvPreview?.counts?.total ?? '—'} />
                    <KpiCard label="Prontos" value={clientsCsvPreview?.counts?.ready ?? '—'} tone="good" />
                    <KpiCard label="Falta WhatsApp" value={clientsCsvPreview?.counts?.needs_phone ?? '—'} tone="warn" />
                    <KpiCard label="Já existentes" value={clientsCsvPreview?.existing_matches ?? 0} />
                  </div>

                  {(clientsCsvPreview?.duplicates_in_file || 0) > 0 ? (
                    <div style={{ marginTop: 10 }}>
                      <Callout tone="warn" title="Detectamos duplicados no CSV">
                        <div style={{ fontSize: 13, lineHeight: 1.45 }}>
                          Existem <b>{clientsCsvPreview.duplicates_in_file}</b> linhas com WhatsApp repetido. Vamos importar sem duplicar (por WhatsApp).
                        </div>
                      </Callout>
                    </div>
                  ) : null}

                  <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="action-btn"
                      onClick={commitClientsCsv}
                      disabled={clientsCsvCommitting}
                      style={{ background: '#0f1724', color: '#fff', border: '1px solid rgba(15,23,42,0.18)' }}
                    >
                      {clientsCsvCommitting ? 'Importando…' : 'Confirmar importação de clientes'}
                    </button>
                    {clientsCsvCommitResult && clientsCsvCommitResult.ok ? (
                      <div style={{ fontSize: 12, color: '#065f46' }}>
                        Criados: <b>{clientsCsvCommitResult.created}</b> • Atualizados: <b>{clientsCsvCommitResult.updated}</b> • Ignorados: <b>{clientsCsvCommitResult.skipped}</b>
                      </div>
                    ) : null}
                  </div>

                  <div style={{ marginTop: 12, overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ textAlign: 'left', color: '#334155' }}>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>Nome</th>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>WhatsApp</th>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(clientsCsvPreview.items || []).slice(0, 200).map((it, idx) => {
                          const ok = it?.status === 'ok'
                          return (
                            <tr key={idx} style={{ background: idx % 2 ? '#fff' : '#fbfdff' }}>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9' }}>{it?.name || ''}</td>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9' }}>{it?.phone || ''}</td>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9' }}>
                                <span style={{ display: 'inline-flex', alignItems: 'center', padding: '4px 10px', borderRadius: 999, background: ok ? '#ecfdf5' : '#fff7ed', color: ok ? '#065f46' : '#9a3412', fontWeight: 900, fontSize: 12 }}>
                                  {ok ? 'OK' : 'AJUSTAR'}
                                </span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                    <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>
                      Mostrando até 200 linhas na tela (para performance).
                    </div>
                  </div>
                </div>
              ) : null}
            </Card>

            <Card
              title="Integrar agenda (arquivo .ics)"
              subtitle="Primeiro analisamos o arquivo, depois você confirma a importação."
              right={(
                <button
                  type="button"
                  className="action-btn"
                  onClick={previewIcs}
                  disabled={importLoading || !importFile || !importProfessionalId}
                >
                  {importLoading ? 'Analisando…' : 'Analisar arquivo'}
                </button>
              )}
            >
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Arquivo .ics *</label>
                  <input
                    type="file"
                    accept=".ics,text/calendar"
                    onChange={(e) => {
                      const f = e?.target?.files?.[0] || null
                      setImportFile(f)
                      setImportPreview(null)
                      setImportErr(null)
                      setImportCommitResult(null)
                    }}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff' }}
                  />
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Quanto mais detalhes no evento (nome + WhatsApp), mais automático fica.
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Profissional *</label>
                  <select
                    value={importProfessionalId || ''}
                    onChange={(e) => setImportProfessionalId(e.target.value ? Number(e.target.value) : null)}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  >
                    <option value="">Selecione…</option>
                    {(adminConfig?.professionals || []).map((p) => (
                      <option key={p.id || p.name} value={p.id || ''}>{p.name || p.nome || `#${p.id}`}</option>
                    ))}
                  </select>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Se você tiver uma agenda por profissional, importe uma por vez.
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, alignItems: 'start' }}>
                <div>
                  <label style={{ fontSize: 13, color: '#374151' }}>Serviço (opcional)</label>
                  <select
                    value={importServiceId}
                    onChange={(e) => setImportServiceId(e.target.value)}
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  >
                    <option value="">(Sem serviço específico)</option>
                    {(adminConfig?.services || []).map((s) => (
                      <option key={s.id || s.name} value={s.id || ''}>{s.name || `#${s.id}`}</option>
                    ))}
                  </select>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Se não selecionar, o evento entra com serviço vazio (mas ainda aparece na agenda).
                  </div>
                </div>

                <Callout tone="info" title="Como exportar (.ics)">
                  <div style={{ fontSize: 13, lineHeight: 1.45 }}>
                    <div><b>Google Calendar:</b> Configurações → Importar e exportar → Exportar</div>
                    <div style={{ marginTop: 6 }}><b>iPhone/iCloud:</b> Compartilhar calendário → Exportar (.ics)</div>
                    <div style={{ marginTop: 6 }}><b>Outlook:</b> Calendário → Salvar calendário → iCalendar (.ics)</div>
                  </div>
                </Callout>
              </div>

              {importErr ? (
                <div style={{ marginTop: 12, color: '#b91c1c', fontSize: 13 }}>{importErr}</div>
              ) : null}

              {importPreview && importPreview.ok ? (
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                    <KpiCard label="Eventos" value={importPreview?.counts?.total ?? '—'} />
                    <KpiCard label="Prontos" value={importPreview?.counts?.ready ?? '—'} tone="good" />
                    <KpiCard label="Falta WhatsApp" value={importPreview?.counts?.needs_phone ?? '—'} tone="warn" />
                    <KpiCard label="Conflitos" value={importPreview?.counts?.conflicts ?? '—'} tone="bad" />
                  </div>

                  <div style={{ marginTop: 10, fontSize: 13, color: '#6b7280' }}>
                    Timezone detectada: <b>{importPreview.timezone || '—'}</b>. Eventos “dia inteiro” são ignorados.
                  </div>

                  <div style={{ marginTop: 12, overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ textAlign: 'left', color: '#334155' }}>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>Início</th>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>Resumo</th>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>Cliente</th>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>WhatsApp</th>
                          <th style={{ padding: '8px 6px', borderBottom: '1px solid #e5e7eb' }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(importPreview.items || []).slice(0, 200).map((it, idx) => {
                          const ed = importEdits[String(idx)] || {}
                          const st = it?.start_local ? String(it.start_local).replace('T', ' ').slice(0, 16) : '—'
                          const status = it?.status || ''
                          const conflict = !!it?.conflict
                          const tone = conflict ? '#b91c1c' : (status === 'needs_phone' ? '#9a3412' : '#065f46')
                          const badge = conflict ? 'CONFLITO' : (status === 'needs_phone' ? 'AJUSTAR' : (status === 'skipped_all_day' ? 'IGNORADO' : 'OK'))
                          return (
                            <tr key={idx} style={{ background: idx % 2 ? '#fff' : '#fbfdff' }}>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9', whiteSpace: 'nowrap' }}>{st}</td>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9' }}>{it?.summary || ''}</td>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9' }}>
                                <input
                                  value={ed.customer_name != null ? ed.customer_name : (it?.customer_name || '')}
                                  onChange={(e) => editImportItem(idx, { customer_name: e.target.value })}
                                  placeholder="Nome"
                                  style={{ width: '100%', minWidth: 140, padding: 8, borderRadius: 8, border: '1px solid #e5e7eb' }}
                                />
                              </td>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9' }}>
                                <input
                                  value={ed.customer_whatsapp != null ? ed.customer_whatsapp : (it?.customer_whatsapp || '')}
                                  onChange={(e) => editImportItem(idx, { customer_whatsapp: e.target.value })}
                                  placeholder="+55... / +34..."
                                  style={{ width: '100%', minWidth: 160, padding: 8, borderRadius: 8, border: '1px solid #e5e7eb' }}
                                />
                              </td>
                              <td style={{ padding: '8px 6px', borderBottom: '1px solid #f1f5f9' }}>
                                <span style={{ display: 'inline-flex', alignItems: 'center', padding: '4px 10px', borderRadius: 999, background: conflict ? '#fff1f2' : (status === 'needs_phone' ? '#fff7ed' : '#ecfdf5'), color: tone, fontWeight: 900, fontSize: 12 }}>
                                  {badge}
                                </span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                    <div style={{ marginTop: 8, fontSize: 12, color: '#6b7280' }}>
                      Mostrando até 200 eventos na tela (para performance). A importação usa a lista completa.
                    </div>
                  </div>

                  <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="action-btn"
                      onClick={commitIcs}
                      disabled={importCommitting}
                      style={{ background: '#0f1724', color: '#fff', border: '1px solid rgba(15,23,42,0.18)' }}
                    >
                      {importCommitting ? 'Importando…' : 'Confirmar importação'}
                    </button>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>
                      Para lembretes funcionarem, preencha o WhatsApp nos itens “AJUSTAR”.
                    </div>
                  </div>

                  {importCommitResult && importCommitResult.ok ? (
                    <Callout tone="good" title="Importação concluída">
                      <div style={{ fontSize: 13 }}>
                        Importados: <b>{importCommitResult.imported}</b> • Duplicados: <b>{importCommitResult.duplicates}</b> • Ignorados: <b>{importCommitResult.skipped}</b>
                      </div>
                    </Callout>
                  ) : null}
                </div>
              ) : null}

              <div style={{ marginTop: 12 }}>
                <Callout tone="warn" title="Para ficar 100% automático">
                  <div style={{ fontSize: 13, lineHeight: 1.45 }}>
                    Garanta que cada evento tenha o WhatsApp do cliente no título ou descrição (ex: <b>+34...</b> / <b>+55...</b>). Se não tiver,
                    ajuste aqui antes de importar.
                  </div>
                </Callout>
              </div>
            </Card>

            <Card
              title="Google Calendar (link iCal)"
              subtitle="Cole o link iCal secreto do calendário. Importa sem login (sem OAuth)."
              right={(
                <button
                  type="button"
                  className="action-btn"
                  onClick={previewIcalUrl}
                  disabled={importIcalLoading || !importIcalUrl || !importProfessionalId}
                >
                  {importIcalLoading ? 'Analisando…' : 'Analisar link'}
                </button>
              )}
            >
              <Callout tone="info" title="Como pegar o link iCal">
                <div style={{ fontSize: 13, lineHeight: 1.45 }}>
                  Google Calendar → <b>Configurações</b> do calendário → <b>Integrar calendário</b> → <b>Endereço secreto em formato iCal</b>.
                  Cole o link abaixo.
                </div>
              </Callout>

              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label style={{ fontSize: 13, color: '#374151' }}>Link iCal (https://…)</label>
                  <input
                    value={importIcalUrl}
                    onChange={(e) => {
                      setImportIcalUrl(e.target.value)
                      setImportIcalPreview(null)
                      setImportIcalErr(null)
                    }}
                    placeholder="https://calendar.google.com/calendar/ical/.../basic.ics"
                    style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff' }}
                  />
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Segurança: aceitamos apenas links <b>https</b> e bloqueamos destinos privados.
                  </div>
                </div>
              </div>

              {importIcalErr ? (
                <div style={{ marginTop: 12, color: '#b91c1c', fontSize: 13 }}>{importIcalErr}</div>
              ) : null}

              {importIcalPreview && importIcalPreview.ok ? (
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                    <KpiCard label="Eventos" value={importIcalPreview?.counts?.total ?? '—'} />
                    <KpiCard label="Prontos" value={importIcalPreview?.counts?.ready ?? '—'} tone="good" />
                    <KpiCard label="Falta WhatsApp" value={importIcalPreview?.counts?.needs_phone ?? '—'} tone="warn" />
                    <KpiCard label="Conflitos" value={importIcalPreview?.counts?.conflicts ?? '—'} tone="bad" />
                  </div>
                  <div style={{ marginTop: 10, fontSize: 13, color: '#6b7280' }}>
                    Timezone detectada: <b>{importIcalPreview.timezone || '—'}</b>
                  </div>
                  <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="action-btn"
                      onClick={() => {
                        setImportPreview(importIcalPreview)
                        setImportEdits({})
                        setImportErr(null)
                        setImportCommitResult(null)
                      }}
                      style={{ background: '#0f1724', color: '#fff', border: '1px solid rgba(15,23,42,0.18)' }}
                    >
                      Editar e importar (recomendado)
                    </button>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>
                      Abre a mesma prévia na tabela acima para você corrigir WhatsApp antes de confirmar.
                    </div>
                  </div>
                </div>
              ) : null}
            </Card>
          </div>
        )}

        {step === 7 && (
          <div className="agenda-card">
            <div className="agenda-header" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: 0 }}>8) Revisão & Salvar</h3>
              <div style={{ color: '#6b7280', fontSize: 13 }}>Confirme e salve no backend/SQL.</div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <BookingShareCard slug={b.slug} businessName={b.nome} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
              <div className="card-surface" style={{ padding: 14, border: '1px solid rgba(15,23,42,0.06)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
                  <div style={{ fontSize: 13, color: '#6b7280' }}>Negócio</div>
                  <span style={{ fontSize: 12, color: '#111827', background: '#eef2ff', border: '1px solid rgba(99,102,241,0.25)', padding: '3px 8px', borderRadius: 999 }}>
                    {String(b.slug || '-').trim() ? `/${b.slug}` : '/-'}
                  </span>
                </div>

                <div style={{ fontSize: 16, fontWeight: 900, color: '#0f1724', marginTop: 8 }}>
                  {b.nome || '—'}
                </div>

                <div style={{ marginTop: 10, padding: 10, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: 'linear-gradient(180deg,#ffffff,#fbfdff)' }}>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>Setup</div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    Timezone: <b>{setupPayload?.business?.timezone || '—'}</b> • Moeda: <b>{currencyLabel(setupPayload?.business?.currency || 'BRL')}</b>
                  </div>
                </div>
              </div>

              <div className="card-surface" style={{ padding: 14, border: '1px solid rgba(15,23,42,0.06)' }}>
                <div style={{ fontSize: 13, color: '#6b7280' }}>Serviços</div>
                <div style={{ marginTop: 10, padding: 10, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: '#fbfdff' }}>
                  <div style={{ fontWeight: 900, color: '#111827', fontSize: 13 }}>Nomes dos serviços</div>
                  <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {(() => {
                      const list = Array.isArray(adminConfig.services) ? adminConfig.services : []
                      if (list.length === 0) {
                        return <div style={{ fontSize: 12, color: '#6b7280' }}>Nenhum serviço cadastrado.</div>
                      }

                      return list
                        .map((s) => String(s?.name || '').trim())
                        .filter(Boolean)
                        .slice(0, 10)
                        .map((name, i) => (
                          <span
                            key={`${name}-${i}`}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              padding: '6px 10px',
                              borderRadius: 999,
                              background: '#ffffff',
                              border: '1px solid rgba(15,23,42,0.10)',
                              color: '#0f1724',
                              fontSize: 13,
                              fontWeight: 800,
                            }}
                          >
                            {name}
                          </span>
                        ))
                    })()}
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 10 }}>
                    Os preços e duração ficam configurados no catálogo e são usados no booking.
                  </div>
                </div>
              </div>

              <div className="card-surface" style={{ padding: 14, border: '1px solid rgba(15,23,42,0.06)' }}>
                <div style={{ fontSize: 13, color: '#6b7280' }}>Políticas</div>
                <div style={{ marginTop: 10, padding: 10, borderRadius: 12, border: '1px solid rgba(15,23,42,0.08)', background: 'linear-gradient(180deg,#ffffff,#fbfdff)' }}>
                  <div style={{ fontSize: 13, fontWeight: 900, color: '#0f1724' }}>Depósito</div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6, lineHeight: 1.45 }}>
                    {setupPayload.policies.depositEnabled
                      ? <>Ativo (<b>{setupPayload.policies.depositPercent}%</b>). Em no-show: reter <b>{setupPayload.policies.noShowRetainPercentOfService}%</b> e reembolsar <b>{setupPayload.policies.noShowRefundPercentOfService}%</b> do valor do serviço.</>
                      : <>Desativado. (Sem cobrança automática em no-show.)</>
                    }
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 10 }}>
                    Cancelamento: <b>{setupPayload.policies.cancellationWindowHours}h</b> • Tolerância: <b>{setupPayload.policies.latePolicy || '—'}</b>
                  </div>
                </div>
              </div>
            </div>

            <div className="card-surface" style={{ padding: 12, marginTop: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 900, color: '#0f1724' }}>Preview real (como o cliente vê)</div>
                  <div style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>
                    Exemplo didático para você visualizar o fluxo de confirmação.
                  </div>
                </div>
                <div style={{ fontSize: 12, color: '#6b7280' }}>
                  Regra: <b>{(Number(setupPayload?.notifications?.confirmationRuleHours) === 36) ? 36 : 24}h</b> • Janela: <b>6h</b>
                </div>
              </div>

              <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                <div style={{ padding: 12, borderRadius: 12, background: '#fbfdff', border: '1px solid rgba(15,23,42,0.08)' }}>
                  <div style={{ fontWeight: 900, fontSize: 13, color: '#111827' }}>Cenário A (agendamento com antecedência)</div>
                  <div style={{ fontSize: 13, color: '#0f1724', marginTop: 8, lineHeight: 1.45 }}>
                    1) Pré-agendamento: “Seu pré-agendamento foi registrado. Fique no aguardo do 2º lembrete (confirmação oficial) — nele você poderá reagendar ou cancelar.”
                  </div>
                  <div style={{ fontSize: 13, color: '#0f1724', marginTop: 8, lineHeight: 1.45 }}>
                    2) Confirmação final (17:30 ou 08:30): “Responda 1 Confirmar • 2 Reagendar • 3 Cancelar (até HH:MM).”
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 8 }}>
                    No 2º lembrete, o cliente tem <b>6h</b> para responder. Sem resposta, cancelamos automaticamente e oferecemos reagendamento.
                  </div>
                </div>

                <div style={{ padding: 12, borderRadius: 12, background: '#fff', border: '1px solid rgba(15,23,42,0.08)' }}>
                  <div style={{ fontWeight: 900, fontSize: 13, color: '#111827' }}>Cenário B (agendamento em cima da hora)</div>
                  <div style={{ fontSize: 13, color: '#0f1724', marginTop: 8, lineHeight: 1.45 }}>
                    1) Confirmação (imediata): “Responda 1 Confirmar • 2 Reagendar • 3 Cancelar (até HH:MM).”
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 8 }}>
                    O cliente tem 6h para responder. Sem resposta, cancelamos automaticamente e oferecemos reagendamento.
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 8 }}>
                    Texto fixo: profissional, humano, educado e sem emojis.
                  </div>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 14 }}>
              <button className="action-btn" onClick={() => setStep(0)} disabled={saving}>Voltar ao início</button>
              <button className="action-btn action-confirm" onClick={handleSaveAll} disabled={saving}>
                {saving ? 'Salvando…' : 'Salvar setup'}
              </button>
            </div>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 8 }}>
          <button className="action-btn" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>Anterior</button>
          <button className="action-btn" onClick={() => setStep((s) => Math.min(steps.length - 1, s + 1))} disabled={step === steps.length - 1}>Próximo</button>
        </div>

        <div className="card-surface" style={{ padding: 12 }}>
          <div style={{ fontSize: 12, color: '#6b7280' }}>
            Importante: este setup salva <b>Serviços</b>, <b>Profissionais</b> e dados do <b>Estabelecimento</b> no banco.
            As políticas avançadas (depósito/no-show/canais) ficam guardadas no SQL em um perfil de setup para usarmos no booking e finanças.
          </div>
        </div>
      </div>
    </div>
  )
}
