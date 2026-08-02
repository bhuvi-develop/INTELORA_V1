"""Layer 1 — Anomaly Detection.

Two detectors run over every reading, because each catches what the other
misses:

* **Envelope** — is the value outside the physically acceptable band for this
  asset type? Catches absolute faults immediately, including on a device that
  has been broken since the platform first saw it.
* **Statistical** — is the value far from this asset's own recent behaviour?
  Catches drift that stays technically in range, and adapts to a device whose
  normal is not the nameplate.

An anomaly becomes an alert only if it is severe enough and no open alert
already exists for the same asset and fault. Without that check, a device stuck
in a fault would raise a new alert every cycle and bury the operator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.digital_twin.profiles import get_profile
from app.intelligence.context import AssetWindow, IntelligenceContext
from app.intelligence.diagnosis import diagnose
from app.models import Alert, AnomalyResult
from app.schemas.enums import (
    AlertSeverity,
    AlertStatus,
    AnomalyStatus,
    ChargingState,
    FaultType,
    HealthState,
)
from app.services.dashboard_service import activity_log

#: Z-score beyond which a reading is considered statistically anomalous.
SIGMA_WARNING = 3.0
SIGMA_CRITICAL = 4.5

#: Minimum samples before the statistical detector is trusted.
MIN_SAMPLES = 20

#: Only these severities open an alert; informational anomalies are recorded
#: and surfaced on the Anomaly page but do not page anyone.
ALERTING_SEVERITIES = (AlertSeverity.CRITICAL, AlertSeverity.WARNING)

#: Charging phases in which a low draw is correct behaviour rather than a
#: fault. Without this distinction every charger raises a power-loss alert the
#: moment it finishes its job.
_LOW_DRAW_PHASES = frozenset(
    {
        ChargingState.IDLE,
        ChargingState.TOPPING_OFF,
        ChargingState.TRICKLE,
        ChargingState.COMPLETE,
    }
)

#: Commanded load below which delivered power is not judged at all.
COMMANDED_LOAD_FLOOR = 35.0

#: Silence after which an asset is declared offline. Several multiples of the
#: telemetry interval, so ordinary scheduling jitter never flaps the state.
OFFLINE_AFTER_SECONDS = 45.0

#: Share of expected readings below which delivery counts as degraded.
COMMUNICATION_DELIVERY_FLOOR = 0.72

#: Channels the statistical detector may examine.
#:
#: Deliberately excludes power and current. Those track load by definition, and
#: a duty-cycled asset's load swings across its whole range every few minutes —
#: so a z-score against their rolling mean measures the duty cycle, not the
#: asset's condition. Load-dependent channels are checked against *commanded*
#: output instead; only channels with a genuinely stable expected value belong
#: here.
STATISTICAL_CHANNELS = frozenset(
    {"voltage_v", "temperature_c", "power_factor", "frequency_hz"}
)


@dataclass(slots=True)
class Detection:
    """One detected anomaly, before persistence."""

    channel: str
    fault_type: FaultType
    severity: AlertSeverity
    score: float
    confidence: float
    observed: float
    expected_min: float | None
    expected_max: float | None
    sigma: float | None
    description: str


def _envelope_checks(window: AssetWindow) -> list[Detection]:
    """Absolute bounds derived from the asset's own profile."""
    reading = window.latest
    if reading is None:
        return []

    profile = get_profile(window.identity.asset_type)
    detections: list[Detection] = []

    # --- Voltage ------------------------------------------------------------
    if reading.voltage_v is not None:
        nominal = profile.nominal_voltage_v
        tolerance = profile.voltage_tolerance
        low = nominal * (1.0 - tolerance * 2.2)
        high = nominal * (1.0 + tolerance * 2.2)
        if reading.voltage_v < low:
            deficit = (low - reading.voltage_v) / max(low, 1.0)
            detections.append(
                Detection(
                    channel="voltage_v",
                    fault_type=FaultType.VOLTAGE_DROP,
                    severity=AlertSeverity.CRITICAL if deficit > 0.08 else AlertSeverity.WARNING,
                    score=min(1.0, 0.55 + deficit * 3.0),
                    confidence=0.93,
                    observed=reading.voltage_v,
                    expected_min=round(low, 1),
                    expected_max=round(high, 1),
                    sigma=None,
                    description=(
                        f"Supply voltage {reading.voltage_v:.1f} V is below the "
                        f"acceptable minimum of {low:.1f} V."
                    ),
                )
            )
        elif reading.voltage_v > high:
            detections.append(
                Detection(
                    channel="voltage_v",
                    fault_type=FaultType.VOLTAGE_SPIKE,
                    severity=AlertSeverity.WARNING,
                    score=0.62,
                    confidence=0.90,
                    observed=reading.voltage_v,
                    expected_min=round(low, 1),
                    expected_max=round(high, 1),
                    sigma=None,
                    description=(
                        f"Supply voltage {reading.voltage_v:.1f} V exceeds the "
                        f"acceptable maximum of {high:.1f} V."
                    ),
                )
            )

    # --- Temperature ---------------------------------------------------------
    if reading.temperature_c is not None:
        thermal = profile.thermal
        if reading.temperature_c >= thermal.critical_c:
            detections.append(
                Detection(
                    channel="temperature_c",
                    fault_type=FaultType.OVER_TEMPERATURE,
                    severity=AlertSeverity.CRITICAL,
                    score=0.95,
                    confidence=0.97,
                    observed=reading.temperature_c,
                    expected_min=None,
                    expected_max=thermal.warning_c,
                    sigma=None,
                    description=(
                        f"Temperature {reading.temperature_c:.1f} °C has passed the "
                        f"critical limit of {thermal.critical_c:.0f} °C."
                    ),
                )
            )
        elif reading.temperature_c >= thermal.warning_c:
            detections.append(
                Detection(
                    channel="temperature_c",
                    fault_type=FaultType.OVER_TEMPERATURE,
                    severity=AlertSeverity.WARNING,
                    score=0.68,
                    confidence=0.92,
                    observed=reading.temperature_c,
                    expected_min=None,
                    expected_max=thermal.warning_c,
                    sigma=None,
                    description=(
                        f"Temperature {reading.temperature_c:.1f} °C is above the "
                        f"warning threshold of {thermal.warning_c:.0f} °C."
                    ),
                )
            )

    # --- Current -------------------------------------------------------------
    if reading.current_a is not None and profile.nominal_voltage_v > 0:
        rated_current = profile.rated_power_w / profile.nominal_voltage_v
        if rated_current > 0 and reading.current_a > rated_current * 1.30:
            detections.append(
                Detection(
                    channel="current_a",
                    fault_type=FaultType.OVER_CURRENT,
                    severity=AlertSeverity.CRITICAL,
                    score=0.90,
                    confidence=0.94,
                    observed=reading.current_a,
                    expected_min=0.0,
                    expected_max=round(rated_current * 1.30, 3),
                    sigma=None,
                    description=(
                        f"Current draw {reading.current_a:.2f} A exceeds 130% of the "
                        f"rated {rated_current:.2f} A."
                    ),
                )
            )

    # --- Power factor ---------------------------------------------------------
    if reading.power_factor is not None and profile.power_factor_range is not None:
        floor = profile.power_factor_range[0] - 0.12
        if reading.power_factor < floor:
            detections.append(
                Detection(
                    channel="power_factor",
                    fault_type=FaultType.POOR_POWER_FACTOR,
                    severity=AlertSeverity.WARNING,
                    score=0.58,
                    confidence=0.86,
                    observed=reading.power_factor,
                    expected_min=round(floor, 3),
                    expected_max=1.0,
                    sigma=None,
                    description=(
                        f"Power factor {reading.power_factor:.2f} is below the expected "
                        f"floor of {floor:.2f}, indicating wasted apparent power."
                    ),
                )
            )

    # --- Frequency -------------------------------------------------------------
    if reading.frequency_hz is not None and profile.nominal_frequency_hz is not None:
        drift = abs(reading.frequency_hz - profile.nominal_frequency_hz)
        if drift > 0.8:
            detections.append(
                Detection(
                    channel="frequency_hz",
                    fault_type=FaultType.FREQUENCY_VARIATION,
                    severity=AlertSeverity.WARNING,
                    score=min(1.0, 0.5 + drift / 4.0),
                    confidence=0.88,
                    observed=reading.frequency_hz,
                    expected_min=profile.nominal_frequency_hz - 0.8,
                    expected_max=profile.nominal_frequency_hz + 0.8,
                    sigma=None,
                    description=(
                        f"Supply frequency {reading.frequency_hz:.2f} Hz has drifted "
                        f"{drift:.2f} Hz from nominal."
                    ),
                )
            )

    # --- Delivered against commanded ---------------------------------------------
    #
    # Power is judged against what the asset was *asked* to draw, never against
    # its own recent average. A duty-cycled asset swings from near-zero to full
    # by design: an unplugged charger, one tapering towards a full battery, and
    # an air conditioner between compressor cycles all sit far below their
    # rolling mean while behaving perfectly. Comparing to that mean reports
    # every one of them as a power loss.
    if (
        reading.power_w is not None
        and reading.load_percent is not None
        and reading.load_percent >= COMMANDED_LOAD_FLOOR
        and reading.charging_state not in _LOW_DRAW_PHASES
    ):
        expected = profile.rated_power_w * (reading.load_percent / 100.0)
        # The threshold is deliberately looser than the Health Engine's, so
        # condition degrades before anyone is paged.
        floor = expected * 0.6
        if expected > 1.0 and reading.power_w < floor:
            shortfall = (floor - reading.power_w) / floor
            detections.append(
                Detection(
                    channel="power_w",
                    fault_type=FaultType.POWER_LOSS,
                    severity=(
                        AlertSeverity.CRITICAL if shortfall > 0.4 else AlertSeverity.WARNING
                    ),
                    score=min(1.0, 0.55 + shortfall),
                    confidence=0.9,
                    observed=reading.power_w,
                    expected_min=round(floor, 2),
                    expected_max=round(expected, 2),
                    sigma=None,
                    description=(
                        f"Drawing {reading.power_w:.1f} W while commanded to "
                        f"{reading.load_percent:.0f}% load, which should deliver about "
                        f"{expected:.1f} W."
                    ),
                )
            )

    # --- Power spike ---------------------------------------------------------
    if (
        reading.power_w is not None
        and reading.load_percent is not None
        and reading.load_percent >= COMMANDED_LOAD_FLOOR
    ):
        expected = profile.rated_power_w * (reading.load_percent / 100.0)
        if expected > 1.0 and reading.power_w > expected * 1.35:
            excess = (reading.power_w - expected) / expected
            detections.append(
                Detection(
                    channel="power_w",
                    fault_type=FaultType.POWER_SPIKE,
                    severity=(
                        AlertSeverity.CRITICAL if excess > 0.6 else AlertSeverity.WARNING
                    ),
                    score=min(1.0, 0.5 + excess),
                    confidence=0.88,
                    observed=reading.power_w,
                    expected_min=0.0,
                    expected_max=round(expected * 1.35, 2),
                    sigma=None,
                    description=(
                        f"Drawing {reading.power_w:.1f} W against an expected "
                        f"{expected:.1f} W for {reading.load_percent:.0f}% commanded load."
                    ),
                )
            )

    # --- Current collapse -----------------------------------------------------
    # Distinct from a power loss: current can collapse while voltage holds,
    # which points at the connection rather than the supply.
    if (
        reading.current_a is not None
        and reading.load_percent is not None
        and reading.load_percent >= COMMANDED_LOAD_FLOOR
        and reading.charging_state not in _LOW_DRAW_PHASES
        and profile.nominal_voltage_v > 0
    ):
        expected_current = (
            profile.rated_power_w * (reading.load_percent / 100.0)
        ) / profile.nominal_voltage_v
        if expected_current > 0.001 and reading.current_a < expected_current * 0.55:
            detections.append(
                Detection(
                    channel="current_a",
                    fault_type=FaultType.UNDER_CURRENT,
                    severity=AlertSeverity.WARNING,
                    score=0.7,
                    confidence=0.85,
                    observed=reading.current_a,
                    expected_min=round(expected_current * 0.55, 4),
                    expected_max=round(expected_current * 1.3, 4),
                    sigma=None,
                    description=(
                        f"Current {reading.current_a:.3f} A is well below the "
                        f"{expected_current:.3f} A the commanded load requires."
                    ),
                )
            )

    # --- Abnormal energy accumulation ------------------------------------------
    # A cumulative meter must only ever climb, and it should climb at a rate
    # consistent with measured power. Either violation is a metering fault, and
    # both silently corrupt every cost and consumption figure downstream if
    # nobody notices.
    if reading.energy_kwh is not None and window.energy_delta_kwh is not None:
        implied_kwh = (window.mean_running_power_w / 1000.0) * window.window_hours
        if window.energy_delta_kwh < -0.0001:
            detections.append(
                Detection(
                    channel="energy_kwh",
                    fault_type=FaultType.ABNORMAL_ENERGY,
                    severity=AlertSeverity.WARNING,
                    score=0.75,
                    confidence=0.9,
                    observed=reading.energy_kwh,
                    expected_min=None,
                    expected_max=None,
                    sigma=None,
                    description=(
                        "Cumulative energy meter decreased over the window, which a "
                        "lifetime counter cannot legitimately do."
                    ),
                )
            )
        elif implied_kwh > 0.01 and window.energy_delta_kwh > implied_kwh * 2.5:
            detections.append(
                Detection(
                    channel="energy_kwh",
                    fault_type=FaultType.ABNORMAL_ENERGY,
                    severity=AlertSeverity.WARNING,
                    score=0.68,
                    confidence=0.78,
                    observed=round(window.energy_delta_kwh, 4),
                    expected_min=0.0,
                    expected_max=round(implied_kwh * 2.5, 4),
                    sigma=None,
                    description=(
                        f"Energy accumulated {window.energy_delta_kwh:.3f} kWh while "
                        f"measured power implies about {implied_kwh:.3f} kWh."
                    ),
                )
            )

    # --- Physical coherence -----------------------------------------------------
    # Every channel can sit inside its own envelope while the relationship
    # between them is impossible. P = V·I·cosφ is not negotiable, and a reading
    # that violates it is instrumentation to distrust, not physics to believe.
    if (
        reading.voltage_v is not None
        and reading.current_a is not None
        and reading.power_w is not None
        and reading.voltage_v > 1.0
        and reading.current_a > 0.001
    ):
        factor = reading.power_factor if reading.power_factor else 1.0
        implied_power = reading.voltage_v * reading.current_a * factor
        if implied_power > 1.0:
            divergence = abs(implied_power - reading.power_w) / implied_power
            if divergence > 0.35:
                detections.append(
                    Detection(
                        channel="power_w",
                        fault_type=FaultType.UNEXPECTED_BEHAVIOUR,
                        severity=AlertSeverity.WARNING,
                        score=min(1.0, 0.5 + divergence),
                        confidence=0.72,
                        observed=reading.power_w,
                        expected_min=round(implied_power * 0.65, 2),
                        expected_max=round(implied_power * 1.35, 2),
                        sigma=None,
                        description=(
                            f"Reported {reading.power_w:.1f} W but voltage, current and "
                            f"power factor imply {implied_power:.1f} W — the channels "
                            "are not physically consistent."
                        ),
                    )
                )

    return detections


