from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.receipt import ReceiptStatus


class ReceiptItemWrite(BaseModel):
    product_id: UUID | None = None
    category_id: UUID | None = None
    raw_name: str = Field(min_length=1, max_length=300)
    normalized_name: str | None = Field(default=None, max_length=160)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, decimal_places=3)
    unit: str = Field(default="szt", min_length=1, max_length=20)
    unit_price_grosze: int | None = Field(default=None, ge=0)
    original_total_price_grosze: int | None = Field(default=None, ge=0)
    discount_grosze: int = Field(default=0, ge=0)
    total_price_grosze: int = Field(ge=0)
    confidence: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=3)
    bounding_box: dict[str, Any] | None = None

    @model_validator(mode="after")
    def reconcile_discount_amounts(self) -> "ReceiptItemWrite":
        if self.discount_grosze and self.original_total_price_grosze is None:
            self.original_total_price_grosze = (
                self.total_price_grosze + self.discount_grosze
            )
        if (
            self.original_total_price_grosze is not None
            and self.original_total_price_grosze < self.total_price_grosze
        ):
            raise ValueError("Price before discount cannot be lower than final price")
        return self


class ReceiptItemRead(ReceiptItemWrite):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    created_at: datetime


class ReceiptDepositRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    raw_name: str
    quantity: Decimal
    unit_amount_grosze: int
    total_grosze: int
    confidence: Decimal | None
    created_at: datetime


class ReceiptCreate(BaseModel):
    merchant: str | None = Field(default=None, max_length=160)
    purchased_at: datetime | None = None
    total_grosze: int | None = Field(default=None, ge=0)
    currency: str = Field(default="PLN", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ReceiptUpdate(BaseModel):
    merchant: str | None = Field(default=None, max_length=160)
    purchased_at: datetime | None = None
    total_grosze: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: ReceiptStatus | None = None
    raw_ocr_text: str | None = None
    processing_error: str | None = None

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    merchant: str | None
    purchased_at: datetime | None
    total_grosze: int | None
    subtotal_grosze: int | None
    deposit_total_grosze: int
    currency: str
    image_path: str | None
    status: str
    raw_ocr_text: str | None
    extraction_json: dict[str, Any] | None
    processing_error: str | None
    created_at: datetime
    updated_at: datetime
    items: list[ReceiptItemRead] = Field(default_factory=list)
    deposits: list[ReceiptDepositRead] = Field(default_factory=list)


class SignedImageUrl(BaseModel):
    url: str
    expires_in: int
