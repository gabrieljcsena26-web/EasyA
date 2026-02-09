"""Application configuration - EPIC LEVEL"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings with PostgreSQL + WhatsApp Meta API."""
    
    # Application
    APP_NAME: str = "EasyAgenda"
    VERSION: str = "2.0.0"
    ENV: str = Field(default="development", env="ENV")
    DEBUG: bool = Field(default=True, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Security
    SECRET_KEY: str = Field(default="easyagenda-epic-secret-key-change-in-production-xyz789", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=10080, env="ACCESS_TOKEN_EXPIRE_MINUTES")  # 7 days
    ALGORITHM: str = "HS256"
    
    # PostgreSQL Database
    DATABASE_URL: str = Field(
        default="postgresql://easyagenda_user:easyagenda_pass_secure_2024@localhost:5432/easyagenda",
        env="DATABASE_URL"
    )
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # CORS
    FRONTEND_URLS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        env="FRONTEND_URLS"
    )
    BOOKING_PUBLIC_BASE_URL: str = Field(
        default="http://localhost:3000",
        env="BOOKING_PUBLIC_BASE_URL"
    )
    API_PUBLIC_BASE_URL: str = Field(
        default="http://localhost:8001",
        env="API_PUBLIC_BASE_URL"
    )
    
    def get_frontend_urls(self) -> List[str]:
        """Get frontend URLs as list."""
        return [url.strip() for url in self.FRONTEND_URLS.split(',')]
    
    # WhatsApp - Meta Cloud API (NOT Twilio)
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="", env="WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_ACCESS_TOKEN: str = Field(default="", env="WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_VERIFY_TOKEN: str = Field(default="", env="WHATSAPP_VERIFY_TOKEN")
    WHATSAPP_WEBHOOK_SECRET: str = Field(default="", env="WHATSAPP_WEBHOOK_SECRET")
    WHATSAPP_API_VERSION: str = Field(default="v21.0", env="WHATSAPP_API_VERSION")
    
    # Email (optional fallback)
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: Optional[str] = Field(default=None, env="SMTP_USER")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SMTP_FROM: str = Field(default="noreply@easyagenda.com", env="SMTP_FROM")
    
    # Stripe
    STRIPE_SECRET_KEY: str = Field(default="", env="STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str = Field(default="", env="STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_ID: str = Field(default="", env="STRIPE_PRICE_ID")
    
    # Google OAuth (for Calendar Import)
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: Optional[str] = Field(default=None, env="GOOGLE_REDIRECT_URI")
    
    # Trial settings
    TRIAL_DAYS: int = Field(default=4, env="TRIAL_DAYS")
    
    # Workers
    ENABLE_WORKERS: bool = Field(default=True, env="ENABLE_WORKERS")
    WORKER_CONCURRENCY: int = Field(default=4, env="WORKER_CONCURRENCY")
    
    # PDF Generation
    PDF_LOGO_URL: Optional[str] = Field(default=None, env="PDF_LOGO_URL")
    PDF_COMPANY_INFO: Optional[str] = Field(default=None, env="PDF_COMPANY_INFO")
    
    # Cloudflare
    ALLOWED_HOSTS: str = Field(default="*", env="ALLOWED_HOSTS")
    
    def get_allowed_hosts(self) -> List[str]:
        """Get allowed hosts as list."""
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        return [host.strip() for host in self.ALLOWED_HOSTS.split(',')]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
