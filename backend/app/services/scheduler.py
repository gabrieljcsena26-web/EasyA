from __future__ import annotations

from datetime import datetime, timedelta, timezone, time as dt_time

from app.services.notifications_v2 import enqueue_notification
from app.i18n import get_message
from app.core.locale import resolve_lang, resolve_timezone, as_utc
from app.services.notificar_interessados import notificar_interessados
from app.services.pending_actions import enqueue_pending_action

LEMBRETE_PADRAO_HORAS = [14, 2]  # legado / fallback

CONFIRM_WINDOW_HOURS = 6
OFFICIAL_CONFIRM_WINDOW_HOURS = 3
MIN_HOURS_FOR_TWO_STEP = 24
MORNING_CUTOFF_HOUR = 14

# Official confirmation (final reminder/handshake) defaults (business-local time)
# - Appointment <= 14:00 => send 14:00 previous day, cap deadline 17:00 previous day.
# - Appointment  > 14:00 => send 17:00 previous day, deadline = send + 3h.
SEND_PREV_DAY_MORNING_AT = dt_time(14, 0)
DEADLINE_PREV_DAY_MORNING_AT = dt_time(17, 0)
SEND_PREV_DAY_AFTERNOON_AT = dt_time(17, 0)


def _parse_hhmm(value: object) -> dt_time | None:
    if not value:
        return None
    if isinstance(value, dt_time):
        return value
    if isinstance(value, str):
        s = value.strip()
        try:
            parts = s.split(":")
            if len(parts) < 2:
                return None
            hh = int(parts[0])
            mm = int(parts[1])
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return dt_time(hh, mm)
        except Exception:
            return None
    return None


def _extract_confirmation_container(setup_payload: dict) -> dict:
    setup_payload = setup_payload if isinstance(setup_payload, dict) else {}
    if isinstance(setup_payload.get("confirmation"), dict):
        return setup_payload.get("confirmation")  # type: ignore[return-value]
    biz = setup_payload.get("business") if isinstance(setup_payload.get("business"), dict) else {}
    if isinstance(biz.get("confirmation"), dict):
        return biz.get("confirmation")  # type: ignore[return-value]
    return {}


def _as_utc(dt: datetime) -> datetime:
    return as_utc(dt)


def _get_timezone(setup_payload: dict):
    tz, _tz_name = resolve_timezone(setup_payload)
    return tz


def _get_estabelecimento_lang(estabelecimento_id: int | None, db=None) -> str | None:
    if not estabelecimento_id:
        return None
    owns_db = False
    try:
        if db is None:
            from app.db.database import SessionLocal
            db = SessionLocal()
            owns_db = True
        from app.models.models import Estabelecimento
        est = db.query(Estabelecimento).filter(Estabelecimento.id == estabelecimento_id).first()
        return getattr(est, 'idioma_padrao', None) if est else None
    finally:
        if owns_db and db is not None:
            db.close()


def _deposit_enabled(setup_payload: dict) -> bool:
    setup_payload = setup_payload if isinstance(setup_payload, dict) else {}
    pol = setup_payload.get('policies') if isinstance(setup_payload.get('policies'), dict) else {}
    return bool(pol.get('depositEnabled'))


def _human_when(now_local: datetime, when_local: datetime) -> str:
    """Converte um datetime local em uma descrição curta (hoje/amanhã/data)."""

    try:
        if when_local.date() == now_local.date():
            return f"hoje às {when_local.strftime('%H:%M')}"
        if when_local.date() == (now_local.date() + timedelta(days=1)):
            return f"amanhã às {when_local.strftime('%H:%M')}"
        return when_local.strftime("%d/%m às %H:%M")
    except Exception:
        return when_local.strftime('%H:%M')


def get_setup_payload_for_estabelecimento(estabelecimento_id: int | None, db=None) -> dict:
    if not estabelecimento_id:
        return {}

    owns_db = False
    try:
        if db is None:
            from app.db.database import SessionLocal
            db = SessionLocal()
            owns_db = True

        from app.models.models import SetupProfile

        sp = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == estabelecimento_id).first()
        payload = getattr(sp, 'payload', None)
        return payload if isinstance(payload, dict) else {}
    finally:
        if owns_db and db is not None:
            db.close()


