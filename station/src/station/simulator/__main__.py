"""python -m station.simulator"""

import argparse
import asyncio
import logging

from station.addresses import address

from .device import Device
from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="station.simulator", description=__doc__)
    # Loopback by default: the link has no authentication.
    parser.add_argument("--listen", type=address, default=("127.0.0.1", 5001))
    parser.add_argument("--telemetry", type=address, default=("127.0.0.1", 5002))
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
