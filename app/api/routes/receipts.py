import logging
import uuid
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import get_db, get_session_factory
from app.dependencies import CurrentUser, get_current_user
from app.models import Category, Product, Receipt, ReceiptItem, ReceiptStatus
from app.schemas.receipt import (
    ReceiptCreate,
    ReceiptItemWrite,
    ReceiptRead,
    ReceiptUpdate,
    SignedImageUrl,
)
from app.services.receipt_ai import ReceiptAIError, ReceiptExtractor, get_receipt_extractor
from app.services.receipt_image import ReceiptImageError, prepare_receipt_image
from app.services.receipt_processing import process_receipt_image
from app.services.supabase import SupabaseGateway, get_supabase_gateway

router = APIRouter(prefix="/receipts", tags=["receipts"])
logger = logging.getLogger(__name__)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _process_receipt_in_background(
    session_factory: sessionmaker[Session],
    receipt_id: UUID,
    owner_id: UUID,
    image: bytes,
    content_type: str,
    extractor: ReceiptExtractor,
    auto_complete_confidence: float,
) -> None:
    """Process a receipt after the upload response using an independent DB session."""
    db = session_factory()
    try:
        receipt = db.scalar(
            select(Receipt).where(Receipt.id == receipt_id, Receipt.owner_id == owner_id)
        )
        if not receipt:
            logger.error("Receipt %s disappeared before background processing", receipt_id)
            return

        process_receipt_image(
            db=db,
            receipt=receipt,
            owner_id=owner_id,
            image=image,
            content_type=content_type,
            extractor=extractor,
            auto_complete_confidence=auto_complete_confidence,
        )
    except ReceiptAIError as exc:
        db.rollback()
        failed_receipt = db.get(Receipt, receipt_id)
        if failed_receipt:
            failed_receipt.status = ReceiptStatus.FAILED.value
            failed_receipt.processing_error = str(exc)[:2000]
            db.commit()
        logger.warning("Receipt AI extraction failed for %s: %s", receipt_id, exc)
    except Exception:
        db.rollback()
        failed_receipt = db.get(Receipt, receipt_id)
        if failed_receipt:
            failed_receipt.status = ReceiptStatus.FAILED.value
            failed_receipt.processing_error = "Unexpected receipt processing error"
            db.commit()
        logger.exception("Unexpected receipt processing failure for %s", receipt_id)
    finally:
        db.close()


def _get_owned_receipt(db: Session, receipt_id: UUID, owner_id: UUID) -> Receipt:
    receipt = db.scalar(
        select(Receipt)
        .options(selectinload(Receipt.items), selectinload(Receipt.deposits))
        .execution_options(populate_existing=True)
        .where(Receipt.id == receipt_id, Receipt.owner_id == owner_id)
    )
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    return receipt


@router.get("", response_model=list[ReceiptRead])
def list_receipts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Receipt]:
    query = (
        select(Receipt)
        .options(selectinload(Receipt.items), selectinload(Receipt.deposits))
        .where(Receipt.owner_id == current_user.id)
        .order_by(Receipt.purchased_at.desc().nullslast(), Receipt.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(query))


@router.post("", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def create_receipt(
    payload: ReceiptCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Receipt:
    receipt = Receipt(owner_id=current_user.id, **payload.model_dump())
    db.add(receipt)
    db.commit()
    return _get_owned_receipt(db, receipt.id, current_user.id)


@router.post("/upload", response_model=ReceiptRead, status_code=status.HTTP_202_ACCEPTED)
def upload_receipt(
    file: Annotated[UploadFile, File(description="JPEG, PNG, WebP, HEIC or HEIF receipt")],
    background_tasks: BackgroundTasks,
    merchant: Annotated[str | None, Form(max_length=160)] = None,
    purchased_at: Annotated[datetime | None, Form()] = None,
    total_grosze: Annotated[int | None, Form(ge=0)] = None,
    currency: Annotated[str, Form(min_length=3, max_length=3)] = "PLN",
    db: Session = Depends(get_db),
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    storage: SupabaseGateway = Depends(get_supabase_gateway),
    extractor: ReceiptExtractor = Depends(get_receipt_extractor),
) -> Receipt:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Supported formats: JPEG, PNG, WebP, HEIC and HEIF",
        )

    contents = file.file.read(settings.max_upload_bytes + 1)
    if not contents:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file")
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large"
        )

    try:
        prepared_image = prepare_receipt_image(
            contents,
            max_dimension=settings.receipt_image_max_dimension,
            webp_quality=settings.receipt_image_webp_quality,
            max_pixels=settings.receipt_image_max_pixels,
        )
    except ReceiptImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    contents = prepared_image.data
    content_type = prepared_image.content_type
    receipt_id = uuid.uuid4()
    extension = prepared_image.extension
    image_path = f"{current_user.id}/{receipt_id}/{uuid.uuid4().hex}{extension}"

    try:
        storage.upload_receipt(image_path, contents, content_type)
    except Exception as exc:
        logger.exception("Supabase Storage upload failed for receipt %s", receipt_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Supabase Storage upload failed. Check the private receipts bucket "
                "and SUPABASE_SECRET_KEY."
            ),
        ) from exc
    receipt = Receipt(
        id=receipt_id,
        owner_id=current_user.id,
        merchant=merchant.strip() if merchant else None,
        purchased_at=purchased_at,
        total_grosze=total_grosze,
        currency=currency.upper(),
        image_path=image_path,
        status=(
            ReceiptStatus.PROCESSING.value
            if settings.receipt_ai_enabled
            else ReceiptStatus.UPLOADED.value
        ),
    )
    db.add(receipt)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.remove_receipt(image_path)
        raise

    if settings.receipt_ai_enabled:
        background_tasks.add_task(
            _process_receipt_in_background,
            session_factory=session_factory,
            receipt_id=receipt.id,
            owner_id=current_user.id,
            image=contents,
            content_type=content_type,
            extractor=extractor,
            auto_complete_confidence=settings.receipt_auto_complete_confidence,
        )
    return _get_owned_receipt(db, receipt.id, current_user.id)


