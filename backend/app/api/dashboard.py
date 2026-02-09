"""Dashboard Router - Metrics & Reports
Premium dashboard with:
- Appointments overview (today, week, month)
- Revenue metrics
- Customer insights
- Advanced search
"""
import logging
from datetime import datetime, timedelta, date as dt_date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, extract

from app.core.database import get_db
from app.models.models import (
    Appointment,
    Customer,
    Invoice,
    Service,
    Professional,
    AppointmentStatus,
    utcnow,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# DASHBOARD OVERVIEW
# ============================================

@router.get("/{establishment_id}/overview")
def get_dashboard_overview(
    establishment_id: str,
    db: Session = Depends(get_db)
):
    """Get dashboard overview - TODAY's snapshot.
    
    Returns:
    - Today's appointments
    - Week's upcoming appointments
    - Revenue stats
    - Quick metrics
    """
    now = utcnow()
    today_start = datetime.combine(now.date(), datetime.min.time())
    today_end = datetime.combine(now.date(), datetime.max.time())
    week_end = today_start + timedelta(days=7)
    
    # Today's appointments
    today_appointments = db.query(Appointment).filter(
        and_(
            Appointment.establishment_id == establishment_id,
            Appointment.start_time >= today_start,
            Appointment.start_time <= today_end,
            Appointment.status != AppointmentStatus.CANCELLED
        )
    ).order_by(Appointment.start_time).all()
    
    # Week's upcoming
    week_appointments = db.query(Appointment).filter(
        and_(
            Appointment.establishment_id == establishment_id,
            Appointment.start_time > today_end,
            Appointment.start_time <= week_end,
            Appointment.status == AppointmentStatus.CONFIRMED
        )
    ).count()
    
    # This month's stats
    month_start = datetime(now.year, now.month, 1)
    month_appointments = db.query(Appointment).filter(
        and_(
            Appointment.establishment_id == establishment_id,
            Appointment.start_time >= month_start,
            Appointment.status != AppointmentStatus.CANCELLED
        )
    ).count()
    
    # Revenue this month
    month_revenue = db.query(func.sum(Invoice.amount)).filter(
        and_(
            Invoice.establishment_id == establishment_id,
            Invoice.invoice_date >= month_start,
            Invoice.payment_status == paid
        )
    ).scalar() or 0.0
    
    # Total customers
    total_customers = db.query(Customer).filter(
        Customer.establishment_id == establishment_id
    ).count()
    
    return {
        "today": {
            date: now.date().isoformat(),
            appointments: [
                {
                    "id": apt.id,
                    "time": apt.start_time.strftime("%H:%M"),
                    "customer_name": apt.customer_name,
                    "customer_phone": apt.customer_phone,
                    "service_id": apt.service_id,
                    "professional_id": apt.professional_id,
                    "status": apt.status.value,
                    "duration_minutes": int((apt.end_time - apt.start_time).total_seconds() / 60)
                }
                for apt in today_appointments
            ],
            "count": len(today_appointments)
        },
        week_upcoming: week_appointments,
        "month": {
            appointments: month_appointments,
            revenue: month_revenue
        },
        total_customers: total_customers
    }


# ============================================
# APPOINTMENTS MANAGEMENT
# ============================================

@router.get("/{establishment_id}/appointments")
def get_appointments(
    establishment_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    professional_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get appointments with filters - EPIC SEARCH.
    
    Filters:
    - Date range
    - Status (confirmed, cancelled, completed, no_show)
    - Professional
    """
    query = db.query(Appointment).filter(
        Appointment.establishment_id == establishment_id
    )
    
    # Date range filter
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Appointment.start_time >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Appointment.start_time < end_dt)
        except ValueError:
            pass
    
    # Status filter
    if status:
        try:
            status_enum = AppointmentStatus(status)
            query = query.filter(Appointment.status == status_enum)
        except ValueError:
            pass
    
    # Professional filter
    if professional_id:
        query = query.filter(Appointment.professional_id == professional_id)
    
    appointments = query.order_by(Appointment.start_time.desc()).limit(100).all()
    
    return {
        appointments: [
            {
                "id": apt.id,
                "start_time": apt.start_time.isoformat(),
                "end_time": apt.end_time.isoformat(),
                "customer_name": apt.customer_name,
                "customer_phone": apt.customer_phone,
                "customer_email": apt.customer_email,
                "service_id": apt.service_id,
                "professional_id": apt.professional_id,
                "status": apt.status.value,
                "notes": apt.notes,
                "created_at": apt.created_at.isoformat()
            }
            for apt in appointments
        ],
        "count": len(appointments)
    }


# ============================================
# CUSTOMERS MANAGEMENT - ADVANCED SEARCH
# ============================================

@router.get("/{establishment_id}/customers")
def search_customers(
    establishment_id: str,
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """Search customers - EPIC SEARCH.
    
    Search by:
    - Name
    - Email
    - Phone
    """
    query = db.query(Customer).filter(
        Customer.establishment_id == establishment_id
    )
    
    if search:
        search_pattern = f%{search}%
        query = query.filter(
            or_(
                Customer.name.ilike(search_pattern),
                Customer.email.ilike(search_pattern),
                Customer.phone.ilike(search_pattern)
            )
        )
    
    customers = query.order_by(Customer.created_at.desc()).limit(limit).all()
    
    # Get appointment count for each
    result = []
    for customer in customers:
        apt_count = db.query(Appointment).filter(
            Appointment.customer_id == customer.id
        ).count()
        
        result.append({
            id: customer.id,
            name: customer.name,
            email: customer.email,
            phone: customer.phone,
            language: customer.language,
            appointment_count: apt_count,
            created_at: customer.created_at.isoformat()
        })
    
    return {
        customers: result,
        "count": len(result)
    }


@router.get("/{establishment_id}/customers/{customer_id}")
def get_customer_detail(
    establishment_id: str,
    customer_id: str,
    db: Session = Depends(get_db)
):
    """Get customer details with appointment history."""
    customer = db.query(Customer).filter(
        and_(
            Customer.id == customer_id,
            Customer.establishment_id == establishment_id
        )
    ).first()
    
    if not customer:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Customer not found
        )
    
    # Get appointments
    appointments = db.query(Appointment).filter(
        Appointment.customer_id == customer_id
    ).order_by(Appointment.start_time.desc()).limit(50).all()
    
    # Get invoices
    invoices = db.query(Invoice).filter(
        Invoice.customer_id == customer_id
    ).order_by(Invoice.invoice_date.desc()).limit(20).all()
    
    return {
        "customer": {
            id: customer.id,
            name: customer.name,
            email: customer.email,
            phone: customer.phone,
            language: customer.language,
            notes: customer.notes,
            opt_out_whatsapp: customer.opt_out_whatsapp,
            opt_out_email: customer.opt_out_email,
            created_at: customer.created_at.isoformat()
        },
        appointments: [
            {
                "id": apt.id,
                "start_time": apt.start_time.isoformat(),
                "service_id": apt.service_id,
                "professional_id": apt.professional_id,
                "status": apt.status.value
            }
            for apt in appointments
        ],
        invoices: [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": inv.amount,
                "currency": inv.currency,
                "payment_status": inv.payment_status,
                "invoice_date": inv.invoice_date.isoformat()
            }
            for inv in invoices
        ]
    }


# ============================================
# MONTHLY REPORT - FINANCIAL
# ============================================

@router.get("/{establishment_id}/report/monthly")
def get_monthly_report(
    establishment_id: str,
    month: str,  # YYYY-MM format
    db: Session = Depends(get_db)
):
    """Get monthly financial report - EPIC METRICS."""
    
    Returns:
    - Total revenue
    - Appointments breakdown
    - Top services
    - Top professionals
    - Invoices
    
    try:
        year, month_num = map(int, month.split('-'))
        month_start = datetime(year, month_num, 1)
        
        if month_num == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month_num + 1, 1)
    except ValueError:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Invalid month format. Use YYYY-MM
        )
    
    # Appointments stats
    appointments = db.query(Appointment).filter(
        and_(
            Appointment.establishment_id == establishment_id,
            Appointment.start_time >= month_start,
            Appointment.start_time < month_end
        )
    ).all()
    
    total_appointments = len(appointments)
    completed = sum(1 for apt in appointments if apt.status == AppointmentStatus.COMPLETED)
    cancelled = sum(1 for apt in appointments if apt.status == AppointmentStatus.CANCELLED)
    no_show = sum(1 for apt in appointments if apt.status == AppointmentStatus.NO_SHOW)
    
    # Revenue
    invoices = db.query(Invoice).filter(
        and_(
            Invoice.establishment_id == establishment_id,
            Invoice.invoice_date >= month_start,
            Invoice.invoice_date < month_end
        )
    ).all()
    
    total_revenue = sum(inv.amount for inv in invoices if inv.payment_status == paid)
    pending_revenue = sum(inv.amount for inv in invoices if inv.payment_status == pending)
    
    return {
        month: month,
        "appointments": {
            total: total_appointments,
            completed: completed,
            cancelled: cancelled,
            no_show: no_show,
            confirmed: total_appointments - completed - cancelled - no_show
        },
        "revenue": {
            total: total_revenue,
            pending: pending_revenue,
            currency: USD  # TODO: Get from establishment
        },
        invoices: [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": inv.amount,
                "payment_status": inv.payment_status,
                "invoice_date": inv.invoice_date.isoformat(),
                "pdf_url": inv.pdf_url
            }
            for inv in invoices
        ]
    }
