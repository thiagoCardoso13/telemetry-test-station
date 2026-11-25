"""The simulated equipment as the link sees it: datagrams in, datagrams out. No sockets here."""

from dataclasses import asdict
from enum import IntEnum

from station import protocol

from .tank import FaultError, StuckValveError, Tank


class ErrorCode(IntEnum):
    BAD_PAYLOAD = 1
    UNSUPPORTED = 2
    BAD_ARGUMENT = 3
    VALVE_STUCK = 4


class Device:
    def __init__(self, seed: int = 0):
        self.tank = Tank(seed)
        self.rejected: dict[str, int] = {}
        self._sequence = 0

    def tick(self, dt: float, now_ms: int) -> list[bytes]:
        """Advance the physics; return the events followed by one housekeeping report."""
        messages = [protocol.EventReport(name, self.tank.pressure) for name in self.tank.step(dt)]
        messages.append(protocol.Housekeeping(asdict(self.tank.read())))
        return [self._frame(m, now_ms) for m in messages]

    def handle(self, datagram: bytes, now_ms: int) -> list[bytes]:
        """Execute one telecommand and return the reports about it.

        Datagrams that cannot be trusted at all (damaged, not for us, not a command) are only
        counted: there is no reliable request id to answer to.
        """
        try:
            packet = protocol.decode(datagram)
        except protocol.PacketError as error:
            return self._reject(error.reason)
        if packet.type != protocol.PacketType.TELECOMMAND:
            return self._reject("not_a_command")
        if packet.apid != protocol.DEFINITIONS.apid:
            return self._reject("wrong_apid")

        request_id = datagram[:4]
        accepted = protocol.Stage.ACCEPTANCE
        try:
            command = protocol.from_packet(packet)
        except protocol.PacketError as error:
            code = (
                ErrorCode.BAD_PAYLOAD
                if isinstance(error, protocol.PayloadError)
                else ErrorCode.UNSUPPORTED
            )
            return [self._frame(protocol.Verification(accepted, request_id, code), now_ms)]

        reports: list[protocol.Message] = [protocol.Verification(accepted, request_id)]
        error_code = None
        try:
            reports += self._execute(command)
        except StuckValveError:
            error_code = ErrorCode.VALVE_STUCK
        except ValueError:
            error_code = ErrorCode.BAD_ARGUMENT
        reports.append(protocol.Verification(protocol.Stage.COMPLETION, request_id, error_code))
        return [self._frame(m, now_ms) for m in reports]

    def _execute(self, command: protocol.Message) -> list[protocol.Message]:
        match command:
            case protocol.Ping():
                return [protocol.Pong()]
            case protocol.Command("set_valve", args):
                if args["open"] not in (0, 1):
                    raise ValueError("open must be 0 or 1")
                self.tank.set_valve(args["valve"], bool(args["open"]))
            case protocol.Command("inject_fault", args):
                self.tank.inject_fault(args["fault"], args["magnitude"])
                return [protocol.EventReport("fault_injected", args["magnitude"])]
            case protocol.Command("clear_faults"):
                self.tank.clear_faults()
            case protocol.Command("reset"):
                self.tank.reset()
            case _:
                raise FaultError(f"no handler for {command}")
        return []

    def _reject(self, reason: str) -> list[bytes]:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1
        return []

    def _frame(self, message: protocol.Message, now_ms: int) -> bytes:
        packet = protocol.to_packet(message, sequence=self._sequence, time_ms=now_ms)
        self._sequence = (self._sequence + 1) % (protocol.MAX_SEQUENCE + 1)
        return protocol.encode(packet)
