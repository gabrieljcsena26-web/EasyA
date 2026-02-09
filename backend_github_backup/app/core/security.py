# backend/app/core/security.py

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import re

# 🔐 CHAVE FIXA (não muda)
# Load secrets from environment for safety
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def _is_production() -> bool:
    env = str(os.getenv("ENV", "development") or "").strip().lower()
    return env in ("prod", "production")


if _is_production():
    if not SECRET_KEY or SECRET_KEY.strip() in ("dev-secret-change-me", "change-me-dev-secret"):
        raise RuntimeError("SECRET_KEY must be set to a strong random value in production")

security = HTTPBearer()

# -------------------------------
# CRIAR TOKEN
# -------------------------------
def create_access_token(data: dict, expires_in_hours: int = None, expires_in_minutes: int = None):
    """Create a JWT. Pass either expires_in_hours or expires_in_minutes to override default."""
    to_encode = data.copy()
    if expires_in_hours is not None:
        expire = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    elif expires_in_minutes is not None:
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

# -------------------------------
# VALIDAR TOKEN
# -------------------------------
def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")


# Dependency wrapper that extracts credentials via HTTPBearer and decodes the token
def verify_access_token_dep(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency wrapper that extracts credentials via HTTPBearer and decodes the token.
    Always validates the JWT and returns the payload.
    """
    return verify_access_token(credentials.credentials)


def get_password_hash(password: str) -> str:
    """Hash password for storage.

    Uses bcrypt (industry standard) and returns a UTF-8 string.
    """
    try:
        import bcrypt  # type: ignore

        pw = str(password or "").encode("utf-8")
        hashed = bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12))
        return hashed.decode("utf-8")
    except Exception:
        # Extremely defensive fallback (should not be used in production)
        return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()


_SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")


def _is_legacy_sha256_hash(password_hash: str | None) -> bool:
    if not password_hash:
        return False
    s = str(password_hash).strip().lower()
    return bool(_SHA256_HEX_RE.match(s))


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    ph = str(password_hash).strip()

    # Legacy SHA256 support (older demo data). Not recommended, but keeps compatibility.
    if _is_legacy_sha256_hash(ph):
        return hashlib.sha256(str(plain_password or "").encode("utf-8")).hexdigest() == ph.lower()

    # bcrypt
    try:
        import bcrypt  # type: ignore

        return bcrypt.checkpw(
            str(plain_password or "").encode("utf-8"),
            ph.encode("utf-8"),
        )
    except Exception:
        return False


def upgrade_password_hash_if_needed(plain_password: str, password_hash: str | None) -> str | None:
    """Return a new bcrypt hash if the stored hash is legacy and password is correct."""
    if not password_hash:
        return None
    if not _is_legacy_sha256_hash(password_hash):
        return None
    if not verify_password(plain_password, password_hash):
        return None
    return get_password_hash(plain_password)
