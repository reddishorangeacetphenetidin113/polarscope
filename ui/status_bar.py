"""StatusArea: top banner (errors/info) + status-bar stats label + REC indicator."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QStatusBar

import theme


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
        super().__init__("Scan rate: -- Hz | Points: --", parent)

    def update_stats(self, hz: float, n: int) -> None:
        self.setText(f"Scan rate: {hz:.1f} Hz | Points: {n}")


class RecIndicator(QLabel):
    """Blinking red REC pill shown in the status bar while recording."""

    def __init__(self, parent=None) -> None:
        super().__init__("● REC", parent)
        self.setStyleSheet(
            f"color: {theme.LED_ERROR}; font-weight: bold; padding-right: 8px;"
        )
        self.hide()
        self._blink = QTimer(self)
        self._blink.setInterval(600)
        self._blink.timeout.connect(self._toggle)
        self._visible_phase = True

    def _toggle(self) -> None:
        self._visible_phase = not self._visible_phase
        self.setStyleSheet(
            f"color: {theme.LED_ERROR if self._visible_phase else theme.SURFACE};"
            " font-weight: bold; padding-right: 8px;"
        )

    def start(self) -> None:
        self._visible_phase = True
        self.setStyleSheet(
            f"color: {theme.LED_ERROR}; font-weight: bold; padding-right: 8px;"
        )
        self.show()
        self._blink.start()

    def stop(self) -> None:
        self._blink.stop()
        self.hide()


@dataclass
class StatusWidgets:
    stats: StatsLabel
    rec: RecIndicator


def attach_status_widgets(status_bar: QStatusBar) -> StatusWidgets:
    rec = RecIndicator()
    stats = StatsLabel()
    status_bar.addPermanentWidget(rec)
    status_bar.addPermanentWidget(stats)
    return StatusWidgets(stats=stats, rec=rec)
