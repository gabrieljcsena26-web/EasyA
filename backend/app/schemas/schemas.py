# Interesse (waitlist)
from typing import Optional
from pydantic import BaseModel, root_validator, validator
from datetime import datetime


class InteresseBase(BaseModel):
    cliente_id: int
    funcionario_id: Optional[int] = None
    data_hora_desejada: Optional[datetime] = None


class InteresseCreate(InteresseBase):
    pass


class InteresseOut(InteresseBase):
    id: int
    criado_em: datetime

    class Config:
        orm_mode = True


class EstabelecimentoBase(BaseModel):
    nome: str
    telefone: str
    slug: str
    email: str | None = None
    idioma_padrao: str | None = None
    lembrete_horas_antes: list[int] | None = None
    horario_inicio: int | None = None
    horario_fim: int | None = None
    timezone: str | None = None
    # Business-local clock helpers for frontend date-range generation.
    # NOTE: These are informational; booking rules are enforced on the backend.
    today_local: str | None = None  # YYYY-MM-DD in business timezone
    now_local_iso: str | None = None  # ISO datetime in business timezone (includes offset when available)
    photos: list[str] | None = None
    reviews: list[dict] | None = None


class EstabelecimentoCreate(EstabelecimentoBase):
    pass


class EstabelecimentoOut(EstabelecimentoBase):
    id: int

    class Config:
        orm_mode = True


class ClienteBase(BaseModel):
    nome: str
    telefone: str
    observacoes: str
    tipo_servico: str
    idioma: str | None = "pt-BR"


class ClienteCreate(ClienteBase):
    pass


class ClienteOut(ClienteBase):
    id: int

    class Config:
        orm_mode = True


class ServiceOut(BaseModel):
    id: int
    name: str
    duration_min: int
    buffer_min: int | None = None
    price_cents: int
    display_interval_min: int

    class Config:
        orm_mode = True


class ProfessionalOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class BookingDepositRuleOut(BaseModel):
    enabled: bool = False
    deposit_percent_of_service: int = 50
    no_show_retain_percent_of_service: int = 15
    no_show_refund_percent_of_service: int = 35
    popup_text: str | None = None


class ConfigOut(BaseModel):
    services: list[ServiceOut]
    professionals: list[ProfessionalOut]
    business: EstabelecimentoOut | None = None
    deposit_rule: BookingDepositRuleOut | None = None


class AgendamentoBase(BaseModel):
    cliente_id: int
    funcionario_id: int
    descricao: str | None = None
    data_hora: datetime


class AgendamentoCreate(AgendamentoBase):
    pass


class AgendamentoOut(AgendamentoBase):
    id: int
    status: str | None = None
    updated_at: datetime | None = None

    class Config:
        orm_mode = True


class AppointmentCreate(BaseModel):
    service_id: int
    professional_id: int
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    channel: str = "landing"
    customer_name: str = "Cliente"
    customer_whatsapp: str
    customer_lang: str | None = None

    @root_validator(pre=True)
    def _coerce_legacy_keys(cls, values):
        # Accept older/camelCase payloads to reduce 422s in production.
        if not isinstance(values, dict):
            return values

        # Unwrap common envelope shapes like {appointment:{...}} or {payload:{...}}.
        for envelope_key in ("appointment", "payload", "data"):
            inner = values.get(envelope_key)
            if isinstance(inner, dict):
                for k, v in inner.items():
                    if k not in values and v is not None:
                        values[k] = v

        # Accept nested customer objects.
        for customer_key in ("customer", "cliente", "client"):
            cust = values.get(customer_key)
            if not isinstance(cust, dict):
                continue
            if values.get("customer_name") is None:
                v = cust.get("customer_name") or cust.get("customerName") or cust.get("name") or cust.get("nome")
                if v is not None:
                    values["customer_name"] = v
            if values.get("customer_whatsapp") is None:
                v = (
                    cust.get("customer_whatsapp")
                    or cust.get("customerWhatsapp")
                    or cust.get("whatsapp")
                    or cust.get("phone")
                    or cust.get("phoneNumber")
                    or cust.get("telefone")
                )
                if v is not None:
                    values["customer_whatsapp"] = v

        def _pick(*keys):
            for k in keys:
                if k in values and values.get(k) is not None:
                    return values.get(k)
            return None

        mapped = {
            "service_id": _pick("service_id", "serviceId", "serviceID"),
            "professional_id": _pick(
                "professional_id",
                "professionalId",
                "professionalID",
                "staff_id",
                "staffId",
                "funcionario_id",
                "funcionarioId",
            ),
            "start_time": _pick("start_time", "startTime", "start", "slot", "slotTime", "time"),
            "customer_name": _pick("customer_name", "customerName", "name"),
            "customer_whatsapp": _pick(
                "customer_whatsapp",
                "customerWhatsapp",
                "whatsapp",
                "phone",
                "phoneNumber",
                "telefone",
            ),
            "channel": _pick("channel", "source", "origin", "utm_source"),
            "date": _pick("date", "dateISO", "day", "selectedDate", "dayISO"),
            "customer_lang": _pick(
                "customer_lang",
                "customerLang",
                "lang",
                "language",
                "idioma",
                "locale",
                "uiLang",
            ),
        }

        for target, val in mapped.items():
            if target not in values and val is not None:
                values[target] = val

        return values

    @validator("date", "start_time", "customer_name", "customer_whatsapp", "channel", "customer_lang", pre=True)
    def _strip_strings(cls, v):
        if v is None:
            return v
        return str(v).strip()


class AppointmentOut(BaseModel):
    id: int
    service_id: int
    professional_id: int
    date: str
    start_time: str
    duration_min: int
    buffer_min: int
    status: str
    customer_name: str
    customer_whatsapp: str


class NotificacaoCreate(BaseModel):
    canal: str
    destinatario: str
    mensagem: str
    agendamento_id: int | None = None


class NotificacaoOut(BaseModel):
    id: int
    canal: str
    destinatario: str
    mensagem: str
    status: str
    provider_response: dict | None = None
    erro: str | None = None
    criado_em: datetime

    class Config:
        orm_mode = True


class HistoricoOut(BaseModel):
    id: int
    agendamento_id: int
    acao: str
    detalhes: str | None = None
    data_hora: datetime

    class Config:
        orm_mode = True


class InvoiceBase(BaseModel):
    cliente_id: int
    descricao: str | None = None
    valor_centavos: int
    currency: str | None = "EUR"
    tipo: str | None = None
    metodo_pagamento: str | None = None
    origem: str | None = None
    gateway_payment_id: str | None = None
    gateway_status: str | None = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceOut(InvoiceBase):
    id: int
    status: str
    created_at: datetime
    paid_at: datetime | None = None

    class Config:
        orm_mode = True
