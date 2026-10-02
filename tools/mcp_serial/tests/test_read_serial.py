"""read_serial against a fake port that replays scripted reads (no hardware)."""

import time

import pytest

import server

# Lines as the firmware sends them; read_serial drops the first line it sees
# (normally a fragment), so every script starts with a partial line.
PARTIAL = b"7,0.0811,0.0149,1.3422\r\n"
LINES = [
    b"2264007,0.0841,0.0149,1.3346",
    b"2264027,0.0775,0.0107,1.3381",
    b"2264047,0.0809,0.0132,1.3395",
    b"2264067,0.0814,0.0122,1.3374",
    b"2264087,0.0798,0.0143,1.3409",
]
STREAM = PARTIAL + b"".join(l + b"\r\n" for l in LINES)
EXPECTED = [l.decode() for l in LINES]


class ScriptedSerial:
    """Each read() returns the next scripted chunk (b"" = a timed-out read)."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def reset_input_buffer(self):
        pass

    @property
    def in_waiting(self) -> int:
        return len(self._chunks[0]) if self._chunks else 0

    def read(self, n: int = 1) -> bytes:
        if not self._chunks:
            time.sleep(0.005)  # behave like a short read timeout
            return b""
        chunk = self._chunks.pop(0)
        if len(chunk) > n:
            self._chunks.insert(0, chunk[n:])
            chunk = chunk[:n]
        return chunk


def capture(monkeypatch, chunks: list[bytes]) -> dict:
    monkeypatch.setattr(server, "_open", lambda port: ScriptedSerial(chunks))
    return server.read_serial("COM4", 0.1)


def byte_chunks(data: bytes) -> list[bytes]:
    return [data[i : i + 1] for i in range(len(data))]


@pytest.mark.parametrize(
    "chunks",
    [
        pytest.param([STREAM], id="one-chunk"),
        pytest.param(byte_chunks(STREAM), id="1-byte-chunks"),
        pytest.param([STREAM[:40], STREAM[40:41], STREAM[41:]], id="split-mid-line"),
        pytest.param(
            [c for i in range(0, len(STREAM), 7) for c in (STREAM[i : i + 7], b"", b"")],
            id="7-byte-chunks-with-empty-reads",
        ),
        pytest.param(
            [STREAM[: STREAM.index(b"\r") + 1], STREAM[STREAM.index(b"\r") + 1 :]],
            id="split-between-cr-and-lf",
        ),
        pytest.param(
            [PARTIAL] + [l + b"\r\n" for l in LINES], id="one-line-per-chunk"
        ),
    ],
)
def test_each_line_emitted_exactly_once(monkeypatch, chunks):
    result = capture(monkeypatch, chunks)
    assert result["output"].splitlines() == EXPECTED
    assert result["data_lines"] == len(LINES)
    assert result["total_lines"] == len(LINES)
    assert result["duplicate_lines"] == 0
    # +1 for the dropped first line
    assert result["newlines_received"] == len(LINES) + 1


def test_duplicate_lines_counts_consecutive_repeats(monkeypatch):
    a, b = LINES[0] + b"\r\n", LINES[1] + b"\r\n"
    result = capture(monkeypatch, [PARTIAL, a, a, a, b, b])
    assert result["data_lines"] == 5
    assert result["duplicate_lines"] == 3
    assert result["output"].splitlines() == [EXPECTED[0]] * 3 + [EXPECTED[1]] * 2


def test_duplicate_lines_ignores_repeated_comments(monkeypatch):
    c = b"# WHO_AM_I=0x68\r\n"
    result = capture(monkeypatch, [PARTIAL, c, c, LINES[0] + b"\r\n"])
    assert result["duplicate_lines"] == 0


def test_duplicate_chunks_counts_identical_reads(monkeypatch):
    a = LINES[0] + b"\r\n"
    # Empty reads between repeats must not reset the comparison.
    result = capture(monkeypatch, [PARTIAL, a, b"", a, b"", b"", a, LINES[1] + b"\r\n"])
    assert result["duplicate_chunks"] == 2
    assert result["duplicate_lines"] == 2
    assert result["newlines_received"] == 5


def test_repeats_inside_one_chunk_show_in_raw_newlines(monkeypatch):
    # A replay delivered inside a single read: duplicate_chunks can't see it,
    # but the raw newline count proves the copies were in the received bytes.
    a = LINES[0] + b"\r\n"
    result = capture(monkeypatch, [PARTIAL + a * 4])
    assert result["duplicate_chunks"] == 0
    assert result["duplicate_lines"] == 3
    assert result["newlines_received"] == result["total_lines"] + 1
