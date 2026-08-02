"""Tenancy and asset hierarchy.

The SSOT scope chain is organisation → location → asset group → asset. Every
query that reaches asset or telemetry data is expected to be filtered by
organisation; one organisation must never see another's data.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import Asset


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tenant. The root of every scope chain."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    locations: Mapped[list[Location]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    asset_groups: Mapped[list[AssetGroup]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    assets: Mapped[list[Asset]] = relationship(back_populates="organization")

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<Organization {self.slug}>"


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A physical site — building, plant, campus or floor.

    ``department`` is carried here rather than as its own table: the SSOT rolls
    OEE up by department but defines no separate department entity, so it is
    modelled as an attribute of the location it belongs to.
    """

    __tablename__ = "locations"
    # Name omitted deliberately: the metadata naming convention derives it as
    # `uq_locations_organization_id_code`. An explicit name here would collide
    # with the identical constraint on `asset_groups`, because PostgreSQL
    # requires constraint names to be unique across the whole schema.
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    building: Mapped[str | None] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(120), index=True)

    organization: Mapped[Organization] = relationship(back_populates="locations")
    assets: Mapped[list[Asset]] = relationship(back_populates="location")

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<Location {self.code}>"


class AssetGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-defined fleet.

    Independent of asset *type*: a group may mix categories, which is why OEE
    fleet rollups are computed over groups rather than over types.
    """

    __tablename__ = "asset_groups"
    # See the note on Location: the convention supplies a table-scoped name.
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(String(400))

    organization: Mapped[Organization] = relationship(back_populates="asset_groups")
    assets: Mapped[list[Asset]] = relationship(back_populates="asset_group")

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<AssetGroup {self.code}>"
