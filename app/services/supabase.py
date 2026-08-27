from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


class SupabaseGateway:
    def __init__(self, client: Client, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def get_user_id(self, access_token: str) -> str:
        response = self.client.auth.get_user(access_token)
        if response.user is None:
            raise ValueError("Supabase did not return a user")
        return str(response.user.id)

    def upload_receipt(self, path: str, file: bytes, content_type: str) -> str:
        response = self.client.storage.from_(self.bucket).upload(
            path=path,
            file=file,
            file_options={
                "cache-control": "3600",
                "content-type": content_type,
                "upsert": "false",
            },
        )
        return getattr(response, "path", None) or path

    def remove_receipt(self, path: str) -> None:
        self.client.storage.from_(self.bucket).remove([path])

    def create_signed_url(self, path: str, expires_in: int) -> str:
        response = self.client.storage.from_(self.bucket).create_signed_url(path, expires_in)
        if isinstance(response, dict):
            url = response.get("signedURL") or response.get("signedUrl")
        else:
            url = getattr(response, "signed_url", None) or getattr(response, "signedURL", None)
        if not url:
            raise RuntimeError("Supabase did not return a signed URL")
        return str(url)

    def ensure_private_bucket(self, max_upload_bytes: int) -> None:
        buckets = self.client.storage.list_buckets()
        bucket_ids = {
            str(bucket.get("id") if isinstance(bucket, dict) else getattr(bucket, "id", ""))
            for bucket in buckets
        }
        if self.bucket not in bucket_ids:
            self.client.storage.create_bucket(
                self.bucket,
                options={
                    "public": False,
                    "allowed_mime_types": [
                        "image/jpeg",
                        "image/png",
                        "image/webp",
                        "image/heic",
                        "image/heif",
                    ],
                    "file_size_limit": max_upload_bytes,
                },
            )


@lru_cache
def get_supabase_gateway() -> SupabaseGateway:
    settings = get_settings()
    settings.require_supabase()
    client = create_client(settings.supabase_url, settings.supabase_server_key)  # type: ignore[arg-type]
    return SupabaseGateway(client, settings.supabase_storage_bucket)
