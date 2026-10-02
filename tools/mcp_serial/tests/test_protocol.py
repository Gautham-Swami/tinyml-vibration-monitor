import pytest

from protocol import classify_line, is_boot_banner, is_reply, validate_command


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("PING", "PING"),
        ("ping", "PING"),
        ("  Stream On ", "STREAM ON"),
        ("stream off", "STREAM OFF"),
        ("STREAM   OFF", "STREAM OFF"),
        ("RATE 10", "RATE 10"),
        ("RATE 200", "RATE 200"),
        ("rate 050", "RATE 50"),
    ],
)
def test_valid_commands_are_canonicalized(text, expected):
    assert validate_command(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "RATE",
        "RATE 9",
        "RATE 201",
        "RATE 0",
        "RATE -50",
        "RATE 5.5",
        "RATE abc",
        "RATE 50 60",
        "RATE50",
        "STREAM",
        "STREAM MAYBE",
        "STREAMON",
        "PING PING",
        "PING\nRATE 50",
        "PING\r",
        "PING\n",
        "PING\x00",
        "RATE\t100",
        "RESET",
        "AT",
        "PONG",
        "OK",
        "RATE ٥٠",  # Arabic-Indic digits "50"
        "RATE " + "0" * 28 + "50",  # 35 chars
        "P" * 33,
    ],
)
def test_invalid_commands_are_rejected(text):
    with pytest.raises(ValueError):
        validate_command(text)


def test_non_string_is_rejected():
    with pytest.raises(ValueError):
        validate_command(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("12340,0.0123,-0.0045,0.9987", "data"),
        ("0,-1.0000,1.0000,-0.5000", "data"),
        ("12340,0.0123,-0.0045", "other"),
        ("0.9987", "other"),
        ("# t_ms,ax,ay,az", "comment"),
        ("# WHO_AM_I=0x68", "comment"),
        ("# overruns=3 read_errors=0", "comment"),
        ("PONG", "reply"),
        ("OK RATE 50", "reply"),
        ("OK STREAM OFF", "reply"),
        ("ERR RATE 10-200", "reply"),
        ("ERR UNKNOWN", "reply"),
        ("OKAY", "other"),
        ("PONGS", "other"),
        ("", "other"),
    ],
)
def test_classify_line(line, kind):
    assert classify_line(line) == kind


def test_is_reply_ignores_surrounding_whitespace():
    assert is_reply("PONG\r")
    assert is_reply("  OK RATE 50 ")
    assert not is_reply("ERRATA")


def test_boot_banner():
    assert is_boot_banner("# tinyml-vibration-monitor imu-stream\r")
    assert not is_boot_banner("# t_ms,ax,ay,az")
