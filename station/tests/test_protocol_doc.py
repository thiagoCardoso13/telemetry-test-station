"""The worked examples in docs/PROTOCOL.md must be what the code really produces."""

import re
from pathlib import Path

from station.protocol import Command, Housekeeping, encode, to_packet

DOC = Path(__file__).parents[2] / "docs" / "PROTOCOL.md"


def test_worked_examples_match_the_encoder():
    documented = re.findall(r"```text\n(.+)\n```", DOC.read_text("utf-8"))
    messages = [
        Command("set_valve", {"valve": "vent", "open": 1}),
        Housekeeping(
            {
                "tank_pressure": 2.5,
                "tank_temperature": 21.0,
                "fill_valve": 1,
                "vent_valve": 0,
                "relief_valve": 0,
            }
        ),
    ]

    produced = [
        encode(to_packet(m, sequence=1, time_ms=1_700_000_000_000)).hex(" ") for m in messages
    ]

    assert documented == produced
