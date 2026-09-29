"""add compare_ollama_model to chat_sessions

Revision ID: 5c8f2a1e9d34
Revises: 3b7c1d9f4a2e
Create Date: 2026-09-27

S13 (#15): the compare chat gains an optional fifth column backed by an
installed Ollama model. The column stores the chosen model name; null keeps
the existing four-column layout for every session created before this change.
"""
import sqlalchemy as sa
from alembic import op

revision = "5c8f2a1e9d34"
down_revision = "3b7c1d9f4a2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.add_column(sa.Column("compare_ollama_model", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_column("compare_ollama_model")
