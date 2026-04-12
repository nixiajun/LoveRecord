"""messages.speaker_role：情侣空间侧 owner/partner/unknown

Revision ID: 006
Revises: 005
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "speaker_role",
            sa.String(16),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.create_index(
        "ix_messages_couple_id_speaker_role_day_key",
        "messages",
        ["couple_id", "speaker_role", "day_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_couple_id_speaker_role_day_key", table_name="messages")
    op.drop_column("messages", "speaker_role")
