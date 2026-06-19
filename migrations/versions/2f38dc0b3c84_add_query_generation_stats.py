"""Add query generation stats

Revision ID: 2f38dc0b3c84
Revises: c4d8e1f6a2b9
Create Date: 2026-06-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f38dc0b3c84"
down_revision: Union[str, Sequence[str], None] = "c4d8e1f6a2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add persisted query generation statistics."""
    op.add_column(
        "conversations",
        sa.Column("final_generation_input_text_length", sa.Integer(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("retrieval_unique_chunk_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("retrieval_unique_file_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove persisted query generation statistics."""
    op.drop_column("conversations", "retrieval_unique_file_count")
    op.drop_column("conversations", "retrieval_unique_chunk_count")
    op.drop_column("conversations", "final_generation_input_text_length")
