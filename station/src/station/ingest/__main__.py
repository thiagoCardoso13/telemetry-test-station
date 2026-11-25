"""python -m station.ingest (the database comes from the DATABASE_URL variable)"""

import argparse
import asyncio
import logging
import os
from datetime import timedelta

from station.addresses import address

from .service import Ingest
from .store import Store


def main() -> None:
    parser = argparse.ArgumentParser(prog="station.ingest", description=__doc__)
    parser.add_argument("--listen", type=address, default=("127.0.0.1", 5002))
    parser.add_argument("--simulator", type=address, default=("127.0.0.1", 5001))
    parser.add_argument("--keep-minutes", type=int, default=60)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("set DATABASE_URL, e.g. postgresql://user:password@localhost:5432/station")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.info("telemetry on %s:%d, commands to %s:%d", *args.listen, *args.simulator)

    async def run() -> None:
        ingest = Ingest(Store(url), args.simulator, keep=timedelta(minutes=args.keep_minutes))
        await ingest.run(args.listen)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
