import React, { useEffect, useMemo, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import AdminConfig from './pages/AdminConfig';
import SetupWizard from './pages/SetupWizard';
import Clients from './pages/Clients';
import Finance from './pages/Finance';
import PendingActions from './pages/PendingActions';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import BookingPremium from './pages/BookingPremium';
import NotificationsOps from './pages/NotificationsOps';
import ClientsDirectory from './pages/ClientsDirectory';
import DemoDashboardCopilot from './pages/DemoDashboardCopilot';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';
import './components/dashboard/dashboard.css';
import { LanguageProvider } from './i18n';
import { getStoredToken } from './utils/auth';

function useViteEnv() {
	return useMemo(() => {
		try {
			// eslint-disable-next-line no-undef
			return (import.meta && import.meta.env) ? import.meta.env : {};
		} catch (_) {
			return (typeof process !== 'undefined' && process.env) ? process.env : {};
		}
	}, []);
}

function AutoAdminLoginGate({ children }) {
	const env = useViteEnv();
	const [ready, setReady] = useState(false);
	const [error, setError] = useState(null);

	useEffect(() => {
		let cancelled = false;
		const isProdBuild = !!(env && (env.PROD === true || String(env.MODE || '').toLowerCase() === 'production'));
		const isAutomation = (typeof navigator !== 'undefined' && navigator.webdriver) ||
			(env && (env.VITE_E2E === 'true' || env.REACT_APP_E2E === 'true')) ||
			(typeof window !== 'undefined' && window.__E2E__ === true);

		const auto = String(env.VITE_AUTO_DEV_LOGIN || '').toLowerCase();
		const enabled = (auto === '1' || auto === 'true' || auto === 'yes');
		// Never auto-login in production builds.
		if (isProdBuild) {
			setReady(true);
			return () => { cancelled = true };
		}
		if (!enabled || isAutomation) {
			setReady(true);
			return () => { cancelled = true };
		}

		let existingToken = null;
		try {
			existingToken = localStorage.getItem('DEV_JWT_TOKEN') || localStorage.getItem('ea_dev_token') || localStorage.getItem('token');
		} catch (_) {}

		if (existingToken) {
			try { window.__DEV_TOKEN__ = existingToken } catch (_) {}
			setReady(true);
			return () => { cancelled = true };
		}

		const apiBase = (typeof window !== 'undefined' && window.__API_URL__) ? window.__API_URL__ : 'http://127.0.0.1:8000';
		const slug = String(env.VITE_DEV_SLUG || env.REACT_APP_DEV_SLUG || 'dev');
		const url = apiBase.replace(/\/$/, '') + '/auth/dev-login?slug=' + encodeURIComponent(slug);

		;(async () => {
			try {
				const res = await fetch(url, { method: 'POST', credentials: 'include' });
				if (!res.ok) throw new Error('HTTP ' + res.status);
				const body = await res.json();
				const tok = body && body.token ? String(body.token) : '';
				if (!tok) throw new Error('Missing token');

				if (cancelled) return;
				try {
					localStorage.setItem('DEV_JWT_TOKEN', tok);
					localStorage.setItem('ea_dev_token', tok);
					localStorage.setItem('token', tok);
				} catch (_) {}
				try { window.__DEV_TOKEN__ = tok } catch (_) {}
				setReady(true);
			} catch (e) {
				if (cancelled) return;
				setError('Auto-login falhou. Cole um token em /config/avancado.');
				setReady(true);
			}
		})();

		return () => { cancelled = true };
	}, [env]);

	if (!ready) {
		return (
			<div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
				Entrando…
			</div>
		);
	}

	return (
		<>
			{error ? (
				<div style={{ padding: '8px 12px', background: '#fff7ed', borderBottom: '1px solid #fed7aa', color: '#9a3412', fontSize: 13 }}>
					{error}
				</div>
			) : null}
			{children}
		</>
	);
}

function RequireAuth({ children }) {
	const location = useLocation();
	let token = '';
	try { token = getStoredToken(); } catch (_) { token = ''; }
	if (!token) {
		const nextPath = location && (location.pathname + (location.search || ''));
		return <Navigate to="/login" replace state={{ nextPath }} />;
	}
	return children;
}

function App(){
	return (
		<LanguageProvider storageKey="ea_lang_admin">
			<AutoAdminLoginGate>
				<BrowserRouter>
					<Routes>
						{/* Demos (no auth) */}
						<Route path="/demo/dashboard-copilot" element={<ErrorBoundary><DemoDashboardCopilot/></ErrorBoundary>} />

						{/* Public booking (no auth) */}
						<Route path="/booking/:slug" element={<ErrorBoundary><BookingPremium/></ErrorBoundary>} />
						<Route path="/booking" element={<ErrorBoundary><BookingPremium/></ErrorBoundary>} />

						<Route path="/login" element={<Login/>} />
						<Route path="/forgot-password" element={<ForgotPassword/>} />
						<Route path="/reset-password" element={<ResetPassword/>} />

						<Route path="/dashboard" element={<RequireAuth><Dashboard/></RequireAuth>} />
						<Route path="/" element={<RequireAuth><Navigate to="/dashboard" replace /></RequireAuth>} />

						{/* Config (setup) */}
						<Route path="/config" element={<RequireAuth><SetupWizard/></RequireAuth>} />
						<Route path="/config/avancado" element={<RequireAuth><AdminConfig/></RequireAuth>} />
						<Route path="/admin/config" element={<Navigate to="/config" replace />} />

						{/* Operations */}
						<Route path="/pendencias" element={<RequireAuth><PendingActions/></RequireAuth>} />
						<Route path="/notificacoes" element={<RequireAuth><NotificationsOps/></RequireAuth>} />

						{/* Analytics */}
						<Route path="/clientes" element={<RequireAuth><Navigate to="/clientes/lista" replace /></RequireAuth>} />
						<Route path="/clientes/lista" element={<RequireAuth><ErrorBoundary><ClientsDirectory/></ErrorBoundary></RequireAuth>} />
						<Route path="/clientes/relatorios" element={<RequireAuth><Clients/></RequireAuth>} />
						<Route path="/financas" element={<RequireAuth><Finance/></RequireAuth>} />
					</Routes>
				</BrowserRouter>
			</AutoAdminLoginGate>
		</LanguageProvider>
	);
}

export default App;
