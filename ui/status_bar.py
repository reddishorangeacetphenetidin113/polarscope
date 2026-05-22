"""StatusArea: top banner (errors/info) + status-bar stats label."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QStatusBar


class TopBanner(QLabel):
    """Non-modal banner above plot area. Auto-hides after duration_ms."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def _show_with_object_name(self, msg: str, name: str, duration_ms: int) -> None:
        self.setObjectName(name)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setText(msg)
        self.show()
        self._timer.start(duration_ms)

    def show_error(self, msg: str, duration_ms: int = 6000) -> None:
        self._show_with_object_name(msg, "banner_error", duration_ms)

    def show_info(self, msg: str, duration_ms: int = 4000) -> None:
        self._show_with_object_name(msg, "banner_info", duration_ms)


class StatsLabel(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__("FPS: -- Hz | Points: --", parent)

    def update_stats(self, hz: float, n: int) -> None:
        self.setText(f"FPS: {hz:.1f} Hz | Points: {n}")


def attach_status_widgets(status_bar: QStatusBar) -> StatsLabel:
    stats = StatsLabel()
    status_bar.addPermanentWidget(stats)
    return stats
