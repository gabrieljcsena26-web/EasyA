from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Cliente, Invoice, Estabelecimento, SetupProfile
from app.core.security import verify_access_token_dep, security
from app.core.responses import success_response
from app.schemas.schemas import InvoiceCreate
from app.services.notifications_v2 import enqueue_notification
from app.services.payments_stripe import (
    create_checkout_session_for_invoice,
    create_checkout_session_for_subscription,
    create_billing_portal_session,
    is_stripe_configured,
    is_stripe_subscription_configured,
    is_stripe_webhook_configured,
    verify_and_construct_webhook_event,
)



router = APIRouter(prefix="/billing", tags=["billing"])


def _ensure_dict(v):
    # IMPORTANT: SQLAlchemy JSON columns do not track in-place mutations unless using MutableDict.
    # Always copy dicts before mutating so changes are persisted on commit.
    return dict(v) if isinstance(v, dict) else {}


def _get_setup_profile(db: Session, est_id: int) -> SetupProfile:
    sp = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est_id).first()
    if not sp:
        sp = SetupProfile(estabelecimento_id=est_id, payload={})
        db.add(sp)
        db.commit()
        db.refresh(sp)
    return sp


def _set_trial_active_plan(sp: SetupProfile, *, active: bool, reason: str | None = None) -> None:
    payload = _ensure_dict(getattr(sp, "payload", None))
    trial = _ensure_dict(payload.get("trial"))
    trial["active_plan"] = bool(active)
    if reason:
        trial["active_plan_reason"] = str(reason)[:120]
    payload["trial"] = trial
    sp.payload = payload


