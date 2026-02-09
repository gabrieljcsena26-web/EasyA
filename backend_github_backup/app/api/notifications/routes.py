from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import os

from app.db.database import get_db
from app.models.models import Notificacao, Agendamento, Cliente
from app.services.scheduler import processar_resposta_agendamento

from twilio.request_validator import RequestValidator

router = APIRouter(prefix="/notifications", tags=["notifications"])
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

@router.get("", response_model=list)
def list_notifications(limit: int = 100, db: Session = Depends(get_db)):
    qs = db.query(Notificacao).order_by(Notificacao.criado_em.desc()).limit(limit).all()
    return qs

@router.post("/webhook/twilio")
async def twilio_webhook(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    data = dict(form)
    
    # Validate Twilio signature if token is set
    if TWILIO_AUTH_TOKEN:
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        if not validator.validate(url, dict(form), signature):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")
    
    sid = data.get("MessageSid") or data.get("SmsSid")
    status_tw = data.get("MessageStatus") or data.get("SmsStatus")
    to = data.get("To")
    from_ = data.get("From")
    
    # Map Twilio statuses to internal statuses
    mapping = {
        "queued": "queued",
        "sending": "sent",
        "sent": "sent",
        "delivered": "delivered",
        "failed": "failed",
        "undelivered": "failed"
    }
    mapped = mapping.get(status_tw, status_tw)
    
    if not sid:
        return {"ok": False, "reason": "no sid"}
    
    # Find notification by provider_id
    notif = db.query(Notificacao).filter(Notificacao.provider_id == sid).first()
    
    # Fallback: match by destinatario (best effort)
    if not notif:
        notif = db.query(Notificacao).filter(Notificacao.destinatario == to).order_by(Notificacao.criado_em.desc()).first()
    
    if not notif:
        return {"ok": True, "updated": False}
    
    # Update status and provider_response
    notif.status = mapped
    pr = notif.provider_response or {}
    pr.update({"sid": sid, "status": status_tw, "to": to, "from": from_})
    notif.provider_response = pr
    db.add(notif)
    db.commit()

    return {"ok": True, "updated": True, "status": mapped}


# Endpoint para processar resposta do cliente (ex: cancelar com '1')
@router.post("/processar_resposta")
def processar_resposta(
    agendamento_id: int,
    resposta: str,
    db: Session = Depends(get_db),
):
    agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    if not agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    status_new = processar_resposta_agendamento(resposta, agendamento, db)
    if status_new:
        return {"ok": True, "status": status_new}
    return {"ok": True, "status": agendamento.status, "ignored": True}