def _extract_reminder_hours(setup_payload: dict) -> list[int]:
    setup_payload = setup_payload if isinstance(setup_payload, dict) else {}
    notifications = setup_payload.get('notifications') if isinstance(setup_payload.get('notifications'), dict) else {}
    business = setup_payload.get('business') if isinstance(setup_payload.get('business'), dict) else {}

    raw = (
        notifications.get('reminderHours')
        or notifications.get('lembrete_horas_antes')
        or business.get('lembrete_horas_antes')
        or []
    )

    hours: list[int] = []
    if isinstance(raw, list):
        for v in raw:
            try:
                n = int(v)
                if n > 0:
                    hours.append(n)
            except Exception:
                continue

    # A UI normalmente salva em ordem decrescente (ex: [24, 3]); garantimos isso aqui.
    hours = sorted(set(hours), reverse=True)

    # Precisamos de 2 etapas. Se vier 1 só, completamos com o fallback.
    if len(hours) >= 2:
        return hours[:2]
    if len(hours) == 1:
        fallback_second = next((h for h in LEMBRETE_PADRAO_HORAS if h != hours[0]), LEMBRETE_PADRAO_HORAS[-1])
        return [hours[0], fallback_second]
    return list(LEMBRETE_PADRAO_HORAS)


def _extract_channels(setup_payload: dict) -> dict:
    setup_payload = setup_payload if isinstance(setup_payload, dict) else {}
    notifications = setup_payload.get('notifications') if isinstance(setup_payload.get('notifications'), dict) else {}
    channels = notifications.get('channels') if isinstance(notifications.get('channels'), dict) else {}

    # Default automático: WhatsApp + SMS.
    whatsapp = channels.get('whatsapp')
    sms = channels.get('sms')
    return {
        'whatsapp': True if whatsapp is None else bool(whatsapp),
        'sms': True if sms is None else bool(sms),
    }


def _extract_confirmation_rule_hours(setup_payload: dict) -> int:
    """Threshold (24/36) para decidir fluxo de confirmação.

    Qualquer valor inesperado cai no fallback 24h.
    """

    setup_payload = setup_payload if isinstance(setup_payload, dict) else {}

    # Preferred (new): confirmation.immediateHorizonHours
    conf = _extract_confirmation_container(setup_payload)
    raw = conf.get("immediateHorizonHours")
    try:
        value = int(raw)
        if value > 0:
            return value
    except Exception:
        pass

    # Legacy: notifications.confirmationRuleHours (24/36)
    notifications = setup_payload.get('notifications') if isinstance(setup_payload.get('notifications'), dict) else {}
    raw = notifications.get('confirmationRuleHours')
    try:
        value = int(raw)
    except Exception:
        return 24
    return 36 if value == 36 else 24


def _extract_immediate_window_hours(setup_payload: dict) -> int:
    conf = _extract_confirmation_container(setup_payload)
    raw = conf.get("immediateWindowHours")
    try:
        value = int(raw)
        if 1 <= value <= 24:
            return value
    except Exception:
        pass
    return CONFIRM_WINDOW_HOURS


def _official_confirmation_schedule_local(appt_local: datetime, setup_payload: dict) -> tuple[datetime, datetime, float]:
    """Returns (send_local, deadline_local, window_hours) for the official confirmation."""

    conf = _extract_confirmation_container(setup_payload)
    is_morning = appt_local.hour <= MORNING_CUTOFF_HOUR

    # Backwards compatible keys:
    # - sendTimePrevDay / capDeadlinePrevDay
    # Optional split keys (allow different morning vs afternoon schedules):
    # - sendTimePrevDayMorning / capDeadlinePrevDayMorning
    # - sendTimePrevDayAfternoon / capDeadlinePrevDayAfternoon
    if is_morning:
        send_prev = _parse_hhmm(conf.get("sendTimePrevDayMorning")) or _parse_hhmm(conf.get("sendTimePrevDay"))
        cap_prev = _parse_hhmm(conf.get("capDeadlinePrevDayMorning")) or _parse_hhmm(conf.get("capDeadlinePrevDay"))
        default_send_clock = SEND_PREV_DAY_MORNING_AT
        default_cap_clock = DEADLINE_PREV_DAY_MORNING_AT
    else:
        send_prev = _parse_hhmm(conf.get("sendTimePrevDayAfternoon")) or _parse_hhmm(conf.get("sendTimePrevDay"))
        cap_prev = _parse_hhmm(conf.get("capDeadlinePrevDayAfternoon")) or _parse_hhmm(conf.get("capDeadlinePrevDay"))
        default_send_clock = SEND_PREV_DAY_AFTERNOON_AT
        default_cap_clock = None

    tz = appt_local.tzinfo
    send_date = appt_local.date() - timedelta(days=1)
    send_clock = send_prev or default_send_clock
    send_local = datetime.combine(send_date, send_clock, tzinfo=tz)

    if cap_prev is not None:
        deadline_local = datetime.combine(send_date, cap_prev, tzinfo=tz)
        if deadline_local < send_local:
            deadline_local = send_local
    else:
        if default_cap_clock is not None:
            deadline_local = datetime.combine(send_date, default_cap_clock, tzinfo=tz)
            if deadline_local < send_local:
                deadline_local = send_local
        else:
            deadline_local = send_local + timedelta(hours=OFFICIAL_CONFIRM_WINDOW_HOURS)

    # Never allow a deadline after the appointment start.
    if deadline_local > appt_local:
        deadline_local = appt_local

    window_hours = max(0.0, (deadline_local - send_local).total_seconds() / 3600.0)
    return send_local, deadline_local, window_hours


