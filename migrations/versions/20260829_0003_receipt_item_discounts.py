"""Add product-level receipt discounts.

Revision ID: 20260829_0003
Revises: 20260827_0002
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0003"
down_revision: str | None = "20260827_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("receipt_items") as batch_op:
        batch_op.add_column(
            sa.Column("original_total_price_grosze", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("discount_grosze", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_receipt_item_discount_nonnegative",
            "discount_grosze >= 0",
        )
        batch_op.create_check_constraint(
            "ck_receipt_item_original_total_not_lower",
            "original_total_price_grosze IS NULL OR "
            "original_total_price_grosze >= total_price_grosze",
        )


def downgrade() -> None:
    with op.batch_alter_table("receipt_items") as batch_op:
        batch_op.drop_constraint(
            "ck_receipt_item_original_total_not_lower", type_="check"
        )
        batch_op.drop_constraint("ck_receipt_item_discount_nonnegative", type_="check")
        batch_op.drop_column("discount_grosze")
        batch_op.drop_column("original_total_price_grosze")
