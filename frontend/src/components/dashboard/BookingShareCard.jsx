import React, { useMemo, useState } from 'react'
import QRCode from 'react-qr-code'
import { useI18n } from '../../i18n'

function safeTrim(v) {
  return String(v || '').trim()
}

function getBookingPublicBaseUrl() {
  try {
    if (typeof window !== 'undefined' && window.__BOOKING_PUBLIC_BASE_URL__) {
      const v = safeTrim(window.__BOOKING_PUBLIC_BASE_URL__)
      if (v) return v.replace(/\/$/, '')
    }
  } catch (_) {}

  try {
    // Vite env (when available)
    // eslint-disable-next-line no-undef
    const env = (import.meta && import.meta.env) ? import.meta.env : null
    const v = env && env.VITE_BOOKING_PUBLIC_BASE_URL ? safeTrim(env.VITE_BOOKING_PUBLIC_BASE_URL) : ''
    if (v) return v.replace(/\/$/, '')
  } catch (_) {}

  try {
    const origin = (typeof window !== 'undefined' && window.location && window.location.origin) ? String(window.location.origin) : ''
    // If dashboard is being served from backend port, default booking to the frontend dev server.
    if (origin && /^https?:\/\//i.test(origin) && !/:8000\b/.test(origin)) return origin.replace(/\/$/, '')
  } catch (_) {}

  // Safe default for local dev
  return 'http://localhost:3002'
}

function buildBookingUrl(slug) {
  const s = safeTrim(slug)
  if (!s) return ''
  const base = getBookingPublicBaseUrl()
  return `${base}/booking/${encodeURIComponent(s)}`
}

async function copyText(text) {
  const value = safeTrim(text)
  if (!value) return false

  try {
    if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch (_) {}

  try {
    const ta = document.createElement('textarea')
    ta.value = value
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return Boolean(ok)
  } catch (_) {
    return false
  }
}

export default function BookingShareCard({ slug, businessName }) {
  const { t } = useI18n()
  const [showQr, setShowQr] = useState(false)
  const [copied, setCopied] = useState(false)

  const bookingUrl = useMemo(() => buildBookingUrl(slug), [slug])

  return (
    <div className="card-surface" style={{ padding: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontWeight: 900, color: '#0f1724' }}>{t('booking_share_title')}</div>
          <div style={{ fontSize: 13, color: '#6b7280' }}>
            {businessName ? t('booking_share_sub_fmt').replace('{name}', String(businessName)) : t('booking_share_sub')}
          </div>
        </div>
        <button
          type="button"
          className="ea-pill"
          onClick={() => setShowQr((v) => !v)}
          style={{ border: '1px solid #e5e7eb', background: '#fff' }}
          aria-expanded={showQr ? 'true' : 'false'}
        >
          {showQr ? t('booking_share_hide_qr') : t('booking_share_show_qr')}
        </button>
      </div>

      {!bookingUrl ? (
        <div style={{ marginTop: 10, padding: 12, borderRadius: 12, background: '#fef2f2', border: '1px solid #fecaca', color: '#7f1d1d', fontSize: 13 }}>
          {t('booking_share_missing_slug')}
        </div>
      ) : (
        <div style={{ marginTop: 10, display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <a
              href={bookingUrl}
              target="_blank"
              rel="noreferrer"
              data-e2e="booking-link"
              style={{ color: '#2563eb', fontWeight: 800, textDecoration: 'none' }}
              title={bookingUrl}
            >
              {t('booking_share_open')}
            </a>
            <div style={{ fontSize: 12, color: '#6b7280', overflowWrap: 'anywhere' }}>{bookingUrl}</div>
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            {copied ? <div style={{ fontSize: 12, color: '#16a34a', fontWeight: 800 }}>{t('booking_share_copied')}</div> : null}
            <button
              type="button"
              className="ea-pill"
              onClick={async () => {
                const ok = await copyText(bookingUrl)
                setCopied(Boolean(ok))
                window.setTimeout(() => setCopied(false), 1500)
              }}
              style={{ border: '1px solid rgba(37,99,235,0.25)', background: '#eff6ff', color: '#1d4ed8' }}
            >
              {t('booking_share_copy')}
            </button>
          </div>

          {showQr ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 10 }}>
              <div
                style={{ background: '#fff', padding: 12, borderRadius: 16, border: '1px solid #e5e7eb', boxShadow: '0 10px 22px rgba(2,6,23,0.06)' }}
                data-e2e="booking-qr"
              >
                <QRCode value={bookingUrl} size={160} />
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
