"""EasyAgenda - Complete Backend with ALL Features"""
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, List
from bson import ObjectId
import os

app = FastAPI(title="EasyAgenda API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB
client = AsyncIOMotorClient(os.getenv("DATABASE_URL", "mongodb://localhost:27017"))
db = client[os.getenv("DB_NAME", "easyagenda")]

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "secret-key-change-in-production")


# ============================================
# SCHEMAS
# ============================================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    establishment_name: str
    establishment_slug: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ProfessionalCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None
    weekly_schedule: Optional[List[dict]] = []
    color: str = "#3B82F6"

class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    duration_minutes: int
    price: float
    buffer_before: int = 0
    buffer_after: int = 0
    color: str = "#10B981"

class AppointmentCreate(BaseModel):
    service_id: str
    professional_id: str
    start_time: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None


# ============================================
# AUTH ENDPOINTS
# ============================================

@app.get("/")
async def root():
    return {"app": "EasyAgenda", "version": "2.0.0", "status": "operational"}

@app.get("/ping")
async def ping():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/auth/signup")
async def signup(data: SignupRequest):
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(status_code=409, detail="Email already exists")
    
    if await db.establishments.find_one({"slug": data.establishment_slug}):
        raise HTTPException(status_code=409, detail="Slug already taken")
    
    establishment = {
        "name": data.establishment_name,
        "slug": data.establishment_slug,
        "trial_end_date": datetime.utcnow() + timedelta(days=4),
        "active_plan": False,
        "timezone": "UTC",
        "booking_settings": {},
        "created_at": datetime.utcnow()
    }
    est_result = await db.establishments.insert_one(establishment)
    est_id = str(est_result.inserted_id)
    
    user = {
        "email": data.email,
        "hashed_password": pwd_context.hash(data.password),
        "full_name": data.full_name,
        "establishment_id": est_id,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    user_result = await db.users.insert_one(user)
    user_id = str(user_result.inserted_id)
    
    token = jwt.encode(
        {"sub": user_id, "establishment_id": est_id, "exp": datetime.utcnow() + timedelta(days=7)},
        SECRET_KEY
    )
    
    return {
        "access_token": token,
        "user": {
            "id": user_id,
            "email": data.email,
            "full_name": data.full_name,
            "establishment_id": est_id,
            "establishment_slug": data.establishment_slug
        }
    }

@app.post("/api/auth/login")
async def login(data: LoginRequest):
    user = await db.users.find_one({"email": data.email})
    if not user or not pwd_context.verify(data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    establishment = await db.establishments.find_one({"_id": ObjectId(user["establishment_id"])})
    
    token = jwt.encode(
        {"sub": str(user["_id"]), "establishment_id": user["establishment_id"], "exp": datetime.utcnow() + timedelta(days=7)},
        SECRET_KEY
    )
    
    return {
        "access_token": token,
        "user": {
            "id": str(user["_id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "establishment_id": user["establishment_id"],
            "establishment_slug": establishment["slug"] if establishment else ""
        }
    }


# ============================================
# ADMIN ENDPOINTS
# ============================================

@app.post("/api/admin/professionals")
async def create_professional(data: ProfessionalCreate, establishment_id: str = Query(...)):
    professional = {
        "establishment_id": establishment_id,
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "specialty": data.specialty,
        "weekly_schedule": data.weekly_schedule,
        "color": data.color,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    result = await db.professionals.insert_one(professional)
    professional["id"] = str(result.inserted_id)
    return professional

@app.get("/api/admin/professionals")
async def get_professionals(establishment_id: str = Query(...)):
    professionals = []
    async for prof in db.professionals.find({"establishment_id": establishment_id, "is_active": True}):
        prof["id"] = str(prof.pop("_id"))
        professionals.append(prof)
    return {"professionals": professionals}

@app.post("/api/admin/services")
async def create_service(data: ServiceCreate, establishment_id: str = Query(...)):
    service = {
        "establishment_id": establishment_id,
        "name": data.name,
        "description": data.description,
        "duration_minutes": data.duration_minutes,
        "price": data.price,
        "buffer_before": data.buffer_before,
        "buffer_after": data.buffer_after,
        "color": data.color,
        "enabled": True,
        "created_at": datetime.utcnow()
    }
    result = await db.services.insert_one(service)
    service["id"] = str(result.inserted_id)
    return service

@app.get("/api/admin/services")
async def get_services(establishment_id: str = Query(...)):
    services = []
    async for svc in db.services.find({"establishment_id": establishment_id, "enabled": True}):
        svc["id"] = str(svc.pop("_id"))
        services.append(svc)
    return {"services": services}


# ============================================
# DASHBOARD ENDPOINTS
# ============================================

@app.get("/api/dashboard/overview")
async def dashboard_overview(establishment_id: str = Query(...)):
    today_start = datetime.combine(datetime.utcnow().date(), dt_time(0, 0))
    today_end = datetime.combine(datetime.utcnow().date(), dt_time(23, 59))
    
    # Today's appointments
    today_apts = []
    async for apt in db.appointments.find({
        "establishment_id": establishment_id,
        "start_time": {"$gte": today_start, "$lte": today_end}
    }).sort("start_time", 1):
        apt["id"] = str(apt.pop("_id"))
        today_apts.append(apt)
    
    # Week upcoming
    week_end = today_start + timedelta(days=7)
    week_count = await db.appointments.count_documents({
        "establishment_id": establishment_id,
        "start_time": {"$gt": today_end, "$lte": week_end}
    })
    
    # Month stats
    month_start = datetime(datetime.utcnow().year, datetime.utcnow().month, 1)
    month_count = await db.appointments.count_documents({
        "establishment_id": establishment_id,
        "start_time": {"$gte": month_start}
    })
    
    # Total customers
    total_customers = await db.customers.count_documents({"establishment_id": establishment_id})
    
    return {
        "today": {
            "appointments": today_apts,
            "count": len(today_apts)
        },
        "week_upcoming": week_count,
        "month_appointments": month_count,
        "total_customers": total_customers
    }

@app.get("/api/dashboard/appointments")
async def get_appointments(
    establishment_id: str = Query(...),
    limit: int = Query(50)
):
    appointments = []
    async for apt in db.appointments.find({"establishment_id": establishment_id}).sort("start_time", -1).limit(limit):
        apt["id"] = str(apt.pop("_id"))
        appointments.append(apt)
    return {"appointments": appointments}

@app.get("/api/dashboard/customers")
async def get_customers(
    establishment_id: str = Query(...),
    search: Optional[str] = Query(None),
    limit: int = Query(50)
):
    query = {"establishment_id": establishment_id}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]
    
    customers = []
    async for customer in db.customers.find(query).limit(limit):
        customer["id"] = str(customer.pop("_id"))
        # Get appointment count
        apt_count = await db.appointments.count_documents({"customer_id": customer["id"]})
        customer["appointment_count"] = apt_count
        customers.append(customer)
    
    return {"customers": customers, "count": len(customers)}


# ============================================
# BOOKING ENDPOINTS
# ============================================

@app.get("/api/booking/{slug}")
async def get_booking_page(slug: str):
    establishment = await db.establishments.find_one({"slug": slug})
    if not establishment:
        raise HTTPException(status_code=404, detail="Establishment not found")
    
    # Check trial
    if not establishment.get("active_plan") and establishment.get("trial_end_date", datetime.utcnow()) < datetime.utcnow():
        raise HTTPException(status_code=402, detail={"code": "TRIAL_EXPIRED", "message": "Trial expired"})
    
    # Get services
    services = []
    async for svc in db.services.find({"establishment_id": str(establishment["_id"]), "enabled": True}):
        svc["id"] = str(svc.pop("_id"))
        services.append(svc)
    
    # Get professionals
    professionals = []
    async for prof in db.professionals.find({"establishment_id": str(establishment["_id"]), "is_active": True}):
        prof["id"] = str(prof.pop("_id"))
        professionals.append(prof)
    
    return {
        "establishment": {
            "id": str(establishment["_id"]),
            "name": establishment["name"],
            "slug": establishment["slug"],
            "address": establishment.get("address"),
            "phone": establishment.get("phone")
        },
        "services": services,
        "professionals": professionals
    }

@app.post("/api/booking/book")
async def create_booking(data: AppointmentCreate, establishment_id: str = Query(...)):
    # Find or create customer
    customer = await db.customers.find_one({
        "establishment_id": establishment_id,
        "phone": data.customer_phone
    })
    
    if not customer:
        customer_doc = {
            "establishment_id": establishment_id,
            "name": data.customer_name,
            "email": data.customer_email,
            "phone": data.customer_phone,
            "created_at": datetime.utcnow()
        }
        result = await db.customers.insert_one(customer_doc)
        customer_id = str(result.inserted_id)
    else:
        customer_id = str(customer["_id"])
    
    # Calculate end time
    service = await db.services.find_one({"_id": ObjectId(data.service_id)})
    start_dt = datetime.fromisoformat(data.start_time.replace('Z', ''))
    end_dt = start_dt + timedelta(minutes=service["duration_minutes"])
    
    # Create appointment
    appointment = {
        "establishment_id": establishment_id,
        "service_id": data.service_id,
        "professional_id": data.professional_id,
        "customer_id": customer_id,
        "start_time": start_dt,
        "end_time": end_dt,
        "customer_name": data.customer_name,
        "customer_phone": data.customer_phone,
        "customer_email": data.customer_email,
        "status": "confirmed",
        "created_at": datetime.utcnow()
    }
    result = await db.appointments.insert_one(appointment)
    appointment["id"] = str(result.inserted_id)
    
    return {
        "message": "Booking confirmed!",
        "appointment": appointment,
        "actions": {
            "calendar": f"/api/appointments/{appointment['id']}/calendar.ics"
        }
    }

@app.get("/api/appointments/{appointment_id}/calendar.ics")
async def download_calendar(appointment_id: str):
    """Download appointment as .ics file."""
    from icalendar import Calendar, Event, Alarm
    
    appointment = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        raise HTTPException(status_code=404, detail="Not found")
    
    cal = Calendar()
    cal.add('prodid', '-//EasyAgenda//EN')
    cal.add('version', '2.0')
    
    event = Event()
    event.add('summary', f"Appointment - {appointment.get('customer_name')}")
    event.add('dtstart', appointment['start_time'])
    event.add('dtend', appointment['end_time'])
    event.add('description', f"Service appointment")
    
    # 24h reminder
    alarm_24h = Alarm()
    alarm_24h.add('trigger', timedelta(hours=-24))
    alarm_24h.add('action', 'DISPLAY')
    event.add_component(alarm_24h)
    
    # 2h reminder
    alarm_2h = Alarm()
    alarm_2h.add('trigger', timedelta(hours=-2))
    alarm_2h.add('action', 'DISPLAY')
    event.add_component(alarm_2h)
    
    cal.add_component(event)
    
    return Response(
        content=cal.to_ical(),
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=appointment-{appointment_id}.ics"}
    )


# ============================================
# AVAILABILITY ENDPOINT
# ============================================

@app.get("/api/availability")
async def get_availability(
    establishment_id: str = Query(...),
    professional_id: str = Query(...),
    date: str = Query(...)
):
    """Get available time slots for a day."""
    # Get professional schedule
    professional = await db.professionals.find_one({"_id": ObjectId(professional_id)})
    if not professional:
        return {"slots": []}
    
    # Get existing appointments
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    start_of_day = datetime.combine(date_obj.date(), dt_time(0, 0))
    end_of_day = datetime.combine(date_obj.date(), dt_time(23, 59))
    
    appointments = []
    async for apt in db.appointments.find({
        "professional_id": professional_id,
        "start_time": {"$gte": start_of_day, "$lte": end_of_day},
        "status": {"$in": ["confirmed", "pending"]}
    }):
        appointments.append(apt)
    
    # Generate slots (9am-6pm, 30min intervals)
    slots = []
    current = datetime.combine(date_obj.date(), dt_time(9, 0))
    end = datetime.combine(date_obj.date(), dt_time(18, 0))
    
    while current < end:
        slot_end = current + timedelta(minutes=30)
        
        # Check if slot is free
        is_free = True
        for apt in appointments:
            if current < apt["end_time"] and slot_end > apt["start_time"]:
                is_free = False
                break
        
        slots.append({
            "time": current.strftime("%H:%M"),
            "datetime": current.isoformat(),
            "available": is_free
        })
        
        current += timedelta(minutes=30)
    
    return {"date": date, "slots": slots}


# ============================================
# ADMIN CONFIG ENDPOINTS
# ============================================

@app.get("/api/admin/config")
async def get_admin_config(establishment_id: str = Query(...)):
    """Get complete admin configuration."""
    establishment = await db.establishments.find_one({"_id": ObjectId(establishment_id)})
    
    professionals = []
    async for prof in db.professionals.find({"establishment_id": establishment_id}):
        prof["id"] = str(prof.pop("_id"))
        professionals.append(prof)
    
    services = []
    async for svc in db.services.find({"establishment_id": establishment_id}):
        svc["id"] = str(svc.pop("_id"))
        services.append(svc)
    
    return {
        "establishment": {
            "id": str(establishment["_id"]),
            "name": establishment["name"],
            "slug": establishment["slug"],
            "booking_settings": establishment.get("booking_settings", {})
        },
        "professionals": professionals,
        "services": services
    }

@app.put("/api/admin/config")
async def update_admin_config(
    establishment_id: str = Query(...),
    name: str = Query(None),
    booking_settings: dict = None
):
    """Update establishment config."""
    update_data = {"updated_at": datetime.utcnow()}
    if name:
        update_data["name"] = name
    if booking_settings:
        update_data["booking_settings"] = booking_settings
    
    await db.establishments.update_one(
        {"_id": ObjectId(establishment_id)},
        {"$set": update_data}
    )
    
    return {"message": "Configuration updated"}
