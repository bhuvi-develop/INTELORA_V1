"""Mission Control assembly.

The Enterprise Cockpit aggregates every intelligence layer into one executive
screen, so this module is where cross-layer roll-up happens. Doing it here
rather than in the browser is what keeps the Presentation Layer free of
business logic and the first paint inside its five-second budget.

Two paths, deliberately different in cost:

* :func:`build_live_tick` runs once per second and touches memory only.
* :func:`build_cockpit_overview` runs on page load and may query the database.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.digital_twin.profiles import PROFILE_ORDER, get_profile
from app.schemas.asset import AssetBusinessModel
from app.schemas.dashboard import (
    ActivityItem,
    ChartBundle,
    CockpitOverview,
    DistributionSlice,
    EnergySummary,
    KpiValue,
    LiveTick,
    SystemStatus,
)
from app.schemas.enums import ConnectivityState, HealthState
from app.schemas.intelligence import IntelligenceSummary
from app.schemas.telemetry import ChartSeries, SeriesPoint
from app.services.alert_service import alert_cache
from app.services.business_model import (
    build_all_business_models,
    energy_ledger,
    summarise_asset_types,
)
from app.services.live_state import live_state
from app.utils.time import utc_now

#: Entries retained in the Cockpit activity feed.
ACTIVITY_HISTORY = 40


class ActivityLog:
    """Rolling feed of notable platform events.

    A human-readable event stream, distinct from the raw telemetry table: this
    answers "what just happened", not "what was the voltage".
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: deque[ActivityItem] = deque(maxlen=ACTIVITY_HISTORY)

    def add(
        self,
        *,
        kind: str,
        severity: str,
        title: str,
        detail: str,
        asset_id: uuid.UUID | None = None,
        asset_code: str | None = None,
        occurred_at: datetime | None = None,
    ) -> ActivityItem:
        item = ActivityItem(
            id=str(uuid.uuid4()),
            kind=kind,
            severity=severity,
            title=title,
            detail=detail,
            asset_id=asset_id,
            asset_code=asset_code,
            occurred_at=occurred_at or utc_now(),
        )
        with self._lock:
            self._items.appendleft(item)
        return item

    def recent(self, limit: int = 12) -> list[ActivityItem]:
        with self._lock:
            return list(self._items)[:limit]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


activity_log = ActivityLog()


# --- Energy -------------------------------------------------------------------


def build_energy_summary(models: list[AssetBusinessModel]) -> EnergySummary:
    """Energy and its business translation.

    ``coverage`` is reported explicitly because not every asset type meters
    energy. A total presented without that caveat would imply completeness the
    fleet does not have.
    """
    metered = [m for m in models if m.energy_kwh is not None]
    today_kwh = sum(m.energy_kwh or 0.0 for m in metered)
    live_power = sum(m.power_w or 0.0 for m in models)
    total = len(models)

    return EnergySummary(
        today_kwh=round(today_kwh, 3),
        today_cost=round(today_kwh * settings.energy_tariff_per_kwh, 2),
        today_saving=0.0,  # supplied by the Prescriptive layer; see overview
        lifetime_kwh=0.0,
        live_power_w=round(live_power, 1),
        currency=settings.currency_code,
        tariff_per_kwh=settings.energy_tariff_per_kwh,
        metered_assets=len(metered),
        total_assets=total,
        coverage=round(len(metered) / total, 3) if total else 0.0,
    )


# --- System status -------------------------------------------------------------


