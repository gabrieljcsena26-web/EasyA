"""Domain errors with stable error codes."""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class DomainError(Exception):
    """Base domain error with stable error code."""
    
    def __init__(self, code: str, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)
    
    def to_response(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                **self.details
            }
        }


class NotFoundError(DomainError):
    """Resource not found."""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier}
        )


class TrialExpiredError(DomainError):
    """Trial period has expired."""
    def __init__(self, establishment_id: str):
        super().__init__(
            code="TRIAL_EXPIRED",
            message="Trial period has expired. Please upgrade to continue.",
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            details={"establishment_id": establishment_id}
        )


class ConflictError(DomainError):
    """Resource conflict (e.g., duplicate, overlap)."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details
        )


class ValidationError(DomainError):
    """Validation error."""
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class UnauthorizedError(DomainError):
    """Authentication required."""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class ForbiddenError(DomainError):
    """Access forbidden."""
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )


class RateLimitError(DomainError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message="Rate limit exceeded. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after}
        )
