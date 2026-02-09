import React, { createContext, useContext, useMemo, useState } from 'react'
import { getStoredLang, normalizeLangCode, t as translate } from './i18n'

const I18nContext = createContext({
  lang: 'pt-BR',
  setLang: () => {},
  t: (key) => key,
})

export function LanguageProvider({ children }) {
export function LanguageProvider({ children, storageKey = 'ea_lang_admin' }) {
  const [lang, setLangState] = useState(() => getStoredLang({ storageKey }))

  const setLang = (next) => {
    const norm = normalizeLangCode(next)
    if (!norm) return
    setLangState(norm)
    try { localStorage.setItem(storageKey, norm) } catch (_) {}
  }

  const value = useMemo(() => ({
    lang,
    setLang,
    t: (key) => translate(lang, key),
  }), [lang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}
