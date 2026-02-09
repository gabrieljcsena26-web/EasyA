"""Database connection and initialization."""
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel
from config import settings

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager."""
    
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None
    
    @classmethod
    async def connect(cls):
        """Connect to MongoDB and create indexes."""
        logger.info(f"Connecting to MongoDB: {settings.MONGO_URL}")
        cls.client = AsyncIOMotorClient(settings.MONGO_URL)
        cls.db = cls.client[settings.DB_NAME]
        
        # Create indexes
        await cls._create_indexes()
        logger.info("MongoDB connected and indexes created")
    
    @classmethod
    async def disconnect(cls):
        """Disconnect from MongoDB."""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB disconnected")
    
    @classmethod
    async def _create_indexes(cls):
        """Create database indexes for performance and constraints."""
        
        # Establishments
        await cls.db.establishments.create_indexes([
            IndexModel([('slug', ASCENDING)], unique=True, name='slug_unique'),
            IndexModel([('created_at', ASCENDING)], name='created_at_idx'),
        ])
        
        # Users
        await cls.db.users.create_indexes([
            IndexModel([('email', ASCENDING), ('establishment_id', ASCENDING)], unique=True, name='email_establishment_unique'),
            IndexModel([('establishment_id', ASCENDING)], name='establishment_idx'),
        ])
        
        # Professionals
        await cls.db.professionals.create_indexes([
            IndexModel([('establishment_id', ASCENDING)], name='establishment_idx'),
            IndexModel([('created_at', ASCENDING)], name='created_at_idx'),
        ])
        
        # Services
        await cls.db.services.create_indexes([
            IndexModel([('establishment_id', ASCENDING)], name='establishment_idx'),
            IndexModel([('enabled', ASCENDING)], name='enabled_idx'),
        ])
        
        # Customers
        await cls.db.customers.create_indexes([
            IndexModel([('establishment_id', ASCENDING)], name='establishment_idx'),
            IndexModel([('email', ASCENDING), ('establishment_id', ASCENDING)], name='email_establishment_idx'),
        ])
        
        # Appointments
        await cls.db.appointments.create_indexes([
            IndexModel([('establishment_id', ASCENDING), ('start_time', ASCENDING)], name='establishment_start_idx'),
            IndexModel([('professional_id', ASCENDING), ('start_time', ASCENDING)], name='professional_start_idx'),
            IndexModel([('customer_id', ASCENDING)], name='customer_idx'),
            IndexModel([('status', ASCENDING)], name='status_idx'),
            IndexModel([('confirmation_token', ASCENDING)], name='confirmation_token_idx'),
        ])
        
        # Notifications
        await cls.db.notifications.create_indexes([
            IndexModel([('establishment_id', ASCENDING)], name='establishment_idx'),
            IndexModel([('appointment_id', ASCENDING)], name='appointment_idx'),
            IndexModel([('scheduled_for', ASCENDING), ('status', ASCENDING)], name='scheduled_status_idx'),
            IndexModel([('status', ASCENDING)], name='status_idx'),
        ])
        
        # Webhook Events (for idempotency)
        await cls.db.webhook_events.create_indexes([
            IndexModel([('event_id', ASCENDING), ('provider', ASCENDING)], unique=True, name='event_provider_unique'),
            IndexModel([('processed_at', ASCENDING)], name='processed_at_idx'),
        ])


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance."""
    return Database.db
