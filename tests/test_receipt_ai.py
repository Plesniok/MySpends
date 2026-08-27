import json
from decimal import Decimal

import pytest

from app.services.receipt_ai import OllamaReceiptExtractor, ReceiptAIError, ReceiptExtraction


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
