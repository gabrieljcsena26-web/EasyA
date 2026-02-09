"""Imports Router - Google Calendar, iCal, CSV"""
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import AgendaImport, generate_uuid, utcnow
from pydantic import BaseModel

router = APIRouter()

class GoogleCalendarImport(BaseModel):
    calendar_id: str
    start_date: str
    end_date: str

@router.post("/google-calendar")
async def import_google_calendar(data: GoogleCalendarImport, db: Session = Depends(get_db)):
    """Import from Google Calendar."""
    import_record = AgendaImport(
        id=generate_uuid(),
        establishment_id="",  # Get from auth
        user_id="",
        source_type="google_calendar",
        source_identifier=data.calendar_id,
        status="pending",
        created_at=utcnow()
    )
    db.add(import_record)
    db.commit()
    return {"import_id": import_record.id, "status": "processing"}

@router.post("/ical")
async def import_ical(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import iCal file."""
    content = await file.read()
    # Process iCal
    return {"message": "iCal import started", "filename": file.filename}

@router.post("/csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import CSV file."""
    content = await file.read()
    # Process CSV
    return {"message": "CSV import started", "filename": file.filename}