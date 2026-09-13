"""Add refundable deposits to receipts.

Revision ID: 20260829_0004
Revises: 20260829_0003
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0004"
down_revision: str | None = "20260829_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("receipts") as batch_op:
        batch_op.add_column(sa.Column("subtotal_grosze", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "deposit_total_grosze", sa.Integer(), server_default="0", nullable=False
            )
        )
        batch_op.create_check_constraint(
            "ck_receipt_subtotal_nonnegative",
            "subtotal_grosze IS NULL OR subtotal_grosze >= 0",
        )
        batch_op.create_check_constraint(
            "ck_receipt_deposit_total_nonnegative",
            "deposit_total_grosze >= 0",
        )

    op.create_table(
        "receipt_deposits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("raw_name", sa.String(length=300), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("unit_amount_grosze", sa.Integer(), nullable=False),
        sa.Column("total_grosze", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_receipt_deposit_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_amount_grosze >= 0",
            name="ck_receipt_deposit_unit_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "total_grosze >= 0", name="ck_receipt_deposit_total_nonnegative"
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_receipt_deposit_confidence_range",
        ),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_receipt_deposits_receipt_id", "receipt_deposits", ["receipt_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_receipt_deposits_receipt_id", table_name="receipt_deposits")
    op.drop_table("receipt_deposits")
    with op.batch_alter_table("receipts") as batch_op:
        batch_op.drop_constraint(
            "ck_receipt_deposit_total_nonnegative", type_="check"
        )
        batch_op.drop_constraint("ck_receipt_subtotal_nonnegative", type_="check")
        batch_op.drop_column("deposit_total_grosze")
        batch_op.drop_column("subtotal_grosze")
