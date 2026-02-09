"""Application configuration and settings."""
import os
from pathlib import Path
from typing import List

ROOT_DIR = Path(__file__).parent.parent

class Settings:
    """Application settings loaded from environment variables."""
    
    # MongoDB
    MONGO_URL: str = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    DB_NAME: str = os.environ.get('DB_NAME', 'easyagenda')
    
    # Redis
    REDIS_URL: str = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Security
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
    JWT_ALGORITHM: str = 'HS256'
    JWT_EXPIRATION_HOURS: int = 24
    ALLOWED_HOSTS: List[str] = os.environ.get('ALLOWED_HOSTS', '*').split(',')
    
    # CORS
    CORS_ORIGINS: List[str] = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Trial
    TRIAL_DAYS: int = 4
    
    # Stripe
    STRIPE_SECRET_KEY: str = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET: str = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    STRIPE_PRICE_ID: str = os.environ.get('STRIPE_PRICE_ID', '')
    
    # WhatsApp - Meta Cloud API
    WHATSAPP_PHONE_NUMBER_ID: str = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
    WHATSAPP_ACCESS_TOKEN: str = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
    WHATSAPP_VERIFY_TOKEN: str = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')
    WHATSAPP_WEBHOOK_SECRET: str = os.environ.get('WHATSAPP_WEBHOOK_SECRET', '')
    
    # Email (for fallback and password reset)
    SMTP_HOST: str = os.environ.get('SMTP_HOST', '')
    SMTP_PORT: int = int(os.environ.get('SMTP_PORT', '587'))
    SMTP_USER: str = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD: str = os.environ.get('SMTP_PASSWORD', '')
    SMTP_FROM: str = os.environ.get('SMTP_FROM', 'noreply@easyagenda.com')
    
    # Translation - Emergent LLM Key
    OPENAI_API_KEY: str = os.environ.get('OPENAI_API_KEY', 'sk-emergent-f292c4d2b87Fa316a6')
    TRANSLATION_CACHE_TTL: int = 86400  # 24 hours
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    RATE_LIMIT_PER_MINUTE: int = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '60'))
    
    # Logging
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
    
settings = Settings()
