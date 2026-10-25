"""add visibility to datasets and fine_tuned_models

Revision ID: c3a9d57e2b41
Revises: 9b4c1e8d3f60
Create Date: 2026-10-25

S31: public/private sharing, part 1. One string column per table, "private"
by default (server_default keeps existing rows and older app deploys safe).
Public rows are readable by any signed-in user; mutations stay owner-only.
"""
import sqlalchemy as sa
from alembic import op

revision = "c3a9d57e2b41"
down_revision = "9b4c1e8d3f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
    )
    op.add_column(
        "fine_tuned_models",
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
    )
    op.create_index("ix_datasets_visibility", "datasets", ["visibility"])
    op.create_index("ix_fine_tuned_models_visibility", "fine_tuned_models", ["visibility"])


def downgrade() -> None:
    op.drop_index("ix_fine_tuned_models_visibility", table_name="fine_tuned_models")
    op.drop_index("ix_datasets_visibility", table_name="datasets")
    op.drop_column("fine_tuned_models", "visibility")
    op.drop_column("datasets", "visibility")
