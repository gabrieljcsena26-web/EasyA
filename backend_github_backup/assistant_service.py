from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from config_loader import load_client_config
from openai_client import get_openai_client

from app.db.database import SessionLocal
from app.services.agendamento_service import (
    get_or_create_cliente,
    get_funcionario_disponivel,
    criar_agendamento
)


def conversar_com_assistente(
    slug: str,
    mensagem: str,
    thread_id: Optional[str] = None,
    data_hora: Optional[datetime] = None  # ✅ Novo parâmetro opcional
):
    """
    Fluxo completo:
    - conversa com o assistant
    - cria cliente se não existir
    - cria agendamento simples no banco
    """

    # 1️⃣ DB session
    db: Session = SessionLocal()

    try:
        # 2️⃣ Config do cliente
        config = load_client_config(slug)
        assistant_id = config["assistant_id"]
        estabelecimento_id = config["estabelecimento_id"]

        # 3️⃣ OpenAI client
        client = get_openai_client()

        # 4️⃣ Thread
        if thread_id is None:
            thread = client.beta.threads.create()
            thread_id = thread.id

        # 5️⃣ Mensagem do usuário
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=mensagem
        )

        # 6️⃣ Run
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )

        while run.status in ("queued", "in_progress"):
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

        if run.status != "completed":
            raise RuntimeError("Erro no assistant")

        # 7️⃣ Resposta
        messages = client.beta.threads.messages.list(thread_id=thread_id)

        resposta_texto = ""
        for msg in messages.data:
            if msg.role == "assistant":
                for content in msg.content:
                    if content.type == "text":
                        resposta_texto = content.text.value
                        break
                break

        # 🔹 EXEMPLO DE AÇÃO REAL NO BANCO
        cliente = get_or_create_cliente(
            db=db,
            nome="Cliente WhatsApp",
            telefone="000000000",
            estabelecimento_id=estabelecimento_id
        )

        # ✅ Passa data_hora para o get_funcionario_disponivel
        funcionario = get_funcionario_disponivel(
            db=db,
            estabelecimento_id=estabelecimento_id,
            data_hora=data_hora if data_hora else datetime.now()
        )

        if funcionario:
            criar_agendamento(
                db=db,
                cliente_id=cliente.id,
                funcionario_id=funcionario.id,
                descricao="Agendamento via assistant",
                data_hora=data_hora if data_hora else datetime.now()
            )

        return resposta_texto, thread_id

    finally:
        db.close()
