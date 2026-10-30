"""Keep UTC-aware Python timestamps consistent across PostgreSQL and SQLite."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Datetime values must include a timezone")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        # SQLite's DATETIME storage does not retain the timezone offset.
        if value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
