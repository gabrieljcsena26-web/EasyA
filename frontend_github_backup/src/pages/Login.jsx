import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import API from '../utils/api';
import Header from '../components/dashboard/Header';
import { setStoredToken, getStoredToken } from '../utils/auth';
import { useI18n } from '../i18n';

export default function Login() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const nextPath = (location.state && location.state.nextPath) ? String(location.state.nextPath) : '/dashboard';

  useEffect(() => {
    const tok = getStoredToken();
    if (tok) {
      navigate(nextPath, { replace: true });
    }
  }, [navigate, nextPath]);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await API.post('/auth/login', { username, password });
      const tok = res && res.token ? String(res.token) : '';
      if (!tok) throw new Error('Missing token');
      setStoredToken(tok);
      navigate(nextPath, { replace: true });
    } catch (err) {
      setError(t('login_error'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dashboard-root">
      <div className="dashboard-main">
        <Header />

        <div className="card-surface" style={{ maxWidth: 520, margin: '18px auto', padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>{t('login_title')}</h3>
          <div style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>{t('login_sub')}</div>

          <form onSubmit={onSubmit}>
            <label style={{ display: 'block', fontSize: 13, marginBottom: 6 }}>{t('login_user')}</label>
            <input
              data-e2e="login-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{ width: '100%', padding: 10, border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 12 }}
              autoComplete="username"
              placeholder="admin | seu-slug | email"
            />

            <label style={{ display: 'block', fontSize: 13, marginBottom: 6 }}>{t('login_password')}</label>
            <input
              data-e2e="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: '100%', padding: 10, border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 12 }}
              autoComplete="current-password"
              placeholder="••••••••"
            />

            {error ? (
              <div data-e2e="login-error" style={{ marginBottom: 12, color: '#b91c1c', fontSize: 13 }}>{error}</div>
            ) : null}

            <button
              data-e2e="login-submit"
              type="submit"
              disabled={loading || !username || !password}
              className="action-btn"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {loading ? t('loading') : t('login_cta')}
            </button>

            <div style={{ marginTop: 10, color: '#6b7280', fontSize: 12 }}>
              {t('login_hint')}
            </div>

            <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
              <Link to="/forgot-password">{t('login_forgot')}</Link>
              <Link to="/reset-password">{t('login_have_code')}</Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
