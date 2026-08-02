"""The Digital Twin Engine.

Owns the virtual fleet and drives it forward on a fixed cadence. On each tick
every device produces at most one reading; the batch is handed to a sink — in
production, the Telemetry Layer — which validates, normalises, stores and
broadcasts it.

The engine deliberately knows nothing about persistence or WebSockets. It is a
data *source*, interchangeable with a real sensor gateway, and the sink
indirection is what keeps it that way.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy import select

from app.config import settings
from app.core.logging import get_logger
from app.database.session import session_scope
from app.digital_twin.device import VirtualDevice
from app.digital_twin.profiles import PROFILES, get_profile
from app.models import Asset
from app.schemas.enums import AssetType, TwinScenario
from app.schemas.telemetry import TelemetryIngest
from app.utils.time import utc_now

logger = get_logger(__name__)

#: Signature of a telemetry consumer.
TelemetrySink = Callable[[list[TelemetryIngest]], Awaitable[None]]


@dataclass
class EngineStats:
    """Cumulative counters, exposed by the twin status endpoint."""

    started_at: object | None = None
    ticks: int = 0
    samples_emitted: int = 0
    devices_offline: int = 0
    last_tick_at: object | None = None
    last_tick_duration_ms: float = 0.0
    overruns: int = 0
    errors: int = 0
    device_counts: dict[str, int] = field(default_factory=dict)


class DigitalTwinEngine:
    """Runs a fleet of :class:`VirtualDevice` instances on a fixed interval."""

    def __init__(self, sink: TelemetrySink) -> None:
        self._sink = sink
        self._devices: dict[uuid.UUID, VirtualDevice] = {}
        self._task: asyncio.Task[None] | None = None
        self._running = asyncio.Event()
        self._stopping = asyncio.Event()
        self._interval = settings.twin_interval_seconds
        self.stats = EngineStats()

    # --- Lifecycle -----------------------------------------------------------

    async def load_fleet(self) -> int:
        """Bind a virtual device to every asset in the registry.

        Counters are resumed from the database so that energy and relay
        operations stay monotonic across restarts.
        """
        async with session_scope() as session:
            assets = list(
                (await session.scalars(select(Asset).order_by(Asset.asset_code))).all()
            )

        devices: dict[uuid.UUID, VirtualDevice] = {}
        counts: dict[str, int] = {}

        for asset in assets:
            if asset.asset_type not in PROFILES:
                logger.warning(
                    "No twin profile for asset type; device skipped",
                    extra={"asset_code": asset.asset_code, "asset_type": asset.asset_type},
                )
                continue

            devices[asset.id] = VirtualDevice.create(
                asset_id=asset.id,
                asset_code=asset.asset_code,
                profile=get_profile(asset.asset_type),
                seed=settings.twin_seed,
                initial_energy_kwh=asset.lifetime_energy_kwh,
                initial_relay_operations=asset.relay_operations,
                initial_operating_hours=asset.operating_hours,
            )
            key = asset.asset_type.value
            counts[key] = counts.get(key, 0) + 1

        self._devices = devices
        self.stats.device_counts = counts
        logger.info("Digital Twin fleet loaded", extra={"devices": len(devices), **counts})
        return len(devices)

    async def start(self) -> None:
        """Begin generating telemetry. Idempotent."""
        if self._task is not None and not self._task.done():
            self._running.set()
            return

        if not self._devices:
            await self.load_fleet()

        self._stopping.clear()
        self._running.set()
        self.stats.started_at = utc_now()
        self._task = asyncio.create_task(self._run(), name="digital-twin-engine")
        logger.info(
            "Digital Twin Engine started",
            extra={"devices": len(self._devices), "interval_s": self._interval},
        )

    async def pause(self) -> None:
        """Stop emitting without tearing down the fleet or its accumulated state."""
        self._running.clear()
        logger.info("Digital Twin Engine paused")

    async def stop(self) -> None:
        """Halt the loop and release the task."""
        self._stopping.set()
        self._running.clear()

        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Digital Twin Engine stopped")

    async def reset(self) -> None:
        """Rebuild every virtual device from its current database state."""
        was_running = self.is_running
        await self.stop()
        self._devices.clear()
        self.stats = EngineStats()
        await self.load_fleet()
        if was_running:
            await self.start()
        logger.info("Digital Twin Engine reset")

    # --- Introspection -------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the loop is active and emitting."""
        return (
            self._task is not None
            and not self._task.done()
            and self._running.is_set()
        )

    @property
    def device_count(self) -> int:
        return len(self._devices)

    def status(self) -> dict[str, object]:
        """Full engine status for the twin control endpoint."""
        return {
            "running": self.is_running,
            "enabled": settings.twin_enabled,
            "interval_seconds": self._interval,
            "devices": len(self._devices),
            "device_counts": dict(self.stats.device_counts),
            "ticks": self.stats.ticks,
            "samples_emitted": self.stats.samples_emitted,
            "devices_offline": self.stats.devices_offline,
            "last_tick_at": self.stats.last_tick_at,
            "last_tick_duration_ms": round(self.stats.last_tick_duration_ms, 2),
            "overruns": self.stats.overruns,
            "errors": self.stats.errors,
            "started_at": self.stats.started_at,
        }

    def device_snapshots(self, limit: int = 60) -> list[dict[str, object]]:
        """Per-device diagnostics, capped so the payload stays small."""
        return [device.snapshot() for device in list(self._devices.values())[:limit]]

    def force_scenario(self, asset_id: uuid.UUID, scenario: TwinScenario) -> bool:
        """Drive one device into a scenario on demand.

        Used to demonstrate a specific condition without waiting for it to
        occur naturally.
        """
        device = self._devices.get(asset_id)
        if device is None:
            return False
        device.scenario.force(scenario)
        return True

    def profiles_for(self, asset_type: AssetType) -> object:
        """Expose a profile, for capability queries."""
        return PROFILES.get(asset_type)

    # --- Loop ----------------------------------------------------------------

    async def _run(self) -> None:
        """Fixed-cadence loop with drift correction.

        Scheduling against a monotonic deadline rather than sleeping for a
        fixed duration keeps the 1 Hz cadence honest even when a tick takes
        longer than expected — otherwise the interval silently becomes
        "one second plus however long the work took".
        """
        loop = asyncio.get_running_loop()
        next_deadline = loop.time()

        while not self._stopping.is_set():
            if not self._running.is_set():
                await asyncio.sleep(0.2)
                next_deadline = loop.time()
                continue

            next_deadline += self._interval
            started = time.perf_counter()

            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.stats.errors += 1
                logger.exception("Digital Twin tick failed")

            self.stats.last_tick_duration_ms = (time.perf_counter() - started) * 1000.0

            delay = next_deadline - loop.time()
            if delay > 0:
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=delay)
                    break
                except asyncio.TimeoutError:
                    pass
            else:
                # The tick overran its slot; resynchronise rather than trying
                # to catch up, which would compound the delay.
                self.stats.overruns += 1
                next_deadline = loop.time()

    async def _tick(self) -> None:
        """Advance every device once and forward the batch to the sink."""
        now = utc_now()
        readings: list[TelemetryIngest] = []
        offline = 0

        for device in self._devices.values():
            reading = device.step(now, self._interval)
            if reading is None:
                offline += 1
                continue
            readings.append(reading)

        self.stats.ticks += 1
        self.stats.samples_emitted += len(readings)
        self.stats.devices_offline = offline
        self.stats.last_tick_at = now

        if readings:
            await self._sink(readings)