def _connectivity_checks(
    window: AssetWindow, now: datetime
) -> list[Detection]:
    """Detect assets the platform has stopped hearing from.

    This is inferred from silence, never from a packet — a device cannot report
    that it has gone away. Without it a failed asset simply disappears from the
    dashboard while its last known values sit there looking healthy, which is
    the most dangerous possible failure mode for a monitoring platform.

    Two distinct conditions:

    * **Offline** — nothing at all for long enough that the device is gone.
    * **Communication failure** — still reporting, but with gaps. The device is
      alive and the network path is not. These need different people.
    """
    identity = window.identity
    last_seen = window.last_seen_at

    if last_seen is None:
        return []

    silence = (now - last_seen).total_seconds()

    if silence >= OFFLINE_AFTER_SECONDS:
        minutes = silence / 60.0
        return [
            Detection(
                channel="connectivity",
                fault_type=FaultType.DEVICE_OFFLINE,
                severity=AlertSeverity.CRITICAL,
                score=1.0,
                confidence=0.98,
                observed=round(silence, 1),
                expected_min=None,
                expected_max=float(OFFLINE_AFTER_SECONDS),
                sigma=None,
                description=(
                    f"{identity.asset_code} has not reported for "
                    f"{minutes:.1f} minutes."
                ),
            )
        ]

    # Alive but patchy: far fewer samples arrived than the interval implies.
    if window.window_hours > 0.05 and window.sample_count > 0:
        expected_samples = window.window_hours * 3600.0
        delivery = window.sample_count / max(expected_samples, 1.0)
        if delivery < COMMUNICATION_DELIVERY_FLOOR:
            return [
                Detection(
                    channel="connectivity",
                    fault_type=FaultType.COMMUNICATION_FAILURE,
                    severity=AlertSeverity.WARNING,
                    score=min(1.0, 1.0 - delivery),
                    confidence=0.82,
                    observed=round(delivery * 100.0, 1),
                    expected_min=round(COMMUNICATION_DELIVERY_FLOOR * 100.0, 1),
                    expected_max=100.0,
                    sigma=None,
                    description=(
                        f"Only {delivery * 100:.0f}% of expected readings arrived over "
                        f"the last {window.window_hours * 60:.0f} minutes."
                    ),
                )
            ]

    return []


