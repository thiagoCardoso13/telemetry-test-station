"""Link protocol: a documented subset inspired by CCSDS Space Packets and ECSS PUS."""

from .definitions import DEFINITIONS
from .errors import (
    CrcError,
    LengthError,
    PacketError,
    PayloadError,
    TooShortError,
    UnsupportedError,
)
from .messages import (
    Command,
    EventReport,
    Housekeeping,
    Message,
    Ping,
    Pong,
    Stage,
    Verification,
    from_packet,
    to_packet,
)
from .packet import MAX_SEQUENCE, Packet, PacketType, crc16, decode, encode

__all__ = [
    "DEFINITIONS",
    "MAX_SEQUENCE",
    "Command",
    "CrcError",
    "EventReport",
    "Housekeeping",
    "LengthError",
    "Message",
    "Packet",
    "PacketError",
    "PacketType",
    "PayloadError",
    "Ping",
    "Pong",
    "Stage",
    "TooShortError",
    "UnsupportedError",
    "Verification",
    "crc16",
    "decode",
    "encode",
    "from_packet",
    "to_packet",
]
