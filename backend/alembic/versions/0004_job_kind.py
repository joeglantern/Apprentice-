"""jobs.kind: poster, image or logo

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("kind", sa.String(16), nullable=False, server_default="poster"),
    )


def downgrade() -> None:
    op.drop_column("jobs", "kind")
