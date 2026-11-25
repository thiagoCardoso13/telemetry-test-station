import math

import pytest

from station.protocol import DEFINITIONS
from station.simulator.tank import (
    AMBIENT_DEGC,
    INITIAL_BAR,
    RELIEF_OPENS_BAR,
    FaultError,
    StuckValveError,
    Tank,
)

DT = 0.1
HIGH_LIMIT = next(p.high for p in DEFINITIONS.parameters if p.name == "tank_pressure")


def run(tank: Tank, seconds: float) -> list[str]:
    events = []
    for _ in range(round(seconds / DT)):
        events += tank.step(DT)
    return events


def test_tank_at_rest_does_not_change():
    tank = Tank()

    run(tank, 60)

    assert tank.pressure == INITIAL_BAR
    assert tank.temperature == AMBIENT_DEGC


def test_fill_raises_pressure_and_temperature_and_vent_lowers_pressure():
    tank = Tank()
    tank.set_valve("fill", True)
    run(tank, 3)
    filled, warm = tank.pressure, tank.temperature

    tank.set_valve("fill", False)
    tank.set_valve("vent", True)
    run(tank, 3)

    assert filled > INITIAL_BAR
    assert warm > AMBIENT_DEGC
    assert tank.pressure < filled


def test_relief_valve_keeps_a_filling_tank_below_the_high_limit():
    tank = Tank()
    tank.set_valve("fill", True)
    highest = 0.0
    events = []
    for _ in range(1_000):
        events += tank.step(DT)
        highest = max(highest, tank.pressure)

    assert RELIEF_OPENS_BAR <= highest < HIGH_LIMIT
    assert events[:2] == ["relief_valve_opened", "relief_valve_closed"]


def test_stuck_relief_valve_lets_pressure_pass_the_high_limit():
    tank = Tank()
    tank.inject_fault("stuck_valve", 3)
    tank.set_valve("fill", True)

    events = run(tank, 60)

    assert tank.pressure > HIGH_LIMIT
    assert events == []


def test_stuck_valve_refuses_to_move_until_faults_are_cleared():
    tank = Tank()
    tank.inject_fault("stuck_valve", 2)

    with pytest.raises(StuckValveError):
        tank.set_valve("vent", True)

    tank.clear_faults()
    tank.set_valve("vent", True)
    assert tank.valves["vent"]


def test_leak_drains_a_closed_tank():
    tank = Tank()
    tank.inject_fault("leak", 0.2)

    run(tank, 30)

    assert 0 <= tank.pressure < 0.5


def test_noise_changes_readings_but_not_the_tank():
    tank = Tank(seed=1)
    tank.inject_fault("noisy_sensor", 0.3)

    readings = {tank.read().tank_pressure for _ in range(20)}

    assert len(readings) == 20
    assert tank.pressure == INITIAL_BAR


def test_same_seed_gives_the_same_noise_also_after_reset():
    def noisy(tank: Tank) -> list[float]:
        tank.inject_fault("noisy_sensor", 0.3)
        return [tank.read().tank_pressure for _ in range(20)]

    first = Tank(seed=5)
    original = noisy(first)

    assert noisy(Tank(seed=5)) == original
    assert noisy(Tank(seed=6)) != original
    first.reset()
    assert noisy(first) == original


@pytest.mark.parametrize(
    ("fault", "magnitude"),
    [
        ("leak", 0),
        ("leak", 5),
        ("leak", math.nan),
        ("noisy_sensor", -1),
        ("noisy_sensor", math.inf),
        ("stuck_valve", 4),
        ("stuck_valve", 1.5),
        ("meteorite", 1),
    ],
)
def test_nonsense_faults_are_refused(fault, magnitude):
    with pytest.raises(FaultError):
        Tank().inject_fault(fault, magnitude)