def build_system_status(models: list[AssetBusinessModel]) -> SystemStatus:
    """The single dominant verdict at the top of the Cockpit.

    One sentence, readable in under five seconds, with the counts that justify
    it. The verdict escalates on the worst condition present rather than on an
    average, because an average hides the one asset that is failing.
    """
    total = len(models)
    online = sum(1 for m in models if m.connectivity_state is ConnectivityState.ONLINE)
    critical = sum(1 for m in models if m.health_state is HealthState.CRITICAL)
    warning = sum(1 for m in models if m.health_state is HealthState.WARNING)
    offline = sum(1 for m in models if m.connectivity_state is ConnectivityState.OFFLINE)

    summary = alert_cache.summary
    live = live_state.has_data

    if not live or total == 0:
        return SystemStatus(
            state=HealthState.HEALTHY,
            headline="Awaiting telemetry",
            detail="No data source is currently reporting to the platform.",
            assets_total=total,
            assets_online=online,
            active_alerts=summary.active,
            critical_alerts=summary.critical,
            live=False,
            generated_at=utc_now(),
        )

    def plural(count: int, noun: str) -> str:
        return f"{count} {noun}{'' if count == 1 else 's'}"

    if critical or summary.critical:
        state = HealthState.CRITICAL
        headline = "Immediate attention required"

        # Name only what is actually driving the verdict. An asset can recover
        # while its alert stays open awaiting acknowledgement, so "0 assets in
        # critical condition and 4 critical alerts" is a real and confusing
        # combination unless the sentence adapts.
        if critical and summary.critical:
            detail = (
                f"{plural(critical, 'asset')} in critical condition, with "
                f"{plural(summary.critical, 'critical alert')} outstanding."
            )
        elif critical:
            detail = f"{plural(critical, 'asset')} in critical condition."
        else:
            detail = (
                f"{plural(summary.critical, 'critical alert')} outstanding. "
                "Affected assets have since recovered but the alerts remain open."
            )
    elif warning or summary.warning:
        state = HealthState.WARNING
        headline = "Operating with degradation"
        if warning:
            detail = (
                f"{plural(warning, 'asset')} showing early warning signs. "
                "No critical faults detected."
            )
        else:
            detail = (
                f"{plural(summary.warning, 'warning alert')} awaiting review. "
                "All assets are currently within normal parameters."
            )
    else:
        state = HealthState.HEALTHY
        headline = "All systems nominal"
        detail = (
            f"{online} of {total} assets online and operating within expected parameters."
        )

    if offline:
        detail += f" {offline} asset{'s are' if offline != 1 else ' is'} unreachable."

    return SystemStatus(
        state=state,
        headline=headline,
        detail=detail,
        assets_total=total,
        assets_online=online,
        active_alerts=summary.active,
        critical_alerts=summary.critical,
        live=True,
        generated_at=utc_now(),
    )


# --- KPIs ----------------------------------------------------------------------


def build_kpis(
    models: list[AssetBusinessModel],
    *,
    energy: EnergySummary,
    average_oee: float | None = None,
    cost_saving: float = 0.0,
) -> list[KpiValue]:
    """The nine executive KPIs.

    Every card carries the route it navigates to. Making each an entry point is
    a product requirement, and keeping the destination in the payload means the
    mapping lives in one place instead of being hardcoded across views.
    """
    total = len(models)
    healthy = sum(1 for m in models if m.health_state is HealthState.HEALTHY)
    warning = sum(1 for m in models if m.health_state is HealthState.WARNING)
    critical = sum(1 for m in models if m.health_state is HealthState.CRITICAL)
    average_health = (
        round(sum(m.health_score for m in models) / total, 1) if total else None
    )
    summary = alert_cache.summary

    return [
        KpiValue(
            key="total_assets",
            label="Total Assets",
            value=float(total),
            tone="primary",
            target="/assets",
            caption="Across all sites",
        ),
        KpiValue(
            key="healthy_assets",
            label="Healthy",
            value=float(healthy),
            tone="healthy",
            target="/assets?health=healthy",
            caption="Operating nominally",
        ),
        KpiValue(
            key="warning_assets",
            label="Warning",
            value=float(warning),
            tone="warning",
            target="/assets?health=warning",
            caption="Early degradation",
        ),
        KpiValue(
            key="critical_assets",
            label="Critical",
            value=float(critical),
            tone="critical",
            target="/assets?health=critical",
            caption="Needs intervention",
        ),
        KpiValue(
            key="average_health",
            label="Average Health",
            value=average_health,
            unit="%",
            precision=1,
            tone="primary",
            target="/apm",
            caption="Fleet condition index",
        ),
        KpiValue(
            key="average_oee",
            label="Average OEE",
            value=average_oee,
            unit="%",
            precision=1,
            tone="primary",
            target="/oee",
            caption="Operational efficiency",
        ),
        KpiValue(
            key="today_energy",
            label="Today's Energy",
            value=round(energy.today_kwh, 2),
            unit="kWh",
            precision=2,
            tone="primary",
            target="/energy",
            caption=f"{int(energy.coverage * 100)}% of fleet metered",
        ),
        KpiValue(
            key="today_saving",
            label="Today's Cost Saving",
            value=round(cost_saving, 2),
            unit=energy.currency,
            precision=2,
            tone="healthy",
            target="/predictive",
            caption="From prescriptive actions",
        ),
        KpiValue(
            key="active_alerts",
            label="Active Alerts",
            value=float(summary.active),
            tone="critical" if summary.critical else "warning" if summary.active else "neutral",
            target="/alerts",
            caption=f"{summary.critical} critical",
        ),
    ]


# --- Live tick -----------------------------------------------------------------


