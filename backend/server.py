from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
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
SECRET_KEY = os.getenv("SECRET_KEY", "secret")

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    establishment_name: str
    establishment_slug: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.get("/")
async def root():
    return {"app": "EasyAgenda", "version": "2.0.0", "status": "operational"}

@app.get("/ping")
async def ping():
    return {"status": "healthy"}

@app.post("/api/auth/signup")
async def signup(data: SignupRequest):
    # Check existing
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(status_code=409, detail="Email already exists")
    
    if await db.establishments.find_one({"slug": data.establishment_slug}):
        raise HTTPException(status_code=409, detail="Slug already taken")
    
    # Create establishment
    establishment = {
        "name": data.establishment_name,
        "slug": data.establishment_slug,
        "trial_end_date": datetime.utcnow() + timedelta(days=4),
        "active_plan": False,
        "created_at": datetime.utcnow()
    }
    est_result = await db.establishments.insert_one(establishment)
    establishment["_id"] = str(est_result.inserted_id)
    
    # Create user
    user = {
        "email": data.email,
        "hashed_password": pwd_context.hash(data.password),
        "full_name": data.full_name,
        "establishment_id": establishment["_id"],
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    user_result = await db.users.insert_one(user)
    user["_id"] = str(user_result.inserted_id)
    
    # Create token
    token = jwt.encode(
        {"sub": user["_id"], "establishment_id": establishment["_id"], "exp": datetime.utcnow() + timedelta(days=7)},
        SECRET_KEY,
        algorithm="HS256"
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["_id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "establishment_id": establishment["_id"],
            "establishment_slug": establishment["slug"]
        }
    }

@app.post("/api/auth/login")
async def login(data: LoginRequest):
    user = await db.users.find_one({"email": data.email})
    if not user or not pwd_context.verify(data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    establishment = await db.establishments.find_one({"_id": user["establishment_id"]})
    
    token = jwt.encode(
        {"sub": str(user["_id"]), "establishment_id": str(user["establishment_id"]), "exp": datetime.utcnow() + timedelta(days=7)},
        SECRET_KEY,
        algorithm="HS256"
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "establishment_id": str(user["establishment_id"]),
            "establishment_slug": establishment["slug"] if establishment else ""
        }
    }

@app.get("/api/booking/{slug}")
async def get_booking_info(slug: str):
    establishment = await db.establishments.find_one({"slug": slug})
    if not establishment:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "establishment": {
            "name": establishment["name"],
            "slug": establishment["slug"]
        },
        "services": [],
        "professionals": []
    }