def _statistical_checks(window: AssetWindow) -> list[Detection]:
    """Deviation from the asset's own recent behaviour."""
    reading = window.latest
    if reading is None:
        return []

    detections: list[Detection] = []

    for channel, stats in window.stats.items():
        if channel not in STATISTICAL_CHANNELS:
            continue
        if stats.samples < MIN_SAMPLES:
            continue
        value = getattr(reading, channel, None)
        if value is None:
            continue

        sigma = abs(stats.z_score(value))
        if sigma < SIGMA_WARNING:
            continue

        severity = (
            AlertSeverity.CRITICAL if sigma >= SIGMA_CRITICAL else AlertSeverity.WARNING
        )
        fault = _fault_for_channel(channel)

        detections.append(
            Detection(
                channel=channel,
                fault_type=fault,
                severity=severity,
                score=min(1.0, sigma / (SIGMA_CRITICAL * 1.4)),
                # Confidence grows with sample count: a judgement from 25
                # samples deserves less weight than one from 900.
                confidence=min(0.95, 0.55 + stats.samples / 1200.0),
                observed=float(value),
                expected_min=round(stats.mean - SIGMA_WARNING * stats.stddev, 3),
                expected_max=round(stats.mean + SIGMA_WARNING * stats.stddev, 3),
                sigma=round(sigma, 2),
                description=(
                    f"{_channel_label(channel)} of {float(value):.2f} sits {sigma:.1f}σ "
                    f"from this asset's {stats.mean:.2f} average over the last "
                    f"{stats.samples} samples."
                ),
            )
        )

    return detections


