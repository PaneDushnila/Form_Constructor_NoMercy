from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def new_uuid() -> str:
    """Generate a new UUID string for an entity primary key."""
    return str(uuid4())


def utc_now() -> str:
    """Return the single UTC representation used for all persisted timestamps."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Base(DeclarativeBase):
    """Base class shared by all database models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
