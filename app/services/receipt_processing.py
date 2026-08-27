from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models import Category, Product, ProductAlias, Receipt, ReceiptItem, ReceiptStatus
from app.services.receipt_ai import (
    ReceiptExtraction,
    ReceiptExtractor,
    money_to_grosze,
    parse_purchase_datetime,
)
from app.services.text_normalization import normalize_lookup_text


def process_receipt_image(
    db: Session,
    receipt: Receipt,
    owner_id: UUID,
    image: bytes,
    content_type: str,
    extractor: ReceiptExtractor,
    auto_complete_confidence: float,
) -> ReceiptExtraction:
    categories = list(
        db.scalars(
            select(Category).where(or_(Category.owner_id.is_(None), Category.owner_id == owner_id))
        )
    )
    extraction = extractor.extract(image, content_type, [category.name for category in categories])
    category_by_key = {normalize_lookup_text(category.name): category for category in categories}

    if extraction.merchant_raw:
        receipt.merchant = " ".join(extraction.merchant_raw.split())
    purchased_at = parse_purchase_datetime(extraction.purchased_at)
    if purchased_at:
        receipt.purchased_at = purchased_at
    extracted_total = money_to_grosze(extraction.total)
    if extracted_total is not None:
        receipt.total_grosze = extracted_total
    receipt.currency = extraction.currency
    receipt.raw_ocr_text = extraction.raw_text
    receipt.extraction_json = extraction.model_dump(mode="json")
    receipt.processing_error = None

    db.execute(delete(ReceiptItem).where(ReceiptItem.receipt_id == receipt.id))
    merchant_key = normalize_lookup_text(receipt.merchant or "")
    item_totals: list[int] = []
    confidences: list[Decimal] = []

    for position, extracted_item in enumerate(extraction.items):
        raw_name = " ".join(extracted_item.raw_name.split())
        raw_key = normalize_lookup_text(raw_name)
        canonical_name = " ".join(extracted_item.normalized_name.casefold().split())
        predicted_category = category_by_key.get(
            normalize_lookup_text(extracted_item.category_name or "")
        )

        alias = db.scalar(
            select(ProductAlias).where(
                ProductAlias.owner_id == owner_id,
                ProductAlias.merchant_key == merchant_key,
                ProductAlias.normalized_raw_name == raw_key,
            )
        )
        product = db.get(Product, alias.product_id) if alias else None

        if product is None:
            product = db.scalar(
                select(Product).where(
                    Product.owner_id == owner_id,
                    Product.canonical_name == canonical_name,
                )
            )
        if product is None:
            product = Product(
                owner_id=owner_id,
                canonical_name=canonical_name,
                category_id=predicted_category.id if predicted_category else None,
            )
            db.add(product)
            db.flush()
        elif product.category_id is None and predicted_category:
            product.category_id = predicted_category.id

        if alias is None:
            db.add(
                ProductAlias(
                    owner_id=owner_id,
                    product_id=product.id,
                    merchant=receipt.merchant,
                    merchant_key=merchant_key,
                    raw_name=raw_name,
                    normalized_raw_name=raw_key,
                    source="ai",
                )
            )
            db.flush()

        total_price_grosze = money_to_grosze(extracted_item.total_price)
        if total_price_grosze is None:
            continue
        unit_price_grosze = money_to_grosze(extracted_item.unit_price)
        category_id = product.category_id or (predicted_category.id if predicted_category else None)
        db.add(
            ReceiptItem(
                receipt_id=receipt.id,
                product_id=product.id,
                category_id=category_id,
                position=position,
                raw_name=raw_name,
                normalized_name=product.canonical_name,
                quantity=extracted_item.quantity,
                unit=extracted_item.unit,
                unit_price_grosze=unit_price_grosze,
                total_price_grosze=total_price_grosze,
                confidence=extracted_item.confidence,
            )
        )
        item_totals.append(total_price_grosze)
        confidences.append(extracted_item.confidence)

    reconciled = (
        receipt.total_grosze is not None and abs(sum(item_totals) - receipt.total_grosze) <= 2
    )
    confidence_ok = bool(confidences) and all(
        confidence >= Decimal(str(auto_complete_confidence)) for confidence in confidences
    )
    receipt.status = (
        ReceiptStatus.COMPLETED.value
        if reconciled and confidence_ok
        else ReceiptStatus.NEEDS_REVIEW.value
    )
    db.commit()
    return extraction
