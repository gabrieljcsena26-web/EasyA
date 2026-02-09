"""WhatsApp Webhook Router"""
from fastapi import APIRouter, Request, HTTPException
from app.services.whatsapp_meta import WhatsAppMetaService

router = APIRouter()

@router.get("/webhook")
async def verify_webhook(request: Request):
    """Verify WhatsApp webhook."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Forbidden")

@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Receive WhatsApp status updates."""
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    
    if not WhatsAppMetaService.verify_webhook(signature, body):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    data = await request.json()
    # Process webhook
    return {"status": "received"}