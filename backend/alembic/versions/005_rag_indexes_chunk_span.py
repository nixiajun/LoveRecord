"""pg_trgm + 复合索引 + conversation_chunks 时间/消息跨度

Revision ID: 005
Revises: 004
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.create_index(
        "ix_messages_couple_id_day_key",
        "messages",
        ["couple_id", "day_key"],
    )
    op.create_index(
        "ix_messages_couple_id_time",
        "messages",
        ["couple_id", "time"],
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_messages_content_trgm ON messages USING gin (content gin_trgm_ops)"
        )
    )

    op.create_index(
        "ix_conversation_chunks_couple_id_day_key",
        "conversation_chunks",
        ["couple_id", "day_key"],
    )
    op.create_index(
        "ix_conversation_chunks_couple_day_chunk_index",
        "conversation_chunks",
        ["couple_id", "day_key", "chunk_index"],
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_conversation_chunks_chunk_text_trgm ON conversation_chunks "
            "USING gin (chunk_text gin_trgm_ops)"
        )
    )

    op.add_column(
        "conversation_chunks",
        sa.Column("start_message_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "conversation_chunks",
        sa.Column("end_message_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "conversation_chunks",
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversation_chunks",
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversation_chunks",
        sa.Column("speaker_roles_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_chunks", "speaker_roles_json")
    op.drop_column("conversation_chunks", "end_time")
    op.drop_column("conversation_chunks", "start_time")
    op.drop_column("conversation_chunks", "end_message_id")
    op.drop_column("conversation_chunks", "start_message_id")

    op.execute(sa.text("DROP INDEX IF EXISTS ix_conversation_chunks_chunk_text_trgm"))
    op.drop_index(
        "ix_conversation_chunks_couple_day_chunk_index",
        table_name="conversation_chunks",
    )
    op.drop_index("ix_conversation_chunks_couple_id_day_key", table_name="conversation_chunks")

    op.execute(sa.text("DROP INDEX IF EXISTS ix_messages_content_trgm"))
    op.drop_index("ix_messages_couple_id_time", table_name="messages")
    op.drop_index("ix_messages_couple_id_day_key", table_name="messages")
