"""add FTS5 search index (S67)

Revision ID: e5a9c3d7b481
Revises: d8e4a1c7b392
Create Date: 2026-11-24

Backfills every existing dataset + QA pair through core/fts.ensure_fts —
one shared DDL implementation with the test fixtures, so the migration and
the tests can never index differently. External-content FTS5 tables touch
only NEW shadow tables (datasets_fts_data/_idx/_docsize/_config and the
qa_pairs_* equivalents) plus triggers on the existing tables; old code is
unaffected (the triggers just keep the index warm while the pre-restart
:8090 process keeps writing), which is the zero-downtime shape S58/S75
established.
"""
from core import fts

from alembic import op

revision = "e5a9c3d7b481"
down_revision = "d8e4a1c7b392"
branch_labels = None
depends_on = None


def upgrade() -> None:
    fts.ensure_fts(op.get_bind())


def downgrade() -> None:
    fts.drop_fts(op.get_bind())
