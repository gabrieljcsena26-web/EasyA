function iso(d) {
  return new Date(d).toISOString()
}

export function demoConfig() {
  return {
    business: { nome: 'Studio Premium' },
    professionals: [
      { id: 1, name: 'Ana' },
      { id: 2, name: 'Julia' },
      { id: 3, name: 'Marcos' },
    ],
  }
}

export function demoClientes() {
  return [
    { id: 101, nome: 'Carla Mendes', telefone: '+55 11 98888-1111', observacoes: 'Prefere manhã • Sensível a atrasos', idioma: 'pt-BR', tipo_servico: 'Corte' },
    { id: 102, nome: 'Fernanda Costa', telefone: '+55 11 97777-2222', observacoes: 'Cliente VIP', idioma: 'pt-BR', tipo_servico: 'Escova' },
    { id: 103, nome: 'João Silva', telefone: '+55 11 96666-3333', observacoes: 'Barba + corte', idioma: 'pt-BR', tipo_servico: 'Barba' },
    { id: 104, nome: 'Maria Oliveira', telefone: '+55 11 95555-4444', observacoes: '', idioma: 'pt-BR', tipo_servico: 'Manicure' },
    { id: 105, nome: 'Rafaela Dias', telefone: '+55 11 94444-5555', observacoes: 'Alérgica a alguns produtos', idioma: 'pt-BR', tipo_servico: 'Coloração' },
  ]
}

export function demoAgendamentos() {
  const now = new Date()
  const d1 = new Date(now); d1.setDate(now.getDate() - 10); d1.setHours(10, 0, 0, 0)
  const d2 = new Date(now); d2.setDate(now.getDate() - 2); d2.setHours(15, 30, 0, 0)
  const d3 = new Date(now); d3.setDate(now.getDate() + 1); d3.setHours(9, 0, 0, 0)
  const d4 = new Date(now); d4.setDate(now.getDate() + 6); d4.setHours(14, 0, 0, 0)

  return [
    { id: 5001, cliente_id: 101, funcionario_id: 1, data_hora: iso(d1), descricao: 'Corte', status: 'confirmado' },
    { id: 5002, cliente_id: 102, funcionario_id: 2, data_hora: iso(d2), descricao: 'Escova', status: 'confirmado' },
    { id: 5003, cliente_id: 101, funcionario_id: 3, data_hora: iso(d3), descricao: 'Corte + finalização', status: 'pendente' },
    { id: 5004, cliente_id: 104, funcionario_id: 2, data_hora: iso(d4), descricao: 'Manicure', status: 'confirmado' },
    { id: 5005, cliente_id: 103, funcionario_id: 3, data_hora: iso(new Date(now.getFullYear(), now.getMonth(), now.getDate(), 18, 0, 0)), descricao: 'Barba', status: 'confirmado' },
  ]
}

export function demoInvoices() {
  const now = new Date()
  const mk = (deltaDays, cents, status, desc, clientId) => {
    const d = new Date(now)
    d.setDate(now.getDate() + deltaDays)
    d.setHours(12, 0, 0, 0)
    return {
      id: `INV-${Math.abs(deltaDays)}-${clientId}`,
      cliente_id: clientId,
      descricao: desc,
      status,
      valor_centavos: cents,
      currency: 'BRL',
      created_at: iso(d),
    }
  }

  return [
    mk(-16, 12000, 'pago', 'Corte + escova', 101),
    mk(-12, 9000, 'pago', 'Manicure', 104),
    mk(-9, 18000, 'pago', 'Coloração', 105),
    mk(-7, 6000, 'cancelado', 'Barba', 103),
    mk(-6, 15000, 'pago', 'Corte premium', 102),
    mk(-3, 12000, 'pago', 'Corte', 101),
    mk(-2, 9000, 'emitido', 'Escova', 102),
    mk(-1, 8000, 'pago', 'Manicure', 104),
    mk(0, 14000, 'emitido', 'Corte + barba', 103),
  ]
}

export function demoTwilioStatus() {
  return {
    ok: true,
    mock: true,
    provider: 'twilio',
    sms: { enabled: true, from: '+1 (555) 000-0000' },
    whatsapp: { enabled: true, from: 'whatsapp:+1 (555) 000-0000' },
    last_check_at: iso(new Date()),
  }
}

export function demoNotificationsSummary() {
  return {
    ok: true,
    mock: true,
    queued: 3,
    sending: 1,
    sent_last_24h: 18,
    failed_last_24h: 1,
    last_error: 'E164_INVALID (exemplo)',
    updated_at: iso(new Date()),
  }
}

export function demoNotificationsDashboard() {
  const now = new Date()
  const addMin = (m) => {
    const d = new Date(now)
    d.setMinutes(d.getMinutes() + m)
    return d
  }
  const mk = (id, patch) => ({
    id,
    tipo: patch.tipo || 'lembrete',
    agendamento_id: patch.agendamento_id ?? 5003,
    agendamento_status: patch.agendamento_status || 'pendente',
    agendamento_data_hora: patch.agendamento_data_hora || iso(addMin(90)),
    cliente_nome: patch.cliente_nome || 'Carla Mendes',
    canal: patch.canal || 'whatsapp',
    status: patch.status || 'queued',
    provider_status: patch.provider_status || null,
    destinatario: patch.destinatario || '+55 11 ****1111',
    created_at: patch.created_at || iso(addMin(-40)),
    next_attempt_at: patch.next_attempt_at || iso(addMin(12)),
    next_in_minutes: patch.next_in_minutes ?? 12,
    attempts: patch.attempts ?? 1,
    max_attempts: patch.max_attempts ?? 5,
    last_error: patch.last_error || null,
  })

  const upcoming = [
    mk(9001, { tipo: 'confirmacao', next_in_minutes: 8, next_attempt_at: iso(addMin(8)), cliente_nome: 'João Silva', agendamento_id: 5005, agendamento_status: 'pendente', canal: 'whatsapp', status: 'queued' }),
    mk(9002, { tipo: 'lembrete', next_in_minutes: 12, next_attempt_at: iso(addMin(12)), cliente_nome: 'Carla Mendes', agendamento_id: 5003, agendamento_status: 'pendente', canal: 'sms', status: 'queued' }),
    mk(9003, { tipo: 'lembrete', next_in_minutes: 0, next_attempt_at: iso(addMin(0)), cliente_nome: 'Maria Oliveira', agendamento_id: 5004, agendamento_status: 'confirmado', canal: 'whatsapp', status: 'failed', attempts: 2, last_error: 'E164_INVALID (exemplo)' }),
  ]

  const recent = [
    mk(9050, { tipo: 'confirmacao', status: 'delivered', canal: 'whatsapp', cliente_nome: 'Fernanda Costa', agendamento_id: 5002, agendamento_status: 'confirmado', next_attempt_at: null, next_in_minutes: null, created_at: iso(addMin(-75)) }),
    mk(9051, { tipo: 'lembrete', status: 'sent', canal: 'sms', cliente_nome: 'Rafaela Dias', agendamento_id: 5001, agendamento_status: 'confirmado', next_attempt_at: null, next_in_minutes: null, created_at: iso(addMin(-55)) }),
  ]

  return {
    ok: true,
    mock: true,
    now: iso(now),
    provider: { twilio_configured: true, smtp_configured: false },
    counts: { queued: 2, failed: 1, sent: 1, delivered: 1 },
    next_in_minutes: 8,
    upcoming,
    recent,
  }
}
