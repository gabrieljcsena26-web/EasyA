"""add notificacao retry fields

Revision ID: 20260102_add_notificacao_retry
Revises: 
Create Date: 2026-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in cols

# revision identifiers, used by Alembic.
revision = '20260102_add_notificacao_retry'
down_revision = '20260202_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns used for retry/idempotency (idempotent)
    table = 'notificacoes'
    if not _has_column(table, 'status'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('status', sa.String(), nullable=True, server_default='queued'))
    if not _has_column(table, 'erro'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('erro', sa.Text(), nullable=True))
    if not _has_column(table, 'attempts'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'))
    if not _has_column(table, 'last_error'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('last_error', sa.Text(), nullable=True))
    if not _has_column(table, 'next_attempt_at'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True))
    if not _has_column(table, 'max_attempts'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'))
    if not _has_column(table, 'idempotency_key'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('idempotency_key', sa.String(), nullable=True))
    if not _has_column(table, 'provider_response'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('provider_response', sa.JSON(), nullable=True))
    if not _has_column(table, 'provider_id'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('provider_id', sa.String(), nullable=True))


def downgrade():
    table = 'notificacoes'
    if _has_column(table, 'idempotency_key'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('idempotency_key')
    if _has_column(table, 'max_attempts'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('max_attempts')
    if _has_column(table, 'next_attempt_at'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('next_attempt_at')
    if _has_column(table, 'last_error'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('last_error')
    if _has_column(table, 'attempts'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('attempts')
    if _has_column(table, 'erro'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('erro')
    if _has_column(table, 'status'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('status')
    if _has_column(table, 'provider_id'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('provider_id')
    if _has_column(table, 'provider_response'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('provider_response')
