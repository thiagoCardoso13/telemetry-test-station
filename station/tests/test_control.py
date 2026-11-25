import asyncio

import psycopg
from aiohttp.test_utils import TestClient, TestServer

from station import protocol
from station.ingest.control import build_app


class FakeIngest:
    def __init__(self, error=None):
        self.sent = []
        self.error = error

    async def send_command(self, message):
        # encoding is what rejects a bad command in the real service
        protocol.to_packet(message, sequence=0, time_ms=0)
        if self.error:
            raise self.error
        self.sent.append(message)
        return len(self.sent)


def run(ingest, scenario):
    async def wrapped():
        async with TestClient(TestServer(build_app(ingest))) as client:
            await scenario(client)

    asyncio.run(asyncio.wait_for(wrapped(), timeout=10))


def test_commands_and_ping_are_forwarded():
    ingest = FakeIngest()

    async def scenario(client):
        valve = {"name": "set_valve", "args": {"valve": "fill", "open": 1}}
        first = await client.post("/commands", json=valve)
        second = await client.post("/commands", json={"name": "ping"})
        assert (first.status, await first.json()) == (202, {"id": 1})
        assert second.status == 202

    run(ingest, scenario)
    assert ingest.sent == [
        protocol.Command("set_valve", {"valve": "fill", "open": 1}),
        protocol.Ping(),
    ]


def test_malformed_commands_get_400_and_send_nothing():
    ingest = FakeIngest()
    bad = [
        [],
        {"name": 5},
        {"name": "set_valve", "args": []},
        {"name": "explode"},
        {"name": "set_valve", "args": {"valve": ["fill"], "open": 1}},
        {"name": "set_valve", "args": {"valve": "fill", "open": "yes"}},
        {"name": "inject_fault", "args": {"fault": "leak", "magnitude": 1e300}},
    ]

    async def scenario(client):
        for body in bad:
            assert (await client.post("/commands", json=body)).status == 400, body
        assert (await client.post("/commands", data=b"not json")).status == 400

    run(ingest, scenario)
    assert ingest.sent == []


def test_database_outage_is_503():
    async def scenario(client):
        assert (await client.post("/commands", json={"name": "reset"})).status == 503

    run(FakeIngest(psycopg.OperationalError("gone")), scenario)


def test_definitions_expose_limits():
    async def scenario(client):
        body = await (await client.get("/definitions")).json()
        pressure = body["parameters"][0]
        assert (pressure["name"], pressure["low"], pressure["high"]) == ("tank_pressure", 0.5, 8.0)
        assert body["enums"]["valve"] == {"fill": 1, "vent": 2}

    run(FakeIngest(), scenario)
