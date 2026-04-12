"""couples: add bot_name and bot_persona

Revision ID: 011
Revises: 010
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("couples", sa.Column("bot_name", sa.String(64), nullable=True))
    op.add_column("couples", sa.Column("bot_persona", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("couples", "bot_persona")
    op.drop_column("couples", "bot_name")
