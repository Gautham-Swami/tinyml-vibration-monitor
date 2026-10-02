"""send_command against a fake serial port (no hardware)."""

import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import server


class FakeSerial:
    """Returns scripted bytes once the command has been written."""

    def __init__(self, response: bytes):
        self._response = response
        self._pending = b""
        self.written = b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def reset_input_buffer(self):
        self._pending = b""

    def write(self, data: bytes):
        self.written += data
        self._pending += self._response

    def flush(self):
        pass

    @property
    def in_waiting(self) -> int:
        return len(self._pending)

    def read(self, n: int = 1) -> bytes:
        if not self._pending:
            time.sleep(0.005)  # behave like a short read timeout
            return b""
        chunk, self._pending = self._pending[:n], self._pending[n:]
        return chunk


@pytest.fixture
def fake_port(monkeypatch):
    def install(response: bytes) -> FakeSerial:
        fake = FakeSerial(response)
        monkeypatch.setattr(server, "_open", lambda port: fake)
        return fake

    return install


def test_comment_after_reply_is_captured(fake_port):
    fake = fake_port(b"OK STREAM OFF\r\n# overruns=2 read_errors=1\r\n")
    result = server.send_command("COM4", "stream off")
    assert fake.written == b"STREAM OFF\n"
    assert result["reply"] == "OK STREAM OFF"
    assert result["comments"] == ["# overruns=2 read_errors=1"]
    assert result["reset_detected"] is False


def test_data_lines_are_skipped(fake_port):
    fake_port(b"0.9987\n12340,0.0123,-0.0045,0.9987\nPONG\n12350,0.0120,-0.0040,0.9990\n")
    result = server.send_command("COM4", "PING")
    assert result["reply"] == "PONG"
    assert result["comments"] == []


def test_boot_banner_sets_reset_detected(fake_port):
    fake_port(b"# tinyml-vibration-monitor imu-stream\nPONG\n")
    result = server.send_command("COM4", "PING")
    assert result["reset_detected"] is True


def test_no_reply_raises(fake_port):
    fake_port(b"12340,0.0123,-0.0045,0.9987\n")
    with pytest.raises(ToolError, match="no reply"):
        server.send_command("COM4", "PING")


def test_invalid_command_never_opens_port(monkeypatch):
    def fail(port):
        raise AssertionError("port opened for an invalid command")

    monkeypatch.setattr(server, "_open", fail)
    with pytest.raises(ToolError, match="not allowed"):
        server.send_command("COM4", "RESET")
