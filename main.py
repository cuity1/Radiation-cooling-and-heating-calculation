"""New application entry point (thin).

You can point PyInstaller to this file to build.
"""

from __future__ import annotations

import sys

from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication

from gui.i18n import COLORS
from gui.main_window import MainWindow


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

