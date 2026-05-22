"""LidarWorker — QObject that drives pyrplidar and emits scan data."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot

from pyrplidar import PyRPlidar

from .recorder import CsvRecorder
from .transform import filter_scan, polar_to_xy

C1_BAUDRATE = 460800
SERIAL_TIMEOUT_S = 3


class LidarWorker(QObject):
    scan_ready = Signal(object)        # np.ndarray of shape (N, 2) float32
    stats = Signal(float, int)         # hz, n_points
    status_changed = Signal(str)       # "connected" | "scanning" | "connected (idle)" | "disconnected"
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._lidar: Optional[PyRPlidar] = None
        self._stop_event = threading.Event()
        self._recorder: Optional[CsvRecorder] = None
        self._scan_idx = 0
        self._last_emit = 0.0
        self._hz_ema = 0.0

    # ----- lifecycle slots -----

    @Slot(str)
    def open_device(self, port: str) -> None:
        try:
            lidar = PyRPlidar()
            lidar.connect(port=port, baudrate=C1_BAUDRATE, timeout=SERIAL_TIMEOUT_S)
            self._lidar = lidar
            info = lidar.get_info()
            if info is None:
                self.error_occurred.emit(f"Device on {port} not RPLIDAR")
                self._shutdown_driver()
                return
            health = lidar.get_health()
            if health is not None and health.status == 2:
                self.error_occurred.emit("Device health ERROR — restart device")
                self._shutdown_driver()
                return
            self.status_changed.emit("connected")
        except Exception as exc:
            self.error_occurred.emit(f"Open failed: {exc}")
            self._shutdown_driver()

    @Slot()
    def close_device(self) -> None:
        self._shutdown_driver()
        self.status_changed.emit("disconnected")

    @Slot(str)
    def record_started(self, path: str) -> None:
        if self._recorder is not None:
            self._recorder.stop()
        self._recorder = CsvRecorder(path)
        self._recorder.start()

    @Slot()
    def record_stopped(self) -> None:
        if self._recorder is not None:
            self._recorder.stop()
            self._recorder = None

    @Slot()
    def start_scan(self) -> None:
        if self._lidar is None:
            self.error_occurred.emit("Not connected")
            return
        self._stop_event.clear()
        self._last_emit = time.perf_counter()
        self._hz_ema = 0.0
        self._scan_idx = 0
        self.status_changed.emit("scanning")

        try:
            scan_gen = self._lidar.start_scan()
            self._run_scan_loop(scan_gen)
        except Exception as exc:
            self.error_occurred.emit(f"Lidar disconnected: {exc}")
            self._shutdown_driver()
            self.status_changed.emit("disconnected")
            return
        finally:
            self._safe_stop()

        if self._lidar is not None:
            self.status_changed.emit("connected (idle)")

    # ----- hot loop -----

    def _run_scan_loop(self, scan_gen) -> None:
        """Iterate per-measurement, accumulate into full scans, emit per rotation."""
        cur_a: list[float] = []
        cur_r: list[float] = []
        cur_q: list[int] = []

        for m in scan_gen():
            if self._stop_event.is_set():
                break
            if m.start_flag and cur_a:
                self._emit_scan(cur_a, cur_r, cur_q)
                cur_a, cur_r, cur_q = [], [], []
            cur_a.append(m.angle)
            cur_r.append(m.distance)
            cur_q.append(m.quality)

    def _emit_scan(self, angles_deg: list[float], distances_mm: list[float], qualities: list[int]) -> None:
        a_deg = np.asarray(angles_deg, dtype=np.float32)
        r_mm = np.asarray(distances_mm, dtype=np.float32)
        q = np.asarray(qualities, dtype=np.uint8)
        a_rad = np.deg2rad(a_deg)
        r_m = r_mm / 1000.0
        a_rad, r_m, q = filter_scan(a_rad, r_m, q)
        if len(a_rad) == 0:
            return
        x, y = polar_to_xy(a_rad, r_m)
        xy = np.column_stack([x, y]).astype(np.float32)
        self.scan_ready.emit(xy)

        now = time.perf_counter()
        dt = now - self._last_emit
        self._last_emit = now
        if dt > 0:
            self._hz_ema = 0.9 * self._hz_ema + 0.1 * (1.0 / dt)
        self.stats.emit(self._hz_ema, len(x))

        if self._recorder is not None:
            self._recorder.write(
                scan_index=self._scan_idx,
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
                angles_deg=np.degrees(a_rad),
                distances_m=r_m,
                qualities=q,
            )
        self._scan_idx += 1

    # ----- helpers -----

    def _safe_stop(self) -> None:
        if self._lidar is not None:
            try:
                self._lidar.stop()
            except Exception:
                pass

    def _shutdown_driver(self) -> None:
        self._safe_stop()
        if self._lidar is not None:
            try:
                self._lidar.disconnect()
            except Exception:
                pass
            self._lidar = None
        if self._recorder is not None:
            try:
                self._recorder.stop()
            except Exception:
                pass
            self._recorder = None
