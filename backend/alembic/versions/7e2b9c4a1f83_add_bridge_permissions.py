"""add bridge_permissions table

Revision ID: 7e2b9c4a1f83
Revises: 5c8f2a1e9d34
Create Date: 2026-10-14

S25 (#28): the opt-in bridge. One row per explicit hardware-access grant a
user issues from the web shell — name, scoped job kinds (JSON list), the
sha256 of the one-time pairing token, active/revoked state, and the last
capability snapshot + seen time from the companion's hello frame.
"""
import sqlalchemy as sa
from alembic import op

revision = "7e2b9c4a1f83"
down_revision = "5c8f2a1e9d34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bridge_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_capabilities", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.current_timestamp(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bridge_permissions_id", "bridge_permissions", ["id"])
    op.create_index("ix_bridge_permissions_token_hash", "bridge_permissions",
                    ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_bridge_permissions_token_hash", table_name="bridge_permissions")
    op.drop_index("ix_bridge_permissions_id", table_name="bridge_permissions")
    op.drop_table("bridge_permissions")
