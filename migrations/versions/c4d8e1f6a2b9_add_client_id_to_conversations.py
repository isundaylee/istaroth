"""Add client_id column to conversations

Revision ID: c4d8e1f6a2b9
Revises: 6795c7c63409
Create Date: 2026-06-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8e1f6a2b9"
down_revision: Union[str, Sequence[str], None] = "6795c7c63409"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "conversations",
        sa.Column("client_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_conversations_client_id_id", "conversations", ["client_id", "id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_conversations_client_id_id", table_name="conversations")
    op.drop_column("conversations", "client_id")
