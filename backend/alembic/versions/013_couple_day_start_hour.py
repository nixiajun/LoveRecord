"""couples: add day_start_hour

Revision ID: 013
Revises: 012
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("couples", sa.Column("day_start_hour", sa.Integer(), nullable=False, server_default="6"))


def downgrade() -> None:
    op.drop_column("couples", "day_start_hour")
