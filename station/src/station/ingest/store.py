"""PostgreSQL access. One batch is one transaction, announced with NOTIFY when it commits."""

import asyncio
import json
import math
from datetime import datetime, timedelta
from importlib import resources

import psycopg
from psycopg.types.json import Jsonb

from .records import Batch

CHANNEL = "station"


def _finite(value: float) -> float | None:
    return value if math.isfinite(value) else None  # NaN is not valid JSON


class Store:
    def __init__(self, url: str):
        self.url = url
        self._connection: psycopg.AsyncConnection | None = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> psycopg.AsyncConnection:
        if self._connection is None or self._connection.closed:
            self._connection = await psycopg.AsyncConnection.connect(self.url, autocommit=True)
        return self._connection

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()

    async def setup(self, now: datetime) -> None:
        """Create missing tables and close alarms left open by a previous run."""
        schema = resources.files(__package__).joinpath("schema.sql").read_text("utf-8")
        async with self._lock:
            connection = await self._connect()
            async with connection.transaction():
                await connection.execute(schema)
                await connection.execute(
                    "UPDATE alarm SET cleared_at = %s WHERE cleared_at IS NULL", (now,)
                )

    async def write(self, batch: Batch) -> None:
        async with self._lock:
            connection = await self._connect()
            async with connection.transaction(), connection.cursor() as cursor:
                if batch.samples:
                    async with cursor.copy(
                        "COPY telemetry_sample (time, parameter, value) FROM STDIN"
                    ) as copy:
                        for s in batch.samples:
                            await copy.write_row((s.time, s.parameter, s.value))
                    await self._notify(cursor, self._latest(batch))
                for e in batch.log:
                    await cursor.execute(
                        "INSERT INTO packet_log"
                        " (time, direction, service, subservice, sequence, valid, detail)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (e.time, e.direction, e.service, e.subservice, e.sequence, e.valid,
                         e.detail),
                    )  # fmt: skip
                for a in batch.alarms:
                    if a.raised:
                        await cursor.execute(
                            "INSERT INTO alarm (parameter, bound, value, raised_at)"
                            " VALUES (%s, %s, %s, %s)",
                            (a.parameter, a.bound, a.value, a.time),
                        )
                    else:
                        await cursor.execute(
                            "UPDATE alarm SET cleared_at = %s"
                            " WHERE parameter = %s AND bound = %s AND cleared_at IS NULL",
                            (a.time, a.parameter, a.bound),
                        )
                    await self._notify(
                        cursor,
                        {"type": "alarm", "parameter": a.parameter, "bound": a.bound,
                         "raised": a.raised, "time": a.time.isoformat()},
                    )  # fmt: skip
                for c in batch.commands:
                    # the sequence count wraps, so only the newest unfinished command can match
                    await cursor.execute(
                        "UPDATE command SET status = %s, error = %s, updated_at = %s"
                        " WHERE id = (SELECT id FROM command WHERE request_id = %s"
                        "   AND status IN ('sent', 'accepted') ORDER BY id DESC LIMIT 1)"
                        " RETURNING id",
                        (c.status, c.error, c.time, c.request_id),
                    )
                    if row := await cursor.fetchone():
                        await self._notify(
                            cursor,
                            {"type": "command", "id": row[0], "status": c.status,
                             "error": c.error},
                        )  # fmt: skip
                for name, amount in batch.counters.items():
                    await cursor.execute(
                        "INSERT INTO link_counter (name, value) VALUES (%s, %s)"
                        " ON CONFLICT (name) DO UPDATE"
                        " SET value = link_counter.value + EXCLUDED.value",
                        (name, amount),
                    )

    async def add_command(self, sent_at: datetime, request_id: bytes, name: str, args: dict) -> int:
        async with self._lock:
            connection = await self._connect()
            async with connection.transaction(), connection.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO command (sent_at, request_id, name, args)"
                    " VALUES (%s, %s, %s, %s) RETURNING id",
                    (sent_at, request_id, name, Jsonb(args)),
                )
                command_id = (await cursor.fetchone())[0]
                await self._notify(
                    cursor, {"type": "command", "id": command_id, "status": "sent", "error": None}
                )
            return command_id

    async def prune(self, now: datetime, keep: timedelta) -> None:
        async with self._lock:
            connection = await self._connect()
            cutoff = now - keep
            async with connection.transaction():
                await connection.execute("DELETE FROM telemetry_sample WHERE time < %s", (cutoff,))
                await connection.execute("DELETE FROM packet_log WHERE time < %s", (cutoff,))
                await connection.execute("DELETE FROM command WHERE sent_at < %s", (cutoff,))
                await connection.execute("DELETE FROM alarm WHERE cleared_at < %s", (cutoff,))

    @staticmethod
    def _latest(batch: Batch) -> dict:
        newest = batch.samples[-1].time
        values = {s.parameter: _finite(s.value) for s in batch.samples if s.time == newest}
        return {"type": "telemetry", "time": newest.isoformat(), "values": values}

    @staticmethod
    async def _notify(cursor, payload: dict) -> None:
        await cursor.execute("SELECT pg_notify(%s, %s)", (CHANNEL, json.dumps(payload)))
