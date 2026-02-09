# backend/app/services/agendamento_service.py

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.models import (
    Estabelecimento,
    Funcionario,
    Cliente,
    Agendamento
)

# =========================================================
# ESTABELECIMENTO
# =========================================================
def get_or_create_estabelecimento(db: Session, nome: str, telefone: str, slug: str):
    estabelecimento = db.query(Estabelecimento).filter_by(slug=slug).first()
    if estabelecimento:
        return estabelecimento

    estabelecimento = Estabelecimento(
        nome=nome,
        telefone=telefone,
        slug=slug
    )
    db.add(estabelecimento)
    db.commit()
    db.refresh(estabelecimento)
    return estabelecimento


# =========================================================
# CLIENTE
# =========================================================
def get_or_create_cliente(
    db: Session,
    nome: str,
    telefone: str,
    estabelecimento_id: int,
    observacoes: str | None = None,
    tipo_servico: str | None = None
):
    cliente = (
        db.query(Cliente)
        .filter_by(telefone=telefone, estabelecimento_id=estabelecimento_id)
        .first()
    )

    if cliente:
        return cliente

    cliente = Cliente(
        nome=nome,
        telefone=telefone,
        observacoes=observacoes,
        tipo_servico=tipo_servico,
        estabelecimento_id=estabelecimento_id
    )

    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


# =========================================================
# FUNCIONÁRIO
# =========================================================
def get_or_create_funcionario(
    db: Session,
    nome: str,
    telefone: str,
    estabelecimento_id: int
):
    funcionario = (
        db.query(Funcionario)
        .filter_by(telefone=telefone, estabelecimento_id=estabelecimento_id)
        .first()
    )

    if funcionario:
        return funcionario

    funcionario = Funcionario(
        nome=nome,
        telefone=telefone,
        estabelecimento_id=estabelecimento_id
    )

    db.add(funcionario)
    db.commit()
    db.refresh(funcionario)
    return funcionario


# =========================================================
# FUNCIONÁRIO DISPONÍVEL
# =========================================================
def get_funcionario_disponivel(
    db: Session,
    estabelecimento_id: int,
    data_hora: datetime,
    duracao_minutos: int = 60
):
    funcionarios = (
        db.query(Funcionario)
        .filter_by(estabelecimento_id=estabelecimento_id)
        .all()
    )

    for funcionario in funcionarios:
        agendamentos = (
            db.query(Agendamento)
            .filter_by(funcionario_id=funcionario.id)
            .all()
        )

        disponivel = True
        for ag in agendamentos:
            inicio = ag.data_hora
            fim = inicio + timedelta(minutes=duracao_minutos)

            if inicio <= data_hora < fim:
                disponivel = False
                break

        if disponivel:
            return funcionario

    return None


# =========================================================
# AGENDAMENTO
# =========================================================
def criar_agendamento(
    db: Session,
    cliente_id: int,
    funcionario_id: int,
    descricao: str,
    data_hora: datetime
):
    agendamento = Agendamento(
        cliente_id=cliente_id,
        funcionario_id=funcionario_id,
        descricao=descricao,
        data_hora=data_hora
    )

    db.add(agendamento)
    db.commit()
    db.refresh(agendamento)
    return agendamento
