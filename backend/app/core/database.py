"""Database with Motor (MongoDB async)."""
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client = None
db = None

def init_db():
    """Initialize MongoDB connection."""
    global client, db
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    db = client.get_database()
    return db

def get_db():
    """Get database for dependencies."""
    return db

# For sync operations (compatibility)
class SessionLocal:
    def __init__(self):
        self.db = db
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def query(self, model):
        return db[model.__tablename__]
    
    def add(self, obj):
        pass
    
    def commit(self):
        pass
    
    def refresh(self, obj):
        pass
