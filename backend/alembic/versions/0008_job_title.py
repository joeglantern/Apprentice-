"""jobs.title: a short name for a finished piece

Nullable with no backfill on purpose. Existing rows keep a null title and the app
falls back to the prompt, which is exactly what it displayed before; naming several
hundred old jobs would mean that many model calls for history nobody asked to rename.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("title", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "title")