def _update_billing_payload(
    sp: SetupProfile,
    *,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    subscription_status: str | None = None,
    current_period_end_utc: int | None = None,
) -> None:
    payload = _ensure_dict(getattr(sp, "payload", None))
    billing = _ensure_dict(payload.get("billing"))
    stripe_obj = _ensure_dict(billing.get("stripe"))
    if customer_id is not None:
        stripe_obj["customer_id"] = str(customer_id)
    if subscription_id is not None:
        stripe_obj["subscription_id"] = str(subscription_id)
    if subscription_status is not None:
        stripe_obj["subscription_status"] = str(subscription_status)
    if current_period_end_utc is not None:
        stripe_obj["current_period_end_utc"] = int(current_period_end_utc)
    stripe_obj["updated_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    billing["stripe"] = stripe_obj
    payload["billing"] = billing
    sp.payload = payload


def _compute_plan_active_from_stripe(subscription_status: str | None) -> bool:
    s = str(subscription_status or "").strip().lower()
    # Stripe subscription statuses: active, trialing, past_due, canceled, unpaid, incomplete, incomplete_expired, paused
    return s in ("active", "trialing")


def _find_setup_profile_by_stripe_ids(db: Session, *, customer_id: str | None, subscription_id: str | None) -> SetupProfile | None:
    """Best-effort lookup without relying on JSONB SQL operators (keeps SQLite compatibility)."""
    cust = str(customer_id or "").strip()
    sub = str(subscription_id or "").strip()
    if not cust and not sub:
        return None

    # Webhook volume is low; scan is acceptable and portable.
    rows = db.query(SetupProfile).order_by(SetupProfile.id.desc()).limit(500).all()
    for sp in rows:
        payload = sp.payload if isinstance(sp.payload, dict) else {}
        billing = payload.get("billing") if isinstance(payload.get("billing"), dict) else {}
        stripe_obj = billing.get("stripe") if isinstance(billing.get("stripe"), dict) else {}
        if sub and str(stripe_obj.get("subscription_id") or "") == sub:
            return sp
        if cust and str(stripe_obj.get("customer_id") or "") == cust:
            return sp
    return None

@router.post("/invoices")
def criar_fatura(
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security),
    request: Request = None,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
):
    est_id = user.get("estabelecimento_id")

    # Ensure we always have an idioma for the final response (avoid UnboundLocalError)
    lang = (accept_language or "pt-BR").split(",")[0].strip().lower()

    # normal flow (debug logging removed)

    cliente = (
        db.query(Cliente)
        .filter(Cliente.id == data.cliente_id, Cliente.estabelecimento_id == est_id)
        .first()
    )
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado para este estabelecimento")

    invoice = Invoice(
        estabelecimento_id=est_id,
        cliente_id=cliente.id,
        descricao=data.descricao,
        valor_centavos=data.valor_centavos,
        currency=data.currency or "EUR",
        tipo=data.tipo,
        metodo_pagamento=data.metodo_pagamento,
        origem=data.origem,
        gateway_payment_id=data.gateway_payment_id,
        gateway_status=data.gateway_status,
        status="em_aberto",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # Opcionalmente, criar sessão de pagamento Stripe (quando configurado).
    # Não interrompe o fluxo de criação de fatura se Stripe não estiver disponível.
    stripe_session = None
    try:
        # Carrega estabelecimento para enriquecer metadata, se necessário futuramente
        est = db.query(Estabelecimento).filter(Estabelecimento.id == est_id).first()
        stripe_session = create_checkout_session_for_invoice(
            invoice_id=invoice.id,
            amount_cents=invoice.valor_centavos,
            currency=invoice.currency,
            description=invoice.descricao,
            metadata={
                "estabelecimento_id": str(est_id),
                "cliente_id": str(cliente.id),
            },
        )
        if stripe_session and stripe_session.get("id"):
            invoice.gateway_payment_id = stripe_session["id"]
            invoice.gateway_status = stripe_session.get("status") or "created"
            db.add(invoice)
            db.commit()
            db.refresh(invoice)
    except Exception:
        # Não falhar; Stripe é opcional
        stripe_session = None

    # Enfileira notificação de WhatsApp/SMS opcionalmente (Twilio pode estar desativado)
    try:
        valor = (data.valor_centavos or 0) / 100.0
        lang = (accept_language or "pt-BR").split(",")[0].strip().lower()
        if lang.startswith("en"):
            mensagem = (
                f"Hi {cliente.nome}! Thank you for your visit. "
                f"Amount: {valor:.2f} {invoice.currency}. "
                f"This is a payment confirmation generated by the system."
            )
        elif lang.startswith("es"):
            mensagem = (
                f"Hola {cliente.nome}! Gracias por tu visita. "
                f"Importe: {valor:.2f} {invoice.currency}. "
                f"Este es un comprobante de cobro generado por el sistema."
            )
        else:
            mensagem = (
                f"Olá {cliente.nome}! Obrigado pelo serviço realizado. "
                f"Valor: {valor:.2f} {invoice.currency}. "
                f"Esta é uma confirmação de cobrança gerada no sistema."
            )
        # Se houver link de pagamento Stripe, incluir na mensagem de forma amigável.
        if stripe_session and stripe_session.get("url"):
            link_txt = stripe_session["url"]
            if lang.startswith("en"):
                mensagem += f" You can complete the payment using this link: {link_txt}"
            elif lang.startswith("es"):
                mensagem += f" Puedes completar el pago usando este enlace: {link_txt}"
            else:
                mensagem += f" Você pode completar o pagamento por este link: {link_txt}"
        enqueue_notification(
            canal="whatsapp",
            destinatario=cliente.telefone,
            mensagem=mensagem,
            payload={"invoice_id": invoice.id, "idioma_mensagem": lang},
            idempotency_key=f"invoice:{invoice.id}",
        )
    except Exception:
        # Não falhar a criação da fatura por erro na notificação
        pass

    return success_response(
        data={
            "id": invoice.id,
            "cliente_id": invoice.cliente_id,
            "descricao": invoice.descricao,
            "valor_centavos": invoice.valor_centavos,
            "currency": invoice.currency,
            "tipo": invoice.tipo,
            "metodo_pagamento": invoice.metodo_pagamento,
            "origem": invoice.origem,
            "gateway_payment_id": invoice.gateway_payment_id,
            "gateway_status": invoice.gateway_status,
            "status": invoice.status,
            "idioma_mensagem": lang,
            "stripe": {
                "configured": is_stripe_configured(),
                "checkout_session": stripe_session,
            },
        },
        message="Fatura criada com sucesso",
    )


@router.get("/invoices")
def listar_faturas(
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")

    q = db.query(Invoice).filter(Invoice.estabelecimento_id == est_id)
    if cliente_id is not None:
        q = q.filter(Invoice.cliente_id == cliente_id)

    invoices = q.order_by(Invoice.created_at.desc()).all()

    data = [
        {
            "id": inv.id,
            "cliente_id": inv.cliente_id,
            "descricao": inv.descricao,
            "valor_centavos": inv.valor_centavos,
            "currency": inv.currency,
            "tipo": inv.tipo,
            "metodo_pagamento": inv.metodo_pagamento,
            "origem": inv.origem,
            "gateway_payment_id": inv.gateway_payment_id,
            "gateway_status": inv.gateway_status,
            "status": inv.status,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        }
        for inv in invoices
    ]

    return success_response(data=data, message="Faturas listadas com sucesso")


@router.get("/subscription/status")
def subscription_status(
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security),
):
    est_id = int(user.get("estabelecimento_id"))
    sp = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est_id).first()
    payload = sp.payload if sp and isinstance(sp.payload, dict) else {}
    billing = payload.get("billing") if isinstance(payload.get("billing"), dict) else {}
    stripe_obj = billing.get("stripe") if isinstance(billing.get("stripe"), dict) else {}
    trial = payload.get("trial") if isinstance(payload.get("trial"), dict) else {}

    return success_response(
        data={
            "stripe": {
                "configured": bool(is_stripe_configured()),
                "subscription_configured": bool(is_stripe_subscription_configured()),
                "webhook_configured": bool(is_stripe_webhook_configured()),
                "customer_id": stripe_obj.get("customer_id"),
                "subscription_id": stripe_obj.get("subscription_id"),
                "subscription_status": stripe_obj.get("subscription_status"),
                "current_period_end_utc": stripe_obj.get("current_period_end_utc"),
            },
            "trial": {
                "active_plan": bool(trial.get("active_plan")),
            },
        },
        message="Subscription status",
    )


