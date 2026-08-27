"""Add fields used by automatic receipt extraction.

Revision ID: 20260827_0002
Revises: 20260827_0001
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0002"
down_revision: str | None = "20260827_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("receipts", sa.Column("extraction_json", sa.JSON(), nullable=True))
    op.add_column(
        "receipt_items",
        sa.Column("unit", sa.String(length=20), server_default="szt", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("receipt_items", "unit")
    op.drop_column("receipts", "extraction_json")
