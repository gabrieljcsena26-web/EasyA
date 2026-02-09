from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.orm import relationship, declarative_base
import enum
from datetime import datetime

Base = declarative_base()

# Enum para status de agendamento
class StatusAgendamento(str, enum.Enum):
    pendente = "pendente"
    confirmado = "confirmado"
    cancelado = "cancelado"

# Estabelecimento / Dono
class Estabelecimento(Base):
    __tablename__ = "estabelecimentos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=True)
    funcionarios = relationship("Funcionario", back_populates="estabelecimento")
    clientes = relationship("Cliente", back_populates="estabelecimento")

# Profissional / Funcionário
class Funcionario(Base):
    __tablename__ = "funcionarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"))
    estabelecimento = relationship("Estabelecimento", back_populates="funcionarios")
    agendamentos = relationship("Agendamento", back_populates="profissional")

# Cliente
class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=False)
    observacoes = Column(Text, nullable=True)
    tipo_servico = Column(String, nullable=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"))
    estabelecimento = relationship("Estabelecimento", back_populates="clientes")
    agendamentos = relationship("Agendamento", back_populates="cliente")

# Agendamento
class Agendamento(Base):
    __tablename__ = "agendamentos"
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    profissional_id = Column(Integer, ForeignKey("funcionarios.id"))
    data_hora = Column(DateTime, nullable=False)
    status = Column(Enum(StatusAgendamento), default=StatusAgendamento.pendente)
    observacoes = Column(Text, nullable=True)
    confirmado_sms = Column(Boolean, default=False)  # Se o cliente confirmou via SMS
    cliente = relationship("Cliente", back_populates="agendamentos")
    profissional = relationship("Funcionario", back_populates="agendamentos")
    historicos = relationship("Historico", back_populates="agendamento")

# Histórico de ações
class Historico(Base):
    __tablename__ = "historicos"
    id = Column(Integer, primary_key=True, index=True)
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id"))
    acao = Column(String, nullable=False)  # ex: criado, alterado, SMS enviado
    detalhes = Column(Text, nullable=True)  # Observações adicionais
    data_hora = Column(DateTime, default=datetime.utcnow)
    agendamento = relationship("Agendamento", back_populates="historicos")
