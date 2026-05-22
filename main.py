"""Entry point for RPLIDAR C1 viewer."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from theme import apply_dark_theme
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
