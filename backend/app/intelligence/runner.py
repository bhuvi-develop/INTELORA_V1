"""Intelligence Layer orchestration.

Runs the six layers as one ordered pass on a fixed interval. Order matters:
each layer reads the output of the one before it, so anomaly must complete
before predictive, and predictive before preventive.

The pass is transactional. If any layer fails, the whole cycle rolls back —
publishing a prescriptive recommendation derived from a prediction that was
never written would be worse than publishing nothing.
"""

from __future__ import annotations

import asyncio
import time

from app.config import settings
from app.core.logging import get_logger
from app.database.session import session_scope
from app.intelligence.anomaly import run as run_anomaly
from app.intelligence.apm import run as run_apm
from app.intelligence.context import build_context
from app.intelligence.oee import run as run_oee
from app.intelligence.predictive import run as run_predictive
from app.intelligence.prescriptive import run as run_prescriptive
from app.intelligence.preventive import run as run_preventive
from app.intelligence.summaries import build_intelligence_summary
from app.services.alert_service import refresh_cache
from app.websocket.manager import MessageType, connection_manager

logger = get_logger(__name__)


class IntelligenceRunner:
    """Periodic executor for the six intelligence layers."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._interval = settings.intelligence_interval_seconds
        self._cycles = 0
        self._errors = 0
        self._last_duration_ms = 0.0
        self._running_cycle = asyncio.Lock()

    # --- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Begin the periodic pass. Idempotent."""
        if self._task is not None and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="intelligence-runner")
        logger.info("Intelligence runner started", extra={"interval_s": self._interval})

    async def stop(self) -> None:
        """Halt the periodic pass."""
        self._stopping.set()
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Intelligence runner stopped")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict[str, object]:
        return {
            "running": self.is_running,
            "interval_seconds": self._interval,
            "cycles": self._cycles,
            "errors": self._errors,
            "last_duration_ms": round(self._last_duration_ms, 2),
            "window_minutes": settings.intelligence_window_minutes,
        }

    # --- Execution -----------------------------------------------------------

    async def run_cycle(self) -> dict[str, int]:
        """Execute one full pass across all six layers.

        Also invoked directly by the ``POST`` compute endpoints, so a user can
        trigger analysis on demand rather than waiting for the next interval.
        The lock prevents a manual trigger from colliding with the timer.
        """
        async with self._running_cycle:
            started = time.perf_counter()
            counts: dict[str, int] = {}

            async with session_scope() as session:
                context = await build_context(session)

                if not context.windows:
                    return {"assets": 0}

                # Ordered: every layer consumes the one above it.
                counts.update(await run_anomaly(session, context))
                await session.flush()

                counts["predictions"] = await run_predictive(session, context)
                await session.flush()

                counts["maintenance_plans"] = await run_preventive(session, context)
                await session.flush()

                counts["recommendations"] = await run_prescriptive(session, context)
                await session.flush()

                counts["apm_results"] = await run_apm(session, context)
                counts["oee_results"] = await run_oee(session, context)
                counts["assets"] = len(context.windows)

            # A second session: the summary must read committed results.
            async with session_scope() as session:
                summary = await build_intelligence_summary(session)
                alert_summary = await refresh_cache(session)

            await connection_manager.broadcast(
                MessageType.INTELLIGENCE, summary.model_dump(mode="json")
            )
            await connection_manager.broadcast(
                MessageType.ALERT, alert_summary.model_dump(mode="json")
            )

            self._cycles += 1
            self._last_duration_ms = (time.perf_counter() - started) * 1000.0
            return counts

    async def _loop(self) -> None:
        """Run a cycle every interval until stopped."""
        # Let the twin accumulate a little history before the first pass;
        # statistics over three samples are not worth computing.
        await asyncio.sleep(min(self._interval, 8.0))

        while not self._stopping.is_set():
            try:
                counts = await self.run_cycle()
                logger.info(
                    "Intelligence cycle complete",
                    extra={"duration_ms": round(self._last_duration_ms, 1), **counts},
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self._errors += 1
                logger.exception("Intelligence cycle failed")

            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                break
            except asyncio.TimeoutError:
                continue


#: Process-wide runner.
intelligence_runner = IntelligenceRunner()
