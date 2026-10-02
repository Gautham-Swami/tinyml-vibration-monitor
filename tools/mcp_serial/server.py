"""MCP server (stdio) for reading the ESP32 imu-stream serial port.

stdout is the MCP transport: nothing in this file may print to it.

The port is opened per call with DTR and RTS deasserted *before* open(), so
the ESP32 auto-reset circuit (RTS -> EN, DTR -> GPIO0) never fires and
firmware state such as RATE survives between calls.
"""

import time
from collections.abc import Callable, Iterator

import serial
import serial.tools.list_ports
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import protocol

BAUD = 115200
MIN_READ_SECONDS = 0.1
MAX_READ_SECONDS = 10.0
MAX_OUTPUT_CHARS = 16_000
REPLY_TIMEOUT_SECONDS = 1.0
# The firmware prints status comments (e.g. "# overruns=...") right after
# some replies, so keep listening briefly once the reply has arrived.
TRAILING_COMMENT_SECONDS = 0.1

mcp = MCPServer("esp32-serial")


def _open(port: str) -> serial.Serial:
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = BAUD
    ser.timeout = 0.05
    # Must be set before open(): pyserial applies them as the initial line
    # states, so the lines never pulse and the board isn't reset.
    ser.dtr = False
    ser.rts = False
    try:
        ser.open()
    except serial.SerialException as e:
        msg = str(e)
        if "PermissionError" in msg or "Access is denied" in msg:
            raise ToolError(
                f"{port} is in use by another program (close pio device monitor or any serial monitor)"
            ) from e
        if "FileNotFoundError" in msg or "cannot find" in msg:
            raise ToolError(f"{port} not found; use list_ports to see available ports") from e
        raise ToolError(f"could not open {port}: {msg}") from e
    return ser


def _lines(
    ser: serial.Serial, deadline: Callable[[], float], stats: dict | None = None
) -> Iterator[str]:
    """Yield complete lines (without CR/LF) until deadline() has passed.

    deadline is re-read on every pass so callers can shorten it mid-read.
    If stats is given, it receives raw-read diagnostics:
      duplicate_chunks: reads byte-identical to the previous non-empty read
      newlines_received: b"\\n" bytes returned by the port
    """
    if stats is not None:
        stats.update(duplicate_chunks=0, newlines_received=0)
    buf = b""
    prev_chunk = None
    while time.monotonic() < deadline():
        chunk = ser.read(ser.in_waiting or 1)
        if not chunk:
            continue
        if stats is not None:
            if chunk == prev_chunk:
                stats["duplicate_chunks"] += 1
            stats["newlines_received"] += chunk.count(b"\n")
        prev_chunk = chunk
        buf += chunk
        *complete, buf = buf.split(b"\n")
        for raw in complete:
            yield raw.rstrip(b"\r").decode("utf-8", errors="replace")


@mcp.tool()
def list_ports() -> list[dict]:
    """List available serial ports (device, description, hwid, vid, pid)."""
    return [
        {
            "device": p.device,
            "description": p.description,
            "hwid": p.hwid,
            "vid": p.vid,
            "pid": p.pid,
        }
        for p in serial.tools.list_ports.comports()
    ]


@mcp.tool()
def read_serial(port: str, seconds: float = 2.0) -> dict:
    """Capture ESP32 serial output for up to 10 seconds.

    Data lines are t_ms,ax,ay,az (g); lines starting with # are comments.
    Output text is capped at 16,000 characters (truncated=true); line counts
    still cover the whole capture. reset_detected=true means the boot banner
    was seen, i.e. the board restarted during the capture.

    Diagnostics: duplicate_lines counts data lines identical to the line
    before them (the firmware never sends these; they are kept in output).
    duplicate_chunks counts raw reads identical to the previous read, and
    newlines_received counts line endings in the raw bytes (it includes the
    dropped first line), so total_lines + 1 > newlines_received would mean
    lines were duplicated after reading.
    """
    seconds = min(max(float(seconds), MIN_READ_SECONDS), MAX_READ_SECONDS)
    counts = {"data": 0, "comment": 0, "reply": 0, "other": 0}
    kept: list[str] = []
    kept_chars = 0
    truncated = False
    reset_detected = False
    first = True
    prev_line = None
    duplicate_lines = 0
    raw_stats: dict = {}

    end = time.monotonic() + seconds
    with _open(port) as ser:
        ser.reset_input_buffer()
        for line in _lines(ser, lambda: end, raw_stats):
            if first:  # the flush almost always lands mid-line
                first = False
                continue
            kind = protocol.classify_line(line)
            counts[kind] += 1
            if kind == "data" and line == prev_line:
                duplicate_lines += 1
            prev_line = line
            reset_detected |= protocol.is_boot_banner(line)
            if truncated:
                continue
            if kept_chars + len(line) + 1 > MAX_OUTPUT_CHARS:
                truncated = True
                continue
            kept.append(line)
            kept_chars += len(line) + 1

    return {
        "port": port,
        "seconds": seconds,
        "total_lines": sum(counts.values()),
        "data_lines": counts["data"],
        "comment_lines": counts["comment"],
        "reply_lines": counts["reply"],
        "other_lines": counts["other"],
        "truncated": truncated,
        "reset_detected": reset_detected,
        "duplicate_lines": duplicate_lines,
        "duplicate_chunks": raw_stats["duplicate_chunks"],
        "newlines_received": raw_stats["newlines_received"],
        "output": "\n".join(kept),
    }


@mcp.tool()
def send_command(port: str, text: str) -> dict:
    """Send one command to the ESP32 and return its reply.

    Allowed: PING, RATE <10-200>, STREAM ON, STREAM OFF (case-insensitive).
    Anything else is rejected without opening the port. Comment (#) lines
    received before the reply and up to 0.1 s after it (e.g. the
    "# overruns=... read_errors=..." line after STREAM OFF) are returned in
    comments.
    """
    try:
        command = protocol.validate_command(text)
    except ValueError as e:
        raise ToolError(str(e)) from e

    comments: list[str] = []
    reply: str | None = None
    reset_detected = False
    end = time.monotonic() + REPLY_TIMEOUT_SECONDS
    with _open(port) as ser:
        ser.reset_input_buffer()
        ser.write(command.encode("ascii") + b"\n")
        ser.flush()
        for line in _lines(ser, lambda: end):
            if protocol.is_boot_banner(line):
                reset_detected = True
            kind = protocol.classify_line(line)
            if kind == "comment":
                comments.append(line)
            elif kind == "reply" and reply is None:
                reply = line.strip()
                end = time.monotonic() + TRAILING_COMMENT_SECONDS

    if reply is not None:
        return {
            "sent": command,
            "reply": reply,
            "comments": comments,
            "reset_detected": reset_detected,
        }
    raise ToolError(
        f"no reply to {command!r} within {REPLY_TIMEOUT_SECONDS:g}s"
        + (" (board reset detected)" if reset_detected else "")
    )


if __name__ == "__main__":
    mcp.run()
