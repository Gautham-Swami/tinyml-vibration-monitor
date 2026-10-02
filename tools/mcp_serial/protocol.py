"""Pure logic for the ESP32 imu-stream serial protocol (no I/O).

Mirrors firmware/src/commands.cpp: commands are PING, RATE <10-200>,
STREAM ON, STREAM OFF; replies are PONG, OK ..., ERR ...; lines starting
with '#' are comments; data lines are t_ms,ax,ay,az.
"""

import re

MIN_RATE_HZ = 10
MAX_RATE_HZ = 200
MAX_COMMAND_LEN = 32  # firmware LineBuffer::kCapacity

# Printed once by the firmware at boot; seeing it means the board reset.
BOOT_BANNER = "# tinyml-vibration-monitor imu-stream"

_COMMAND_RE = re.compile(r"PING|STREAM ON|STREAM OFF|RATE ([0-9]+)")
_REPLY_RE = re.compile(r"PONG|(OK|ERR)( .*)?")
_DATA_RE = re.compile(r"[0-9]+(,-?[0-9]+(\.[0-9]+)?){3}")


def validate_command(text: str) -> str:
    """Return the canonical form of an allowed command, or raise ValueError."""
    if not isinstance(text, str):
        raise ValueError("command must be a string")
    if len(text) > MAX_COMMAND_LEN:
        raise ValueError(f"command longer than {MAX_COMMAND_LEN} characters")
    # Reject control characters before normalizing, so "PING\nRATE 5" can't
    # smuggle a second line to the device.
    if any(not ch.isprintable() for ch in text):
        raise ValueError("command contains control or non-printable characters")

    normalized = " ".join(text.split()).upper()
    m = _COMMAND_RE.fullmatch(normalized)
    if m is None:
        raise ValueError(
            f"not allowed: {text!r}. Allowed: PING, RATE <{MIN_RATE_HZ}-{MAX_RATE_HZ}>, "
            "STREAM ON, STREAM OFF"
        )
    if m.group(1) is not None:
        rate = int(m.group(1))
        if not MIN_RATE_HZ <= rate <= MAX_RATE_HZ:
            raise ValueError(f"RATE must be {MIN_RATE_HZ}-{MAX_RATE_HZ}, got {rate}")
        return f"RATE {rate}"
    return normalized


def is_reply(line: str) -> bool:
    """True for a command reply: PONG, OK ..., ERR ..."""
    return _REPLY_RE.fullmatch(line.strip()) is not None


def classify_line(line: str) -> str:
    """Classify one received line as 'data', 'comment', 'reply' or 'other'."""
    s = line.strip()
    if s.startswith("#"):
        return "comment"
    if _DATA_RE.fullmatch(s):
        return "data"
    if is_reply(s):
        return "reply"
    return "other"


def is_boot_banner(line: str) -> bool:
    return line.strip() == BOOT_BANNER
