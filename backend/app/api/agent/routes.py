# backend/app/api/agent/routes.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime

from app.db.database import get_db
from app.services.agendamento_service import (
    get_or_create_cliente,
    get_funcionario_disponivel,
    criar_agendamento
)
from assistant_service import conversar_com_assistente
from config_loader import load_client_config
from app.core.security import verify_access_token

router = APIRouter(
    prefix="/agent",
    tags=["agent"]
)

# --------------------------
# AUTENTICAÇÃO
# --------------------------
auth_scheme = HTTPBearer()

def validate_token(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    """
    Valida token JWT no header Authorization: Bearer <token>
    """
    token = credentials.credentials

    # Verifica token com JWT
    try:
        payload = verify_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    # Retorna payload para usar dentro do endpoint (ex: slug do cliente)
    return payload

# --------------------------
# MODELO DE DADOS DE INPUT
# --------------------------
class AgentInput(BaseModel):
    nome_cliente: str
    telefone_cliente: str
    mensagem: str
    slug_estabelecimento: str
    data_hora: Optional[str] = None  # ISO format: '2025-12-20T14:00'

# --------------------------
# ENDPOINT PRINCIPAL
# --------------------------
@router.post("/chat")
def agent_chat(
    input: AgentInput,
    db: Session = Depends(get_db),
    user_payload=Depends(validate_token)  # Payload JWT validado
):

    # 1️⃣ Carrega config do cliente dinamicamente pelo slug
    try:
        client_config = load_client_config(input.slug_estabelecimento)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # 2️⃣ Garantir que cliente exista no banco
    cliente = get_or_create_cliente(
        db=db,
        nome=input.nome_cliente,
        telefone=input.telefone_cliente,
        estabelecimento_id=client_config.get("estabelecimento_id", 1)  # fallback para 1
    )

    # 3️⃣ Converte data_hora se fornecida
    data_hora = None
    if input.data_hora:
        try:
            data_hora = datetime.fromisoformat(input.data_hora)
        except Exception:
            raise HTTPException(status_code=400, detail="data_hora inválida. Use ISO format")

    # 4️⃣ Busca funcionário disponível
    funcionario = get_funcionario_disponivel(
        db=db,
        estabelecimento_id=client_config.get("estabelecimento_id", 1),
        data_hora=data_hora if data_hora else datetime.now()
    )

    # 5️⃣ Cria agendamento se funcionário disponível e data_hora fornecida
    agendamento = None
    funcionario_id = None
    if funcionario:
        funcionario_id = funcionario.id
        if data_hora:
            agendamento = criar_agendamento(
                db=db,
                cliente_id=cliente.id,
                funcionario_id=funcionario.id,
                descricao=input.mensagem,
                data_hora=data_hora
            )

    # 6️⃣ Envia mensagem para o Assistant AI
    resposta, thread_id = conversar_com_assistente(
        slug=input.slug_estabelecimento,
        mensagem=input.mensagem
    )

    # 7️⃣ Retorna tudo para front/dashboard/WhatsApp
    return {
        "resposta_ai": resposta,
        "cliente_id": cliente.id,
        "funcionario_id": funcionario_id,
        "agendamento_id": agendamento.id if agendamento else None,
        "thread_id": thread_id
    }
