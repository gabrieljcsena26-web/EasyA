import React from 'react'
import { useI18n } from '../../i18n'

const TopCards = () => {
  const { t } = useI18n()

  return (
    <section className="top-cards top-cards-grid">
      <div className="top-cards-spacer" aria-hidden="true" />

      <div className="greeting-card">
        <div className="greeting-inner">
          <div className="greeting-title">{t('greeting_title')}</div>
          <div className="greeting-name">{t('greeting_sub')}</div>
        </div>
      </div>

      {/* right spacer keeps greeting truly centered */}
      <div className="top-cards-spacer" aria-hidden="true" />
    </section>
  )
}

export default TopCards
