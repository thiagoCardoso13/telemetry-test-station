"""UDP front end: commands arrive on one port, all telemetry goes to one address."""

import asyncio
import logging
import time

from .device import Device

log = logging.getLogger(__name__)

PERIOD_S = 0.1


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


class _Link(asyncio.DatagramProtocol):
    def __init__(self, device: Device, destination: tuple[str, int]):
        self.device = device
        self.destination = destination
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.send(self.device.handle(data, _now_ms()))

    def error_received(self, exc):
        # Nobody listening yet is normal for UDP; telemetry keeps flowing.
        log.debug("udp error: %s", exc)

    def send(self, datagrams: list[bytes]) -> None:
        for datagram in datagrams:
            self.transport.sendto(datagram, self.destination)


async def serve(
    device: Device,
    listen: tuple[str, int],
    destination: tuple[str, int],
    *,
    period: float = PERIOD_S,
    ready: asyncio.Future | None = None,
) -> None:
    """Run until cancelled. `ready` receives the bound (host, port)."""
    loop = asyncio.get_running_loop()
    transport, link = await loop.create_datagram_endpoint(
        lambda: _Link(device, destination), local_addr=listen
    )
    if ready:
        ready.set_result(transport.get_extra_info("sockname"))
    try:
        deadline = loop.time()
        while True:
            # Fixed physics step, so a run depends on the seed and the commands, not on timing.
            link.send(device.tick(period, _now_ms()))
            deadline += period
            await asyncio.sleep(max(0.0, deadline - loop.time()))
    finally:
        transport.close()
