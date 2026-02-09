import React, { useState, useEffect } from 'react'

const STORAGE_KEY = 'DEV_JWT_TOKEN'

const DevTokenInput = () => {
  const [token, setToken] = useState('')

  useEffect(() => {
    const t = localStorage.getItem(STORAGE_KEY) || ''
    setToken(t)
    if (t) window.__DEV_TOKEN__ = t
  }, [])

  const save = () => {
    localStorage.setItem(STORAGE_KEY, token)
    window.__DEV_TOKEN__ = token
    alert('Dev token salvo')
  }

  const clear = () => {
    localStorage.removeItem(STORAGE_KEY)
    setToken('')
    window.__DEV_TOKEN__ = undefined
  }

  return (
    <div className="dev-token-input" data-e2e="dev-token-wrap">
      <input
        data-e2e="dev-token-input"
        placeholder="Dev JWT (opcional)"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        style={{width:240}}
      />
      <button data-e2e="dev-token-save" onClick={save}>Save</button>
      <button data-e2e="dev-token-clear" onClick={clear} style={{marginLeft:6}}>Clear</button>
    </div>
  )
}

export default DevTokenInput
