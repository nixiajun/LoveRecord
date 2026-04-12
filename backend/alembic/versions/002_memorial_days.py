"""memorial_days

Revision ID: 002
Revises: 001
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memorial_days",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_memorial_days_couple_id", "memorial_days", ["couple_id"])


def downgrade() -> None:
    op.drop_index("ix_memorial_days_couple_id", table_name="memorial_days")
    op.drop_table("memorial_days")
