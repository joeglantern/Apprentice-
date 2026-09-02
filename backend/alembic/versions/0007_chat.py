"""chat_threads and chat_messages: server-side conversation state

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("thread_id", sa.String(length=36), primary_key=True),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("active_job_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_threads_owner", "chat_threads", ["owner"])
    op.create_index("ix_chat_threads_created_at", "chat_threads", ["created_at"])

    op.create_table(
        "chat_messages",
        sa.Column("message_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(length=36),
            sa.ForeignKey("chat_threads.thread_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("landed", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_threads_created_at", table_name="chat_threads")
    op.drop_index("ix_chat_threads_owner", table_name="chat_threads")
    op.drop_table("chat_threads")
