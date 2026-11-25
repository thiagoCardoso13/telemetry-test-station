"""Conditions written as text, such as "tank_pressure >= 7.5" or "alarm tank_pressure high"."""

import operator
import re
from collections.abc import Callable
from dataclasses import dataclass

from station.protocol import DEFINITIONS

OPERATORS = {
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "<": operator.lt,
    ">": operator.gt,
}
_VALUE = re.compile(r"(\w+) (<=|>=|==|<|>) (-?\d+(?:\.\d+)?)")
_ALARM = re.compile(r"(no )?alarm (\w+) (low|high)")


@dataclass(frozen=True)
class Sample:
    """The tank at one instant, as seen from the ground."""

    time: float  # seconds
    values: dict[str, float]
    alarms: frozenset[tuple[str, str]] = frozenset()


@dataclass(frozen=True)
class Condition:
    text: str
    holds: Callable[[Sample], bool]
    parameter: str

    def observed(self, sample: Sample) -> str:
        if "alarm" in self.text.split():
            active = sorted(" ".join(a) for a in sample.alarms)
            return f"active alarms: {', '.join(active) or 'none'}"
        return f"{self.parameter} = {sample.values[self.parameter]:.2f}"


def parse(text: str) -> Condition:
    names = {p.name for p in DEFINITIONS.parameters}
    if match := _VALUE.fullmatch(str(text)):
        parameter, symbol, number = match.groups()
        if parameter in names:
            compare, limit = OPERATORS[symbol], float(number)
            return Condition(text, lambda s: compare(s.values[parameter], limit), parameter)
    elif match := _ALARM.fullmatch(str(text)):
        negated, parameter, bound = match.groups()
        if parameter in names:
            wanted = not negated
            return Condition(text, lambda s: ((parameter, bound) in s.alarms) == wanted, parameter)
    raise ValueError(f"cannot understand condition: {text!r}")
