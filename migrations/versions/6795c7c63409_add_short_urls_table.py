"""add_short_urls_table

Revision ID: 6795c7c63409
Revises: eff10cef49be
Create Date: 2026-02-26 23:06:44.777702

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6795c7c63409"
down_revision: Union[str, Sequence[str], None] = "eff10cef49be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "short_urls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=16), nullable=False),
        sa.Column("target_path", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_short_urls_slug", "short_urls", ["slug"], unique=True)

    # Backfill: generate a ShortURL for each existing conversation
    import datetime
    import secrets
    import string

    conn = op.get_bind()
    _alphabet = string.ascii_letters + string.digits
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    conversations = conn.execute(sa.text("SELECT uuid FROM conversations")).fetchall()
    for (uuid,) in conversations:
        slug = "".join(secrets.choice(_alphabet) for _ in range(8))
        conn.execute(
            sa.text(
                "INSERT INTO short_urls (slug, target_path, created_at)"
                " VALUES (:slug, :target_path, :now)"
            ),
            {"slug": slug, "target_path": f"/conversation/{uuid}", "now": now},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_short_urls_slug", table_name="short_urls")
    op.drop_table("short_urls")
