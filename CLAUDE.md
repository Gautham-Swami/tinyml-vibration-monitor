# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TinyML vibration monitor: an ESP32 reads an MPU-6050 accelerometer/gyroscope and runs a neural network that sorts a fan into one of four states: **normal**, **off**, **blocked**, **imbalanced**.

## Current state

Early stage. The only verified result so far: the MPU-6050 responds over I2C at address `0x68`. The repo has no firmware, training code, or build setup yet, so there are no build, lint, or test commands to document.

`.gitignore` shows the intended toolchain:
- `.pio/` → firmware will probably be a PlatformIO project (ESP32).
- `.venv/`, `__pycache__/` → a Python side, probably for data collection and model training.
- `data/raw/` is git-ignored. Raw sensor captures stay local and are not committed, so don't expect training data in a fresh clone.

Update this file with real commands and architecture once firmware or training code lands.

## Commands (firmware)

   `pio` is not on Git Bash's PATH; use `~/.platformio/penv/Scripts/pio.exe` (or an alias).

   - Build: `pio run -d firmware`
   - Flash: `pio run -d firmware -t upload` (hold BOOT if it can't connect)
   - Monitor: `pio device monitor -d firmware --echo` (115200 baud)

   ## Known issues

   - MPU-6050 z-axis reads about +0.31 g high (offset, gain ≈ 1.02). Calibration not yet implemented.

## Hardware

- Board: ESP32 dev board
- MPU-6050 on I2C at address 0x68 (verified with an I2C scanner)
- SDA = GPIO 21, SCL = GPIO 22

## Workflow rules

- Always work on a feature branch; never commit directly to main.
- Run tests before committing when tests exist.
- Show a plan before making changes.
- Never present results from simulated or test data as project metrics; they are pipeline checks only.

