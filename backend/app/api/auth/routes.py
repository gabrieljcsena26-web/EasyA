from fastapi import APIRouter, HTTPException, Depends, Body, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from app.core.security import (
    create_access_token,
    verify_access_token,
    security,
    get_password_hash,
    verify_password,
    upgrade_password_hash_if_needed,
)
from app.services.notifications_v2 import enqueue_notification
from app.db.database import engine
from datetime import datetime, timedelta, timezone
import secrets
import time
import os


_LOGIN_ATTEMPTS: dict[str, list[float]] = {}


def _is_production() -> bool:
    env = str(os.getenv("ENV", "development") or "").strip().lower()
    return env in ("prod", "production")


def _rate_limit_login(client_ip: str, max_attempts: int = 5, window_seconds: int = 300):
    """Limita tentativas de login por IP em janela deslizante.

    Em produção, idealmente usar Redis ou outro backend compartilhado.
    """
    if not client_ip:
            return
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(client_ip, [])
    # remove tentativas fora da janela
    attempts = [ts for ts in attempts if now - ts <= window_seconds]
    if len(attempts) >= max_attempts:
            raise HTTPException(status_code=429, detail="Muitas tentativas de login. Tente novamente em alguns minutos.")
    attempts.append(now)
    _LOGIN_ATTEMPTS[client_ip] = attempts
from app.db.database import get_db
from app.models.models import Estabelecimento

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginInput(BaseModel):
    username: str  # pode ser slug ou e-mail
    password: str


class RegisterInput(BaseModel):
    nome: str
    telefone: str
    slug: str
    email: str | None = None
    password: str | None = None


class ForgotPasswordInput(BaseModel):
    identifier: str  # slug ou e-mail


class ResetPasswordInput(BaseModel):
    identifier: str  # slug ou e-mail
    code: str
    new_password: str


class TestEmailInput(BaseModel):
    email: str


class TokenOut(BaseModel):
    token: str


class UserOut(BaseModel):
    username: str
    slug: str
    nome: str | None = None
    telefone: str | None = None
    email: str | None = None


@router.post("/login")
def login(data: LoginInput, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else ""
    _rate_limit_login(client_ip)

    # Demo login: only allowed outside production
    if not _is_production() and data.username == "admin" and data.password == "123":
        token = create_access_token({"username": data.username, "slug": "demo", "estabelecimento_id": 0})
        return {"token": token, "user": {"username": data.username, "slug": "demo"}}

    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.slug == data.username).first()
    if not estabelecimento and data.username:
        estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.email == data.username).first()
    if not estabelecimento:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

    # If no password is set, block in production (force reset flow).
    if not estabelecimento.senha_hash:
        if _is_production():
            raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
        # Local/demo compatibility: allow password '123'
        if data.password != "123":
            raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    else:
        if not verify_password(data.password, estabelecimento.senha_hash):
            raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

        # If this was a legacy hash, upgrade it transparently.
        try:
            upgraded = upgrade_password_hash_if_needed(data.password, estabelecimento.senha_hash)
            if upgraded and upgraded != estabelecimento.senha_hash:
                estabelecimento.senha_hash = upgraded
                db.add(estabelecimento)
                db.commit()
        except Exception:
            pass

    token = create_access_token({
        "username": estabelecimento.slug,
        "slug": estabelecimento.slug,
        "estabelecimento_id": estabelecimento.id,
    })
    return {
        "token": token,
        "user": {
            "username": estabelecimento.slug,
            "slug": estabelecimento.slug,
            "nome": estabelecimento.nome,
            "telefone": estabelecimento.telefone,
            "email": getattr(estabelecimento, "email", None),
        },
    }


