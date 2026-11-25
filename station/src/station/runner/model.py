"""Requirements and sequences, loaded from YAML and checked before anything runs."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from station import protocol

from .conditions import Condition, parse

SUITE = Path(__file__).parent / "suite"

# keys allowed besides the one that names the step: (required, optional)
_KEYS = {
    "command": ((), ("args", "expect", "requirement")),
    "inject_fault": ((), ()),
    "wait": ((), ()),
    "wait_for": (("timeout",), ("requirement",)),
    "check": (("requirement",), ()),
    "always": (("for", "requirement"), ()),
    "response": (("requirement",), ()),
}
_RESPONSE_KEYS = ({"when", "then", "within"}, {"after"})


@dataclass(frozen=True)
class Step:
    kind: str
    description: str
    requirement: str | None = None
    condition: Condition | None = None
    after: Condition | None = None
    when: Condition | None = None
    seconds: float = 0.0
    command: str = ""
    args: dict = field(default_factory=dict)
    expect: str = "completed"


@dataclass(frozen=True)
class Sequence:
    name: str
    title: str
    steps: tuple[Step, ...]


def load_requirements(path: Path = SUITE / "requirements.yaml") -> dict[str, str]:
    return yaml.safe_load(path.read_text("utf-8"))


def _check_keys(where: str, given: set, required: set, optional: set) -> None:
    if missing := required - given:
        raise ValueError(f"{where}: missing {sorted(missing)}")
    if unknown := given - required - optional:
        raise ValueError(f"{where}: unknown {sorted(unknown)}")


def _command(name: str, args: dict) -> None:
    """Fail at load time on a command the protocol could not encode."""
    message = protocol.Ping() if name == "ping" else protocol.Command(name, args)
    protocol.to_packet(message, sequence=0, time_ms=0)


def _step(raw: dict, where: str, requirements: dict[str, str]) -> Step:
    kinds = [k for k in _KEYS if k in raw]
    if len(kinds) != 1:
        raise ValueError(f"{where}: a step needs exactly one of {sorted(_KEYS)}")
    kind = kinds[0]
    required, optional = _KEYS[kind]
    _check_keys(where, set(raw) - {kind}, set(required), set(optional))
    requirement = raw.get("requirement")
    if requirement is not None and requirement not in requirements:
        raise ValueError(f"{where}: unknown requirement {requirement}")
    value = raw[kind]

    match kind:
        case "command":
            args, expect = raw.get("args", {}), raw.get("expect", "completed")
            if expect not in ("completed", "failed", "rejected"):
                raise ValueError(f"{where}: unknown expectation {expect!r}")
            _command(value, args)
            shown = " ".join(f"{k}={v}" for k, v in args.items())
            text = f"command {value} {shown}".strip() + f", expect {expect}"
            return Step(kind, text, requirement, command=value, args=args, expect=expect)
        case "inject_fault":
            _command("inject_fault", value)
            text = f"inject {value['fault']} {value['magnitude']}"
            return Step("command", text, command="inject_fault", args=value)
        case "wait":
            return Step(kind, f"wait {value} s", seconds=float(value))
        case "wait_for":
            timeout = float(raw["timeout"])
            text = f"wait up to {raw['timeout']} s for {value}"
            return Step(kind, text, requirement, parse(value), seconds=timeout)
        case "check":
            return Step(kind, f"check {value}", requirement, parse(value))
        case "always":
            text = f"{value} for {raw['for']} s"
            return Step(kind, text, requirement, parse(value), seconds=float(raw["for"]))
        case "response":
            _check_keys(where, set(value), *_RESPONSE_KEYS)
            after = parse(value["after"]) if "after" in value else None
            text = f"{value['then']} within {value['within']} s of {value['when']}"
            if after:
                text += f" (after {after.text})"
            return Step(
                kind,
                text,
                requirement,
                parse(value["then"]),
                after=after,
                when=parse(value["when"]),
                seconds=float(value["within"]),
            )


def load_sequence(path: Path, requirements: dict[str, str]) -> Sequence:
    raw = yaml.safe_load(path.read_text("utf-8"))
    _check_keys(path.name, set(raw), {"title", "steps"}, set())
    steps = tuple(
        _step(step, f"{path.name} step {number}", requirements)
        for number, step in enumerate(raw["steps"], 1)
    )
    return Sequence(path.stem, raw["title"], steps)


def load_sequences(requirements: dict[str, str], *, include_faults: bool = False) -> list[Sequence]:
    folders = ["sequences", "faults"] if include_faults else ["sequences"]
    return [
        load_sequence(path, requirements)
        for folder in folders
        for path in sorted((SUITE / folder).glob("*.yaml"))
    ]
