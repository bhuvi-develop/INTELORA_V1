"""Executive comparison and enterprise roll-ups.

The Business Intelligence Layer's top surface: it answers "which category of
equipment is serving the business best" and "what is the enterprise position",
questions no single intelligence layer can answer because both span all six.

**Categories are compared on business KPIs only.** Raw telemetry is never
compared across categories and the module offers no way to do so. An air
conditioner draws 5.2 kW and a mobile charger 33 W; ranking them on power,
voltage or current measures nothing except nameplate rating, and would produce
a chart that looks authoritative while saying nothing. Health, availability,
reliability, maintainability, lifecycle, utilisation, risk and OEE are already
dimensionless, and the cost figures are reduced to a per-asset basis before
comparison so a category is not penalised for being numerous. Those are the
only terms on which categories can honestly be judged against each other — the
two-model rule applied one level up: telemetry diverges, the business model
does not.

Every figure here is read from what the layers below already computed. Nothing
is recomputed and nothing is invented; if a measure is absent from the result
tables it is absent here too.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.digital_twin.profiles import get_profile
from app.models import (
    ApmResult,
    Asset,
    AssetGroup,
    OeeAssetResult,
    PreventiveResult,
)
from app.schemas.enums import AssetType, BusinessImpact, RiskLevel
from app.schemas.intelligence import (
    ApmRead,
    CategoryComparison,
    ComparisonMetric,
    ComparisonReport,
    EnterpriseKpis,
    FleetRankingEntry,
)
from app.services.business_model import efficiency_for
from app.services.live_state import live_state
from app.utils.time import utc_now

#: Risk score above which an asset is counted as high risk. The score is a
#: probability-weighted blend already normalised to 0–1 by the APM layer, so
#: the upper half of the scale is the natural boundary rather than a tuned one.
HIGH_RISK_THRESHOLD = 0.5

#: How many assets the executive ranking carries. The Cockpit shows a short
#: league table, and shipping the whole fleet on every WebSocket broadcast to
#: render ten rows would multiply the live payload for nothing.
EXECUTIVE_RANKING_SIZE = 10


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """How one comparable KPI is read and normalised.

    ``scale`` divides the raw value onto 0–1 for measures with a known ceiling,
    such as a 0–100 index. When it is ``None`` the metric is normalised against
    the strongest peer in the same report instead — the right choice for costs,
    which have no natural maximum and are only meaningful relative to the other
    categories being compared.
    """

    key: str
    label: str
    unit: str | None = None
    scale: float | None = 1.0
    lower_is_better: bool = False
    #: Divide the category total by its asset count before comparing. Set for
    #: money, where a category is otherwise punished purely for being large.
    per_asset: bool = False


#: The comparison set, in display order. Reliability engineering first, then
#: efficiency, then money — the same ordering the APM screen uses to separate
#: what the equipment is doing from what it costs.
METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec("health_index", "Health Index", "%", scale=100.0),
    MetricSpec("availability", "Availability", "%"),
    MetricSpec("reliability", "Reliability", "%"),
    MetricSpec("maintainability", "Maintainability", "%"),
    MetricSpec("lifecycle_score", "Lifecycle", "%", scale=100.0),
    MetricSpec("utilization", "Asset Utilisation", "%"),
    MetricSpec("oee", "OEE", "%"),
    MetricSpec("performance", "Performance", "%"),
    MetricSpec("risk_score", "Risk", None, lower_is_better=True),
    MetricSpec(
        "business_impact", "Business Impact", None, lower_is_better=True
    ),
    MetricSpec(
        "maintenance_cost",
        "Maintenance Cost",
        "per asset",
        scale=None,
        lower_is_better=True,
        per_asset=True,
    ),
    MetricSpec(
        "energy_cost",
        "Energy Cost",
        "per asset",
        scale=None,
        lower_is_better=True,
        per_asset=True,
    ),
    MetricSpec(
        "cost_exposure",
        "Cost Exposure",
        "per asset",
        scale=None,
        lower_is_better=True,
        per_asset=True,
    ),
)

#: Business impact expressed on the same 0–1 scale as the other measures, so it
#: can take part in the composite. Higher means worse, and the spec above marks
#: it ``lower_is_better`` accordingly.
_IMPACT_WEIGHT: dict[BusinessImpact, float] = {
    BusinessImpact.CRITICAL: 1.0,
    BusinessImpact.HIGH: 0.75,
    BusinessImpact.MODERATE: 0.5,
    BusinessImpact.LOW: 0.25,
    BusinessImpact.NEGLIGIBLE: 0.0,
}


async def _latest_apm(session: AsyncSession) -> list[tuple[ApmResult, Asset]]:
    """Every asset's newest APM result, joined to identity."""
    latest = await session.scalar(select(func.max(ApmResult.computed_at)))
    if latest is None:
        return []

    return list(
        (
            await session.execute(
                select(ApmResult, Asset)
                .join(Asset, ApmResult.asset_id == Asset.id)
                .where(ApmResult.computed_at == latest)
            )
        ).all()
    )


