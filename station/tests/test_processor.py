import math
import random
from datetime import UTC, datetime

from station import protocol
from station.ingest import AlarmMonitor, Batch, Processor

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VALUES = {
    "tank_pressure": 2.0,
    "tank_temperature": 20.0,
    "fill_valve": 0,
    "vent_valve": 0,
    "relief_valve": 0,
}


def telemetry(message=None, sequence=0, time_ms=1_000) -> bytes:
    message = message or protocol.Housekeeping(VALUES)
    return protocol.encode(protocol.to_packet(message, sequence=sequence, time_ms=time_ms))


def process(processor, *datagrams) -> Batch:
    batch = Batch()
    for datagram in datagrams:
        processor.process(datagram, NOW, batch)
    return batch


def stream(*sequences) -> list[bytes]:
    return [telemetry(sequence=s, time_ms=1_000 + i) for i, s in enumerate(sequences)]


def test_housekeeping_becomes_one_sample_per_parameter_and_no_log_line():
    batch = process(Processor(), telemetry())

    assert {s.parameter: s.value for s in batch.samples} == VALUES
    assert batch.counters == {"received": 1}
    assert batch.log == []


def test_missing_sequence_numbers_are_counted_as_lost():
    batch = process(Processor(), *stream(10, 11, 15, 16))

    assert batch.counters["lost"] == 3


def test_wrapping_the_sequence_is_not_a_loss():
    batch = process(Processor(), *stream(protocol.MAX_SEQUENCE, 0, 1))

    assert batch.counters == {"received": 3}


def test_late_and_repeated_packets_are_not_stored():
    processor = Processor()
    process(processor, telemetry(sequence=5, time_ms=2_000))

    batch = process(
        processor, telemetry(sequence=5, time_ms=2_000), telemetry(sequence=4, time_ms=1_900)
    )

    assert batch.counters["out_of_order"] == 2
    assert batch.samples == []


def test_a_restarted_sender_is_followed_again():
    processor = Processor()
    process(processor, telemetry(sequence=5_000, time_ms=2_000))

    batch = process(
        processor, telemetry(sequence=0, time_ms=9_000), telemetry(sequence=1, time_ms=9_100)
    )

    assert batch.counters == {"received": 2, "resync": 1}
    assert len(batch.samples) == 2 * len(VALUES)


def test_one_wild_packet_cannot_silence_the_stream_for_ever():
    processor = Processor()
    process(processor, telemetry(sequence=8_000, time_ms=10**13))

    batch = process(processor, *stream(*range(25)))

    assert batch.counters["out_of_order"] == 19
    assert batch.counters["resync"] == 1
    assert len(batch.samples) == 6 * len(VALUES)


def test_damaged_and_foreign_datagrams_are_counted_not_raised():
    damaged = bytearray(telemetry())
    damaged[-1] ^= 1
    command = telemetry(protocol.Ping())
    far_future = telemetry(time_ms=2**64 - 1)

    batch = process(Processor(), bytes(damaged), b"junk", command, far_future)

    assert batch.counters == {
        "rejected_bad_crc": 1,
        "rejected_too_short": 1,
        "rejected_not_telemetry": 1,
        "rejected_bad_time": 1,
    }
    assert [entry.valid for entry in batch.log] == [False] * 4


def test_random_bytes_never_stop_the_processor():
    generator = random.Random(1)
    processor = Processor()
    batch = process(processor, *(generator.randbytes(generator.randrange(60)) for _ in range(2000)))

    assert batch.samples == []
    assert process(processor, telemetry()).counters["received"] == 1


def test_verification_reports_become_command_updates():
    stage = protocol.Stage
    reports = [
        protocol.Verification(stage.ACCEPTANCE, b"abcd"),
        protocol.Verification(stage.COMPLETION, b"abcd", error=4),
    ]

    batch = process(Processor(), *(telemetry(r, sequence=i) for i, r in enumerate(reports)))

    assert [(c.status, c.error) for c in batch.commands] == [("accepted", None), ("failed", 4)]


def check(monitor, pressure, times=1):
    changes = []
    for _ in range(times):
        changes += monitor.check(NOW, VALUES | {"tank_pressure": pressure})
    return [(c.parameter, c.bound, c.raised) for c in changes]


def test_alarm_needs_three_samples_to_raise_and_to_clear():
    monitor = AlarmMonitor()

    assert check(monitor, 9.0, times=2) == []
    assert check(monitor, 9.0) == [("tank_pressure", "high", True)]
    assert check(monitor, 9.0, times=5) == []
    assert check(monitor, 5.0, times=2) == []
    assert check(monitor, 5.0) == [("tank_pressure", "high", False)]


def test_a_single_spike_raises_nothing():
    monitor = AlarmMonitor()

    for _ in range(10):
        assert check(monitor, 9.0, times=2) == []
        assert check(monitor, 5.0) == []


def test_low_limit_and_unreadable_values():
    monitor = AlarmMonitor()

    assert check(monitor, 0.1, times=3) == [("tank_pressure", "low", True)]
    assert check(monitor, math.nan, times=10) == []
    assert ("tank_pressure", "low") in monitor.active
