"""WhatsApp Meta Cloud API Service - EPIC LEVEL."""
import logging
import hmac
import hashlib
from typing import Dict, Optional
import aiohttp
from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppMetaService:
    """WhatsApp Business Cloud API integration."""
    
    BASE_URL = "https://graph.facebook.com"
    
    @classmethod
    def _get_url(cls, endpoint: str) -> str:
        """Get full API URL."""
        return f"{cls.BASE_URL}/{settings.WHATSAPP_API_VERSION}/{endpoint}"
    
    @classmethod
    async def send_message(
        cls,
        to: str,
        message: str,
        appointment_id: Optional[str] = None
    ) -> Dict:
        """Send WhatsApp message via Meta Cloud API.
        
        Args:
            to: Phone number in format +1234567890
            message: Message text
            appointment_id: Optional appointment ID for tracking
            
        Returns:
            Dict with message_id and status
        """
        if not settings.WHATSAPP_ACCESS_TOKEN:
            logger.warning("WhatsApp not configured, skipping send")
            return {"status": "skipped", "reason": "not_configured"}
        
        url = cls._get_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages")
        
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to.replace("+", "").replace(" ", ""),
            "type": "text",
            "text": {
                "body": message
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"WhatsApp send failed: {response.status} - {error_text}")
                        return {
                            "status": "error",
                            "error": error_text,
                            "status_code": response.status
                        }
                    
                    data = await response.json()
                    message_id = data.get("messages", [{}])[0].get("id")
                    
                    logger.info(f"WhatsApp message sent: {message_id} to {to[:5]}...")
                    
                    return {
                        "status": "sent",
                        "message_id": message_id,
                        "appointment_id": appointment_id
                    }
        
        except Exception as e:
            logger.error(f"WhatsApp send exception: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    @classmethod
    async def send_template(
        cls,
        to: str,
        template_name: str,
        language_code: str,
        parameters: list,
        appointment_id: Optional[str] = None
    ) -> Dict:
        """Send WhatsApp template message.
        
        Args:
            to: Phone number
            template_name: Approved template name
            language_code: Language code (e.g., 'en', 'pt_BR')
            parameters: List of parameter values
            appointment_id: Optional appointment ID
            
        Returns:
            Dict with message_id and status
        """
        if not settings.WHATSAPP_ACCESS_TOKEN:
            return {"status": "skipped", "reason": "not_configured"}
        
        url = cls._get_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages")
        
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Build template components
        components = []
        if parameters:
            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(param)}
                    for param in parameters
                ]
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to.replace("+", "").replace(" ", ""),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                },
                "components": components
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"WhatsApp template send failed: {response.status} - {error_text}")
                        return {
                            "status": "error",
                            "error": error_text,
                            "status_code": response.status
                        }
                    
                    data = await response.json()
                    message_id = data.get("messages", [{}])[0].get("id")
                    
                    logger.info(f"WhatsApp template sent: {message_id} to {to[:5]}...")
                    
                    return {
                        "status": "sent",
                        "message_id": message_id,
                        "appointment_id": appointment_id,
                        "template": template_name
                    }
        
        except Exception as e:
            logger.error(f"WhatsApp template send exception: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    @classmethod
    def verify_webhook(cls, signature: str, payload: bytes) -> bool:
        """Verify WhatsApp webhook signature.
        
        Args:
            signature: X-Hub-Signature-256 header value
            payload: Raw request body
            
        Returns:
            True if signature is valid
        """
        if not settings.WHATSAPP_WEBHOOK_SECRET:
            logger.warning("Webhook secret not configured")
            return True  # Allow in dev
        
        # Remove 'sha256=' prefix if present
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        # Calculate expected signature
        expected = hmac.new(
            settings.WHATSAPP_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    @classmethod
    async def get_message_status(cls, message_id: str) -> Dict:
        """Get message delivery status.
        
        Args:
            message_id: WhatsApp message ID
            
        Returns:
            Dict with status info
        """
        # Meta API doesn't have a direct "get status" endpoint
        # Status updates come via webhook
        # This is a placeholder for future implementation
        return {"message_id": message_id, "note": "Status via webhook"}
