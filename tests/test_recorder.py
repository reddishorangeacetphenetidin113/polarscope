import csv
import numpy as np
import pytest
from lidar.recorder import CsvRecorder


def test_writes_header_and_rows(tmp_path):
    path = tmp_path / "scan.csv"
    rec = CsvRecorder(str(path))
    rec.start()

    a = np.array([0.0, 90.0, 180.0])
    r = np.array([1.0, 2.0, 3.0])
    q = np.array([45, 50, 55], dtype=np.uint8)
    rec.write(
        scan_index=0,
        timestamp_iso="2026-05-21T22:46:00",
        angles_deg=a,
        distances_m=r,
        qualities=q,
    )
    rec.stop()

    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["timestamp_iso", "scan_index", "angle_deg", "distance_m", "quality"]
    assert len(rows) == 4
    assert rows[1][1] == "0"
    assert float(rows[1][2]) == 0.0
    assert float(rows[1][3]) == 1.0
    assert int(rows[1][4]) == 45


def test_multiple_scans(tmp_path):
    path = tmp_path / "scan.csv"
    rec = CsvRecorder(str(path))
    rec.start()
    for i in range(3):
        rec.write(
            scan_index=i,
            timestamp_iso=f"t{i}",
            angles_deg=np.array([0.0, 1.0]),
            distances_m=np.array([1.0, 2.0]),
            qualities=np.array([10, 20], dtype=np.uint8),
        )
    rec.stop()
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 1 + 3 * 2


def test_stop_idempotent(tmp_path):
    rec = CsvRecorder(str(tmp_path / "scan.csv"))
    rec.start()
    rec.stop()
    rec.stop()


def test_write_before_start_raises(tmp_path):
    rec = CsvRecorder(str(tmp_path / "scan.csv"))
    with pytest.raises(RuntimeError):
        rec.write(
            0,
            "t",
            np.array([0.0]),
            np.array([1.0]),
            np.array([10], dtype=np.uint8),
        )
