"""Use DATABASE_URL for both online migrations and generated SQL."""

from alembic import context

from dream_journey.database import database_url, make_engine
from dream_journey.models import Base
from dream_journey.types import UTCDateTime

target_metadata = Base.metadata


def render_item(kind, item, autogen_context):
    if kind == "type" and isinstance(item, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate_connection(connection) -> None:
    sqlite = connection.dialect.name == "sqlite"
    raw = connection.connection.driver_connection if sqlite else None
    # SQLite table rebuilds must not fire cascading deletes on child tables.
    # Callers provide an untransactioned Connection; PostgreSQL retains transactional DDL.
    if sqlite:
        if raw.in_transaction:
            raise RuntimeError("SQLite migrations require a connection outside a write transaction")
        raw.execute("PRAGMA foreign_keys=OFF")
    try:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=render_item,
            render_as_batch=sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()
            if sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Migration left invalid foreign key references")
        if sqlite:
            connection.commit()
    except BaseException:
        if sqlite:
            connection.rollback()
        raise
    finally:
        if sqlite:
            raw.execute("PRAGMA foreign_keys=ON")


def run_migrations_online() -> None:
    provided_connection = context.config.attributes.get("connection")
    if provided_connection is not None:
        migrate_connection(provided_connection)
        return
    engine = make_engine()
    with engine.connect() as connection:
        migrate_connection(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
