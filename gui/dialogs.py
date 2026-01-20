"""Dialogs such as progress dialog."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from gui.i18n import COLORS, language_manager


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


class CitationDialog(QDialog):
    """Citation dialog shown when closing the main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        language_manager.language_changed.connect(self.on_language_changed)
        self.setWindowTitle(language_manager.get('citation_title'))
        self.setFixedSize(600, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.init_ui()
        self.retranslate_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        
        self.title_label = QLabel()
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"color: {COLORS['accent']}; padding: 10px;")
        layout.addWidget(self.title_label)

        # Message
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(f"color: {COLORS['primary_text']}; padding: 5px;")
        layout.addWidget(self.message_label)

        # Cooling citation
        cooling_layout = QVBoxLayout()
        cooling_layout.setSpacing(5)
        
        self.cooling_title_label = QLabel()
        self.cooling_title_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        cooling_layout.addWidget(self.cooling_title_label)
        
        self.cooling_link_label = QLabel()
        self.cooling_link_label.setWordWrap(True)
        self.cooling_link_label.setStyleSheet(
            f"color: {COLORS['accent']}; text-decoration: underline; padding-left: 20px;"
        )
        self.cooling_link_label.setOpenExternalLinks(False)
        self.cooling_link_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        cooling_layout.addWidget(self.cooling_link_label)
        
        self.cooling_button = QPushButton()
        self.cooling_button.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(language_manager.get('citation_cooling_link'))
        ))
        cooling_layout.addWidget(self.cooling_button)
        
        layout.addLayout(cooling_layout)

        # Heating citation
        heating_layout = QVBoxLayout()
        heating_layout.setSpacing(5)
        
        self.heating_title_label = QLabel()
        self.heating_title_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        heating_layout.addWidget(self.heating_title_label)
        
        self.heating_link_label = QLabel()
        self.heating_link_label.setWordWrap(True)
        self.heating_link_label.setStyleSheet(
            f"color: {COLORS['accent']}; text-decoration: underline; padding-left: 20px;"
        )
        self.heating_link_label.setOpenExternalLinks(False)
        self.heating_link_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        heating_layout.addWidget(self.heating_link_label)
        
        self.heating_button = QPushButton()
        self.heating_button.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(language_manager.get('citation_heating_link'))
        ))
        heating_layout.addWidget(self.heating_button)
        
        layout.addLayout(heating_layout)

        # Thanks message
        self.thanks_label = QLabel()
        self.thanks_label.setAlignment(Qt.AlignCenter)
        self.thanks_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold; padding: 10px;")
        layout.addWidget(self.thanks_label)

        layout.addStretch()

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 500;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: #2980B9;
            }}
            QPushButton:pressed {{
                background-color: #21618C;
            }}
        """)

    def on_language_changed(self, lang: str):
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(language_manager.get('citation_title'))
        self.title_label.setText(language_manager.get('citation_title'))
        self.message_label.setText(language_manager.get('citation_message'))
        
        self.cooling_title_label.setText(language_manager.get('citation_cooling_title'))
        self.cooling_link_label.setText(language_manager.get('citation_cooling_link'))
        self.cooling_button.setText(f"🔗 {language_manager.get('citation_open_link')}")
        
        self.heating_title_label.setText(language_manager.get('citation_heating_title'))
        self.heating_link_label.setText(language_manager.get('citation_heating_link'))
        self.heating_button.setText(f"🔗 {language_manager.get('citation_open_link')}")
        
        self.thanks_label.setText(language_manager.get('citation_thanks'))
        self.close_button.setText(language_manager.get('close'))
