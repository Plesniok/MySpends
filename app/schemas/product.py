from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=160)
    category_id: UUID | None = None


class ProductCategoryUpdate(BaseModel):
    category_id: UUID | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_name: str
    category_id: UUID | None
    created_at: datetime


class ProductAliasCreate(BaseModel):
    raw_name: str = Field(min_length=1, max_length=300)
    merchant: str | None = Field(default=None, max_length=160)


class ProductAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    merchant: str | None
    raw_name: str
    normalized_raw_name: str
    source: str
    created_at: datetime
