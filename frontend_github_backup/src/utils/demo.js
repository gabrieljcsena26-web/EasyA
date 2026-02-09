export function isDemoMode() {
  if (typeof window === 'undefined') return false
  try {
    const params = new URLSearchParams(window.location.search || '')
    const v = String(params.get('demo') || '').toLowerCase()
    if (v === '1' || v === 'true' || v === 'yes') return true
  } catch (_) {}

  try {
    return localStorage.getItem('ea_demo') === '1'
  } catch (_) {
    return false
  }
}

export function setDemoMode(next) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem('ea_demo', next ? '1' : '0')
  } catch (_) {}
  try {
    const url = new URL(window.location.href)
    if (next) url.searchParams.set('demo', '1')
    else url.searchParams.delete('demo')
    window.location.href = url.toString()
  } catch (_) {
    window.location.reload()
  }
}

export function demoBadgeStyle() {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 10px',
    borderRadius: 999,
    background: 'linear-gradient(180deg,#ecfdf5,#d1fae5)',
    color: '#065f46',
    border: '1px solid #dcfce7',
    fontWeight: 900,
    fontSize: 12,
  }
}
