"""Database models - EPIC LEVEL with PostgreSQL."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import enum

from app.core.database import Base


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """Generate UUID string."""
    return str(uuid.uuid4())


# Enums
class AppointmentStatus(str, enum.Enum):
    """Appointment status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class NotificationStatus(str, enum.Enum):
    """Notification status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(str, enum.Enum):
    """Notification type."""
    PRE_CONFIRMATION = "pre_confirmation"
    OFFICIAL_CONFIRMATION = "official_confirmation"
    URGENT_CONFIRMATION = "urgent_confirmation"
    REMINDER_24H = "reminder_24h"
    REMINDER_2H = "reminder_2h"
    CANCELLATION = "cancellation"
    RESCHEDULE = "reschedule"


class InvoiceType(str, enum.Enum):
    """Invoice type."""
    DEPOSIT = "deposit"
    BALANCE = "balance"
    FULL = "full"
    REFUND = "refund"


class PaymentMethod(str, enum.Enum):
    """Payment method."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PIX = "pix"
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"


# ============================================
# MODELS
# ============================================

class Establishment(Base):
    """Establishment (Business) model."""
    __tablename__ = "establishments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    
    # Contact
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(Text)
    
    # Settings
    timezone = Column(String(50), default="UTC", nullable=False)
    default_language = Column(String(10), default="en", nullable=False)
    
    # Booking settings (JSONB for flexibility)
    booking_settings = Column(JSONB, default={})  # minLeadHours, quietHours, etc.
    
    # Trial & Subscription
    trial_end_date = Column(DateTime(timezone=True), nullable=False)
    active_plan = Column(Boolean, default=False, nullable=False)
    subscription_id = Column(String(255))
    stripe_customer_id = Column(String(255))
    subscription_current_period_end = Column(DateTime(timezone=True))
    
    # WhatsApp usage tracking
    whatsapp_messages_sent_this_month = Column(Integer, default=0, nullable=False)
    whatsapp_included_messages = Column(Integer, default=100, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    professionals = relationship("Professional", back_populates="establishment", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="establishment", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="establishment", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="establishment", cascade="all, delete-orphan")
    users = relationship("User", back_populates="establishment", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="establishment", cascade="all, delete-orphan")


class User(Base):
    """Admin user model."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    email = Column(String(255), nullable=False, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(200))
    
    # OAuth
    google_id = Column(String(255), unique=True, index=True)
    apple_id = Column(String(255), unique=True, index=True)
    
    # Password reset
    reset_code = Column(String(10))
    reset_code_expires = Column(DateTime(timezone=True))
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    establishment = relationship("Establishment", back_populates="users")


class Professional(Base):
    """Professional (Worker) model."""
    __tablename__ = "professionals"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(200), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    specialty = Column(String(200))
    bio = Column(Text)
    photo_url = Column(String(500))
    color = Column(String(20), default="#3B82F6")
    
    # Schedule (JSONB for flexibility - weekly templates, breaks, closures)
    weekly_schedule = Column(JSONB, default=[])
    breaks = Column(JSONB, default=[])
    closures = Column(JSONB, default=[])
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    establishment = relationship("Establishment", back_populates="professionals")
    appointments = relationship("Appointment", back_populates="professional")


class Service(Base):
    """Service model."""
    __tablename__ = "services"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(200), nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    buffer_before_minutes = Column(Integer, default=0, nullable=False)
    buffer_after_minutes = Column(Integer, default=0, nullable=False)
    
    price = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    
    # Deposit settings
    requires_deposit = Column(Boolean, default=False, nullable=False)
    deposit_percentage = Column(Float, default=0.0)  # 0-100
    
    color = Column(String(20), default="#10B981")
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Professional restrictions (JSONB array of professional IDs)
    professional_ids = Column(JSONB, default=[])  # Empty = all professionals
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    establishment = relationship("Establishment", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")


class Customer(Base):
    """Customer model."""
    __tablename__ = "customers"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(200), nullable=False)
    email = Column(String(255), index=True)
    phone = Column(String(50), index=True)
    language = Column(String(10), default="en", nullable=False)
    notes = Column(Text)
    
    # Opt-out preferences
    opt_out_whatsapp = Column(Boolean, default=False, nullable=False)
    opt_out_email = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    establishment = relationship("Establishment", back_populates="customers")
    appointments = relationship("Appointment", back_populates="customer")


class Appointment(Base):
    """Appointment model with anti-double-booking."""
    __tablename__ = "appointments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(String, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True)
    professional_id = Column(String, ForeignKey("professionals.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.CONFIRMED, nullable=False, index=True)
    language = Column(String(10), default="en", nullable=False)
    
    notes = Column(Text)
    
    # Customer snapshot (denormalized for quick access)
    customer_name = Column(String(200), nullable=False)
    customer_email = Column(String(255))
    customer_phone = Column(String(50))
    
    # Tokens
    confirmation_token = Column(String(100), unique=True, nullable=False, default=generate_uuid, index=True)
    
    # Idempotency (prevent double-booking on retry)
    idempotency_key = Column(String(100), unique=True, index=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    establishment = relationship("Establishment", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    professional = relationship("Professional", back_populates="appointments")
    customer = relationship("Customer", back_populates="appointments")
    notifications = relationship("Notification", back_populates="appointment", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="appointment", cascade="all, delete-orphan")


class Notification(Base):
    """Notification queue model."""
    __tablename__ = "notifications"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    type = Column(SQLEnum(NotificationType), nullable=False)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False, index=True)
    
    scheduled_for = Column(DateTime(timezone=True), nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    
    recipient_phone = Column(String(50))
    recipient_email = Column(String(255))
    language = Column(String(10), default="en", nullable=False)
    
    message_body = Column(Text)
    
    # Provider tracking
    provider = Column(String(50))  # "whatsapp", "email"
    provider_message_id = Column(String(255))
    provider_error = Column(Text)
    
    # Retry tracking
    retry_count = Column(Integer, default=0, nullable=False)
    last_retry_at = Column(DateTime(timezone=True))
    
    # Idempotency
    idempotency_key = Column(String(100), unique=True, nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    
    # Relationships
    appointment = relationship("Appointment", back_populates="notifications")


class Invoice(Base):
    """Invoice model with PDF generation support."""
    __tablename__ = "invoices"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id", ondelete="SET NULL"))
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"))
    
    # Invoice details
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    invoice_date = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    due_date = Column(DateTime(timezone=True))
    
    type = Column(SQLEnum(InvoiceType), nullable=False)
    
    # Amounts
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    
    # Payment
    payment_method = Column(SQLEnum(PaymentMethod))
    payment_status = Column(String(50), default="pending", nullable=False)
    paid_at = Column(DateTime(timezone=True))
    
    # Stripe integration
    stripe_payment_intent_id = Column(String(255))
    stripe_charge_id = Column(String(255))
    
    # PDF
    pdf_url = Column(String(500))
    pdf_generated_at = Column(DateTime(timezone=True))
    
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    establishment = relationship("Establishment", back_populates="invoices")
    appointment = relationship("Appointment", back_populates="invoices")


class AgendaImport(Base):
    """Agenda import tracking (Google Calendar, iCal, CSV)."""
    __tablename__ = "agenda_imports"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    establishment_id = Column(String, ForeignKey("establishments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    source_type = Column(String(50), nullable=False)  # "google_calendar", "ical", "csv"
    source_identifier = Column(String(500))  # Calendar ID, file name, etc.
    
    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    
    # Statistics
    total_items = Column(Integer, default=0)
    imported_items = Column(Integer, default=0)
    skipped_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    error_log = Column(JSONB, default=[])
    
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class WebhookEvent(Base):
    """Webhook event for idempotency (Stripe, WhatsApp)."""
    __tablename__ = "webhook_events"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    
    payload = Column(JSONB)
    processed = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at = Column(DateTime(timezone=True))
