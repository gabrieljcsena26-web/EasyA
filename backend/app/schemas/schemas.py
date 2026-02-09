"""Pydantic schemas for API validation - EPIC LEVEL."""
from datetime import datetime, time as dt_time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator
from app.models.models import (
    AppointmentStatus,
    NotificationStatus,
    NotificationType,
    InvoiceType,
    PaymentMethod,
)


# ============================================
# ESTABLISHMENT SCHEMAS
# ============================================

class WeeklyScheduleItem(BaseModel):
    """Weekly schedule for a day."""
    day: str  # monday, tuesday, etc.
    enabled: bool = True
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format


class BreakPeriod(BaseModel):
    """Break period."""
    start_time: str  # HH:MM
    end_time: str    # HH:MM
    description: Optional[str] = None


class EstablishmentConfig(BaseModel):
    """Complete establishment configuration."""
    # Basic info
    name: str
    slug: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    timezone: str = "UTC"
    default_language: str = "en"
    
    # Booking settings
    min_lead_hours: int = 4
    confirmation_policy_hours: int = 24
    quiet_hours_start: str = "21:00"
    quiet_hours_end: str = "08:00"
    
    # Weekly schedule (default for business)
    weekly_schedule: List[WeeklyScheduleItem]
    
    # Breaks (default for business)
    daily_breaks: List[BreakPeriod] = []


class EstablishmentOut(BaseModel):
    """Establishment output."""
    id: str
    name: str
    slug: str
    email: Optional[str]
    phone: Optional[str]
    timezone: str
    default_language: str
    trial_end_date: datetime
    active_plan: bool
    
    class Config:
        from_attributes = True


# ============================================
# PROFESSIONAL SCHEMAS
# ============================================

class ProfessionalConfig(BaseModel):
    """Professional configuration."""
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    color: str = "#3B82F6"
    
    # Individual schedule (overrides establishment defaults)
    weekly_schedule: Optional[List[WeeklyScheduleItem]] = None
    breaks: Optional[List[BreakPeriod]] = None
    
    # Days off (specific dates)
    closures: Optional[List[Dict[str, str]]] = None  # [{start_date, end_date, reason}]


class ProfessionalCreate(ProfessionalConfig):
    """Create professional."""
    establishment_id: str


class ProfessionalOut(BaseModel):
    """Professional output."""
    id: str
    establishment_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    specialty: Optional[str]
    color: str
    weekly_schedule: List[Dict[str, Any]]
    breaks: List[Dict[str, Any]]
    is_active: bool
    
    class Config:
        from_attributes = True


# ============================================
# SERVICE SCHEMAS
# ============================================

class ServiceConfig(BaseModel):
    """Service configuration."""
    name: str
    description: Optional[str] = None
    duration_minutes: int = Field(..., gt=0, le=480)
    buffer_before_minutes: int = Field(default=0, ge=0)
    buffer_after_minutes: int = Field(default=0, ge=0)
    price: float = Field(default=0.0, ge=0)
    currency: str = "USD"
    color: str = "#10B981"
    
    # Deposit settings
    requires_deposit: bool = False
    deposit_percentage: float = Field(default=0.0, ge=0, le=100)
    
    # Professional restrictions (empty = all professionals can perform)
    professional_ids: List[str] = []


class ServiceCreate(ServiceConfig):
    """Create service."""
    establishment_id: str


class ServiceOut(BaseModel):
    """Service output."""
    id: str
    establishment_id: str
    name: str
    description: Optional[str]
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    price: float
    currency: str
    enabled: bool
    
    class Config:
        from_attributes = True


# ============================================
# APPOINTMENT SCHEMAS
# ============================================

class AppointmentCreate(BaseModel):
    """Create appointment (public booking)."""
    service_id: str
    professional_id: str
    start_time: datetime
    
    # Customer info
    customer_name: str
    customer_email: Optional[EmailStr] = None
    customer_phone: str
    customer_language: str = "en"
    
    notes: Optional[str] = None


class AppointmentOut(BaseModel):
    """Appointment output."""
    id: str
    establishment_id: str
    service_id: str
    professional_id: str
    customer_id: str
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    customer_name: str
    customer_phone: str
    language: str
    
    class Config:
        from_attributes = True


# ============================================
# AVAILABILITY SCHEMAS
# ============================================

class TimeSlot(BaseModel):
    """Available time slot."""
    time: str  # HH:MM format
    available: bool
    reason: Optional[str] = None  # If not available: "booked", "break", "closed", etc.


class DayAvailability(BaseModel):
    """Availability for a specific day."""
    date: str  # YYYY-MM-DD
    slots: List[TimeSlot]
    total_slots: int
    available_slots: int


# ============================================
# ADMIN CONFIG SCHEMA (THE EPIC ONE)
# ============================================

class AdminConfigComplete(BaseModel):
    """Complete admin configuration - EPIC DASHBOARD SETUP."""
    
    # Establishment settings
    establishment: EstablishmentConfig
    
    # Professionals with full schedule config
    professionals: List[ProfessionalConfig]
    
    # Services with pricing and timing
    services: List[ServiceConfig]


class AdminConfigOut(BaseModel):
    """Admin config output."""
    establishment: EstablishmentOut
    professionals: List[ProfessionalOut]
    services: List[ServiceOut]


# ============================================
# IMPORT SCHEMAS
# ============================================

class GoogleCalendarImportRequest(BaseModel):
    """Google Calendar import request."""
    calendar_id: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    default_service_id: Optional[str] = None
    default_professional_id: Optional[str] = None


class ICalImportRequest(BaseModel):
    """iCal file import request."""
    ical_content: str
    default_service_id: Optional[str] = None
    default_professional_id: Optional[str] = None


class CSVImportRequest(BaseModel):
    """CSV import request."""
    csv_content: str
    mapping: Dict[str, str]  # Column mappings


class ImportProgress(BaseModel):
    """Import progress."""
    import_id: str
    status: str
    total_items: int
    imported_items: int
    skipped_items: int
    failed_items: int
    error_log: List[str]


# ============================================
# INVOICE SCHEMAS
# ============================================

class InvoiceCreate(BaseModel):
    """Create invoice."""
    appointment_id: Optional[str] = None
    customer_id: str
    type: InvoiceType
    amount: float
    currency: str = "USD"
    payment_method: Optional[PaymentMethod] = None
    notes: Optional[str] = None


class InvoiceOut(BaseModel):
    """Invoice output."""
    id: str
    invoice_number: str
    invoice_date: datetime
    type: InvoiceType
    amount: float
    currency: str
    payment_status: str
    pdf_url: Optional[str]
    
    class Config:
        from_attributes = True


class MonthlyReport(BaseModel):
    """Monthly financial report."""
    month: str  # YYYY-MM
    total_revenue: float
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_show_count: int
    invoices: List[InvoiceOut]
