"""Database models for EasyAgenda."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from enum import Enum
import uuid


def utcnow() -> datetime:
    """Get current UTC time with timezone."""
    return datetime.now(timezone.utc)


def generate_id() -> str:
    """Generate UUID string."""
    return str(uuid.uuid4())


class AppointmentStatus(str, Enum):
    """Appointment status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class NotificationStatus(str, Enum):
    """Notification status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(str, Enum):
    """Notification type."""
    CONFIRMATION = "confirmation"
    REMINDER_24H = "reminder_24h"
    REMINDER_2H = "reminder_2h"
    CANCELLATION = "cancellation"
    RESCHEDULE = "reschedule"


class DayOfWeek(str, Enum):
    """Day of week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class WeeklySchedule(BaseModel):
    """Weekly schedule template."""
    day: DayOfWeek
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format
    enabled: bool = True


class BreakPeriod(BaseModel):
    """Break period."""
    id: str = Field(default_factory=generate_id)
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None


class Closure(BaseModel):
    """Closure period."""
    id: str = Field(default_factory=generate_id)
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None


# Establishment (Business)
class EstablishmentBase(BaseModel):
    """Establishment base model."""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z0-9-]+$')
    timezone: str = Field(default="UTC")  # e.g., "America/Sao_Paulo"
    default_language: str = Field(default="en")  # e.g., "en", "es", "pt", "de", "it", "fr"
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    
    # Booking settings
    confirmation_policy_hours: int = Field(default=2)  # Minimum hours ahead for booking
    cancellation_policy_hours: int = Field(default=24)  # Minimum hours for cancellation
    
    # WhatsApp budget (Mode B)
    whatsapp_included_messages: int = Field(default=100)
    whatsapp_overage_price: float = Field(default=0.05)  # Per message


class EstablishmentCreate(EstablishmentBase):
    """Create establishment."""
    pass


class Establishment(EstablishmentBase):
    """Establishment model."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    
    # Trial and subscription
    trial_end_date: datetime = Field(default_factory=lambda: utcnow() + timedelta(days=4))
    active_plan: bool = Field(default=False)
    subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    subscription_current_period_end: Optional[datetime] = None
    
    # Usage tracking
    whatsapp_messages_sent_this_month: int = Field(default=0)
    last_webhook_event_id: Optional[str] = None


# Professional (Worker)
class ProfessionalBase(BaseModel):
    """Professional base model."""
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    color: str = Field(default="#3B82F6")  # For calendar display


class ProfessionalCreate(ProfessionalBase):
    """Create professional."""
    establishment_id: str


class Professional(ProfessionalBase):
    """Professional model."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    establishment_id: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    
    # Schedule
    weekly_schedule: List[WeeklySchedule] = Field(default_factory=list)
    breaks: List[BreakPeriod] = Field(default_factory=list)
    closures: List[Closure] = Field(default_factory=list)


# Service
class ServiceBase(BaseModel):
    """Service base model."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    duration_minutes: int = Field(..., gt=0, le=480)  # Max 8 hours
    buffer_before_minutes: int = Field(default=0, ge=0)
    buffer_after_minutes: int = Field(default=0, ge=0)
    price: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD")
    color: str = Field(default="#10B981")  # For calendar display
    enabled: bool = Field(default=True)


class ServiceCreate(ServiceBase):
    """Create service."""
    establishment_id: str
    professional_ids: List[str] = Field(default_factory=list)  # Empty = all professionals


class Service(ServiceBase):
    """Service model."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    establishment_id: str
    professional_ids: List[str] = Field(default_factory=list)  # Empty = all professionals
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# Customer
class CustomerBase(BaseModel):
    """Customer base model."""
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    language: str = Field(default="en")
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    """Create customer."""
    establishment_id: str


class Customer(CustomerBase):
    """Customer model."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    establishment_id: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    
    # Preferences
    opt_out_whatsapp: bool = Field(default=False)
    opt_out_email: bool = Field(default=False)
    opt_out_sms: bool = Field(default=False)


# Appointment
class AppointmentBase(BaseModel):
    """Appointment base model."""
    service_id: str
    professional_id: str
    customer_id: str
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    """Create appointment."""
    establishment_id: str
    customer_name: str
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    customer_language: str = Field(default="en")


class Appointment(AppointmentBase):
    """Appointment model."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    establishment_id: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    
    status: AppointmentStatus = Field(default=AppointmentStatus.CONFIRMED)
    language: str = Field(default="en")  # Language for notifications
    
    # Tokens for public access
    confirmation_token: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Customer snapshot (denormalized for easy access)
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None


# User (Admin)
class UserBase(BaseModel):
    """User base model."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Create user."""
    password: str = Field(..., min_length=8)
    establishment_id: str


class User(UserBase):
    """User model."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    establishment_id: str
    hashed_password: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    
    # Password reset
    reset_code: Optional[str] = None
    reset_code_expires: Optional[datetime] = None
    
    is_active: bool = Field(default=True)


# Notification
class NotificationBase(BaseModel):
    """Notification base model."""
    appointment_id: str
    type: NotificationType
    scheduled_for: datetime
    recipient_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    language: str = Field(default="en")


class NotificationCreate(NotificationBase):
    """Create notification."""
    establishment_id: str


class Notification(NotificationBase):
    """Notification model."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    establishment_id: str
    created_at: datetime = Field(default_factory=utcnow)
    
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)
    sent_at: Optional[datetime] = None
    
    # Provider tracking
    provider: Optional[str] = None  # "whatsapp", "email", "sms"
    provider_message_id: Optional[str] = None
    provider_error: Optional[str] = None
    
    # Retry tracking
    retry_count: int = Field(default=0)
    last_retry_at: Optional[datetime] = None


# Webhook Event (for idempotency)
class WebhookEvent(BaseModel):
    """Webhook event for idempotency."""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=generate_id)
    event_id: str  # External event ID from provider
    provider: str  # "stripe", "whatsapp", etc.
    event_type: str
    processed_at: datetime = Field(default_factory=utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
