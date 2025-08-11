"""add uuid column for conversations

Revision ID: 854b61397c55
Revises: 51e030967e15
Create Date: 2025-08-10 21:13:30.560664

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "854b61397c55"
down_revision: Union[str, Sequence[str], None] = "51e030967e15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add uuid column and populate for existing conversations."""
    # Add uuid column as nullable first
    op.add_column("conversations", sa.Column("uuid", sa.String(36), nullable=True))

    # Generate UUIDs for existing conversations
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT id FROM conversations"))
    for row in result:
        conversation_id = row[0]
        new_uuid = str(uuid.uuid4())
        connection.execute(
            sa.text("UPDATE conversations SET uuid = :uuid WHERE id = :id"),
            {"uuid": new_uuid, "id": conversation_id},
        )

    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # Create new table with uuid as non-nullable
    op.create_table(
        "conversations_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("k", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("generation_time_seconds", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid", name="uq_conversations_uuid"),
    )

    # Copy data from old table to new table
    connection.execute(
        sa.text(
            """
        INSERT INTO conversations_new (id, uuid, question, answer, model, k, created_at, generation_time_seconds)
        SELECT id, uuid, question, answer, model, k, created_at, generation_time_seconds
        FROM conversations
    """
        )
    )

    # Drop old table and rename new table
    op.drop_table("conversations")
    op.rename_table("conversations_new", "conversations")


def downgrade() -> None:
    """Remove uuid column."""
    op.drop_constraint("uq_conversations_uuid", "conversations", type_="unique")
    op.drop_column("conversations", "uuid")
