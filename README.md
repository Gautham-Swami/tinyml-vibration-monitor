# TinyML Vibration Monitor

This project uses an ESP32 and a MPU-6050 (accelerometer and gyroscope) to classify a fan into 4 states; normal, off, blocked, and imbalanced through a neural network.
Status: in progress. MPU-6050 verified over I2C at address 0x68.

## Serial MCP server

`tools/mcp_serial/` is an MCP server that lets Claude Code read the ESP32's serial port. It has three tools:

- `list_ports`: lists the available serial ports.
- `read_serial(port, seconds)`: captures up to 10 s of output, capped at 16,000 characters.
- `send_command(port, text)`: sends `PING`, `RATE <10-200>`, `STREAM ON` or `STREAM OFF`. Anything else is rejected before it reaches the port.

The port is opened with DTR and RTS held low, so connecting doesn't reset the ESP32 and settings like `RATE` persist between calls. If a reset does happen anyway, the result reports `reset_detected: true`.

### Setup (Windows, Git Bash, from the repo root)

```bash
py -3 -m venv .venv
.venv/Scripts/python -m pip install -r tools/mcp_serial/requirements.txt
.venv/Scripts/python -m pytest tools/mcp_serial    # validation tests, no hardware needed
```

Register the server with Claude Code. It uses local scope, because the paths are specific to this machine:

```bash
claude mcp add esp32-serial -- "C:/Projects/tinyml-vibration-monitor/.venv/Scripts/python.exe" "C:/Projects/tinyml-vibration-monitor/tools/mcp_serial/server.py"
claude mcp list    # esp32-serial should show as connected
```

Close `pio device monitor` (or any other serial monitor) before using the tools. Windows lets only one program open a COM port at a time.
