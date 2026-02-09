from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.models.models import Estabelecimento
from app.core.security import create_access_token


def run_local_flow():
    s = SessionLocal()
    est = s.query(Estabelecimento).first()
    s.close()
    if not est:
        print('No establishment found in DB')
        return

    token = create_access_token({"slug": est.slug, "role": "admin", "estabelecimento_id": est.id})
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)

    print('Using establishment', est.slug)

    # 1) create cliente
    cl_payload = {"nome": "ManualTest", "telefone": "+999999999", "observacoes": "test", "tipo_servico": "t", "idioma": "pt-BR"}
    r = client.post('/dashboard/clientes', headers=headers, json=cl_payload)
    print('POST /dashboard/clientes =>', r.status_code, r.text)
    if r.status_code != 200:
        return
    cliente = r.json().get('data')

    # 2) pick professional
    cfg = client.get(f'/config?slug={est.slug}').json()
    pros = cfg.get('professionals') or []
    if not pros:
        print('No professionals for est')
        return
    prof_id = pros[0]['id']
    print('Using professional', prof_id)

    # 3) create appointment
    date = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
    ag_payload = {"cliente_id": cliente['id'], "funcionario_id": prof_id, "descricao": "manual test", "data_hora": date}
    r = client.post('/dashboard/agendamentos', headers=headers, json=ag_payload)
    print('POST /dashboard/agendamentos =>', r.status_code, r.text)
    if r.status_code != 200:
        return
    appt = r.json().get('data')
    appt_id = appt.get('id')

    # confirm
    r = client.put(f'/dashboard/agendamentos/{appt_id}/status', headers=headers, json={'status': 'confirmado'})
    print('confirm =>', r.status_code, r.text)

    # cancel
    r = client.put(f'/dashboard/agendamentos/{appt_id}/status', headers=headers, json={'status': 'cancelado'})
    print('cancel =>', r.status_code, r.text)

    # reschedule
    new_dt = (datetime.now() + timedelta(days=3)).replace(hour=13, minute=0, second=0, microsecond=0).isoformat()
    res_payload = {"cliente_id": cliente['id'], "funcionario_id": prof_id, "descricao": "rescheduled by manual", "data_hora": new_dt}
    r = client.put(f'/dashboard/agendamentos/{appt_id}', headers=headers, json=res_payload)
    print('reschedule =>', r.status_code, r.text)

    # historico
    r = client.get(f'/dashboard/agendamentos/{appt_id}/historico', headers=headers)
    print('historico =>', r.status_code, r.text)


if __name__ == '__main__':
    run_local_flow()