def pick_notification_channel(tipo: str, setup_payload: dict) -> str:
    channels = _extract_channels(setup_payload)

    tipo = (tipo or '').lower()
    if tipo in ['lembrete', 'reminder']:
        preferred = ['sms', 'whatsapp']
    else:
        preferred = ['whatsapp', 'sms']

    for c in preferred:
        if channels.get(c):
            return c
    return 'sms'


def pick_confirmation_response_channel(setup_payload: dict) -> str:
    """Canal para confirmação oficial (resposta via texto).

    Preferimos SMS para garantir que a resposta por texto chegue no mesmo canal.
    """

    channels = _extract_channels(setup_payload)
    if channels.get('sms'):
        return 'sms'
    if channels.get('whatsapp'):
        return 'whatsapp'
    return 'sms'


def _official_confirmation_send_time_local(appt_local: datetime) -> datetime:
    """Regra operacional:

    - Se consulta <= 14:00: enviar 14:00 no dia anterior.
    - Se consulta > 14:00: enviar 17:00 no dia anterior.
    """

    tz = appt_local.tzinfo
    if appt_local.hour <= MORNING_CUTOFF_HOUR:
        send_date = appt_local.date() - timedelta(days=1)
        return datetime.combine(send_date, SEND_PREV_DAY_MORNING_AT, tzinfo=tz)
    send_date = appt_local.date() - timedelta(days=1)
    return datetime.combine(send_date, SEND_PREV_DAY_AFTERNOON_AT, tzinfo=tz)


