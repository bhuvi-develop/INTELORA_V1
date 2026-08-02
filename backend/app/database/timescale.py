"""TimescaleDB storage tiers.

At 120 devices and 1 Hz the platform writes about **10.4 million telemetry rows
a day**. Raw storage alone is fine for writes and useless for reads: a
thirty-day chart would scan over three hundred million rows to fill a few
hundred pixels, and thirty days of uncompressed rows is tens of gigabytes.

So the telemetry hypertable is read through three tiers:

======================  ==================  ==============================
Query window            Source              Rows scanned for 30 days
======================  ==================  ==============================
up to a few hours       raw hypertable      —
up to a couple of days  ``telemetry_1m``    —
beyond that             ``telemetry_1h``    ~86 000 instead of ~311 000 000
======================  ==================  ==============================

Both rollups are continuous aggregates: TimescaleDB maintains them
incrementally in the background, and because real-time aggregation is left on,
a query against a rollup still sees the newest raw rows that have not been
materialised yet. Nothing is ever lost — the raw hypertable keeps every packet,
compressed roughly ten-to-one once it is a few hours old.

Everything here is idempotent and guarded. On plain PostgreSQL without the
extension the platform still runs correctly, just without partitioning,
compression or rollups, and says so in the log.
"""

from __future__ import annotations

from sqlalchemy import text

from app.config import settings
from app.core.logging import get_logger
from app.database.session import engine

logger = get_logger(__name__)

#: Rollup view names, in ascending granularity.
MINUTE_VIEW = "telemetry_1m"
HOUR_VIEW = "telemetry_1h"

#: Channels rolled up as averages. Cumulative meters are handled separately —
#: averaging a lifetime counter is meaningless, its maximum is the reading.
_AVERAGED_CHANNELS = (
    "voltage_v",
    "current_a",
    "power_w",
    "reactive_power_var",
    "apparent_power_va",
    "frequency_hz",
    "power_factor",
    "temperature_c",
    "indoor_temperature_c",
    "load_percent",
    "battery_percent",
    "health_score",
)


def _rollup_select(source: str, bucket: str) -> str:
    """Build the aggregate projection shared by both rollups.

    Averages, plus min and max on the two channels whose extremes carry
    diagnostic weight — a mean hides the spike that tripped a breaker.
    """
    averages = ",\n        ".join(
        f"avg({channel}) AS {channel}" for channel in _AVERAGED_CHANNELS
    )

    return f"""
    SELECT
        time_bucket(INTERVAL '{bucket}', time) AS bucket,
        asset_id,
        {averages},
        min(power_w)        AS power_w_min,
        max(power_w)        AS power_w_max,
        min(temperature_c)  AS temperature_c_min,
        max(temperature_c)  AS temperature_c_max,
        max(energy_kwh)     AS energy_kwh,
        max(runtime_hours)  AS runtime_hours,
        max(charge_cycles)  AS charge_cycles,
        max(relay_operations) AS relay_operations,
        count(*)            AS samples,
        count(*) FILTER (WHERE quality = 'good')            AS good_samples,
        count(*) FILTER (WHERE operational_state = 'running') AS running_samples
    FROM {source}
    GROUP BY bucket, asset_id
    """


async def _extension_present() -> bool:
    """Whether TimescaleDB is installed in this database."""
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
        )
        return result.scalar() is not None


async def configure_chunking() -> None:
    """Size chunks for the configured write rate.

    The default one-day chunk holds roughly ten million rows here, which is far
    too large to stay resident. Narrower chunks keep recent data in memory and
    let compression and retention operate at a sensible granularity.
    """
    hours = settings.timescale_chunk_interval_hours

    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        try:
            # `INTERVAL :param` is a syntax error — `INTERVAL` introduces a
            # literal, not a value expression, so the placeholder has nowhere
            # to go. Casting a bound string is the parameterised form.
            await connection.execute(
                text(
                    "SELECT set_chunk_time_interval('telemetry', "
                    "CAST(:interval AS INTERVAL))"
                ).bindparams(interval=f"{hours} hours")
            )
        except Exception as error:  # noqa: BLE001 - never block boot on tuning
            logger.warning(
                "Chunk interval not applied; the hypertable keeps its default",
                extra={"reason": str(error).splitlines()[0]},
            )
            return

    logger.info("Chunk interval configured", extra={"chunk_hours": hours})


