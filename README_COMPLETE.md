# EasyA Agenda — SaaS de Agendamentos com IA

Sistema completo de agendamentos com notificações SMS/WhatsApp, sincronização em tempo real e assistente IA.

## 🎯 Funcionalidades

### Frontend (React)
- ✅ Dashboard com calendário interativo e mini-calendário com polling configurável
- ✅ Agenda list-first com filtros e visualizações (dia/semana/mês)
- ✅ Tela de Clientes com tabela searchable, export CSV e gráfico pizza com percentuais
- ✅ Página de Equipe
- ✅ **Admin de Notificações** com mascote animado (👋), lista de notificações e modal de detalhes
- ✅ Polling automático (60s-120s) que pausa quando aba inativa (Page Visibility API)

### Backend (FastAPI + SQLAlchemy)
- ✅ Autenticação JWT com tokens temporários de 8h para staff
- ✅ CRUD completo: clientes, agendamentos, notificações
- ✅ **Integração Twilio** para SMS e WhatsApp (confirmações, lembretes, promoções)
- ✅ **Webhook Twilio** para receber delivery receipts e atualizar status automaticamente
- ✅ **Endpoint `/sync/changes`** com suporte a `If-Modified-Since` e 304 (Not Modified)
- ✅ Persistência de histórico completo de notificações (payload, status, erros)
- ✅ Assistente IA (OpenAI) para conversação e criação de agendamentos
- ✅ Suporte a PostgreSQL e SQLite

---

## 📦 Instalação

### Backend

1. **Ativar venv e instalar dependências**
```powershell
cd Backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Ou instalar manualmente:
pip install twilio python-dotenv psycopg2-binary APScheduler fastapi uvicorn sqlalchemy pydantic python-jose[cryptography]
```

2. **Configurar `.env`** (copie `.env.example` ou crie):
```env
# Twilio (SMS/WhatsApp)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_SMS_FROM=+1234567890
TWILIO_WHATSAPP_FROM=whatsapp:+1415XXXXXXX

# Database (use PostgreSQL em prod, SQLite em dev)
DATABASE_URL=postgresql://user:password@localhost:5432/easyaagenda
# Ou deixar vazio para usar SQLite: sqlite:///./test.db

# JWT
SECRET_KEY=your-super-secret-key-change-me
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Frontend URLs (CORS)
FRONTEND_URL=http://localhost:3002
FRONTEND_URLS=http://localhost:3002

# OpenAI (se usar assistente IA)
OPENAI_API_KEY=sk-...
```

3. **Criar tabelas do banco**
```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts\create_tables.py
```

4. **Rodar servidor**
```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Acesse docs em: http://127.0.0.1:8000/docs

---

### Frontend (frontend_v2)

1. **Instalar dependências**
```powershell
cd ..\frontend_v2
npm ci
```

2. **Rodar dev server**
```powershell
npm run dev
```

Acesse em: http://localhost:3002

---

## 🔐 Segurança

### ⚠️ IMPORTANTE — Rotacionar chaves vazadas
Se você commitou o `.env` com a `OPENAI_API_KEY` real:
1. Gere nova chave em https://platform.openai.com/api-keys
2. Revogue a chave antiga imediatamente
3. Adicione `.env` ao `.gitignore`
4. Remova do histórico Git:
```powershell
git filter-branch --index-filter "git rm -rf --cached --ignore-unmatch Backend/.env" HEAD
# Ou use git-filter-repo (mais rápido)
```

### Twilio Webhook Signature Validation
- Em produção, sempre configure `TWILIO_AUTH_TOKEN` no `.env`
- O endpoint `/notifications/webhook/twilio` valida assinaturas automaticamente
- Para testar localmente sem validação, remova temporariamente `TWILIO_AUTH_TOKEN`

---

## 📡 Webhooks e Ngrok (Testes Locais)

Para Twilio enviar delivery receipts ao seu backend local:

1. **Instalar ngrok**
```powershell
# Download: https://ngrok.com/download
# Ou via chocolatey:
choco install ngrok
```

2. **Expor backend local**
```powershell
ngrok http 8000
```

3. **Configurar Twilio Webhook**
- Copie a URL do ngrok (ex: `https://abc123.ngrok.io`)
- No console Twilio, configure:
  - **SMS Status Callback:** `https://abc123.ngrok.io/notifications/webhook/twilio`
  - **WhatsApp Status Callback:** mesma URL

4. **Testar com curl**
```bash
curl -X POST https://abc123.ngrok.io/notifications/webhook/twilio \
  -d "MessageSid=SM1234567890" \
  -d "MessageStatus=delivered" \
  -d "To=+34600000000" \
  -d "From=+1415XXXXXXX"
```

---

## 🎨 Frontend — Estrutura

### Componentes principais
- `src/components/MiniCalendar.jsx` — Calendário com sync on/off e polling
- `src/components/Mascot.jsx` — Mascote com animação de aceno (👋)
- `src/components/NotificationsPanel.jsx` — Lista de notificações + modal de detalhes
- `src/pages/AdminNotifications.jsx` — Página administrativa de notificações
- `src/hooks/useSyncPoll.js` — Hook de polling com backoff e Page Visibility

### Ativar Admin de Notificações
No Dashboard, adicione uma aba/botão que seta `active={4}` ou navegue para `/admin/notifications`.

