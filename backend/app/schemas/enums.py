"""Platform-wide enumerations.

These types are the shared vocabulary of INTELORA. They are mirrored exactly by
``frontend/src/types/enums.ts`` — when one side changes, the other must change
with it.

The status model is deliberately three independent dimensions. Health,
operation and connectivity are orthogonal: an asset is always all three at
once, and collapsing them into a single field would make legitimate
combinations such as *running · warning · online* unrepresentable.
"""

from __future__ import annotations

from enum import StrEnum


class AssetType(StrEnum):
    """Supported asset categories.

    Adding a category means adding a member here and a twin profile; no
    dashboard or intelligence code changes.
    """

    LAPTOP_CHARGER = "laptop_charger"
    MOBILE_CHARGER = "mobile_charger"
    AIR_CONDITIONER = "air_conditioner"


class HealthState(StrEnum):
    """Condition dimension, derived from the numeric health score."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class OperationalState(StrEnum):
    """What the asset is currently doing."""

    RUNNING = "running"
    IDLE = "idle"
    MAINTENANCE = "maintenance"


class ConnectivityState(StrEnum):
    """Whether the platform is hearing from the asset.

    ``UNKNOWN`` distinguishes "we have not heard anything yet" from a confirmed
    ``OFFLINE``, which matters on unreliable networks.
    """

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class TelemetrySource(StrEnum):
    """Provenance of a telemetry record.

    Intelligence and dashboard code must never branch on this value — it exists
    for audit and trust, so an operator can see that a demo is running on the
    Digital Twin rather than on real hardware.
    """

    REAL_SENSOR = "real_sensor"
    DIGITAL_TWIN = "digital_twin"
    SIMULATOR = "simulator"
    REST_API = "rest_api"
    MQTT = "mqtt"


class DataQuality(StrEnum):
    """Confidence in an individual reading.

    Distinct from OEE quality (:class:`~app.schemas.enums.OeeFactor`); the two
    concepts share a word and nothing else.
    """

    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"


class OeeFactor(StrEnum):
    """The three factors whose product is OEE."""

    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    QUALITY = "quality"


class AlertSeverity(StrEnum):
    """How urgent an alert is. Orthogonal to :class:`AlertStatus`."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFORMATION = "information"


class AlertStatus(StrEnum):
    """Where an alert sits in its lifecycle. Orthogonal to severity."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class RiskLevel(StrEnum):
    """Shared ranking scale.

    Used by predictive risk, APM criticality and maintenance priority so that a
    single colour vocabulary carries across every module instead of each layer
    inventing its own.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class LifecycleStage(StrEnum):
    """Where an asset sits in its service life."""

    COMMISSIONING = "commissioning"
    NORMAL = "normal"
    WEAR = "wear"
    END_OF_LIFE = "end_of_life"


class FaultType(StrEnum):
    """Fault taxonomy across all supported asset types.

    Which faults apply to which asset type is declared by that type's
    capability profile, not by this enum.
    """

    # Electrical — common to every asset type
    VOLTAGE_SPIKE = "voltage_spike"
    VOLTAGE_DROP = "voltage_drop"
    OVER_CURRENT = "over_current"
    UNDER_CURRENT = "under_current"
    POWER_SPIKE = "power_spike"
    POWER_LOSS = "power_loss"
    OVER_TEMPERATURE = "over_temperature"
    FREQUENCY_VARIATION = "frequency_variation"
    POOR_POWER_FACTOR = "poor_power_factor"
    ABNORMAL_ENERGY = "abnormal_energy"

    # Connectivity — the platform infers these from silence, not from a packet
    DEVICE_OFFLINE = "device_offline"
    COMMUNICATION_FAILURE = "communication_failure"

    #: Catch-all for a device whose channels are individually in range but
    #: collectively incoherent — the electrical relationships do not hold.
    UNEXPECTED_BEHAVIOUR = "unexpected_behaviour"

    # Asset-specific
    ADAPTER_FAILURE = "adapter_failure"
    CABLE_FAILURE = "cable_failure"
    COMPRESSOR_WEAR = "compressor_wear"
    FILTER_DIRTY = "filter_dirty"
    RELAY_FAILURE = "relay_failure"


