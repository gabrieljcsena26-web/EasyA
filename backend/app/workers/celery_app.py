"""Celery Worker Configuration"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    'easyagenda',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task
def send_notification(appointment_id: str, notification_type: str):
    """Send notification task."""
    # TODO: Implement notification sending
    return {"status": "sent", "appointment_id": appointment_id}

@celery_app.task
def process_pending_notifications():
    """Process pending notifications."""
    # TODO: Query and send pending notifications
    return {"processed": 0}