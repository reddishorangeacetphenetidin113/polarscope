"""MainWindow: owns QThread + LidarWorker, wires Sidebar <-> Worker <-> Plot."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QMetaObject, Qt, QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from lidar.ports import list_serial_ports
from lidar.worker import LidarWorker
from ui.plot_widget import LidarPlot
from ui.sidebar import Sidebar
from ui.status_bar import TopBanner, attach_status_widgets


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RPLIDAR C1 Viewer")
        self.resize(1200, 800)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar()
        root.addWidget(self._sidebar)

        plot_col = QVBoxLayout()
        plot_col.setContentsMargins(8, 8, 8, 8)
        self._banner = TopBanner()
        self._plot = LidarPlot()
        plot_col.addWidget(self._banner)
        plot_col.addWidget(self._plot, stretch=1)
        root.addLayout(plot_col, stretch=1)

        self.setCentralWidget(central)
        self._stats = attach_status_widgets(self.statusBar())

        # Worker on a QThread
        self._thread = QThread(self)
        self._worker = LidarWorker()
        self._worker.moveToThread(self._thread)
        self._thread.start()

        self._wire_signals()
        self._sidebar.set_ports(list_serial_ports())
        self._sidebar.set_state("disconnected")
        self._first_scan_seen = False

    def _wire_signals(self) -> None:
        s, w = self._sidebar, self._worker
        # Sidebar -> Worker (queued; worker lives on another thread)
        s.connect_requested.connect(w.open_device, Qt.QueuedConnection)
        s.disconnect_requested.connect(w.close_device, Qt.QueuedConnection)
        s.start_requested.connect(w.start_scan, Qt.QueuedConnection)
        s.stop_requested.connect(self._on_stop)
        s.refresh_requested.connect(self._on_refresh)
        s.snapshot_requested.connect(self._on_snapshot)
        s.record_started.connect(w.record_started, Qt.QueuedConnection)
        s.record_stopped.connect(w.record_stopped, Qt.QueuedConnection)

        # Worker -> GUI
        w.scan_ready.connect(self._on_scan_ready)
        w.stats.connect(self._stats.update_stats)
        w.status_changed.connect(s.set_state)
        w.status_changed.connect(self._on_status)
        w.error_occurred.connect(self._on_error)

    # ----- handlers -----

    def _on_stop(self) -> None:
        # Direct, NOT a Qt slot — must bypass queued dispatch because scan loop
        # blocks the worker's event loop.
        self._worker._stop_event.set()

    def _on_refresh(self) -> None:
        self._sidebar.set_ports(list_serial_ports())

    def _on_scan_ready(self, xy) -> None:
        self._plot.update_points(xy)
        if not self._first_scan_seen:
            self._first_scan_seen = True
            self._sidebar.enable_snapshot()

    def _on_status(self, state: str) -> None:
        if state == "disconnected":
            self._plot.clear_points()
            self._first_scan_seen = False

    def _on_error(self, msg: str) -> None:
        self._banner.show_error(msg)

    def _on_snapshot(self) -> None:
        default = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(self, "Save snapshot", default, "PNG (*.png)")
        if path:
            self._plot.grab().save(path, "PNG")
            self._banner.show_info(f"Saved {path}")

    # ----- shutdown -----

    def closeEvent(self, event: QCloseEvent) -> None:
        self._worker._stop_event.set()
        # Give the scan loop time to exit and the worker thread to return to its event loop.
        self._thread.wait(500)
        # Queued-invoke close_device on worker thread.
        QMetaObject.invokeMethod(self._worker, "close_device", Qt.QueuedConnection)
        self._thread.quit()
        self._thread.wait(2000)
        event.accept()
