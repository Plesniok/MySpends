from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    Product,
    ProductAlias,
    Receipt,
    ReceiptDeposit,
    ReceiptItem,
    ReceiptStatus,
)
from app.services.receipt_ai import (
    ReceiptExtraction,
    ReceiptExtractor,
    discount_to_grosze,
    money_to_grosze,
    parse_purchase_datetime,
)
from app.services.text_normalization import normalize_lookup_text

DISCOUNT_LINE_PREFIXES = ("rabat", "opust", "znizka", "kupon rabatowy")


def _is_standalone_discount_line(raw_name: str, normalized_name: str) -> bool:
    key = normalize_lookup_text(f"{raw_name} {normalized_name}")
    return any(key == prefix or key.startswith(f"{prefix} ") for prefix in DISCOUNT_LINE_PREFIXES)


def _is_standalone_deposit_line(raw_name: str, normalized_name: str) -> bool:
    key = normalize_lookup_text(f"{raw_name} {normalized_name}")
    return key == "kaucja" or key.startswith("kaucja ")


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
    extracted_subtotal = money_to_grosze(extraction.subtotal)
    extracted_deposit_total = money_to_grosze(extraction.deposit_total)
    extracted_total = money_to_grosze(extraction.total)
    receipt.currency = extraction.currency
    receipt.raw_ocr_text = extraction.raw_text
    receipt.extraction_json = extraction.model_dump(mode="json")
    receipt.processing_error = None

    db.execute(delete(ReceiptItem).where(ReceiptItem.receipt_id == receipt.id))
    db.execute(delete(ReceiptDeposit).where(ReceiptDeposit.receipt_id == receipt.id))
    merchant_key = normalize_lookup_text(receipt.merchant or "")
    item_totals: list[int] = []
    deposit_totals: list[int] = []
    confidences: list[Decimal] = []
    last_receipt_item: ReceiptItem | None = None
    last_item_has_structured_discount = False

    for position, extracted_deposit in enumerate(extraction.deposits):
        unit_amount_grosze = money_to_grosze(extracted_deposit.unit_amount)
        deposit_total_grosze = money_to_grosze(extracted_deposit.total)
        if unit_amount_grosze is None or deposit_total_grosze is None:
            continue
        db.add(
            ReceiptDeposit(
                receipt_id=receipt.id,
                position=position,
                raw_name=" ".join(extracted_deposit.raw_name.split()),
                quantity=extracted_deposit.quantity,
                unit_amount_grosze=unit_amount_grosze,
                total_grosze=deposit_total_grosze,
                confidence=extracted_deposit.confidence,
            )
        )
        deposit_totals.append(deposit_total_grosze)
        confidences.append(extracted_deposit.confidence)

    for position, extracted_item in enumerate(extraction.items):
        raw_name = " ".join(extracted_item.raw_name.split())
        raw_key = normalize_lookup_text(raw_name)
        canonical_name = " ".join(extracted_item.normalized_name.casefold().split())

        if _is_standalone_deposit_line(raw_name, canonical_name):
            if extraction.deposits:
                continue
            unit_amount_grosze = money_to_grosze(extracted_item.unit_price)
            deposit_total_grosze = money_to_grosze(extracted_item.total_price)
            if unit_amount_grosze is not None and deposit_total_grosze is not None:
                db.add(
                    ReceiptDeposit(
                        receipt_id=receipt.id,
                        position=len(deposit_totals),
                        raw_name=raw_name,
                        quantity=extracted_item.quantity,
                        unit_amount_grosze=unit_amount_grosze,
                        total_grosze=deposit_total_grosze,
                        confidence=extracted_item.confidence,
                    )
                )
                deposit_totals.append(deposit_total_grosze)
                confidences.append(extracted_item.confidence)
            continue

        if _is_standalone_discount_line(raw_name, canonical_name):
            discount_grosze = discount_to_grosze(
                extracted_item.discount or extracted_item.total_price
            )
            if last_receipt_item is not None and discount_grosze:
                if last_item_has_structured_discount:
                    continue
                original_total = (
                    last_receipt_item.original_total_price_grosze
                    or last_receipt_item.total_price_grosze
                )
                last_receipt_item.original_total_price_grosze = original_total
                last_receipt_item.discount_grosze += discount_grosze
                last_receipt_item.total_price_grosze = max(
                    original_total - last_receipt_item.discount_grosze, 0
                )
                item_totals[-1] = last_receipt_item.total_price_grosze
                confidences[-1] = min(confidences[-1], extracted_item.confidence)
            continue

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
            last_receipt_item = None
            last_item_has_structured_discount = False
            continue
        price_before_discount_grosze = money_to_grosze(
            extracted_item.price_before_discount
        )
        discount_grosze = discount_to_grosze(extracted_item.discount)

        if price_before_discount_grosze is None and discount_grosze:
            price_before_discount_grosze = total_price_grosze + discount_grosze
        elif price_before_discount_grosze is not None:
            expected_total = price_before_discount_grosze - discount_grosze
            if discount_grosze and abs(expected_total - total_price_grosze) > 2:
                if abs(price_before_discount_grosze - total_price_grosze) <= 2:
                    total_price_grosze = max(expected_total, 0)
                else:
                    discount_grosze = max(
                        price_before_discount_grosze - total_price_grosze, 0
                    )
        unit_price_grosze = money_to_grosze(extracted_item.unit_price)
        category_id = product.category_id or (predicted_category.id if predicted_category else None)
        receipt_item = ReceiptItem(
            receipt_id=receipt.id,
            product_id=product.id,
            category_id=category_id,
            position=position,
            raw_name=raw_name,
            normalized_name=product.canonical_name,
            quantity=extracted_item.quantity,
            unit=extracted_item.unit,
            unit_price_grosze=unit_price_grosze,
            original_total_price_grosze=price_before_discount_grosze,
            discount_grosze=discount_grosze,
            total_price_grosze=total_price_grosze,
            confidence=extracted_item.confidence,
        )
        db.add(receipt_item)
        last_receipt_item = receipt_item
        last_item_has_structured_discount = discount_grosze > 0
        item_totals.append(total_price_grosze)
        confidences.append(extracted_item.confidence)

    receipt.deposit_total_grosze = (
        extracted_deposit_total
        if extracted_deposit_total is not None
        else sum(deposit_totals)
    )
    receipt.subtotal_grosze = (
        extracted_subtotal if extracted_subtotal is not None else sum(item_totals)
    )
    receipt.total_grosze = (
        extracted_total
        if extracted_total is not None
        else receipt.subtotal_grosze + receipt.deposit_total_grosze
    )

    products_reconciled = abs(sum(item_totals) - receipt.subtotal_grosze) <= 2
    deposits_reconciled = abs(sum(deposit_totals) - receipt.deposit_total_grosze) <= 2
    grand_total_reconciled = (
        abs(
            receipt.subtotal_grosze
            + receipt.deposit_total_grosze
            - receipt.total_grosze
        )
        <= 2
    )
    reconciled = products_reconciled and deposits_reconciled and grand_total_reconciled
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
