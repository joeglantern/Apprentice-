"""jobs.revise: revision provenance JSON

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("revise", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "revise")
