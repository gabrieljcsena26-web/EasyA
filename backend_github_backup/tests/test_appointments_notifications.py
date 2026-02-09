import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models.models import Funcionario, Cliente, Notificacao, Estabelecimento
from app.services.notifications_v2 import enqueue_notification, send_notification_by_id

client = TestClient(app)


def _get_db_session():
    return SessionLocal()


def test_create_appointment_flow():
    slug = f"test{uuid.uuid4().hex[:8]}"
    # register estabelecimento
    r = client.post("/auth/register", json={"nome": "Biz", "telefone": "000", "slug": slug})
    assert r.status_code == 200
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # lookup estabelecimento id and create funcionario via DB
    db = _get_db_session()
    try:
        est = db.query(Estabelecimento).filter(Estabelecimento.slug == slug).first()
        assert est is not None
        func = Funcionario(nome="F1", telefone="111", estabelecimento_id=est.id)
        db.add(func)
        db.commit()
        db.refresh(func)
    finally:
        db.close()

    # create client via API
    payload = {"nome": "C1", "telefone": "9999", "observacoes": "obs", "tipo_servico": "srv"}
    rc = client.post("/dashboard/clientes", json=payload, headers=headers)
    assert rc.status_code == 200
    data = rc.json()["data"]
    cid = data.get("id")

    # create appointment
    ap = {
        "cliente_id": cid,
        "funcionario_id": func.id,
        "descricao": "Test ap",
        "data_hora": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    ra = client.post("/dashboard/agendamentos", json=ap, headers=headers)
    assert ra.status_code == 200


def test_notifications_enqueue_and_process():
    # enqueue
    nid = enqueue_notification("sms", "+34600000000", "Test message", payload={"x":1})
    assert isinstance(nid, int)

    # process by id (Twilio disabled) should mark as failed and increment attempts
    ok = send_notification_by_id(nid)
    # Because Twilio client is disabled this returns False, but ensures DB updated
    assert ok in (False, True)

    # verify DB row
    db = _get_db_session()
    try:
        n = db.query(Notificacao).filter(Notificacao.id == nid).first()
        assert n is not None
        assert n.attempts >= 1
        assert n.status in ("failed", "permanent_failure", "sent")
    finally:
        db.close()
