"""bot_identities：OpenClaw 双 bot 身份映射

Revision ID: 009
Revises: 008
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_identities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bot_id", sa.String(64), nullable=False),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("acting_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_role", sa.String(16), nullable=False, server_default="self"),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("gateway_name", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allowed_capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bot_identities_bot_id", "bot_identities", ["bot_id"], unique=True)
    op.create_index("ix_bot_identities_couple_id", "bot_identities", ["couple_id"])


def downgrade() -> None:
    op.drop_index("ix_bot_identities_couple_id", table_name="bot_identities")
    op.drop_index("ix_bot_identities_bot_id", table_name="bot_identities")
    op.drop_table("bot_identities")
