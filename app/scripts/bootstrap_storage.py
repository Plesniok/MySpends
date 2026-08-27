from app.core.config import get_settings
from app.services.supabase import get_supabase_gateway


def main() -> None:
    settings = get_settings()
    get_supabase_gateway().ensure_private_bucket(settings.max_upload_bytes)
    print(f"Private bucket '{settings.supabase_storage_bucket}' is ready.")


if __name__ == "__main__":
    main()