@router.post("/register")
def register(data: RegisterInput, db: Session = Depends(get_db)):
    if _is_production():
        if not data.password or len(str(data.password)) < 8:
            raise HTTPException(status_code=400, detail="Senha obrigatória (mínimo 8 caracteres)")
    existing = db.query(Estabelecimento).filter(Estabelecimento.slug == data.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug já existe")

    if data.email:
        email_exists = db.query(Estabelecimento).filter(Estabelecimento.email == data.email).first()
        if email_exists:
            raise HTTPException(status_code=400, detail="E-mail já está em uso")

    senha_hash = get_password_hash(data.password) if data.password else None

    estabelecimento = Estabelecimento(
        nome=data.nome,
        telefone=data.telefone,
        email=data.email,
        slug=data.slug,
        idioma_padrao='pt-BR',
        senha_hash=senha_hash,
    )
    db.add(estabelecimento)

    try:
        db.commit()
    except OperationalError as e:
        # Corrige rapidamente se a coluna email ainda não existir (ambiente legado)
        if 'no such column: estabelecimentos.email' in str(e).lower():
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE estabelecimentos ADD COLUMN email VARCHAR;"))
            db.rollback()
            db.add(estabelecimento)
            db.commit()
        else:
            raise

    db.refresh(estabelecimento)

    # Envia e-mail de boas-vindas / confirmação (fila interna)
    if data.email:
        try:
            welcome_msg = (
                f"Bem-vindo(a) ao EasyAgenda, {data.nome}!\n\n"
                f"Sua conta está ativa. Use seu usuário (slug): {data.slug} ou este e-mail para entrar.\n"
                f"Guarde esta mensagem para referência."
            )
            enqueue_notification(
                canal="email",
                destinatario=data.email,
                mensagem=welcome_msg,
                payload={"motivo": "welcome", "slug": data.slug},
                idempotency_key=f"welcome-email:{data.slug}"
            )
        except Exception:
            pass

    token = create_access_token({
        "username": estabelecimento.slug,
        "slug": estabelecimento.slug,
        "estabelecimento_id": estabelecimento.id,
    })

    return {"token": token, "user": {"username": estabelecimento.slug, "slug": estabelecimento.slug, "nome": estabelecimento.nome}}


@router.get("/me")
def me(token: str = Depends(security), db: Session = Depends(get_db)):
    payload = verify_access_token(token.credentials)
    slug = payload.get("slug")
    estabelecimento = db.query(Estabelecimento).filter(Estabelecimento.slug == slug).first()
    if estabelecimento:
        return {
            "username": estabelecimento.slug,
            "slug": estabelecimento.slug,
            "nome": estabelecimento.nome,
            "telefone": estabelecimento.telefone,
            "email": getattr(estabelecimento, "email", None),
            "idioma_padrao": estabelecimento.idioma_padrao,
        }

    return {"username": payload.get("username"), "slug": slug, "nome": "Demo User"}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordInput, db: Session = Depends(get_db)):
    """Dispara código de redefinição de senha via WhatsApp e e-mail.

    Sempre retorna mensagem genérica para não expor se o slug existe ou não.
    """
    est = db.query(Estabelecimento).filter(Estabelecimento.slug == data.identifier).first()
    if not est and data.identifier:
        est = db.query(Estabelecimento).filter(Estabelecimento.email == data.identifier).first()
    estabelecimento = est
    debug_code: str | None = None
    if estabelecimento:
        # Gerar código de 6 dígitos e armazenar hash com expiração curta
        code = f"{secrets.randbelow(1_000_000):06d}"
        estabelecimento.reset_token_hash = get_password_hash(code)
        estabelecimento.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.add(estabelecimento)
        db.commit()

        if os.getenv("MOCK_NOTIFICATIONS", "false").lower() in ("1", "true", "yes") or os.getenv(
            "RETURN_RESET_CODE", "false"
        ).lower() in ("1", "true", "yes"):
            debug_code = code

        # Tentar enfileirar notificação para o telefone cadastrado (WhatsApp)
        try:
            msg = (
                f"Seu código para redefinir a senha do EasyAgenda é: {code}. "
                f"Ele expira em 30 minutos."
            )
            enqueue_notification(
                canal="whatsapp",
                destinatario=estabelecimento.telefone,
                mensagem=msg,
                payload={"motivo": "reset_password", "slug": estabelecimento.slug},
                idempotency_key=f"reset:{estabelecimento.id}:{int(estabelecimento.reset_token_expires_at.timestamp())}",
            )
        except Exception:
            # Não falhar fluxo de esqueci senha se notificação der erro
            pass

        # Enviar também por e-mail, se houver e-mail cadastrado
        if getattr(estabelecimento, "email", None):
            try:
                email_msg = (
                    f"Olá,\n\n"
                    f"Seu código para redefinir a senha do EasyAgenda é: {code}. "
                    f"Ele expira em 30 minutos.\n\n"
                    f"Se não foi você que solicitou, ignore esta mensagem."
                )
                enqueue_notification(
                    canal="email",
                    destinatario=estabelecimento.email,
                    mensagem=email_msg,
                    payload={"motivo": "reset_password", "slug": estabelecimento.slug},
                    idempotency_key=f"reset-email:{estabelecimento.id}:{int(estabelecimento.reset_token_expires_at.timestamp())}",
                )
            except Exception:
                pass

    resp = {"detail": "Se o usuário existir, um código foi enviado para os contatos cadastrados (WhatsApp/e-mail)."}
    if debug_code:
        resp["debug_code"] = debug_code
    return resp


