import os
import logging
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

try:
    from twilio.rest import Client
except ImportError:  # twilio may not be installed in some environments
    Client = None

from app.db.database import SessionLocal
from app.models.models import Notificacao, Agendamento, SetupProfile
from app.core.trial import compute_trial_status

logger = logging.getLogger(__name__)

# Read credentials from env
TWILIO_SID = os.getenv('TWILIO_SID')
TWILIO_TOKEN = os.getenv('TWILIO_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
# Número de SMS (deve ser um número habilitado para SMS na sua conta Twilio, ex: +1765xxxxxxx)
TWILIO_SMS_NUMBER = os.getenv('TWILIO_SMS_NUMBER')
MOCK_NOTIFICATIONS = os.getenv('MOCK_NOTIFICATIONS', 'false').lower() in ['1', 'true', 'yes']

# SMTP settings for sending email
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER or 'no-reply@easyagenda')
SMTP_TLS = os.getenv('SMTP_TLS', 'true').lower() not in ['false', '0', 'no']

if TWILIO_SID and TWILIO_TOKEN and Client is not None:
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
    except Exception:
        client = None
else:
    client = None


def is_twilio_configured():
    return client is not None


def is_smtp_configured():
    return SMTP_HOST is not None and SMTP_USER is not None and SMTP_PASS is not None


def _smtp_send(to: str, subject: str, body: str):
    if MOCK_NOTIFICATIONS:
        logger.info('MOCK SMTP send to %s subject=%s body=%s', to, subject, (body or '')[:120])
        return {'mock': True, 'status': 'sent'}
    if not is_smtp_configured():
        raise RuntimeError('SMTP not configured')
    msg = EmailMessage()
    msg['Subject'] = subject or 'EasyAgenda'
    msg['From'] = SMTP_FROM
    msg['To'] = to
    msg.set_content(body or '')

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_TLS:
            server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def _twilio_send(canal: str, to: str, body: str):
    """Low-level Twilio sender. Returns dict with response info or raises."""
    if MOCK_NOTIFICATIONS:
        # simulate a Twilio-like response without sending
        fake_sid = f"MOCK-{int(datetime.now(timezone.utc).timestamp())}"
        logger.info('MOCK Twilio send canal=%s to=%s body=%s', canal, to, (body or '')[:120])
        return {'sid': fake_sid, 'status': 'queued', 'raw': 'MOCK'}
    if not client:
        raise RuntimeError('Twilio client not configured')
    canal = (canal or '').lower()
    # normalizar destino para WhatsApp (precisa do prefixo whatsapp:)
    if canal == 'whatsapp':
        normalized_to = to if to.startswith('whatsapp:') else f'whatsapp:{to}'
        from_number = TWILIO_WHATSAPP_NUMBER
    else:
        normalized_to = to
        # Para SMS usamos TWILIO_SMS_NUMBER quando disponível; se não houver, caímos no número padrão
        from_number = TWILIO_SMS_NUMBER or TWILIO_WHATSAPP_NUMBER
    msg = client.messages.create(body=body, from_=from_number, to=normalized_to)
    return {"sid": getattr(msg, 'sid', None), "status": getattr(msg, 'status', None), "raw": str(msg)}


def enqueue_notification(
    canal: str,
    destinatario: str,
    mensagem: str,
    payload: dict = None,
    idempotency_key: str = None,
    max_attempts: int = 5,
    send_at: datetime | None = None,
):
    """Create a Notificacao row (queued) and return its id.

    If ``idempotency_key`` matches an existing non-permanent notification, returns that
    existing record's id instead.

    ``send_at`` (quando informado) é usado para agendar o primeiro envio no futuro,
    preenchendo ``next_attempt_at``. Quando omitido ou no passado, o envio é considerado
    imediatamente elegível e ficará com ``next_attempt_at`` em branco, sendo tratado pelo
    processador assim que ele rodar.
    """
    db = SessionLocal()
    try:
        if idempotency_key:
            existing = db.query(Notificacao).filter(Notificacao.idempotency_key == idempotency_key).first()
            if existing and existing.status != 'permanent_failure':
                return existing.id

        now = datetime.now(timezone.utc)

        notif = Notificacao(
            canal=canal,
            destinatario=destinatario,
            mensagem=mensagem,
            payload=payload,
            status='queued',
            attempts=0,
            max_attempts=max_attempts,
            idempotency_key=idempotency_key,
            criado_em=now,
        )

        # Se um horário futuro foi especificado, usamos next_attempt_at para controlar
        # quando o primeiro envio ficará elegível. Horários no passado/None significam
        # "assim que o worker rodar".
        if isinstance(send_at, datetime) and send_at > now:
            notif.next_attempt_at = send_at
        db.add(notif)
        db.commit()
        db.refresh(notif)

        # Se for e-mail e SMTP estiver configurado e não houver agendamento futuro,
        # enviar imediatamente para evitar fila parada.
        if canal == 'email' and is_smtp_configured() and not notif.next_attempt_at:
            try:
                subject = None
                if payload and isinstance(payload, dict):
                    subject = payload.get('subject') or payload.get('assunto')
                _smtp_send(destinatario, subject or 'EasyAgenda - Notificação', mensagem)
                notif.status = 'sent'
                notif.provider_response = {'provider': 'smtp', 'status': 'sent'}
                db.add(notif)
                db.commit()
            except Exception as e:
                # Em caso de falha, mantemos queued para retry via process_pending_notifications
                notif.last_error = f"SMTP error: {type(e).__name__}: {str(e)}"
                db.add(notif)
                db.commit()
        return notif.id
    finally:
        db.close()


