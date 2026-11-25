"""Ingest against a real PostgreSQL and the real simulator, over loopback UDP.

Needs TEST_DATABASE_URL pointing to a database that may be wiped.
"""

import asyncio
import contextlib
import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from station import protocol
from station.ingest import CHANNEL, Ingest, Store
from station.simulator import Device, serve

URL = os.environ.get("TEST_DATABASE_URL")
if not URL and os.environ.get("CI"):
    raise RuntimeError("CI must provide TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is not set")


@pytest.fixture(autouse=True)
def empty_database():
    with psycopg.connect(URL, autocommit=True) as connection:
        connection.execute(
            "DROP TABLE IF EXISTS telemetry_sample, packet_log, command, alarm, link_counter"
        )


def query(sql, *parameters):
    with psycopg.connect(URL) as connection:
        return connection.execute(sql, parameters).fetchall()


async def eventually(sql, *parameters):
    """Poll until the query returns rows."""
    while True:
        if rows := await asyncio.to_thread(query, sql, *parameters):
            return rows
        await asyncio.sleep(0.02)


async def stop(*tasks):
    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@contextlib.asynccontextmanager
async def station(**options):
    """Ingest and simulator wired to each other on free ports."""
    loop = asyncio.get_running_loop()
    ingest = Ingest(Store(URL), ("127.0.0.1", 0), **options)
    ready = loop.create_future()
    ingest_task = asyncio.create_task(ingest.run(("127.0.0.1", 0), ready))
    ingest_address = await ready
    ready = loop.create_future()
    simulator_task = asyncio.create_task(
        serve(Device(), ("127.0.0.1", 0), ingest_address, period=0.01, ready=ready)
    )
    ingest.simulator = await ready
    try:
        yield ingest, ingest_address
    finally:
        await stop(simulator_task, ingest_task)


def run(scenario):
    asyncio.run(asyncio.wait_for(scenario(), timeout=20))


def test_telemetry_is_stored_and_announced():
    async def scenario():
        async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as listener:
            await listener.execute(f"LISTEN {CHANNEL}")
            async with station():
                notice = await anext(listener.notifies())
                await eventually("SELECT 1 FROM telemetry_sample WHERE parameter='tank_pressure'")
        assert '"type": "telemetry"' in notice.payload

    run(scenario)


def test_command_is_followed_to_completion_and_raises_an_alarm():
    async def scenario():
        async with station() as (ingest, _):
            leak = protocol.Command("inject_fault", {"fault": "leak", "magnitude": 1.0})
            command_id = await ingest.send_command(leak)
            await eventually("SELECT 1 FROM command WHERE id=%s AND status='completed'", command_id)
            # the leak at 1/s takes 2 bar below 0.5 in about 1.4 simulated seconds
            await eventually("SELECT 1 FROM alarm WHERE bound='low' AND cleared_at IS NULL")

            await ingest.send_command(protocol.Command("reset", {}))
            await eventually("SELECT 1 FROM alarm WHERE cleared_at IS NOT NULL")

    run(scenario)


def test_bad_datagrams_and_losses_are_counted_and_ingest_keeps_going():
    async def scenario():
        async with station() as (ingest, address):
            loop = asyncio.get_running_loop()
            transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol, remote_addr=address
            )
            transport.sendto(b"not a packet")
            rows = await eventually(
                "SELECT value FROM link_counter WHERE name='rejected_too_short'"
            )
            assert rows == [(1,)]
            ingest.datagram_received(
                protocol.encode(
                    protocol.to_packet(protocol.Pong(), sequence=8_000, time_ms=10**13)
                ),
                None,
            )
            await eventually("SELECT 1 FROM link_counter WHERE name='lost' AND value > 0")
            transport.close()

    run(scenario)


def test_a_database_outage_is_survived(monkeypatch):
    original = Store.write
    failures = []

    async def flaky(self, batch):
        if len(failures) < 3:
            failures.append(batch)
            raise psycopg.OperationalError("gone")
        await original(self, batch)

    monkeypatch.setattr(Store, "write", flaky)

    async def scenario():
        async with station(retry_after=0.01):
            await eventually("SELECT 1 FROM telemetry_sample")
        assert failures[0] is failures[2]

    run(scenario)


def test_old_rows_are_pruned_and_stale_alarms_closed():
    async def scenario():
        store = Store(URL)
        now = datetime.now(UTC)
        await store.setup(now)
        with psycopg.connect(URL, autocommit=True) as connection:
            connection.execute(
                "INSERT INTO telemetry_sample VALUES (%s, 'x', 1), (%s, 'x', 2)",
                (now - timedelta(hours=2), now),
            )
            connection.execute(
                "INSERT INTO alarm (parameter, bound, value, raised_at) VALUES ('x','low',0,%s)",
                (now,),
            )

        await store.prune(now, timedelta(hours=1))
        await store.setup(now)
        await store.close()

        assert query("SELECT value FROM telemetry_sample") == [(2.0,)]
        assert query("SELECT count(*) FROM alarm WHERE cleared_at IS NULL") == [(0,)]

    run(scenario)
