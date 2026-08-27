from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy.orm import Session, sessionmaker
from starlette.datastructures import Headers

from app.api.routes.health import healthcheck
from app.api.routes.products import create_product, create_product_alias, update_product_category
from app.api.routes.receipts import (
    create_receipt,
    get_receipt,
    replace_receipt_items,
    upload_receipt,
)
from app.core.config import Settings
from app.dependencies import CurrentUser
from app.main import app
from app.models import Category, Product, ProductAlias
from app.schemas.product import ProductAliasCreate, ProductCategoryUpdate, ProductCreate
from app.schemas.receipt import ReceiptCreate, ReceiptItemWrite, ReceiptRead
from app.services.receipt_ai import ReceiptExtraction, ReceiptExtractionItem
from tests.conftest import TEST_USER_ID


def test_healthcheck_and_openapi() -> None:
    assert healthcheck() == {"status": "ok"}
    schema = app.openapi()
    assert "/api/v1/receipts/upload" in schema["paths"]
    assert "202" in schema["paths"]["/api/v1/receipts/upload"]["post"]["responses"]
    assert "/api/v1/products/{product_id}/aliases" in schema["paths"]
    assert "/api/v1/products/{product_id}/category" in schema["paths"]


def test_product_alias_and_receipt_flow(db_session: Session, current_user: CurrentUser) -> None:
    category = Category(owner_id=None, name="Nabiał", slug="nabial")
    db_session.add(category)
    db_session.commit()

    product = create_product(
        ProductCreate(canonical_name="Mozzarella", category_id=category.id),
        db_session,
        current_user,
    )
    assert product.canonical_name == "mozzarella"

    alias = create_product_alias(
        product.id,
        ProductAliasCreate(raw_name="MOZZ. GALBANI 125G", merchant="Lidl"),
        db_session,
        current_user,
    )
    assert alias.normalized_raw_name == "mozz galbani 125g"

    receipt = create_receipt(
        ReceiptCreate(
            merchant="Lidl",
            purchased_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
            total_grosze=1098,
            currency="pln",
        ),
        db_session,
        current_user,
    )
    assert receipt.currency == "PLN"

    saved = replace_receipt_items(
        receipt.id,
        [
            ReceiptItemWrite(
                product_id=product.id,
                raw_name="MOZZ. GALBANI 125G",
                quantity="2",
                unit_price_grosze=549,
                total_price_grosze=1098,
                confidence="0.94",
            )
        ],
        db_session,
        current_user,
    )
    response = ReceiptRead.model_validate(saved)
    assert response.status == "needs_review"
    assert response.items[0].normalized_name == "mozzarella"
    assert response.items[0].category_id == category.id
    assert response.items[0].raw_name == "MOZZ. GALBANI 125G"

    assert db_session.query(Category).filter(Category.owner_id == TEST_USER_ID).count() == 0


def test_user_cannot_reference_unknown_product(
    db_session: Session, current_user: CurrentUser
) -> None:
    receipt = create_receipt(ReceiptCreate(currency="PLN"), db_session, current_user)
    with pytest.raises(HTTPException) as error:
        replace_receipt_items(
            receipt.id,
            [
                ReceiptItemWrite(
                    product_id=UUID("99999999-9999-9999-9999-999999999999"),
                    raw_name="UNKNOWN",
                    quantity="1",
                    total_price_grosze=100,
                )
            ],
            db_session,
            current_user,
        )
    assert error.value.status_code == 422
    assert error.value.detail == "Unknown product"


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}

    def upload_receipt(self, path: str, file: bytes, content_type: str) -> str:
        assert content_type == "image/jpeg"
        self.uploaded[path] = file
        return path

    def remove_receipt(self, path: str) -> None:
        self.uploaded.pop(path, None)


class FakeExtractor:
    def extract(
        self, image: bytes, content_type: str, category_names: list[str]
    ) -> ReceiptExtraction:
        assert image == b"fake-jpeg-data"
        assert content_type == "image/jpeg"
        assert "Nabiał" in category_names
        return ReceiptExtraction(
            merchant_raw="STODOŁA MARKET",
            purchased_at="2022-03-09T10:36:00+01:00",
            total="8.40",
            currency="PLN",
            raw_text="MLEKO ŁACIATE BUT. 1 ... BUŁKA MONTOWA 100G",
            items=[
                ReceiptExtractionItem(
                    raw_name="MLEKO ŁACIATE BUT. 1",
                    normalized_name="mleko",
                    quantity="1",
                    unit="szt",
                    unit_price="3.40",
                    total_price="3.40",
                    category_name="Nabiał",
                    confidence="0.96",
                ),
                ReceiptExtractionItem(
                    raw_name="BUŁKA MONTOWA 100G",
                    normalized_name="bułka",
                    quantity="4",
                    unit="szt",
                    unit_price="1.25",
                    total_price="5.00",
                    category_name="Pieczywo",
                    confidence="0.91",
                ),
            ],
        )


def test_receipt_image_upload(db_session: Session, current_user: CurrentUser) -> None:
    dairy = Category(owner_id=None, name="Nabiał", slug="nabial")
    bread = Category(owner_id=None, name="Pieczywo", slug="pieczywo")
    db_session.add_all([dairy, bread])
    db_session.commit()
    storage = FakeStorage()
    background_tasks = BackgroundTasks()
    task_session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False
    )
    upload = UploadFile(
        BytesIO(b"fake-jpeg-data"),
        filename="receipt.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    receipt = upload_receipt(
        file=upload,
        background_tasks=background_tasks,
        merchant=None,
        purchased_at=None,
        total_grosze=None,
        currency="PLN",
        db=db_session,
        session_factory=task_session_factory,
        current_user=current_user,
        settings=Settings(max_upload_bytes=1024),
        storage=storage,  # type: ignore[arg-type]
        extractor=FakeExtractor(),
    )
    assert receipt.image_path is not None
    assert receipt.image_path.startswith(f"{current_user.id}/{receipt.id}/")
    assert storage.uploaded[receipt.image_path] == b"fake-jpeg-data"
    assert receipt.merchant is None
    assert receipt.total_grosze is None
    assert receipt.status == "processing"
    assert receipt.items == []
    assert len(background_tasks.tasks) == 1
    assert db_session.query(Product).count() == 0

    queued_task = background_tasks.tasks[0]
    queued_task.func(*queued_task.args, **queued_task.kwargs)
    processed = get_receipt(receipt.id, db_session, current_user)

    assert processed.merchant == "STODOŁA MARKET"
    assert processed.total_grosze == 840
    assert processed.status == "completed"
    assert len(processed.items) == 2
    assert processed.items[0].raw_name == "MLEKO ŁACIATE BUT. 1"
    assert processed.items[0].normalized_name == "mleko"
    assert processed.items[1].quantity == 4
    assert processed.items[1].unit_price_grosze == 125
    assert db_session.query(Product).count() == 2
    assert db_session.query(ProductAlias).count() == 2

    milk = db_session.query(Product).filter(Product.canonical_name == "mleko").one()
    updated = update_product_category(
        milk.id,
        ProductCategoryUpdate(category_id=bread.id),
        db_session,
        current_user,
    )
    assert updated.category_id == bread.id
    db_session.refresh(processed.items[0])
    assert processed.items[0].category_id == bread.id
