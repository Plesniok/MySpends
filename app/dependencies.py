from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.services.supabase import SupabaseGateway, get_supabase_gateway

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if settings.auth_disabled:
        return CurrentUser(id=settings.dev_user_id)

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Supabase access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        gateway: SupabaseGateway = get_supabase_gateway()
        return CurrentUser(id=UUID(gateway.get_user_id(credentials.credentials)))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Supabase access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
