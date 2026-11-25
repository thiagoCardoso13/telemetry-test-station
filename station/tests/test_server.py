"""The simulator over real UDP sockets on loopback."""

import asyncio
import contextlib
import socket

from station import protocol
from station.simulator import Device, serve


def test_telemetry_flows_and_commands_are_answered_over_udp():
    async def scenario():
        loop = asyncio.get_running_loop()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as ground:
            ground.bind(("127.0.0.1", 0))
            ground.setblocking(False)
            ready = loop.create_future()
            task = asyncio.create_task(
                serve(
                    Device(),
                    ("127.0.0.1", 0),
                    ground.getsockname(),
                    period=0.01,
                    ready=ready,
                )
            )

            async def receive_until(kind):
                while True:
                    data = await loop.sock_recv(ground, 2048)
                    message = protocol.from_packet(protocol.decode(data))
                    if isinstance(message, kind):
                        return message

            try:
                address = await ready
                await receive_until(protocol.Housekeeping)
                ping = protocol.to_packet(protocol.Ping(), sequence=1, time_ms=0)
                ground.sendto(protocol.encode(ping), address)
                await receive_until(protocol.Pong)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    asyncio.run(asyncio.wait_for(scenario(), timeout=5))
