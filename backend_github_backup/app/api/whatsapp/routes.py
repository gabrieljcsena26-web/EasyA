from __future__ import annotations

import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Estabelecimento, SetupProfile

try:
    from twilio.twiml.messaging_response import MessagingResponse
except Exception:  # pragma: no cover
    MessagingResponse = None


router = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
)


def _normalize_whatsapp_number(v: Optional[str]) -> str:
    """Normaliza números no formato Twilio WhatsApp.

    Exemplos de entrada:
    - "whatsapp:+5511999999999"
    - "+55 11 99999-9999"

    Saída: "+5511999999999" (quando possível)
    """
    if not v:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    if s.lower().startswith("whatsapp:"):
        s = s.split(":", 1)[1].strip()
    # keep leading + if present, remove all other non-digits
    has_plus = s.startswith("+")
    digits = re.sub(r"\D+", "", s)
    if not digits:
        return ""
    return ("+" if has_plus else "") + digits


def _booking_base_url() -> str:
    base = (
        os.getenv("BOOKING_PUBLIC_BASE_URL")
        or os.getenv("FRONTEND_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or "http://localhost:3002"
    )
    base = str(base).strip().rstrip("/")
    return base or "http://localhost:3002"


def _booking_link_for_slug(slug: str) -> str:
    return f"{_booking_base_url()}/booking/{slug}"


def _find_est_by_inbound_to(db: Session, to_number: str) -> Optional[Estabelecimento]:
    """Resolve estabelecimento pelo número "To" do WhatsApp.

    Prioriza SetupProfile.payload.business.whatsapp_booking quando existir.
    Faz fallback para Estabelecimento.telefone.

    Observação: isso pressupõe que cada cliente tem um número único.
    """
    to_norm = _normalize_whatsapp_number(to_number)
    if not to_norm:
        return None

    # 1) SetupProfile mapping
    try:
        rows = (
            db.query(SetupProfile)
            .join(Estabelecimento, Estabelecimento.id == SetupProfile.estabelecimento_id)
            .all()
        )
        for row in rows:
            payload = row.payload if isinstance(row.payload, dict) else None
            biz = payload.get("business") if isinstance(payload, dict) else None
            wb = biz.get("whatsapp_booking") if isinstance(biz, dict) else None
            if _normalize_whatsapp_number(wb) == to_norm:
                return row.estabelecimento
    except Exception:
        pass

    # 2) Fallback: match by Estabelecimento.telefone
    try:
        for est in db.query(Estabelecimento).all():
            if _normalize_whatsapp_number(est.telefone) == to_norm:
                return est
    except Exception:
        return None

    return None


@router.post("/incoming")
async def whatsapp_incoming(
    request: Request,
    db: Session = Depends(get_db),
    slug: Optional[str] = Query(default=None, description="Override slug (dev/testing)."),
    Body: str = Form(default=""),
    From: str = Form(default=""),  # Twilio uses capitalized keys
    To: str = Form(default=""),
    ProfileName: str = Form(default=""),
):
    """Webhook de entrada do Twilio WhatsApp.

    - Responde com uma mensagem imediata contendo greeting + link de agendamento.
    - Em produção, recomenda-se validar assinatura do Twilio.

    Docs Twilio: envia application/x-www-form-urlencoded.
    """

    if MessagingResponse is None:
        raise HTTPException(status_code=500, detail="twilio package not available")

    use_slug = (slug or "").strip()
    est: Optional[Estabelecimento] = None

    if use_slug:
        est = db.query(Estabelecimento).filter(Estabelecimento.slug == use_slug).first()
        if not est:
            raise HTTPException(status_code=404, detail="Slug não encontrado")
    else:
        est = _find_est_by_inbound_to(db, To)

    if not est:
        # fallback: no mapping found; still reply with a generic message
        resp = MessagingResponse()
        resp.message(
            "Olá! Para agendar, acesse: "
            + f"{_booking_base_url()}/booking"
            + "\n\nSe você já tem um link do seu salão, use o link específico (com o slug)."
        )
        return str(resp)

    booking_link = _booking_link_for_slug(est.slug)
    name = str(ProfileName or "").strip()

    greeting = "Olá" + (f", {name}" if name else "") + "!"

    text = (
        f"{greeting}\n"
        f"Para agendar online, use este link:\n{booking_link}\n\n"
        "Se preferir, me diga: serviço + melhor dia/horário."
    )

    # Optional: attach assistant output (disabled by default; requires legacy assistant config)
    if os.getenv("WHATSAPP_USE_ASSISTANT", "").lower() in ("1", "true", "yes"):
        try:
            from assistant_service import conversar_com_assistente

            ai_text, _thread_id = conversar_com_assistente(
                slug=est.slug,
                mensagem=str(Body or "").strip() or "Cliente iniciou contato no WhatsApp.",
            )
            ai_text = str(ai_text or "").strip()
            if ai_text:
                text = text + "\n\n" + ai_text
        except Exception:
            # never fail the webhook for assistant errors
            pass

    resp = MessagingResponse()
    resp.message(text)
    return str(resp)
