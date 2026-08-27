import re
import unicodedata


def normalize_lookup_text(value: str) -> str:
    """Create a stable lookup key without destroying the user-visible raw value."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def slugify(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or "category"
