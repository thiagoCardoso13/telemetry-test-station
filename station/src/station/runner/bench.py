"""Two ways to reach a tank: simulated in-process with simulated time, or the running station."""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import psycopg

from station import protocol
from station.ingest import Batch, Processor
from station.simulator import Device

from .conditions import Sample

PERIOD_S = 0.1


class BenchError(RuntimeError):
    """The test bench itself does not work, so no verdict about the tank is possible."""


@dataclass(frozen=True)
class Result:
    status: str  # "completed", "failed" or "rejected"
    error: int | None = None


class Bench(Protocol):
    def send(self, name: str, args: dict) -> Result: ...
    def wait(self, seconds: float) -> None: ...
    def mark(self) -> None:
        """Forget what happened so far."""

    def samples(self) -> list[Sample]:
        """Everything since the mark, oldest first."""


class SimulatedBench:
    """Simulator and ingest logic wired together without sockets, database or real time."""

    def __init__(self, seed: int = 1):
        self._device = Device(seed)
        self._processor = Processor()
        self._steps = 0
        self._sequence = 0
        self._samples: list[Sample] = []

    def _now_ms(self) -> int:
        return 1_700_000_000_000 + self._steps * 100

    def _receive(self, datagrams: list[bytes]) -> Batch:
        batch = Batch()
        for datagram in datagrams:
            self._processor.process(datagram, datetime.now(UTC), batch)
        return batch

    def send(self, name: str, args: dict) -> Result:
        message = protocol.Ping() if name == "ping" else protocol.Command(name, args)
        packet = protocol.to_packet(message, sequence=self._sequence, time_ms=self._now_ms())
        self._sequence += 1
        batch = self._receive(self._device.handle(protocol.encode(packet), self._now_ms()))
        if not batch.commands:
            raise BenchError(f"no answer to {name}")
        last = batch.commands[-1]
        return Result(last.status, last.error)

    def wait(self, seconds: float) -> None:
        for _ in range(round(seconds / PERIOD_S)):
            self._steps += 1
            batch = self._receive(self._device.tick(PERIOD_S, self._now_ms()))
            values = {s.parameter: s.value for s in batch.samples}
            self._samples.append(
                Sample(self._steps * PERIOD_S, values, frozenset(self._processor.alarms.active))
            )

    def mark(self) -> None:
        self._samples = []

    def samples(self) -> list[Sample]:
        return self._samples


class LiveBench:
    """The running station: commands through ingest, observations from its database."""

    def __init__(self, control_url: str, database_url: str):
        self.control_url = control_url.rstrip("/")
        try:
            self._database = psycopg.connect(database_url, autocommit=True)
        except psycopg.OperationalError as error:
            raise BenchError(f"cannot reach the database: {error}") from error
        self._mark: datetime = self._latest()

    def close(self) -> None:
        self._database.close()

    def _latest(self) -> datetime:
        (latest,) = self._database.execute("SELECT max(time) FROM telemetry_sample").fetchone()
        if latest is None:
            raise BenchError("no telemetry: is the station running?")
        return latest

    def send(self, name: str, args: dict) -> Result:
        request = urllib.request.Request(
            f"{self.control_url}/commands",
            data=json.dumps({"name": name, "args": args}).encode(),
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                command_id = json.load(response)["id"]
        except (urllib.error.URLError, TimeoutError) as error:
            raise BenchError(f"ingest did not accept {name}: {error}") from error

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status, code = self._database.execute(
                "SELECT status, error FROM command WHERE id = %s", (command_id,)
            ).fetchone()
            if status not in ("sent", "accepted"):
                return Result(status, code)
            time.sleep(0.05)
        raise BenchError(f"no answer to {name}")

    def wait(self, seconds: float) -> None:
        before = self._latest()
        time.sleep(seconds)
        if seconds >= 1 and self._latest() == before:
            raise BenchError("telemetry stopped")

    def mark(self) -> None:
        self._mark = self._latest()

    def samples(self) -> list[Sample]:
        # the time on a sample is the simulator's clock, and so are the alarm times
        rows = self._database.execute(
            "SELECT time, parameter, value FROM telemetry_sample WHERE time > %s ORDER BY time",
            (self._mark,),
        ).fetchall()
        alarms = self._database.execute(
            "SELECT parameter, bound, raised_at, cleared_at FROM alarm"
            " WHERE cleared_at IS NULL OR cleared_at > %s",
            (self._mark,),
        ).fetchall()
        values: dict[datetime, dict[str, float]] = {}
        for when, parameter, value in rows:
            values.setdefault(when, {})[parameter] = value
        return [
            Sample(
                when.timestamp(),
                read,
                frozenset(
                    (parameter, bound)
                    for parameter, bound, raised, cleared in alarms
                    if raised <= when and (cleared is None or when < cleared)
                ),
            )
            for when, read in values.items()
        ]
