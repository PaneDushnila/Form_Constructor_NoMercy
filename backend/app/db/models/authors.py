from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, new_uuid, utc_now

if TYPE_CHECKING:
    from .forms import Form


class Author(Base):
    """Anonymous author session that owns forms."""

    __tablename__ = "authors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    session_expires_at: Mapped[str] = mapped_column(String(27), nullable=False)
    created_at: Mapped[str] = mapped_column(String(27), nullable=False, default=utc_now)

    forms: Mapped[list[Form]] = relationship(back_populates="owner")
