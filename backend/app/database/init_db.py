"""Database bootstrap.

Runs on every application start and is idempotent. Responsible for three
things: creating the schema, converting ``telemetry`` into a TimescaleDB
hypertable, and provisioning the asset registry that the Digital Twin Engine
operates.

Provisioning assets here is deliberate. An asset row is an *identity*, not
telemetry — the twin needs devices to be, in the same way a real deployment
needs commissioned hardware before readings can arrive.
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.database.base import Base
from app.database.session import engine, session_scope
from app.database.timescale import configure_storage_tiers
from app.models import Asset, AssetGroup, Location, Organization
from app.schemas.enums import AssetType, ConnectivityState, LifecycleStage
from app.utils.time import utc_now

logger = get_logger(__name__)

ORGANIZATION_SLUG = "intelora-demo"
ORGANIZATION_NAME = "INTELORA Industries"

# Sites the virtual fleet is distributed across. Department is carried on the
# location because the SSOT rolls OEE up by department without defining a
# separate entity for it.
LOCATION_BLUEPRINT: tuple[tuple[str, str, str, str], ...] = (
    ("HQ-01", "Headquarters Tower", "Tower A", "Corporate Services"),
    ("PLT-02", "Production Plant", "Block B", "Manufacturing"),
    ("DC-03", "Data Centre East", "Hall 1", "IT Infrastructure"),
)

GROUP_BLUEPRINT: tuple[tuple[str, str, str], ...] = (
    ("FLEET-PWR", "Power Delivery Fleet", "Chargers and adapters across all sites."),
    ("FLEET-HVAC", "Climate Control Fleet", "Air conditioning and environmental units."),
)

# Nameplate characteristics per asset type: (manufacturer, model, rated W,
# rated V, group code, name prefix, code prefix).
ASSET_BLUEPRINT: dict[AssetType, tuple[str, str, float, float, str, str, str]] = {
    AssetType.LAPTOP_CHARGER: (
        "Mikos Power",
        "MX-90 GaN",
        90.0,
        230.0,
        "FLEET-PWR",
        "Laptop Charger",
        "LC",
    ),
    AssetType.MOBILE_CHARGER: (
        "Mikos Power",
        "MX-33 Rapid",
        33.0,
        230.0,
        "FLEET-PWR",
        "Mobile Charger",
        "MC",
    ),
    AssetType.AIR_CONDITIONER: (
        "Voltaris Climate",
        "VC-5200 Inverter",
        5200.0,
        400.0,
        "FLEET-HVAC",
        "Air Conditioner",
        "AC",
    ),
}


async def create_schema() -> None:
    """Create any missing tables."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    logger.info("Schema ready", extra={"tables": len(Base.metadata.tables)})


def _default_literal(column) -> str | None:
    """Render a column's default as a SQL literal, if it has a usable one.

    Only scalar defaults qualify. A callable default (``uuid4``, ``utcnow``)
    cannot be expressed as a constant, and backfilling every existing row with
    the *same* generated value would be worse than refusing.
    """
    if column.server_default is not None:
        # Already expressed in the database; the ALTER carries it over.
        return None

    default = column.default
    if default is None or getattr(default, "is_callable", False):
        return None

    value = getattr(default, "arg", None)
    if callable(value) or value is None:
        return None

    # Enums persist as their value, matching `enum_column`'s storage form.
    if isinstance(value, Enum):
        value = value.value

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    return None


async def reconcile_schema() -> None:
    """Add columns that exist in the models but not yet in the database.

    ``create_all`` creates missing *tables* and silently ignores missing
    *columns*, so a release that adds a field to an existing table starts up
    and then fails on the first insert. The alternatives were both bad: drop
    the volume on every schema change, which contradicts "never lose telemetry
    history", or hand-write a migration for what is a purely additive change.

    This walks the model metadata, compares it to what the database actually
    has, and issues ``ADD COLUMN`` for the difference. Strictly additive —
    nothing is dropped, renamed or retyped, so it cannot destroy data. Anything
    beyond adding a nullable column is a real migration and belongs in Alembic,
    which is already a dependency for exactly that purpose.
    """
    added: list[str] = []

    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")

        for table in Base.metadata.sorted_tables:
            existing = await connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :table"
                ).bindparams(table=table.name)
            )
            present = {row[0] for row in existing}
            if not present:
                # Table does not exist yet; create_all will handle it.
                continue

            for column in table.columns:
                if column.name in present:
                    continue

                ddl = column.type.compile(dialect=connection.dialect)
                clause = f'ADD COLUMN IF NOT EXISTS "{column.name}" {ddl}'

                if not column.nullable:
                    # A NOT NULL column needs a value for the rows already
                    # there. SQLAlchemy's `default=` is applied in Python on
                    # insert, so the database knows nothing about it — the
                    # literal has to be handed to PostgreSQL explicitly, which
                    # then backfills existing rows in one pass.
                    literal = _default_literal(column)
                    if literal is None:
                        logger.warning(
                            "Column needs a migration; no default to backfill with",
                            extra={"table": table.name, "column": column.name},
                        )
                        continue
                    clause += f" DEFAULT {literal} NOT NULL"

                try:
                    await connection.execute(
                        text(f'ALTER TABLE "{table.name}" {clause}')
                    )
                    added.append(f"{table.name}.{column.name}")
                except Exception as error:  # noqa: BLE001 - report, do not block
                    logger.warning(
                        "Could not add column",
                        extra={
                            "table": table.name,
                            "column": column.name,
                            "reason": str(error).splitlines()[0],
                        },
                    )

    if added:
        logger.info("Schema reconciled", extra={"columns_added": added})


