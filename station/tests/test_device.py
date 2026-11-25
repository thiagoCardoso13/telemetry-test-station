from station import protocol
from station.protocol import Command, EventReport, Housekeeping, Ping, Pong, Stage, Verification
from station.simulator import Device, ErrorCode

NOW = 1_700_000_000_000


def command(message, sequence=1) -> bytes:
    return protocol.encode(protocol.to_packet(message, sequence=sequence, time_ms=NOW))


def messages(datagrams):
    return [protocol.from_packet(protocol.decode(d)) for d in datagrams]


def raw_command(service, subservice, payload=b"", apid=protocol.DEFINITIONS.apid) -> bytes:
    kind = protocol.PacketType.TELECOMMAND
    return protocol.encode(protocol.Packet(kind, apid, 3, service, subservice, NOW, payload))


def pressure(device, seconds=1.0) -> float:
    for _ in range(round(seconds * 10)):
        datagrams = device.tick(0.1, NOW)
    return messages(datagrams)[-1].values["tank_pressure"]


def test_a_command_visibly_changes_the_reported_pressure():
    device = Device()
    before = pressure(device)

    sent = command(Command("set_valve", {"valve": "fill", "open": 1}))
    reports = messages(device.handle(sent, NOW))

    assert reports == [
        Verification(Stage.ACCEPTANCE, sent[:4]),
        Verification(Stage.COMPLETION, sent[:4]),
    ]
    assert pressure(device) > before + 0.5


def test_ping_is_answered():
    sent = command(Ping())

    assert messages(Device().handle(sent, NOW)) == [
        Verification(Stage.ACCEPTANCE, sent[:4]),
        Pong(),
        Verification(Stage.COMPLETION, sent[:4]),
    ]


def test_injecting_a_fault_raises_an_event():
    sent = command(Command("inject_fault", {"fault": "leak", "magnitude": 0.5}))

    assert EventReport("fault_injected", 0.5) in messages(Device().handle(sent, NOW))


def test_relief_valve_event_comes_before_the_report_of_the_same_tick():
    device = Device()
    device.handle(command(Command("set_valve", {"valve": "fill", "open": 1})), NOW)

    for _ in range(600):
        sent = messages(device.tick(0.1, NOW))
        if len(sent) > 1:
            break

    assert isinstance(sent[0], EventReport) and sent[0].name == "relief_valve_opened"
    assert isinstance(sent[1], Housekeeping) and sent[1].values["relief_valve"] == 1


def failure(datagrams) -> tuple[Stage, int]:
    last = messages(datagrams)[-1]
    return last.stage, last.error


def test_moving_a_stuck_valve_fails_at_completion():
    device = Device()
    device.handle(command(Command("inject_fault", {"fault": "stuck_valve", "magnitude": 1})), NOW)

    reports = device.handle(command(Command("set_valve", {"valve": "fill", "open": 1})), NOW)

    assert failure(reports) == (Stage.COMPLETION, ErrorCode.VALVE_STUCK)


def test_bad_argument_values_fail_at_completion():
    device = Device()
    for bad in (
        Command("set_valve", {"valve": "fill", "open": 7}),
        Command("inject_fault", {"fault": "leak", "magnitude": 99.0}),
    ):
        reports = device.handle(command(bad), NOW)
        assert failure(reports) == (Stage.COMPLETION, ErrorCode.BAD_ARGUMENT)


def test_unreadable_commands_are_refused_at_acceptance():
    device = Device()

    unknown_function = device.handle(raw_command(8, 1, b"\xff"), NOW)
    unknown_service = device.handle(raw_command(99, 1), NOW)

    assert failure(unknown_function) == (Stage.ACCEPTANCE, ErrorCode.BAD_PAYLOAD)
    assert failure(unknown_service) == (Stage.ACCEPTANCE, ErrorCode.UNSUPPORTED)
    assert len(unknown_function) == len(unknown_service) == 1


def test_untrustworthy_datagrams_are_counted_and_not_answered():
    device = Device()
    damaged = bytearray(command(Ping()))
    damaged[-1] ^= 1

    assert device.handle(bytes(damaged), NOW) == []
    assert device.handle(b"hello", NOW) == []
    assert device.handle(raw_command(17, 1, apid=5), NOW) == []
    assert device.handle(device.tick(0.1, NOW)[0], NOW) == []
    assert device.rejected == {"bad_crc": 1, "too_short": 1, "wrong_apid": 1, "not_a_command": 1}


def test_sequence_count_increases_and_wraps():
    device = Device()
    device._sequence = protocol.MAX_SEQUENCE

    counts = [protocol.decode(device.tick(0.1, NOW)[0]).sequence for _ in range(3)]

    assert counts == [protocol.MAX_SEQUENCE, 0, 1]


def test_a_faulty_run_is_reproducible_byte_for_byte():
    def record(seed):
        device = Device(seed)
        out = device.handle(
            command(Command("inject_fault", {"fault": "noisy_sensor", "magnitude": 0.2})), NOW
        )
        for step in range(50):
            out += device.tick(0.1, NOW + step * 100)
        return out

    assert record(3) == record(3)
    assert record(3) != record(4)
