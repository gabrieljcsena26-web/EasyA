from app.models.models import Interesse, Agendamento, Cliente
from app.services.notifications_v2 import enqueue_notification
from sqlalchemy.orm import Session

def notificar_interessados(agendamento_cancelado: Agendamento, db: Session):
    """
    Notifica clientes interessados em horário/funcionário liberado.
    """
    interessados = db.query(Interesse).filter(
        (Interesse.funcionario_id == agendamento_cancelado.funcionario_id) |
        (Interesse.funcionario_id == None)
    ).all()
    for interesse in interessados:
        cliente = db.query(Cliente).filter(Cliente.id == interesse.cliente_id).first()
        if not cliente:
            continue
        msg = (
            f"Olá {cliente.nome}, surgiu uma vaga para hoje às {agendamento_cancelado.data_hora.strftime('%H:%M')} com nosso profissional. Responda 1 para reservar!"
        )
        enqueue_notification('sms', cliente.telefone, msg, payload={"tipo": "vaga_interessado", "agendamento_id": agendamento_cancelado.id}, idempotency_key=f"interesse_{interesse.id}")
