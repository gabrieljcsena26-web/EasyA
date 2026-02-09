from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from main import app


def run(admin_token: str, est_slug: str):
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1) Discover professionals for the establishment via /config?slug=
    r = client.get(f"/config?slug={est_slug}")
    print("GET /config?slug =>", r.status_code)
    cfg = r.json()
    pros = cfg.get("professionals") or []
    if not pros:
        print("No professionals for est")
        return
    prof_id = pros[0]["id"]
    print("Using professional id", prof_id)

    # 2) Create Cliente via admin endpoint
    cliente_payload = {
        "nome": "Admin Test",
        "telefone": "+1111111111",
        "observacoes": "Created by admin_flow",
        "tipo_servico": "Teste",
        "idioma": "pt-BR",
    }
    r = client.post("/dashboard/clientes", headers=headers, json=cliente_payload)
    print("POST /dashboard/clientes =>", r.status_code, r.json())
    cliente = r.json().get("data") or r.json()
    cliente_id = cliente.get("id")

    # 3) Create Agendamento via admin endpoint for tomorrow at 10:00 (or next free slot)
    date = (datetime.now().date() + timedelta(days=1)).isoformat()
    ag_payload = {
        "cliente_id": cliente_id,
        "funcionario_id": prof_id,
        "descricao": "Admin created appointment",
        "data_hora": f"{date}T10:00:00"
    }
    r = client.post("/dashboard/agendamentos", headers=headers, json=ag_payload)
    print("POST /dashboard/agendamentos =>", r.status_code, r.json())
    appt = r.json().get("data") or r.json()
    appt_id = appt.get("id")

    # 4) Run confirm/cancel/reschedule using operate_appt.run logic inline
    if not appt_id:
        print("Failed to create admin appointment")
        return

    # Confirm
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "confirmado"})
    print("confirm =>", r.status_code, r.json())

    # Cancel
    r = client.put(f"/dashboard/agendamentos/{appt_id}/status", headers=headers, json={"status": "cancelado"})
    print("cancel =>", r.status_code, r.json())

    # Reschedule
    new_dt = datetime.now() + timedelta(days=3)
    new_iso = new_dt.replace(hour=13, minute=0, second=0, microsecond=0).isoformat()
    res_payload = {
        "cliente_id": cliente_id,
        "funcionario_id": prof_id,
        "descricao": "Rescheduled by admin_flow",
        "data_hora": new_iso,
    }
    r = client.put(f"/dashboard/agendamentos/{appt_id}", headers=headers, json=res_payload)
    print("reschedule =>", r.status_code, r.json())


if __name__ == '__main__':
    print('Use run(admin_token, est_slug)')
