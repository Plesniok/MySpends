import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import TimestampMixin


class ReceiptStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"
    FAILED = "failed"


class Receipt(TimestampMixin, Base):
    __tablename__ = "receipts"
    __table_args__ = (
        CheckConstraint(
            "total_grosze IS NULL OR total_grosze >= 0", name="ck_receipt_total_nonnegative"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    merchant: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    purchased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    total_grosze: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PLN")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ReceiptStatus.UPLOADED.value, index=True
    )
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    items = relationship(
        "ReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="ReceiptItem.position",
    )


class ReceiptItem(TimestampMixin, Base):
    __tablename__ = "receipt_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_receipt_item_quantity_positive"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_receipt_item_confidence_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="szt")
    unit_price_grosze: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_price_grosze: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    bounding_box: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    receipt = relationship("Receipt", back_populates="items")
    product = relationship("Product")
    category = relationship("Category")
