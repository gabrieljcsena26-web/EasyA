from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Cliente, Estabelecimento
from app.services.scheduler import agendar_lembretes_para_agendamento
from app.core.locale import resolve_lang
from app.schemas.schemas import ClienteOut, ClienteCreate
from app.core.security import verify_access_token_dep, security
from app.core.responses import success_response
from app.models.models import Agendamento, Funcionario, Historico
from app.schemas.schemas import AgendamentoCreate, AgendamentoOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# -------------------------------
# GET clientes
# -------------------------------
@router.get("/clientes")
def listar_clientes(
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")
    clientes = db.query(Cliente).filter(Cliente.estabelecimento_id == est_id).all()

    return success_response(
        data=clientes,
        message="Clients listed successfully"
    )

# -------------------------------
# POST cliente
# -------------------------------
@router.post("/clientes")
def criar_cliente(
    cliente: ClienteCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")

    novo_cliente = Cliente(
        nome=cliente.nome,
        telefone=cliente.telefone,
        observacoes=cliente.observacoes,
        tipo_servico=cliente.tipo_servico,
        estabelecimento_id=est_id,
        idioma=getattr(cliente, 'idioma', 'pt-BR')
    )

    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)

    return success_response(
        data=novo_cliente,
        message="Client created successfully"
    )

# -------------------------------
# PUT cliente
# -------------------------------
@router.put("/clientes/{cliente_id}")
def atualizar_cliente(
    cliente_id: int,
    cliente: ClienteCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")

    db_cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.estabelecimento_id == est_id
    ).first()

    if not db_cliente:
        raise HTTPException(status_code=404, detail="Client not found")

    db_cliente.nome = cliente.nome
    db_cliente.telefone = cliente.telefone
    db_cliente.observacoes = cliente.observacoes
    db_cliente.tipo_servico = cliente.tipo_servico
    db_cliente.idioma = getattr(cliente, 'idioma', db_cliente.idioma)

    db.commit()
    db.refresh(db_cliente)

    return success_response(
        data=db_cliente,
        message="Client updated successfully"
    )

# -------------------------------
# DELETE cliente
# -------------------------------
@router.delete("/clientes/{cliente_id}")
def deletar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")

    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.estabelecimento_id == est_id
    ).first()

    if not cliente:
        raise HTTPException(status_code=404, detail="Client not found")

    db.delete(cliente)
    db.commit()

    return success_response(
        data=None,
        message="Client deleted successfully"
    )