---

## 🔧 Backend — Endpoints Principais

### Autenticação
- `POST /auth/login` — Login com JWT
- `POST /auth/staff/{staff_id}/temporary-link` — Gera link temporário (8h) para staff

### Agendamentos
- `GET /dashboard/agendamentos` — Lista todos
- `POST /dashboard/agendamentos` — Cria novo
- `PUT /dashboard/agendamentos/{id}` — Atualiza
- `DELETE /dashboard/agendamentos/{id}` — Remove

### Notificações
- `GET /notifications?limit=100` — Lista notificações (paginado)
- `POST /notifications/webhook/twilio` — Webhook para Twilio (delivery receipts)

### Sincronização
- `GET /sync/changes?since=2025-12-31T03:00:00` — Retorna apenas mudanças desde timestamp
  - Suporta header `If-Modified-Since` → responde 304 se nada mudou
  - Retorna `{"notificacoes": [...], "agendamentos": [...], "last_modified": "..."}`

### Agente IA
- `POST /agent/chat` — Conversa com assistente OpenAI

---

## 🚀 Próximos Passos Recomendados

### 1. Templates de Mensagens
Crie `app/services/message_templates.py`:
```python
def template_confirmacao(nome, data, hora):
    return f"Olá {nome}! Seu agendamento foi confirmado para {data} às {hora}. Até lá! 😊"

def template_lembrete(nome, data, hora):
    return f"Oi {nome}! Lembrete: seu atendimento é amanhã ({data}) às {hora}. Nos vemos em breve!"

def template_promocao(nome, oferta):
    return f"Ei {nome}! 🎉 Oferta especial: {oferta}. Agende já!"
```

### 2. Scheduler (Lembretes Automáticos)
Adicione APScheduler no backend para enviar lembretes 24h/2h antes:
```python
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.notifications import NotificationsService

scheduler = BackgroundScheduler()
scheduler.start()

def enviar_lembretes():
    # Buscar agendamentos nas próximas 24h
    # Chamar svc.send_sms(...) para cada um
    pass

scheduler.add_job(enviar_lembretes, 'interval', hours=1)
```

### 3. Retries e Filas
- Use Celery + Redis para filas assíncronas
- Adicione retry com backoff exponencial em `NotificationsService`

### 4. Monitoramento
- Integre Sentry: `pip install sentry-sdk[fastapi]`
- Configure alertas para taxa de falhas > 10%

### 5. Testes E2E
Crie `tests/test_notifications_flow.py`:
```python
def test_send_sms_and_webhook():
    # 1. POST /dashboard/agendamentos
    # 2. Verificar POST /notifications com status='sent'
    # 3. Simular webhook Twilio com status='delivered'
    # 4. Verificar atualização no DB
    pass
```

---

## 📊 Status do Projeto

### ✅ Concluído
- Unificação de status (pendente, confirmado, cancelado, lembrete_enviado, entregue, falha_envio)
- Contratos API front↔back documentados
- Serviço de notificações (abstração Twilio)
- Integração SMS e WhatsApp
- Webhook de delivery receipts
- Persistência de histórico de notificações
- Admin UI com mascote
- Instalação de dependências
- Polling/sync configurável (1-2min)

### 🚧 Pendente
- Templates i18n de mensagens
- Scheduler (lembretes automáticos)
- Retries, idempotência e filas
- Monitoramento (Sentry/Prometheus)
- Rotacionar/remover OPENAI_API_KEY vazada
- Documentação de runbook de erros
- Testes E2E

---

## 🤝 Contribuindo

1. Crie feature branch (`git checkout -b feature/AmazingFeature`)
2. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
3. Push para branch (`git push origin feature/AmazingFeature`)
4. Abra Pull Request

---

## 📝 Licença

Propriedade privada — todos os direitos reservados.

---

## 🆘 Troubleshooting

### Backend não inicia
- Verifique `.env` (DATABASE_URL, SECRET_KEY)
- Rode `python -m compileall -q app main.py` para verificar sintaxe
- Cheque logs do uvicorn

### Notificações não enviam
- Confirme credenciais Twilio no `.env`
- Teste endpoint `/notifications/test-send` manualmente
- Verifique saldo da conta Twilio

### Webhook não atualiza status
- Confirme ngrok está rodando e URL configurada no Twilio
- Verifique logs do backend (`uvicorn ... --log-level debug`)
- Desative validação de assinatura temporariamente (remova `TWILIO_AUTH_TOKEN`) para testar

### Frontend não sincroniza
- Abra DevTools → Network e verifique chamadas a `/sync/changes`
- Confirme backend rodando e CORS configurado
- Inspecione console para erros do `useSyncPoll`

---

## 🎉 Resultado Final

Você agora tem:
- ✅ Backend FastAPI robusto com Twilio, webhooks, sync endpoint
- ✅ Frontend React com polling inteligente, admin de notificações, mascote
- ✅ Integração completa SMS/WhatsApp
- ✅ Estrutura escalável para scheduler, retries e monitoramento

**Próxima ação sugerida:** Configure o Twilio Sandbox para WhatsApp e teste o fluxo end-to-end de criação de agendamento → envio de confirmação → recepção de webhook → atualização na UI admin.

Bora dominar o mercado! 🚀
