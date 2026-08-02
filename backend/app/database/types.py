"""Reusable column types.

Centralises how Python enums are persisted so that every table treats them the
same way.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def enum_column(enum_cls: type[StrEnum], *, length: int = 40) -> SAEnum:
    """Persist a :class:`StrEnum` as a checked VARCHAR.

    Deliberately not a native PostgreSQL ``ENUM`` type. Native enums require an
    ``ALTER TYPE`` migration to add a member, which would make adding an asset
    type or fault code a schema change — exactly the friction the SSOT forbids.
    A varchar with a check constraint gives the same validation with none of
    the migration cost.

    The stored form is the member *value* (``"laptop_charger"``), not its name,
    so the database matches the JSON the API emits and the TypeScript union the
    frontend declares.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda enum: [member.value for member in enum],
        validate_strings=True,
    )