def build_live_tick() -> LiveTick:
    """The per-second delta pushed over the WebSocket.

    Memory only — no database access. Called once per Digital Twin tick
    regardless of how many clients are connected, then fanned out, so cost does
    not scale with audience size.
    """
    models = build_all_business_models(alert_cache.per_asset)
    energy = build_energy_summary(models)
    total = len(models)

    return LiveTick(
        generated_at=utc_now(),
        system_status=build_system_status(models),
        kpis=build_kpis(models, energy=energy),
        asset_types=summarise_asset_types(models),
        energy=energy,
        live_power_w=energy.live_power_w,
        fleet_health=(
            round(sum(m.health_score for m in models) / total, 1) if total else 0.0
        ),
        samples_ingested=live_state.samples_ingested,
    )


# --- Charts --------------------------------------------------------------------


def _series(key: str, label: str, unit: str, values: list[tuple[datetime, float | None]]) -> ChartSeries:
    return ChartSeries(
        key=key,
        label=label,
        unit=unit,
        points=[SeriesPoint(t=moment, v=value) for moment, value in values],
    )


def build_chart_bundle() -> ChartBundle:
    """Every Cockpit chart in one payload.

    Delivered together so the charts resolve as one coordinated wave rather
    than a dozen independent loading states arriving at random.
    """
    samples = live_state.aggregates()
    models = build_all_business_models(alert_cache.per_asset)

    health_counts = {state: 0 for state in HealthState}
    for model in models:
        health_counts[model.health_state] += 1

    type_counts: dict[str, int] = {}
    for model in models:
        type_counts[model.asset_type.value] = type_counts.get(model.asset_type.value, 0) + 1

    tone_by_health = {
        HealthState.HEALTHY: "healthy",
        HealthState.WARNING: "warning",
        HealthState.CRITICAL: "critical",
    }

    return ChartBundle(
        generated_at=utc_now(),
        window_minutes=30,
        energy=_series(
            "energy", "Energy", "kWh", [(s.t, s.energy_kwh) for s in samples]
        ),
        power=_series("power", "Total Power", "W", [(s.t, s.power_w) for s in samples]),
        voltage=_series(
            "voltage", "Average Voltage", "V", [(s.t, s.voltage_v) for s in samples]
        ),
        current=_series(
            "current", "Average Current", "A", [(s.t, s.current_a) for s in samples]
        ),
        temperature=_series(
            "temperature", "Average Temperature", "°C",
            [(s.t, s.temperature_c) for s in samples],
        ),
        power_factor=_series(
            "power_factor", "Average Power Factor", "",
            [(s.t, s.power_factor) for s in samples],
        ),
        health=_series(
            "health", "Fleet Health", "%", [(s.t, s.health_score) for s in samples]
        ),
        health_distribution=[
            DistributionSlice(
                key=state.value,
                label=state.value.capitalize(),
                value=float(count),
                tone=tone_by_health[state],
            )
            for state, count in health_counts.items()
        ],
        type_distribution=[
            DistributionSlice(
                key=asset_type.value,
                label=get_profile(asset_type).label,
                value=float(type_counts.get(asset_type.value, 0)),
                tone="primary",
            )
            for asset_type in PROFILE_ORDER
        ],
    )


# --- Full overview --------------------------------------------------------------


async def build_cockpit_overview(
    session: AsyncSession, intelligence: IntelligenceSummary
) -> CockpitOverview:
    """Assemble the complete Mission Control payload.

    Takes the intelligence summary as an argument rather than computing it, so
    the caller controls whether that work happens — the WebSocket path must
    never pay for it.
    """
    del session  # reserved: scope filtering arrives with authentication

    models = build_all_business_models(alert_cache.per_asset)
    energy = build_energy_summary(models)

    cost_saving = intelligence.prescriptive.total_cost_saving
    energy.today_saving = round(cost_saving, 2)

    average_oee = (
        intelligence.oee.enterprise.oee * 100.0 if intelligence.oee.enterprise else None
    )

    return CockpitOverview(
        organization=live_state.organization_name,
        generated_at=utc_now(),
        system_status=build_system_status(models),
        kpis=build_kpis(
            models, energy=energy, average_oee=average_oee, cost_saving=cost_saving
        ),
        asset_types=summarise_asset_types(models),
        intelligence=intelligence,
        energy=energy,
        alerts=alert_cache.summary,
        activity=activity_log.recent(12),
    )


def reset_dashboard_state() -> None:
    """Clear derived dashboard state. Used by the twin reset endpoint."""
    activity_log.clear()
    energy_ledger.reset()