async def configure_hypertable() -> None:
    """Convert ``telemetry`` into a TimescaleDB hypertable.

    Guarded rather than assumed: the platform still runs correctly on stock
    PostgreSQL, just without time-series partitioning, and refusing to start in
    that case would make local development needlessly brittle.
    """
    async with engine.begin() as connection:
        extension = await connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
        )
        if extension.scalar() is None:
            logger.warning(
                "TimescaleDB extension not present; telemetry remains a plain table. "
                "Time-series partitioning and compression are unavailable."
            )
            return

        await connection.execute(
            text(
                "SELECT create_hypertable("
                "  'telemetry', 'time',"
                "  chunk_time_interval => INTERVAL '1 day',"
                "  if_not_exists => TRUE,"
                "  migrate_data => TRUE"
                ")"
            )
        )
        logger.info("Telemetry hypertable configured", extra={"chunk_interval": "1 day"})


async def _seed_scope(session: AsyncSession) -> Organization:
    """Create the organisation, locations and asset groups if absent."""
    organization = await session.scalar(
        select(Organization).where(Organization.slug == ORGANIZATION_SLUG)
    )
    if organization is None:
        organization = Organization(
            name=ORGANIZATION_NAME,
            slug=ORGANIZATION_SLUG,
            industry="Facility Management",
            timezone="UTC",
        )
        session.add(organization)
        await session.flush()
        logger.info("Organisation provisioned", extra={"slug": ORGANIZATION_SLUG})

    for code, name, building, department in LOCATION_BLUEPRINT:
        exists = await session.scalar(
            select(Location).where(
                Location.organization_id == organization.id, Location.code == code
            )
        )
        if exists is None:
            session.add(
                Location(
                    organization_id=organization.id,
                    code=code,
                    name=name,
                    building=building,
                    department=department,
                )
            )

    for code, name, description in GROUP_BLUEPRINT:
        exists = await session.scalar(
            select(AssetGroup).where(
                AssetGroup.organization_id == organization.id, AssetGroup.code == code
            )
        )
        if exists is None:
            session.add(
                AssetGroup(
                    organization_id=organization.id,
                    code=code,
                    name=name,
                    description=description,
                )
            )

    await session.flush()
    return organization


async def _seed_assets(session: AsyncSession, organization: Organization) -> int:
    """Provision virtual assets up to the configured fleet size.

    Only creates the shortfall, so raising a count in the environment adds
    devices without disturbing existing ones or their history.
    """
    locations = list(
        (
            await session.scalars(
                select(Location)
                .where(Location.organization_id == organization.id)
                .order_by(Location.code)
            )
        ).all()
    )
    groups = {
        group.code: group
        for group in (
            await session.scalars(
                select(AssetGroup).where(AssetGroup.organization_id == organization.id)
            )
        ).all()
    }

    targets: dict[AssetType, int] = {
        AssetType.LAPTOP_CHARGER: settings.twin_laptop_chargers,
        AssetType.MOBILE_CHARGER: settings.twin_mobile_chargers,
        AssetType.AIR_CONDITIONER: settings.twin_air_conditioners,
    }

    now = utc_now()
    created = 0

    for asset_type, target in targets.items():
        existing = await session.scalar(
            select(func.count())
            .select_from(Asset)
            .where(Asset.organization_id == organization.id, Asset.asset_type == asset_type)
        )
        existing = int(existing or 0)
        if existing >= target:
            continue

        manufacturer, model, rated_w, rated_v, group_code, label, prefix = ASSET_BLUEPRINT[
            asset_type
        ]
        group = groups.get(group_code)

        for index in range(existing, target):
            sequence = index + 1
            location = locations[index % len(locations)] if locations else None
            session.add(
                Asset(
                    asset_code=f"{prefix}-{sequence:04d}",
                    name=f"{label} {sequence:02d}",
                    asset_type=asset_type,
                    manufacturer=manufacturer,
                    model=model,
                    serial_number=f"{prefix}{sequence:04d}-{organization.slug[:3].upper()}",
                    organization_id=organization.id,
                    location_id=location.id if location else None,
                    asset_group_id=group.id if group else None,
                    rated_power_w=rated_w,
                    rated_voltage_v=rated_v,
                    # Staggered commissioning dates give the APM layer a real
                    # spread of service ages to compute lifecycle stage from.
                    commissioned_at=now - timedelta(days=90 + (index * 37) % 900),
                    lifecycle_stage=LifecycleStage.NORMAL,
                    connectivity_state=ConnectivityState.UNKNOWN,
                )
            )
            created += 1

    if created:
        logger.info("Assets provisioned", extra={"assets_created": created})
    return created


async def initialise_database() -> None:
    """Full bootstrap: schema, hypertable, storage tiers, scope and registry."""
    await create_schema()
    # Additive column sync, for releases that extend an existing table.
    await reconcile_schema()
    await configure_hypertable()

    # Chunking, rollups and compression. Separate from hypertable creation
    # because these are read-path optimisations that must degrade gracefully:
    # the platform runs correctly without them, just slowly over long ranges.
    await configure_storage_tiers()

    async with session_scope() as session:
        organization = await _seed_scope(session)
        await _seed_assets(session, organization)

    logger.info("Database initialisation complete")
