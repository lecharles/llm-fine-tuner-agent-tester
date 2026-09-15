"""add error_message to training_runs

Revision ID: 3b7c1d9f4a2e
Revises: ef840716d6de
Create Date: 2026-09-15

#42: training failures were silent -- status flipped to "failed" with no error
text stored. This column carries the exception message plus a log tail so the
API and Train UI can surface why a run died.
"""
import sqlalchemy as sa
from alembic import op

revision = "3b7c1d9f4a2e"
down_revision = "ef840716d6de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_runs") as batch_op:
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("training_runs") as batch_op:
        batch_op.drop_column("error_message")
