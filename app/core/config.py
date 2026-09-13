from functools import lru_cache
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "my-spends-api"
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./my_spends.db"
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    # Backward compatibility with legacy Supabase projects.
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "receipts"

    auth_disabled: bool = False
    dev_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")

    max_upload_bytes: int = 10 * 1024 * 1024
    receipt_image_max_dimension: int = Field(default=2560, ge=1200, le=6000)
    receipt_image_webp_quality: int = Field(default=82, ge=60, le=95)
    receipt_image_max_pixels: int = Field(default=50_000_000, ge=1_000_000)
    signed_url_ttl_seconds: int = 15 * 60
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    receipt_ai_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3-vl:4b-instruct"
    ollama_context_length: int = 8192
    ollama_timeout_seconds: float = 300
    receipt_auto_complete_confidence: float = 0.70

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def normalized_database_url(self) -> str:
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    def require_supabase(self) -> None:
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_SECRET_KEY", self.supabase_server_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Supabase configuration: {', '.join(missing)}")

    @property
    def supabase_server_key(self) -> str | None:
        """Prefer the current secret key, with legacy service_role as fallback."""
        return self.supabase_secret_key or self.supabase_service_role_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