async def create_continuous_aggregates() -> None:
    """Create the one-minute and one-hour rollups and their refresh policies.

    Both are built from the raw hypertable rather than chaining the hourly view
    off the minute one. Averaging an average across buckets with unequal sample
    counts is subtly wrong, and telemetry gaps make counts unequal routinely.
    """
    statements: list[tuple[str, str]] = [
        (
            f"{MINUTE_VIEW} view",
            f"CREATE MATERIALIZED VIEW IF NOT EXISTS {MINUTE_VIEW} "
            f"WITH (timescaledb.continuous) AS {_rollup_select('telemetry', '1 minute')} "
            "WITH NO DATA",
        ),
        (
            f"{HOUR_VIEW} view",
            f"CREATE MATERIALIZED VIEW IF NOT EXISTS {HOUR_VIEW} "
            f"WITH (timescaledb.continuous) AS {_rollup_select('telemetry', '1 hour')} "
            "WITH NO DATA",
        ),
        (
            f"{MINUTE_VIEW} policy",
            f"""
            SELECT add_continuous_aggregate_policy('{MINUTE_VIEW}',
                start_offset      => INTERVAL '4 hours',
                end_offset        => INTERVAL '1 minute',
                schedule_interval => INTERVAL '1 minute',
                if_not_exists     => TRUE)
            """,
        ),
        (
            f"{HOUR_VIEW} policy",
            f"""
            SELECT add_continuous_aggregate_policy('{HOUR_VIEW}',
                start_offset      => INTERVAL '3 days',
                end_offset        => INTERVAL '1 hour',
                schedule_interval => INTERVAL '10 minutes',
                if_not_exists     => TRUE)
            """,
        ),
    ]

    # Continuous aggregate DDL cannot run inside a transaction block, so this
    # connection runs in autocommit rather than the usual managed transaction.
    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        for label, statement in statements:
            try:
                await connection.execute(text(statement))
            except Exception as error:  # noqa: BLE001 - degrade, never block boot
                logger.warning(
                    "Continuous aggregate step skipped",
                    extra={"step": label, "reason": str(error).splitlines()[0]},
                )

    logger.info("Continuous aggregates ready", extra={"views": [MINUTE_VIEW, HOUR_VIEW]})


async def configure_compression() -> None:
    """Compress telemetry chunks once they are past the hot window.

    Segmenting by ``asset_id`` matters: telemetry is almost always read for one
    asset over a time range, and segmenting on that column lets the engine skip
    every other asset's compressed batches instead of decompressing them.

    The policy age must exceed the window the intelligence layers scan, or
    every cycle would decompress data it is about to read.
    """
    hours = settings.timescale_compress_after_hours

    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        try:
            await connection.execute(
                text(
                    "ALTER TABLE telemetry SET ("
                    "  timescaledb.compress,"
                    "  timescaledb.compress_segmentby = 'asset_id',"
                    "  timescaledb.compress_orderby = 'time DESC'"
                    ")"
                )
            )
            await connection.execute(
                text(
                    "SELECT add_compression_policy('telemetry', "
                    "CAST(:age AS INTERVAL), if_not_exists => TRUE)"
                ).bindparams(age=f"{hours} hours")
            )
        except Exception as error:  # noqa: BLE001 - compression is an optimisation
            logger.warning(
                "Compression not configured; telemetry will be stored uncompressed",
                extra={"reason": str(error).splitlines()[0]},
            )
            return

    logger.info("Compression policy active", extra={"compress_after_hours": hours})


async def configure_storage_tiers() -> None:
    """Apply chunking, rollups and compression, in dependency order."""
    if not await _extension_present():
        logger.warning(
            "TimescaleDB absent; running on plain PostgreSQL. Telemetry is still "
            "stored in full, but without partitioning, compression or rollups "
            "long-range history queries will be slow."
        )
        return

    await configure_chunking()

    if settings.timescale_continuous_aggregates_enabled:
        await create_continuous_aggregates()

    # Compression last: the rollups must exist before chunks start compressing,
    # so their initial materialisation reads uncompressed data.
    if settings.timescale_compression_enabled:
        await configure_compression()


async def rollup_health() -> dict[str, object]:
    """Report what the storage tiers actually contain, for diagnostics."""
    async with engine.connect() as connection:
        try:
            raw = await connection.execute(
                text("SELECT count(*) FROM telemetry")
            )
            minute = await connection.execute(
                text(f"SELECT count(*) FROM {MINUTE_VIEW}")
            )
            hour = await connection.execute(text(f"SELECT count(*) FROM {HOUR_VIEW}"))
            size = await connection.execute(
                text("SELECT pg_size_pretty(hypertable_size('telemetry'))")
            )
            return {
                "raw_rows": int(raw.scalar() or 0),
                "minute_rows": int(minute.scalar() or 0),
                "hour_rows": int(hour.scalar() or 0),
                "hypertable_size": size.scalar(),
            }
        except Exception as error:  # noqa: BLE001 - diagnostics must never fail a request
            return {"available": False, "reason": str(error).splitlines()[0]}
