"""add rating to chat_messages

Revision ID: d8e4a1c7b392
Revises: b7d3f2a8c5e1
Create Date: 2026-11-15

S58 (Compare 3, side-by-side scoring): a nullable thumbs column per compare
reply. +1 = 👍, -1 = 👎, NULL = unrated. Only answered assistant rows carry
one (routers/chat.py refuses user turns and S75 error rows), and the session
leaderboard GET /api/chat-sessions/{id}/scores aggregates these values.
"""
import sqlalchemy as sa
from alembic import op

revision = "d8e4a1c7b392"
down_revision = "b7d3f2a8c5e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("rating")
