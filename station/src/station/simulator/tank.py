"""Toy physics of a pressurised tank. No I/O and no clock: time only moves in step().

Pressures are gauge (0 bar = outside air). The numbers are chosen to be watchable on a dashboard,
not to model a real tank.
"""

import random
from dataclasses import dataclass

SUPPLY_BAR = 10.0
INITIAL_BAR = 2.0
AMBIENT_DEGC = 20.0
RELIEF_OPENS_BAR = 7.5
RELIEF_CLOSES_BAR = 6.5

# flow coefficients, per second
FILL_RATE = 0.15
VENT_RATE = 0.20
RELIEF_RATE = 0.40

HEATING_DEGC_PER_BAR = 4.0
COOLING_RATE = 0.05

VALVES = ("fill", "vent", "relief")
MAX_LEAK_RATE = 1.0
MAX_NOISE_BAR = 2.0


class FaultError(ValueError):
    """A fault request with a magnitude that makes no sense."""


class StuckValveError(RuntimeError):
    """The valve did not move."""


@dataclass(frozen=True)
class Reading:
    tank_pressure: float
    tank_temperature: float
    fill_valve: int
    vent_valve: int
    relief_valve: int


class Tank:
    def __init__(self, seed: int = 0):
        self._seed = seed
        self.reset()

    def reset(self) -> None:
        self.pressure = INITIAL_BAR
        self.temperature = AMBIENT_DEGC
        self.valves = dict.fromkeys(VALVES, False)
        self.clear_faults()
        self._random = random.Random(self._seed)

    def clear_faults(self) -> None:
        self.leak_rate = 0.0
        self.noise_bar = 0.0
        self.stuck: set[str] = set()

    def set_valve(self, name: str, is_open: bool) -> None:
        """Command the fill or vent valve. The relief valve works by itself."""
        if name in self.stuck:
            raise StuckValveError(f"{name} valve is stuck")
        self.valves[name] = is_open

    def inject_fault(self, fault: str, magnitude: float) -> None:
        # "not (a < x <= b)" also rejects NaN
        match fault:
            case "leak":
                if not 0 < magnitude <= MAX_LEAK_RATE:
                    raise FaultError(f"leak rate must be in (0, {MAX_LEAK_RATE}] per second")
                self.leak_rate = magnitude
            case "noisy_sensor":
                if not 0 < magnitude <= MAX_NOISE_BAR:
                    raise FaultError(f"noise must be in (0, {MAX_NOISE_BAR}] bar")
                self.noise_bar = magnitude
            case "stuck_valve":
                # magnitude picks the valve: 1 = fill, 2 = vent, 3 = relief
                if magnitude not in (1, 2, 3):
                    raise FaultError("stuck valve must be 1, 2 or 3")
                self.stuck.add(VALVES[int(magnitude) - 1])
            case _:
                raise FaultError(f"unknown fault: {fault}")

    def step(self, dt: float) -> list[str]:
        """Advance by dt seconds and return the names of the events that happened."""
        flow = (
            self.valves["fill"] * FILL_RATE * (SUPPLY_BAR - self.pressure)
            - self.valves["vent"] * VENT_RATE * self.pressure
            - self.valves["relief"] * RELIEF_RATE * self.pressure
            - self.leak_rate * self.pressure
        )
        change = flow * dt
        self.pressure = max(0.0, self.pressure + change)
        self.temperature += HEATING_DEGC_PER_BAR * change
        self.temperature -= COOLING_RATE * (self.temperature - AMBIENT_DEGC) * dt
        return self._operate_relief_valve()

    def _operate_relief_valve(self) -> list[str]:
        if "relief" in self.stuck:
            return []
        if not self.valves["relief"] and self.pressure >= RELIEF_OPENS_BAR:
            self.valves["relief"] = True
            return ["relief_valve_opened"]
        if self.valves["relief"] and self.pressure <= RELIEF_CLOSES_BAR:
            self.valves["relief"] = False
            return ["relief_valve_closed"]
        return []

    def read(self) -> Reading:
        """What the sensors report, which is not always the truth."""
        noise = self._random.gauss(0.0, self.noise_bar) if self.noise_bar else 0.0
        return Reading(
            tank_pressure=self.pressure + noise,
            tank_temperature=self.temperature,
            fill_valve=int(self.valves["fill"]),
            vent_valve=int(self.valves["vent"]),
            relief_valve=int(self.valves["relief"]),
        )
