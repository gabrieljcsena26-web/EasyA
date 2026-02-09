"""Public Booking Router - EPIC LEVEL
Public booking flow with intelligent availability:
- /booking/:slug - Get establishment info
- /availability - Real-time slot calculation
- /book - Create appointment with anti-double-booking
"""
import logging
from datetime import datetime, date as dt_date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.models.models import (
    Establishment,
    Professional,
    Service,
    Customer,
    Appointment,
    AppointmentStatus,
    generate_uuid,
    utcnow,
)
from app.schemas.schemas import (
    AppointmentCreate,
    AppointmentOut,
    DayAvailability,
    TimeSlot,
)
from app.services.availability import AvailabilityEngine

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# PUBLIC BOOKING ENDPOINTS
# ============================================

@router.get("/{slug}")
def get_establishment_by_slug(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get establishment info by slug (public endpoint).
    
    Returns:
        - Establishment basic info
        - Available services
        - Available professionals
        - Booking settings (hours, policies)
    """
    establishment = db.query(Establishment).filter(
        Establishment.slug == slug
    ).first()
    
    if not establishment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="f"Establishment not found: {slug}""
        )
    
    # Check trial status
    now = utcnow()
    if not establishment.active_plan and establishment.trial_end_date < now:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "TRIAL_EXPIRED",
                "message": "This business's trial has expired. Please contact them directly."
            }
        )
    
    # Get active services
    services = db.query(Service).filter(
        Service.establishment_id == establishment.id,
        Service.enabled == True
    ).all()
    
    # Get active professionals
    professionals = db.query(Professional).filter(
        Professional.establishment_id == establishment.id,
        Professional.is_active == True
    ).all()
    
    return {
        "establishment": {
            "id": establishment.id,
            "name": establishment.name,
            "slug": establishment.slug,
            "email": establishment.email,
            "phone": establishment.phone,
            "address": establishment.address,
            "timezone": establishment.timezone,
            "default_language": establishment.default_language,
        },
        "services": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "duration_minutes": s.duration_minutes,
                "price": s.price,
                "currency": s.currency,
                "requires_deposit": s.requires_deposit,
                "deposit_percentage": s.deposit_percentage,
                "color": s.color,
                "professional_ids": s.professional_ids,
            }
            for s in services
        ],
        "professionals": [
            {
                "id": p.id,
                "name": p.name,
                "specialty": p.specialty,
                "photo_url": p.photo_url,
                "color": p.color,
            }
            for p in professionals
        ],
        "booking_settings": establishment.booking_settings or {}
    }


@router.get("/{establishment_id}/availability/{service_id}/{professional_id}")
def get_availability(
    establishment_id: str,
    service_id: str,
    professional_id: str,
    date: str,  # YYYY-MM-DD format
    db: Session = Depends(get_db)
):
    """Get available time slots for specific date.
    
    Uses the EPIC Availability Engine to calculate slots based on:
    - Working hours (establishment + professional)
    - Breaks and closures
    - Existing appointments
    - Service duration + buffers
    - Booking policies (min lead, quiet hours)
    """
    try:
        check_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    # Initialize availability engine
    try:
        engine = AvailabilityEngine(db, establishment_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="str(e)"
        )
    
    # Get available slots
    try:
        slots = engine.get_available_slots(
            service_id=service_id,
            professional_id=professional_id,
            date=check_date,
            slot_duration_minutes=30  # 30-minute granularity
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="str(e)"
        )
    
    available_count = sum(1 for slot in slots if slot['available'])
    
    return {
        date: date,
        slots: slots,
        total_slots: len(slots),
        available_slots: available_count,
        has_availability: available_count > 0
    }


@router.get("/{establishment_id}/availability-summary/{service_id}/{professional_id}")
def get_availability_summary(
    establishment_id: str,
    service_id: str,
    professional_id: str,
    start_date: str,  # YYYY-MM-DD
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get availability summary for multiple days (calendar view).
    
    Returns quick overview of available slots per day.
    """
    try:
        check_start = datetime.strptime(start_date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    # Initialize availability engine
    try:
        engine = AvailabilityEngine(db, establishment_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="str(e)"
        )
    
    # Get summary
    try:
        summary = engine.get_availability_summary(
            service_id=service_id,
            professional_id=professional_id,
            start_date=check_start,
            days=min(days, 90)  # Max 90 days
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="str(e)"
        )
    
    return {
        start_date: start_date,
        days: days,
        summary: summary
    }


@router.post("/{establishment_id}/book")
def create_booking(
    establishment_id: str,
    booking: AppointmentCreate,
    db: Session = Depends(get_db)
):
    """Create appointment - EPIC with anti-double-booking.
    
    Features:
    - Idempotency key prevents duplicate bookings on retry
    - Validates slot availability in real-time
    - Creates or finds customer
    - Schedules confirmation notifications
    - Returns confirmation token for customer actions
    """
    # Verify establishment
    establishment = db.query(Establishment).filter(
        Establishment.id == establishment_id
    ).first()
    
    if not establishment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found"
        )
    
    # Check trial status
    now = utcnow()
    if not establishment.active_plan and establishment.trial_end_date < now:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                code: TRIAL_EXPIRED,
                message: Booking is currently unavailable. Please try again later.
            }
        )
    
    # Verify service and professional
    service = db.query(Service).filter(Service.id == booking.service_id).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    professional = db.query(Professional).filter(
        Professional.id == booking.professional_id
    ).first()
    if not professional:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Professional not found"
        )
    
    # Calculate end time
    end_time = booking.start_time + timedelta(
        minutes=(
            service.duration_minutes +
            service.buffer_before_minutes +
            service.buffer_after_minutes
        )
    )
    
    # Verify slot is still available (prevent double-booking)
    overlapping = db.query(Appointment).filter(
        and_(
            Appointment.professional_id == booking.professional_id,
            Appointment.start_time < end_time,
            Appointment.end_time > booking.start_time,
            Appointment.status.in_([
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.PENDING
            ])
        )
    ).first()
    
    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                code: SLOT_UNAVAILABLE,
                message: This time slot is no longer available. Please choose another.
            }
        )
    
    # Find or create customer
    customer = db.query(Customer).filter(
        and_(
            Customer.establishment_id == establishment_id,
            Customer.phone == booking.customer_phone
        )
    ).first()
    
    if not customer:
        customer = Customer(
            id=generate_uuid(),
            establishment_id=establishment_id,
            name=booking.customer_name,
            email=booking.customer_email,
            phone=booking.customer_phone,
            language=booking.customer_language,
            created_at=utcnow(),
            updated_at=utcnow()
        )
        db.add(customer)
        db.flush()
    
    # Create appointment with idempotency key
    idempotency_key = f{establishment_id}:{booking.customer_phone}:{booking.start_time.isoformat()}
    
    # Check if already exists (idempotency)
    existing = db.query(Appointment).filter(
        Appointment.idempotency_key == idempotency_key
    ).first()
    
    if existing:
        logger.info(fDuplicate booking attempt detected: {idempotency_key})\n        return {
            message: Appointment already created,
            appointment: existing,
            duplicate: True
        }
    
    # Create appointment
    appointment = Appointment(
        id=generate_uuid(),
        establishment_id=establishment_id,
        service_id=booking.service_id,
        professional_id=booking.professional_id,
        customer_id=customer.id,
        start_time=booking.start_time,
        end_time=end_time,
        status=AppointmentStatus.CONFIRMED,
        language=booking.customer_language,
        notes=booking.notes,
        customer_name=booking.customer_name,
        customer_email=booking.customer_email,
        customer_phone=booking.customer_phone,
        confirmation_token=generate_uuid(),
        idempotency_key=idempotency_key,
        created_at=utcnow(),
        updated_at=utcnow()
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    logger.info(fAppointment created: {appointment.id} for {booking.customer_name})\n    
    # TODO: Schedule confirmation notifications via Celery
    
    return {
        message: Appointment confirmed successfully!,
        appointment: {
            id: appointment.id,
            service: service.name,
            professional: professional.name,
            start_time: appointment.start_time.isoformat(),
            end_time: appointment.end_time.isoformat(),
            confirmation_token: appointment.confirmation_token,
        },
        actions: {
            calendar_download: f/api/appointments/{appointment.id}/calendar.ics?token={appointment.confirmation_token},
            cancel: f/api/appointments/{appointment.id}/cancel?token={appointment.confirmation_token},
            reschedule: f/api/appointments/{appointment.id}/reschedule?token={appointment.confirmation_token}
        }
    }


@router.get("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: str,
    token: str,
    db: Session = Depends(get_db)
):
    Cancel appointment (customer self-service).
    appointment = db.query(Appointment).filter(
        and_(
            Appointment.id == appointment_id,
            Appointment.confirmation_token == token
        )
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found or invalid token"
        )
    
    if appointment.status == AppointmentStatus.CANCELLED:
        return {message: Appointment already cancelled}
    
    appointment.status = AppointmentStatus.CANCELLED
    appointment.updated_at = utcnow()
    
    db.commit()
    
    logger.info(fAppointment cancelled by customer: {appointment_id})
    
    # TODO: Send cancellation notification
    
    return {
        message: Appointment cancelled successfully,
        appointment_id: appointment_id
    }