def agendar_lembretes_para_agendamento(agendamento, cliente, lang="pt-BR", db=None, estabelecimento_id: int | None = None):
    """Agenda confirmação conforme regras reais:

        - Se agendamento >= 24h (ou 36h, se configurado): envia uma pré-confirmação imediata + uma confirmação oficial em horário fixo
            (14:00 no dia anterior para manhã; 17:00 no dia anterior para tarde), com janela de 3h.
        - Se agendamento < limiar: envia apenas uma confirmação urgente imediata com janela de 6h.

    A janela expirada resulta em auto-cancelamento via PendingAction.
    """

    data_hora = getattr(agendamento, 'data_hora', None)
    telefone = getattr(cliente, "telefone", None)
    nome_cliente = getattr(cliente, "nome", "")

    if not telefone or not data_hora:
        return

    now_utc = datetime.now(timezone.utc)
    data_hora_utc = _as_utc(data_hora)
    if data_hora_utc <= now_utc:
        return

    est_id = estabelecimento_id or getattr(cliente, 'estabelecimento_id', None)
    setup_payload = get_setup_payload_for_estabelecimento(est_id, db=db)
    tz, _tz_name = resolve_timezone(setup_payload)
    appt_local = data_hora_utc.astimezone(tz)
    now_local = now_utc.astimezone(tz)

    est_lang = _get_estabelecimento_lang(est_id, db=db)
    lang = resolve_lang(
        cliente_lang=getattr(cliente, 'idioma', None),
        estabelecimento_lang=est_lang,
        accept_language=lang,
    )

    hours_to_appt = (data_hora_utc - now_utc).total_seconds() / 3600.0

    canal_conf = pick_notification_channel('confirmacao', setup_payload)
    deposit_enabled = _deposit_enabled(setup_payload)

    min_hours_for_two_step = _extract_confirmation_rule_hours(setup_payload)
    immediate_window_hours = _extract_immediate_window_hours(setup_payload)

    if hours_to_appt >= min_hours_for_two_step:
        # 1) Pré-confirmação (imediata)
        send_local, deadline_local, window_hours = _official_confirmation_schedule_local(appt_local, setup_payload)
        msg_pre = get_message(
            "pre_confirmacao",
            lang=lang,
            nome=nome_cliente,
            hora=appt_local.strftime('%H:%M'),
            quando=_human_when(now_local, send_local),
            janela_h=round(window_hours, 1),
        )
        enqueue_notification(
            canal_conf,
            telefone,
            msg_pre,
            payload={"tipo": "pre_confirmacao", "agendamento_id": agendamento.id},
            idempotency_key=f"pre_confirmacao_{agendamento.id}_{telefone}_{canal_conf}",
        )

        # 2) Confirmação oficial (horário fixo)
        send_utc = _as_utc(send_local)
        if send_utc > now_utc:
            deadline_utc = _as_utc(deadline_local)
            key = "confirmacao_oficial_com_deposito" if deposit_enabled else "confirmacao_oficial_sem_deposito"
            msg_off = get_message(
                key,
                lang=lang,
                nome=nome_cliente,
                hora=appt_local.strftime('%H:%M'),
                prazo=deadline_local.strftime('%H:%M'),
            )

            canal_off = pick_confirmation_response_channel(setup_payload)
            enqueue_notification(
                canal_off,
                telefone,
                msg_off,
                payload={
                    "tipo": "confirmacao_oficial",
                    "agendamento_id": agendamento.id,
                    "deadline_at": deadline_utc.isoformat(),
                },
                idempotency_key=f"confirmacao_oficial_{agendamento.id}_{telefone}_{canal_off}_{send_utc.isoformat()}",
                send_at=send_utc,
            )

            if db is not None:
                enqueue_pending_action(
                    db=db,
                    action_type="auto_cancel_no_response",
                    payload={
                        "agendamento_id": agendamento.id,
                        "deadline_at": deadline_utc.isoformat(),
                    },
                    run_at=deadline_utc,
                    idempotency_key=f"auto_cancel_no_response_{agendamento.id}_{deadline_utc.isoformat()}",
                )
        return

    # <24h: confirmação urgente (imediata)
    deadline_utc = now_utc + timedelta(hours=immediate_window_hours)
    if deadline_utc > data_hora_utc:
        deadline_utc = data_hora_utc
    deadline_local = deadline_utc.astimezone(tz)
    key = "confirmacao_urgente_com_deposito" if deposit_enabled else "confirmacao_urgente_sem_deposito"
    msg_urg = get_message(
        key,
        lang=lang,
        nome=nome_cliente,
        hora=appt_local.strftime('%H:%M'),
        prazo=deadline_local.strftime('%H:%M'),
    )

    canal_urg = pick_confirmation_response_channel(setup_payload)
    enqueue_notification(
        canal_urg,
        telefone,
        msg_urg,
        payload={
            "tipo": "confirmacao_urgente",
            "agendamento_id": agendamento.id,
            "deadline_at": deadline_utc.isoformat(),
        },
        idempotency_key=f"confirmacao_urgente_{agendamento.id}_{telefone}_{canal_urg}_{now_utc.isoformat()}",
    )

    if db is not None:
        enqueue_pending_action(
            db=db,
            action_type="auto_cancel_no_response",
            payload={
                "agendamento_id": agendamento.id,
                "deadline_at": deadline_utc.isoformat(),
            },
            run_at=deadline_utc,
            idempotency_key=f"auto_cancel_no_response_{agendamento.id}_{deadline_utc.isoformat()}",
        )

def processar_resposta_agendamento(resposta, agendamento, db):
    """Processa resposta do cliente por texto.

    Regras:
    - 1 => confirmar
    - 2 => reagendar (marca status para ação humana)
    - 3 => cancelar
    """

    r = str(resposta or '').strip().lower()
    if not r:
        return None

    if r in ('1', 'confirmar', 'confirmo', 'sim'):
        agendamento.status = 'confirmado'
        db.commit()
        return 'confirmado'

    if r in ('2', 'reagendar', 'remarcar'):
        agendamento.status = 'reagendar'
        db.commit()
        return 'reagendar'

    if r in ('3', 'cancelar', 'cancelo', 'nao', 'não'):
        agendamento.status = 'cancelado'
        db.commit()
        try:
            notificar_interessados(agendamento, db)
        except Exception:
            pass
        return 'cancelado'

    return None


def processar_resposta_cancelamento(resposta, agendamento, db):
    # Compatibilidade com fluxos antigos ("1" cancelava)
    status = processar_resposta_agendamento(resposta, agendamento, db)
    return status == 'cancelado'
