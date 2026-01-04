"""Main application window."""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from core.theoretical import main_theoretical_heating_vs_solar
from gui.i18n import COLORS, language_manager
from gui.threads import CalculationThread
from gui.windows import InteractivePlotWindow
from gui.widgets import STYLE_SHEET
from utils.path_utils import external_default_dir, res_path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        language_manager.language_changed.connect(self.on_language_changed)

        self.setWindowTitle(language_manager.get('main_title'))
        self.setGeometry(100, 100, 650, 700)
        self.file_paths = {
            'config': (
                os.path.join(external_default_dir(), 'config.ini')
                if os.path.exists(os.path.join(external_default_dir(), 'config.ini'))
                else res_path('default', 'config.ini')
            ),
            'spectrum': res_path('default', 'AM1.5.xlsx'),
            'wavelength': res_path('default', 'wavelength.csv'),
        }

        # 加载配置文件并进行过期检查
        try:
            from core.config import load_config, check_expiration

            config = load_config(self.file_paths['config'])
            check_expiration(config['EXPIRATION_DATE'], config['EMAIL_CONTACT'])
        except Exception as e:
            QMessageBox.critical(
                self,
                language_manager.get('error'),
                f"{language_manager.get('calculation_failed')}: {e}",
            )
            sys.exit(1)

        self.init_ui()
        self.retranslate_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # 标题
        self.title_label = QLabel()
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"color: {COLORS['accent']}; padding: 10px;")
        layout.addWidget(self.title_label)

        # Language selector
        lang_row = QHBoxLayout()
        lang_row.addStretch()
        lang_label = QLabel(language_manager.get('语言'))
        self.language_combo = QComboBox()
        self.language_combo.addItem('中文', 'zh')
        self.language_combo.addItem('English', 'en')
        self.language_combo.setCurrentIndex(0 if language_manager.current_language == 'zh' else 1)
        self.language_combo.currentIndexChanged.connect(self._on_language_combo_changed)
        lang_row.addWidget(lang_label)
        lang_row.addWidget(self.language_combo)
        layout.addLayout(lang_row)

        # 文件选择组
        self.file_group = QGroupBox()
        self.file_layout = QVBoxLayout()
        self.file_layout.setSpacing(10)

        self.reflectance_btn = QPushButton()
        self.reflectance_btn.clicked.connect(self.select_reflectance)
        self.file_layout.addWidget(self.reflectance_btn)

        self.emissivity_btn = QPushButton()
        self.emissivity_btn.clicked.connect(self.select_emissivity)
        self.file_layout.addWidget(self.emissivity_btn)

        self.atm_emissivity_btn = QPushButton()
        self.atm_emissivity_btn.clicked.connect(self.select_atm_emissivity)
        self.file_layout.addWidget(self.atm_emissivity_btn)

        self.file_group.setLayout(self.file_layout)
        layout.addWidget(self.file_group)

        # 功能选择组
        self.func_group = QGroupBox()
        self.func_layout = QVBoxLayout()
        self.func_layout.setSpacing(10)

        self.func_buttons = []
        funcs = [
            ('energy_map', '🗺️ ', self.open_calculating),
            ('cooling_power', '❄️ ', self.open_cooling),
            ('heating_power', '🔥 ', self.open_heating),
            ('wind_cloud', '📈 ', self.open_yuntu),
            ('solar_efficiency', '☀️ ', self.open_heating_vs_solar),
            ('modify_params', '⚙️ ', self.launch_config_editor),
            ('file_converter', '📄 ', self.open_file_processor),
            ('emissivity_solar_cloud', '🌤️ ', self.open_emissivity_solar_cloud),
            ('power_components', '📊 ', self.open_power_components),
        ]

        for key, prefix, func in funcs:
            btn = QPushButton()
            btn.clicked.connect(func)
            self.func_layout.addWidget(btn)
            self.func_buttons.append((btn, key, prefix))

        self.func_group.setLayout(self.func_layout)
        layout.addWidget(self.func_group)

        self.statusBar().showMessage(language_manager.get('info'))
        self.statusBar().setStyleSheet(
            f"background-color: {COLORS['light_bg']}; color: {COLORS['secondary_text']};"
        )

        self.setStyleSheet(STYLE_SHEET)

    def _on_language_combo_changed(self, idx: int):
        lang = self.language_combo.itemData(idx)
        if lang:
            language_manager.set_language(lang)

    def on_language_changed(self, lang: str):
        if hasattr(self, 'language_combo'):
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(0 if lang == 'zh' else 1)
            self.language_combo.blockSignals(False)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(language_manager.get('main_title'))
        if hasattr(self, 'title_label'):
            self.title_label.setText(language_manager.get('main_title'))

        if hasattr(self, 'file_group'):
            self.file_group.setTitle(language_manager.get('select_files'))
        if hasattr(self, 'func_group'):
            self.func_group.setTitle(language_manager.get('select_function'))

        if hasattr(self, 'reflectance_btn'):
            self.reflectance_btn.setText(f"📄 {language_manager.get('select_reflectance')}")
        if hasattr(self, 'emissivity_btn'):
            self.emissivity_btn.setText(f"📊 {language_manager.get('select_emissivity')}")
        if hasattr(self, 'atm_emissivity_btn'):
            self.atm_emissivity_btn.setText(f"🌤️ {language_manager.get('select_atm_transmittance')}")

        if hasattr(self, 'func_buttons'):
            for btn, key, prefix in self.func_buttons:
                btn.setText(f"{prefix}{language_manager.get(key)}")

        try:
            self.statusBar().showMessage(language_manager.get('info'))
        except Exception:
            pass

    def select_reflectance(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, language_manager.get('select_reflectance'), '', 'Text files (*.txt)'
        )
        if file_path:
            self.file_paths['reflectance'] = file_path
            QMessageBox.information(
                self, language_manager.get('info'), f"{language_manager.get('file_selected')}:\n{file_path}"
            )

    def select_emissivity(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, language_manager.get('select_emissivity'), '', 'Text files (*.txt)'
        )
        if file_path:
            self.file_paths['emissivity'] = file_path
            QMessageBox.information(
                self, language_manager.get('info'), f"{language_manager.get('file_selected')}:\n{file_path}"
            )

    def select_atm_emissivity(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(language_manager.get('select_atm_transmittance'))
        dialog.setFixedSize(450, 500)
        layout = QVBoxLayout(dialog)

        label = QLabel(language_manager.get('select_atm_file'))
        layout.addWidget(label)

        default_dir = res_path('default')
        dll_files = []
        try:
            if os.path.exists(default_dir):
                dll_files = sorted([f for f in os.listdir(default_dir) if f.endswith('.dll')])
        except Exception as e:
            print(f"读取 default 目录失败: {e}")

        if not dll_files:
            dll_files = ['1.dll', '2.dll']

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        button_widget = QWidget()
        button_layout = QVBoxLayout(button_widget)
        button_layout.setSpacing(5)

        for dll_file in dll_files:
            file_label = dll_file.replace('.dll', '')

            if '晴' in file_label or 'clear' in file_label.lower() or file_label == '1':
                emoji = '☀️'
            elif '云' in file_label or 'cloud' in file_label.lower() or file_label == '2':
                emoji = '☁️'
            elif '雾' in file_label or 'fog' in file_label.lower():
                emoji = '🌫️'
            elif '城市' in file_label or 'urban' in file_label.lower():
                emoji = '🏙️'
            elif '农村' in file_label or 'rural' in file_label.lower():
                emoji = '🌾'
            elif '海' in file_label or 'sea' in file_label.lower():
                emoji = '🌊'
            elif '污' in file_label or 'polluted' in file_label.lower():
                emoji = '⚠️'
            else:
                emoji = '📄'

            btn = QPushButton(f"{emoji} {file_label}")
            btn.setMinimumHeight(35)
            btn.clicked.connect(lambda checked, fn=dll_file: self._select_atm_file(fn, dialog))
            button_layout.addWidget(btn)

        button_layout.addStretch()
        scroll_area.setWidget(button_widget)
        layout.addWidget(scroll_area)

        dialog.exec_()

    def _select_atm_file(self, file_name: str, dialog: QDialog):
        self.file_paths['atm_emissivity'] = res_path('default', file_name)
        dialog.accept()
        file_label = file_name.replace('.dll', '')
        QMessageBox.information(
            self, language_manager.get('info'), f"{language_manager.get('file_selected')}: {file_label}"
        )

    def check_all_files(self, required_keys: list[str]):
        missing = [k for k in required_keys if k not in self.file_paths or not self.file_paths[k]]
        if missing:
            raise Exception(
                f"{language_manager.get('select_all_files')}. {language_manager.get('missing_files')}: {', '.join(missing)}"
            )

    def open_cooling(self):
        from gui.subwindows import CoolingWindow

        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            CoolingWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def open_calculating(self):
        from gui.subwindows import CalculatingWindow

        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            CalculatingWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def open_heating(self):
        from gui.subwindows import HeatingWindow

        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            HeatingWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def open_yuntu(self):
        from gui.subwindows import WindCoolingPlotWindow

        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            WindCoolingPlotWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def open_heating_vs_solar(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])

            self.calc_thread = CalculationThread(
                main_theoretical_heating_vs_solar, self.file_paths, skip_dialog=True
            )

            def on_finished(result):
                try:
                    results = result['results']
                    T_a_range = result['T_a_range']
                    S_solar_range = result['S_solar_range']

                    fig, ax = plt.subplots(figsize=(8, 6))
                    for i, Ta in enumerate(T_a_range):
                        ax.plot(S_solar_range, results[i, :], label=f"Ta = {Ta:.0f}°C", linewidth=2)
                    ax.set_xlabel('Solar Irradiance (W/m²)', fontsize=12)
                    ax.set_ylabel('Net Radiative Heating Power (W/m²)', fontsize=12)
                    ax.set_title(
                        'Theoretical radiation heating power and solar irradiance relationship\n'
                        '(film temperature=ambient temperature, ΔT=0)',
                        fontsize=14,
                    )
                    ax.legend(); ax.grid(True); fig.tight_layout()

                    dlg = InteractivePlotWindow(fig, parent=self, title='光热VS光照')
                    dlg.exec_()
                except Exception as e:
                    QMessageBox.warning(self, '提示', f"显示图表时出错：{e}")

                try:
                    save_path, _ = QFileDialog.getSaveFileName(self, '保存结果', '', 'CSV files (*.csv)')
                    if save_path:
                        df = pd.DataFrame(
                            results,
                            index=[f"{Ta:.0f}" for Ta in T_a_range],
                            columns=np.round(S_solar_range, 2),
                        )
                        df.index.name = 'Ambient Temperature°C'
                        df.columns.name = 'Solar Irradiance (W/m²)'
                        df.to_csv(save_path)
                        QMessageBox.information(self, '成功', f"结果已保存到 {save_path}")
                except Exception as e:
                    QMessageBox.critical(self, '错误', f"保存数据时出错: {e}")

            def on_error(error_msg: str):
                QMessageBox.critical(self, '错误', f"计算过程中出现错误: {error_msg}")

            self.calc_thread.finished.connect(on_finished)
            self.calc_thread.error.connect(on_error)
            self.calc_thread.start()

        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def launch_config_editor(self):
        from gui.config_editor import launch_config_editor_pyqt

        launch_config_editor_pyqt(self)

    def open_file_processor(self):
        from gui.file_processor import FileProcessorDialog

        FileProcessorDialog(self).exec_()

    def open_power_components(self):
        from gui.subwindows import PowerComponentWindow

        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            PowerComponentWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def open_emissivity_solar_cloud(self):
        from gui.emissivity_cloud import EmissivitySolarCloudDialog

        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            EmissivitySolarCloudDialog(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