def _fault_for_channel(channel: str) -> FaultType:
    """Map a deviating channel onto the fault it most likely indicates."""
    return {
        "voltage_v": FaultType.VOLTAGE_DROP,
        "current_a": FaultType.OVER_CURRENT,
        "power_w": FaultType.POWER_LOSS,
        "temperature_c": FaultType.OVER_TEMPERATURE,
        "power_factor": FaultType.POOR_POWER_FACTOR,
        "frequency_hz": FaultType.FREQUENCY_VARIATION,
    }.get(channel, FaultType.POWER_LOSS)


def _channel_label(channel: str) -> str:
    return {
        "voltage_v": "Voltage",
        "current_a": "Current",
        "power_w": "Power",
        "temperature_c": "Temperature",
        "power_factor": "Power factor",
        "frequency_hz": "Frequency",
    }.get(channel, channel)


def _deduplicate(detections: list[Detection]) -> list[Detection]:
    """Keep only the most severe detection per fault type.

    Envelope and statistical detectors frequently fire on the same underlying
    problem; reporting it twice would inflate every count on the Anomaly page.
    """
    best: dict[FaultType, Detection] = {}
    rank = {
        AlertSeverity.CRITICAL: 3,
        AlertSeverity.WARNING: 2,
        AlertSeverity.INFORMATION: 1,
    }
    for detection in detections:
        current = best.get(detection.fault_type)
        if current is None or rank[detection.severity] > rank[current.severity]:
            best[detection.fault_type] = detection
        elif (
            rank[detection.severity] == rank[current.severity]
            and detection.score > current.score
        ):
            best[detection.fault_type] = detection
    return list(best.values())


