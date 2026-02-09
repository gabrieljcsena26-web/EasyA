"""initial schema

Revision ID: 20260202_initial_schema
Revises:
Create Date: 2026-02-02 00:00:00.000000

This baseline migration creates all tables from the SQLAlchemy models.
It replaces any need for runtime `create_all` in production.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260202_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    from app.db.database import Base  # type: ignore
    import app.models.models as _models  # noqa: F401

    Base.metadata.create_all(bind=bind)


def downgrade():
    bind = op.get_bind()
    from app.db.database import Base  # type: ignore
    import app.models.models as _models  # noqa: F401

    Base.metadata.drop_all(bind=bind)
