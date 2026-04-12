"""report_generation_jobs：后台报表生成队列

Revision ID: 008
Revises: 007
Create Date: 2026-04-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_generation_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("couple_id", sa.Integer(), sa.ForeignKey("couples.id"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("report_type", sa.String(16), nullable=False),
        sa.Column("day_key", sa.String(16), nullable=True),
        sa.Column("date_range_start", sa.String(16), nullable=False),
        sa.Column("date_range_end", sa.String(16), nullable=False),
        sa.Column("include_debug", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("saved_report_id", sa.Integer(), sa.ForeignKey("generated_reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_generation_jobs_couple_id", "report_generation_jobs", ["couple_id"])
    op.create_index("ix_report_generation_jobs_status", "report_generation_jobs", ["status"])
    op.create_index("ix_report_generation_jobs_saved_report_id", "report_generation_jobs", ["saved_report_id"])


def downgrade() -> None:
    op.drop_index("ix_report_generation_jobs_saved_report_id", table_name="report_generation_jobs")
    op.drop_index("ix_report_generation_jobs_status", table_name="report_generation_jobs")
    op.drop_index("ix_report_generation_jobs_couple_id", table_name="report_generation_jobs")
    op.drop_table("report_generation_jobs")