@router.post("/subscription/checkout")
def create_subscription_checkout(
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security),
):
    if not is_stripe_subscription_configured():
        raise HTTPException(status_code=400, detail="Stripe subscription not configured (missing STRIPE_SUBSCRIPTION_PRICE_ID or STRIPE_SECRET_KEY)")

    est_id = int(user.get("estabelecimento_id"))
    est = db.query(Estabelecimento).filter(Estabelecimento.id == est_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")

    session = create_checkout_session_for_subscription(
        estabelecimento_id=est.id,
        estabelecimento_slug=str(est.slug or ""),
        estabelecimento_name=str(getattr(est, "nome", "") or "") or None,
        customer_email=str(getattr(est, "email", "") or "") or None,
    )
    if not session or not session.get("url"):
        raise HTTPException(status_code=502, detail="Falha ao criar sessão Stripe")

    return success_response(
        data={"checkout_session": session},
        message="Stripe checkout session created",
    )


@router.post("/subscription/portal")
def create_subscription_portal(
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security),
):
    if not is_stripe_configured():
        raise HTTPException(status_code=400, detail="Stripe not configured")

    est_id = int(user.get("estabelecimento_id"))
    sp = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est_id).first()
    payload = sp.payload if sp and isinstance(sp.payload, dict) else {}
    billing = payload.get("billing") if isinstance(payload.get("billing"), dict) else {}
    stripe_obj = billing.get("stripe") if isinstance(billing.get("stripe"), dict) else {}
    customer_id = stripe_obj.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Stripe customer not found for this establishment")

    sess = create_billing_portal_session(customer_id=str(customer_id))
    if not sess or not sess.get("url"):
        raise HTTPException(status_code=502, detail="Falha ao criar portal Stripe")

    return success_response(data={"portal_session": sess}, message="Stripe billing portal session created")


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="stripe-signature"), db: Session = Depends(get_db)):
    # Public endpoint; trust only verified Stripe signatures.
    if not is_stripe_webhook_configured():
        raise HTTPException(status_code=400, detail="Stripe webhook not configured")

    payload = await request.body()
    try:
        event = verify_and_construct_webhook_event(payload=payload, sig_header=stripe_signature)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {type(e).__name__}")

    event_type = str(getattr(event, "type", "") or "")
    obj = getattr(getattr(event, "data", None), "object", None)
    data_obj = obj if isinstance(obj, dict) else getattr(obj, "to_dict", lambda: {})()  # stripe objects
    if not isinstance(data_obj, dict):
        data_obj = {}

    # We persist Stripe IDs/status into SetupProfile.payload and flip trial.active_plan when subscription is active.
    try:
        if event_type == "checkout.session.completed":
            # Session includes subscription + customer.
            est_id = data_obj.get("client_reference_id")
            if est_id:
                est_id_int = int(est_id)
                sp = _get_setup_profile(db, est_id_int)

                customer_id = data_obj.get("customer")
                subscription_id = data_obj.get("subscription")
                _update_billing_payload(sp, customer_id=customer_id, subscription_id=subscription_id)
                # We don't know final subscription status here; will come from subscription.updated.
                db.add(sp)
                db.commit()

        elif event_type in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
            # subscription object
            subscription_id = data_obj.get("id")
            customer_id = data_obj.get("customer")
            status = data_obj.get("status")
            current_period_end = data_obj.get("current_period_end")

            # Resolve establishment primarily via metadata (portable, reliable).
            md = data_obj.get("metadata") if isinstance(data_obj.get("metadata"), dict) else {}
            est_id = md.get("estabelecimento_id") if isinstance(md, dict) else None
            sp = None
            if est_id:
                try:
                    sp = _get_setup_profile(db, int(est_id))
                except Exception:
                    sp = None
            if sp is None:
                sp = _find_setup_profile_by_stripe_ids(
                    db,
                    customer_id=str(customer_id) if customer_id else None,
                    subscription_id=str(subscription_id) if subscription_id else None,
                )

            if sp is not None:
                _update_billing_payload(
                    sp,
                    customer_id=str(customer_id) if customer_id else None,
                    subscription_id=str(subscription_id) if subscription_id else None,
                    subscription_status=str(status) if status else None,
                    current_period_end_utc=int(current_period_end) if current_period_end else None,
                )
                _set_trial_active_plan(sp, active=_compute_plan_active_from_stripe(status), reason=f"stripe:{status}")
                db.add(sp)
                db.commit()

        elif event_type in ("invoice.paid", "invoice.payment_failed"):
            # Optional: persist last invoice status for debugging.
            customer_id = data_obj.get("customer")
            subscription_id = data_obj.get("subscription")
            md = data_obj.get("metadata") if isinstance(data_obj.get("metadata"), dict) else {}
            est_id = md.get("estabelecimento_id") if isinstance(md, dict) else None
            sp = None
            if est_id:
                try:
                    sp = _get_setup_profile(db, int(est_id))
                except Exception:
                    sp = None
            if sp is None:
                sp = _find_setup_profile_by_stripe_ids(
                    db,
                    customer_id=str(customer_id) if customer_id else None,
                    subscription_id=str(subscription_id) if subscription_id else None,
                )
            if sp is not None:
                payload_sp = _ensure_dict(sp.payload)
                billing = _ensure_dict(payload_sp.get("billing"))
                stripe_obj = _ensure_dict(billing.get("stripe"))
                stripe_obj["last_invoice_event"] = {
                    "type": event_type,
                    "at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                }
                billing["stripe"] = stripe_obj
                payload_sp["billing"] = billing
                sp.payload = payload_sp
                db.add(sp)
                db.commit()
    except Exception:
        # Never fail webhook: Stripe will retry; keep response 200 to avoid retry storms.
        pass

    return {"ok": True}
