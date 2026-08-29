"""create assets table

Revision ID: 0001
Revises:
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.String(36), primary_key=True),
        sa.Column("source_project", sa.String(200), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_version", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assets_source_project", "assets", ["source_project"])
    op.create_index("ix_assets_captured_at", "assets", ["captured_at"])
    op.create_index("ix_assets_agent_id", "assets", ["agent_id"])
    op.create_index("ix_assets_status", "assets", ["status"])


def downgrade() -> None:
    op.drop_index("ix_assets_status", table_name="assets")
    op.drop_index("ix_assets_agent_id", table_name="assets")
    op.drop_index("ix_assets_captured_at", table_name="assets")
    op.drop_index("ix_assets_source_project", table_name="assets")
    op.drop_table("assets")
