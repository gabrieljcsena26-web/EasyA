import React, { useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import API from '../utils/api';
import Header from '../components/dashboard/Header';
import { useI18n } from '../i18n';

export default function ResetPassword() {
  const { t } = useI18n();
  const location = useLocation();

  const initial = useMemo(() => {
    try {
      const qs = new URLSearchParams(location.search || '');
      return {
        identifier: String(qs.get('identifier') || ''),
        code: String(qs.get('code') || ''),
      };
    } catch (_) {
      return { identifier: '', code: '' };
    }
  }, [location.search]);

  const [identifier, setIdentifier] = useState(initial.identifier);
  const [code, setCode] = useState(initial.code);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError(t('reset_mismatch'));
      return;
    }

    setLoading(true);
    try {
      await API.post('/auth/reset-password', {
        identifier,
        code,
        new_password: newPassword,
      });
      setDone(true);
    } catch (err) {
      setError(t('reset_error'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ maxWidth: 520, margin: '18px auto', padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>{t('reset_title')}</h3>
          <div style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>{t('reset_sub')}</div>

          {done ? (
            <div>
              <div data-e2e="reset-success" style={{ padding: 12, borderRadius: 12, background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#065f46', fontSize: 13 }}>
                {t('reset_success')}
              </div>
              <div style={{ marginTop: 12, fontSize: 13 }}>
                <Link to="/login">{t('back_to_login')}</Link>
              </div>
            </div>
          ) : (
            <form onSubmit={onSubmit}>
              <label style={{ display: 'block', fontSize: 13, marginBottom: 6 }}>{t('reset_identifier_label')}</label>
              <input
                data-e2e="reset-identifier"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                style={{ width: '100%', padding: 10, border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 12 }}
                autoComplete="username"
                placeholder="seu-slug | email"
              />

              <label style={{ display: 'block', fontSize: 13, marginBottom: 6 }}>{t('reset_code_label')}</label>
              <input
                data-e2e="reset-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                style={{ width: '100%', padding: 10, border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 12 }}
                inputMode="numeric"
                placeholder="000000"
              />

              <label style={{ display: 'block', fontSize: 13, marginBottom: 6 }}>{t('reset_new_password')}</label>
              <input
                data-e2e="reset-new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                style={{ width: '100%', padding: 10, border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 12 }}
                autoComplete="new-password"
                placeholder="••••••••"
              />

              <label style={{ display: 'block', fontSize: 13, marginBottom: 6 }}>{t('reset_confirm_password')}</label>
              <input
                data-e2e="reset-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                style={{ width: '100%', padding: 10, border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 12 }}
                autoComplete="new-password"
                placeholder="••••••••"
              />

              {error ? (
                <div data-e2e="reset-error" style={{ marginBottom: 12, color: '#b91c1c', fontSize: 13 }}>{error}</div>
              ) : null}

              <button
                data-e2e="reset-submit"
                type="submit"
                disabled={loading || !identifier || !code || !newPassword || !confirmPassword}
                className="action-btn"
                style={{ width: '100%', justifyContent: 'center' }}
              >
                {loading ? t('loading') : t('reset_cta')}
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
