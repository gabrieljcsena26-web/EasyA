"""Authentication API endpoints."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel, EmailStr, Field

from services.database import get_database
from services.auth import (
    PasswordService, TokenService, EmergentAuthService, AppleAuthService
)
from services.dependencies import get_current_user, CurrentUser
from models import User, UserCreate, generate_id, utcnow
from utils.errors import UnauthorizedError, ValidationError, ConflictError
from middleware import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class SignupRequest(BaseModel):
    """Signup request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    establishment_name: str = Field(..., min_length=1, max_length=200)
    establishment_slug: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z0-9-]+$')


class LoginRequest(BaseModel):
    """Login request."""
    email: EmailStr
    password: str
    remember_me: bool = False


class PasswordResetRequestModel(BaseModel):
    """Password reset request."""
    email: EmailStr
    establishment_slug: str


class PasswordResetConfirmModel(BaseModel):
    """Password reset confirm."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=100)


class EmergentSessionRequest(BaseModel):
    """Emergent Auth session request."""
    session_id: str


class AppleAuthRequest(BaseModel):
    """Apple Sign In request."""
    id_token: str
    code: str
    user: Optional[dict] = None  # Sent on first sign-in only


class AuthResponse(BaseModel):
    """Authentication response."""
    user: User
    session_token: str
    message: str = "Authentication successful"


# ============================================
# SIGNUP & LOGIN (Email/Password)
# ============================================

@router.post("/signup", response_model=AuthResponse)
@limiter.limit("5/minute")
async def signup(request: Request, data: SignupRequest, response: Response):
    """Register a new admin user and create establishment."""
    db = get_database()
    
    try:
        # Check if email already exists
        existing_user = await db.users.find_one({"email": data.email})
        if existing_user:
            raise ConflictError("Email already registered", {"field": "email"})
        
        # Check if slug already exists
        existing_establishment = await db.establishments.find_one({"slug": data.establishment_slug})
        if existing_establishment:
            raise ConflictError("Slug already taken", {"field": "establishment_slug"})
        
        # Create establishment first
        from models import Establishment, EstablishmentCreate
        establishment = Establishment(
            **EstablishmentCreate(
                name=data.establishment_name,
                slug=data.establishment_slug
            ).model_dump()
        )
        
        establishment_dict = establishment.model_dump()
        # Convert datetime to ISO string for MongoDB
        establishment_dict['created_at'] = establishment_dict['created_at'].isoformat()
        establishment_dict['updated_at'] = establishment_dict['updated_at'].isoformat()
        establishment_dict['trial_end_date'] = establishment_dict['trial_end_date'].isoformat()
        
        await db.establishments.insert_one(establishment_dict)
        
        # Create user
        user = User(
            id=generate_id(),
            email=data.email,
            full_name=data.full_name,
            establishment_id=establishment.id,
            hashed_password=PasswordService.hash_password(data.password),
            created_at=utcnow(),
            updated_at=utcnow(),
            is_active=True
        )
        
        user_dict = user.model_dump()
        user_dict['created_at'] = user_dict['created_at'].isoformat()
        user_dict['updated_at'] = user_dict['updated_at'].isoformat()
        
        await db.users.insert_one(user_dict)
        
        # Create session token
        session_token = TokenService.create_session_token(user.id, establishment.id)
        
        # Set httpOnly cookie (secure in production)
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=7 * 24 * 60 * 60,  # 7 days
            samesite="none",
            secure=True,  # HTTPS only in production
            path="/"
        )
        
        logger.info(f"New user registered: {user.email}")
        
        return AuthResponse(
            user=user,
            session_token=session_token,
            message="Account created successfully"
        )
    
    except (ConflictError, ValidationError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Signup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, response: Response):
    """Login with email and password."""
    db = get_database()
    
    try:
        # Find user by email
        user_doc = await db.users.find_one({"email": data.email}, {"_id": 0})
        
        if not user_doc:
            raise UnauthorizedError("Invalid email or password")
        
        # Verify password
        if not PasswordService.verify_password(data.password, user_doc['hashed_password']):
            raise UnauthorizedError("Invalid email or password")
        
        # Check if user is active
        if not user_doc.get('is_active', True):
            raise UnauthorizedError("Account is inactive")
        
        # Convert to User model
        user = User(**user_doc)
        
        # Create session token
        expires_delta = timedelta(days=30) if data.remember_me else timedelta(days=7)
        session_token = TokenService.create_token(
            {"sub": user.id, "establishment_id": user.establishment_id},
            expires_delta=expires_delta,
            token_type="session"
        )
        
        # Set httpOnly cookie
        max_age = 30 * 24 * 60 * 60 if data.remember_me else 7 * 24 * 60 * 60
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=max_age,
            samesite="none",
            secure=True,
            path="/"
        )
        
        logger.info(f"User logged in: {user.email}")
        
        return AuthResponse(
            user=user,
            session_token=session_token,
            message="Login successful"
        )
    
    except UnauthorizedError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


# ============================================
# EMERGENT GOOGLE OAUTH
# ============================================

@router.post("/google/session", response_model=AuthResponse)
async def google_session(data: EmergentSessionRequest, response: Response):
    """Process Emergent Google OAuth session.
    
    REMINDER: Frontend must NOT hardcode redirect URL. Use window.location.origin.
    """
    db = get_database()
    
    try:
        # Get user data from Emergent Auth
        session_data = await EmergentAuthService.get_session_data(data.session_id)
        
        email = session_data.get("email")
        name = session_data.get("name", "")
        picture = session_data.get("picture")
        google_id = session_data.get("id")
        
        if not email:
            raise ValueError("Email not provided by Google")
        
        # Check if user exists
        user_doc = await db.users.find_one({"email": email}, {"_id": 0})
        
        if user_doc:
            # Existing user - update Google ID if not set
            user = User(**user_doc)
            if not user_doc.get('google_id'):
                await db.users.update_one(
                    {"id": user.id},
                    {"$set": {"google_id": google_id, "updated_at": utcnow().isoformat()}}
                )
        else:
            # New user - create account (no establishment for OAuth users initially)
            # They'll need to create/join an establishment after login
            user = User(
                id=generate_id(),
                email=email,
                full_name=name,
                google_id=google_id,
                establishment_id="",  # Will be set when they create/join establishment
                hashed_password="",  # OAuth users don't have password
                created_at=utcnow(),
                updated_at=utcnow(),
                is_active=True
            )
            
            user_dict = user.model_dump()
            user_dict['created_at'] = user_dict['created_at'].isoformat()
            user_dict['updated_at'] = user_dict['updated_at'].isoformat()
            
            await db.users.insert_one(user_dict)
        
        # Create session token
        session_token = TokenService.create_session_token(user.id, user.establishment_id or "")
        
        # Set httpOnly cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=7 * 24 * 60 * 60,  # 7 days
            samesite="none",
            secure=True,
            path="/"
        )
        
        logger.info(f"Google OAuth successful: {email}")
        
        return AuthResponse(
            user=user,
            session_token=session_token,
            message="Google authentication successful"
        )
    
    except Exception as e:
        logger.error(f"Google OAuth failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {str(e)}"
        )


# ============================================
# APPLE SIGN IN
# ============================================

@router.post("/apple/callback", response_model=AuthResponse)
async def apple_callback(data: AppleAuthRequest, response: Response):
    """Handle Apple Sign In callback."""
    db = get_database()
    
    try:
        # Verify Apple ID token
        apple_data = await AppleAuthService.verify_apple_token(data.id_token, data.code)
        
        apple_id = apple_data.get("apple_id")
        email = apple_data.get("email")
        
        # On first sign-in, Apple sends user data
        if data.user and data.user.get("name"):
            first_name = data.user["name"].get("firstName", "")
            last_name = data.user["name"].get("lastName", "")
            full_name = f"{first_name} {last_name}".strip()
        else:
            full_name = email.split("@")[0] if email else "Apple User"
        
        if not email:
            raise ValueError("Email not provided by Apple")
        
        # Check if user exists
        user_doc = await db.users.find_one({"email": email}, {"_id": 0})
        
        if user_doc:
            # Existing user - update Apple ID if not set
            user = User(**user_doc)
            if not user_doc.get('apple_id'):
                await db.users.update_one(
                    {"id": user.id},
                    {"$set": {"apple_id": apple_id, "updated_at": utcnow().isoformat()}}
                )
        else:
            # New user
            user = User(
                id=generate_id(),
                email=email,
                full_name=full_name,
                apple_id=apple_id,
                establishment_id="",  # Will be set later
                hashed_password="",  # OAuth users don't have password
                created_at=utcnow(),
                updated_at=utcnow(),
                is_active=True
            )
            
            user_dict = user.model_dump()
            user_dict['created_at'] = user_dict['created_at'].isoformat()
            user_dict['updated_at'] = user_dict['updated_at'].isoformat()
            
            await db.users.insert_one(user_dict)
        
        # Create session token
        session_token = TokenService.create_session_token(user.id, user.establishment_id or "")
        
        # Set httpOnly cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=7 * 24 * 60 * 60,
            samesite="none",
            secure=True,
            path="/"
        )
        
        logger.info(f"Apple Sign In successful: {email}")
        
        return AuthResponse(
            user=user,
            session_token=session_token,
            message="Apple authentication successful"
        )
    
    except Exception as e:
        logger.error(f"Apple Sign In failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Apple authentication failed: {str(e)}"
        )


# ============================================
# PASSWORD RESET
# ============================================

@router.post("/password-reset/request")
@limiter.limit("3/minute")
async def request_password_reset(request: Request, data: PasswordResetRequestModel):
    """Request password reset code (sent via email/WhatsApp)."""
    db = get_database()
    
    try:
        # Find user by email and establishment
        establishment_doc = await db.establishments.find_one({"slug": data.establishment_slug}, {"_id": 0})
        if not establishment_doc:
            # Don't reveal if slug doesn't exist
            return {"message": "If account exists, reset code will be sent"}
        
        user_doc = await db.users.find_one(
            {"email": data.email, "establishment_id": establishment_doc['id']},
            {"_id": 0}
        )
        
        if not user_doc:
            # Don't reveal if user doesn't exist
            return {"message": "If account exists, reset code will be sent"}
        
        # Generate reset code
        reset_code = PasswordService.generate_reset_code()
        reset_code_expires = utcnow() + timedelta(minutes=15)
        
        # Update user with reset code
        await db.users.update_one(
            {"id": user_doc['id']},
            {
                "$set": {
                    "reset_code": reset_code,
                    "reset_code_expires": reset_code_expires.isoformat(),
                    "updated_at": utcnow().isoformat()
                }
            }
        )
        
        # TODO: Send reset code via email/WhatsApp
        # For now, log it (in production, send via notification system)
        logger.info(f"Password reset code for {data.email}: {reset_code}")
        
        return {"message": "Reset code sent successfully"}
    
    except Exception as e:
        logger.error(f"Password reset request failed: {e}", exc_info=True)
        return {"message": "If account exists, reset code will be sent"}


@router.post("/password-reset/confirm")
@limiter.limit("5/minute")
async def confirm_password_reset(request: Request, data: PasswordResetConfirmModel):
    """Confirm password reset with code."""
    db = get_database()
    
    try:
        # Find user by email
        user_doc = await db.users.find_one({"email": data.email}, {"_id": 0})
        
        if not user_doc:
            raise UnauthorizedError("Invalid reset code")
        
        # Check reset code
        if user_doc.get('reset_code') != data.code:
            raise UnauthorizedError("Invalid reset code")
        
        # Check expiration
        reset_code_expires = user_doc.get('reset_code_expires')
        if isinstance(reset_code_expires, str):
            reset_code_expires = datetime.fromisoformat(reset_code_expires.replace('Z', '+00:00'))
        
        if reset_code_expires.tzinfo is None:
            reset_code_expires = reset_code_expires.replace(tzinfo=timezone.utc)
        
        if reset_code_expires < datetime.now(timezone.utc):
            raise UnauthorizedError("Reset code expired")
        
        # Update password
        hashed_password = PasswordService.hash_password(data.new_password)
        await db.users.update_one(
            {"id": user_doc['id']},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "reset_code": None,
                    "reset_code_expires": None,
                    "updated_at": utcnow().isoformat()
                }
            }
        )
        
        logger.info(f"Password reset successful: {data.email}")
        
        return {"message": "Password reset successful"}
    
    except UnauthorizedError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Password reset confirmation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


# ============================================
# SESSION MANAGEMENT
# ============================================

@router.get("/me", response_model=User)
async def get_me(current_user: CurrentUser):
    """Get current authenticated user."""
    return current_user


@router.post("/logout")
async def logout(response: Response):
    """Logout user by clearing session cookie."""
    response.delete_cookie(
        key="session_token",
        path="/",
        samesite="none",
        secure=True
    )
    
    return {"message": "Logged out successfully"}
