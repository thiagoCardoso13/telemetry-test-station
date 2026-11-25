"""python -m station.simulator"""

import argparse
import asyncio
import logging

from .device import Device
from .server import serve


def _address(text: str) -> tuple[str, int]:
    host, _, port = text.rpartition(":")
    if not host or not port.isdigit():
        raise argparse.ArgumentTypeError(f"expected host:port, got {text!r}")
    return host, int(port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="station.simulator", description=__doc__)
    # Loopback by default: the link has no authentication.
    parser.add_argument("--listen", type=_address, default=("127.0.0.1", 5001))
    parser.add_argument("--telemetry", type=_address, default=("127.0.0.1", 5002))
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.info("commands on %s:%d, telemetry to %s:%d", *args.listen, *args.telemetry)
    try:
        asyncio.run(serve(Device(args.seed), args.listen, args.telemetry))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
