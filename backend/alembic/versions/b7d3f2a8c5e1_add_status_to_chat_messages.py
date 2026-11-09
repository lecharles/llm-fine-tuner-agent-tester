"""add status to chat_messages

Revision ID: b7d3f2a8c5e1
Revises: f2c9d8e4a715
Create Date: 2026-11-09

S75 (self-drafted compare-depth slice, ROADMAP "Surface per-column errors..."):
a failed compare column used to vanish from the transcript on reload — the
errors map lived only in the live POST response. This nullable status column
marks persisted failure rows ("error"; content holds the reason). NULL rows are
normal replies. The history rebuild in routers/chat.py skips "error" rows, so
failure text never replays into a model's context.
"""
import sqlalchemy as sa
from alembic import op

revision = "b7d3f2a8c5e1"
down_revision = "f2c9d8e4a715"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("status")
