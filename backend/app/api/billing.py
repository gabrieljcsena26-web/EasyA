"""Billing Router - Invoices + PDF"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Invoice, InvoiceType, generate_uuid, utcnow
from pydantic import BaseModel

router = APIRouter()

class InvoiceCreate(BaseModel):
    appointment_id: str
    customer_id: str
    amount: float
    type: str = "full"

@router.post("/invoices")
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db)):
    """Create invoice."""
    invoice = Invoice(
        id=generate_uuid(),
        establishment_id="",
        appointment_id=data.appointment_id,
        customer_id=data.customer_id,
        invoice_number=f"INV-{utcnow().strftime('%Y%m%d')}-{generate_uuid()[:8]}",
        invoice_date=utcnow(),
        type=InvoiceType.FULL,
        amount=data.amount,
        payment_status="pending",
        created_at=utcnow()
    )
    db.add(invoice)
    db.commit()
    return invoice

@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: str, db: Session = Depends(get_db)):
    """Download invoice PDF."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    # Generate PDF
    return {"pdf_url": f"/invoices/{invoice_id}.pdf"}

@router.get("/stripe/webhook")
async def stripe_webhook():
    """Stripe webhook handler."""
    return {"received": True}