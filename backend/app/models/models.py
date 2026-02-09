from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.db.database import Base


# ---------------------------
# ESTABELECIMENTO
# ---------------------------
class Estabelecimento(Base):
    __tablename__ = "estabelecimentos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    slug = Column(String, nullable=False, unique=True)
    # Senha com hash (nullable para compatibilidade com registros antigos / demo)
    senha_hash = Column(String, nullable=True)
    # Autenticação: senha com hash e token de reset
    reset_token_hash = Column(String, nullable=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Horários de lembrete em horas antes do agendamento (ex: [16, 3, 2])
    lembrete_horas_antes = Column(JSON, nullable=True, default=None)
    # Idioma padrão do estabelecimento (ex: 'pt-BR')
    idioma_padrao = Column(String, nullable=True, default='pt-BR')
    # Horário de funcionamento (hora inteira, ex: 9 = 09:00)
    horario_inicio = Column(Integer, nullable=False, default=9)
    horario_fim = Column(Integer, nullable=False, default=18)
    # Fotos e reviews para a landing (JSON arrays)
    photos = Column(JSON, nullable=True, default=None)
    reviews = Column(JSON, nullable=True, default=None)

    # Relacionamentos
    funcionarios = relationship(
        "Funcionario",
        back_populates="estabelecimento",
        cascade="all, delete-orphan"
    )

    clientes = relationship(
        "Cliente",
        back_populates="estabelecimento",
        cascade="all, delete-orphan"
    )

    services = relationship(
        "Service",
        back_populates="estabelecimento",
        cascade="all, delete-orphan"
    )

    setup_profile = relationship(
        "SetupProfile",
        back_populates="estabelecimento",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ---------------------------
# SETUP PROFILE (wizard)
# ---------------------------
class SetupProfile(Base):
    __tablename__ = "setup_profiles"

    id = Column(Integer, primary_key=True, index=True)
    estabelecimento_id = Column(
        Integer,
        ForeignKey("estabelecimentos.id"),
        nullable=False,
        unique=True,
    )
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    estabelecimento = relationship(
        "Estabelecimento",
        back_populates="setup_profile",
    )


# ---------------------------
# SERVIÇO
# ---------------------------
class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)

    estabelecimento_id = Column(
        Integer,
        ForeignKey("estabelecimentos.id"),
        nullable=False,
    )

    name = Column(String, nullable=False)
    duration_min = Column(Integer, nullable=False)
    buffer_min = Column(Integer, nullable=True)
    price_cents = Column(Integer, nullable=False, default=0)
    display_interval_min = Column(Integer, nullable=False, default=30)

    estabelecimento = relationship(
        "Estabelecimento",
        back_populates="services",
    )

    agendamentos = relationship(
        "Agendamento",
        back_populates="service",
        cascade="all, delete-orphan",
    )


# ---------------------------
# FUNCIONÁRIO
# ---------------------------
class Funcionario(Base):
    __tablename__ = "funcionarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=False)

    estabelecimento_id = Column(
        Integer,
        ForeignKey("estabelecimentos.id"),
        nullable=False
    )

    # Relacionamentos
    estabelecimento = relationship(
        "Estabelecimento",
        back_populates="funcionarios"
    )

    agendamentos = relationship(
        "Agendamento",
        back_populates="funcionario",
        cascade="all, delete-orphan"
    )


# ---------------------------
# CLIENTE
# ---------------------------
class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=False)

    observacoes = Column(String, nullable=True)
    tipo_servico = Column(String, nullable=True)
    # Preferência de idioma do cliente (ex: 'pt-BR', 'en-US', 'es-ES')
    idioma = Column(String, nullable=True, default='pt-BR')

    estabelecimento_id = Column(
        Integer,
        ForeignKey("estabelecimentos.id"),
        nullable=False
    )

    # Relacionamentos
    estabelecimento = relationship(
        "Estabelecimento",
        back_populates="clientes"
    )

    agendamentos = relationship(
        "Agendamento",
        back_populates="cliente",
        cascade="all, delete-orphan"
    )


