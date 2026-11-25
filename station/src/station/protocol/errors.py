class PacketError(ValueError):
    """A packet that cannot be used. `reason` is a stable key for counting rejections."""

    reason = "invalid"


class TooShortError(PacketError):
    reason = "too_short"


class UnsupportedError(PacketError):
    reason = "unsupported"


class LengthError(PacketError):
    reason = "length_mismatch"


class CrcError(PacketError):
    reason = "bad_crc"


class PayloadError(PacketError):
    reason = "bad_payload"
