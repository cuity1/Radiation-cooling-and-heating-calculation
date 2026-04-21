"""Tool box dialog that aggregates auxiliary analysis/plot tools."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QGroupBox, QVBoxLayout, QPushButton

from gui.i18n import COLORS, language_manager
from gui.widgets import STYLE_SHEET
from gui.era5_tool_dialog import Era5ToolDialog


class ToolBoxDialog(QDialog):
    def __init__(self, parent=None, openers: dict[str, callable] | None = None):
        super().__init__(parent)
        self._openers = openers or {}
        self.setWindowTitle(self._title())
        self.setFixedSize(520, 470)

        language_manager.language_changed.connect(self.on_language_changed)

        self._init_ui()
        self.retranslate_ui()

    def _open_era5_tool(self):
        dlg = Era5ToolDialog(self)
        dlg.exec_()

    def _title(self) -> str:
        return f"{language_manager.get('tool_box')} / {language_manager.get('tool_box_en')}"

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        self.group = QGroupBox()
        v = QVBoxLayout(self.group)
        v.setSpacing(10)

        self.btn_wind_cloud = QPushButton()
        self.btn_wind_cloud.clicked.connect(lambda: self._call('wind_cloud'))
        v.addWidget(self.btn_wind_cloud)

        self.btn_solar_eff = QPushButton()
        self.btn_solar_eff.clicked.connect(lambda: self._call('solar_efficiency'))
        v.addWidget(self.btn_solar_eff)

        self.btn_emissivity_solar_cloud = QPushButton()
        self.btn_emissivity_solar_cloud.clicked.connect(lambda: self._call('emissivity_solar_cloud'))
        v.addWidget(self.btn_emissivity_solar_cloud)

        self.btn_power_components = QPushButton()
        self.btn_power_components.clicked.connect(lambda: self._call('power_components'))
        v.addWidget(self.btn_power_components)

        self.btn_angular_power = QPushButton()
        self.btn_angular_power.clicked.connect(lambda: self._call('angular_power'))
        v.addWidget(self.btn_angular_power)

        self.btn_era5_tool = QPushButton()
        self.btn_era5_tool.clicked.connect(self._open_era5_tool)
        v.addWidget(self.btn_era5_tool)

        layout.addWidget(self.group)

        self.setStyleSheet(STYLE_SHEET)

    def _call(self, key: str):
        fn = self._openers.get(key)
        if callable(fn):
            fn()

    def on_language_changed(self, lang: str):
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(self._title())
        self.group.setTitle(language_manager.get('tool_box'))

        self.btn_wind_cloud.setText(language_manager.get('wind_cloud'))
        self.btn_solar_eff.setText(language_manager.get('solar_efficiency'))
        self.btn_emissivity_solar_cloud.setText(language_manager.get('emissivity_solar_cloud'))
        self.btn_power_components.setText(language_manager.get('power_components'))
        self.btn_angular_power.setText(language_manager.get('angular_power'))
        # ERA5/field experiment tool (English only to avoid missing Chinese fonts in some builds)
        self.btn_era5_tool.setText('In-situ Radiative / 原位模拟')

        # basic styling hint without changing global STYLE_SHEET
        self.group.setStyleSheet(f"QGroupBox {{ color: {COLORS['primary_text']}; }}")
