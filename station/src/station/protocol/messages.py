"""Payloads of each supported service, as typed messages."""

import struct
from dataclasses import dataclass
from enum import IntEnum

from .definitions import DEFINITIONS, TYPES, Function
from .errors import PayloadError, UnsupportedError
from .packet import Packet, PacketType

Number = int | float

_VERIFICATION_OK = struct.Struct(">4s")
_VERIFICATION_FAILED = struct.Struct(">4sB")
_EVENT = struct.Struct(">Hf")
_HOUSEKEEPING_ID = 1


class Stage(IntEnum):
    """Subservice of a successful report; the failed one is the next number."""

    ACCEPTANCE = 1
    COMPLETION = 7


@dataclass(frozen=True)
class Verification:  # service 1
    stage: Stage
    request_id: bytes
    error: int | None = None  # None means success


@dataclass(frozen=True)
class Housekeeping:  # service 3
    values: dict[str, Number]


@dataclass(frozen=True)
class EventReport:  # service 5
    name: str
    value: float = 0.0


@dataclass(frozen=True)
class Command:  # service 8; enum arguments are given by name
    name: str
    args: dict[str, Number | str]


@dataclass(frozen=True)
class Ping:  # TC(17,1)
    pass


@dataclass(frozen=True)
class Pong:  # TM(17,2)
    pass


Message = Verification | Housekeeping | EventReport | Command | Ping | Pong


def _pack(layout: struct.Struct, *values) -> bytes:
    try:
        return layout.pack(*values)
    except (struct.error, OverflowError) as error:
        raise PayloadError(f"value does not fit its type: {error}") from error


def _unpack(layout: struct.Struct, payload: bytes) -> tuple:
    if len(payload) != layout.size:
        raise PayloadError(f"expected {layout.size} payload bytes, got {len(payload)}")
    return layout.unpack(payload)


def _arguments_layout(function: Function) -> struct.Struct:
    return struct.Struct(">" + "".join(TYPES[a.type] for a in function.args))


def _encode_command(command: Command) -> bytes:
    function = next((f for f in DEFINITIONS.functions if f.name == command.name), None)
    if function is None:
        raise PayloadError(f"unknown function: {command.name}")
    if set(command.args) != {a.name for a in function.args}:
        raise PayloadError(f"wrong arguments for {function.name}: {sorted(command.args)}")

    values = []
    for argument in function.args:
        value = command.args[argument.name]
        if argument.enum:
            choices = DEFINITIONS.enums[argument.enum]
            if value not in choices:
                raise PayloadError(f"unknown {argument.enum}: {value}")
            value = choices[value]
        values.append(value)
    return bytes([function.id]) + _pack(_arguments_layout(function), *values)


def _decode_command(payload: bytes) -> Command:
    if not payload:
        raise PayloadError("missing function id")
    function = next((f for f in DEFINITIONS.functions if f.id == payload[0]), None)
    if function is None:
        raise PayloadError(f"unknown function id: {payload[0]}")

    args = {}
    values = _unpack(_arguments_layout(function), payload[1:])
    for argument, value in zip(function.args, values, strict=True):
        if argument.enum:
            names = {number: name for name, number in DEFINITIONS.enums[argument.enum].items()}
            if value not in names:
                raise PayloadError(f"unknown {argument.enum} number: {value}")
            value = names[value]
        args[argument.name] = value
    return Command(function.name, args)


def to_packet(message: Message, *, sequence: int, time_ms: int) -> Packet:
    packet_type = PacketType.TELEMETRY
    match message:
        case Verification(stage, request_id, error):
            service, subservice = 1, stage + (error is not None)
            if len(request_id) != 4:
                raise PayloadError("request id must be 4 bytes")
            if error is None:
                payload = _pack(_VERIFICATION_OK, request_id)
            else:
                payload = _pack(_VERIFICATION_FAILED, request_id, error)
        case Housekeeping(values):
            names = [p.name for p in DEFINITIONS.parameters]
            if set(values) != set(names):
                raise PayloadError("housekeeping needs every parameter exactly once")
            service, subservice = 3, 25
            payload = bytes([_HOUSEKEEPING_ID]) + _pack(
                DEFINITIONS.parameter_format, *(values[n] for n in names)
            )
        case EventReport(name, value):
            event = next((e for e in DEFINITIONS.events if e.name == name), None)
            if event is None:
                raise PayloadError(f"unknown event: {name}")
            service, subservice = 5, event.severity
            payload = _pack(_EVENT, event.id, value)
        case Command():
            packet_type = PacketType.TELECOMMAND
            service, subservice, payload = 8, 1, _encode_command(message)
        case Ping():
            packet_type = PacketType.TELECOMMAND
            service, subservice, payload = 17, 1, b""
        case Pong():
            service, subservice, payload = 17, 2, b""
        case _:
            raise TypeError(f"not a message: {message!r}")

    return Packet(packet_type, DEFINITIONS.apid, sequence, service, subservice, time_ms, payload)


def from_packet(packet: Packet) -> Message:
    """Interpret a decoded packet, or raise a PacketError."""
    if packet.apid != DEFINITIONS.apid:
        raise UnsupportedError(f"unknown APID: {packet.apid}")

    match packet.type, packet.service, packet.subservice:
        case PacketType.TELEMETRY, 1, 1 | 7:
            (request_id,) = _unpack(_VERIFICATION_OK, packet.payload)
            return Verification(Stage(packet.subservice), request_id)
        case PacketType.TELEMETRY, 1, 2 | 8:
            request_id, error = _unpack(_VERIFICATION_FAILED, packet.payload)
            return Verification(Stage(packet.subservice - 1), request_id, error)
        case PacketType.TELEMETRY, 3, 25:
            if packet.payload[:1] != bytes([_HOUSEKEEPING_ID]):
                raise PayloadError("unknown housekeeping structure")
            values = _unpack(DEFINITIONS.parameter_format, packet.payload[1:])
            names = (p.name for p in DEFINITIONS.parameters)
            return Housekeeping(dict(zip(names, values, strict=True)))
        case PacketType.TELEMETRY, 5, severity:
            event_id, value = _unpack(_EVENT, packet.payload)
            for event in DEFINITIONS.events:
                if event.id == event_id and event.severity == severity:
                    return EventReport(event.name, value)
            raise PayloadError(f"unknown event {event_id} with severity {severity}")
        case PacketType.TELECOMMAND, 8, 1:
            return _decode_command(packet.payload)
        case PacketType.TELECOMMAND, 17, 1:
            _unpack(struct.Struct(""), packet.payload)
            return Ping()
        case PacketType.TELEMETRY, 17, 2:
            _unpack(struct.Struct(""), packet.payload)
            return Pong()
    raise UnsupportedError(f"unsupported service ({packet.service},{packet.subservice})")
