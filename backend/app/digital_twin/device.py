"""A single virtual asset.

Each device owns its own state — battery charge, thermal mass, energy
accumulator, relay count, scenario — and steps forward independently. Two
devices of the same type started together diverge within seconds, which is what
makes a fleet view look like real hardware rather than a loop.

The device emits only :class:`~app.schemas.telemetry.TelemetryIngest`, the same
contract a real MIKOS sensor or an MQTT bridge would satisfy. Nothing
downstream can tell the difference, which is the whole point.

**It does not report health.** A physical charger has no opinion about its own
condition; it reports volts, amps, watts and degrees, and the platform draws
the conclusion. Health is computed by
:mod:`app.services.health_engine` during normalisation. Leaving that
determination in the simulator would mean the intelligence layers were grading
an answer the source had already written down.

Load is likewise derived rather than drawn from a distribution. A charger's
power trace is a long plateau followed by a decaying tail, and an air
conditioner's is a square wave gated by a thermostat — neither looks anything
like noise around a mean, and an anomaly detector trained against noise learns
nothing useful.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.digital_twin.profiles import TelemetryProfile
from app.digital_twin.scenarios import Distortion, ScenarioController
from app.schemas.enums import (
    ChargingState,
    ConnectivityState,
    DataQuality,
    OperationalState,
    TelemetrySource,
    TwinScenario,
)
from app.schemas.telemetry import TelemetryIngest

#: Probability per tick that a reading is flagged as less than fully trusted.
UNCERTAIN_CHANCE = 0.004
BAD_CHANCE = 0.0009

#: State of charge at which a charge is considered complete.
FULL_CHARGE_PERCENT = 99.4


@dataclass(slots=True)
class BatteryRuntime:
    """Charge state for assets that charge a battery."""

    #: State of charge, 0–100.
    soc_percent: float = 50.0
    #: Whether a load is currently connected.
    connected: bool = False
    #: Completed charge cycles over the device's life.
    cycles: int = 0
    #: Cumulative charge delivered, in units of full capacity. A cycle is
    #: counted per capacity-equivalent delivered rather than per plug-in, which
    #: is how battery wear is actually measured.
    delivered_capacity: float = 0.0
    fast_charging: bool = False
    state: ChargingState = ChargingState.IDLE
    #: Ticks until the connection state changes.
    phase_remaining: int = 0


@dataclass(slots=True)
class ThermostatRuntime:
    """Conditioned-space state for assets that cool a room."""

    indoor_c: float = 26.0
    #: Whether the compressor is currently energised.
    compressor_on: bool = False


@dataclass(slots=True)
class DeviceRuntime:
    """Mutable per-device state carried between ticks."""

    active: bool = False
    #: Ticks remaining in the current duty phase, for assets without a
    #: physical driver of their own.
    phase_remaining: int = 0
    temperature_c: float = 24.0
    energy_kwh: float = 0.0
    relay_operations: int = 0
    relay_closed: bool = False
    operating_seconds: float = 0.0
    #: Slow-moving wear term that accumulates across the device's life.
    wear: float = 0.0
    samples: int = 0
    load_fraction: float = 0.0

    battery: BatteryRuntime | None = None
    thermostat: ThermostatRuntime | None = None


@dataclass(slots=True)
class VirtualDevice:
    """One simulated asset bound to a real row in the ``assets`` table."""

    asset_id: uuid.UUID
    asset_code: str
    profile: TelemetryProfile
    rng: random.Random
    scenario: ScenarioController
    runtime: DeviceRuntime = field(default_factory=DeviceRuntime)

    @classmethod
    def create(
        cls,
        *,
        asset_id: uuid.UUID,
        asset_code: str,
        profile: TelemetryProfile,
        seed: int | None,
        initial_energy_kwh: float = 0.0,
        initial_relay_operations: int = 0,
        initial_operating_hours: float = 0.0,
    ) -> VirtualDevice:
        """Build a device, resuming from whatever the database already knows.

        Continuing the energy, relay and runtime counters across restarts keeps
        those figures monotonic, which the APM and Business Intelligence layers
        depend on.
        """
        # Deriving each device's seed from the global one keeps the whole fleet
        # reproducible while giving every device its own independent stream.
        device_seed = None if seed is None else seed ^ (asset_id.int & 0xFFFF_FFFF)
        rng = random.Random(device_seed)

        runtime = DeviceRuntime(
            temperature_c=profile.thermal.ambient_c + rng.uniform(-1.5, 2.5),
            energy_kwh=initial_energy_kwh,
            relay_operations=initial_relay_operations,
            operating_seconds=initial_operating_hours * 3600.0,
            phase_remaining=rng.randint(20, 400),
            active=rng.random() < profile.duty.active_fraction,
            wear=rng.uniform(0.0, 0.06),
        )

        if profile.battery is not None:
            runtime.battery = BatteryRuntime(
                # Staggered starting charge, so the fleet is spread across the
                # curve instead of every device finishing at the same moment.
                soc_percent=rng.uniform(12.0, 96.0),
                connected=rng.random() < profile.duty.active_fraction,
                cycles=rng.randint(40, 620),
                fast_charging=(
                    profile.battery.supports_fast_charge and rng.random() < 0.55
                ),
                phase_remaining=rng.randint(20, 500),
            )

        if profile.thermostat is not None:
            thermostat = profile.thermostat
            runtime.thermostat = ThermostatRuntime(
                indoor_c=thermostat.setpoint_c + rng.uniform(-1.0, 4.0),
                compressor_on=rng.random() < 0.5,
            )

        return cls(
            asset_id=asset_id,
            asset_code=asset_code,
            profile=profile,
            rng=rng,
            scenario=ScenarioController(profile, rng),
            runtime=runtime,
        )

    # --- Load drivers ---------------------------------------------------------

    def _advance_battery(self, interval_s: float) -> float:
        """Advance the charge curve and return the load fraction it implies.

        Bulk charge holds a near-constant draw; above the constant-voltage knee
        the current tapers towards trickle. Once full the charger sits at
        standby until the load is disconnected.
        """
        battery = self.runtime.battery
        model = self.profile.battery
        if battery is None or model is None:
            return 0.0

        # Plug and unplug on an exponential schedule, so connection events are
        # memoryless rather than periodic.
        battery.phase_remaining -= 1
        if battery.phase_remaining <= 0:
            battery.connected = not battery.connected
            duty = self.profile.duty
            mean = duty.mean_active_seconds if battery.connected else duty.mean_idle_seconds
            battery.phase_remaining = max(
                1, int(self.rng.expovariate(1.0 / mean) / max(interval_s, 0.001))
            )
            if battery.connected and model.supports_fast_charge:
                battery.fast_charging = self.rng.random() < 0.6

        if not battery.connected:
            battery.state = ChargingState.IDLE
            battery.soc_percent = max(
                0.0,
                battery.soc_percent
                - model.self_discharge_per_hour * (interval_s / 3600.0),
            )
            return self.rng.uniform(*self.profile.duty.idle_load)

        # --- Connected: work out where on the curve the cell sits ------------
        soc = battery.soc_percent

        if soc >= FULL_CHARGE_PERCENT:
            battery.state = ChargingState.COMPLETE
            load = model.trickle_load
        elif soc >= model.cv_knee_percent:
            # Constant-voltage taper: current decays as the cell approaches
            # full, so power falls away smoothly rather than cutting out.
            span = max(FULL_CHARGE_PERCENT - model.cv_knee_percent, 0.1)
            remaining = (FULL_CHARGE_PERCENT - soc) / span
            battery.state = (
                ChargingState.TRICKLE if remaining < 0.25 else ChargingState.TOPPING_OFF
            )
            load = model.trickle_load + (model.bulk_load - model.trickle_load) * (
                remaining**1.4
            )
        else:
            battery.state = ChargingState.CHARGING
            load = model.bulk_load
            if battery.fast_charging and soc < model.fast_charge_until_percent:
                load *= model.fast_charge_boost

        # Energy actually delivered into the cell this tick, allowing for
        # conversion loss, converted into a change in state of charge.
        delivered_wh = (
            self.profile.rated_power_w * load * 0.92 * (interval_s / 3600.0)
        )
        gain = (delivered_wh / model.capacity_wh) * 100.0

        previous = battery.soc_percent
        battery.soc_percent = min(100.0, previous + gain)
        battery.delivered_capacity += gain / 100.0

        # A cycle is a capacity-equivalent delivered, not a plug-in event.
        while battery.delivered_capacity >= 1.0:
            battery.delivered_capacity -= 1.0
            battery.cycles += 1

        return max(0.0, min(1.15, load))

    def _advance_thermostat(self, interval_s: float) -> float:
        """Advance the conditioned space and return the load fraction.

        Classic hysteresis: the compressor starts when the room drifts above
        the deadband and stops when it falls below. Every transition is a relay
        operation, which is what makes the operation count meaningful.
        """
        thermostat = self.runtime.thermostat
        model = self.profile.thermostat
        if thermostat is None or model is None:
            return 0.0

        upper = model.setpoint_c + model.hysteresis_c
        lower = model.setpoint_c - model.hysteresis_c

        if thermostat.compressor_on and thermostat.indoor_c <= lower:
            thermostat.compressor_on = False
            self.runtime.relay_operations += 1
        elif not thermostat.compressor_on and thermostat.indoor_c >= upper:
            thermostat.compressor_on = True
            self.runtime.relay_operations += 1

        hours = interval_s / 3600.0
        if thermostat.compressor_on:
            thermostat.indoor_c -= model.cooling_rate_c_per_hour * hours
        else:
            # Newton-style drift back towards ambient: fast when the gap is
            # wide, slow as it closes.
            gap = model.ambient_c - thermostat.indoor_c
            thermostat.indoor_c += (
                model.warming_rate_c_per_hour * hours * max(0.0, gap / 10.0)
            )

        thermostat.indoor_c += self.rng.gauss(0.0, 0.012)
        self.runtime.relay_closed = thermostat.compressor_on

        if not thermostat.compressor_on:
            return self.rng.uniform(*self.profile.duty.idle_load)

        # A modulating inverter unit works harder the further the room is from
        # setpoint, so load tracks the error rather than sitting flat.
        error = max(0.0, thermostat.indoor_c - model.setpoint_c)
        low, high = self.profile.duty.active_load
        return low + (high - low) * min(1.0, error / (model.hysteresis_c * 2.4))

    def _advance_generic_duty(self, interval_s: float) -> float:
        """Fallback duty cycle for categories with no physical driver."""
        runtime = self.runtime
        runtime.phase_remaining -= 1
        if runtime.phase_remaining <= 0:
            runtime.active = not runtime.active
            duty = self.profile.duty
            mean = duty.mean_active_seconds if runtime.active else duty.mean_idle_seconds
            runtime.phase_remaining = max(
                1, int(self.rng.expovariate(1.0 / mean) / max(interval_s, 0.001))
            )

        low, high = (
            self.profile.duty.active_load
            if runtime.active
            else self.profile.duty.idle_load
        )
        base = self.rng.uniform(low, high)
        if not runtime.active:
            return base

        sway = 0.06 * math.sin(runtime.samples / 47.0 + self.asset_id.int % 17)
        return max(0.0, min(1.05, base + sway))

    def _load_fraction(self, interval_s: float) -> float:
        """Share of rated power drawn this tick, from whichever driver applies."""
        if self.profile.battery is not None:
            fraction = self._advance_battery(interval_s)
            self.runtime.active = bool(
                self.runtime.battery and self.runtime.battery.connected
            )
            return fraction

        if self.profile.thermostat is not None:
            fraction = self._advance_thermostat(interval_s)
            self.runtime.active = bool(
                self.runtime.thermostat and self.runtime.thermostat.compressor_on
            )
            return fraction

        return self._advance_generic_duty(interval_s)

    # --- Thermal ---------------------------------------------------------------

    def _update_temperature(
        self, power_w: float, interval_s: float, distortion: Distortion
    ) -> float:
        """Advance the first-order case-temperature model by one tick."""
        thermal = self.profile.thermal
        rise_per_watt = thermal.rise_per_watt + distortion.thermal_penalty
        target = thermal.ambient_c + power_w * rise_per_watt + distortion.temperature_delta

        alpha = 1.0 - math.exp(-interval_s / thermal.time_constant_s)
        current = self.runtime.temperature_c
        updated = current + (target - current) * alpha
        updated += self.rng.gauss(0.0, 0.09)

        self.runtime.temperature_c = updated
        return updated

    # --- Tick ------------------------------------------------------------------

    def step(self, now: datetime, interval_s: float) -> TelemetryIngest | None:
        """Advance the device and produce one reading.

        Returns ``None`` when the device is offline: a genuinely disconnected
        asset publishes nothing, and the platform must infer its state from
        silence rather than from a packet announcing its own absence.
        """
        runtime = self.runtime
        runtime.samples += 1

        state = self.scenario.advance()
        distortion = self.scenario.distortion()

        load = self._load_fraction(interval_s)
        runtime.load_fraction = load

        if not distortion.reporting:
            runtime.wear = min(0.45, runtime.wear + 0.0000006)
            return None

        profile = self.profile
        noise = profile.noise

        # --- Electrical --------------------------------------------------------
        voltage = (
            profile.nominal_voltage_v
            * distortion.voltage_scale
            * (1.0 + self.rng.gauss(0.0, profile.voltage_tolerance / 3.0))
        )

        power = profile.rated_power_w * load * distortion.power_scale
        power = max(0.0, power * (1.0 + self.rng.gauss(0.0, noise)))

        power_factor: float | None = None
        if profile.power_factor_range is not None:
            pf_low, pf_high = profile.power_factor_range
            pf_base = pf_low + (pf_high - pf_low) * min(1.0, load * 1.25)
            power_factor = pf_base + distortion.power_factor_delta
            power_factor = max(0.05, min(1.0, power_factor + self.rng.gauss(0.0, 0.006)))

        # Current follows from power, voltage and power factor rather than
        # being generated independently, so the three stay physically coherent.
        effective_pf = power_factor if power_factor else 1.0
        current = 0.0
        if voltage > 1.0:
            current = power / (voltage * effective_pf)
        current = max(
            0.0, current * distortion.current_scale * (1.0 + self.rng.gauss(0.0, noise))
        )

        reactive_power: float | None = None
        apparent_power: float | None = None
        if profile.capabilities.apparent_power:
            apparent_power = voltage * current
            reactive_power = math.sqrt(max(apparent_power**2 - power**2, 0.0))

        frequency: float | None = None
        if profile.nominal_frequency_hz is not None:
            frequency = (
                profile.nominal_frequency_hz
                + distortion.frequency_delta
                + self.rng.gauss(0.0, 0.021)
            )

        # --- Thermal, energy and runtime ---------------------------------------
        temperature = self._update_temperature(power, interval_s, distortion)

        energy: float | None = None
        if profile.capabilities.energy:
            runtime.energy_kwh += (power * interval_s) / 3_600_000.0
            energy = runtime.energy_kwh

        if runtime.active:
            runtime.operating_seconds += interval_s

        stress = 1.0 + (distortion.health_penalty / 55.0)
        runtime.wear = min(0.45, runtime.wear + 0.0000009 * stress)

        # --- Operational mode ---------------------------------------------------
        if state.scenario is TwinScenario.MAINTENANCE:
            operational = OperationalState.MAINTENANCE
        elif runtime.active:
            operational = OperationalState.RUNNING
        else:
            operational = OperationalState.IDLE

        quality = DataQuality.GOOD
        roll = self.rng.random()
        if roll < BAD_CHANCE:
            quality = DataQuality.BAD
        elif roll < UNCERTAIN_CHANCE:
            quality = DataQuality.UNCERTAIN

        battery = runtime.battery
        thermostat = runtime.thermostat

        return TelemetryIngest(
            asset_id=self.asset_id,
            time=now,
            voltage_v=round(voltage, 3),
            current_a=round(current, 4),
            power_w=round(power, 3),
            reactive_power_var=None if reactive_power is None else round(reactive_power, 3),
            apparent_power_va=None if apparent_power is None else round(apparent_power, 3),
            energy_kwh=None if energy is None else round(energy, 6),
            frequency_hz=None if frequency is None else round(frequency, 3),
            power_factor=None if power_factor is None else round(power_factor, 4),
            temperature_c=round(temperature, 2),
            runtime_hours=round(runtime.operating_seconds / 3600.0, 4),
            load_percent=round(load * 100.0, 2),
            relay_status=runtime.relay_closed if profile.capabilities.relay else None,
            relay_operations=runtime.relay_operations if profile.capabilities.relay else None,
            charging_state=battery.state if battery else None,
            battery_percent=round(battery.soc_percent, 2) if battery else None,
            charge_cycles=battery.cycles if battery else None,
            fast_charging=(
                battery.fast_charging
                if battery and profile.capabilities.fast_charging
                else None
            ),
            indoor_temperature_c=(
                round(thermostat.indoor_c, 2) if thermostat else None
            ),
            # Health is deliberately absent. The Health Engine derives it from
            # the channels above during normalisation.
            health_score=None,
            health_state=None,
            operational_state=operational,
            connectivity_state=ConnectivityState.ONLINE,
            source=TelemetrySource.DIGITAL_TWIN,
            quality=quality,
        )

    @property
    def operating_hours(self) -> float:
        """Total hours this device has spent under load."""
        return self.runtime.operating_seconds / 3600.0

    def snapshot(self) -> dict[str, object]:
        """Diagnostic view, surfaced by the twin status endpoint."""
        battery = self.runtime.battery
        return {
            "asset_code": self.asset_code,
            "asset_type": self.profile.asset_type.value,
            "scenario": self.scenario.describe(),
            "temperature_c": round(self.runtime.temperature_c, 1),
            "load_percent": round(self.runtime.load_fraction * 100.0, 1),
            "active": self.runtime.active,
            "samples": self.runtime.samples,
            "battery_percent": round(battery.soc_percent, 1) if battery else None,
            "charging_state": battery.state.value if battery else None,
            "indoor_temperature_c": (
                round(self.runtime.thermostat.indoor_c, 1)
                if self.runtime.thermostat
                else None
            ),
        }
