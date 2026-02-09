"""EasyAgenda - Premium Appointment Booking SaaS"""
from fastapi import FastAPI, APIRouter, status
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import redis.asyncio as redis

from config import settings
from services.database import Database, get_database
from middleware import setup_middleware
from utils.logging import setup_logging
from utils.errors import DomainError

# Setup logging
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting EasyAgenda application...")
    await Database.connect()
    logger.info("EasyAgenda application started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down EasyAgenda application...")
    await Database.disconnect()
    logger.info("EasyAgenda application stopped")


# Create FastAPI app
app = FastAPI(
    title="EasyAgenda API",
    description="Premium Appointment Booking SaaS",
    version="1.0.0",
    lifespan=lifespan
)

# Create API router
api_router = APIRouter(prefix="/api")


# ============================================
# HEALTH ENDPOINTS
# ============================================

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "easyagenda",
        "version": "1.0.0"
    }


@api_router.get("/health/db", status_code=status.HTTP_200_OK)
async def health_check_db():
    """Database health check."""
    try:
        db = get_database()
        # Simple ping to check connection
        await db.command('ping')
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


@api_router.get("/health/redis", status_code=status.HTTP_200_OK)
async def health_check_redis():
    """Redis health check."""
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        await client.close()
        return {
            "status": "healthy",
            "redis": "connected"
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "redis": "disconnected",
                "error": str(e)
            }
        )


# ============================================
# PLACEHOLDER ENDPOINTS (will be built in phases)
# ============================================

@api_router.get("/")
async def root():
    """API root."""
    return {
        "message": "Welcome to EasyAgenda API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# Include API router
app.include_router(api_router)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup security middleware
setup_middleware(app)

logger.info("EasyAgenda server initialized")
