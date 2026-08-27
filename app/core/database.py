from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = settings.normalized_database_url
    connect_args: dict[str, object] = {}

    if url.startswith("postgresql+psycopg://"):
        # Compatible with Supavisor transaction mode as well as direct/session connections.
        connect_args["prepare_threshold"] = None
    elif url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
