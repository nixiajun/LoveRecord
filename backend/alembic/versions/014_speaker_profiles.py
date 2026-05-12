"""speaker_profiles：人物语言画像蒸馏

Revision ID: 014
Revises: 013
Create Date: 2026-04-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "speaker_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("speaker_role", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("speaking_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("common_phrases", postgresql.JSONB(), nullable=True),
        sa.Column("emoji_habits", postgresql.JSONB(), nullable=True),
        sa.Column("emotional_patterns", postgresql.JSONB(), nullable=True),
        sa.Column("topic_preferences", postgresql.JSONB(), nullable=True),
        sa.Column("communication_traits", postgresql.JSONB(), nullable=True),
        sa.Column("voice_sample", sa.Text(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_speaker_profiles_couple_id", "speaker_profiles", ["couple_id"])
    op.create_index("ix_speaker_profiles_role", "speaker_profiles", ["couple_id", "speaker_role"], unique=True)


def downgrade() -> None:
    op.drop_table("speaker_profiles")
