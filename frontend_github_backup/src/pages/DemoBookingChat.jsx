import React, { useEffect, useMemo, useRef, useState } from 'react';

function nowTime() {
	try {
		return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	} catch (_) {
		return '';
	}
}

function getApiBase() {
	try {
		if (typeof window !== 'undefined' && window.__API_URL__) return String(window.__API_URL__);
	} catch (_) {}
	return 'http://127.0.0.1:8000';
}

function getInitials(name) {
	const clean = String(name || '').trim();
	if (!clean) return 'EA';
	const parts = clean.split(/\s+/).filter(Boolean);
	const a = parts[0] ? parts[0][0] : '';
	const b = parts.length > 1 ? parts[parts.length - 1][0] : '';
	return (String(a) + String(b)).toUpperCase();
}

function normalizePhotoList(photos) {
	if (Array.isArray(photos)) return photos.map((s) => String(s || '').trim()).filter(Boolean);
	const raw = String(photos || '');
	return raw
		.split(/\r?\n/)
		.map((s) => String(s || '').trim())
		.filter(Boolean);
}

const FALLBACK_BOOKING_CONFIG = {
	services: [
		{ id: 1, name: 'Corte', duration_min: 30, price_cents: 1500 },
		{ id: 2, name: 'Barba', duration_min: 20, price_cents: 1000 },
		{ id: 3, name: 'Corte + barba', duration_min: 50, price_cents: 2200 },
	],
	professionals: [
		{ id: 2, name: 'Ana' },
		{ id: 3, name: 'Júlia' },
		{ id: 4, name: 'Pedro' },
	],
	business: {
		id: 0,
		nome: 'EasyAgenda Demo',
		telefone: '+34 600 000 000',
		slug: 'demo',
		photos: [],
	},
};

function ensureMinimumBookingConfig(raw) {
	const cfg = (raw && typeof raw === 'object') ? raw : {};
	const servicesIn = Array.isArray(cfg.services) ? cfg.services : [];
	const prosIn = Array.isArray(cfg.professionals) ? cfg.professionals : [];

	const mergeById = (primary, fallback, minCount) => {
		const out = [];
		const seen = new Set();
		(primary || []).forEach((it) => {
			const id = String(it?.id ?? '').trim();
			out.push(it);
			if (id) seen.add(id);
		});
		(fallback || []).forEach((it) => {
			if (out.length >= minCount) return;
			const id = String(it?.id ?? '').trim();
			if (id && seen.has(id)) return;
			out.push(it);
			if (id) seen.add(id);
		});
		return out;
	};

	const services = mergeById(servicesIn, FALLBACK_BOOKING_CONFIG.services, 3);
	const professionals = mergeById(prosIn, FALLBACK_BOOKING_CONFIG.professionals, 3);

	return {
		...FALLBACK_BOOKING_CONFIG,
		...cfg,
		services,
		professionals,
		business: (cfg.business && typeof cfg.business === 'object')
			? { ...FALLBACK_BOOKING_CONFIG.business, ...cfg.business }
			: FALLBACK_BOOKING_CONFIG.business,
	};
}

function chipStyle(active) {
	return {
		padding: '8px 10px',
		borderRadius: 999,
		border: '1px solid ' + (active ? '#2563eb' : '#e5e7eb'),
		background: active ? '#eff6ff' : '#ffffff',
		color: '#111827',
		fontSize: 13,
		cursor: 'pointer',
	};
}

function bubble(isUser) {
	return {
		maxWidth: '78%',
		padding: '10px 12px',
		borderRadius: 14,
		whiteSpace: 'pre-wrap',
		background: isUser ? '#2563eb' : '#f3f4f6',
		color: isUser ? '#ffffff' : '#111827',
		alignSelf: isUser ? 'flex-end' : 'flex-start',
	};
}

function wrap() {
	return {
		minHeight: 'calc(100vh - 48px)',
		background: 'linear-gradient(180deg, #0b1220 0%, #111827 40%, #0b1220 100%)',
		padding: 16,
		fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
	};
}

function card() {
	return {
		maxWidth: 980,
		margin: '0 auto',
		background: '#0f172a',
		border: '1px solid rgba(255,255,255,0.08)',
		borderRadius: 16,
		overflow: 'hidden',
	};
}