async def _auto_resolve(
    session: AsyncSession,
    window: AssetWindow,
    detected: set[FaultType],
    resolved_at,
) -> int:
    """Close open alerts whose underlying condition has cleared.

    Without this the alert queue only ever grows: a transient voltage dip that
    recovered seconds later would stay open indefinitely, the operator would
    lose any sense of what is actually wrong now, and — because Layer 2 weighs
    open alerts when estimating failure probability — a fleet in perfect health
    would drift towards being flagged at risk.

    Resolution is conservative. An alert closes only when its fault is absent
    *and* the asset is currently healthy, so a fault that momentarily reads
    inside its envelope does not cause the alert to flap open and shut.
    """
    if window.latest is None or window.latest.health_state is not HealthState.HEALTHY:
        return 0

    detected_keys = {fault.value for fault in detected}
    stale = [
        (key, alert_id)
        for key, alert_id in window.open_alert_ids.items()
        if key not in detected_keys
    ]
    if not stale:
        return 0

    await session.execute(
        update(Alert)
        .where(Alert.id.in_([alert_id for _, alert_id in stale]))
        .values(
            status=AlertStatus.RESOLVED,
            resolved_at=resolved_at,
            acknowledged_at=func.coalesce(Alert.acknowledged_at, resolved_at),
        )
    )

    for key, alert_id in stale:
        window.open_fault_keys.discard(key)
        window.open_alert_ids.pop(key, None)

    return len(stale)


