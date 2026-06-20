"""Add proper_nouns column to conversations

Revision ID: 7fc4d28e9a1b
Revises: 2f38dc0b3c84
Create Date: 2026-06-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7fc4d28e9a1b"
down_revision: Union[str, Sequence[str], None] = "2f38dc0b3c84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add proper_nouns column to conversations table."""
    op.add_column(
        "conversations",
        sa.Column("proper_nouns", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove proper_nouns column from conversations table."""
    op.drop_column("conversations", "proper_nouns")