function header() {
	return {
		padding: '14px 16px',
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'space-between',
		background: 'rgba(255,255,255,0.03)',
		borderBottom: '1px solid rgba(255,255,255,0.08)',
	};
}

function parseIntent(text) {
	const t = String(text || '').toLowerCase();
	if (/(endere|morada|address)/.test(t)) return 'address';
	if (/(pre[cç]o|quanto|custa|valor)/.test(t)) return 'price';
	if (/(hor[aá]rio|agenda|dispon[ií]vel|hoje|amanh[aã])/.test(t)) return 'slots';
	if (/(cancel|remarcar|reagendar)/.test(t)) return 'policy';
	if (/(servi[cç]o|fazem|oferecem|barba|corte|tintura)/.test(t)) return 'services';
	return 'generic';
}

function botReply(intent, context) {
	const businessName = context.businessName;
	if (intent === 'address') {
		return `Endereço do ${businessName}:\nRua Example, 123 — Centro\n\nQuer que eu te mande o link do mapa?`;
	}
	if (intent === 'price') {
		return `Valores (exemplo):\n- Corte: €15\n- Barba: €10\n- Corte + Barba: €22\n\nQuer agendar qual serviço?`;
	}
	if (intent === 'services') {
		return `Serviços (exemplo):\n- Corte\n- Barba\n- Corte + barba\n- Coloração\n\nMe diga qual serviço você quer e eu te mostro os próximos horários.`;
	}
	if (intent === 'policy') {
		return `Política (exemplo):\n- Cancelamento até 2h antes\n- Atraso acima de 10 min pode perder a vaga\n\nQuer que eu te ajude a escolher um horário?`;
	}
	if (intent === 'slots') {
		return `Próximos horários (demo):\n- Hoje 16:30\n- Hoje 17:00\n- Amanhã 10:30\n\nQual você prefere? Você pode clicar em uma opção abaixo.`;
	}
	return `Posso te ajudar com: horários, preços, endereço e regras.\n\nO que você quer saber?`;
}

function makeInitialMessages(context) {
	return [
		{
			id: 'm1',
			from: 'bot',
			time: nowTime(),
			text: `Olá! Eu sou o assistente do ${context.businessName}.\n\nObrigado por nos escolher. Quer conhecer a equipe (à direita) ou já ver horários?`,
		},
	];
}

