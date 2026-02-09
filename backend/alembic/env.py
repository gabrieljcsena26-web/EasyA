from __future__ import with_statement
import sys
import os
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
config = context.config

# Some environments may not provide a full logging config (logger_sqlalchemy);
# guard the fileConfig call so Alembic doesn't fail to start.
try:
    if config.config_file_name:
        fileConfig(config.config_file_name)
except Exception:
    pass

target_metadata = None

# Enable autogenerate by importing app metadata.
# This must stay resilient: Alembic should still run even if optional imports fail.
try:
    from app.db.database import Base  # type: ignore
    import app.models.models as _models  # noqa: F401

    target_metadata = Base.metadata
except Exception:
    target_metadata = None


def _default_database_url() -> str:
    try:
        # Prefer the app's configured default (keeps behavior consistent).
        from app.db.database import SQLALCHEMY_DATABASE_URL as _url  # type: ignore

        if _url:
            return str(_url)
    except Exception:
        pass

    # Final fallback: use an absolute sqlite path under Backend/ to avoid cwd-dependent DB files.
    p = (Path(__file__).resolve().parents[1] / "test.db").as_posix()
    return f"sqlite:///{p}"

def run_migrations_offline():
    url = os.getenv('DATABASE_URL') or _default_database_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = os.getenv('DATABASE_URL') or _default_database_url()
    connectable = engine_from_config(configuration, prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
