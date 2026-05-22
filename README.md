# RPLIDAR C1 Live Viewer

Dark-mode macOS desktop app for visualizing Slamtec RPLIDAR C1 scans.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Hardware notes

- C1 ships with USB-C → CP210x UART. macOS 11+ ships an Apple-signed CP210x driver — no install needed. If you ever installed the legacy SiLabs kext, remove it.
- Baud rate is fixed at 460800 (C1 spec).
- Port shows up as `/dev/cu.usbserial-*`.

## Tests

```bash
pytest -v
```
