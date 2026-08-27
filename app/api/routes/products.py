from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models import Category, Product, ProductAlias, ReceiptItem
from app.schemas.product import (
    ProductAliasCreate,
    ProductAliasRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductRead,
)
from app.services.text_normalization import normalize_lookup_text

router = APIRouter(prefix="/products", tags=["products"])


def _accessible_category(db: Session, category_id: UUID, owner_id: UUID) -> Category | None:
    category = db.get(Category, category_id)
    if category and (category.owner_id is None or category.owner_id == owner_id):
        return category
    return None


@router.get("", response_model=list[ProductRead])
def list_products(
    search: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Product]:
    query = select(Product).where(Product.owner_id == current_user.id)
    if search:
        query = query.where(Product.canonical_name.ilike(f"%{search.strip()}%"))
    query = query.order_by(Product.canonical_name).limit(limit)
    return list(db.scalars(query))


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Product:
    canonical_name = " ".join(payload.canonical_name.casefold().split())
    if payload.category_id and not _accessible_category(db, payload.category_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown category"
        )

    product = Product(
        owner_id=current_user.id,
        canonical_name=canonical_name,
        category_id=payload.category_id,
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Product already exists"
        ) from exc
    db.refresh(product)
    return product


@router.patch("/{product_id}/category", response_model=ProductRead)
def update_product_category(
    product_id: UUID,
    payload: ProductCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Product:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == current_user.id)
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if payload.category_id and not _accessible_category(db, payload.category_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown category"
        )

    product.category_id = payload.category_id
    db.execute(
        update(ReceiptItem)
        .where(ReceiptItem.product_id == product.id)
        .values(category_id=payload.category_id)
    )
    db.commit()
    db.refresh(product)
    return product


@router.post(
    "/{product_id}/aliases", response_model=ProductAliasRead, status_code=status.HTTP_201_CREATED
)
def create_product_alias(
    product_id: UUID,
    payload: ProductAliasCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProductAlias:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == current_user.id)
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    merchant = " ".join(payload.merchant.split()) if payload.merchant else None
    alias = ProductAlias(
        owner_id=current_user.id,
        product_id=product.id,
        merchant=merchant,
        merchant_key=normalize_lookup_text(merchant) if merchant else "",
        raw_name=payload.raw_name.strip(),
        normalized_raw_name=normalize_lookup_text(payload.raw_name),
        source="user",
    )
    db.add(alias)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Alias already exists"
        ) from exc
    db.refresh(alias)
    return alias
