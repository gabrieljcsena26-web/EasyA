from datetime import datetime, timedelta, timezone
import json

from app.db.database import SessionLocal
from app.models.models import PendingAction
from main import app
from fastapi.testclient import TestClient


def process_once():
    s = SessionLocal()
    now = datetime.now(timezone.utc)
    actions = s.query(PendingAction).filter(PendingAction.status == 'pending').all()
    if not actions:
        print('No pending actions')
        s.close()
        return

    client = TestClient(app)

    for a in actions:
        print('Processing', a.id, a.tipo)
        a.status = 'processing'
        s.add(a)
        s.commit()
        try:
            if a.tipo == 'appointments.create':
                r = client.post('/appointments', json=a.payload)
            else:
                print('Unknown action type', a.tipo)
                r = None

            if r is not None and r.status_code in (200, 201):
                a.status = 'done'
                print('Action succeeded', a.id)
            else:
                a.attempts = (a.attempts or 0) + 1
                a.last_error = (r.text if r is not None else 'no response')
                if a.attempts >= (a.max_attempts or 5):
                    a.status = 'failed'
                else:
                    a.status = 'pending'
                    a.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=2 ** a.attempts)
                print('Action failed', a.id, a.last_error)

        except Exception as e:
            a.attempts = (a.attempts or 0) + 1
            a.last_error = str(e)
            a.status = 'pending'
                a.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=2 ** a.attempts)
            print('Exception while processing', a.id, e)

        s.add(a)
        s.commit()

    s.close()


if __name__ == '__main__':
    process_once()
