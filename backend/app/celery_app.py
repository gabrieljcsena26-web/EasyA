import os
# from celery import Celery

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# celery_app = Celery('easya', broker=REDIS_URL, backend=REDIS_URL)
celery_app = None  # Celery disabled

# optional: load custom config from env
# celery_app.conf.update(task_track_started=True, worker_prefetch_multiplier=1)
