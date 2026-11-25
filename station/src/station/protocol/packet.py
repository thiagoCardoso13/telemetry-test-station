"""Packet framing: primary header, secondary header, payload and CRC."""

import binascii
import struct
from dataclasses import dataclass
from enum import IntEnum

from .errors import CrcError, LengthError, TooShortError, UnsupportedError

_PRIMARY = struct.Struct(">HHH")
_SECONDARY = struct.Struct(">BBQ")
_CRC = struct.Struct(">H")

MIN_LENGTH = _PRIMARY.size + _SECONDARY.size + _CRC.size
# The length field holds "bytes after the primary header, minus one" in 16 bits.
MAX_PAYLOAD = 0x10000 - _SECONDARY.size - _CRC.size
MAX_SEQUENCE = 0x3FFF
MAX_APID = 0x7FF
_UNSEGMENTED = 0b11


class PacketType(IntEnum):
    TELEMETRY = 0
    TELECOMMAND = 1


@dataclass(frozen=True)
class Packet:
    type: PacketType
    apid: int
    sequence: int
    service: int
    subservice: int
    time_ms: int
    payload: bytes = b""

    @property
    def request_id(self) -> bytes:
        """First four header bytes, used by verification reports to name a command."""
        return encode(self)[:4]


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: polynomial 0x1021, initial value 0xFFFF."""
    return binascii.crc_hqx(data, 0xFFFF)


def encode(packet: Packet) -> bytes:
    if not 0 <= packet.apid <= MAX_APID:
        raise ValueError(f"APID out of range: {packet.apid}")
    if not 0 <= packet.sequence <= MAX_SEQUENCE:
        raise ValueError(f"sequence count out of range: {packet.sequence}")
    if len(packet.payload) > MAX_PAYLOAD:
        raise ValueError(f"payload too long: {len(packet.payload)} bytes")

    # version 000, type, secondary header flag 1, APID
    identification = (packet.type << 12) | (1 << 11) | packet.apid
    sequence_control = (_UNSEGMENTED << 14) | packet.sequence
    data_length = _SECONDARY.size + len(packet.payload) + _CRC.size - 1

    body = (
        _PRIMARY.pack(identification, sequence_control, data_length)
        + _SECONDARY.pack(packet.service, packet.subservice, packet.time_ms)
        + packet.payload
    )
    return body + _CRC.pack(crc16(body))


def decode(data: bytes) -> Packet:
    """Decode exactly one packet, or raise a PacketError."""
    if len(data) < MIN_LENGTH:
        raise TooShortError(f"{len(data)} bytes, need at least {MIN_LENGTH}")

    identification, sequence_control, data_length = _PRIMARY.unpack_from(data)
    expected = _PRIMARY.size + data_length + 1
    if len(data) != expected:
        raise LengthError(f"header says {expected} bytes, got {len(data)}")

    (received,) = _CRC.unpack_from(data, len(data) - _CRC.size)
    if received != crc16(data[: -_CRC.size]):
        raise CrcError("checksum does not match")

    if identification >> 13 != 0:
        raise UnsupportedError("unknown packet version")
    if not identification & (1 << 11):
        raise UnsupportedError("secondary header is required")
    if sequence_control >> 14 != _UNSEGMENTED:
        raise UnsupportedError("segmented packets are not supported")

    service, subservice, time_ms = _SECONDARY.unpack_from(data, _PRIMARY.size)
    return Packet(
        type=PacketType((identification >> 12) & 1),
        apid=identification & MAX_APID,
        sequence=sequence_control & MAX_SEQUENCE,
        service=service,
        subservice=subservice,
        time_ms=time_ms,
        payload=bytes(data[_PRIMARY.size + _SECONDARY.size : -_CRC.size]),
    )