# -------------------------------
# AGENDAMENTOS
# -------------------------------
@router.get("/agendamentos")
def listar_agendamentos(
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")
    # join via estabelecimento_id through Cliente
    ags = db.query(Agendamento).join(Cliente).filter(Cliente.estabelecimento_id == est_id).all()
    return success_response(data=ags, message="Appointments listed successfully")


@router.get("/clientes/{cliente_id}")
def obter_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.estabelecimento_id == est_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Client not found")
    return success_response(data=cliente, message="Client fetched")


@router.get("/estabelecimento/me")
def obter_estabelecimento_me(
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")
    est = db.query(Estabelecimento).filter(Estabelecimento.id == est_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento not found")
    return success_response(data=est, message="Estabelecimento fetched")


@router.post("/agendamentos")
def criar_agendamento(
    ag: AgendamentoCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")

    # verify cliente belongs to estabelecimento
    cliente = db.query(Cliente).filter(Cliente.id == ag.cliente_id, Cliente.estabelecimento_id == est_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado ou não pertence ao estabelecim")

    funcionario = db.query(Funcionario).filter(Funcionario.id == ag.funcionario_id, Funcionario.estabelecimento_id == cliente.estabelecimento_id).first()
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado ou não pertence ao estabelecimento")

    novo = Agendamento(
        cliente_id=ag.cliente_id,
        funcionario_id=ag.funcionario_id,
        descricao=ag.descricao,
        data_hora=ag.data_hora
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    # Registro no histórico
    try:
        detalhes = f"Agendamento criado para cliente {cliente.nome} (id={cliente.id}) em {novo.data_hora.isoformat()}"
        hist = Historico(agendamento_id=novo.id, acao="criado", detalhes=detalhes)
        db.add(hist)
        db.commit()
    except Exception:
        pass

    # Agendar lembretes usando o idioma preferido do cliente (APScheduler desativado por enquanto)
    try:
        lang = resolve_lang(
            cliente_lang=getattr(cliente, 'idioma', None),
            estabelecimento_lang=getattr(db.query(Estabelecimento).filter(Estabelecimento.id == est_id).first(), 'idioma_padrao', None),
            accept_language=None,
        )
        agendar_lembretes_para_agendamento(
            novo,
            cliente,
            lang,
            db=db,
            estabelecimento_id=est_id,
        )
    except Exception:
        # Não falhar a criação do agendamento por erro no agendador
        pass

    return success_response(data=novo, message="Appointment created")
    


@router.put("/agendamentos/{agendamento_id}")
def atualizar_agendamento(
    agendamento_id: int,
    ag: AgendamentoCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")
    ag_db = db.query(Agendamento).join(Cliente).filter(Agendamento.id == agendamento_id, Cliente.estabelecimento_id == est_id).first()
    if not ag_db:
        raise HTTPException(status_code=404, detail="Appointment not found")

    ag_db.cliente_id = ag.cliente_id
    ag_db.funcionario_id = ag.funcionario_id
    ag_db.descricao = ag.descricao
    ag_db.data_hora = ag.data_hora
    db.commit()
    db.refresh(ag_db)

    # Histórico: registrar alteração
    try:
        detalhes = f"Agendamento atualizado: data_hora={ag_db.data_hora.isoformat()} funcionario_id={ag_db.funcionario_id}"
        hist = Historico(agendamento_id=ag_db.id, acao="alterado", detalhes=detalhes)
        db.add(hist)
        db.commit()
    except Exception:
        pass

    return success_response(data=ag_db, message="Appointment updated")



@router.put("/agendamentos/{agendamento_id}/status")
def atualizar_status_agendamento(
    agendamento_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    """Atualiza apenas o status de um agendamento (confirmado/cancelado/pendente)."""
    est_id = user.get("estabelecimento_id")
    ag_db = db.query(Agendamento).join(Cliente).filter(Agendamento.id == agendamento_id, Cliente.estabelecimento_id == est_id).first()
    if not ag_db:
        raise HTTPException(status_code=404, detail="Appointment not found")

    status = payload.get('status') if isinstance(payload, dict) else None
    if not status:
        raise HTTPException(status_code=400, detail="Missing status in payload")

    old = getattr(ag_db, 'status', None)
    ag_db.status = status
    db.commit()
    db.refresh(ag_db)

    # Histórico: registrar mudança de status
    try:
        detalhes = f"Status alterado de {old} para {status}"
        hist = Historico(agendamento_id=ag_db.id, acao="status_alterado", detalhes=detalhes)
        db.add(hist)
        db.commit()
    except Exception:
        pass

    return success_response(data=ag_db, message="Appointment status updated")


@router.delete("/agendamentos/{agendamento_id}")
def deletar_agendamento(
    agendamento_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security)
):
    est_id = user.get("estabelecimento_id")
    ag_db = db.query(Agendamento).join(Cliente).filter(Agendamento.id == agendamento_id, Cliente.estabelecimento_id == est_id).first()
    if not ag_db:
        raise HTTPException(status_code=404, detail="Appointment not found")
    # Registrar histórico antes de deletar
    try:
        detalhes = f"Agendamento deletado: cliente_id={ag_db.cliente_id} funcionario_id={ag_db.funcionario_id} data_hora={ag_db.data_hora.isoformat()}"
        hist = Historico(agendamento_id=ag_db.id, acao="deletado", detalhes=detalhes)
        db.add(hist)
        db.commit()
    except Exception:
        pass

    db.delete(ag_db)
    db.commit()
    return success_response(data=None, message="Appointment deleted")


@router.get("/agendamentos/{agendamento_id}/historico")
def obter_historico_agendamento(
    agendamento_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(verify_access_token_dep),
    token: str = Depends(security),
):
    est_id = user.get("estabelecimento_id")
    ag_db = db.query(Agendamento).join(Cliente).filter(Agendamento.id == agendamento_id, Cliente.estabelecimento_id == est_id).first()
    if not ag_db:
        raise HTTPException(status_code=404, detail="Appointment not found")

    hists = db.query(Historico).filter(Historico.agendamento_id == agendamento_id).order_by(Historico.data_hora.asc()).all()
    return success_response(data=hists, message="Appointment historico fetched")
