"""Add proper nouns to conversations

Revision ID: d3f9a07c1b42
Revises: 2f38dc0b3c84
Create Date: 2026-06-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f9a07c1b42"
down_revision: Union[str, Sequence[str], None] = "2f38dc0b3c84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add answer proper nouns persisted for frontend highlighting."""
    op.add_column(
        "conversations",
        sa.Column("proper_nouns", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove persisted answer proper nouns."""
    op.drop_column("conversations", "proper_nouns")
