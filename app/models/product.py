import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import TimestampMixin


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("owner_id", "canonical_name", name="uq_product_owner_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(160), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category = relationship("Category", back_populates="products")
    aliases = relationship("ProductAlias", back_populates="product", cascade="all, delete-orphan")


class ProductAlias(TimestampMixin, Base):
    __tablename__ = "product_aliases"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "merchant_key", "normalized_raw_name", name="uq_alias_owner_merchant_raw"
        ),
        Index("ix_alias_normalized_raw_name", "normalized_raw_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    merchant: Mapped[str | None] = mapped_column(String(160), nullable=True)
    merchant_key: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    raw_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_raw_name: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="user")

    product = relationship("Product", back_populates="aliases")
