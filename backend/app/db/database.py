from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL env var for production (e.g. postgresql://user:pass@host:port/dbname)
# Fallback to local SQLite for development.
# IMPORTANT: avoid relative SQLite paths (./test.db) because the working directory can vary
# across execution contexts (tests, uvicorn, celery, systemd), causing multiple DB files.
_default_sqlite_path = (Path(__file__).resolve().parents[2] / "test.db").as_posix()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_sqlite_path}")

if SQLALCHEMY_DATABASE_URL.startswith("sqlite:"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # For Postgres and other engines
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Retorna uma sessÃ£o de banco de dados, para usar em rotas FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
