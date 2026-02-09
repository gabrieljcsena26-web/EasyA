from fastapi import FastAPI, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import create_access_token
from app.models.models import Estabelecimento
import os
import logging
import threading
import time
import uuid
# import sentry_sdk
# from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
# from sentry_sdk.integrations.logging import LoggingIntegration

from app.api.auth.routes import router as auth_router
from app.api.dashboard.routes import router as dashboard_router
from app.api.billing.routes import router as billing_router
from app.api.admin.routes import router as admin_router
from app.api.admin.import_routes import router as admin_import_router
from app.api.notifications.routes import router as notifications_router
from app.api.sync.routes import router as sync_router
from app.api.interesses.routes import router as interesses_router
from app.api.agent.routes import router as agent_router
from app.api.booking.routes import router as booking_router
from app.api.whatsapp.routes import router as whatsapp_router


def _is_production() -> bool:
    env = str(os.getenv("ENV", "development") or "").strip().lower()
    return env in ("prod", "production")


def _cors_origins_from_env() -> list[str]:
    """Return a safe list of allowed CORS origins.

    In production, avoid wildcard origins.
    """
    raw = str(os.getenv("FRONTEND_URLS", "") or "").strip()
    origins: list[str] = []

    if raw:
        for part in raw.split(","):
            o = str(part or "").strip().rstrip("/")
            if o:
                origins.append(o)

    # Common single-url env vars fallbacks
    for key in ("FRONTEND_BASE_URL", "BOOKING_PUBLIC_BASE_URL", "PUBLIC_BASE_URL"):
        v = str(os.getenv(key, "") or "").strip().rstrip("/")
        if v and v not in origins:
            origins.append(v)

    # Dev convenience: even when FRONTEND_URLS is set (e.g. docker-compose),
    # allow common local dev ports so the dashboard can run on Vite.
    if not _is_production():
        for o in (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ):
            if o not in origins:
                origins.append(o)

    if not origins and not _is_production():
        return ["*"]

    return origins