async def _clear_anomalies(
    session: AsyncSession,
    window: AssetWindow,
    detected: set[FaultType],
    cleared_at: datetime,
) -> int:
    """Close open anomalies whose condition is no longer present.

    Cleared by ``(asset, fault)`` rather than by the single tracked id. The
    tracking dictionary holds one id per fault, so clearing by id would leave
    any duplicate rows for the same condition open indefinitely — which is
    exactly what happens to rows written before this lifecycle existed, and to
    anything a crash mid-cycle leaves behind. Matching on the condition itself
    is self-healing.
    """
    stale_keys = [
        key
        for key in window.open_anomaly_ids
        if key not in {fault.value for fault in detected}
    ]
    if not stale_keys:
        return 0

    result = await session.execute(
        update(AnomalyResult)
        .where(
            AnomalyResult.asset_id == window.identity.id,
            AnomalyResult.fault_type.in_(stale_keys),
            AnomalyResult.status == AnomalyStatus.OPEN,
        )
        .values(status=AnomalyStatus.CLEARED, cleared_at=cleared_at)
    )

    for key in stale_keys:
        window.open_anomaly_ids.pop(key, None)

    return result.rowcount or 0


async def run(session: AsyncSession, context: IntelligenceContext) -> dict[str, int]:
    """Detect anomalies across the fleet, diagnose them, and manage lifecycle.

    Every asset is examined, including those that have stopped reporting —
    connectivity faults are inferred from silence, and skipping silent assets
    would make a failed device simply vanish from the platform while its last
    known values sit on the dashboard looking healthy.
    """
    counts = {"opened": 0, "cleared": 0, "alerts_opened": 0, "alerts_resolved": 0}

    for window in context.assets():
        profile = get_profile(window.identity.asset_type)

        detections = _deduplicate(
            _envelope_checks(window)
            + _statistical_checks(window)
            + _connectivity_checks(window, context.computed_at)
        )
        detected_faults = {detection.fault_type for detection in detections}

        counts["cleared"] += await _clear_anomalies(
            session, window, detected_faults, context.computed_at
        )
        counts["alerts_resolved"] += await _auto_resolve(
            session, window, detected_faults, context.computed_at
        )

        if not detections:
            continue

        for detection in detections:
            fault_key = detection.fault_type.value

            # One anomaly per occurrence, not per detection cycle. A fault that
            # persists for an hour is one event that lasted an hour, not two
            # hundred and forty separate findings.
            if fault_key in window.open_anomaly_ids:
                continue

            diagnosis = diagnose(
                fault_type=detection.fault_type,
                reading=window.latest,
                window=window,
                profile=profile,
                evidence=detection.description,
            )

            result = AnomalyResult(
                asset_id=window.identity.id,
                telemetry_time=(
                    window.latest.time if window.latest else context.computed_at
                ),
                detected_at=context.computed_at,
                channel=detection.channel,
                fault_type=detection.fault_type,
                severity=detection.severity,
                anomaly_score=round(detection.score, 4),
                confidence=round(detection.confidence, 4),
                observed_value=detection.observed,
                expected_min=detection.expected_min,
                expected_max=detection.expected_max,
                deviation_sigma=detection.sigma,
                description=diagnosis.explanation,
                root_cause=diagnosis.root_cause,
                recommendation=diagnosis.recommendation,
                status=AnomalyStatus.OPEN,
            )
            session.add(result)
            await session.flush()
            window.open_anomaly_ids[fault_key] = result.id
            counts["opened"] += 1

            if detection.severity not in ALERTING_SEVERITIES:
                continue

            # One open alert per asset per fault. A device stuck in a fault
            # must not generate a new alert on every cycle.
            if fault_key in window.open_fault_keys:
                continue
            window.open_fault_keys.add(fault_key)

            alert = Alert(
                asset_id=window.identity.id,
                anomaly_result_id=result.id,
                severity=detection.severity,
                status=AlertStatus.ACTIVE,
                fault_type=detection.fault_type,
                title=f"{_channel_label(detection.channel)} anomaly on "
                f"{window.identity.asset_code}",
                # The alert carries the diagnosis, not the raw observation, so
                # whoever is paged sees the cause and the remedy rather than
                # only the symptom.
                message=f"{diagnosis.explanation} {diagnosis.recommendation}",
                channel=detection.channel,
                observed_value=detection.observed,
                expected_min=detection.expected_min,
                expected_max=detection.expected_max,
                triggered_at=context.computed_at,
            )
            session.add(alert)
            await session.flush()
            window.open_alert_ids[fault_key] = alert.id
            counts["alerts_opened"] += 1

            activity_log.add(
                kind="alert",
                severity=detection.severity.value,
                title=f"{detection.fault_type.value.replace('_', ' ').title()} detected",
                detail=diagnosis.explanation,
                asset_id=window.identity.id,
                asset_code=window.identity.asset_code,
                occurred_at=context.computed_at,
            )

    return counts
