"""Platform settings.

A narrow key-value table rather than a wide column-per-setting one: settings
are added and removed far more often than they are queried relationally, and a
new preference should never require a migration.
"""

from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SystemSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One configuration entry, scoped to the platform."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="general")
    description: Mapped[str | None] = mapped_column(Text)
