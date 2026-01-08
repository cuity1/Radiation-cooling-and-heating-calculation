"""New application entry point (thin).

You can point PyInstaller to this file to build.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication


def _ensure_project_on_path() -> None:
    """
    Ensure that the directory containing the 'gui' package is on sys.path.

    This works both when running from source and when running from a PyInstaller
    bundle (which uses sys._MEIPASS as the temp extraction dir).
    """
    # When running as a PyInstaller onefile exe, _MEIPASS points to the
    # temporary extraction directory that contains our bundled packages.
    base_dir: Path
    if hasattr(sys, "_MEIPASS"):
        base_dir = Path(getattr(sys, "_MEIPASS"))  # type: ignore[arg-type]
    else:
        # When running from source, use the directory of this file.
        base_dir = Path(__file__).resolve().parent

    base_str = str(base_dir)
    if base_str not in sys.path:
        sys.path.insert(0, base_str)


_ensure_project_on_path()

from gui.i18n import COLORS  # noqa: E402  (import after sys.path adjustment)
from gui.main_window import MainWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS['background']))
    palette.setColor(QPalette.WindowText, QColor(COLORS['primary_text']))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

