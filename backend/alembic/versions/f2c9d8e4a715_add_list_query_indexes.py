"""add list-query indexes (S44 perf sweep)

Revision ID: f2c9d8e4a715
Revises: a41f7c8e2d90
Create Date: 2026-10-31

S44: every list endpoint so far filters on a foreign key or the S31
visibility column, and none of those columns were indexed (only PKs,
users.email, and bridge token_hash were). Names match the ix_<table>_<col>
convention the ORM's index=True flags generate, so create_all and this
migration stay consistent on fresh vs existing databases.
"""
import sqlalchemy as sa
from alembic import op

revision = "f2c9d8e4a715"
down_revision = "a41f7c8e2d90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # (ix_datasets_visibility / ix_fine_tuned_models_visibility already exist
    # from c3a9d57e2b41/S31 — the ORM index=True flags added this slice match
    # that naming, they are not recreated here.)
    op.create_index("ix_datasets_user_id", "datasets", ["user_id"])
    op.create_index("ix_qa_pairs_dataset_id", "qa_pairs", ["dataset_id"])
    op.create_index("ix_training_runs_user_id", "training_runs", ["user_id"])
    op.create_index("ix_training_runs_dataset_id", "training_runs", ["dataset_id"])
    op.create_index("ix_fine_tuned_models_user_id", "fine_tuned_models", ["user_id"])
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_fine_tuned_model_id", "chat_sessions", ["fine_tuned_model_id"])
    op.create_index("ix_chat_messages_chat_session_id", "chat_messages", ["chat_session_id"])
    op.create_index("ix_bridge_permissions_user_id", "bridge_permissions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_bridge_permissions_user_id", table_name="bridge_permissions")
    op.drop_index("ix_chat_messages_chat_session_id", table_name="chat_messages")
    op.drop_index("ix_chat_sessions_fine_tuned_model_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_index("ix_fine_tuned_models_user_id", table_name="fine_tuned_models")
    op.drop_index("ix_training_runs_dataset_id", table_name="training_runs")
    op.drop_index("ix_training_runs_user_id", table_name="training_runs")
    op.drop_index("ix_qa_pairs_dataset_id", table_name="qa_pairs")
    op.drop_index("ix_datasets_user_id", table_name="datasets")
