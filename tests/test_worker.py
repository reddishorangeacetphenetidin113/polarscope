"""Worker tests with mocked pyrplidar driver."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QTimer

from lidar.worker import LidarWorker


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def _fake_measurement(angle_deg: float, distance_mm: float, quality: int, start_flag: bool):
    m = MagicMock()
    m.angle = angle_deg
    m.distance = distance_mm
    m.quality = quality
    m.start_flag = start_flag
    return m


def _make_lidar(measurements, model=24, status=0):
    """Build a fake PyRPlidar instance.

    `measurements`: list of fake measurement objects to yield from the scan generator.
    """
    lidar = MagicMock()
    lidar.get_info.return_value = MagicMock(
        model=model, firmware_minor=0, firmware_major=1, hardware=1, serialnumber="ABC123"
    )
    lidar.get_health.return_value = MagicMock(status=status, error_code=0)

    # PyRPlidar.start_scan returns a callable that, when called, returns a generator.
    def gen():
        for m in measurements:
            yield m
        # After list exhausts, simulate stalled serial (raise on next read)
        raise IndexError("serial read returned empty")

    lidar.start_scan.return_value = gen
    return lidar


def test_open_device_emits_connected(qapp):
    fake = _make_lidar([])
    with patch("lidar.worker.PyRPlidar", return_value=fake):
        worker = LidarWorker()
        states = []
        worker.status_changed.connect(states.append)
        worker.open_device("/dev/cu.usbserial-FAKE")
        QCoreApplication.processEvents()
    assert "connected" in states
    fake.connect.assert_called_once()


def test_open_device_health_error_emits_error(qapp):
    fake = _make_lidar([], status=2)
    with patch("lidar.worker.PyRPlidar", return_value=fake):
        worker = LidarWorker()
        errors = []
        worker.error_occurred.connect(errors.append)
        worker.open_device("/dev/cu.usbserial-FAKE")
        QCoreApplication.processEvents()
    assert any("health" in e.lower() for e in errors)


def test_scan_loop_emits_one_signal_per_full_rotation(qapp):
    # Three points in scan A, marker for scan B, then a few B points.
    # start_flag=True marks the BEGINNING of a new scan.
    meas = [
        _fake_measurement(0.0, 1000.0, 40, start_flag=True),
        _fake_measurement(90.0, 2000.0, 40, start_flag=False),
        _fake_measurement(180.0, 3000.0, 40, start_flag=False),
        _fake_measurement(0.0, 1100.0, 40, start_flag=True),  # marks scan B
        _fake_measurement(90.0, 2100.0, 40, start_flag=False),
    ]
    fake = _make_lidar(meas)
    with patch("lidar.worker.PyRPlidar", return_value=fake):
        worker = LidarWorker()
        worker.open_device("/dev/cu.usbserial-FAKE")
        QCoreApplication.processEvents()

        received = []
        worker.scan_ready.connect(lambda xy: received.append(xy))

        # Stop after a short delay to bound the test.
        QTimer.singleShot(300, worker._stop_event.set)
        worker.start_scan()
    # First full rotation accumulated (3 points), then generator raises, loop exits.
    # We expect at least one emit (scan A).
    assert len(received) >= 1
    xy = received[0]
    assert xy.shape == (3, 2)
    # Point 1: angle=0° → up → x≈0, y≈1
    assert abs(xy[0, 0]) < 1e-3
    assert abs(xy[0, 1] - 1.0) < 1e-3


def test_unplug_during_scan_emits_disconnected(qapp):
    # Empty measurement list → generator raises on first iteration → unplug path.
    fake = _make_lidar([])
    with patch("lidar.worker.PyRPlidar", return_value=fake):
        worker = LidarWorker()
        worker.open_device("/dev/cu.usbserial-FAKE")
        QCoreApplication.processEvents()

        errors = []
        states = []
        worker.error_occurred.connect(errors.append)
        worker.status_changed.connect(states.append)
        worker.start_scan()
    assert any("disconnect" in e.lower() or "lidar" in e.lower() for e in errors)
    assert "disconnected" in states


def test_close_device_disconnects(qapp):
    fake = _make_lidar([])
    with patch("lidar.worker.PyRPlidar", return_value=fake):
        worker = LidarWorker()
        worker.open_device("/dev/cu.usbserial-FAKE")
        QCoreApplication.processEvents()
        worker.close_device()
    fake.disconnect.assert_called()
