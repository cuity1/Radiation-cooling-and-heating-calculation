"""Dialogs such as progress dialog."""

from __future__ import annotations

from PyQt5.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout


class ProgressDialog(QDialog):
    """Indeterminate progress dialog."""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(350, 100)
        self.setWindowFlags(self.windowFlags() & ~self.windowFlags() & ~0x00000800)  # no help button

        layout = QVBoxLayout()

        self.message_label = QLabel(message)
        layout.addWidget(self.message_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def update_language(self):
        """Placeholder for language update."""
        pass
