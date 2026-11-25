import argparse


def address(text: str) -> tuple[str, int]:
    """Parse "host:port" from the command line or the environment."""
    host, _, port = text.rpartition(":")
    if not host or not port.isdigit():
        raise argparse.ArgumentTypeError(f"expected host:port, got {text!r}")
    return host, int(port)