def _cors_origin_regex_from_env() -> str | None:
    """Optional regex for allowed CORS origins.

    Useful for Cloudflare Pages previews where the origin is a dynamic subdomain.
    Keep this opt-in in production.

    Env vars:
      - CORS_ALLOW_ORIGIN_REGEX: explicit regex
      - ENABLE_PAGES_DEV_CORS: when true, allow https://*.app-easy-agenda.pages.dev
    """
    raw = str(os.getenv("CORS_ALLOW_ORIGIN_REGEX", "") or "").strip()
    if raw:
        return raw

    enable_pages = str(os.getenv("ENABLE_PAGES_DEV_CORS", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if enable_pages:
        return r"^https:\/\/([a-z0-9-]+\.)?app-easy-agenda\.pages\.dev$"

    return None


def _before_send(event, hint):
    # sanitize PII: remove raw message bodies and mask phone numbers if present
    try:
        if 'extra' in event:
            extra = event['extra']
            if isinstance(extra, dict):
                extra.pop('mensagem_raw', None)
                if 'destinatario' in extra and isinstance(extra['destinatario'], str):
                    d = extra['destinatario']
                    # mask all but last 4 chars
                    extra['destinatario'] = (d[:6] + '****') if len(d) > 6 else '****'
    except Exception:
        pass
    return event


# SENTRY_DSN = os.getenv('SENTRY_DSN')
# if SENTRY_DSN:
#     logging_integration = LoggingIntegration(level=None, event_level=None)
#     sentry_sdk.init(
#         dsn=SENTRY_DSN,
#         integrations=[logging_integration],
#         environment=os.getenv('ENV', 'development'),
#         traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.05')),
#         before_send=_before_send,
#     )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Proteções básicas contra clickjacking, MIME sniffing e rastreamento excessivo
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Evita indexação de endpoints de API por robôs de busca
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path in ("/healthz", "/readyz"):
            return await call_next(request)

        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logging.getLogger("easya.request").exception(
                "request_error method=%s path=%s duration_ms=%s request_id=%s",
                request.method,
                path,
                duration_ms,
                request_id,
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers.setdefault("X-Request-Id", request_id)
        logging.getLogger("easya.request").info(
            "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response


log_level = str(os.getenv("LOG_LEVEL", "INFO") or "INFO").strip().upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log only structured validation errors (avoid logging request bodies/PII).
    logging.getLogger("easya.validation").warning(
        "validation_error method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# CORS middleware for frontend
# Em desenvolvimento, liberamos todas as origens para facilitar testes
# (file://, localhost em portas diferentes, etc.).
cors_origins = _cors_origins_from_env()

cors_origin_regex = _cors_origin_regex_from_env()

cors_kwargs = dict(
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if cors_origin_regex:
    cors_kwargs["allow_origin_regex"] = cors_origin_regex

app.add_middleware(CORSMiddleware, **cors_kwargs)

# Optional host header allowlist (recommended in production)
# Example: ALLOWED_HOSTS=api.easy-agenda.com,localhost,127.0.0.1
allowed_hosts_raw = str(os.getenv("ALLOWED_HOSTS", "") or "").strip()
if allowed_hosts_raw:
    allowed_hosts = [h.strip() for h in allowed_hosts_raw.split(",") if h.strip()]
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Cabeçalhos de segurança em todas as respostas
app.add_middleware(SecurityHeadersMiddleware)

# Logging mínimo de requests (sem payload/PII)
app.add_middleware(RequestLoggingMiddleware)

# Incluir routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(admin_import_router)
app.include_router(notifications_router)
app.include_router(sync_router)
app.include_router(interesses_router)
app.include_router(agent_router)
app.include_router(booking_router)
app.include_router(whatsapp_router)

# Ensure DB tables exist (development convenience)
from app.db.database import engine, Base
import app.models.models as _models  # register models

if not _is_production() and os.getenv("AUTO_CREATE_DB", "true").lower() in ("1", "true", "yes"):
    Base.metadata.create_all(bind=engine)


def _ensure_dev_migrations():
    """Aplicar pequenas migrações automáticas em ambiente de desenvolvimento.

    Evita erros como "no such column" quando adicionamos campos novos aos modelos.
    """
    try:
        with engine.connect() as conn:
            # Garantir colunas de autenticação em estabelecimentos
            res = conn.execute(text("PRAGMA table_info(estabelecimentos);"))
            cols = [row[1] for row in res]
            if "senha_hash" not in cols:
                conn.execute(text("ALTER TABLE estabelecimentos ADD COLUMN senha_hash VARCHAR;"))
            if "reset_token_hash" not in cols:
                conn.execute(text("ALTER TABLE estabelecimentos ADD COLUMN reset_token_hash VARCHAR;"))
            if "reset_token_expires_at" not in cols:
                conn.execute(text("ALTER TABLE estabelecimentos ADD COLUMN reset_token_expires_at DATETIME;"))
            if "email" not in cols:
                conn.execute(text("ALTER TABLE estabelecimentos ADD COLUMN email VARCHAR;"))

            # Garantir colunas extras em notificacoes para idempotência/retries
            res_notif = conn.execute(text("PRAGMA table_info(notificacoes);"))
            notif_cols = [row[1] for row in res_notif]
            if "idempotency_key" not in notif_cols:
                conn.execute(text("ALTER TABLE notificacoes ADD COLUMN idempotency_key VARCHAR;"))
            if "attempts" not in notif_cols:
                conn.execute(text("ALTER TABLE notificacoes ADD COLUMN attempts INTEGER;"))
            if "max_attempts" not in notif_cols:
                conn.execute(text("ALTER TABLE notificacoes ADD COLUMN max_attempts INTEGER;"))
            if "last_error" not in notif_cols:
                conn.execute(text("ALTER TABLE notificacoes ADD COLUMN last_error TEXT;"))
            if "next_attempt_at" not in notif_cols:
                conn.execute(text("ALTER TABLE notificacoes ADD COLUMN next_attempt_at DATETIME;"))

            # Garantir colunas extras em invoices para faturamento mais rico/estruturado
            try:
                res_inv = conn.execute(text("PRAGMA table_info(invoices);"))
                inv_cols = [row[1] for row in res_inv]
                if "tipo" not in inv_cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN tipo VARCHAR;"))
                if "metodo_pagamento" not in inv_cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN metodo_pagamento VARCHAR;"))
                if "origem" not in inv_cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN origem VARCHAR;"))
                if "gateway_payment_id" not in inv_cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN gateway_payment_id VARCHAR;"))
                if "gateway_status" not in inv_cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN gateway_status VARCHAR;"))
            except Exception:
                # se a tabela não existir ainda ou outro erro, deixamos para o create_all padrão
                pass

            # Garantir coluna de service_id em agendamentos para vincular serviços
            try:
                res_ag = conn.execute(text("PRAGMA table_info(agendamentos);"))
                ag_cols = [row[1] for row in res_ag]
                if "service_id" not in ag_cols:
                    conn.execute(text("ALTER TABLE agendamentos ADD COLUMN service_id INTEGER;"))
            except Exception:
                # Se a tabela não existir ainda, será criada pelo create_all
                pass
    except Exception:
        # Em produção, usar ferramenta de migração apropriada (Alembic)
        pass


if not _is_production() and os.getenv("AUTO_DEV_MIGRATIONS", "true").lower() in ("1", "true", "yes"):
    _ensure_dev_migrations()


def _inline_workers_enabled() -> bool:
    """Inline workers are useful in dev, but dangerous with multi-worker uvicorn.

    - Dev default: enabled (can disable via DISABLE_NOTIFICATIONS_WORKER)
    - Prod default: disabled (opt-in via ENABLE_INLINE_WORKERS=true)
    """
    if _is_production():
        return str(os.getenv("ENABLE_INLINE_WORKERS", "false") or "").lower() in ("1", "true", "yes")
    return str(os.getenv("ENABLE_INLINE_WORKERS", "true") or "").lower() in ("1", "true", "yes")


def _start_inline_workers():
    """Start a lightweight background loop to process pending notifications/actions.

    Prefer Celery/beat in real production. This mode is best for single-process deploys.
    """

    def _loop():
        time.sleep(5)
        while True:
            try:
                from app.services.notifications_v2 import process_pending_notifications
                from app.services.pending_actions import process_pending_actions

                process_pending_notifications(limit=100)
                process_pending_actions(limit=50)
            except Exception:
                pass
            time.sleep(60)

    t = threading.Thread(target=_loop, name="inline-workers", daemon=True)
    t.start()


@app.on_event("startup")
def _on_startup_inline_workers():
    disable_worker = str(os.getenv("DISABLE_NOTIFICATIONS_WORKER", "") or "").lower() in ("1", "true", "yes")
    running_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    if disable_worker or running_pytest:
        return
    if not _inline_workers_enabled():
        return

    try:
        _start_inline_workers()
    except Exception:
        logging.getLogger("easya.startup").exception("failed to start inline workers")

# Add Sentry ASGI middleware if configured
# if SENTRY_DSN:
#     app.add_middleware(SentryAsgiMiddleware)


# Endpoint de teste
@app.get("/ping")
def ping():
    return {"status": "ok", "message": "EasyAI backend rodando"}


@app.get("/healthz")
def healthz():
    """Public health endpoint (safe for load balancers/uptime monitors)."""
    from app.db.database import engine as _engine

    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "db_ok": True}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"ok": False, "db_ok": False, "error": str(e)})


@app.get("/readyz")
def readyz():
    """Readiness check: currently same as healthz (DB connectivity)."""
    return healthz()


# Temporary wrapper: expose a simple dev-login route on the running app
# This ensures a dev-login is available even if the auth router isn't registering
# (useful during reloads or environment mismatches). Remove when not needed.
if not _is_production():

    @app.post('/auth/dev-login')
    def dev_login_wrapper(slug: str | None = None, db: Session = Depends(get_db)):
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


# Quick wrapper to call admin.seed_test_data directly when Authorization headers
# or router registration aren't available for any reason. This is a temporary helper
# for local dev only.
if not _is_production():

    @app.post('/admin/seed-test-data')
    def admin_seed_wrapper(payload: dict | None = None, db: Session = Depends(get_db)):
        try:
            from app.api.admin import routes as admin_routes

            # call the function directly, providing a minimal auth dict
            return admin_routes.seed_test_data(payload, db=db, auth={'slug': 'dev', 'estabelecimento_id': 0})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"seed wrapper failed: {type(e).__name__}: {e}")


# (Removed temporary debug endpoint `/__routes`)
