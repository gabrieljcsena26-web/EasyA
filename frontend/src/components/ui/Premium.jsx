import React from 'react'

export function Card({ title, subtitle, right, children, style, headerStyle, bodyStyle }) {
  return (
    <div className="card-surface ea-card" style={style}>
      {(title || subtitle || right) ? (
        <div className="ea-card-header" style={headerStyle}>
          <div style={{ minWidth: 0 }}>
            {title ? <div className="ea-card-title">{title}</div> : null}
            {subtitle ? <div className="ea-card-subtitle">{subtitle}</div> : null}
          </div>
          {right ? <div className="ea-card-right">{right}</div> : null}
        </div>
      ) : null}
      <div className="ea-card-body" style={bodyStyle}>{children}</div>
    </div>
  )
}

export function KpiCard({ label, value, hint, tone = 'neutral' }) {
  return (
    <div className={`ea-kpi ea-kpi-${tone}`}>
      <div className="ea-kpi-label">{label}</div>
      <div className="ea-kpi-value">{value}</div>
      {hint ? <div className="ea-kpi-hint">{hint}</div> : null}
    </div>
  )
}

export function KeyValueList({ items = [] }) {
  const list = Array.isArray(items) ? items : []
  return (
    <div className="ea-kv">
      {list.map((it, idx) => (
        <div key={idx} className="ea-kv-row">
          <div className="ea-kv-key">{it.label}</div>
          <div className="ea-kv-val">{it.value != null && it.value !== '' ? it.value : '—'}</div>
        </div>
      ))}
    </div>
  )
}

export function DebugJson({ label = 'Ver JSON (debug)', value, defaultOpen = false }) {
  return (
    <details className="ea-debug" open={defaultOpen}>
      <summary>{label}</summary>
      <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}

export function Callout({ tone = 'info', title, children }) {
  return (
    <div className={`ea-callout ea-callout-${tone}`}>
      {title ? <div className="ea-callout-title">{title}</div> : null}
      <div className="ea-callout-body">{children}</div>
    </div>
  )
}
