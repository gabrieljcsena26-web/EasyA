"""EasyAgenda - EPIC FastAPI Application
Premium appointment booking SaaS with:
- PostgreSQL database
- WhatsApp Meta Cloud API
- Intelligent availability engine
- PDF invoice generation
- Google Calendar import
"""
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_db

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    logger.info("🚀 Starting EasyAgenda - EPIC Edition...")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"PostgreSQL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")
    
    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    
    logger.info("🎯 EasyAgenda ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down EasyAgenda...")


# Create FastAPI app
app = FastAPI(
    title="EasyAgenda API",
    description="Premium Appointment Booking SaaS - EPIC Edition",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_frontend_urls(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# ROOT & HEALTH ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """API root."""
    return {
        "app": "EasyAgenda",
        "version": "2.0.0",
        "status": "operational",
        "edition": "EPIC",
        "features": [
            "PostgreSQL Database",
            "WhatsApp Meta Cloud API",
            "Intelligent Availability Engine",
            "PDF Invoice Generation",
            "Google Calendar Import",
            "Multi-language Support"
        ]
    }


@app.get("/api/ping")
async def ping():
    """Health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/health/db")
async def health_db():
    """Database health check."""
    from app.core.database import engine
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


# ============================================
# INCLUDE API ROUTERS
# ============================================

from app.api import admin, booking, auth, dashboard

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(booking.router, prefix="/api/booking", tags=["booking"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])

logger.info("✅ All API routers loaded")


# For supervisor compatibility
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