async def _latest_asset_oee(session: AsyncSession) -> dict[uuid.UUID, OeeAssetResult]:
    """Every asset's newest OEE, keyed by asset."""
    latest = await session.scalar(select(func.max(OeeAssetResult.computed_at)))
    if latest is None:
        return {}

    return {
        row.asset_id: row
        for row in (
            await session.scalars(
                select(OeeAssetResult).where(OeeAssetResult.computed_at == latest)
            )
        ).all()
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


async def build_comparison(session: AsyncSession) -> ComparisonReport | None:
    """Compare every asset category on normalised business KPIs.

    Returns ``None`` before the first intelligence pass. An all-zero report
    would be indistinguishable from a fleet that is genuinely failing on every
    measure, which is a far worse answer than "not computed yet".
    """
    rows = await _latest_apm(session)
    if not rows:
        return None

    asset_oee = await _latest_asset_oee(session)

    # Bucket the raw measures per category first; normalisation needs to see
    # every category before it can scale the cost metrics against each other.
    raw: dict[AssetType, dict[str, float]] = {}
    counts: dict[AssetType, int] = {}

    for result, asset in rows:
        category = asset.asset_type
        bucket = raw.setdefault(category, {})
        counts[category] = counts.get(category, 0) + 1

        oee = asset_oee.get(result.asset_id)

        contributions = {
            "health_index": result.health_index,
            "availability": result.availability,
            "reliability": result.reliability,
            "maintainability": result.maintainability,
            "lifecycle_score": result.lifecycle_score,
            "utilization": result.utilization,
            "risk_score": result.risk_score,
            "business_impact": _IMPACT_WEIGHT.get(result.business_impact, 0.25),
            # Money accumulates; the per-asset reduction happens below.
            "maintenance_cost": result.maintenance_cost,
            "energy_cost": result.energy_cost,
            "cost_exposure": result.cost_exposure,
            # An asset with no OEE row yet contributes nothing rather than a
            # zero, which would drag its category's mean down for a reason that
            # has nothing to do with the equipment.
            "oee": oee.oee if oee else None,
            "performance": oee.performance if oee else None,
        }

        for key, value in contributions.items():
            if value is None:
                continue
            bucket[key] = bucket.get(key, 0.0) + float(value)
            bucket[f"{key}__n"] = bucket.get(f"{key}__n", 0.0) + 1.0

    # Reduce each category to one value per metric.
    reduced: dict[AssetType, dict[str, float]] = {}
    for category, bucket in raw.items():
        values: dict[str, float] = {}
        for spec in METRIC_SPECS:
            total = bucket.get(spec.key)
            samples = bucket.get(f"{spec.key}__n", 0.0)
            if total is None or samples <= 0:
                continue
            values[spec.key] = (
                total / counts[category] if spec.per_asset else total / samples
            )
        reduced[category] = values

    # Peer maxima, for the metrics with no natural ceiling.
    peak: dict[str, float] = {}
    for spec in METRIC_SPECS:
        if spec.scale is None:
            peak[spec.key] = max(
                (values.get(spec.key, 0.0) for values in reduced.values()), default=0.0
            )

    categories: list[CategoryComparison] = []

    for category, values in reduced.items():
        metrics: list[ComparisonMetric] = []

        for spec in METRIC_SPECS:
            if spec.key not in values:
                continue

            value = values[spec.key]

            if spec.scale is None:
                # Relative to the strongest peer. With a single category, or
                # when every category reports zero, there is nothing to compare
                # against and the metric scores neutral rather than perfect.
                ceiling = peak.get(spec.key, 0.0)
                normalised = (value / ceiling) if ceiling > 0 else 0.0
            else:
                normalised = value / spec.scale

            normalised = max(0.0, min(1.0, normalised))
            if spec.lower_is_better:
                normalised = 1.0 - normalised

            metrics.append(
                ComparisonMetric(
                    key=spec.key,
                    label=spec.label,
                    raw=round(value, 4),
                    normalised=round(normalised, 4),
                    unit=spec.unit,
                    lower_is_better=spec.lower_is_better,
                )
            )

        composite = _mean([metric.normalised for metric in metrics])

        categories.append(
            CategoryComparison(
                asset_type=category,
                label=get_profile(category).label,
                asset_count=counts[category],
                composite_score=round(composite, 4),
                metrics=metrics,
            )
        )

    categories.sort(key=lambda item: item.composite_score, reverse=True)
    for position, entry in enumerate(categories, start=1):
        entry.rank = position

    return ComparisonReport(
        computed_at=utc_now(),
        categories=categories,
        metric_keys=[spec.key for spec in METRIC_SPECS],
        best_category=categories[0].asset_type if categories else None,
        worst_category=categories[-1].asset_type if categories else None,
    )


async def build_fleet_ranking(session: AsyncSession) -> list[FleetRankingEntry]:
    """Rank asset groups against each other.

    A fleet is what an operations manager actually owns, so ranking at that
    level is what turns the estate-wide numbers into somebody's to-do list.
    The composite deliberately mirrors the category comparison — condition,
    availability and efficiency up, exposure down — so a group and a category
    scored on the same day are scored the same way.
    """
    rows = await _latest_apm(session)
    if not rows:
        return []

    asset_oee = await _latest_asset_oee(session)

    groups = {
        group.id: group.name
        for group in (await session.scalars(select(AssetGroup))).all()
    }

    buckets: dict[uuid.UUID | None, dict[str, list[float] | float]] = {}

    for result, asset in rows:
        key = asset.asset_group_id
        bucket = buckets.setdefault(
            key, {"health": [], "availability": [], "oee": [], "exposure": 0.0}
        )
        bucket["health"].append(result.health_index)  # type: ignore[union-attr]
        bucket["availability"].append(result.availability)  # type: ignore[union-attr]
        bucket["exposure"] = float(bucket["exposure"]) + result.cost_exposure

        oee = asset_oee.get(result.asset_id)
        if oee is not None:
            bucket["oee"].append(oee.oee)  # type: ignore[union-attr]

    entries: list[FleetRankingEntry] = []
    exposures = [float(bucket["exposure"]) for bucket in buckets.values()]
    worst_exposure = max(exposures) if exposures else 0.0

    for key, bucket in buckets.items():
        health = _mean(bucket["health"])  # type: ignore[arg-type]
        availability = _mean(bucket["availability"])  # type: ignore[arg-type]
        oee = _mean(bucket["oee"])  # type: ignore[arg-type]
        exposure = float(bucket["exposure"])

        # Exposure is relative to the worst group in the same ranking, for the
        # same reason costs are relative in the category comparison: there is
        # no absolute ceiling on how much money a fleet can be at risk of.
        exposure_score = 1.0 - (exposure / worst_exposure) if worst_exposure > 0 else 1.0

        composite = _mean(
            [health / 100.0, availability, oee, max(0.0, min(1.0, exposure_score))]
        )

        entries.append(
            FleetRankingEntry(
                asset_group_id=key,
                label=groups.get(key, "Ungrouped") if key else "Ungrouped",
                asset_count=len(bucket["health"]),  # type: ignore[arg-type]
                average_health_index=round(health, 2),
                average_availability=round(availability, 4),
                average_oee=round(oee, 4),
                total_cost_exposure=round(exposure, 2),
                composite_score=round(composite, 4),
            )
        )

    entries.sort(key=lambda item: item.composite_score, reverse=True)
    for position, entry in enumerate(entries, start=1):
        entry.rank = position

    return entries


async def build_enterprise_kpis(session: AsyncSession) -> EnterpriseKpis | None:
    """The executive position, assembled across every layer.

    One payload behind the Cockpit's ten headline questions, so the browser
    composes nothing. Returns ``None`` before the first pass for the same
    reason the comparison does.
    """
    rows = await _latest_apm(session)
    if not rows:
        return None

    asset_oee = await _latest_asset_oee(session)
    results = [result for result, _ in rows]

    # Maintenance due comes from Layer 3's newest plan set, read rather than
    # recomputed — the preventive layer owns that judgement.
    due = 0
    latest_plan = await session.scalar(select(func.max(PreventiveResult.computed_at)))
    if latest_plan is not None:
        due = int(
            await session.scalar(
                select(func.count())
                .select_from(PreventiveResult)
                .where(
                    PreventiveResult.computed_at == latest_plan,
                    PreventiveResult.maintenance_due.is_(True),
                )
            )
            or 0
        )

    oee_values = [row.oee for row in asset_oee.values()]
    availability_values = [row.availability for row in asset_oee.values()]
    performance_values = [row.performance for row in asset_oee.values()]
    quality_values = [row.quality for row in asset_oee.values()]

    # Energy efficiency reuses the platform's existing per-asset electrical
    # efficiency — power factor against the category's achievable range, plus
    # thermal headroom — rather than defining a second, competing notion of the
    # same word. Read from live state because it is an instantaneous measure.
    efficiencies = [
        efficiency_for(live_state.latest(identity.id), identity)
        for identity in live_state.identities()
    ]

    return EnterpriseKpis(
        generated_at=utc_now(),
        enterprise_health=round(_mean([r.health_index for r in results]), 2),
        enterprise_oee=round(_mean(oee_values), 4),
        enterprise_availability=round(_mean(availability_values), 4),
        enterprise_performance=round(_mean(performance_values), 4),
        enterprise_quality=round(_mean(quality_values), 4),
        total_assets=len(results),
        critical_assets=sum(
            1 for r in results if r.criticality is RiskLevel.SEVERE
        ),
        high_risk_assets=sum(
            1 for r in results if r.risk_score >= HIGH_RISK_THRESHOLD
        ),
        maintenance_due=due,
        energy_efficiency=round(_mean(efficiencies), 2),
        total_energy_cost=round(sum(r.energy_cost for r in results), 4),
        total_cost_exposure=round(sum(r.cost_exposure for r in results), 2),
        total_business_value=round(sum(r.business_value for r in results), 2),
        critical_business_impact=sum(
            1 for r in results if r.business_impact is BusinessImpact.CRITICAL
        ),
        fleet_ranking=await build_fleet_ranking(session),
        asset_ranking=[
            ApmRead(
                **(
                    ApmRead.model_validate(result).model_dump()
                    | {
                        "asset_code": asset.asset_code,
                        "asset_name": asset.name,
                        "asset_type": asset.asset_type,
                    }
                )
            )
            for result, asset in sorted(rows, key=lambda pair: pair[0].rank or 10_000)[
                :EXECUTIVE_RANKING_SIZE
            ]
        ],
    )
