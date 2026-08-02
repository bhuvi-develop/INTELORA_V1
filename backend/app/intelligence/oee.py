"""Layer 6 — Overall Equipment Efficiency.

The classic formulation, applied to electrical assets:

``OEE = Availability × Performance × Quality``

* **Availability** — share of the window the asset was reachable and usable.
* **Performance** — output delivered against what the nameplate says it should
  deliver while running. An asset drawing far below or far above its rated
  envelope is not performing to specification either way.
* **Quality** — share of readings the platform can trust, blended with the
  asset's health. Note this is *OEE quality*, entirely unrelated to the
  ``quality`` field on a telemetry row despite sharing the word.

Results are produced at every aggregation scope the SSOT requires: enterprise,
building, department, fleet and asset type. Department is read from the
location, which is where that attribute lives in this schema.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.digital_twin.profiles import get_profile
from app.intelligence.context import AssetWindow, IntelligenceContext
from app.models import OeeAssetResult, OeeResult
from app.schemas.enums import AssetType, ConnectivityState, ScopeType
from app.services.live_state import live_state

#: Performance is scored against a band around rated draw rather than a point,
#: because real equipment modulates and should not be penalised for it.
PERFORMANCE_FLOOR = 0.30
PERFORMANCE_CEILING = 1.10


@dataclass(slots=True)
class Factors:
    """The three OEE factors for one asset."""

    availability: float
    performance: float
    quality: float

    @property
    def oee(self) -> float:
        return self.availability * self.performance * self.quality


def _availability(window: AssetWindow, connectivity: ConnectivityState) -> float:
    """Share of the window the asset was available to work."""
    if connectivity is ConnectivityState.OFFLINE or window.sample_count == 0:
        return 0.0
    # Running time counts fully; idle-but-ready counts as available capacity.
    return round(min(1.0, window.running_ratio + (1.0 - window.running_ratio) * 0.9), 4)


def _performance(window: AssetWindow) -> float:
    """Output delivered against output commanded, while running.

    The yardstick is the asset's own commanded load, not a static nameplate
    midpoint. That distinction became essential once chargers began following a
    real charge curve: a device tapering towards full is drawing a fraction of
    its rated power *and doing exactly what it should*. Judged against a fixed
    expectation it would look like a chronic underperformer, and the OEE of
    every charger on the platform would sag every time it finished a charge.

    Falls back to the profile's load band for categories that do not report
    commanded load.
    """
    if window.running_ratio <= 0.01 or window.mean_running_power_w <= 0.0:
        # Never ran during the window: nothing to judge, so neither credit nor
        # penalty. Availability already reflects the idleness.
        return 1.0

    profile = get_profile(window.identity.asset_type)
    rated = profile.rated_power_w
    if rated <= 0:
        return 1.0

    if window.mean_load_percent > 0.5:
        expected = rated * (window.mean_load_percent / 100.0)
    else:
        low, high = profile.duty.active_load
        expected = rated * ((low + high) / 2.0)

    if expected <= 0:
        return 1.0

    ratio = window.mean_running_power_w / expected

    if ratio > PERFORMANCE_CEILING:
        # Over-drawing is a defect, not an achievement: the excess is loss.
        return round(max(0.0, 1.0 - (ratio - PERFORMANCE_CEILING)), 4)

    return round(max(PERFORMANCE_FLOOR, min(1.0, ratio)), 4)


def _quality(window: AssetWindow) -> float:
    """Trustworthy output, blending data quality with asset condition."""
    health = (window.health_last if window.health_last is not None else 100.0) / 100.0
    return round(max(0.0, min(1.0, window.good_quality_ratio * 0.4 + health * 0.6)), 4)


def _aggregate(groups: list[Factors]) -> Factors:
    """Mean of each factor across a group.

    Averaging the factors and multiplying, rather than averaging the products,
    keeps the reported OEE consistent with the three numbers shown beside it.
    """
    if not groups:
        return Factors(0.0, 0.0, 0.0)
    count = len(groups)
    return Factors(
        availability=round(sum(f.availability for f in groups) / count, 4),
        performance=round(sum(f.performance for f in groups) / count, 4),
        quality=round(sum(f.quality for f in groups) / count, 4),
    )


def _result(
    context: IntelligenceContext,
    *,
    scope_type: ScopeType,
    scope_id: uuid.UUID | None,
    label: str,
    factors: Factors,
    count: int,
    asset_type: AssetType | None = None,
) -> OeeResult:
    return OeeResult(
        scope_type=scope_type,
        scope_id=scope_id,
        scope_label=label,
        asset_type=asset_type,
        computed_at=context.computed_at,
        availability=factors.availability,
        performance=factors.performance,
        quality=factors.quality,
        oee=round(factors.oee, 4),
        asset_count=count,
    )


async def run(session: AsyncSession, context: IntelligenceContext) -> int:
    """Compute OEE at every aggregation scope."""
    per_asset: dict[uuid.UUID, Factors] = {}

    by_building: dict[str, list[Factors]] = defaultdict(list)
    by_department: dict[str, list[Factors]] = defaultdict(list)
    by_fleet: dict[tuple[uuid.UUID | None, str], list[Factors]] = defaultdict(list)
    by_type: dict[AssetType, list[Factors]] = defaultdict(list)
    enterprise: list[Factors] = []

    for window in context.assets():
        if window.sample_count == 0:
            continue

        connectivity = live_state.connectivity_for(
            window.identity.id, now=context.computed_at
        )
        factors = Factors(
            availability=_availability(window, connectivity),
            performance=_performance(window),
            quality=_quality(window),
        )
        per_asset[window.identity.id] = factors
        enterprise.append(factors)

        identity = window.identity
        if identity.building:
            by_building[identity.building].append(factors)
        if identity.department:
            by_department[identity.department].append(factors)
        by_fleet[(identity.asset_group_id, identity.asset_group_name or "Ungrouped")].append(
            factors
        )
        by_type[identity.asset_type].append(factors)

    if not enterprise:
        return 0

    written = 0

    # --- Per-asset OEE ---------------------------------------------------------
    # The individual asset is the level every rollup above is built from, and
    # the only level at which "why is this number low" has a concrete answer.
    # Persisting it is what makes the OEE drill-down answerable at all; without
    # these rows the factors are computed each cycle and immediately lost, and
    # every asset-level question has to be answered from an aggregate that has
    # already averaged the detail away.
    #
    # Ranked here rather than on read so the ordering is stamped alongside the
    # factors that produced it — a later re-rank against a different cycle's
    # rows would disagree with the numbers displayed beside it.
    ordered = sorted(per_asset.items(), key=lambda item: item[1].oee, reverse=True)
    type_position: dict[AssetType, int] = {}

    for position, (asset_id, factors) in enumerate(ordered, start=1):
        window = context.windows[asset_id]
        category = window.identity.asset_type
        type_position[category] = type_position.get(category, 0) + 1

        session.add(
            OeeAssetResult(
                asset_id=asset_id,
                computed_at=context.computed_at,
                availability=factors.availability,
                performance=factors.performance,
                quality=factors.quality,
                oee=round(factors.oee, 4),
                rank=position,
                type_rank=type_position[category],
            )
        )
        written += 1

    session.add(
        _result(
            context,
            scope_type=ScopeType.ENTERPRISE,
            scope_id=None,
            label="Enterprise",
            factors=_aggregate(enterprise),
            count=len(enterprise),
        )
    )
    written += 1

    for building, factors in by_building.items():
        session.add(
            _result(
                context,
                scope_type=ScopeType.BUILDING,
                scope_id=None,
                label=building,
                factors=_aggregate(factors),
                count=len(factors),
            )
        )
        written += 1

    for department, factors in by_department.items():
        session.add(
            _result(
                context,
                scope_type=ScopeType.DEPARTMENT,
                scope_id=None,
                label=department,
                factors=_aggregate(factors),
                count=len(factors),
            )
        )
        written += 1

    for (group_id, group_name), factors in by_fleet.items():
        session.add(
            _result(
                context,
                scope_type=ScopeType.FLEET,
                scope_id=group_id,
                label=group_name,
                factors=_aggregate(factors),
                count=len(factors),
            )
        )
        written += 1

    for asset_type, factors in by_type.items():
        session.add(
            _result(
                context,
                scope_type=ScopeType.ASSET,
                scope_id=None,
                label=get_profile(asset_type).label,
                factors=_aggregate(factors),
                count=len(factors),
                asset_type=asset_type,
            )
        )
        written += 1

    return written
