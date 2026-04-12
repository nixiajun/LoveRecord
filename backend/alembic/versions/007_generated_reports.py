"""generated_reports：归档多 Agent 报表

Revision ID: 007
Revises: 006
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generated_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("report_type", sa.String(16), nullable=False),
        sa.Column("date_range_start", sa.String(16), nullable=False),
        sa.Column("date_range_end", sa.String(16), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body_web", sa.Text(), nullable=False),
        sa.Column("body_wechat", sa.Text(), nullable=False),
        sa.Column("structured_sections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trace", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_reports_couple_id", "generated_reports", ["couple_id"])


def downgrade() -> None:
    op.drop_index("ix_generated_reports_couple_id", table_name="generated_reports")
    op.drop_table("generated_reports")
