"""Limit checking with debounce, so one noisy sample neither raises nor clears an alarm."""

import math
from datetime import datetime

from station.protocol import DEFINITIONS

from .records import AlarmChange

SAMPLES_TO_CHANGE = 3


class AlarmMonitor:
    def __init__(self, samples_to_change: int = SAMPLES_TO_CHANGE):
        self.samples_to_change = samples_to_change
        self._limits = [
            (p.name, bound, limit)
            for p in DEFINITIONS.parameters
            for bound, limit in (("low", p.low), ("high", p.high))
            if limit is not None
        ]
        self.active: set[tuple[str, str]] = set()
        self._streak: dict[tuple[str, str], int] = {}

    def check(self, time: datetime, values: dict[str, float]) -> list[AlarmChange]:
        changes = []
        for name, bound, limit in self._limits:
            value = values[name]
            # a reading that is not a number says nothing about the limit
            if math.isnan(value):
                continue
            key = (name, bound)
            outside = value < limit if bound == "low" else value > limit
            if outside == (key in self.active):
                self._streak[key] = 0
                continue
            self._streak[key] = self._streak.get(key, 0) + 1
            if self._streak[key] >= self.samples_to_change:
                self._streak[key] = 0
                self.active ^= {key}
                changes.append(AlarmChange(time, name, bound, outside, value))
        return changes
