"""drop empty chat threads and index the column the session list orders by

The client used to create a thread on every mount of the chat screen, so a visit
that sent nothing still left a row behind. Those rows are about to become visible in
a sidebar, where they would read as a list of sessions that never happened. Threads
are created lazily now, on the first message, so an empty one cannot be made again
and this is a one-off clear rather than a recurring sweep.

Only threads with no messages go. A thread with messages is a real conversation
whatever state it is in.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM chat_threads
        WHERE thread_id NOT IN (SELECT DISTINCT thread_id FROM chat_messages)
        """
    )
    # list_threads orders by updated_at on every render of the session list; 0007
    # only indexed created_at.
    op.create_index("ix_chat_threads_updated_at", "chat_threads", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_threads_updated_at", table_name="chat_threads")
