"""Layer 3 — Preventive Maintenance.

Decides when an asset should be serviced *before* it fails, combining two
independent triggers:

* **Interval** — hours run since the last service, against the profile's
  recommended interval. This is classic time-based maintenance.
* **Condition** — the Layer 2 prediction. An asset heading for failure inside
  its remaining interval should be pulled forward regardless of the clock.

This layer has no page of its own. Its output surfaces on the Predictive and
APM screens, and it answers the Cockpit question "which devices require
maintenance?".
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.digital_twin.profiles import get_profile
from app.intelligence.context import AssetWindow, IntelligenceContext
from app.models import Asset, MaintenanceLog, PredictiveResult, PreventiveResult
from app.schemas.enums import (
    AssetType,
    MaintenanceOutcome,
    MaintenanceTaskType,
    RiskLevel,
)
from app.utils.time import hours_between

#: Fraction of the service interval at which an asset enters the planning
#: window — early enough to schedule, late enough not to waste service life.
DUE_SOON_FRACTION = 0.85

#: Preferred length of a maintenance window, in hours.
WINDOW_HOURS = 8.0

#: Technician hours available per day across the estate.
#:
#: Scheduling has to respect capacity or it is not scheduling. Without a budget
#: every job whose priority implies the same lead time lands on the same
#: morning, and the calendar reports eighty jobs and seventy hours of work in a
#: single day — which no one can act on and which quietly hides whether the
#: team is actually over-committed.
DAILY_CAPACITY_HOURS = 16.0

#: Earliest lead time before work can start, by priority. Severe work jumps the
#: queue; routine work is planned further out.
_LEAD_HOURS: dict[RiskLevel, float] = {
    RiskLevel.SEVERE: 4.0,
    RiskLevel.HIGH: 24.0,
    RiskLevel.MODERATE: 72.0,
    RiskLevel.LOW: 168.0,
}

#: Ordering used when competing for capacity.
_PRIORITY_RANK: dict[RiskLevel, int] = {
    RiskLevel.SEVERE: 0,
    RiskLevel.HIGH: 1,
    RiskLevel.MODERATE: 2,
    RiskLevel.LOW: 3,
}


class CapacityPlanner:
    """Assigns service windows without over-committing any single day.

    Work is placed at the earliest day that has room, from its priority's lead
    time onward. Higher-priority work claims capacity first, so an urgent job
    is never pushed out by a routine one that happened to be processed sooner.
    """

    def __init__(self, origin: datetime, capacity_hours: float) -> None:
        self._origin = origin
        self._capacity = capacity_hours
        self._used: dict[int, float] = {}

    def place(self, priority: RiskLevel, duration_hours: float) -> datetime:
        """Reserve capacity and return when the window opens."""
        earliest = self._origin + timedelta(hours=_LEAD_HOURS[priority])
        day_offset = max(0, (earliest - self._origin).days)

        # Walk forward to the first day with room. Bounded so a fleet larger
        # than the team can service still terminates, piling the remainder on
        # the last day rather than looping — an honest signal of overload.
        for _ in range(180):
            used = self._used.get(day_offset, 0.0)
            if used + duration_hours <= self._capacity or used == 0.0:
                self._used[day_offset] = used + duration_hours
                start = self._origin + timedelta(days=day_offset)
                # Stagger within the day so jobs do not all read as 09:00.
                return start.replace(
                    hour=8, minute=0, second=0, microsecond=0
                ) + timedelta(hours=min(used, 10.0))
            day_offset += 1

        self._used[day_offset] = self._used.get(day_offset, 0.0) + duration_hours
        return self._origin + timedelta(days=day_offset)

    @property
    def committed_days(self) -> int:
        return len(self._used)


def _priority(
    *, interval_ratio: float, risk: RiskLevel | None, rul_hours: float | None
) -> RiskLevel:
    """How urgently the work should be scheduled.

    Severe priority requires the forecast to be both imminent *and* confident.
    A short projected life on its own reflects a steep recent trend, which is
    frequently transient; escalating on that alone marks the whole fleet urgent
    and the ranking stops meaning anything.
    """
    if rul_hours is not None and rul_hours <= 24.0 and risk is RiskLevel.SEVERE:
        return RiskLevel.SEVERE
    if risk in {RiskLevel.SEVERE, RiskLevel.HIGH}:
        return RiskLevel.HIGH
    if interval_ratio >= 1.0:
        return RiskLevel.HIGH
    if interval_ratio >= DUE_SOON_FRACTION:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


async def _latest_predictions(
    session: AsyncSession, context: IntelligenceContext
) -> dict[object, PredictiveResult]:
    """Most recent prediction per asset, from this cycle."""
    rows = (
        await session.scalars(
            select(PredictiveResult).where(
                PredictiveResult.computed_at == context.computed_at
            )
        )
    ).all()
    return {row.asset_id: row for row in rows}


#: Work definitions per asset category. The headline task is the profile's own
#: maintenance description; this is the work behind it, so a technician gets a
#: checklist rather than a sentence.
_BASE_TASKS: dict[AssetType, list[tuple[MaintenanceTaskType, str, float]]] = {
    AssetType.LAPTOP_CHARGER: [
        (MaintenanceTaskType.INSPECTION, "Inspect adapter housing for damage or discolouration", 0.15),
        (MaintenanceTaskType.CLEANING, "Clean connector contacts and vents", 0.2),
        (MaintenanceTaskType.ELECTRICAL_TEST, "Verify output voltage under load", 0.25),
    ],
    AssetType.MOBILE_CHARGER: [
        (MaintenanceTaskType.INSPECTION, "Inspect cable along its length for strain damage", 0.15),
        (MaintenanceTaskType.ELECTRICAL_TEST, "Confirm output stability across the charge curve", 0.2),
    ],
    AssetType.AIR_CONDITIONER: [
        (MaintenanceTaskType.CLEANING, "Clean or replace air filter", 0.5),
        (MaintenanceTaskType.INSPECTION, "Inspect coil and condensate drain", 0.4),
        (MaintenanceTaskType.THERMAL_SERVICE, "Verify refrigerant charge and superheat", 0.75),
        (MaintenanceTaskType.ELECTRICAL_TEST, "Test contactor operation and compressor current", 0.4),
    ],
}

#: Extra work triggered by a specific subsystem being degraded. Condition-based
#: maintenance is the point of the platform: the plan should reflect what is
#: actually wrong, not just what the calendar says.
_COMPONENT_TASKS: dict[str, tuple[MaintenanceTaskType, str, float]] = {
    "supply_path": (
        MaintenanceTaskType.ELECTRICAL_TEST,
        "Measure supply voltage stability at the outlet across a full duty cycle",
        0.5,
    ),
    "conversion_stage": (
        MaintenanceTaskType.COMPONENT_REPLACEMENT,
        "Bench-test the conversion stage; replace if output is below specification",
        1.0,
    ),
    "thermal_path": (
        MaintenanceTaskType.THERMAL_SERVICE,
        "Clear ventilation path and verify heatsink contact",
        0.5,
    ),
    "output_cable": (
        MaintenanceTaskType.COMPONENT_REPLACEMENT,
        "Replace the output cable and connector assembly",
        0.3,
    ),
    "compressor": (
        MaintenanceTaskType.THERMAL_SERVICE,
        "Perform compressor health check: current draw, winding resistance, vibration",
        1.5,
    ),
    "airflow": (
        MaintenanceTaskType.CLEANING,
        "Deep-clean filter, coil and blower assembly",
        0.75,
    ),
    "switching_relay": (
        MaintenanceTaskType.COMPONENT_REPLACEMENT,
        "Inspect contactor for pitting; replace if operation count is near rating",
        0.5,
    ),
}


def _build_work(
    asset_type: AssetType, degraded_components: list[str]
) -> tuple[list[dict], list[dict], float, str | None]:
    """Assemble the task list, checklist and estimated duration.

    Returns the tasks, a checklist derived from them, total estimated hours,
    and the component that drove any condition-based additions.
    """
    entries = list(_BASE_TASKS.get(asset_type, []))
    triggered_by: str | None = None

    for component in degraded_components:
        extra = _COMPONENT_TASKS.get(component)
        if extra is not None:
            entries.append(extra)
            if triggered_by is None:
                triggered_by = component

    tasks = [
        {
            "type": task_type.value,
            "description": description,
            "estimated_hours": hours,
            "condition_based": index >= len(_BASE_TASKS.get(asset_type, [])),
        }
        for index, (task_type, description, hours) in enumerate(entries)
    ]

    checklist = [
        {"step": index + 1, "description": entry["description"], "complete": False}
        for index, entry in enumerate(tasks)
    ]

    duration = round(sum(entry["estimated_hours"] for entry in tasks), 2)
    return tasks, checklist, duration, triggered_by


async def _degraded_components(
    session: AsyncSession, context: IntelligenceContext
) -> dict[uuid.UUID, list[str]]:
    """Subsystems the predictive layer flagged as degraded, per asset."""
    rows = (
        await session.scalars(
            select(PredictiveResult).where(
                PredictiveResult.computed_at == context.computed_at
            )
        )
    ).all()

    degraded: dict[uuid.UUID, list[str]] = {}
    for row in rows:
        if not row.component_health:
            continue
        degraded[row.asset_id] = [
            component["key"]
            for component in row.component_health
            if component.get("degraded")
        ]
    return degraded


async def run(session: AsyncSession, context: IntelligenceContext) -> int:
    """Generate maintenance recommendations for the fleet."""
    predictions = await _latest_predictions(session, context)
    degraded_by_asset = await _degraded_components(session, context)

    # Work already outstanding, indexed by asset. Two things depend on this:
    # not filing a duplicate service record every cycle, and keeping a job that
    # has not started yet aligned with the current plan. A scheduled date that
    # never moves goes stale the moment priorities change, and the calendar
    # then shows a schedule nobody is actually working to.
    outstanding = {
        log.asset_id: log
        for log in (
            await session.scalars(
                select(MaintenanceLog).where(
                    MaintenanceLog.outcome.in_(
                        (
                            MaintenanceOutcome.SCHEDULED,
                            MaintenanceOutcome.IN_PROGRESS,
                        )
                    )
                )
            )
        ).all()
    }

    asset_rows = (
        await session.scalars(
            select(Asset).where(Asset.id.in_(list(context.windows.keys())))
        )
    ).all()
    assets = {asset.id: asset for asset in asset_rows}

    written = 0

    # Two passes. The first works out what each asset needs; the second places
    # that work into the calendar. They have to be separate, because capacity
    # must go to the most urgent job rather than to whichever asset happened to
    # be iterated first.
    assessments: list[dict] = []

    for window in context.assets():
        asset = assets.get(window.identity.id)
        if asset is None:
            continue

        profile = get_profile(window.identity.asset_type)
        interval = profile.maintenance_interval_hours

        # Service age. With no recorded service history the commissioning date
        # is the reference, which is correct for an asset never yet serviced.
        reference = asset.commissioned_at or context.computed_at
        hours_since_service = hours_between(reference, context.computed_at)

        # Blend elapsed calendar hours with metered running hours: an asset
        # that has sat idle has consumed less of its service interval than one
        # that has been under load the whole time.
        effective_hours = max(hours_since_service * 0.4, asset.operating_hours)
        interval_ratio = effective_hours / interval if interval > 0 else 0.0

        prediction = predictions.get(window.identity.id)
        risk = prediction.risk_level if prediction else None
        rul_hours = prediction.remaining_useful_life_hours if prediction else None

        # Condition-based scheduling pulls work forward only for assets the
        # predictive layer genuinely flags. Treating any projected life inside
        # a week as due would put the entire fleet on the schedule at once.
        condition_triggered = risk in {RiskLevel.SEVERE, RiskLevel.HIGH} and (
            rul_hours is None or rul_hours <= 168.0
        )
        interval_triggered = interval_ratio >= DUE_SOON_FRACTION
        due = condition_triggered or interval_ratio >= 1.0

        priority = _priority(
            interval_ratio=interval_ratio, risk=risk, rul_hours=rul_hours
        )

        degraded = degraded_by_asset.get(window.identity.id, [])
        tasks, checklist, duration, triggered_by = _build_work(
            window.identity.asset_type, degraded
        )

        assessments.append(
            {
                "window": window,
                "profile": profile,
                "due": due,
                "interval_triggered": interval_triggered,
                "interval": interval,
                "interval_ratio": interval_ratio,
                "effective_hours": effective_hours,
                "priority": priority,
                "tasks": tasks,
                "checklist": checklist,
                "duration": duration,
                "triggered_by": triggered_by,
            }
        )

    # Second pass: allocate capacity, most urgent first.
    planner = CapacityPlanner(context.computed_at, DAILY_CAPACITY_HOURS)
    assessments.sort(key=lambda item: _PRIORITY_RANK[item["priority"]])

    for item in assessments:
        window = item["window"]
        profile = item["profile"]
        priority = item["priority"]
        due = item["due"]
        duration = item["duration"]
        tasks = item["tasks"]
        checklist = item["checklist"]
        triggered_by = item["triggered_by"]

        if due:
            window_start = planner.place(priority, duration)
        elif item["interval_triggered"]:
            remaining = max(0.0, (1.0 - item["interval_ratio"]) * item["interval"])
            window_start = context.computed_at + timedelta(hours=remaining)
        else:
            window_start = None

        window_end = (
            window_start + timedelta(hours=max(WINDOW_HOURS, duration))
            if window_start is not None
            else None
        )

        # Remind ahead of the window opening, with more notice for lower
        # priorities — an urgent job needs doing now, a routine one needs
        # planning.
        reminder_lead = {
            RiskLevel.SEVERE: 2.0,
            RiskLevel.HIGH: 12.0,
            RiskLevel.MODERATE: 48.0,
            RiskLevel.LOW: 96.0,
        }[priority]
        reminder_at = (
            window_start - timedelta(hours=reminder_lead)
            if window_start is not None
            else None
        )

        plan = PreventiveResult(
            asset_id=window.identity.id,
            computed_at=context.computed_at,
            maintenance_due=due,
            due_at=window_start,
            window_start=window_start,
            window_end=window_end,
            priority=priority,
            task=profile.maintenance_task,
            interval_hours=item["interval"],
            hours_since_service=round(item["effective_hours"], 2),
            tasks=tasks,
            checklist=checklist,
            estimated_duration_hours=duration,
            reminder_at=reminder_at,
            triggered_by_component=triggered_by,
        )
        session.add(plan)
        written += 1

        # Keep the service record in step with the plan, so the platform has an
        # actual maintenance history rather than only a rolling recommendation.
        # Without this every asset reads as "never serviced" forever, and MTTR
        # and maintenance ROI have nothing to compute from.
        if not due:
            continue

        existing = outstanding.get(window.identity.id)

        if existing is None:
            await session.flush()
            session.add(
                MaintenanceLog(
                    asset_id=window.identity.id,
                    preventive_result_id=plan.id,
                    task_type=(
                        MaintenanceTaskType(tasks[0]["type"])
                        if tasks
                        else MaintenanceTaskType.INSPECTION
                    ),
                    title=profile.maintenance_task,
                    description=(
                        f"Condition-based work on {triggered_by.replace('_', ' ')}."
                        if triggered_by
                        else "Interval-based service."
                    ),
                    priority=priority,
                    outcome=MaintenanceOutcome.SCHEDULED,
                    scheduled_for=window_start,
                    window_end=window_end,
                    checklist=checklist,
                    health_before=window.health_last,
                )
            )
        elif existing.outcome is MaintenanceOutcome.SCHEDULED:
            # Not started yet, so it can still move. Work already in progress is
            # left alone — rescheduling a job a technician is stood in front of
            # would be worse than a slightly stale date.
            existing.scheduled_for = window_start
            existing.window_end = window_end
            existing.priority = priority
            existing.checklist = checklist

    return written
