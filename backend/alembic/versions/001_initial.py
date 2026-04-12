"""initial schema with pgvector

Revision ID: 001
Revises:
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBED_DIM = 1536


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "couples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("partner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "chat_uploads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("upload_date", sa.String(32), nullable=False),
        sa.Column("parse_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("raw_text_excerpt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_chat_uploads_couple_id", "chat_uploads", ["couple_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("upload_id", sa.Integer(), sa.ForeignKey("chat_uploads.id"), nullable=False),
        sa.Column("message_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("day_key", sa.String(16), nullable=False),
        sa.Column("speaker", sa.String(128), nullable=False),
        sa.Column("speaker_role", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_couple_day", "messages", ["couple_id", "day_key"])

    op.create_table(
        "daily_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("day_key", sa.String(16), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_message_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("participants_json", postgresql.JSONB(), nullable=True),
        sa.Column("topics_json", postgresql.JSONB(), nullable=True),
        sa.Column("emotion_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_daily_conv_couple_day", "daily_conversations", ["couple_id", "day_key"])

    op.create_table(
        "daily_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("day_key", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False, server_default=""),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("highlights_json", postgresql.JSONB(), nullable=True),
        sa.Column("mood_tags_json", postgresql.JSONB(), nullable=True),
        sa.Column("conflict_flags_json", postgresql.JSONB(), nullable=True),
        sa.Column("generated_by_model", sa.String(128), nullable=True),
        sa.Column("generation_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("sent_status", sa.String(32), nullable=False, server_default="unsent"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_daily_sum_couple_day", "daily_summaries", ["couple_id", "day_key"])

    op.create_table(
        "weekly_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("week_key", sa.String(16), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("highlights_json", postgresql.JSONB(), nullable=True),
        sa.Column("generated_by_model", sa.String(128), nullable=True),
        sa.Column("generation_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_weekly_sum_couple_week", "weekly_summaries", ["couple_id", "week_key"])

    op.create_table(
        "conversation_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref_id", sa.Integer(), nullable=False),
        sa.Column("day_key", sa.String(16), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_chunks_couple_day", "conversation_chunks", ["couple_id", "day_key"])

    op.create_table(
        "bot_query_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=True),
        sa.Column("channel", sa.String(64), nullable=False, server_default="openclaw"),
        sa.Column("sender_id", sa.String(128), nullable=True),
        sa.Column("sender_name", sa.String(128), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("retrieved_refs_json", postgresql.JSONB(), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ok"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_bot_logs_couple", "bot_query_logs", ["couple_id"])


def downgrade() -> None:
    op.drop_index("ix_bot_logs_couple", table_name="bot_query_logs")
    op.drop_table("bot_query_logs")
    op.drop_index("ix_chunks_couple_day", table_name="conversation_chunks")
    op.drop_table("conversation_chunks")
    op.drop_index("ix_weekly_sum_couple_week", table_name="weekly_summaries")
    op.drop_table("weekly_summaries")
    op.drop_index("ix_daily_sum_couple_day", table_name="daily_summaries")
    op.drop_table("daily_summaries")
    op.drop_index("ix_daily_conv_couple_day", table_name="daily_conversations")
    op.drop_table("daily_conversations")
    op.drop_index("ix_messages_couple_day", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chat_uploads_couple_id", table_name="chat_uploads")
    op.drop_table("chat_uploads")
    op.drop_table("couples")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
