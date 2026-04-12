"""report_generation_jobs: add progress fields

Revision ID: 012
Revises: 011
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("report_generation_jobs", sa.Column("current_agent", sa.String(64), nullable=True))
    op.add_column("report_generation_jobs", sa.Column("progress_pct", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("report_generation_jobs", "progress_pct")
    op.drop_column("report_generation_jobs", "current_agent")
