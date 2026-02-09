"""Authentication Router - Multi-provider Auth
Supports:
- Email/Password signup & login
- Google OAuth (via Emergent)
- Apple Sign In
- Password reset
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import settings
from app.models.models import User, Establishment, generate_uuid, utcnow
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ============================================
# UTILITIES
# ============================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ============================================
# ENDPOINTS
# ============================================

@router.post("/signup")
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    """Sign up with email/password and create establishment."""
    # Check if email exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Check if slug exists
    existing_est = db.query(Establishment).filter(
        Establishment.slug == request.establishment_slug
    ).first()
    if existing_est:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slug already taken"
        )
    
    # Create establishment
    trial_end = utcnow() + timedelta(days=settings.TRIAL_DAYS)
    establishment = Establishment(
        id=generate_uuid(),
        name=request.establishment_name,
        slug=request.establishment_slug,
        trial_end_date=trial_end,
        active_plan=False,
        created_at=utcnow(),
        updated_at=utcnow()
    )
    db.add(establishment)
    db.flush()
    
    # Create user
    user = User(
        id=generate_uuid(),
        establishment_id=establishment.id,
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        is_active=True,
        created_at=utcnow(),
        updated_at=utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create token
    token = create_access_token({"sub": user.id, "establishment_id": establishment.id})
    
    logger.info(f"User signed up: {user.email}")
    
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "establishment_id": establishment.id,
            "establishment_slug": establishment.slug
        }
    )


@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login with email/password."""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Get establishment
    establishment = db.query(Establishment).filter(
        Establishment.id == user.establishment_id
    ).first()
    
    # Create token
    token = create_access_token({"sub": user.id, "establishment_id": user.establishment_id})
    
    logger.info(f"User logged in: {user.email}")
    
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "establishment_id": user.establishment_id,
            "establishment_slug": establishment.slug if establishment else None
        }
    )
