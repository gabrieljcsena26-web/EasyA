from app.celery_app import celery_app
from app.services.notifications_v2 import process_pending_notifications, send_notification_by_id


# @celery_app.task(name='notifications.process_pending')
def process_pending_notifications_task(limit=50):
    return process_pending_notifications(limit=limit)


# @celery_app.task(name='notifications.send_by_id')
def send_notification_task(notif_id):
    return send_notification_by_id(notif_id)
