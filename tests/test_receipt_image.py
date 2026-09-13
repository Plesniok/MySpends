from io import BytesIO

import pytest
from PIL import Image

from app.services.receipt_image import ReceiptImageError, prepare_receipt_image


def test_receipt_image_is_resized_and_encoded_as_webp() -> None:
    source_buffer = BytesIO()
    Image.new("RGB", (4000, 3000), "white").save(source_buffer, format="JPEG", quality=95)
    source = source_buffer.getvalue()

    prepared = prepare_receipt_image(
        source,
        max_dimension=2000,
        webp_quality=82,
        max_pixels=50_000_000,
    )

    assert prepared.content_type == "image/webp"
    assert prepared.extension == ".webp"
    assert (prepared.width, prepared.height) == (2000, 1500)
    assert len(prepared.data) < len(source)
    with Image.open(BytesIO(prepared.data)) as compressed:
        assert compressed.format == "WEBP"
        assert compressed.size == (2000, 1500)


def test_invalid_receipt_image_is_rejected() -> None:
    with pytest.raises(ReceiptImageError, match="valid supported receipt image"):
        prepare_receipt_image(
            b"not-an-image",
            max_dimension=2000,
            webp_quality=82,
            max_pixels=50_000_000,
        )