@router.post("/reset-password")
def reset_password(data: ResetPasswordInput, db: Session = Depends(get_db)):
    if not data.new_password or len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 6 caracteres")

    est = db.query(Estabelecimento).filter(Estabelecimento.slug == data.identifier).first()
    if not est and data.identifier:
        est = db.query(Estabelecimento).filter(Estabelecimento.email == data.identifier).first()
    estabelecimento = est
    if not estabelecimento or not estabelecimento.reset_token_hash or not estabelecimento.reset_token_expires_at:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado")

    if datetime.now(timezone.utc) > estabelecimento.reset_token_expires_at:
        estabelecimento.reset_token_hash = None
        estabelecimento.reset_token_expires_at = None
        db.add(estabelecimento)
        db.commit()
        raise HTTPException(status_code=400, detail="Código inválido ou expirado")

    if not verify_password(data.code, estabelecimento.reset_token_hash):
        raise HTTPException(status_code=400, detail="Código inválido ou expirado")

    # Atualiza senha e limpa token
    estabelecimento.senha_hash = get_password_hash(data.new_password)
    estabelecimento.reset_token_hash = None
    estabelecimento.reset_token_expires_at = None
    db.add(estabelecimento)
    db.commit()

    return {"detail": "Senha redefinida com sucesso. Você já pode fazer login com a nova senha."}


if not _is_production():

    @router.post("/send-test-email")
    def send_test_email(data: TestEmailInput | None = None, email: str | None = None, db: Session = Depends(get_db)):
        """Enfileira um e-mail de teste para validar SMTP (dev only)."""
        target = (data.email if data else None) or email
        if not target:
            raise HTTPException(status_code=400, detail="E-mail obrigatório")
        try:
            enqueue_notification(
                canal="email",
                destinatario=target,
                mensagem="Teste de e-mail do EasyAgenda. Se você recebeu, o SMTP está funcionando.",
                payload={"motivo": "test_email", "subject": "Teste EasyAgenda"},
                idempotency_key=f"test-email:{target}",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Falha ao enfileirar e-mail: {e}")
        return {"detail": "E-mail de teste enfileirado"}

    @router.post('/dev-login')
    def dev_login(slug: str | None = None, db: Session = Depends(get_db)):
        """Dev-only endpoint: return a stable JWT for a test establishment."""
        if os.getenv('ENABLE_DEV_LOGIN', 'true').lower() in ('0', 'false', 'no'):
            raise HTTPException(status_code=403, detail='Dev login disabled')

        use_slug = slug or os.getenv('DEV_SLUG', 'dev')
        est = db.query(Estabelecimento).filter(Estabelecimento.slug == use_slug).first()
        if not est:
            est = Estabelecimento(
                nome=f'Dev {use_slug}',
                telefone='0000000000',
                email=f'{use_slug}@example.local',
                slug=use_slug,
                idioma_padrao='pt-BR',
            )
            db.add(est)
            db.commit()
            db.refresh(est)

        token = create_access_token({
            'username': est.slug,
            'slug': est.slug,
            'estabelecimento_id': est.id,
        })

        return {'token': token, 'user': {'username': est.slug, 'slug': est.slug, 'nome': est.nome}}
