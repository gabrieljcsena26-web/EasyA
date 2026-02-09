export function buildApiUrl(apiBase, path) {
  const base = String(apiBase || '').trim().replace(/\/$/, '')
  const p = String(path || '').trim()
  if (!p) return ''
  if (/^https?:\/\//i.test(p)) return p
  if (base) return p.startsWith('/') ? base + p : base + '/' + p
  return p.startsWith('/') ? p : '/' + p
}

function shouldRetry(err) {
  // Network errors, aborted, temporary failures.
  const msg = String(err && err.message ? err.message : err)
  return /network|failed to fetch|abort|timeout|ECONN|EAI_AGAIN/i.test(msg)
}

export async function fetchJson(url, {
  method = 'GET',
  headers,
  body,
  timeoutMs = 10000,
  retries = 1,
  signal,
} = {}) {
  const attemptOnce = async () => {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), Math.max(500, Number(timeoutMs) || 10000))

    const onAbort = () => controller.abort()
    if (signal) {
      if (signal.aborted) controller.abort()
      else signal.addEventListener('abort', onAbort, { once: true })
    }

    try {
      const res = await fetch(url, {
        method,
        headers,
        body,
        signal: controller.signal,
      })

      const text = await res.text()
      let json = null
      try { json = text ? JSON.parse(text) : null } catch (_) { json = null }

      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`)
        err.status = res.status
        err.body = json || text
        throw err
      }

      return json
    } finally {
      clearTimeout(timeout)
      if (signal) {
        try { signal.removeEventListener('abort', onAbort) } catch (_) {}
      }
    }
  }

  let lastErr = null
  for (let i = 0; i <= Number(retries || 0); i += 1) {
    try {
      return await attemptOnce()
    } catch (e) {
      lastErr = e
      if (i >= Number(retries || 0)) break
      if (!shouldRetry(e)) break
      await new Promise((r) => setTimeout(r, 250 + i * 250))
    }
  }
  throw lastErr
}
