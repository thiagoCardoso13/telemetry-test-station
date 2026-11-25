"""python -m station.runner: run the test sequences and report per requirement.

Exit code: 0 everything run passed, 1 something failed, 2 the bench did not work.
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import report
from .bench import BenchError, LiveBench, SimulatedBench
from .engine import run
from .model import load_requirements, load_sequences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="station.runner", description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="use the running station (needs DATABASE_URL) instead of an in-process simulation",
    )
    parser.add_argument("--control", default="http://127.0.0.1:5003", help="ingest, with --live")
    parser.add_argument(
        "--include-faults",
        action="store_true",
        help="also run the sequences that break the tank on purpose and are meant to fail",
    )
    parser.add_argument("--report", type=Path, help="write the HTML report to this file")
    args = parser.parse_args(argv)

    requirements = load_requirements()
    sequences = load_sequences(requirements, include_faults=args.include_faults)
    try:
        if args.live:
            url = os.environ.get("DATABASE_URL")
            if not url:
                parser.error("--live needs DATABASE_URL")
            bench = LiveBench(args.control, url)
        else:
            bench = SimulatedBench()
        results = run(bench, sequences)
    except BenchError as error:
        print(f"bench error: {error}", file=sys.stderr)
        return 2

    print(report.text(requirements, results))
    if args.report:
        name = "running station" if args.live else "in-process simulation"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            report.html(requirements, results, bench=name, created=datetime.now(UTC)), "utf-8"
        )
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
