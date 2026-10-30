"""Engine configuration and caller-owned transaction boundaries."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///dream_journey.db"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    url = url or database_url()
    options: dict = {"pool_pre_ping": True, "echo": echo}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        # SQLite otherwise silently accepts orphan foreign keys.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Commit on success; roll back the whole operation on any exception."""
    with factory.begin() as session:
        yield session