class AnomalyStatus(StrEnum):
    """Lifecycle of a detected anomaly.

    Distinct from alert lifecycle. An anomaly is an observation the platform
    made; an alert is a request for someone to act. Most anomalies never become
    alerts, and they clear on their own when the condition passes.
    """

    OPEN = "open"
    CLEARED = "cleared"
    SUPPRESSED = "suppressed"


class RootCause(StrEnum):
    """Diagnosed origin of an anomaly.

    A fault type says *what* the platform saw; a root cause says *why*. Two
    assets can both report over-temperature — one because its airflow is
    blocked, another because the supply is sagging and it is drawing
    compensating current. The remedies are unrelated, so the distinction has to
    survive into the recommendation.
    """

    SUPPLY_INSTABILITY = "supply_instability"
    THERMAL_DISSIPATION = "thermal_dissipation"
    AIRFLOW_RESTRICTION = "airflow_restriction"
    COMPONENT_DEGRADATION = "component_degradation"
    CONNECTION_INTEGRITY = "connection_integrity"
    LOAD_MISMATCH = "load_mismatch"
    REACTIVE_LOADING = "reactive_loading"
    MECHANICAL_WEAR = "mechanical_wear"
    NETWORK_PATH = "network_path"
    POWER_INTERRUPTION = "power_interruption"
    METERING_FAULT = "metering_fault"
    UNDETERMINED = "undetermined"


class BusinessImpact(StrEnum):
    """How much a prescriptive recommendation is worth acting on."""

    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class MaintenanceTaskType(StrEnum):
    """Categories of work a maintenance plan can call for."""

    INSPECTION = "inspection"
    CLEANING = "cleaning"
    CALIBRATION = "calibration"
    COMPONENT_REPLACEMENT = "component_replacement"
    THERMAL_SERVICE = "thermal_service"
    ELECTRICAL_TEST = "electrical_test"
    FIRMWARE = "firmware"


class MaintenanceOutcome(StrEnum):
    """How a recorded maintenance activity concluded."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class TwinScenario(StrEnum):
    """Behaviours the Digital Twin can drive a virtual device through.

    These are engine-side scenarios, not asset states. ``FAILURE`` and
    ``RECOVERY`` surface to the platform as transitions into and out of
    ``HealthState.CRITICAL``.
    """

    HEALTHY = "healthy"
    DEGRADING = "degrading"
    FAILURE = "failure"
    RECOVERY = "recovery"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class RecommendedAction(StrEnum):
    """Prescriptive optimisation outcomes.

    All are advisory. INTELORA observes and recommends; it does not actuate.
    """

    CONTINUE_MONITORING = "continue_monitoring"
    REDUCE_LOAD = "reduce_load"
    INCREASE_SETPOINT = "increase_setpoint"
    SCHEDULE_INSPECTION = "schedule_inspection"
    CLEAN_FILTER = "clean_filter"
    REPLACE_COMPONENT = "replace_component"
    REPLACE_ASSET = "replace_asset"


class ChargingState(StrEnum):
    """Battery charging phase, reported by asset types that charge a battery.

    Follows the shape of a real charge curve rather than a simple on/off flag:
    constant-current while the cell fills, constant-voltage as it tapers near
    full, then trickle. The distinction matters because current and power
    behave completely differently in each phase, and an anomaly detector that
    cannot tell a CV taper from a genuine power loss will produce false alarms
    on every device that finishes charging.
    """

    #: Not connected to a load.
    IDLE = "idle"
    #: Constant-current bulk charge.
    CHARGING = "charging"
    #: Constant-voltage taper above roughly 80 percent.
    TOPPING_OFF = "topping_off"
    #: Maintenance current at full charge.
    TRICKLE = "trickle"
    #: Connected and full; drawing standby only.
    COMPLETE = "complete"


class TimeRange(StrEnum):
    """Named query windows supported across the historical endpoints.

    Named rather than free-form because the range determines which storage tier
    answers the query — raw hypertable, one-minute rollup, or one-hour rollup.
    Letting a caller ask for thirty days of raw one-second telemetry would mean
    scanning hundreds of millions of rows to draw a few hundred pixels.
    """

    LIVE = "live"
    LAST_HOUR = "last_hour"
    TODAY = "today"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"


class ScopeType(StrEnum):
    """Aggregation level for OEE and efficiency rollups."""

    ENTERPRISE = "enterprise"
    ORGANIZATION = "organization"
    BUILDING = "building"
    DEPARTMENT = "department"
    FLEET = "fleet"
    ASSET = "asset"
