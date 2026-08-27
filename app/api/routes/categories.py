from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import CurrentUser, get_current_user
from app.models import Category
from app.schemas.category import CategoryCreate, CategoryRead
from app.services.text_normalization import slugify

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> list[Category]:
    query = (
        select(Category)
        .where(or_(Category.owner_id.is_(None), Category.owner_id == current_user.id))
        .order_by(Category.name)
    )
    return list(db.scalars(query))


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Category:
    name = " ".join(payload.name.split())
    category_slug = slugify(name)
    existing = db.scalar(
        select(Category).where(
            Category.slug == category_slug,
            or_(Category.owner_id.is_(None), Category.owner_id == current_user.id),
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists")

    category = Category(owner_id=current_user.id, name=name, slug=category_slug)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
