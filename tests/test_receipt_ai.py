import json
from decimal import Decimal

import httpx
import pytest

from app.services.receipt_ai import (
    OllamaReceiptExtractor,
    ReceiptAIError,
    ReceiptExtraction,
    discount_to_grosze,
)


class EmptyOllamaResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "message": {"role": "assistant", "content": "", "thinking": "long reasoning"},
            "done": True,
            "done_reason": "length",
            "eval_count": 4096,
        }


def test_empty_thinking_model_response_has_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.receipt_ai.httpx.post", lambda *args, **kwargs: EmptyOllamaResponse()
    )
    extractor = OllamaReceiptExtractor("http://localhost:11434", "qwen3-vl:4b", 10)

    with pytest.raises(ReceiptAIError) as error:
        extractor.extract(b"image", "image/jpeg", ["Nabiał"])

    assert "done_reason=length" in str(error.value)
    assert "eval_count=4096" in str(error.value)
    assert "'-instruct'" in str(error.value)


def test_extractor_requests_larger_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: dict[str, object] = {}

    def fake_post(*args: object, **kwargs: object) -> httpx.Response:
        captured_request.update(kwargs["json"])  # type: ignore[arg-type]
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "merchant_raw": "Castorama",
                            "total": "860.00",
                            "items": [
                                {
                                    "raw_name": "BECKERS IT'S S",
                                    "normalized_name": "farba",
                                    "quantity": "3",
                                    "unit": "szt",
                                    "unit_price": "168.00",
                                    "total_price": "504.00",
                                    "confidence": "0.9",
                                }
                            ],
                        }
                    )
                }
            },
        )

    monkeypatch.setattr("app.services.receipt_ai.httpx.post", fake_post)
    extractor = OllamaReceiptExtractor(
        "http://localhost:11434", "qwen3-vl:4b-instruct", 10, context_length=8192
    )

    extractor.extract(b"large-image", "image/jpeg", ["Dom i ogród"])

    assert captured_request["options"] == {"temperature": 0, "num_ctx": 8192}


def test_http_error_contains_ollama_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(
        400,
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        json={"error": "request (4580 tokens) exceeds the available context size (4096 tokens)"},
    )
    monkeypatch.setattr("app.services.receipt_ai.httpx.post", lambda *args, **kwargs: response)
    extractor = OllamaReceiptExtractor("http://localhost:11434", "qwen3-vl:4b-instruct", 10)

    with pytest.raises(ReceiptAIError) as error:
        extractor.extract(b"large-image", "image/jpeg", ["Dom i ogród"])

    assert "HTTP 400" in str(error.value)
    assert "4580 tokens" in str(error.value)
    assert "4096 tokens" in str(error.value)


def test_zero_weight_quantity_is_inferred_from_prices() -> None:
    extraction = ReceiptExtraction.model_validate_json(
        json.dumps(
            {
                "merchant_raw": "STODOŁA MARKET",
                "total": "6.43",
                "items": [
                    {
                        "raw_name": "POMIDORY MALINÓWKI",
                        "normalized_name": "pomidory malinowe",
                        "quantity": 0,
                        "unit": "kg",
                        "unit_price": "15.50",
                        "total_price": "6.43",
                        "category_name": "Warzywa i owoce",
                        "confidence": 0.83,
                    }
                ],
            }
        )
    )

    assert extraction.items[0].quantity == Decimal("0.415")


def test_polish_decimal_separator_is_accepted() -> None:
    extraction = ReceiptExtraction.model_validate(
        {
            "merchant_raw": "STODOŁA MARKET",
            "total": "6,43",
            "items": [
                {
                    "raw_name": "POMIDORY MALINÓWKI",
                    "normalized_name": "pomidory malinowe",
                    "quantity": "0,415",
                    "unit": "kg",
                    "unit_price": "15,50",
                    "total_price": "6,43",
                    "category_name": "Warzywa i owoce",
                    "confidence": "0,83",
                }
            ],
        }
    )

    assert extraction.items[0].quantity == Decimal("0.415")
    assert extraction.items[0].confidence == Decimal("0.83")


def test_negative_polish_discount_is_stored_as_positive_grosze() -> None:
    assert discount_to_grosze("-4,60 PLN") == 460
