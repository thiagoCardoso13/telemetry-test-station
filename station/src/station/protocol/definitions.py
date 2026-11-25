"""Typed view of definitions.yaml."""

import struct
from dataclasses import dataclass
from importlib import resources

import yaml

# struct format characters, big-endian is applied by the user of the code
TYPES = {"uint8": "B", "uint16": "H", "float32": "f"}


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    enum: str | None = None
    unit: str | None = None
    low: float | None = None
    high: float | None = None


@dataclass(frozen=True)
class Function:
    id: int
    name: str
    args: tuple[Field, ...]


@dataclass(frozen=True)
class Event:
    id: int
    name: str
    severity: int


@dataclass(frozen=True)
class Definitions:
    apid: int
    parameters: tuple[Field, ...]
    enums: dict[str, dict[str, int]]
    functions: tuple[Function, ...]
    events: tuple[Event, ...]

    @property
    def parameter_format(self) -> struct.Struct:
        return struct.Struct(">" + "".join(TYPES[p.type] for p in self.parameters))


def load() -> Definitions:
    text = resources.files(__package__).joinpath("definitions.yaml").read_text("utf-8")
    raw = yaml.safe_load(text)
    return Definitions(
        apid=raw["apid"],
        parameters=tuple(Field(**p) for p in raw["parameters"]),
        enums=raw["enums"],
        functions=tuple(
            Function(f["id"], f["name"], tuple(Field(**a) for a in f["args"]))
            for f in raw["functions"]
        ),
        events=tuple(Event(**e) for e in raw["events"]),
    )


DEFINITIONS = load()