@router.get("/{receipt_id}", response_model=ReceiptRead)
def get_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Receipt:
    return _get_owned_receipt(db, receipt_id, current_user.id)


@router.patch("/{receipt_id}", response_model=ReceiptRead)
def update_receipt(
    receipt_id: UUID,
    payload: ReceiptUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Receipt:
    receipt = _get_owned_receipt(db, receipt_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "status" and value is not None:
            value = value.value
        setattr(receipt, field, value)
    db.commit()
    return _get_owned_receipt(db, receipt.id, current_user.id)


@router.put("/{receipt_id}/items", response_model=ReceiptRead)
def replace_receipt_items(
    receipt_id: UUID,
    payload: list[ReceiptItemWrite],
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Receipt:
    receipt = _get_owned_receipt(db, receipt_id, current_user.id)

    product_ids = {item.product_id for item in payload if item.product_id}
    category_ids = {item.category_id for item in payload if item.category_id}

    products = (
        {
            product.id: product
            for product in db.scalars(
                select(Product).where(
                    Product.owner_id == current_user.id, Product.id.in_(product_ids)
                )
            )
        }
        if product_ids
        else {}
    )
    categories = (
        set(
            db.scalars(
                select(Category.id).where(
                    Category.id.in_(category_ids),
                    or_(Category.owner_id.is_(None), Category.owner_id == current_user.id),
                )
            )
        )
        if category_ids
        else set()
    )

    if set(products) != product_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown product"
        )
    if categories != category_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown category"
        )

    db.execute(delete(ReceiptItem).where(ReceiptItem.receipt_id == receipt.id))
    for position, item in enumerate(payload):
        data = item.model_dump()
        product = products.get(item.product_id)
        if product:
            data["normalized_name"] = data["normalized_name"] or product.canonical_name
            data["category_id"] = data["category_id"] or product.category_id
        db.add(ReceiptItem(receipt_id=receipt.id, position=position, **data))

    receipt.status = ReceiptStatus.NEEDS_REVIEW.value
    db.commit()
    return _get_owned_receipt(db, receipt.id, current_user.id)


@router.get("/{receipt_id}/image-url", response_model=SignedImageUrl)
def get_receipt_image_url(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    storage: SupabaseGateway = Depends(get_supabase_gateway),
) -> SignedImageUrl:
    receipt = _get_owned_receipt(db, receipt_id, current_user.id)
    if not receipt.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt has no image")
    return SignedImageUrl(
        url=storage.create_signed_url(receipt.image_path, settings.signed_url_ttl_seconds),
        expires_in=settings.signed_url_ttl_seconds,
    )


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    storage: SupabaseGateway = Depends(get_supabase_gateway),
) -> None:
    receipt = _get_owned_receipt(db, receipt_id, current_user.id)
    image_path = receipt.image_path
    db.delete(receipt)
    db.commit()
    if image_path:
        storage.remove_receipt(image_path)
