import uuid
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Ensure DB schema matches models for test run
from app.db.database import engine, Base
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


def test_register_and_login_and_me():
    slug = f"test{uuid.uuid4().hex[:8]}"

    # register
    r = client.post("/auth/register", json={"nome": "T", "telefone": "000", "slug": slug})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body

    # login
    r2 = client.post("/auth/login", json={"username": slug, "password": "123"})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert "token" in body2

    token = body2["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # me
    r3 = client.get("/auth/me", headers=headers)
    assert r3.status_code == 200, r3.text
    mb = r3.json()
    # if stored, slug should match
    assert mb.get("slug") == slug or mb.get("username") == slug


def test_clients_crud():
    slug = f"test{uuid.uuid4().hex[:8]}"
    r = client.post("/auth/register", json={"nome": "T2", "telefone": "111", "slug": slug})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # create
    payload = {"nome": "Client A", "telefone": "9999", "observacoes": "obs", "tipo_servico": "srv"}
    rc = client.post("/dashboard/clientes", json=payload, headers=headers)
    assert rc.status_code == 200, rc.text

    # list
    rl = client.get("/dashboard/clientes", headers=headers)
    assert rl.status_code == 200, rl.text
    # ensure response is successful wrapper
    data = rl.json()
    assert data.get("success", False) is True

    # try update first item if exists
    items = data.get("data") or []
    if items:
        first = items[0]
        cid = first.get("id") or first.get("pk") or None
        if cid:
            ru = client.put(f"/dashboard/clientes/{cid}", json={"nome": "Client A 2", "telefone": "0000", "observacoes": "u", "tipo_servico": "srv"}, headers=headers)
            assert ru.status_code == 200, ru.text

            rd = client.delete(f"/dashboard/clientes/{cid}", headers=headers)
            assert rd.status_code == 200, rd.text
