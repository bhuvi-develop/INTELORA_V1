"""Digital Twin Engine.

Creates realistic virtual assets that behave like physical devices, so the
platform can be developed, demonstrated and validated without hardware. It is
one data source among several and holds no privileged position: everything it
emits satisfies the same telemetry contract a real MIKOS sensor would.
"""

from app.digital_twin.device import BatteryRuntime, ThermostatRuntime, VirtualDevice
from app.digital_twin.engine import DigitalTwinEngine, EngineStats, TelemetrySink
from app.digital_twin.profiles import (
    PROFILES,
    PROFILE_ORDER,
    BatteryModel,
    TelemetryProfile,
    ThermostatModel,
    capabilities_for,
    get_profile,
)
from app.digital_twin.scenarios import ScenarioController, ScenarioState

__all__ = [
    "PROFILES",
    "PROFILE_ORDER",
    "BatteryModel",
    "BatteryRuntime",
    "DigitalTwinEngine",
    "EngineStats",
    "ScenarioController",
    "ScenarioState",
    "TelemetryProfile",
    "TelemetrySink",
    "ThermostatModel",
    "ThermostatRuntime",
    "VirtualDevice",
    "capabilities_for",
    "get_profile",
]
