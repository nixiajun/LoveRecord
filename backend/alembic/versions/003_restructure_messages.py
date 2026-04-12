"""restructure messages: time name type seq url

Revision ID: 003
Revises: 002
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("messages", "message_time", new_column_name="time")
    op.alter_column("messages", "speaker", new_column_name="name")
    op.alter_column("messages", "message_type", new_column_name="type")
    op.alter_column("messages", "sequence_no", new_column_name="seq")
    op.add_column("messages", sa.Column("url", sa.Text(), nullable=True))
    op.drop_column("messages", "speaker_role")
    op.drop_column("messages", "metadata_json")


def downgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("speaker_role", sa.String(32), nullable=False, server_default="unknown"),
    )
    op.drop_column("messages", "url")
    op.alter_column("messages", "seq", new_column_name="sequence_no")
    op.alter_column("messages", "type", new_column_name="message_type")
    op.alter_column("messages", "name", new_column_name="speaker")
    op.alter_column("messages", "time", new_column_name="message_time")
