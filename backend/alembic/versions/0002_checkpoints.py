"""checkpoints table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkpoints",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("base_model", sa.String(200), nullable=False),
        sa.Column("files", sa.JSON(), nullable=False),
        sa.Column("run", sa.JSON(), nullable=False),
        sa.Column("pushed_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_checkpoints_kind", "checkpoints", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_checkpoints_kind", table_name="checkpoints")
    op.drop_table("checkpoints")
