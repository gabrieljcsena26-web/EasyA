"""Authentication services and utilities."""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from passlib.context import CryptContext
import jwt
import aiohttp
from config import settings
from models import User, generate_id

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordService:
    """Password hashing and verification."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_reset_code() -> str:
        """Generate a 6-digit reset code."""
        return str(secrets.randbelow(1000000)).zfill(6)


class TokenService:
    """JWT token generation and verification."""
    
    @staticmethod
    def create_token(
        data: Dict,
        expires_delta: Optional[timedelta] = None,
        token_type: str = "access"
    ) -> str:
        """Create a JWT token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            # Default: 24 hours for access, 7 days for refresh
            if token_type == "refresh":
                expire = datetime.now(timezone.utc) + timedelta(days=7)
            else:
                expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
        
        to_encode.update({
            "exp": expire,
            "type": token_type,
            "iat": datetime.now(timezone.utc)
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Dict:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
    
    @staticmethod
    def create_session_token(user_id: str, establishment_id: str) -> str:
        """Create a long-lived session token (7 days)."""
        return TokenService.create_token(
            {"sub": user_id, "establishment_id": establishment_id},
            expires_delta=timedelta(days=7),
            token_type="session"
        )
    
    @staticmethod
    def create_ics_token(appointment_id: str, establishment_id: str) -> str:
        """Create a token for calendar .ics download."""
        return TokenService.create_token(
            {
                "appointment_id": appointment_id,
                "establishment_id": establishment_id,
                "purpose": "ics"
            },
            expires_delta=timedelta(days=365),  # Long-lived for calendar apps
            token_type="ics"
        )


class EmergentAuthService:
    """Emergent Google OAuth service."""
    
    SESSION_DATA_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
    
    @staticmethod
    async def get_session_data(session_id: str) -> Dict:
        """Get user data from Emergent Auth session."""
        headers = {"X-Session-ID": session_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                EmergentAuthService.SESSION_DATA_URL,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Emergent Auth error: {response.status} - {error_text}")
                    raise ValueError(f"Failed to get session data: {response.status}")
                
                data = await response.json()
                return data


class AppleAuthService:
    """Apple Sign In service."""
    
    @staticmethod
    async def verify_apple_token(id_token: str, code: str) -> Dict:
        """Verify Apple ID token and return user data."""
        # For now, we'll implement a basic verification
        # In production, you should:
        # 1. Fetch Apple's public keys from https://appleid.apple.com/auth/keys
        # 2. Verify the JWT signature using the public key
        # 3. Validate claims (iss, aud, exp, etc.)
        
        try:
            # Decode without verification for now (implement proper verification in production)
            decoded = jwt.decode(id_token, options={"verify_signature": False})
            
            return {
                "apple_id": decoded.get("sub"),
                "email": decoded.get("email"),
                "email_verified": decoded.get("email_verified", False)
            }
        except Exception as e:
            logger.error(f"Apple token verification failed: {e}", exc_info=True)
            raise ValueError(f"Invalid Apple token: {e}")
