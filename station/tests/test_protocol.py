import random

import pytest

from station.protocol import (
    DEFINITIONS,
    MAX_SEQUENCE,
    Command,
    CrcError,
    EventReport,
    Housekeeping,
    LengthError,
    Packet,
    PacketError,
    PacketType,
    PayloadError,
    Ping,
    Pong,
    Stage,
    TooShortError,
    UnsupportedError,
    Verification,
    crc16,
    decode,
    encode,
    from_packet,
    to_packet,
)

HOUSEKEEPING = Housekeeping(
    {
        "tank_pressure": 2.5,
        "tank_temperature": 21.0,
        "fill_valve": 1,
        "vent_valve": 0,
        "relief_valve": 0,
    }
)

MESSAGES = [
    Verification(Stage.ACCEPTANCE, b"\x18\x64\xc0\x01"),
    Verification(Stage.COMPLETION, b"\x18\x64\xc0\x01"),
    Verification(Stage.ACCEPTANCE, b"\x18\x64\xc0\x01", error=2),
    Verification(Stage.COMPLETION, b"\x18\x64\xc0\x01", error=3),
    HOUSEKEEPING,
    EventReport("relief_valve_opened", 8.5),
    Command("set_valve", {"valve": "vent", "open": 1}),
    Command("inject_fault", {"fault": "leak", "magnitude": 0.5}),
    Command("clear_faults", {}),
    Command("reset", {}),
    Ping(),
    Pong(),
]


def frame(message=HOUSEKEEPING, sequence=1) -> bytes:
    return encode(to_packet(message, sequence=sequence, time_ms=1_700_000_000_000))


def with_crc(body: bytes) -> bytes:
    return body + crc16(body).to_bytes(2, "big")


def test_crc_matches_the_published_check_value():
    assert crc16(b"123456789") == 0x29B1


@pytest.mark.parametrize("message", MESSAGES, ids=lambda m: type(m).__name__)
def test_every_message_survives_a_round_trip(message):
    assert from_packet(decode(frame(message))) == message


@pytest.mark.parametrize("sequence", [0, 1, MAX_SEQUENCE])
def test_header_fields_survive_a_round_trip(sequence):
    packet = Packet(PacketType.TELECOMMAND, 0x7FF, sequence, 17, 1, 2**64 - 1, b"abc")

    assert decode(encode(packet)) == packet


@pytest.mark.parametrize(
    "changes", [{"apid": 0x800}, {"sequence": MAX_SEQUENCE + 1}, {"payload": bytes(70_000)}]
)
def test_encoding_refuses_values_that_do_not_fit(changes):
    fields = {"apid": 1, "sequence": 1, "payload": b""} | changes

    with pytest.raises(ValueError):
        encode(Packet(PacketType.TELEMETRY, service=3, subservice=25, time_ms=0, **fields))


def test_any_single_flipped_bit_is_rejected():
    original = frame()
    for position in range(len(original) * 8):
        corrupted = bytearray(original)
        corrupted[position // 8] ^= 0x80 >> (position % 8)
        with pytest.raises(PacketError):
            decode(bytes(corrupted))


def test_flipped_payload_bit_is_reported_as_bad_crc():
    corrupted = bytearray(frame())
    corrupted[-5] ^= 0x01

    with pytest.raises(CrcError):
        decode(bytes(corrupted))


def test_truncated_and_padded_packets_are_rejected():
    original = frame()

    with pytest.raises(TooShortError):
        decode(original[:10])
    with pytest.raises(LengthError):
        decode(original[:-1])
    with pytest.raises(LengthError):
        decode(original + b"\x00")


def test_unsupported_header_with_a_valid_crc_is_rejected():
    body = bytearray(frame()[:-2])
    body[0] |= 0b0010_0000  # version 1

    with pytest.raises(UnsupportedError):
        decode(with_crc(bytes(body)))


def test_random_bytes_only_ever_raise_packet_errors():
    generator = random.Random(42)
    for _ in range(5_000):
        junk = generator.randbytes(generator.randrange(64))
        with pytest.raises(PacketError):
            from_packet(decode(junk))


def test_random_payloads_never_crash_the_interpreter_of_messages():
    generator = random.Random(7)
    for _ in range(5_000):
        packet = Packet(
            type=generator.choice(list(PacketType)),
            apid=DEFINITIONS.apid,
            sequence=0,
            service=generator.choice([1, 3, 5, 8, 17]),
            subservice=generator.choice([1, 2, 7, 8, 25]),
            time_ms=0,
            payload=generator.randbytes(generator.randrange(20)),
        )
        try:
            from_packet(packet)
        except PacketError:
            pass


def test_unknown_apid_is_rejected():
    packet = Packet(PacketType.TELECOMMAND, 5, 0, 17, 1, 0)

    with pytest.raises(UnsupportedError):
        from_packet(packet)


@pytest.mark.parametrize(
    "command",
    [
        Command("self_destruct", {}),
        Command("set_valve", {"valve": "vent"}),
        Command("set_valve", {"valve": "main", "open": 1}),
        Command("set_valve", {"valve": "vent", "open": 300}),
    ],
)
def test_invalid_commands_cannot_be_encoded(command):
    with pytest.raises(PayloadError):
        to_packet(command, sequence=0, time_ms=0)


def test_request_id_names_the_command_by_its_first_four_bytes():
    packet = to_packet(Ping(), sequence=9, time_ms=0)

    assert packet.request_id == encode(packet)[:4]
