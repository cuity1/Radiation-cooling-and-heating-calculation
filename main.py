<<<<<<< HEAD
"""New application entry point (thin).

You can point PyInstaller to this file to build.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QApplication


def _run_compare_materials() -> None:
    """Entry for launching the material comparison GUI (used by --compare-materials)."""
    # 延迟导入，避免主界面启动时额外负担
    from material_comparison_tool.examples.compare_materials import main as compare_main
    compare_main()


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
        # When running from source or during PyInstaller analysis, use the directory of this file.
        # During PyInstaller analysis, __file__ might be a relative path, so resolve it.
        try:
            base_dir = Path(__file__).resolve().parent
        except (OSError, ValueError):
            # Fallback: use current working directory if __file__ is not available
            base_dir = Path(os.getcwd())

    base_str = str(base_dir)
    # 确保项目根目录在 sys.path 的最前面，这样 core 模块可以被正确导入
    if base_str in sys.path:
        sys.path.remove(base_str)
    sys.path.insert(0, base_str)


_ensure_project_on_path()

from gui.i18n import COLORS  # noqa: E402  (import after sys.path adjustment)
from gui.main_window import MainWindow  # noqa: E402


def main() -> None:
    # 如果带有对比工具参数，直接转去 compare GUI（同一个 exe，单文件）。
    if '--compare-materials' in sys.argv:
        _run_compare_materials()
        return

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
    import multiprocessing

    # 允许 PyInstaller onefile 下的多进程安全启动
    multiprocessing.freeze_support()
    main()

=======
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

>>>>>>> parent of 836f680 (update)
