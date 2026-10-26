"""add lora_rank and lora_alpha to training_runs

Revision ID: a41f7c8e2d90
Revises: c3a9d57e2b41
Create Date: 2026-10-26

S33 (#35) advanced hyperparameter panel, backend half: LoRA rank/alpha join
iters/learning_rate on the run row. server_default 8/16 equals mlx_lm.lora's
own defaults, so pre-panel runs and older deploys keep training identically.
"""
import sqlalchemy as sa
from alembic import op

revision = "a41f7c8e2d90"
down_revision = "c3a9d57e2b41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_runs") as batch_op:
        batch_op.add_column(
            sa.Column("lora_rank", sa.Integer(), nullable=False, server_default="8")
        )
        batch_op.add_column(
            sa.Column("lora_alpha", sa.Integer(), nullable=False, server_default="16")
        )


def downgrade() -> None:
    with op.batch_alter_table("training_runs") as batch_op:
        batch_op.drop_column("lora_alpha")
        batch_op.drop_column("lora_rank")
