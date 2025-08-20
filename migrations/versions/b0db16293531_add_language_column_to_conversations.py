"""Add language column to conversations

Revision ID: b0db16293531
Revises: 854b61397c55
Create Date: 2025-08-10 23:06:33.549870

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0db16293531"
down_revision: Union[str, Sequence[str], None] = "854b61397c55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add language column with default value 'CHS'
    op.add_column(
        "conversations",
        sa.Column("language", sa.String(10), nullable=False, server_default="CHS"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop language column
    op.drop_column("conversations", "language")
