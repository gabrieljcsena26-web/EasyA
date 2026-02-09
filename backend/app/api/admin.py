"""Admin Configuration Router - EPIC DASHBOARD SETUP
Complete configuration management for:
- Establishment settings (hours, timezone, policies)
- Professionals (schedules, breaks, days off)
- Services (pricing, duration, buffers)
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Establishment, Professional, Service, generate_uuid, utcnow
from app.schemas.schemas import (
    EstablishmentConfig,
    ProfessionalConfig,
    ProfessionalCreate,
    ProfessionalOut,
    ServiceConfig,
    ServiceCreate,
    ServiceOut,
    AdminConfigComplete,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# ESTABLISHMENT CONFIG - THE BRAIN
# ============================================

@router.get("/config/{establishment_id}")
def get_establishment_config(
    establishment_id: str,
    db: Session = Depends(get_db)
):
    """Get complete establishment configuration.
    
    Returns:
        - Establishment settings (hours, timezone, policies)
        - All professionals with schedules
        - All services with pricing
    """
    # Get establishment
    establishment = db.query(Establishment).filter(
        Establishment.id == establishment_id
    ).first()
    
    if not establishment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found"
        )
    
    # Get professionals
    professionals = db.query(Professional).filter(
        Professional.establishment_id == establishment_id,
        Professional.is_active == True
    ).all()
    
    # Get services
    services = db.query(Service).filter(
        Service.establishment_id == establishment_id,
        Service.enabled == True
    ).all()
    
    return {
        "establishment": establishment,
        "professionals": professionals,
        "services": services,
        "booking_settings": establishment.booking_settings or {}
    }


@router.put("/config/{establishment_id}")
def update_establishment_config(
    establishment_id: str,
    config: EstablishmentConfig,
    db: Session = Depends(get_db)
):
    """Update establishment configuration - EPIC SETUP.
    
    Updates:
    - Business info (name, contact, timezone)
    - Working hours (weekly schedule)
    - Booking policies (min lead, quiet hours)
    - Default breaks
    """
    establishment = db.query(Establishment).filter(
        Establishment.id == establishment_id
    ).first()
    
    if not establishment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found"
        )
    
    # Update basic info
    establishment.name = config.name
    establishment.email = config.email
    establishment.phone = config.phone
    establishment.address = config.address
    establishment.timezone = config.timezone
    establishment.default_language = config.default_language
    
    # Update booking settings
    booking_settings = {
        "min_lead_hours": config.min_lead_hours,
        "confirmation_policy_hours": config.confirmation_policy_hours,
        "quiet_hours_start": config.quiet_hours_start,
        "quiet_hours_end": config.quiet_hours_end,
        "weekly_schedule": [item.model_dump() for item in config.weekly_schedule],
        "daily_breaks": [item.model_dump() for item in config.daily_breaks],
    }
    
    establishment.booking_settings = booking_settings
    establishment.updated_at = utcnow()
    
    db.commit()
    db.refresh(establishment)
    
    logger.info(f"Establishment config updated: {establishment_id}")
    
    return {
        "message": "Configuration updated successfully",
        "establishment": establishment
    }


# ============================================
# PROFESSIONALS MANAGEMENT
# ============================================

@router.post("/professionals")
def create_professional(
    professional: ProfessionalCreate,
    db: Session = Depends(get_db)
):
    """Create professional with individual schedule."""
    # Verify establishment exists
    establishment = db.query(Establishment).filter(
        Establishment.id == professional.establishment_id
    ).first()
    
    if not establishment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found"
        )
    
    # Create professional
    db_professional = Professional(
        id=generate_uuid(),
        establishment_id=professional.establishment_id,
        name=professional.name,
        email=professional.email,
        phone=professional.phone,
        specialty=professional.specialty,
        color=professional.color,
        weekly_schedule=(
            [item.model_dump() for item in professional.weekly_schedule]
            if professional.weekly_schedule else []
        ),
        breaks=(
            [item.model_dump() for item in professional.breaks]
            if professional.breaks else []
        ),
        closures=professional.closures or [],
        is_active=True,
        created_at=utcnow(),
        updated_at=utcnow()
    )
    
    db.add(db_professional)
    db.commit()
    db.refresh(db_professional)
    
    logger.info(f"Professional created: {db_professional.id} - {db_professional.name}")
    
    return db_professional


@router.get("/professionals/{establishment_id}", response_model=List[ProfessionalOut])
def get_professionals(
    establishment_id: str,
    db: Session = Depends(get_db)
):
    """Get all professionals for establishment."""
    professionals = db.query(Professional).filter(
        Professional.establishment_id == establishment_id,
        Professional.is_active == True
    ).all()
    
    return professionals


@router.put("/professionals/{professional_id}")
def update_professional(
    professional_id: str,
    config: ProfessionalConfig,
    db: Session = Depends(get_db)
):
    """Update professional configuration - schedules, breaks, etc."""
    professional = db.query(Professional).filter(
        Professional.id == professional_id
    ).first()
    
    if not professional:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Professional not found"
        )
    
    # Update info
    professional.name = config.name
    professional.email = config.email
    professional.phone = config.phone
    professional.specialty = config.specialty
    professional.color = config.color
    
    # Update schedule if provided
    if config.weekly_schedule is not None:
        professional.weekly_schedule = [
            item.model_dump() for item in config.weekly_schedule
        ]
    
    if config.breaks is not None:
        professional.breaks = [
            item.model_dump() for item in config.breaks
        ]
    
    if config.closures is not None:
        professional.closures = config.closures
    
    professional.updated_at = utcnow()
    
    db.commit()
    db.refresh(professional)
    
    logger.info(f"Professional updated: {professional_id}")
    
    return professional


@router.delete("/professionals/{professional_id}")
def delete_professional(
    professional_id: str,
    db: Session = Depends(get_db)
):
    """Soft delete professional."""
    professional = db.query(Professional).filter(
        Professional.id == professional_id
    ).first()
    
    if not professional:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Professional not found"
        )
    
    professional.is_active = False
    professional.updated_at = utcnow()
    
    db.commit()
    
    logger.info(f"Professional deleted: {professional_id}")
    
    return {"message": "Professional deleted successfully"}


# ============================================
# SERVICES MANAGEMENT
# ============================================

@router.post("/services")
def create_service(
    service: ServiceCreate,
    db: Session = Depends(get_db)
):
    """Create service with pricing, duration, buffers."""
    # Verify establishment exists
    establishment = db.query(Establishment).filter(
        Establishment.id == service.establishment_id
    ).first()
    
    if not establishment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found"
        )
    
    # Create service
    db_service = Service(
        id=generate_uuid(),
        establishment_id=service.establishment_id,
        name=service.name,
        description=service.description,
        duration_minutes=service.duration_minutes,
        buffer_before_minutes=service.buffer_before_minutes,
        buffer_after_minutes=service.buffer_after_minutes,
        price=service.price,
        currency=service.currency,
        requires_deposit=service.requires_deposit,
        deposit_percentage=service.deposit_percentage,
        color=service.color,
        professional_ids=service.professional_ids,
        enabled=True,
        created_at=utcnow(),
        updated_at=utcnow()
    )
    
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    
    logger.info(f"Service created: {db_service.id} - {db_service.name}")
    
    return db_service


@router.get("/services/{establishment_id}", response_model=List[ServiceOut])
def get_services(
    establishment_id: str,
    db: Session = Depends(get_db)
):
    """Get all services for establishment."""
    services = db.query(Service).filter(
        Service.establishment_id == establishment_id,
        Service.enabled == True
    ).all()
    
    return services


@router.put("/services/{service_id}")
def update_service(
    service_id: str,
    config: ServiceConfig,
    db: Session = Depends(get_db)
):
    """Update service configuration."""
    service = db.query(Service).filter(
        Service.id == service_id
    ).first()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Update all fields
    service.name = config.name
    service.description = config.description
    service.duration_minutes = config.duration_minutes
    service.buffer_before_minutes = config.buffer_before_minutes
    service.buffer_after_minutes = config.buffer_after_minutes
    service.price = config.price
    service.currency = config.currency
    service.requires_deposit = config.requires_deposit
    service.deposit_percentage = config.deposit_percentage
    service.color = config.color
    service.professional_ids = config.professional_ids
    service.updated_at = utcnow()
    
    db.commit()
    db.refresh(service)
    
    logger.info(f"Service updated: {service_id}")
    
    return service


@router.delete("/services/{service_id}")
def delete_service(
    service_id: str,
    db: Session = Depends(get_db)
):
    """Soft delete service."""
    service = db.query(Service).filter(
        Service.id == service_id
    ).first()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    service.enabled = False
    service.updated_at = utcnow()
    
    db.commit()
    
    logger.info(f"Service deleted: {service_id}")
    
    return {"message": "Service deleted successfully"}
