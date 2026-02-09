import pytest
from fastapi.testclient import TestClient
from app.db.database import SessionLocal
from app.models.models import Estabelecimento
from app.core.security import create_access_token

from main import app


def setup_establishment():
    s = SessionLocal()
    est = s.query(Estabelecimento).first()
    s.close()
    return est


def test_historico_flow():
    client = TestClient(app)
    est = setup_establishment()
    assert est is not None

    token = create_access_token({"slug": est.slug, "role": "admin", "estabelecimento_id": est.id})
    headers = {"Authorization": f"Bearer {token}"}

    # create cliente
    cl_payload = {"nome": "TestHist", "telefone": "+22222222", "observacoes": "x", "tipo_servico": "t", "idioma": "pt-BR"}
    r = client.post("/dashboard/clientes", headers=headers, json=cl_payload)
    assert r.status_code == 200
    cliente = r.json().get("data")

    # pick a professional from /config?slug
    cfg = client.get(f"/config?slug={est.slug}").json()
    pros = cfg.get("professionals") or []
    assert pros, "no professionals for est"
    prof_id = pros[0]["id"]

    # create appointment via admin
    date = "2026-01-20T09:00:00"
    ag_payload = {"cliente_id": cliente["id"], "funcionario_id": prof_id, "descricao": "test", "data_hora": date}
    r = client.post("/dashboard/agendamentos", headers=headers, json=ag_payload)
    assert r.status_code == 200
    appt = r.json().get("data")
    appt_id = appt.get("id")

    # confirm
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "confirmado"})
    assert r.status_code == 200

    # cancel
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "cancelado"})
    assert r.status_code == 200

    # reschedule
    res_payload = {"cliente_id": cliente["id"], "funcionario_id": prof_id, "descricao": "res", "data_hora": "2026-01-22T11:00:00"}
    r = client.put(f"/dashboard/agendamentos/{appt_id}", headers=headers, json=res_payload)
    assert r.status_code == 200

    # historico
    r = client.get(f"/dashboard/agendamentos/{appt_id}/historico", headers=headers)
    assert r.status_code == 200
    data = r.json().get("data")
    assert isinstance(data, list)
    # expect at least criado, status_alterado, alterado
    actions = [h.get("acao") for h in data]
    assert any(a == "criado" for a in actions)
    assert any(a == "status_alterado" for a in actions)
    assert any(a == "alterado" for a in actions)

    # Ensure status history records the old->new transition (regression guard)
    status_changes = [h for h in data if h.get("acao") == "status_alterado"]
    assert status_changes, "expected status_alterado entries"
    details = "\n".join((h.get("detalhes") or "") for h in status_changes)
    assert "pendente" in details
    assert "confirmado" in details
