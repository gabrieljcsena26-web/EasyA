import React, { useEffect, useMemo, useState } from 'react'
import Header from '../components/dashboard/Header'
import API from '../utils/api'
import '../components/dashboard/dashboard.css'
import { useI18n } from '../i18n'
import { isDemoMode, setDemoMode, demoBadgeStyle } from '../utils/demo'
import { demoInvoices } from '../utils/demoData'
import { Card, Callout, KpiCard } from '../components/ui/Premium'

function monthKey(d = new Date()) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

function normalizeSuccessData(resp) {
  if (resp && typeof resp === 'object' && 'data' in resp) return resp.data
  return resp
}

function centsToMoney(cents = 0, currency = 'EUR') {
  const v = (Number(cents) || 0) / 100
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: currency || 'EUR' }).format(v)
  } catch (_) {
    return `${v.toFixed(2)} ${currency || ''}`.trim()
  }
}

function dtSafe(v) {
  if (!v) return null
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? null : d
}

function inMonth(dateObj, ym) {
  if (!dateObj) return false
  const y = dateObj.getFullYear()
  const m = String(dateObj.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}` === ym
}

function startOfWeek(d) {
  const x = new Date(d)
  const day = (x.getDay() + 6) % 7 // monday=0
  x.setDate(x.getDate() - day)
  x.setHours(0, 0, 0, 0)
  return x
}

function escapeHtml(v) {
  return String(v ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function invoiceStatusMeta(statusRaw) {
  const s = String(statusRaw || '').toLowerCase().trim()
  if (s === 'pago' || s.includes('pago')) return { label: statusRaw || 'Pago', tone: 'good' }
  if (s === 'cancelado' || s.includes('cancel')) return { label: statusRaw || 'Cancelado', tone: 'bad' }
  return { label: statusRaw || 'Emitido', tone: 'neutral' }
}

export default function Finance() {
  const { t } = useI18n()
  const demo = isDemoMode()
  const [selectedMonth, setSelectedMonth] = useState(() => monthKey())
  const [loading, setLoading] = useState(true)
  const [errorKey, setErrorKey] = useState(null)

  const [trial, setTrial] = useState(null)
  const [subStatus, setSubStatus] = useState(null)
  const [subBusy, setSubBusy] = useState(false)
  const [subErr, setSubErr] = useState(null)

  const [invoices, setInvoices] = useState([])

  const CACHE_KEY = 'ea_cache_finance_invoices_v1'
  const CACHE_TTL_MS = 2 * 60 * 1000

  useEffect(() => {
    let mounted = true

    if (demo) {
      setErrorKey(null)
      setInvoices(demoInvoices())
      setLoading(false)
      return () => { mounted = false }
    }

    // Hydrate from cache to avoid "reload" feeling when navigating back.
    try {
      const raw = localStorage.getItem(CACHE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        const ts = Number(parsed?.ts || 0)
        const items = parsed?.items
        if (Array.isArray(items) && (Date.now() - ts) < CACHE_TTL_MS) {
          setInvoices(items)
          setLoading(false)
        }
      }
    } catch (_) {}

    async function load() {
      // If we already have cached items, refresh silently.
      const hasData = Array.isArray(invoices) && invoices.length > 0
      if (!hasData) setLoading(true)
      setErrorKey(null)
      try {
        const invRaw = await API.get('/billing/invoices')
        const inv = normalizeSuccessData(invRaw)
        if (!mounted) return
        const list = Array.isArray(inv) ? inv : []
        setInvoices(list)
        try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), items: list })) } catch (_) {}
      } catch (e) {
        if (!mounted) return
        setErrorKey('err_invoices_load')
        if (!hasData) setInvoices([])
      } finally {
        if (mounted) setLoading(false)
      }
    }

    load()
    return () => { mounted = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    let mounted = true
    async function loadTrial() {
      try {
        const data = await API.get('/admin/trial-status')
        if (!mounted) return
        const tr = (data && data.trial && typeof data.trial === 'object') ? data.trial : null
        setTrial(tr)
      } catch (_) {
        if (!mounted) return
        setTrial(null)
      }
    }
    loadTrial()
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    let mounted = true
    async function loadSubStatus() {
      if (demo) return
      try {
        const raw = await API.get('/billing/subscription/status')
        const data = normalizeSuccessData(raw)
        if (!mounted) return
        setSubStatus(data)
      } catch (_) {
        if (!mounted) return
        setSubStatus(null)
      }
    }
    loadSubStatus()
    return () => { mounted = false }
  }, [demo])

  async function startStripeCheckout() {
    setSubErr(null)
    setSubBusy(true)
    try {
      const raw = await API.post('/billing/subscription/checkout', {})
      const data = normalizeSuccessData(raw)
      const url = data?.checkout_session?.url
      if (!url) throw new Error('missing_checkout_url')
      window.location.href = String(url)
    } catch (_) {
      setSubErr('finance_stripe_checkout_failed')
    } finally {
      setSubBusy(false)
    }
  }

  async function openStripePortal() {
    setSubErr(null)
    setSubBusy(true)
    try {
      const raw = await API.post('/billing/subscription/portal', {})
      const data = normalizeSuccessData(raw)
      const url = data?.portal_session?.url
      if (!url) throw new Error('missing_portal_url')
      window.open(String(url), '_blank', 'noopener,noreferrer')
    } catch (_) {
      setSubErr('finance_stripe_portal_failed')
    } finally {
      setSubBusy(false)
    }
  }

  const salesWhatsApp = useMemo(() => {
    try {
      const w = (typeof window !== 'undefined') ? window : null
      const v = w && w.__SALES_WHATSAPP__ ? String(w.__SALES_WHATSAPP__) : ''
      if (v) return v
    } catch (_) {}
    try {
      if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_SALES_WHATSAPP) {
        return String(import.meta.env.VITE_SALES_WHATSAPP)
      }
    } catch (_) {}
    try {
      if (typeof process !== 'undefined' && process.env && process.env.REACT_APP_SALES_WHATSAPP) {
        return String(process.env.REACT_APP_SALES_WHATSAPP)
      }
    } catch (_) {}
    return ''
  }, [])

  function toWaDigits(v) {
    const raw = String(v || '').trim()
    if (!raw) return ''
    return raw.replace(/\D+/g, '')
  }

  const planWhatsAppLink = useMemo(() => {
    const digits = toWaDigits(salesWhatsApp)
    if (!digits) return ''
    const slug = (() => {
      try {
        const raw = localStorage.getItem('ea_admin_config')
        const cfg = raw ? JSON.parse(raw) : null
        return String(cfg?.business?.slug || '').trim()
      } catch (_) {
        return ''
      }
    })()
    const msg = `Olá! Quero ativar o plano do EasyAgenda. Slug: ${slug || '(sem slug)'}.`
    return `https://wa.me/${digits}?text=${encodeURIComponent(msg)}`
  }, [salesWhatsApp])

  const derived = useMemo(() => {
    const now = new Date()
    const weekStart = startOfWeek(now)
    const weekEnd = new Date(weekStart)
    weekEnd.setDate(weekEnd.getDate() + 7)

    const month = []
    const week = []

    for (const inv of invoices) {
      const created = dtSafe(inv.created_at)
      if (created && inMonth(created, selectedMonth)) month.push(inv)
      if (created && created >= weekStart && created < weekEnd) week.push(inv)
    }

    const sum = (arr, filterFn) => arr.reduce((acc, inv) => {
      if (filterFn && !filterFn(inv)) return acc
      return acc + (Number(inv.valor_centavos) || 0)
    }, 0)

    const count = (arr, filterFn) => arr.reduce((acc, inv) => acc + ((filterFn && !filterFn(inv)) ? 0 : 1), 0)

    const isPaid = (inv) => String(inv.status || '').toLowerCase() === 'pago'
    const isCanceled = (inv) => String(inv.status || '').toLowerCase() === 'cancelado'

    const currency = (month.find(x => x.currency)?.currency) || (week.find(x => x.currency)?.currency) || 'EUR'

    // revenue chart per day (issued)
    const perDay = new Map()
    for (const inv of month) {
      const created = dtSafe(inv.created_at)
      if (!created) continue
      const k = created.toISOString().slice(0, 10)
      perDay.set(k, (perDay.get(k) || 0) + (Number(inv.valor_centavos) || 0))
    }

    const perDaySorted = Array.from(perDay.entries()).sort((a, b) => a[0].localeCompare(b[0]))

    return {
      currency,
      month,
      week,
      totals: {
        monthIssued: sum(month),
        monthPaid: sum(month, isPaid),
        monthCanceled: sum(month, isCanceled),
        monthCount: count(month),
        weekIssued: sum(week),
        weekPaid: sum(week, isPaid),
        weekCount: count(week),
      },
      perDaySorted,
    }
  }, [invoices, selectedMonth])

  const whatsappWarnPct = 80
  const whatsappOverageValue = useMemo(() => {
    const cur = derived?.currency || 'EUR'
    const v = 0.03
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: cur }).format(v)
    } catch (_) {
      return `${v.toFixed(2)} ${cur}`.trim()
    }
  }, [derived?.currency])

  const showTrialPlanCta = useMemo(() => {
    if (!trial || typeof trial !== 'object') return false
    if (trial.active_plan) return false
    if (!trial.started) return true
    if (trial.expired) return true
    if (typeof trial.days_left === 'number' && trial.days_left <= 2) return true
    return false
  }, [trial])

  const stripeConfigured = !!subStatus?.stripe?.configured && !!subStatus?.stripe?.subscription_configured
  const stripeHasCustomer = !!subStatus?.stripe?.customer_id

  const invoiceStatusClass = (statusRaw) => {
    const tone = invoiceStatusMeta(statusRaw).tone
    if (tone === 'good') return 'status-confirmado'
    if (tone === 'bad') return 'status-cancelado'
    return 'status-pending'
  }

  function handlePrintMonthlyReport() {
    const title = `Relatório Financeiro – ${selectedMonth}`
    const generatedAt = new Date()
    const allRows = derived.month.slice().sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')))
    const paidRows = allRows.filter(inv => invoiceStatusMeta(inv.status).tone === 'good')
    const paidCount = paidRows.length
    const paidTotal = paidRows.reduce((acc, inv) => acc + (Number(inv.valor_centavos) || 0), 0)
    const avgTicket = paidCount > 0 ? Math.round(paidTotal / paidCount) : 0

    // Investments/expenses are not modeled yet; provide a clean, printable section for manual accounting.
    const investmentsRows = [
      { date: '', category: 'Equipamentos', desc: '', amount: '' },
      { date: '', category: 'Marketing', desc: '', amount: '' },
      { date: '', category: 'Software', desc: '', amount: '' },
      { date: '', category: 'Reformas', desc: '', amount: '' },
      { date: '', category: 'Outros', desc: '', amount: '' },
    ]
    const investmentsTotal = 0
    const netResult = paidTotal - investmentsTotal

    const html = `
      <html lang="pt-BR">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>${escapeHtml(title)}</title>
          <style>
            :root{
              --ink:#0b1220;
              --muted:#5b6476;
              --line:#e7eaf0;
              --bg:#ffffff;
              --soft:#f6f8fc;
              --accent:#2563eb;
              --accent2:#60a5fa;
              --goodBg:#ecfdf5;
              --goodInk:#065f46;
              --badBg:#fff1f2;
              --badInk:#7f1d1d;
              --warnBg:#fffbeb;
              --warnInk:#92400e;
              --shadow: 0 12px 30px rgba(15,23,42,0.08);
            }
            *{box-sizing:border-box}
            html,body{background:var(--soft);margin:0;padding:0;color:var(--ink)}
            body{font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";}
            a{color:inherit;text-decoration:none}

            @page{margin:18mm}
            @media print{
              html,body{background:#fff}
              .page{box-shadow:none;border:0}
              .no-print{display:none !important}
            }

            .page{max-width:980px;margin:18px auto;background:var(--bg);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);overflow:hidden}
            .topbar{padding:22px 26px;background:linear-gradient(135deg, rgba(37,99,235,0.10), rgba(96,165,250,0.10));border-bottom:1px solid var(--line)}
            .brand{display:flex;align-items:center;gap:12px}
            .mark{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;letter-spacing:0.5px}
            .titleWrap{display:flex;flex-direction:column;gap:2px}
            .title{font-size:20px;font-weight:900;letter-spacing:-0.02em;margin:0}
            .subtitle{margin:0;color:var(--muted);font-size:13px}

            .content{padding:18px 26px 26px 26px}
            .meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
            .chip{display:inline-flex;align-items:center;gap:8px;padding:8px 10px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--ink);font-size:12px}
            .chip b{font-weight:900}

            .kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:16px}
            .kpi{background:linear-gradient(180deg,#fff, #fbfcff);border:1px solid var(--line);border-radius:14px;padding:12px 12px 10px 12px}
            .kpi .lbl{color:var(--muted);font-size:12px;margin-bottom:6px}
            .kpi .val{font-size:18px;font-weight:900;letter-spacing:-0.02em}
            .kpi .hint{color:var(--muted);font-size:11px;margin-top:4px}

            .section{margin-top:18px}
            .h2{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:0 0 10px 0}
            .h2 h2{margin:0;font-size:14px;font-weight:900;letter-spacing:-0.01em}
            .h2 p{margin:0;color:var(--muted);font-size:12px}

            .note{border:1px solid var(--line);background:var(--soft);border-radius:14px;padding:12px;color:var(--muted);font-size:12px;line-height:1.4}
            .note ul{margin:10px 0 0 0;padding-left:18px}
            .note li{margin:4px 0}

            table{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border:1px solid var(--line);border-radius:14px;background:#fff}
            thead th{position:sticky;top:0;background:linear-gradient(180deg,#fbfcff,#f6f8fc);text-align:left;color:#334155;font-size:12px;padding:10px 12px;border-bottom:1px solid var(--line)}
            tbody td{font-size:12px;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}
            tbody tr:nth-child(2n) td{background:#fcfdff}
            tbody tr:last-child td{border-bottom:0}
            .num{text-align:right;font-variant-numeric:tabular-nums}
            .mono{font-variant-numeric:tabular-nums}

            .badge{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;font-weight:800;font-size:11px;border:1px solid transparent;white-space:nowrap}
            .badge.neutral{background:#f3f4f6;color:#111827;border-color:#e5e7eb}
            .badge.good{background:var(--goodBg);color:var(--goodInk);border-color:#dcfce7}
            .badge.bad{background:var(--badBg);color:var(--badInk);border-color:#fee2e2}

            .footer{margin-top:16px;display:flex;justify-content:space-between;gap:10px;align-items:center;color:var(--muted);font-size:11px}
            .footer .small{max-width:640px;line-height:1.35}
            .btn{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);background:#fff;padding:8px 10px;border-radius:10px;font-weight:800;font-size:12px;cursor:pointer}

            @media (max-width:900px){
              .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
              .page{border-radius:14px}
            }
          </style>
        </head>
        <body>
          <div class="page">
            <div class="topbar">
              <div class="brand">
                <div class="mark">EA</div>
                <div class="titleWrap">
                  <h1 class="title">${escapeHtml(title)}</h1>
                  <p class="subtitle">Resumo mensal para contabilidade/conciliação</p>
                </div>
              </div>

              <div class="meta">
                <div class="chip"><span>Período</span> <b>${escapeHtml(selectedMonth)}</b></div>
                <div class="chip"><span>Gerado em</span> <b>${escapeHtml(generatedAt.toLocaleString())}</b></div>
                <div class="chip"><span>Moeda</span> <b>${escapeHtml(derived.currency || '')}</b></div>
              </div>
            </div>

            <div class="content">
              <div class="kpis">
                <div class="kpi"><div class="lbl">Faturado (mês)</div><div class="val">${escapeHtml(centsToMoney(paidTotal, derived.currency))}</div><div class="hint">Somente faturas pagas</div></div>
                <div class="kpi"><div class="lbl">Pagamentos (mês)</div><div class="val">${escapeHtml(paidCount)}</div><div class="hint">Quantidade de faturas pagas</div></div>
                <div class="kpi"><div class="lbl">Ticket médio</div><div class="val">${escapeHtml(centsToMoney(avgTicket, derived.currency))}</div><div class="hint">Faturado ÷ pagamentos</div></div>
                <div class="kpi"><div class="lbl">Resultado líquido</div><div class="val">${escapeHtml(centsToMoney(netResult, derived.currency))}</div><div class="hint">Faturado − investimentos</div></div>
              </div>

              <div class="section">
                <div class="h2">
                  <h2>Notas rápidas</h2>
                  <p>Para evitar confusões na leitura</p>
                </div>
                <div class="note">
                  <div><b>Este PDF mostra somente faturas pagas</b> (faturado). Canceladas/pendentes não entram na lista nem nos totais.</div>
                  <ul>
                    <li>Este relatório é apenas leitura/ impressão (não altera dados).</li>
                    <li>Se precisar do detalhe por cliente, use o ID do cliente como referência.</li>
                    <li>O bloco de investimentos/despesas é para organização contábil (preenchimento manual).</li>
                  </ul>
                </div>
              </div>

              <div class="section">
                <div class="h2">
                  <h2>Faturas pagas (faturamento do mês)</h2>
                  <p>${escapeHtml(paidCount)} registro(s)</p>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th style="width:170px">Data</th>
                      <th style="width:74px">ID</th>
                      <th style="width:120px">Cliente (ID)</th>
                      <th>Descrição</th>
                      <th style="width:120px" class="num">Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${paidRows.map(inv => {
                      const v = centsToMoney(inv.valor_centavos, inv.currency || derived.currency)
                      const cAt = inv.created_at ? new Date(inv.created_at).toLocaleString() : ''
                      return `
                        <tr>
                          <td class="mono">${escapeHtml(cAt)}</td>
                          <td class="mono">${escapeHtml(inv.id)}</td>
                          <td class="mono">${escapeHtml(inv.cliente_id)}</td>
                          <td>${escapeHtml(inv.descricao || '')}</td>
                          <td class="num mono">${escapeHtml(v)}</td>
                        </tr>
                      `
                    }).join('')}
                    ${paidRows.length === 0 ? `
                      <tr>
                        <td colspan="5" style="color:var(--muted);padding:14px">Sem faturas pagas no mês selecionado.</td>
                      </tr>
                    ` : ''}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colspan="4" style="padding:12px;border-top:1px solid var(--line);background:linear-gradient(180deg,#fbfcff,#f6f8fc);font-weight:900">Total faturado</td>
                      <td class="num mono" style="padding:12px;border-top:1px solid var(--line);background:linear-gradient(180deg,#fbfcff,#f6f8fc);font-weight:900">${escapeHtml(centsToMoney(paidTotal, derived.currency))}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              <div class="section">
                <div class="h2">
                  <h2>Investimentos / Despesas (opcional)</h2>
                  <p>Organize separadamente para contabilidade</p>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th style="width:170px">Data</th>
                      <th style="width:180px">Categoria</th>
                      <th>Descrição</th>
                      <th style="width:140px" class="num">Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${investmentsRows.map((r) => `
                      <tr>
                        <td class="mono">${escapeHtml(r.date)}</td>
                        <td>${escapeHtml(r.category)}</td>
                        <td style="color:var(--muted)">________________________________</td>
                        <td class="num mono">__________</td>
                      </tr>
                    `).join('')}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colspan="3" style="padding:12px;border-top:1px solid var(--line);background:linear-gradient(180deg,#fbfcff,#f6f8fc);font-weight:900">Total investimentos</td>
                      <td class="num mono" style="padding:12px;border-top:1px solid var(--line);background:linear-gradient(180deg,#fbfcff,#f6f8fc);font-weight:900">${escapeHtml(centsToMoney(investmentsTotal, derived.currency))}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              <div class="section">
                <div class="h2">
                  <h2>Resumo contábil</h2>
                  <p>Visão rápida em formato planilha</p>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th class="num" style="width:180px">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><b>Faturamento (pagos)</b></td>
                      <td class="num mono"><b>${escapeHtml(centsToMoney(paidTotal, derived.currency))}</b></td>
                    </tr>
                    <tr>
                      <td>Investimentos / despesas</td>
                      <td class="num mono">${escapeHtml(centsToMoney(investmentsTotal, derived.currency))}</td>
                    </tr>
                    <tr>
                      <td><b>Resultado líquido</b></td>
                      <td class="num mono"><b>${escapeHtml(centsToMoney(netResult, derived.currency))}</b></td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div class="footer">
                <div class="small">Sugestão: use “Salvar como PDF” no diálogo de impressão para arquivar o mês. Este PDF é focado em faturamento (pagos). Para completar investimentos, preencha o bloco opcional.</div>
                <button class="btn no-print" onclick="window.print()">Imprimir / Salvar PDF</button>
              </div>
            </div>
          </div>
        </body>
      </html>
    `

    const w = window.open('', '_blank')
    if (!w) return
    w.document.open()
    w.document.write(html)
    w.document.close()
    w.focus()
    // User prints/saves as PDF; we do not auto-print to avoid popup blockers.
  }

  const maxDay = Math.max(1, ...derived.perDaySorted.map(([, v]) => v))

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0 }}>{t('finance_title')}</h3>
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
              <div style={{ color: '#6b7280', fontSize: 13, marginTop: 4 }}>{t('finance_sub')}</div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <label style={{ fontSize: 13, color: '#374151' }}>{t('month_label')}</label>
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
              <button className="action-btn" onClick={handlePrintMonthlyReport} title={t('finance_print_title')}>{t('finance_print')}</button>
            </div>
          </div>

          {errorKey && <div style={{ color: 'crimson', marginTop: 10 }}>{t(errorKey)}</div>}
          {loading ? (
            <div style={{ padding: 18, color: '#6b7280' }}>{t('loading')}</div>
          ) : (
            <>
              {showTrialPlanCta ? (
                <div style={{ marginTop: 12 }}>
                  <Callout
                    tone={trial?.expired ? 'danger' : 'warn'}
                    title={t('trial_banner_title')}
                  >
                    <div style={{ display: 'grid', gap: 10 }}>
                      <div>
                        {!trial?.started
                          ? t('trial_banner_not_started')
                          : trial?.expired
                          ? t('trial_banner_expired')
                          : String(t('trial_banner_running_fmt') || '').replace('{days}', String(trial?.days_left ?? ''))}
                      </div>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                        {stripeConfigured ? (
                          <button
                            type="button"
                            className="action-btn"
                            onClick={startStripeCheckout}
                            disabled={subBusy}
                            style={{ background: '#0f1724', color: '#fff', border: '1px solid rgba(15,23,42,0.12)', padding: '10px 12px', borderRadius: 12, fontWeight: 950 }}
                          >
                            {subBusy ? t('finance_stripe_redirecting') : t('finance_stripe_pay_card')}
                          </button>
                        ) : null}

                        {stripeHasCustomer ? (
                          <button
                            type="button"
                            className="action-btn"
                            onClick={openStripePortal}
                            disabled={subBusy}
                            style={{ padding: '10px 12px', borderRadius: 12, fontWeight: 950 }}
                          >
                            {t('finance_stripe_manage')}
                          </button>
                        ) : null}

                        {planWhatsAppLink ? (
                          <a
                            href={planWhatsAppLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: 'fit-content',
                              padding: '10px 12px',
                              borderRadius: 12,
                              fontWeight: 950,
                              background: 'transparent',
                              color: '#0f1724',
                              textDecoration: 'none',
                              border: '1px solid rgba(15,23,42,0.16)',
                            }}
                          >
                            {t('trial_banner_cta_plan')}
                          </a>
                        ) : null}
                      </div>

                      {subErr ? (
                        <div style={{ fontSize: 12, color: '#b91c1c' }}>{t(subErr)}</div>
                      ) : null}

                      {!stripeConfigured && !planWhatsAppLink ? (
                        <div style={{ fontSize: 12, color: '#6b7280' }}>
                          {t('finance_stripe_not_configured_hint')}
                        </div>
                      ) : null}
                    </div>
                  </Callout>
                </div>
              ) : null}

              <div style={{ marginTop: 12 }}>
                <Callout tone="info" title={t('finance_whatsapp_budget_title')}>
                  <div style={{ display: 'grid', gap: 6 }}>
                    <div>{t('finance_whatsapp_budget_included')}</div>
                    <div>{t('finance_whatsapp_budget_warn').replace('{pct}', String(whatsappWarnPct))}</div>
                    <div>{t('finance_whatsapp_budget_overage').replace('{value}', String(whatsappOverageValue))}</div>
                    <div style={{ color: '#6b7280' }}>{t('finance_whatsapp_budget_transparency')}</div>
                  </div>
                </Callout>
              </div>

              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
                <KpiCard
                  label="Emitido (mês)"
                  value={centsToMoney(derived.totals.monthIssued, derived.currency)}
                  hint={`Pago: ${centsToMoney(derived.totals.monthPaid, derived.currency)} • Nº: ${derived.totals.monthCount}`}
                  tone="neutral"
                />
                <KpiCard
                  label="Emitido (semana atual)"
                  value={centsToMoney(derived.totals.weekIssued, derived.currency)}
                  hint={`Pago: ${centsToMoney(derived.totals.weekPaid, derived.currency)} • Nº: ${derived.totals.weekCount}`}
                  tone="neutral"
                />
                <KpiCard
                  label="Cancelado (mês)"
                  value={centsToMoney(derived.totals.monthCanceled, derived.currency)}
                  hint="Total marcado como cancelado no período."
                  tone={derived.totals.monthCanceled > 0 ? 'warn' : 'neutral'}
                />
              </div>

              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                <Card
                  title="Visão geral"
                  subtitle="Resumo simples para entender o mês rapidamente."
                  right={
                    <button className="action-btn" onClick={handlePrintMonthlyReport} title={t('finance_print_title')}>
                      Exportar PDF
                    </button>
                  }
                >
                  <Callout tone="info" title="PDF do mês">
                    Gera uma página pronta para imprimir/salvar como PDF (Excel/contabilidade). Não envia dados para fora.
                  </Callout>
                </Card>

                <Card title="Como interpretar" subtitle="Definições rápidas (para evitar confusão).">
                  <div style={{ display: 'grid', gap: 10 }}>
                    <Callout tone="success" title="Emitido">
                      Faturas criadas no mês (não significa pago).
                    </Callout>
                    <Callout tone="info" title="Pago">
                      Status “pago”. Útil para conciliação.
                    </Callout>
                    <Callout tone="warn" title="Cancelado">
                      Faturas marcadas como canceladas (não entram no pago).
                    </Callout>
                  </div>
                </Card>
              </div>
            </>
          )}
        </div>

        {!loading && !errorKey && (
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 12 }}>
            <div className="agenda-card">
              <div className="agenda-header" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Faturamento diário (mês)</h3>
              </div>
              {derived.perDaySorted.length === 0 ? (
                <div style={{ color: '#6b7280', padding: 14 }}>Sem faturas no período.</div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 180, padding: '10px 4px 4px 4px' }}>
                  {derived.perDaySorted.slice(-24).map(([day, v]) => {
                    const h = Math.max(6, Math.round((v / maxDay) * 160))
                    return (
                      <div key={day} title={`${day}: ${centsToMoney(v, derived.currency)}`} style={{ flex: 1, minWidth: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                        <div style={{ width: '100%', height: h, borderRadius: 8, background: 'linear-gradient(180deg,#93c5fd,#1d4ed8)' }} />
                        <div style={{ fontSize: 10, color: '#6b7280' }}>{day.slice(8, 10)}</div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="agenda-card">
              <div className="agenda-header" style={{ marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Últimas faturas</h3>
              </div>
              <div className="agenda-table">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Valor</th>
                      <th>Criado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {derived.month.slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || ''))).slice(0, 12).map((inv) => (
                      <tr key={inv.id}>
                        <td>{inv.id}</td>
                        <td>
                          <span className={`status-badge ${invoiceStatusClass(inv.status)}`}>{inv.status || 'Emitido'}</span>
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 700 }}>{centsToMoney(inv.valor_centavos, inv.currency || derived.currency)}</td>
                        <td style={{ color: '#6b7280', fontSize: 12 }}>{inv.created_at ? new Date(inv.created_at).toLocaleString() : ''}</td>
                      </tr>
                    ))}
                    {derived.month.length === 0 && (
                      <tr><td colSpan={4} style={{ color: '#6b7280', padding: 14 }}>Sem faturas no mês selecionado.</td></tr>
                    )}
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
