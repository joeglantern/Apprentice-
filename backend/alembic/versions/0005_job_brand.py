"""jobs.brand: optional brand kit JSON

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("brand", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "brand")