# ---------------------------
# AGENDAMENTO
# ---------------------------
class Agendamento(Base):
    __tablename__ = "agendamentos"

    id = Column(Integer, primary_key=True, index=True)

    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id"),
        nullable=False
    )

    funcionario_id = Column(
        Integer,
        ForeignKey("funcionarios.id"),
        nullable=False
    )

    # Serviço associado (para duração, buffer, preço, etc.)
    service_id = Column(
        Integer,
        ForeignKey("services.id"),
        nullable=True,
    )

    descricao = Column(String, nullable=True)

    # DATA E HORA DO ATENDIMENTO
    data_hora = Column(DateTime, default=datetime.now)
    
    # Track updates for sync endpoint
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Status field
    status = Column(String, default="pendente")

    # Relacionamentos
    cliente = relationship(
        "Cliente",
        back_populates="agendamentos"
    )

    funcionario = relationship(
        "Funcionario",
        back_populates="agendamentos"
    )

    service = relationship(
        "Service",
        back_populates="agendamentos",
    )
    
    historicos = relationship(
        "Historico",
        back_populates="agendamento",
        cascade="all, delete-orphan"
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "funcionario_id": self.funcionario_id,
            "service_id": self.service_id,
            "descricao": self.descricao,
            "data_hora": self.data_hora.isoformat() if self.data_hora else None,
            "status": self.status,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# ---------------------------
# NOTIFICAÇÃO
# ---------------------------
class Notificacao(Base):
    __tablename__ = "notificacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    canal = Column(String, index=True)  # 'sms' | 'whatsapp'
    destinatario = Column(String, index=True)
    mensagem = Column(Text)
    payload = Column(JSON, nullable=True)
    provider_response = Column(JSON, nullable=True)
    provider_id = Column(String, nullable=True, index=True)  # Twilio SID
    status = Column(String, index=True)  # 'sent' | 'delivered' | 'failed' | 'queued'
    erro = Column(Text, nullable=True)
    # New fields expected by notifications service
    idempotency_key = Column(String, nullable=True, index=True)
    attempts = Column(Integer, nullable=True, default=0)
    max_attempts = Column(Integer, nullable=True, default=5)
    last_error = Column(Text, nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        return {
            "id": self.id,
            "canal": self.canal,
            "destinatario": self.destinatario,
            "mensagem": self.mensagem,
            "payload": self.payload,
            "provider_response": self.provider_response,
            "provider_id": self.provider_id,
            "status": self.status,
            "erro": self.erro,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None
        }


# ---------------------------
# INTERESSE EM HORÁRIO
# ---------------------------
class Interesse(Base):
    __tablename__ = "interesses"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    funcionario_id = Column(Integer, ForeignKey("funcionarios.id"), nullable=True)
    data_hora_desejada = Column(DateTime, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Cliente")
    funcionario = relationship("Funcionario")


# ---------------------------
# FATURAMENTO SIMPLES (INVOICE)
# ---------------------------
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    estabelecimento_id = Column(
        Integer,
        ForeignKey("estabelecimentos.id"),
        nullable=False
    )

    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id"),
        nullable=False
    )

    descricao = Column(Text, nullable=True)

    # Valor armazenado em centavos para evitar problemas de ponto flutuante
    valor_centavos = Column(Integer, nullable=False)
    currency = Column(String, nullable=True, default="EUR")

    # Campos adicionais para tornar o faturamento mais rico/estruturado
    # tipo: 'servico_completo' | 'deposito' | 'saldo_restante' | etc.
    tipo = Column(String, nullable=True)
    # metodo_pagamento: 'pix' | 'cartao' | 'dinheiro' | 'link' | etc.
    metodo_pagamento = Column(String, nullable=True)
    # origem: de onde essa fatura foi gerada (whatsapp_confirmacao, link_pagamento, manual, ...)
    origem = Column(String, nullable=True)
    # campos para integrar com gateway de pagamento (ex.: Stripe/MercadoPago)
    gateway_payment_id = Column(String, nullable=True, index=True)
    gateway_status = Column(String, nullable=True)

    status = Column(String, nullable=False, default="em_aberto")  # em_aberto | pago | cancelado | reembolsado
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)


# ---------------------------
# HISTÓRICO
# ---------------------------
class Historico(Base):
    __tablename__ = "historicos"
    id = Column(Integer, primary_key=True, index=True)
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id"), nullable=False)
    acao = Column(String, nullable=False)
    detalhes = Column(Text, nullable=True)
    data_hora = Column(DateTime, server_default=func.now())
    agendamento = relationship("Agendamento", back_populates="historicos")


# ---------------------------
# PENDING ACTIONS (SERVER-SIDE QUEUE)
# ---------------------------
class PendingAction(Base):
    __tablename__ = "pending_actions"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    idempotency_key = Column(String, nullable=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    status = Column(String, nullable=False, default="pending")
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "payload": self.payload,
            "idempotency_key": self.idempotency_key,
            "attempts": self.attempts,
            "status": self.status,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }


