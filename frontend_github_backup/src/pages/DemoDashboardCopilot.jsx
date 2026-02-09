import React, { useMemo, useState } from 'react';

function box() {
	return {
		minHeight: 'calc(100vh - 48px)',
		background: 'linear-gradient(180deg, #0b1220 0%, #111827 40%, #0b1220 100%)',
		padding: 16,
		fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
	};
}

function panel() {
	return {
		maxWidth: 1080,
		margin: '0 auto',
		background: '#0f172a',
		border: '1px solid rgba(255,255,255,0.08)',
		borderRadius: 16,
		overflow: 'hidden',
	};
}

function btn(kind = 'secondary') {
	const base = {
		padding: '10px 12px',
		borderRadius: 12,
		border: '1px solid rgba(255,255,255,0.12)',
		fontWeight: 800,
		cursor: 'pointer',
	};
	if (kind === 'primary') return { ...base, background: '#2563eb', color: '#fff' };
	if (kind === 'success') return { ...base, background: '#10b981', color: '#052e2b' };
	return { ...base, background: 'rgba(255,255,255,0.04)', color: '#e2e8f0' };
}

function formatDate(d) {
	try {
		return new Date(d).toLocaleString([], { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
	} catch (_) {
		return String(d);
	}
}

function waUrl(phoneE164, text) {
	return `https://wa.me/${phoneE164}?text=${encodeURIComponent(text)}`;
}

function template(type, appt, business) {
	const base = {
		confirm: `Olá${appt.clientName ? ' ' + appt.clientName : ''}! ✅\n\nSeu horário para *${appt.serviceName}* está confirmado: *${formatDate(appt.startsAt)}*.\n\nLocal: ${business.addressShort}\nSe precisar reagendar, me avise por aqui.`,
		remind: `Oi${appt.clientName ? ' ' + appt.clientName : ''}! Só passando para lembrar do seu horário *${formatDate(appt.startsAt)}* para *${appt.serviceName}*.\n\nSe precisar reagendar, responda aqui. Até já!`,
		reschedule: `Olá${appt.clientName ? ' ' + appt.clientName : ''}! Sem problemas em reagendar.\n\nTenho estas opções (demo):\n1) Amanhã 10:30\n2) Amanhã 15:30\n3) Qua 11:00\n\nQual você prefere?`,
		review: `Oi${appt.clientName ? ' ' + appt.clientName : ''}! 🙂\nGostou do atendimento de hoje?\nSe puder, deixa uma avaliação rapidinha — ajuda muito o ${business.name}:\n${business.reviewLink}\n\nObrigado!`,
	};
	return base[type] || base.confirm;
}

async function copyToClipboard(text) {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch (_) {
		return false;
	}
}

export default function DemoDashboardCopilot() {
	const business = useMemo(() => ({
		name: 'EasyAgenda Demo',
		addressShort: 'Rua Example, 123 — Centro',
		reviewLink: 'https://example.com/review',
		whatsappE164: '34600000000',
	}), []);

	const appt = useMemo(() => ({
		id: 123,
		clientName: 'Ana',
		serviceName: 'Corte + Barba',
		startsAt: new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString(),
		status: 'pending_confirmation',
	}), []);

	const [mode, setMode] = useState('confirm');
	const [text, setText] = useState(() => template('confirm', appt, business));
	const [copied, setCopied] = useState(false);

	function generate(nextMode) {
		setCopied(false);
		setMode(nextMode);
		setText(template(nextMode, appt, business));
	}

	async function doCopy() {
		const ok = await copyToClipboard(text);
		setCopied(ok);
		if (!ok) {
			alert('Não consegui copiar automaticamente. Selecione o texto e copie manualmente.');
		}
	}

	function openWA() {
		window.open(waUrl(business.whatsappE164, text), '_blank', 'noreferrer');
	}

	return (
		<div style={box()}>
			<div style={{ color: '#cbd5e1', maxWidth: 1080, margin: '0 auto 10px auto', fontSize: 13 }}>
				Demo ao vivo — Copilot no Dashboard (simulado, sem backend)
			</div>

			<div style={panel()}>
				<div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)' }}>
					<div>
						<div style={{ color: '#fff', fontWeight: 900 }}>Copilot Operacional</div>
						<div style={{ color: '#94a3b8', fontSize: 13 }}>Mensagem pronta + atalhos para WhatsApp</div>
					</div>
					<div style={{ display: 'flex', gap: 8 }}>
						<button style={btn()} onClick={() => generate('confirm')}>Confirmar</button>
						<button style={btn()} onClick={() => generate('remind')}>Lembrete</button>
						<button style={btn()} onClick={() => generate('reschedule')}>Reagendar</button>
						<button style={btn()} onClick={() => generate('review')}>Review</button>
					</div>
				</div>

				<div style={{ display: 'grid', gridTemplateColumns: '0.9fr 1.1fr', gap: 12, padding: 14 }}>
					<div style={{ background: '#0b1220', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: 12, color: '#e5e7eb' }}>
						<div style={{ fontWeight: 900, marginBottom: 8 }}>Agendamento</div>
						<div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>Contexto usado pela AI (sem “chute”)</div>
						<div style={{ display: 'grid', gap: 8, fontSize: 14 }}>
							<div><span style={{ color: '#94a3b8' }}>Cliente:</span> {appt.clientName}</div>
							<div><span style={{ color: '#94a3b8' }}>Serviço:</span> {appt.serviceName}</div>
							<div><span style={{ color: '#94a3b8' }}>Quando:</span> {formatDate(appt.startsAt)}</div>
							<div><span style={{ color: '#94a3b8' }}>Status:</span> {appt.status}</div>
							<div><span style={{ color: '#94a3b8' }}>Modo:</span> {mode}</div>
						</div>

						<div style={{ marginTop: 12, padding: 10, borderRadius: 12, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)', color: '#cbd5e1', fontSize: 12 }}>
							Aqui o “bot” é seguro: ele só prepara texto e você envia.
							Depois, se quiser automação total, entramos com WhatsApp Cloud API.
						</div>
					</div>

					<div style={{ background: '#0b1220', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: 12 }}>
						<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
							<div style={{ color: '#fff', fontWeight: 900 }}>Mensagem sugerida</div>
							{copied ? <div style={{ color: '#34d399', fontSize: 12, fontWeight: 800 }}>Copiado</div> : null}
						</div>
						<textarea
							value={text}
							onChange={(e) => { setCopied(false); setText(e.target.value); }}
							rows={10}
							style={{
								width: '100%',
								padding: 12,
								borderRadius: 12,
								border: '1px solid rgba(255,255,255,0.10)',
								background: 'rgba(255,255,255,0.02)',
								color: '#e5e7eb',
								resize: 'vertical',
							}}
						/>

						<div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
							<button style={btn('primary')} onClick={doCopy}>Copiar</button>
							<button style={btn('success')} onClick={openWA}>Abrir WhatsApp</button>
							<button
								style={btn()}
								onClick={() => alert('Demo: aqui salvaria “mensagem enviada” no histórico e mudaria o status do agendamento.')}
							>
								Marcar como enviado
							</button>
						</div>

						<div style={{ color: '#94a3b8', fontSize: 12, marginTop: 10 }}>
							Depois a gente liga isso ao backend para puxar dados reais e registrar histórico.
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
