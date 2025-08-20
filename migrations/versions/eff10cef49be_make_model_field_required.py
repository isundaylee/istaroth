"""make_model_field_required

Revision ID: eff10cef49be
Revises: b0db16293531
Create Date: 2025-08-16 23:39:51.128336

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eff10cef49be"
down_revision: Union[str, Sequence[str], None] = "b0db16293531"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # First, update any existing NULL values to empty string or a default value
    op.execute("UPDATE conversations SET model = '' WHERE model IS NULL")

    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.alter_column("model", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert the column to be nullable
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.alter_column("model", nullable=True)