def _compute_backoff_seconds(attempts: int):
    # exponential backoff base 60s, cap at 24h
    secs = (2 ** (attempts - 1)) * 60
    return min(secs, 60 * 60 * 24)


def send_notification_by_id(notif_id: int):
    """Attempt to send a notification by id; update DB with results and schedule retry if needed."""
    db = SessionLocal()
    try:
        notif = db.query(Notificacao).filter(Notificacao.id == notif_id).first()
        if not notif:
            return False

        # Trial hard stop: do not send appointment-related notifications after trial expiry.
        try:
            p = notif.payload if isinstance(notif.payload, dict) else {}
            ag_id = p.get('agendamento_id') or p.get('appointment_id')
            if ag_id is not None:
                ag = db.query(Agendamento).filter(Agendamento.id == int(ag_id)).first()
                est_id = None
                if ag is not None:
                    try:
                        # Prefer Cliente.estabelecimento_id (stable) if available.
                        if getattr(ag, 'cliente', None) is not None:
                            est_id = getattr(ag.cliente, 'estabelecimento_id', None)
                    except Exception:
                        est_id = None

                    if est_id is None:
                        try:
                            # Fallback: resolve via professional.
                            from app.models.models import Funcionario
                            prof = db.query(Funcionario).filter(Funcionario.id == ag.funcionario_id).first()
                            est_id = getattr(prof, 'estabelecimento_id', None) if prof else None
                        except Exception:
                            est_id = None

                if est_id is not None:
                    row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == int(est_id)).first()
                    setup_payload = row.payload if row else None
                    st = compute_trial_status(setup_payload)
                    if st.expired:
                        notif.status = 'permanent_failure'
                        notif.last_error = 'trial_expired'
                        notif.provider_response = {'error': 'trial_expired'}
                        notif.next_attempt_at = None
                        db.add(notif)
                        db.commit()
                        return False
        except Exception:
            # Never crash the worker due to trial checks.
            pass

        # Mark as sending
        notif.status = 'sending'
        notif.attempts = (notif.attempts or 0) + 1
        notif.last_error = None
        db.add(notif)
        db.commit()
        db.refresh(notif)

        try:
            if (notif.canal or '').lower() == 'email':
                subject = None
                if notif.payload and isinstance(notif.payload, dict):
                    subject = notif.payload.get('subject') or notif.payload.get('assunto')
                _smtp_send(notif.destinatario, subject or 'EasyAgenda - Notificação', notif.mensagem)
                notif.provider_response = {'provider': 'smtp', 'status': 'sent'}
                notif.provider_id = None
                notif.status = 'sent'
                notif.last_error = None
                notif.next_attempt_at = None
            else:
                resp = _twilio_send(notif.canal or 'sms', notif.destinatario, notif.mensagem)
                notif.provider_response = resp
                notif.provider_id = resp.get('sid')
                notif.status = 'sent'
                notif.last_error = None
                notif.next_attempt_at = None
        except Exception as e:
            # transient failure
            err_text = f"{type(e).__name__}: {str(e)}"
            logger.exception('Notification send failed')
            notif.last_error = err_text
            notif.attempts = (notif.attempts or 0)
            if notif.attempts >= (notif.max_attempts or 5):
                notif.status = 'permanent_failure'
                notif.next_attempt_at = None
            else:
                notif.status = 'failed'
                backoff = _compute_backoff_seconds(notif.attempts)
                notif.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)

        db.add(notif)
        db.commit()
        return notif.status == 'sent'
    finally:
        db.close()


def process_pending_notifications(limit: int = 50):
    """Scan queued/failed notifications and try to send those due for retry."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        q = db.query(Notificacao).filter(
            Notificacao.status.in_(['queued', 'failed']),
            ((Notificacao.next_attempt_at == None) | (Notificacao.next_attempt_at <= now))
        ).order_by(Notificacao.criado_em).limit(limit)
        items = q.all()
        for n in items:
            send_notification_by_id(n.id)
    finally:
        db.close()
