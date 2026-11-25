"""The runner against ingest, simulator and PostgreSQL, in real time."""

import asyncio
import os

import pytest
from test_ingest_db import empty_database, eventually, station  # noqa: F401

from station.ingest.control import serve_control
from station.runner import report
from station.runner.bench import BenchError, LiveBench
from station.runner.engine import run
from station.runner.model import load_requirements, load_sequences

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is not set")


def test_sequences_pass_on_the_running_station():
    requirements = load_requirements()
    sequences = [
        s
        for s in load_sequences(requirements)
        if s.name in ("03_low_pressure_alarm", "04_stuck_vent")
    ]

    async def scenario():
        # the simulator in station() runs 10 ms periods; slow it to the real 100 ms
        async with station(period=0.1) as (ingest, _):
            control = await serve_control(ingest, "127.0.0.1", 0)
            port = control.addresses[0][1]
            try:
                await eventually("SELECT 1 FROM telemetry_sample")

                def work():
                    bench = LiveBench(f"http://127.0.0.1:{port}", URL)
                    try:
                        return run(bench, sequences)
                    finally:
                        bench.close()

                return await asyncio.to_thread(work)
            finally:
                await control.cleanup()

    results = asyncio.run(asyncio.wait_for(scenario(), timeout=60))

    assert all(r.passed for r in results), report.text(requirements, results)


def test_a_station_without_telemetry_is_a_bench_error_not_a_verdict():
    async def scenario():
        async with station() as _:
            await eventually("SELECT 1 FROM telemetry_sample")

    asyncio.run(asyncio.wait_for(scenario(), timeout=20))
    # station stopped: the table has old rows, so the bench connects but sees nothing new
    bench = LiveBench("http://127.0.0.1:9", URL)
    try:
        with pytest.raises(BenchError):
            bench.wait(1)
        with pytest.raises(BenchError):
            bench.send("reset", {})
    finally:
        bench.close()