export default function DemoBookingChat() {
	const apiBase = useMemo(() => getApiBase().replace(/\/$/, ''), []);
	const slug = useMemo(() => {
		try {
			const sp = new URLSearchParams(window.location.search);
			return String(sp.get('slug') || '').trim() || 'demo';
		} catch (_) {
			return 'demo';
		}
	}, []);

	const [cfg, setCfg] = useState(() => ensureMinimumBookingConfig(null));
	const [cfgLoaded, setCfgLoaded] = useState(false);

	useEffect(() => {
		let cancelled = false;
		setCfgLoaded(false);
		const url = new URL(apiBase + '/config');
		if (slug) url.searchParams.set('slug', slug);

		(async () => {
			try {
				const res = await fetch(url.toString(), { method: 'GET' });
				if (!res.ok) throw new Error('HTTP ' + res.status);
				const json = ensureMinimumBookingConfig(await res.json());
				if (cancelled) return;
				setCfg(json);
				setCfgLoaded(true);
			} catch (_) {
				if (cancelled) return;
				setCfg(ensureMinimumBookingConfig(null));
				setCfgLoaded(true);
			}
		})();

		return () => {
			cancelled = true;
		};
	}, [apiBase, slug]);

	const businessName = (cfg && cfg.business && (cfg.business.nome || cfg.business.name))
		? String(cfg.business.nome || cfg.business.name)
		: 'EasyAgenda Demo';
	const businessPhone = (cfg && cfg.business && (cfg.business.telefone || cfg.business.phone))
		? String(cfg.business.telefone || cfg.business.phone)
		: '+34 600 000 000';
	const heroUrl = (() => {
		const ph = (cfg && cfg.business) ? normalizePhotoList(cfg.business.photos) : [];
		return (ph && ph.length) ? String(ph[0]) : '';
	})();

	const context = useMemo(() => ({
		businessName,
		phoneE164: String(businessPhone || '').replace(/\D/g, '') || '34600000000',
	}), [businessName, businessPhone]);

	const [messages, setMessages] = useState(() => makeInitialMessages(context));
	const [draft, setDraft] = useState('');
	const listRef = useRef(null);

	useEffect(() => {
		setMessages(makeInitialMessages(context));
		setDraft('');
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [context.businessName]);

	function scrollToBottom() {
		try {
			const el = listRef.current;
			if (!el) return;
			el.scrollTop = el.scrollHeight;
		} catch (_) {}
	}

	function pushUser(text) {
		const msg = { id: 'u_' + Date.now(), from: 'user', time: nowTime(), text };
		setMessages((prev) => [...prev, msg]);
		setTimeout(scrollToBottom, 0);
	}

	function pushBot(text) {
		const msg = { id: 'b_' + Date.now(), from: 'bot', time: nowTime(), text };
		setMessages((prev) => [...prev, msg]);
		setTimeout(scrollToBottom, 0);
	}

	function send(text) {
		const clean = String(text || '').trim();
		if (!clean) return;
		pushUser(clean);
		setDraft('');

		const intent = parseIntent(clean);
		const reply = botReply(intent, context);
		setTimeout(() => pushBot(reply), 200);
	}

	function openWhatsAppPrefilled(text) {
		const base = `https://wa.me/${context.phoneE164}?text=`;
		const url = base + encodeURIComponent(text);
		window.open(url, '_blank', 'noreferrer');
	}

	const quick = [
		{ label: 'Ver horários', text: 'Quais horários tem hoje?' },
		{ label: 'Preços', text: 'Quanto custa corte + barba?' },
		{ label: 'Endereço', text: 'Qual é o endereço?' },
		{ label: 'Regras', text: 'Como funciona cancelamento?' },
	];

	const slotChoices = [
		{ label: 'Hoje 16:30', text: 'Quero Hoje 16:30' },
		{ label: 'Hoje 17:00', text: 'Quero Hoje 17:00' },
		{ label: 'Amanhã 10:30', text: 'Quero Amanhã 10:30' },
	];

	return (
		<div style={wrap()}>
			<div style={{ color: '#cbd5e1', maxWidth: 980, margin: '0 auto 10px auto', fontSize: 13 }}>
				Demo ao vivo — Chat do Booking ({cfgLoaded ? 'com config' : 'carregando config…'}) — Dica: use `?slug=SEU_SLUG`
			</div>

			<div style={card()}>
				<div style={header()}>
					<div>
						<div style={{ color: '#fff', fontWeight: 700 }}>Chat do Booking</div>
						<div style={{ color: '#94a3b8', fontSize: 13 }}>Auto-ajuda + conversão em agendamento</div>
					</div>
					<button
						onClick={() => {
							setMessages(makeInitialMessages(context));
							setDraft('');
						}}
						style={{
							padding: '8px 10px',
							borderRadius: 10,
							border: '1px solid rgba(255,255,255,0.12)',
							background: 'rgba(255,255,255,0.04)',
							color: '#e2e8f0',
							cursor: 'pointer',
						}}
					>
						Reiniciar
					</button>
				</div>

				<div style={{ padding: 14, display: 'grid', gridTemplateColumns: '1.3fr 0.7fr', gap: 12 }}>
					<div style={{
						background: '#0b1220',
						border: '1px solid rgba(255,255,255,0.08)',
						borderRadius: 14,
						display: 'flex',
						flexDirection: 'column',
						height: '68vh',
					}}>
						<div style={{
							padding: 12,
							display: 'flex',
							gap: 10,
							alignItems: 'center',
							borderBottom: '1px solid rgba(255,255,255,0.08)',
						}}>
							<div style={{
								width: 36,
								height: 36,
								borderRadius: 12,
								overflow: 'hidden',
								background: 'rgba(255,255,255,0.06)',
								display: 'grid',
								placeItems: 'center',
								color: '#e2e8f0',
								fontWeight: 900,
							}}>
								{heroUrl ? (
									<img src={heroUrl} alt={businessName} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
								) : (
									<span>{getInitials(businessName)}</span>
								)}
							</div>
							<div style={{ minWidth: 0 }}>
								<div style={{ color: '#fff', fontWeight: 850, lineHeight: 1.1 }}>
									{businessName}
								</div>
								<div style={{ color: '#94a3b8', fontSize: 12 }}>
									Eu sou seu assistente. Conheça a equipe à direita.
								</div>
							</div>
						</div>

						<div ref={listRef} style={{ padding: 12, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
							{messages.map((m) => (
								<div key={m.id} style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: m.from === 'user' ? 'flex-end' : 'flex-start' }}>
									<div style={bubble(m.from === 'user')}>{m.text}</div>
									<div style={{ fontSize: 11, color: '#64748b' }}>{m.time}</div>
								</div>
							))}
						</div>

						<div style={{ padding: 10, borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: 8 }}>
							<input
								value={draft}
								onChange={(e) => setDraft(e.target.value)}
								onKeyDown={(e) => {
									if (e.key === 'Enter') send(draft);
								}}
								placeholder="Digite uma pergunta (ex: 'quais horários tem hoje?')"
								style={{
									flex: 1,
									padding: '10px 12px',
									borderRadius: 12,
									border: '1px solid rgba(255,255,255,0.10)',
									background: 'rgba(255,255,255,0.02)',
									color: '#e5e7eb',
								}}
							/>
							<button
								onClick={() => send(draft)}
								style={{
									padding: '10px 12px',
									borderRadius: 12,
									border: '1px solid rgba(255,255,255,0.12)',
									background: '#2563eb',
									color: '#fff',
									fontWeight: 700,
									cursor: 'pointer',
								}}
							>
								Enviar
							</button>
						</div>
					</div>

					<div style={{
						background: '#0b1220',
						border: '1px solid rgba(255,255,255,0.08)',
						borderRadius: 14,
						padding: 12,
						color: '#e5e7eb',
					}}>
						<div style={{
							border: '1px solid rgba(255,255,255,0.08)',
							borderRadius: 12,
							padding: 10,
							marginBottom: 12,
							background: 'rgba(255,255,255,0.03)',
						}}>
							<div style={{ fontWeight: 850, marginBottom: 6 }}>Equipe</div>
							<div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 8 }}>
								Clique para perguntar “tem horário com…”.
							</div>
							<div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
								{(cfg && Array.isArray(cfg.professionals) ? cfg.professionals : []).slice(0, 10).map((p) => {
									const name = String(p?.name || p?.nome || '').trim() || 'Profissional';
									return (
										<button
											key={String(p?.id ?? name)}
											onClick={() => send('Tem horário com ' + name + '?')}
											style={{
												padding: '8px 10px',
												borderRadius: 999,
												border: '1px solid rgba(255,255,255,0.14)',
												background: 'rgba(255,255,255,0.05)',
												color: '#e2e8f0',
												cursor: 'pointer',
												fontSize: 13,
											}}
									>
										{name}
									</button>
									);
								})}
							</div>
						</div>

						<div style={{ fontWeight: 800, marginBottom: 8 }}>Atalhos (conversão)</div>
						<div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>
							O chat não “enrola”. Ele te leva para ação.
						</div>

						<div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
							{quick.map((q) => (
								<button key={q.label} onClick={() => send(q.text)} style={chipStyle(false)}>
									{q.label}
								</button>
							))}
						</div>

						<div style={{ fontWeight: 800, marginBottom: 8 }}>Escolher horário (demo)</div>
						<div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
							{slotChoices.map((s) => (
								<button key={s.label} onClick={() => send(s.text)} style={chipStyle(false)}>
									{s.label}
								</button>
							))}
						</div>

						<div style={{ fontWeight: 800, marginBottom: 8 }}>Falar no WhatsApp</div>
						<button
							onClick={() => openWhatsAppPrefilled('Olá! Quero agendar um horário. Pode me ajudar?')}
							style={{
								width: '100%',
								padding: '10px 12px',
								borderRadius: 12,
								border: '1px solid rgba(255,255,255,0.12)',
								background: '#10b981',
								color: '#052e2b',
								fontWeight: 900,
								cursor: 'pointer',
							}}
						>
							Abrir WhatsApp com texto
						</button>

						<div style={{ color: '#94a3b8', fontSize: 12, marginTop: 10 }}>
							Esse modelo é o “bot sem API”: a AI prepara, você só envia.
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
