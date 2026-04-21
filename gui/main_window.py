"""Main application window."""

from __future__ import annotations

import json
import os
import sys
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont, QCloseEvent, QDesktopServices
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
from gui.dialogs import CitationDialog
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

        # 加载配置文件
        try:
            from core.config import load_config

            config = load_config(self.file_paths['config'])
        except Exception as e:
            QMessageBox.critical(
                self,
                language_manager.get('error'),
                f"{language_manager.get('calculation_failed')}: {e}",
            )
            sys.exit(1)

        self.init_ui()
        self.retranslate_ui()
        self.load_notice_info()

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
        # Website buttons (left side)
        self.github_btn = QPushButton('🌐')
        self.github_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl('https://github.com/cuity1/Radiation-cooling-and-heating-calculation')
        ))
        self.github_btn.setToolTip('访问GitHub')
        self.github_btn.setFixedWidth(0)
        self.github_btn.setFixedHeight(25)
        self.github_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.2);
            }
        """)
        lang_row.addWidget(self.github_btn)
        self.gitee_btn = QPushButton('📦')
        self.gitee_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl('https://gitee.com/cuity1999/Radiation-cooling-and-heating-calculation')
        ))
        self.gitee_btn.setToolTip('访问Gitee')
        self.gitee_btn.setFixedWidth(0)
        self.gitee_btn.setFixedHeight(25)
        self.gitee_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.2);
            }
        """)
        lang_row.addWidget(self.gitee_btn)
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
            ('modify_params', '⚙️ ', self.launch_config_editor),
            ('file_converter', '📄 ', self.open_file_processor),
        ]

        for key, prefix, func in funcs:
            btn = QPushButton()
            btn.clicked.connect(func)
            self.func_layout.addWidget(btn)
            self.func_buttons.append((btn, key, prefix))

        self.func_group.setLayout(self.func_layout)
        layout.addWidget(self.func_group)

        # Tool box (bottom)
        layout.addStretch()

        self.toolbox_btn = QPushButton()
        self.toolbox_btn.clicked.connect(self.open_toolbox)
        self.toolbox_btn.setMinimumHeight(36)
        layout.addWidget(self.toolbox_btn)

        notice_layout = QVBoxLayout()
        notice_layout.setSpacing(2)
        notice_layout.setContentsMargins(0, 0, 0, 0)

        self.notice_info_label = QLabel("")
        self.notice_info_label.setAlignment(Qt.AlignCenter)
        self.notice_info_label.setStyleSheet(
            f"color: {COLORS['secondary_text']}; font-size: 12px; line-height: 14px; margin: 0; padding: 0;"
        )
        notice_layout.addWidget(self.notice_info_label)

        self.notice_version_label = QLabel("")
        self.notice_version_label.setAlignment(Qt.AlignCenter)
        self.notice_version_label.setStyleSheet(
            f"color: {COLORS['secondary_text']}; font-size: 12px; line-height: 14px; margin: 0; padding: 0;"
        )
        notice_layout.addWidget(self.notice_version_label)

        layout.addLayout(notice_layout)

        self.statusBar().showMessage(language_manager.get('info'))
        self.statusBar().setStyleSheet(
            f"background-color: {COLORS['light_bg']}; color: {COLORS['secondary_text']};"
        )

        self.setStyleSheet(STYLE_SHEET)

    def load_notice_info(self):
        """从远程URL加载公告信息"""
        notice_url = "https://gitee.com/cuity1999/Radiation-cooling-and-heating-calculation/raw/main/notice.json"
        
        try:
            with urlopen(notice_url, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                # 查找info和version项
                info_text = ""
                version_text = ""
                # 当前版本号固定为4.0
                current_version = "4.1"
                
                if 'items' in data:
                    for item in data['items']:
                        if item.get('level') == 'info':
                            info_text = item.get('text', '')
                        elif item.get('level') == 'version':
                            version_text = item.get('text', '')
                
                # 更新标签
                if info_text:
                    self.notice_info_label.setText(info_text)
                
                if version_text:
                    self.notice_version_label.setText(f"now version：{current_version}，{version_text}")
                else:
                    self.notice_version_label.setText(f"now version：{current_version}")
                        
        except (URLError, HTTPError) as e:
            # 网络错误，使用默认值或留空
            print(f"Failed to load notice info: {e}")
            self.notice_info_label.setText("")
            self.notice_version_label.setText("")
        except json.JSONDecodeError as e:
            # JSON解析错误
            print(f"Failed to parse notice JSON: {e}")
            self.notice_info_label.setText("")
            self.notice_version_label.setText("")
        except Exception as e:
            # 其他错误
            print(f"Error loading notice info: {e}")
            self.notice_info_label.setText("")
            self.notice_version_label.setText("")

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

        if hasattr(self, 'toolbox_btn'):
            self.toolbox_btn.setText(f"{language_manager.get('tool_box')} / {language_manager.get('tool_box_en')}")

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

        # Import custom weather DLL
        import_btn = QPushButton(f"📥 {language_manager.get('import_custom_weather_dll')}")
        import_btn.setMinimumHeight(35)
        import_btn.clicked.connect(lambda: self._import_custom_atm_dll(dialog))
        layout.addWidget(import_btn)

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

    def _import_custom_atm_dll(self, dialog: QDialog):
        """Import a custom atmospheric/weather DLL and use it immediately."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            language_manager.get('import_custom_weather_dll'),
            '',
            'DLL files (*.dll)',
        )
        if not file_path:
            return

        self.file_paths['atm_emissivity'] = file_path
        dialog.accept()
        QMessageBox.information(
            self,
            language_manager.get('info'),
            f"{language_manager.get('file_selected')}:\n{file_path}",
        )

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

    def open_angular_power_analysis(self):
        from gui.subwindows import AngularPowerWindow

        try:
            self.check_all_files(['config', 'wavelength', 'emissivity', 'atm_emissivity'])
            AngularPowerWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def open_emissivity_solar_cloud(self):
        from gui.emissivity_cloud import EmissivitySolarCloudDialog

        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            EmissivitySolarCloudDialog(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def open_toolbox(self):
        from gui.toolbox_dialog import ToolBoxDialog

        openers = {
            'wind_cloud': self.open_yuntu,
            'solar_efficiency': self.open_heating_vs_solar,
            'emissivity_solar_cloud': self.open_emissivity_solar_cloud,
            'power_components': self.open_power_components,
            'angular_power': self.open_angular_power_analysis,
        }

        ToolBoxDialog(self, openers=openers).exec_()

    def closeEvent(self, event: QCloseEvent):
        """Override close event to show citation dialog."""
        citation_dialog = CitationDialog(self)
        citation_dialog.exec_()
        event.accept()

