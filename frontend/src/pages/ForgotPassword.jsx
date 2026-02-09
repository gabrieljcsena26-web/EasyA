import React, { useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import API from '../utils/api';
import Header from '../components/dashboard/Header';
import { useI18n } from '../i18n';

export default function ForgotPassword() {
  const { t } = useI18n();
  const location = useLocation();

  const prefill = useMemo(() => {
    try {
      const qs = new URLSearchParams(location.search || '');
      return String(qs.get('identifier') || '');
    } catch (_) {
      return '';
    }
  }, [location.search]);

  const [identifier, setIdentifier] = useState(prefill);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await API.post('/auth/forgot-password', { identifier });
      setDone(true);
    } catch (err) {
      // Não vazar detalhes: mesma UX de sucesso, mas sem travar o usuário.
      setDone(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ maxWidth: 520, margin: '18px auto', padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>{t('forgot_title')}</h3>
          <div style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>{t('forgot_sub')}</div>

          {done ? (
            <div>
              <div data-e2e="forgot-success" style={{ padding: 12, borderRadius: 12, background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#065f46', fontSize: 13 }}>
                {t('forgot_success')}
              </div>
              <div style={{ marginTop: 12, fontSize: 13 }}>
                <Link to="/login">{t('back_to_login')}</Link>
              </div>
            </div>
          ) : (
            <form onSubmit={onSubmit}>
              <label style={{ display: 'block', fontSize: 13, marginBottom: 6 }}>{t('forgot_identifier_label')}</label>
              <input
                data-e2e="forgot-identifier"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                style={{ width: '100%', padding: 10, border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 12 }}
                autoComplete="username"
                placeholder="seu-slug | email"
              />

              {error ? (
                <div style={{ marginBottom: 12, color: '#b91c1c', fontSize: 13 }}>{error}</div>
              ) : null}

              <button
                data-e2e="forgot-submit"
                type="submit"
                disabled={loading || !identifier}
                className="action-btn"
                style={{ width: '100%', justifyContent: 'center' }}
              >
                {loading ? t('loading') : t('forgot_cta')}
              </button>

              <div style={{ marginTop: 10, color: '#6b7280', fontSize: 12 }}>
                <Link to="/login">{t('back_to_login')}</Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
