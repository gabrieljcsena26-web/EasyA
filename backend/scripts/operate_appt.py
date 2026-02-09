from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.models.models import Historico


def run(appt_id: int, token: str):
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Confirm
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "confirmado"})
    print("confirm =>", r.status_code, r.json())

    # Historico after confirm
    session = SessionLocal()
    hists = session.query(Historico).filter(Historico.agendamento_id == appt_id).all()
    print(f"historico count after confirm: {len(hists)}")
    for h in hists:
        print(h.id, h.acao, (h.detalhes or '')[:200])

    # Cancel
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "cancelado"})
    print("cancel =>", r.status_code, r.json())

    hists = session.query(Historico).filter(Historico.agendamento_id == appt_id).all()
    print(f"historico count after cancel: {len(hists)}")
    for h in hists:
        print(h.id, h.acao, (h.detalhes or '')[:200])

    # Get appointment via dashboard list to obtain cliente_id/funcionario_id
    r = client.get("/dashboard/agendamentos", headers=headers)
    print("GET /dashboard/agendamentos =>", r.status_code)
    ags = r.json().get("data") or []
    target = None
    for a in ags:
        if a.get("id") == appt_id:
            target = a
            break

    if not target:
        print("Appointment not found in dashboard list; cannot reschedule")
        session.close()
        return

    cliente_id = target.get("cliente_id")
    funcionario_id = target.get("funcionario_id")
    descricao = target.get("descricao") or "Reagendado"

    new_dt = datetime.now() + timedelta(days=3)
    new_iso = new_dt.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()
    payload = {
        "cliente_id": cliente_id,
        "funcionario_id": funcionario_id,
        "descricao": descricao,
        "data_hora": new_iso,
    }

    r = client.put(f"/dashboard/agendamentos/{appt_id}", headers=headers, json=payload)
    print("reschedule =>", r.status_code, r.json())

    hists = session.query(Historico).filter(Historico.agendamento_id == appt_id).all()
    print(f"historico count after reschedule: {len(hists)}")
    for h in hists:
        print(h.id, h.acao, (h.detalhes or '')[:200])

    session.close()


if __name__ == '__main__':
    print('This module provides run(appt_id, token)')
