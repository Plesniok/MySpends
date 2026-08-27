import base64
import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import lru_cache
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import get_settings


class ReceiptExtractionItem(BaseModel):
    raw_name: str = Field(min_length=1, max_length=300)
    normalized_name: str = Field(min_length=1, max_length=160)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    unit: str = Field(default="szt", min_length=1, max_length=20)
    unit_price: str | None = None
    total_price: str
    category_name: str | None = None
    confidence: Decimal = Field(ge=0, le=1, decimal_places=3)

    @field_validator("quantity", "confidence", mode="before")
    @classmethod
    def normalize_decimal_separator(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().replace(",", ".")
        return value

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str) -> str:
        normalized = value.strip().casefold().rstrip(".")
        aliases = {
            "sztuka": "szt",
            "sztuki": "szt",
            "kilogram": "kg",
            "kilogramy": "kg",
            "litr": "l",
            "litry": "l",
        }
        return aliases.get(normalized, normalized or "szt")


class ReceiptExtraction(BaseModel):
    merchant_raw: str | None = Field(default=None, max_length=160)
    purchased_at: str | None = None
    total: str | None = None
    currency: str = Field(default="PLN", min_length=3, max_length=3)
    raw_text: str | None = None
    items: list[ReceiptExtractionItem] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def repair_invalid_quantities(cls, value: object) -> object:
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            return value

        repaired_items: list[object] = []
        for item in value["items"]:
            if not isinstance(item, dict):
                repaired_items.append(item)
                continue

            try:
                quantity = Decimal(str(item.get("quantity")))
            except InvalidOperation:
                repaired_items.append(item)
                continue
            if quantity > 0:
                repaired_items.append(item)
                continue

            try:
                unit_price = Decimal(str(item.get("unit_price")).strip().replace(",", "."))
                total_price = Decimal(str(item.get("total_price")).strip().replace(",", "."))
            except InvalidOperation:
                continue
            if unit_price <= 0 or total_price <= 0:
                continue

            inferred_quantity = (total_price / unit_price).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )
            if inferred_quantity <= 0:
                continue
            repaired_items.append({**item, "quantity": inferred_quantity})

        return {**value, "items": repaired_items}

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class ReceiptAIError(RuntimeError):
    pass


class ReceiptExtractor(Protocol):
    def extract(
        self, image: bytes, content_type: str, category_names: list[str]
    ) -> ReceiptExtraction: ...


class OllamaReceiptExtractor:
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract(
        self, image: bytes, content_type: str, category_names: list[str]
    ) -> ReceiptExtraction:
        prompt = self._prompt(category_names)
        request_body = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": ReceiptExtraction.model_json_schema(),
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(image).decode("ascii")],
                }
            ],
            "options": {"temperature": 0},
        }
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=request_body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                done_reason = payload.get("done_reason", "unknown")
                eval_count = payload.get("eval_count", "unknown")
                model_hint = ""
                if self.model in {"qwen3-vl:2b", "qwen3-vl:4b", "qwen3-vl:8b"} or (
                    "qwen3-vl" in self.model and "thinking" in self.model
                ):
                    model_hint = (
                        " This is a Qwen3-VL thinking variant; use the corresponding "
                        "'-instruct' model for structured receipt extraction."
                    )
                raise ReceiptAIError(
                    "Ollama returned an empty answer "
                    f"(done_reason={done_reason}, eval_count={eval_count}).{model_hint}"
                )
            return ReceiptExtraction.model_validate_json(content)
        except ReceiptAIError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ReceiptAIError(
                f"Ollama could not process the receipt with model '{self.model}': {exc}"
            ) from exc

    @staticmethod
    def _prompt(category_names: list[str]) -> str:
        categories = json.dumps(category_names, ensure_ascii=False)
        return f"""
Jesteś precyzyjnym parserem polskich paragonów fiskalnych. Odczytaj ten jeden paragon.

Zasady:
- merchant_raw: przepisz widoczną nazwę sklepu dokładnie, bez adresu i NIP-u.
- items: zwróć każdą kupioną pozycję osobno. Pomiń podsumowania VAT, SUMA, płatność,
  resztę, numer kasy, NIP i nagłówki.
- raw_name: przepisz nazwę produktu z paragonu bez ilości i ceny; nie poprawiaj skrótów.
- normalized_name: krótka polska nazwa rodzaju produktu małymi literami; usuń markę,
  gramaturę i techniczne skróty, np. "MLEKO ŁACIATE BUT. 1" -> "mleko",
  "CZOSNEK SZT MŁODY" -> "czosnek młody".
- Nie łącz dwóch osobnych wierszy produktu.
- quantity: liczba z paragonu. Dla produktów wagowych zachowaj wartość, np. 0.415.
- unit: używaj głównie "szt", "kg", "l" albo "opak".
- unit_price i total_price: tekst dziesiętny w PLN z kropką, bez symbolu waluty,
  np. "15.50". Nie przeliczaj, jeśli cena jednostkowa nie jest widoczna.
- purchased_at: ISO 8601, jeśli data/czas są czytelne; w przeciwnym razie null.
- total: kwota z wiersza SUMA jako tekst dziesiętny z kropką.
- confidence: ostrożna pewność od 0 do 1 dla całej odczytanej pozycji.
- category_name: wybierz dokładnie jedną nazwę z listy {categories} albo null.
- raw_text: opcjonalna pełna transkrypcja najważniejszej części paragonu.
- Nie wymyślaj produktów, których nie ma na obrazie.
""".strip()


def money_to_grosze(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip().upper().replace("PLN", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ReceiptAIError(f"Invalid money value returned by AI: {value!r}") from exc
    if amount < 0:
        raise ReceiptAIError(f"Negative money value returned by AI: {value!r}")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_purchase_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


@lru_cache
def get_receipt_extractor() -> ReceiptExtractor:
    settings = get_settings()
    return OllamaReceiptExtractor(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.ollama_timeout_seconds,
    )
