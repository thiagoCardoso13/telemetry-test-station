"""The only process that talks to the equipment: receives telemetry and sends commands."""

import asyncio
import contextlib
import logging
from collections import deque
from datetime import UTC, datetime, timedelta

import psycopg

from station import protocol

from .processor import Processor
from .records import Batch, LogEntry
from .store import Store

log = logging.getLogger(__name__)

# datagrams held while the database is slow or away: about 100 s of telemetry
QUEUE_LIMIT = 1_000
MAX_BATCH = 200


def _now() -> datetime:
    return datetime.now(UTC)


class Ingest(asyncio.DatagramProtocol):
    def __init__(
        self,
        store: Store,
        simulator: tuple[str, int],
        *,
        keep: timedelta = timedelta(hours=1),
        prune_every: float = 60.0,
        retry_after: float = 1.0,
        queue_limit: int = QUEUE_LIMIT,
    ):
        self.store = store
        self.simulator = simulator
        self.keep = keep
        self.prune_every = prune_every
        self.retry_after = retry_after
        self.processor = Processor()
        self._queue: deque[tuple[bytes, datetime]] = deque()
        self._queue_limit = queue_limit
        self._arrived = asyncio.Event()
        self._dropped = 0
        self._transport: asyncio.DatagramTransport | None = None
        self._sequence = 0

    # network side

    def connection_made(self, transport):
        self._transport = transport

    def datagram_received(self, data, addr):
        if len(self._queue) >= self._queue_limit:
            self._dropped += 1
        else:
            self._queue.append((data, _now()))
        self._arrived.set()

    def error_received(self, exc):
        log.debug("udp error: %s", exc)

    async def send_command(self, message: protocol.Command | protocol.Ping) -> int:
        """Record and send one command; its status follows from the reports that come back."""
        now = _now()
        packet = protocol.to_packet(
            message, sequence=self._sequence, time_ms=int(now.timestamp() * 1000)
        )
        self._sequence = (self._sequence + 1) % (protocol.MAX_SEQUENCE + 1)
        name, args = (
            (message.name, message.args) if isinstance(message, protocol.Command) else ("ping", {})
        )
        # stored before sending, so the reply always finds it
        command_id = await self.store.add_command(now, packet.request_id, name, args)
        self._transport.sendto(protocol.encode(packet), self.simulator)
        return command_id

    # database side

    def _next_batch(self) -> Batch:
        batch = Batch()
        for _ in range(min(len(self._queue), MAX_BATCH)):
            self.processor.process(*self._queue.popleft(), batch)
        if self._dropped:
            batch.counters["dropped"] += self._dropped
            batch.log.append(
                LogEntry(_now(), "in", False, f"dropped: {self._dropped} datagrams, queue full")
            )
            self._dropped = 0
        return batch

    async def _persist(self, batch: Batch) -> None:
        # Retrying the same batch keeps the alarm table in step with the alarm monitor.
        while True:
            try:
                return await self.store.write(batch)
            except psycopg.OperationalError as error:
                log.warning("database unavailable, retrying: %s", error)
                await asyncio.sleep(self.retry_after)

    async def _write_loop(self) -> None:
        while True:
            await self._arrived.wait()
            self._arrived.clear()
            while self._queue or self._dropped:
                await self._persist(self._next_batch())

    async def _prune_loop(self) -> None:
        while True:
            try:
                await self.store.prune(_now(), self.keep)
            except psycopg.OperationalError as error:
                log.warning("could not prune: %s", error)
            await asyncio.sleep(self.prune_every)

    async def run(self, listen: tuple[str, int], ready: asyncio.Future | None = None) -> None:
        """Run until cancelled. `ready` receives the bound (host, port)."""
        await self.store.setup(_now())
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(lambda: self, local_addr=listen)
        if ready:
            ready.set_result(transport.get_extra_info("sockname"))
        try:
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(self._write_loop())
                tasks.create_task(self._prune_loop())
        finally:
            transport.close()
            with contextlib.suppress(psycopg.Error):
                await self.store.close()
