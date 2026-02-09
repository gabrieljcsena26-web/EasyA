from fastapi import APIRouter, Depends, HTTPException, status, Header
# touch: trigger reload when backend running with --reload
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
import math
from app.db.database import get_db
from app.models.models import (
    Estabelecimento,
    Cliente,
    Agendamento,
    Notificacao,
    Interesse,
    Service,
    Funcionario,
    Invoice,
    PendingAction,
    SetupProfile,
)
from fastapi.security import OAuth2PasswordBearer
import os
from pydantic import BaseModel
from fastapi import Body
from app.services.notifications_v2 import enqueue_notification, is_twilio_configured, is_smtp_configured, process_pending_notifications, send_notification_by_id
from app.core.security import verify_access_token
from app.core.trial import TRIAL_DAYS_DEFAULT, compute_trial_status

router = APIRouter(prefix="/admin", tags=["admin"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL")

def check_superadmin(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
    x_dev_auth: str | None = Header(None),
):
    """Valida o token JWT e restringe acesso ao SUPERADMIN_EMAIL (se definido).

    - Se SUPERADMIN_EMAIL estiver configurado, somente o estabelecimento com esse e-mail
      terá acesso às rotas /admin.
    - Caso não esteja definido, qualquer token válido terá acesso (modo dev).
    """
    # Produção/normal: ler Authorization header manualmente
    import os
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não fornecido")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Header Authorization inválido")

    token = authorization[len("Bearer ") :]
    try:
        payload = verify_access_token(token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")

    slug = payload.get("slug")
    if not slug:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem slug")
    # Ambiente de desenvolvimento: qualquer usuário autenticado pode acessar /admin.
    # Futuramente, podemos reativar o filtro por SUPERADMIN_EMAIL aqui.
    est_id = payload.get("estabelecimento_id") or 0
    return {"slug": slug, "estabelecimento_id": est_id}

@router.get("/resumo")
def resumo_geral(db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    return {
        "clientes": db.query(Cliente).count(),
        "estabelecimentos": db.query(Estabelecimento).count(),
        "agendamentos": db.query(Agendamento).count(),
        "notificacoes": db.query(Notificacao).count(),
        "interesses": db.query(Interesse).count(),
    }


# Endpoint de teste rápido para verificar DEV_AUTH_BYPASS e header X-Dev-Auth


# Adicione endpoints para faturamento, logs, erros, etc, sempre usando check_superadmin
class TestSmsPayload(BaseModel):
    to: str
    message: str
    canal: str = 'sms'


@router.post('/test-sms')
def test_sms(payload: TestSmsPayload, auth=Depends(check_superadmin)):
    """Enfileira e tenta enviar imediatamente uma notificação de teste via Twilio."""
    if not is_twilio_configured():
        raise HTTPException(status_code=400, detail='Twilio não configurado (TWILIO_SID/TWILIO_TOKEN ausentes)')

    notif_id = enqueue_notification(
        payload.canal,
        payload.to,
        payload.message,
        payload={"test": True},
        idempotency_key=None,
    )

    try:
        sent = send_notification_by_id(notif_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao enviar via Twilio: {type(e).__name__}: {e}")

    return {"ok": True, "notification_id": notif_id, "sent": bool(sent), "canal": payload.canal, "to": payload.to}


class SimulateRemindersPayload(BaseModel):
    """Payload para simular lembretes rápidos usando MOCK_NOTIFICATIONS.

    Cria duas notificações na fila ("confirmacao" e "lembrete") com horários
    próximos, para você ver o worker processando no log sem esperar horas.
    """

    to: str
    # minutos até o primeiro envio (confirmacao); o segundo será +delta_minutos
    minutos_para_confirmacao: int = 1
    minutos_para_lembrete: int = 3
    canal: str = "sms"


@router.post("/simular-lembretes")
def simular_lembretes(payload: SimulateRemindersPayload, auth=Depends(check_superadmin)):
    """Agenda duas notificações de teste para daqui a poucos minutos.

    Pensado para ambiente com MOCK_NOTIFICATIONS=true:
    - Cria uma notificação "confirmacao" para agora + N minutos
    - Cria uma notificação "lembrete" para agora + M minutos

    O worker em background (ou o endpoint /admin/notifications-retry) irá
    processar esses itens quando chegar a hora, gerando logs de envio
    simulado via Twilio/SMTP.
    """

    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    minutos_conf = max(payload.minutos_para_confirmacao, 0)
    minutos_lem = max(payload.minutos_para_lembrete, minutos_conf + 1)

    send_at_conf = now + timedelta(minutes=minutos_conf)
    send_at_lem = now + timedelta(minutes=minutos_lem)

    id_conf = enqueue_notification(
        payload.canal,
        payload.to,
        "[SIMULACAO] Confirmacao de agendamento EasyAgenda.",
        payload={"tipo": "confirmacao", "simulacao": True},
        idempotency_key=f"sim_conf_{payload.to}_{int(send_at_conf.timestamp())}",
        send_at=send_at_conf,
    )

    id_lem = enqueue_notification(
        payload.canal,
        payload.to,
        "[SIMULACAO] Lembrete de agendamento EasyAgenda.",
        payload={"tipo": "lembrete", "simulacao": True},
        idempotency_key=f"sim_lem_{payload.to}_{int(send_at_lem.timestamp())}",
        send_at=send_at_lem,
    )

    return {
        "ok": True,
        "confirmacao": {
            "id": id_conf,
            "send_at": send_at_conf,
        },
        "lembrete": {
            "id": id_lem,
            "send_at": send_at_lem,
        },
    }

    return {"notificacao_id": notif_id, "sent": sent}


@router.get('/twilio-status')
def twilio_status(auth=Depends(check_superadmin)):
    configured = is_twilio_configured()
    tw_num = os.getenv('TWILIO_WHATSAPP_NUMBER', None)
    if tw_num and isinstance(tw_num, str):
        masked = (tw_num[:6] + '****') if len(tw_num) > 6 else '****'
    else:
        masked = None
    return {"configured": configured, "from": masked}


@router.get('/notifications-summary')
def notifications_summary(db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    """Resumo rápido da fila de notificações (por status)."""
    rows = (
        db.query(Notificacao.status, func.count(Notificacao.id))
        .group_by(Notificacao.status)
        .all()
    )
    counts = {status or 'unknown': count for status, count in rows}

    # Última notificação com erro (se existir)
    last_failed = (
        db.query(Notificacao)
        .filter(Notificacao.status.in_(['failed', 'permanent_failure']))
        .order_by(Notificacao.atualizado_em.desc() if hasattr(Notificacao, 'atualizado_em') else Notificacao.criado_em.desc())
        .first()
    )
    last_error = None
    if last_failed and getattr(last_failed, 'last_error', None):
        last_error = last_failed.last_error

    oldest_queued = (
        db.query(Notificacao)
        .filter(Notificacao.status.in_(['queued', 'failed']))
        .order_by(Notificacao.criado_em.asc())
        .first()
    )

    return {
        "counts": counts,
        "oldest_queued_at": getattr(oldest_queued, 'criado_em', None),
        "last_error": last_error,
    }


def _mask_phone(v: str | None):
    if not v:
        return None
    s = str(v).strip()
    if len(s) <= 4:
        return '****'
    # keep last 4 digits-ish
    tail = ''.join([c for c in s if c.isdigit()])[-4:]
    prefix = s[:6]
    return f"{prefix}****{tail}" if tail else f"{prefix}****"


def _notif_to_ops_row(n: Notificacao, now: datetime, ag_by_id: dict[int, Agendamento]):
    payload = n.payload if isinstance(n.payload, dict) else {}
    ag_id = payload.get('agendamento_id')
    ag = ag_by_id.get(int(ag_id)) if ag_id is not None and str(ag_id).isdigit() else None

    next_at = getattr(n, 'next_attempt_at', None)
    next_in_minutes = None
    if isinstance(next_at, datetime):
        try:
            delta = (next_at - now).total_seconds()
            next_in_minutes = int(delta // 60)
        except Exception:
            next_in_minutes = None

    cliente_nome = None
    ag_data_hora = None
    ag_status = None
    if ag is not None:
        ag_status = getattr(ag, 'status', None)
        if getattr(ag, 'data_hora', None):
            ag_data_hora = ag.data_hora.isoformat()
        if getattr(ag, 'cliente', None) is not None:
            cliente_nome = getattr(ag.cliente, 'nome', None)

    provider_status = None
    if isinstance(n.provider_response, dict):
        provider_status = n.provider_response.get('status')

    return {
        "id": n.id,
        "tipo": payload.get('tipo'),
        "agendamento_id": int(ag_id) if ag_id is not None and str(ag_id).isdigit() else None,
        "agendamento_status": ag_status,
        "agendamento_data_hora": ag_data_hora,
        "cliente_nome": cliente_nome,
        "canal": n.canal,
        "status": n.status,
        "provider_status": provider_status,
        "destinatario": _mask_phone(n.destinatario),
        "created_at": n.criado_em.isoformat() if n.criado_em else None,
        "next_attempt_at": next_at.isoformat() if isinstance(next_at, datetime) else None,
        "next_in_minutes": next_in_minutes,
        "attempts": getattr(n, 'attempts', None),
        "max_attempts": getattr(n, 'max_attempts', None),
        "last_error": getattr(n, 'last_error', None) or getattr(n, 'erro', None),
    }


@router.get('/notifications-dashboard')
def notifications_dashboard(
    limit_upcoming: int = 25,
    limit_recent: int = 25,
    db: Session = Depends(get_db),
    auth=Depends(check_superadmin),
):
    """Painel operacional de notificações (automático).

    Retorna:
    - contagens por status
    - próximos envios (queued/failed) com minutos até o envio
    - últimas entregas/envios (sent/delivered/failed/permanent_failure)
    - enriquecimento com agendamento/cliente quando payload contém agendamento_id
    """
    now = datetime.now(timezone.utc)

    # counts
    rows = (
        db.query(Notificacao.status, func.count(Notificacao.id))
        .group_by(Notificacao.status)
        .all()
    )
    counts = {status or 'unknown': count for status, count in rows}

    # upcoming: due or scheduled
    upcoming_raw = (
        db.query(Notificacao)
        .filter(Notificacao.status.in_(['queued', 'failed']))
        .order_by(Notificacao.next_attempt_at.asc())
        .limit(max(1, limit_upcoming) * 5)
        .all()
    )
    # Normalize ordering: None means "eligible now"
    upcoming_raw.sort(key=lambda n: getattr(n, 'next_attempt_at', None) or now)
    upcoming_raw = upcoming_raw[: max(1, limit_upcoming)]

    recent_raw = (
        db.query(Notificacao)
        .filter(Notificacao.status.in_(['sent', 'delivered', 'sending', 'failed', 'permanent_failure']))
        .order_by(Notificacao.criado_em.desc())
        .limit(max(1, limit_recent))
        .all()
    )

    # Enrich using agendamento_id from payload
    ag_ids: set[int] = set()
    for n in list(upcoming_raw) + list(recent_raw):
        payload = n.payload if isinstance(n.payload, dict) else {}
        ag_id = payload.get('agendamento_id')
        if ag_id is not None and str(ag_id).isdigit():
            ag_ids.add(int(ag_id))

    ag_by_id: dict[int, Agendamento] = {}
    if ag_ids:
        ags = (
            db.query(Agendamento)
            .options(joinedload(Agendamento.cliente))
            .filter(Agendamento.id.in_(sorted(list(ag_ids))))
            .all()
        )
        ag_by_id = {a.id: a for a in ags}

    upcoming = [_notif_to_ops_row(n, now=now, ag_by_id=ag_by_id) for n in upcoming_raw]
    recent = [_notif_to_ops_row(n, now=now, ag_by_id=ag_by_id) for n in recent_raw]

    next_in_minutes = None
    for r in upcoming:
        m = r.get('next_in_minutes')
        if m is None:
            continue
        if next_in_minutes is None or m < next_in_minutes:
            next_in_minutes = m

    return {
        "ok": True,
        "now": now.isoformat(),
        "provider": {
            "twilio_configured": bool(is_twilio_configured()),
            "smtp_configured": bool(is_smtp_configured()),
        },
        "counts": counts,
        "next_in_minutes": next_in_minutes,
        "upcoming": upcoming,
        "recent": recent,
    }


@router.post('/notifications-retry')
def notifications_retry(limit: int = 50, auth=Depends(check_superadmin)):
    """Força um ciclo de retry das notificações pendentes/falhas.

    Útil como "auto-fix" rápido quando há itens presos na fila.
    """
    processed = process_pending_notifications(limit=limit)
    # process_pending_notifications não retorna contagem; para simplicidade, só retornamos o limit pedido
    return {"requested_limit": limit, "status": "ok"}


@router.get("/health")
def admin_health(db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    """Retorna um diagnóstico rápido do backend para o painel admin.

    Verifica:
    - Conexão com o banco
    - Configuração de SMTP
    - Configuração de Twilio
    - Se SECRET_KEY ainda está no valor de desenvolvimento
    """

    issues: list[str] = []

    # DB check simples
    db_ok = True
    db_error: str | None = None
    try:
        # consulta leve só para validar conexão
        db.query(Estabelecimento).count()
    except Exception as e:
        db_ok = False
        db_error = str(e)
        issues.append("db_error")

    smtp_ok = is_smtp_configured()
    if not smtp_ok:
        issues.append("smtp_not_configured")

    twilio_ok = is_twilio_configured()
    if not twilio_ok:
        issues.append("twilio_not_configured")

    secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
    secret_key_default = secret_key == "dev-secret-change-me"
    if secret_key_default:
        issues.append("secret_key_default")

    return {
        "db_ok": db_ok,
        "db_error": db_error,
        "smtp_configured": smtp_ok,
        "twilio_configured": twilio_ok,
        "secret_key_default": secret_key_default,
        "issues": issues,
    }


# ---------------------------
# CONFIGURAÇÃO DO NEGÓCIO (para dashboard principal)
# ---------------------------


class BusinessConfig(BaseModel):
    """Dados básicos do estabelecimento que o painel pode editar.

    Mantemos próximo do modelo Estabelecimento existente para evitar
    campos soltos.
    """

    nome: str
    telefone: str
    slug: str
    email: str | None = None
    idioma_padrao: str | None = None
    timezone: str | None = None
    lembrete_horas_antes: list[int] | None = None
    horario_inicio: int | None = None
    horario_fim: int | None = None
    photos: list[str] | None = None
    reviews: list[dict] | None = None


class ServiceConfig(BaseModel):
    id: int | None = None
    name: str
    duration_min: int
    buffer_min: int | None = None
    price_cents: int = 0
    display_interval_min: int = 30


class ProfessionalConfig(BaseModel):
    id: int | None = None
    name: str
    telefone: str


class AdminConfigPayload(BaseModel):
    """Shape usado pelo painel para salvar configurações.

    - business: dados gerais do salão
    - services: serviços oferecidos
    - professionals: equipe
    """

    business: BusinessConfig
    services: list[ServiceConfig] = []
    professionals: list[ProfessionalConfig] = []


def _get_primary_estabelecimento(db: Session, auth: dict | None = None) -> Estabelecimento:
    """Replica a lógica de booking._get_single_estabelecimento.

    Assim garantimos que o /admin/config está mexendo no mesmo
    estabelecimento que /booking/config expõe para dashboard/landing.
    """

    # 0) Se o auth vier com slug ou estabelecimento_id, preferimos usá-lo
    est = None
    if auth:
        auth_slug = auth.get("slug")
        auth_id = auth.get("estabelecimento_id")
        if auth_slug:
            est = db.query(Estabelecimento).filter(Estabelecimento.slug == auth_slug).first()
        if not est and auth_id:
            est = db.query(Estabelecimento).filter(Estabelecimento.id == auth_id).first()

    if not est:
        est = (
            db.query(Estabelecimento)
            .filter(Estabelecimento.slug == "ana-beleza-madrid")
            .first()
        )

    if not est:
        est = db.query(Estabelecimento).first()

    if not est:
        raise HTTPException(status_code=400, detail="Nenhum estabelecimento configurado")

    return est


@router.get("/config")
def get_admin_config(db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    """Retorna configuração de negócio + serviços + equipe para o painel.

    Esta rota é pensada para a tela "Configurações" do dashboard e
    complementa o /booking/config (focado na landing/agenda).
    """

    est = _get_primary_estabelecimento(db, auth=auth)

    services = (
        db.query(Service)
        .filter(Service.estabelecimento_id == est.id)
        .order_by(Service.id.asc())
        .all()
    )
    professionals = (
        db.query(Funcionario)
        .filter(Funcionario.estabelecimento_id == est.id)
        .order_by(Funcionario.id.asc())
        .all()
    )

    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row and isinstance(setup_row.payload, dict) else {}
    business_payload = setup_payload.get('business') if isinstance(setup_payload.get('business'), dict) else {}
    tz_name = business_payload.get('timezone') or setup_payload.get('timezone')

    return {
        "business": {
            "nome": est.nome,
            "telefone": est.telefone,
            "slug": est.slug,
            "email": est.email,
            "idioma_padrao": est.idioma_padrao,
            "timezone": tz_name,
            "lembrete_horas_antes": est.lembrete_horas_antes or [],
            "horario_inicio": est.horario_inicio,
            "horario_fim": est.horario_fim,
            "photos": est.photos or [],
            "reviews": est.reviews or [],
        },
        "services": [
            {
                "id": s.id,
                "name": s.name,
                "duration_min": s.duration_min,
                "buffer_min": s.buffer_min,
                "price_cents": s.price_cents,
                "display_interval_min": s.display_interval_min,
            }
            for s in services
        ],
        "professionals": [
            {
                "id": p.id,
                "name": p.nome,
                "telefone": p.telefone,
            }
            for p in professionals
        ],
    }


@router.get("/trial-status")
def get_trial_status(db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    """Return computed trial status for the establishment.

    Used by the admin UI to show a trial countdown/expired banner.
    Trial state is stored in SetupProfile.payload.trial (JSON).
    """

    est = _get_primary_estabelecimento(db, auth=auth)
    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row and isinstance(setup_row.payload, dict) else {}

    now = datetime.now(timezone.utc)
    status_obj = compute_trial_status(setup_payload, trial_days=TRIAL_DAYS_DEFAULT, now_utc=now)

    seconds_left = None
    days_left = None
    hours_left = None
    if status_obj.end_utc and not status_obj.expired and not status_obj.active_plan:
        try:
            seconds_left = max(0, int((status_obj.end_utc - now).total_seconds()))
            days_left = int(math.ceil(seconds_left / 86400.0))
            hours_left = int(math.ceil(seconds_left / 3600.0))
        except Exception:
            seconds_left = None
            days_left = None
            hours_left = None

    return {
        "ok": True,
        "estabelecimento_id": est.id,
        "slug": est.slug,
        "now_utc": now.isoformat(),
        "trial": {
            "trial_days": TRIAL_DAYS_DEFAULT,
            "active_plan": bool(status_obj.active_plan),
            "started": bool(status_obj.started),
            "expired": bool(status_obj.expired),
            "start_utc": status_obj.start_utc.isoformat() if status_obj.start_utc else None,
            "end_utc": status_obj.end_utc.isoformat() if status_obj.end_utc else None,
            "seconds_left": seconds_left,
            "hours_left": hours_left,
            "days_left": days_left,
        },
    }


class SetupSavePayload(BaseModel):
    """Payload do Setup Inteligente (wizard).

    Guardamos respostas e preferências em JSON para permitir evolução do
    produto sem migrations constantes.
    """

    payload: dict


@router.get("/setup")
def get_setup_profile(db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    est = _get_primary_estabelecimento(db, auth=auth)
    row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    if not row:
        return {"ok": True, "exists": False, "payload": None, "updated_at": None}
    return {
        "ok": True,
        "exists": True,
        "payload": row.payload,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.put("/setup")
def save_setup_profile(data: SetupSavePayload, db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    est = _get_primary_estabelecimento(db, auth=auth)
    row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    if row:
        row.payload = data.payload
    else:
        row = SetupProfile(estabelecimento_id=est.id, payload=data.payload)
        db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "payload": row.payload,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }

class SeedPayload(BaseModel):
    slug: str | None = None


@router.post('/seed-test-data')
def seed_test_data(payload: SeedPayload | None = None, db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    """Cria dados de desenvolvimento (estabelecimento, 2 clientes, 1 invoice).

    Protegido por `check_superadmin` (dev-only). Use para testar E2E de forma determinística.
    """
    slug = (payload.slug if payload and payload.slug else 'dev')
    est = db.query(Estabelecimento).filter(Estabelecimento.slug == slug).first()
    if not est:
        est = Estabelecimento(nome='Dev Estabelecimento', telefone='0000000000', email=f'{slug}@example.local', slug=slug)
        db.add(est)
        db.commit()
        db.refresh(est)

    # create simple services and staff if missing
    svc = db.query(Service).filter(Service.estabelecimento_id == est.id).first()
    if not svc:
        svc = Service(estabelecimento_id=est.id, name='Corte', duration_min=30, price_cents=3000)
        db.add(svc)

    func = db.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).first()
    if not func:
        func = Funcionario(nome='João', telefone='000', estabelecimento_id=est.id)
        db.add(func)

    db.commit()

    # clients
    clients = []
    for i, cdata in enumerate([('Cliente Um','111111111'), ('Cliente Dois','222222222')], start=1):
        existing = db.query(Cliente).filter(Cliente.telefone == cdata[1], Cliente.estabelecimento_id == est.id).first()
        if not existing:
            cl = Cliente(nome=cdata[0], telefone=cdata[1], estabelecimento_id=est.id)
            db.add(cl)
            db.commit()
            db.refresh(cl)
        else:
            cl = existing
        clients.append(cl)

    # invoice for first client
    inv = db.query(Invoice).filter(Invoice.estabelecimento_id == est.id).first()
    if not inv and clients:
        inv = Invoice(estabelecimento_id=est.id, cliente_id=clients[0].id, descricao='Serviço teste', valor_centavos=3000, currency='BRL')
        db.add(inv)
        db.commit()
        db.refresh(inv)

    return {
        'ok': True,
        'estabelecimento': {'id': est.id, 'slug': est.slug},
        'clients': [{'id': c.id, 'nome': c.nome, 'telefone': c.telefone} for c in clients],
        'invoice': {'id': inv.id if inv else None}
    }


class PendingActionPayload(BaseModel):
    tipo: str
    payload: dict
    idempotency_key: str | None = None


@router.post('/pending-actions')
def create_pending_action(data: PendingActionPayload, db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    pa = PendingAction(tipo=data.tipo, payload=data.payload, idempotency_key=data.idempotency_key)
    db.add(pa)
    db.commit()
    db.refresh(pa)
    return {'ok': True, 'pending_action': pa.to_dict()}


@router.get('/pending-actions')
def list_pending_actions(db: Session = Depends(get_db), auth=Depends(check_superadmin)):
    items = db.query(PendingAction).order_by(PendingAction.criado_em.desc()).limit(200).all()
    return {'ok': True, 'items': [i.to_dict() for i in items]}


@router.put("/config")
def save_admin_config(
    payload: AdminConfigPayload,
    db: Session = Depends(get_db),
    auth=Depends(check_superadmin),
):
    """Salva configurações básicas do salão, serviços e equipe.

    Pensado para o botão "Salvar" do card de Configurações no dashboard.

    - Atualiza dados do Estabelecimento principal
    - Atualiza ou cria serviços e profissionais listados no payload

    (Por simplicidade, não removemos registros que não vierem no payload;
    isso evita deletar dados por engano. No futuro podemos adicionar
    um campo `arquivado`/`ativo`.)
    """

    est = _get_primary_estabelecimento(db, auth=auth)

    # Negócio
    est.nome = payload.business.nome
    est.telefone = payload.business.telefone
    est.slug = payload.business.slug
    est.email = payload.business.email
    est.idioma_padrao = payload.business.idioma_padrao or est.idioma_padrao
    est.lembrete_horas_antes = payload.business.lembrete_horas_antes
    if payload.business.horario_inicio is not None:
        est.horario_inicio = payload.business.horario_inicio
    if payload.business.horario_fim is not None:
        est.horario_fim = payload.business.horario_fim
    est.photos = payload.business.photos
    est.reviews = payload.business.reviews

    # Timezone lives in SetupProfile payload (business.timezone) to avoid DB migrations.
    try:
        tz_name = (payload.business.timezone or '').strip() if payload.business.timezone is not None else None
        if tz_name:
            row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
            if row and isinstance(row.payload, dict):
                sp_payload = dict(row.payload)
            else:
                sp_payload = {}
            biz = sp_payload.get('business') if isinstance(sp_payload.get('business'), dict) else {}
            biz = dict(biz)
            biz['timezone'] = tz_name
            sp_payload['business'] = biz
            if row:
                row.payload = sp_payload
            else:
                row = SetupProfile(estabelecimento_id=est.id, payload=sp_payload)
                db.add(row)
    except Exception:
        # Never block admin save due to timezone payload issues
        pass

    # Serviços
    existing_services: dict[int, Service] = {
        s.id: s
        for s in db.query(Service).filter(Service.estabelecimento_id == est.id).all()
    }
    for svc_in in payload.services:
        if svc_in.id and svc_in.id in existing_services:
            svc = existing_services[svc_in.id]
            svc.name = svc_in.name
            svc.duration_min = svc_in.duration_min
            svc.buffer_min = svc_in.buffer_min
            svc.price_cents = svc_in.price_cents
            svc.display_interval_min = svc_in.display_interval_min
        else:
            svc = Service(
                estabelecimento_id=est.id,
                name=svc_in.name,
                duration_min=svc_in.duration_min,
                buffer_min=svc_in.buffer_min,
                price_cents=svc_in.price_cents,
                display_interval_min=svc_in.display_interval_min,
            )
            db.add(svc)

    # Profissionais
    existing_profs: dict[int, Funcionario] = {
        p.id: p
        for p in db.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).all()
    }
    for prof_in in payload.professionals:
        if prof_in.id and prof_in.id in existing_profs:
            prof = existing_profs[prof_in.id]
            prof.nome = prof_in.name
            prof.telefone = prof_in.telefone
        else:
            prof = Funcionario(
                nome=prof_in.name,
                telefone=prof_in.telefone,
                estabelecimento_id=est.id,
            )
            db.add(prof)

    db.commit()

    # Retornamos a configuração atualizada usando o mesmo formato do GET
    return get_admin_config(db=db, auth=auth)
