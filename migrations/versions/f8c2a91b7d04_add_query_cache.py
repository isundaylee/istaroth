"""Add query cache

Revision ID: f8c2a91b7d04
Revises: d3f9a07c1b42
Create Date: 2026-06-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8c2a91b7d04"
down_revision: Union[str, Sequence[str], None] = "d3f9a07c1b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the generic query-result cache table."""
    op.create_table(
        "query_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column(
            "conversation_uuid",
            sa.String(length=36),
            sa.ForeignKey("conversations.uuid"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cache_key", name="uq_query_cache_key"),
    )


def downgrade() -> None:
    """Drop the query-result cache table."""
    op.drop_table("query_cache")
