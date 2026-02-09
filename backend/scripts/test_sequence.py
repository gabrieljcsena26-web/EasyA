from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from main import app

from app.db.database import SessionLocal
from app.models.models import Historico


def run_sequence(token: str):
    client = TestClient(app)

    # 1) GET /config
    r = client.get("/config")
    print("GET /config =>", r.status_code)
    cfg = r.json()
    services = cfg.get("services") or []
    professionals = cfg.get("professionals") or []
    if not services or not professionals:
        raise RuntimeError("No services or professionals available in /config")

    service_id = services[0]["id"]
    professional_id = professionals[0]["id"]

    # 2) Create appointment (tomorrow at 10:00)
    date = (datetime.now().date() + timedelta(days=1)).isoformat()
    payload = {
        "service_id": service_id,
        "professional_id": professional_id,
        "date": date,
        "start_time": "10:00",
        "channel": "web",
        "customer_name": "Test User",
        "customer_whatsapp": "+0000000000",
    }

    r = client.post("/appointments", json=payload)
    print("POST /appointments =>", r.status_code, r.json())
    appt = r.json().get("appointment") or r.json()
    appt_id = appt.get("id")
    if not appt_id:
        raise RuntimeError("Failed to create appointment")

    # 3) Confirm via dashboard endpoint (protected)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "confirmado"})
    print(f"PUT /dashboard/agendamentos/{appt_id}/status confirm =>", r.status_code, r.json())

    # Inspect historico entries
    session = SessionLocal()
    hists = session.query(Historico).filter(Historico.agendamento_id == appt_id).all()
    print(f"Historico entries after confirm: {len(hists)}")
    for h in hists:
        print(h.id, h.acao, (h.detalhes or '')[:200])

    # 4) Cancel
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "cancelado"})
    print(f"PUT /dashboard/agendamentos/{appt_id}/status cancel =>", r.status_code, r.json())

    hists = session.query(Historico).filter(Historico.agendamento_id == appt_id).all()
    print(f"Historico entries after cancel: {len(hists)}")
    for h in hists:
        print(h.id, h.acao, (h.detalhes or '')[:200])

    # 5) Reschedule: fetch appointment record to get cliente_id and funcionario_id
    r = client.get("/dashboard/agendamentos", headers=headers)
    print("GET /dashboard/agendamentos =>", r.status_code)
    ags = r.json().get("data") or []
    target = None
    for a in ags:
        if a.get("id") == appt_id:
            target = a
            break
    if not target:
        raise RuntimeError("Could not find appointment in /dashboard/agendamentos")

    cliente_id = target.get("cliente_id")
    funcionario_id = target.get("funcionario_id")

    new_dt = datetime.now() + timedelta(days=2)
    new_iso = new_dt.replace(hour=11, minute=0, second=0, microsecond=0).isoformat()
    res_payload = {
        "cliente_id": cliente_id,
        "funcionario_id": funcionario_id,
        "descricao": target.get("descricao") or "Rescheduled",
        "data_hora": new_iso,
    }

    r = client.put(f"/dashboard/agendamentos/{appt_id}", headers=headers, json=res_payload)
    print(f"PUT /dashboard/agendamentos/{appt_id} reschedule =>", r.status_code, r.json())

    hists = session.query(Historico).filter(Historico.agendamento_id == appt_id).all()
    print(f"Historico entries after reschedule: {len(hists)}")
    for h in hists:
        print(h.id, h.acao, (h.detalhes or '')[:200])

    session.close()


if __name__ == "__main__":
    # Paste the dev JWT here if running interactively
    dev_token = ""
    if not dev_token:
        print("Please set dev_token variable in the script before running as standalone.")
    else:
        run_sequence(dev_token)
