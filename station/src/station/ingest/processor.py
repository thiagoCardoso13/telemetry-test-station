"""Turn raw datagrams into records. No sockets and no database."""

from datetime import UTC, datetime

from station import protocol

from .alarms import AlarmMonitor
from .records import Batch, CommandUpdate, LogEntry, Sample

_SEQUENCES = protocol.MAX_SEQUENCE + 1
# After this many "old" packets in a row, they are the real stream and the reference was wrong.
OLD_PACKETS_BEFORE_RESYNC = 20


class Processor:
    def __init__(self, alarms: AlarmMonitor | None = None):
        self.alarms = alarms or AlarmMonitor()
        self._last: tuple[int, int] | None = None  # sequence and time of the newest packet
        self._old_in_a_row = 0

    def process(self, datagram: bytes, received: datetime, batch: Batch) -> None:
        """Add what one datagram means to the batch. Bad input is counted, never raised."""
        try:
            packet = protocol.decode(datagram)
        except protocol.PacketError as error:
            return self._invalid(batch, received, error.reason, str(error))
        header = (packet.service, packet.subservice, packet.sequence)
        if packet.type != protocol.PacketType.TELEMETRY:
            return self._invalid(batch, received, "not_telemetry", "telecommand received", header)
        try:
            message = protocol.from_packet(packet)
            time = datetime.fromtimestamp(packet.time_ms / 1000, UTC)
        except protocol.PacketError as error:
            return self._invalid(batch, received, error.reason, str(error), header)
        except (OverflowError, ValueError, OSError):
            return self._invalid(batch, received, "bad_time", "time out of range", header)

        batch.counters["received"] += 1
        if not self._is_new(packet, batch):
            return

        match message:
            case protocol.Housekeeping(values):
                batch.samples += [Sample(time, name, value) for name, value in values.items()]
                batch.alarms += self.alarms.check(time, values)
                return  # too frequent for the packet log
            case protocol.Verification(stage, request_id, error):
                accepted = stage == protocol.Stage.ACCEPTANCE
                if error is None:
                    status = "accepted" if accepted else "completed"
                else:
                    status = "rejected" if accepted else "failed"
                batch.commands.append(CommandUpdate(time, request_id, status, error))
                detail = f"command {status}"
            case protocol.EventReport(name, value):
                detail = f"event {name} ({value:.2f})"
            case _:
                detail = type(message).__name__.lower()
        batch.log.append(LogEntry(time, "in", True, detail, *header))

    def _is_new(self, packet: protocol.Packet, batch: Batch) -> bool:
        """Count gaps in the sequence. False for late or repeated packets."""
        if self._last is not None:
            last_sequence, last_time = self._last
            gap = (packet.sequence - last_sequence - 1) % _SEQUENCES
            if gap >= _SEQUENCES // 2:  # the sequence went backwards
                if packet.time_ms <= last_time:
                    self._old_in_a_row += 1
                    if self._old_in_a_row < OLD_PACKETS_BEFORE_RESYNC:
                        batch.counters["out_of_order"] += 1
                        return False
                batch.counters["resync"] += 1  # the sender restarted
            elif gap:
                batch.counters["lost"] += gap
        self._last = (packet.sequence, packet.time_ms)
        self._old_in_a_row = 0
        return True

    def _invalid(self, batch, received, reason, detail, header=()) -> None:
        batch.counters[f"rejected_{reason}"] += 1
        batch.log.append(LogEntry(received, "in", False, f"{reason}: {detail}", *header))
