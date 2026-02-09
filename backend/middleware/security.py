"""Security and middleware components."""
import logging
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from utils.errors import DomainError
from utils.logging import set_correlation_id, get_correlation_id
from config import settings

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Add correlation ID to all requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or create correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        set_correlation_id(correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response
        response.headers['X-Correlation-ID'] = get_correlation_id()
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle domain errors."""
    logger.warning(f"Domain error: {exc.code} - {exc.message}", extra={'correlation_id': get_correlation_id()})
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response()
    )


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


def setup_middleware(app):
    """Setup all middleware."""
    
    # Correlation ID
    app.add_middleware(CorrelationIDMiddleware)
    
    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Trusted hosts (only in production)
    if settings.ALLOWED_HOSTS != ['*']:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    
    # Exception handlers
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Rate limiting state
    app.state.limiter = limiter
    
    logger.info("Middleware setup complete")
