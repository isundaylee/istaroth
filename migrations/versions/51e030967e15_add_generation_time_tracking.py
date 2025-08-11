"""Add generation time tracking

Revision ID: 51e030967e15
Revises: e9d1d31f1d66
Create Date: 2025-08-10 20:14:12.536624

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "51e030967e15"
down_revision: Union[str, Sequence[str], None] = "e9d1d31f1d66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add generation_time_seconds column to conversations table."""
    op.add_column(
        "conversations", sa.Column("generation_time_seconds", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    """Remove generation_time_seconds column from conversations table."""
    op.drop_column("conversations", "generation_time_seconds")
