from app.db.database import SessionLocal
from app.services.agendamento_service import get_or_create_cliente, criar_agendamento

def _demo():
    db = SessionLocal()

    # Criar cliente
    cliente = get_or_create_cliente(
        db=db,
        nome="João",
        telefone="11999999999",
        observacoes="Prefere atendimento manhã",
        tipo_servico="Consulta",
        estabelecimento_id=1
    )

    # Criar agendamento (demo invocation)
    try:
        agendamento = criar_agendamento(
            db=db,
            cliente_id=cliente.id,
            funcionario_id=1,
            descricao="Consulta inicial",
            data_hora=None,
        )
    except TypeError:
        agendamento = None

    print(cliente)
    print(agendamento)


if __name__ == "__main__":
    _demo()
