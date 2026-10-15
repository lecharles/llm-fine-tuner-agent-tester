"""add device_artifacts table

Revision ID: 9b4c1e8d3f60
Revises: 7e2b9c4a1f83
Create Date: 2026-10-15

S26 (#29): the data model split. Device artifact *bytes* stay on the Mac
that produced them; the hosted database keeps only metadata pointers —
one row per (bridge permission, device run, kind). Nothing here stores
content; `device_path` is display-only and is never opened host-side.
"""
import sqlalchemy as sa
from alembic import op

revision = "9b4c1e8d3f60"
down_revision = "7e2b9c4a1f83"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("bridge_permissions.id"),
                  nullable=False),
        sa.Column("device_run_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_model", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("device_path", sa.Text(), nullable=True),
        sa.Column("first_reported_at", sa.DateTime(timezone=True),
                  server_default=sa.func.current_timestamp(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True),
                  server_default=sa.func.current_timestamp(), nullable=True),
        sa.UniqueConstraint("permission_id", "device_run_id", "kind",
                            name="uq_device_artifacts_run_kind"),
    )
    op.create_index("ix_device_artifacts_id", "device_artifacts", ["id"])
    op.create_index("ix_device_artifacts_user_id", "device_artifacts", ["user_id"])
    op.create_index("ix_device_artifacts_permission_id", "device_artifacts",
                    ["permission_id"])


def downgrade() -> None:
    op.drop_index("ix_device_artifacts_permission_id", table_name="device_artifacts")
    op.drop_index("ix_device_artifacts_user_id", table_name="device_artifacts")
    op.drop_index("ix_device_artifacts_id", table_name="device_artifacts")
    op.drop_table("device_artifacts")
