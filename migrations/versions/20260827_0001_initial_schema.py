"""Initial expense tracking schema.

Revision ID: 20260827_0001
Revises:
Create Date: 2026-08-27
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_owner_id", "categories", ["owner_id"])
    op.create_index("ix_categories_slug", "categories", ["slug"])

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=160), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "canonical_name", name="uq_product_owner_name"),
    )
    op.create_index("ix_products_owner_id", "products", ["owner_id"])
    op.create_index("ix_products_category_id", "products", ["category_id"])

    op.create_table(
        "product_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("merchant", sa.String(length=160), nullable=True),
        sa.Column("merchant_key", sa.String(length=160), nullable=False),
        sa.Column("raw_name", sa.String(length=300), nullable=False),
        sa.Column("normalized_raw_name", sa.String(length=300), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "merchant_key", "normalized_raw_name", name="uq_alias_owner_merchant_raw"
        ),
    )
    op.create_index("ix_product_aliases_owner_id", "product_aliases", ["owner_id"])
    op.create_index("ix_product_aliases_product_id", "product_aliases", ["product_id"])
    op.create_index("ix_alias_normalized_raw_name", "product_aliases", ["normalized_raw_name"])

    op.create_table(
        "receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("merchant", sa.String(length=160), nullable=True),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_grosze", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
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
            "total_grosze IS NULL OR total_grosze >= 0", name="ck_receipt_total_nonnegative"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receipts_owner_id", "receipts", ["owner_id"])
    op.create_index("ix_receipts_merchant", "receipts", ["merchant"])
    op.create_index("ix_receipts_purchased_at", "receipts", ["purchased_at"])
    op.create_index("ix_receipts_status", "receipts", ["status"])

    op.create_table(
        "receipt_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("raw_name", sa.String(length=300), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("unit_price_grosze", sa.Integer(), nullable=True),
        sa.Column("total_price_grosze", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
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
        sa.CheckConstraint("quantity > 0", name="ck_receipt_item_quantity_positive"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_receipt_item_confidence_range",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receipt_items_receipt_id", "receipt_items", ["receipt_id"])
    op.create_index("ix_receipt_items_product_id", "receipt_items", ["product_id"])
    op.create_index("ix_receipt_items_category_id", "receipt_items", ["category_id"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("categories", "products", "product_aliases", "receipts", "receipt_items"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))

    categories = sa.table(
        "categories",
        sa.column("id", sa.Uuid()),
        sa.column("owner_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        categories,
        [
            {
                "id": UUID("10000000-0000-0000-0000-000000000001"),
                "owner_id": None,
                "name": "Nabiał",
                "slug": "nabial",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000002"),
                "owner_id": None,
                "name": "Mięso i ryby",
                "slug": "mieso-i-ryby",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000003"),
                "owner_id": None,
                "name": "Warzywa i owoce",
                "slug": "warzywa-i-owoce",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000004"),
                "owner_id": None,
                "name": "Pieczywo",
                "slug": "pieczywo",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000005"),
                "owner_id": None,
                "name": "Napoje",
                "slug": "napoje",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000006"),
                "owner_id": None,
                "name": "Słodycze i przekąski",
                "slug": "slodycze-i-przekaski",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000007"),
                "owner_id": None,
                "name": "Chemia domowa",
                "slug": "chemia-domowa",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000008"),
                "owner_id": None,
                "name": "Kosmetyki",
                "slug": "kosmetyki",
            },
            {
                "id": UUID("10000000-0000-0000-0000-000000000009"),
                "owner_id": None,
                "name": "Restauracje",
                "slug": "restauracje",
            },
            {
                "id": UUID("10000000-0000-0000-0000-00000000000a"),
                "owner_id": None,
                "name": "Transport",
                "slug": "transport",
            },
            {
                "id": UUID("10000000-0000-0000-0000-00000000000b"),
                "owner_id": None,
                "name": "Zdrowie",
                "slug": "zdrowie",
            },
            {
                "id": UUID("10000000-0000-0000-0000-00000000000c"),
                "owner_id": None,
                "name": "Pozostałe",
                "slug": "pozostale",
            },
        ],
        multiinsert=False,
    )


def downgrade() -> None:
    op.drop_table("receipt_items")
    op.drop_table("receipts")
    op.drop_table("product_aliases")
    op.drop_table("products")
    op.drop_table("categories")
