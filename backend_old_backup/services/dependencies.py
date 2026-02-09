"""Authentication dependencies and middleware."""
import logging
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.database import get_database
from services.auth import TokenService
from models import User
from utils.errors import UnauthorizedError, TrialExpiredError
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """Get current authenticated user from token (cookie or header).
    
    Checks session_token cookie first, then Authorization header as fallback.
    """
    db = get_database()
    token = None
    
    # Check cookie first (from Emergent Auth and remember me)
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    # Fallback to Authorization header
    elif credentials:
        token = credentials.credentials
    
    if not token:
        raise UnauthorizedError("No authentication token provided")
    
    try:
        # Verify token
        payload = TokenService.verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise UnauthorizedError("Invalid token: no user ID")
        
        # Get user from database
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
        
        if not user_doc:
            raise UnauthorizedError("User not found")
        
        # Check if user is active
        if not user_doc.get("is_active", True):
            raise UnauthorizedError("User account is inactive")
        
        return User(**user_doc)
    
    except ValueError as e:
        logger.warning(f"Token verification failed: {e}")
        raise UnauthorizedError(str(e))


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(request, credentials)
    except UnauthorizedError:
        return None


async def check_trial_status(user: Annotated[User, Depends(get_current_user)]):
    """Check if establishment's trial has expired.
    
    Raises TrialExpiredError if trial expired and no active plan.
    """
    db = get_database()
    
    # Get establishment
    establishment_doc = await db.establishments.find_one(
        {"id": user.establishment_id},
        {"_id": 0}
    )
    
    if not establishment_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Establishment not found"
        )
    
    # Check trial and plan status
    trial_end = establishment_doc.get("trial_end_date")
    active_plan = establishment_doc.get("active_plan", False)
    
    if not active_plan:
        # Convert trial_end to datetime if it's a string
        if isinstance(trial_end, str):
            trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
        
        # Ensure trial_end is timezone-aware
        if trial_end and trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        
        # Check if trial expired
        now = datetime.now(timezone.utc)
        if trial_end and trial_end < now:
            raise TrialExpiredError(user.establishment_id)
    
    return True


# Type aliases for dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[Optional[User], Depends(get_current_user_optional)]
TrialCheck = Annotated[bool, Depends(check_trial_status)]
