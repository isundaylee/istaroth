"""add budget column to conversations

Revision ID: 3c2d29b727da
Revises: f8c2a91b7d04
Create Date: 2026-06-22 03:35:20.660417

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c2d29b727da"
down_revision: Union[str, Sequence[str], None] = "f8c2a91b7d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable budget column to conversations."""
    op.add_column(
        "conversations",
        sa.Column("budget", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Drop budget column."""
    op.drop_column("conversations", "budget")
