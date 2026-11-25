"""What processing one or more datagrams asks the database to do."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Sample:
    time: datetime
    parameter: str
    value: float


@dataclass(frozen=True)
class LogEntry:
    time: datetime
    direction: str  # "in" or "out"
    valid: bool
    detail: str
    service: int | None = None
    subservice: int | None = None
    sequence: int | None = None


@dataclass(frozen=True)
class AlarmChange:
    time: datetime
    parameter: str
    bound: str  # "low" or "high"
    raised: bool  # False means cleared
    value: float


@dataclass(frozen=True)
class CommandUpdate:
    time: datetime
    request_id: bytes
    status: str  # "accepted", "rejected", "completed" or "failed"
    error: int | None = None


@dataclass
class Batch:
    samples: list[Sample] = field(default_factory=list)
    log: list[LogEntry] = field(default_factory=list)
    alarms: list[AlarmChange] = field(default_factory=list)
    commands: list[CommandUpdate] = field(default_factory=list)
    counters: Counter = field(default_factory=Counter)

    def __bool__(self) -> bool:
        return any((self.samples, self.log, self.alarms, self.commands, self.counters))
