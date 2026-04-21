"""Secondary calculation windows (cooling/heating/map params/wind cloud).

These windows wrap core calculations and provide plotting/export UI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
)

from core.calculations import main_calculating_gui, main_cooling_gui, main_heating_gui
from core.plots import generate_wind_cooling_plot
from gui.i18n import COLORS, language_manager
from gui.threads import CalculationThread
from gui.windows import InteractivePlotWindow
from gui.widgets import STYLE_SHEET


class CalculationWindow(QDialog):
    """Base class for calculation dialogs."""

    # NOTE: Do not put feature-specific methods here (e.g., PowerComponentWindow export).

    @staticmethod
    def _parse_optional_float(widget, default=None):
        if widget is None:
            return default
        text = (widget.text() or '').strip()
        if text == '':
            return default
        return float(text)

    def __init__(self, parent, file_paths: dict, title_key_or_text: str):
        super().__init__(parent)
        language_manager.language_changed.connect(self.on_language_changed)
        self._title_key_or_text = title_key_or_text
        self.setWindowTitle(self._tr_title())
        self.setFixedSize(600, 450)
        self.file_paths = file_paths.copy()
        self.calc_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        self.execute_btn = QPushButton()
        self.execute_btn.clicked.connect(self.run_calculation)
        layout.addWidget(self.execute_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel('')
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.result_label = QLabel('')
        self.result_label.setStyleSheet(f"color: {COLORS['primary_text']}; font-size: 12px;")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        self.setStyleSheet(STYLE_SHEET)
        self.retranslate_ui()

    def run_calculation(self):
        raise NotImplementedError

    def _tr_title(self) -> str:
        key = self._title_key_or_text
        if isinstance(key, str) and key in language_manager.translations.get(language_manager.current_language, {}):
            return language_manager.get(key)
        return key

    def on_language_changed(self, lang: str):
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(self._tr_title())
        self.execute_btn.setText(language_manager.get('execute'))

    def on_calculation_finished(self, result):
        self.execute_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(language_manager.get('calculation_complete'))
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")


    def on_calculation_error(self, error_msg: str):
        self.execute_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(
            self,
            language_manager.get('error'),
            f"{language_manager.get('calculation_failed')}: {error_msg}",
        )
        self.status_label.setText(language_manager.get('calculation_failed'))
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")


class AngularPowerWindow(QDialog):
    """Window for angular power distribution analysis."""
    def __init__(self, parent, file_paths: dict):
        super().__init__(parent)
        self.setWindowTitle(language_manager.get('angular_power_title'))
        self.setFixedSize(550, 300)
        self.file_paths = file_paths.copy()
        self.calc_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Temperature difference input
        h_row = QHBoxLayout()
        h_label = QLabel(language_manager.get('angular_power_delta_t'))
        self.delta_t_input = QLineEdit("0.0")
        self.delta_t_input.setValidator(QDoubleValidator(-100.0, 100.0, 2))
        h_row.addWidget(h_label)
        h_row.addWidget(self.delta_t_input)
        layout.addLayout(h_row)

        self.execute_btn = QPushButton(language_manager.get('angular_power_generate'))
        self.execute_btn.clicked.connect(self.run_calculation)
        layout.addWidget(self.execute_btn)

        self.status_label = QLabel('')
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.setStyleSheet(STYLE_SHEET)

    def run_calculation(self):
        try:
            delta_t = float(self.delta_t_input.text().strip())
            self.execute_btn.setEnabled(False)
            self.status_label.setText(language_manager.get('angular_power_calculating'))
            self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")

            from core.calculations import calculate_angular_power
            
            self.calc_thread = CalculationThread(
                calculate_angular_power,
                self.file_paths,
                temp_diff_c=delta_t
            )
            self.calc_thread.finished.connect(self.on_calculation_finished)
            self.calc_thread.error.connect(self.on_calculation_error)
            self.calc_thread.start()

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"无效的输入值: {e}")
            self.execute_btn.setEnabled(True)
        except Exception as e:
            self.on_calculation_error(str(e))

    def on_calculation_finished(self, result):
        self.execute_btn.setEnabled(True)
        self.status_label.setText(language_manager.get('angular_power_done'))
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        self.plot_results(result)

    def on_calculation_error(self, error_msg: str):
        self.execute_btn.setEnabled(True)
        QMessageBox.critical(self, language_manager.get('error'), f"{language_manager.get('calculation_failed')}: {error_msg}")
        self.status_label.setText(language_manager.get('angular_power_failed'))
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")

    def plot_results(self, result):
        theta_deg = result['theta_deg']
        power_density = result['power_density_per_sr']

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

        # Plot 1: Cartesian plot
        ax1.plot(theta_deg, power_density, lw=2)
        ax1.set_xlabel("Zenith angle (deg)")
        ax1.set_ylabel("Radiative power density (W/m²/sr)")
        ax1.set_title("Angular radiative power density")
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax1.set_xlim(0, 90)

        # Plot 2: Polar plot
        ax2.remove()
        ax2 = fig.add_subplot(1, 2, 2, projection='polar')
        theta_rad = np.deg2rad(theta_deg)
        ax2.plot(theta_rad, power_density, lw=2)
        ax2.set_theta_zero_location('N')  # 0 degrees at the top
        ax2.set_theta_direction(-1)  # Clockwise
        ax2.set_rlabel_position(90)
        ax2.set_thetagrids(np.arange(0, 91, 15))
        ax2.set_title("Hemispherical angular distribution", pad=20)

        fig.tight_layout()

        dlg = InteractivePlotWindow(fig, parent=self, title='Angular Profile')
        dlg.exec_()


class CoolingWindow(CalculationWindow):
    def __init__(self, parent, file_paths: dict):
        self.angle_steps = 2000
        super().__init__(parent, file_paths, 'cooling_power')

    def init_ui(self):
        super().init_ui()

        # precision selector
        precision_row = QHBoxLayout()
        precision_label = QLabel(language_manager.get('calculation_precision') + ':')
        self.precision_combo = QComboBox()
        self.precision_combo.addItem(language_manager.get('precision_low'), 1000)
        self.precision_combo.addItem(language_manager.get('precision_medium'), 2000)
        self.precision_combo.addItem(language_manager.get('precision_high'), 5000)
        self.precision_combo.setCurrentIndex(1)

        precision_row.addWidget(precision_label)
        precision_row.addWidget(self.precision_combo)
        precision_row.addStretch()

        # phase-change inputs
        phase_row1 = QHBoxLayout()
        phase_row1.addWidget(QLabel(language_manager.get('phase_temp') + ':'))
        self.phase_temp_input = QLineEdit()
        self.phase_temp_input.setPlaceholderText('e.g. 25')
        phase_row1.addWidget(self.phase_temp_input)

        phase_row2 = QHBoxLayout()
        phase_row2.addWidget(QLabel(language_manager.get('phase_power') + ':'))
        self.phase_power_input = QLineEdit()
        self.phase_power_input.setPlaceholderText('e.g. 50')
        phase_row2.addWidget(self.phase_power_input)

        phase_row3 = QHBoxLayout()
        phase_row3.addWidget(QLabel(language_manager.get('phase_width') + ':'))
        self.phase_width_input = QLineEdit()
        self.phase_width_input.setPlaceholderText('e.g. 2')
        self.phase_width_input.setToolTip('相变功率从相变温度开始线性爬升，到 (T_phase + 展宽) 达到最大值，并在更高温度保持最大值')
        phase_row3.addWidget(self.phase_width_input)

        # debug checkbox
        debug_row = QHBoxLayout()
        self.debug_checkbox = QCheckBox(language_manager.get('debug_print'))
        self.debug_checkbox.setChecked(False)
        debug_row.addWidget(self.debug_checkbox)
        debug_row.addStretch()

        convection_row = QHBoxLayout()
        self.convection_checkbox = QCheckBox("启用自然对流换热")
        self.convection_checkbox.setChecked(True)
        convection_row.addWidget(self.convection_checkbox)
        convection_row.addStretch()

        # insert below execute button
        self.layout().insertLayout(1, precision_row)
        self.layout().insertLayout(2, debug_row)
        self.layout().insertLayout(3, convection_row)
        self.layout().insertLayout(4, phase_row1)
        self.layout().insertLayout(5, phase_row2)
        self.layout().insertLayout(6, phase_row3)

    def retranslate_ui(self):
        super().retranslate_ui()
        if hasattr(self, 'precision_combo'):
            self.precision_combo.blockSignals(True)
            self.precision_combo.setItemText(0, language_manager.get('precision_low'))
            self.precision_combo.setItemText(1, language_manager.get('precision_medium'))
            self.precision_combo.setItemText(2, language_manager.get('precision_high'))
            self.precision_combo.blockSignals(False)

        # phase labels
        # (we used QLabel(...) inline, so nothing to update here other than placeholders)
        if hasattr(self, 'phase_temp_input'):
            self.phase_temp_input.setPlaceholderText('e.g. 25')
        if hasattr(self, 'phase_power_input'):
            self.phase_power_input.setPlaceholderText('e.g. 50')
        if hasattr(self, 'phase_width_input'):
            self.phase_width_input.setPlaceholderText('e.g. 2')

    def run_calculation(self):
        self.execute_btn.setEnabled(False)
        self.status_label.setText(language_manager.get('calculating_msg'))
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.angle_steps = int(self.precision_combo.currentData() or 2000)

        # Phase-change params (optional)
        phase_temp_c = self._parse_optional_float(getattr(self, 'phase_temp_input', None))
        phase_power_wm2 = self._parse_optional_float(getattr(self, 'phase_power_input', None), default=0.0) or 0.0
        phase_half_width_c = self._parse_optional_float(getattr(self, 'phase_width_input', None), default=0.0) or 0.0

        debug = bool(getattr(self, 'debug_checkbox', None) and self.debug_checkbox.isChecked())

        enable_nat_conv = bool(getattr(self, 'convection_checkbox', None) and self.convection_checkbox.isChecked())

        self.calc_thread = CalculationThread(
            main_cooling_gui,
            self.file_paths,
            angle_steps=self.angle_steps,
            skip_dialog=True,
            enable_natural_convection=enable_nat_conv,
            debug=debug,
            phase_temp_c=phase_temp_c,
            phase_power_wm2=phase_power_wm2,
            phase_half_width_c=phase_half_width_c,
        )
        self.calc_thread.finished.connect(self.on_calculation_finished)
        self.calc_thread.error.connect(self.on_calculation_error)
        self.calc_thread.start()

    def on_calculation_finished(self, result):
        super().on_calculation_finished(result)
        power_0 = result['Power_0']
        self.result_label.setText(f"{language_manager.get('cooling_power_result')} = {power_0:.4f} W/m²")
        self.show_result_dialog(result)

    def show_result_dialog(self, result):
        dialog = QDialog(self)
        dialog.setWindowTitle(language_manager.get('choose_action'))
        dialog.setFixedSize(350, 200)
        layout = QVBoxLayout(dialog)

        plot_btn = QPushButton(language_manager.get('plot_chart'))
        plot_btn.clicked.connect(lambda: self.plot_results(result))
        layout.addWidget(plot_btn)

        export_btn = QPushButton(language_manager.get('export_data'))
        export_btn.clicked.connect(lambda: self.export_data(result))
        layout.addWidget(export_btn)

        cancel_btn = QPushButton(language_manager.get('cancel'))
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)

        dialog.setStyleSheet(STYLE_SHEET)
        dialog.exec_()

    def plot_results(self, result):
        from itertools import cycle

        results = result['results']
        T_film = result['T_film']
        T_a1 = result['T_a1']
        HC_VALUES = result['HC_VALUES']

        fig = plt.figure(figsize=(10, 6))
        num_lines = len(HC_VALUES)
        cmap = plt.get_cmap('tab10')
        colors = [cmap(i % cmap.N) for i in range(num_lines)]
        linestyles = cycle(['-', '--', '-.', ':'])

        # Use absolute film temperature on X-axis
        T_film_abs_c = T_film

        for hc_index in range(num_lines):
            color = colors[hc_index]
            linestyle = next(linestyles)
            plt.plot(
                T_film_abs_c,
                results[:, hc_index],
                color=color,
                linestyle=linestyle,
                linewidth=2,
                label=f'h_c={HC_VALUES[hc_index]} W m⁻² K⁻¹',
            )

        plt.xlabel('T_film (°C)', fontsize=12)
        plt.ylabel('Cooling Power (W m⁻²)', fontsize=12)
        plt.title('Radiative cooling power vs film temperature', fontsize=14)
        plt.legend(); plt.grid(True); plt.tight_layout()

        # Use interactive Qt dialog instead of blocking plt.show()
        dlg = InteractivePlotWindow(fig, parent=self, title=language_manager.get('preview_chart'))
        dlg.exec_()

    def export_data(self, result):
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, language_manager.get('save_file'), '', 'CSV files (*.csv)')
            if save_path:
                results = result['results']
                T_film = result['T_film']
                T_a1 = result['T_a1']
                HC_VALUES = result['HC_VALUES']

                export_data_dict = {'T_film (°C)': T_film}
                for hc_index, hc_value in enumerate(HC_VALUES):
                    export_data_dict[f'Cooling_Power_hc_{hc_value}'] = results[:, hc_index]

                df_export = pd.DataFrame(export_data_dict)
                df_export.to_csv(save_path, index=False)
                QMessageBox.information(self, language_manager.get('success'), f"{language_manager.get('saved_to')} {save_path}")
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"保存数据时出错: {e}")


class CalculatingWindow(CalculationWindow):
    def __init__(self, parent, file_paths: dict):
        super().__init__(parent, file_paths, 'map_params_calculation')

    def init_ui(self):
        super().init_ui()
        
        # 添加"打开对比计算器"按钮
        self.comparison_btn = QPushButton()
        self.comparison_btn.clicked.connect(self.open_material_comparison)
        self.comparison_btn.setStyleSheet("font-size: 14px; padding: 8px;")
        # 在布局中插入按钮（在执行按钮之后）
        self.layout().insertWidget(1, self.comparison_btn)
        self.retranslate_ui()

    def retranslate_ui(self):
        super().retranslate_ui()
        if hasattr(self, 'comparison_btn'):
            self.comparison_btn.setText(language_manager.get('open_comparison_calculator'))

    def open_material_comparison(self):
        """打开材料对比计算器（独立进程模式）。"""
        try:
            import sys
            import os
            import subprocess
            import platform
            from pathlib import Path

            # 在开发环境下，直接用当前解释器 + 脚本路径启动
            if not getattr(sys, 'frozen', False):
                current_file = Path(__file__).resolve()
                project_root = current_file.parent.parent
                comparison_script = project_root / 'material_comparison_tool' / 'examples' / 'compare_materials.py'
                if not comparison_script.exists():
                    QMessageBox.critical(
                        self,
                        language_manager.get('error'),
                        f"找不到对比计算器脚本：{comparison_script}\n"
                        f"请确保 material_comparison_tool/examples/compare_materials.py 文件存在。"
                    )
                    return

                env = os.environ.copy()
                pythonpath = env.get('PYTHONPATH', '')
                pythonpath = f"{str(project_root)}{os.pathsep}{pythonpath}" if pythonpath else str(project_root)
                env['PYTHONPATH'] = pythonpath

                subprocess.Popen(
                    [sys.executable, str(comparison_script)],
                    cwd=str(project_root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return

            # 打包后的 onefile：重新调用自身 exe，并带上专用参数，让主进程分支到 compare GUI
            python_exe = sys.executable  # 即当前 exe
            creation_flags = 0
            popen_kwargs = {
                "cwd": os.getcwd(),
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if platform.system() == 'Windows':
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                popen_kwargs["creationflags"] = creation_flags
            else:
                popen_kwargs["start_new_session"] = True

            subprocess.Popen(
                [python_exe, '--compare-materials'],
                **popen_kwargs,
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                language_manager.get('error'),
                f"无法打开对比计算器：{str(e)}"
            )
            import traceback
            traceback.print_exc()



    def run_calculation(self):
        self.execute_btn.setEnabled(False)
        self.status_label.setText(language_manager.get('calculating_msg'))
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.calc_thread = CalculationThread(main_calculating_gui, self.file_paths)
        self.calc_thread.finished.connect(self.on_calculation_finished)
        self.calc_thread.error.connect(self.on_calculation_error)
        self.calc_thread.start()

    def on_calculation_finished(self, result):
        super().on_calculation_finished(result)
        avg_emissivity, R_sol, R_sol1 = result
        self.result_label.setText(
            f"{language_manager.get('avg_emissivity')} = {avg_emissivity:.4f}\n"
            f"{language_manager.get('solar_reflectance')} = {R_sol:.4f}\n"
            f"{language_manager.get('visible_reflectance')} = {R_sol1:.4f}\n"
            f"{language_manager.get('map_plot_contact')}"
        )


class HeatingWindow(CalculationWindow):
    def __init__(self, parent, file_paths: dict):
        self.angle_steps = 2000
        super().__init__(parent, file_paths, 'heating_power_calculation')

    def init_ui(self):
        super().init_ui()

        precision_row = QHBoxLayout()
        precision_label = QLabel(language_manager.get('calculation_precision') + ':')
        self.precision_combo = QComboBox()
        self.precision_combo.addItem(language_manager.get('precision_low'), 1000)
        self.precision_combo.addItem(language_manager.get('precision_medium'), 2000)
        self.precision_combo.addItem(language_manager.get('precision_high'), 5000)
        self.precision_combo.setCurrentIndex(1)

        precision_row.addWidget(precision_label)
        precision_row.addWidget(self.precision_combo)
        precision_row.addStretch()

        # phase-change inputs
        phase_row1 = QHBoxLayout()
        phase_row1.addWidget(QLabel(language_manager.get('phase_temp') + ':'))
        self.phase_temp_input = QLineEdit()
        self.phase_temp_input.setPlaceholderText('e.g. 25')
        phase_row1.addWidget(self.phase_temp_input)

        phase_row2 = QHBoxLayout()
        phase_row2.addWidget(QLabel(language_manager.get('phase_power') + ':'))
        self.phase_power_input = QLineEdit()
        self.phase_power_input.setPlaceholderText('e.g. 50')
        phase_row2.addWidget(self.phase_power_input)

        phase_row3 = QHBoxLayout()
        phase_row3.addWidget(QLabel(language_manager.get('phase_width') + ':'))
        self.phase_width_input = QLineEdit()
        self.phase_width_input.setPlaceholderText('e.g. 1')
        phase_row3.addWidget(self.phase_width_input)

        # debug checkbox
        debug_row = QHBoxLayout()
        self.debug_checkbox = QCheckBox(language_manager.get('debug_print'))
        self.debug_checkbox.setChecked(False)
        debug_row.addWidget(self.debug_checkbox)
        debug_row.addStretch()

        convection_row = QHBoxLayout()
        self.convection_checkbox = QCheckBox("启用自然对流换热")
        self.convection_checkbox.setChecked(True)
        convection_row.addWidget(self.convection_checkbox)
        convection_row.addStretch()

        self.layout().insertLayout(1, precision_row)
        self.layout().insertLayout(2, debug_row)
        self.layout().insertLayout(3, convection_row)
        self.layout().insertLayout(4, phase_row1)
        self.layout().insertLayout(5, phase_row2)
        self.layout().insertLayout(6, phase_row3)

    def retranslate_ui(self):
        super().retranslate_ui()
        if hasattr(self, 'precision_combo'):
            self.precision_combo.blockSignals(True)
            self.precision_combo.setItemText(0, language_manager.get('precision_low'))
            self.precision_combo.setItemText(1, language_manager.get('precision_medium'))
            self.precision_combo.setItemText(2, language_manager.get('precision_high'))
            self.precision_combo.blockSignals(False)

    def run_calculation(self):
        self.execute_btn.setEnabled(False)
        self.status_label.setText(language_manager.get('calculating_msg'))
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.angle_steps = int(self.precision_combo.currentData() or 2000)

        # Phase-change params (optional)
        phase_temp_c = self._parse_optional_float(getattr(self, 'phase_temp_input', None))
        phase_power_wm2 = self._parse_optional_float(getattr(self, 'phase_power_input', None), default=0.0) or 0.0
        phase_half_width_c = self._parse_optional_float(getattr(self, 'phase_width_input', None), default=0.0) or 0.0

        enable_nat_conv = bool(getattr(self, 'convection_checkbox', None) and self.convection_checkbox.isChecked())

        self.calc_thread = CalculationThread(
            main_heating_gui,
            self.file_paths,
            angle_steps=self.angle_steps,
            skip_dialog=True,
            enable_natural_convection=enable_nat_conv,
            phase_temp_c=phase_temp_c,
            phase_power_wm2=phase_power_wm2,
            phase_half_width_c=phase_half_width_c,
        )
        self.calc_thread.finished.connect(self.on_calculation_finished)
        self.calc_thread.error.connect(self.on_calculation_error)
        self.calc_thread.start()

    def on_calculation_finished(self, result):
        super().on_calculation_finished(result)
        power_0 = result['Power_0']
        self.result_label.setText(f"{language_manager.get('heating_power_result')} = {power_0:.4f} W/m²")
        self.show_result_dialog(result)

    def show_result_dialog(self, result):
        dialog = QDialog(self)
        dialog.setWindowTitle(language_manager.get('choose_action'))
        dialog.setFixedSize(350, 200)
        layout = QVBoxLayout(dialog)

        plot_btn = QPushButton(language_manager.get('plot_chart'))
        plot_btn.clicked.connect(lambda: self.plot_results(result))
        layout.addWidget(plot_btn)

        export_btn = QPushButton(language_manager.get('export_data'))
        export_btn.clicked.connect(lambda: self.export_data(result))
        layout.addWidget(export_btn)

        cancel_btn = QPushButton(language_manager.get('cancel'))
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)

        dialog.setStyleSheet(STYLE_SHEET)
        dialog.exec_()

    def plot_results(self, result):
        from itertools import cycle

        results = result['results']
        T_film = result['T_film']
        T_a1 = result['T_a1']
        HC_VALUES = result['HC_VALUES']

        fig = plt.figure(figsize=(10, 6))
        num_lines = len(HC_VALUES)
        cmap = plt.get_cmap('tab10')
        colors = [cmap(i % cmap.N) for i in range(num_lines)]
        linestyles = cycle(['-', '--', '-.', ':'])

        # Use absolute film temperature on X-axis
        T_film_abs_c = T_film

        for hc_index in range(num_lines):
            color = colors[hc_index]
            linestyle = next(linestyles)
            plt.plot(
                T_film_abs_c,
                results[:, hc_index],
                color=color,
                linestyle=linestyle,
                linewidth=2,
                label=f'h_c={HC_VALUES[hc_index]} W m⁻² K⁻¹',
            )

        plt.xlabel('T_film (°C)', fontsize=12)
        plt.ylabel('Heating Power (W m⁻²)', fontsize=12)
        plt.title('Radiative Heating power vs film temperature', fontsize=14)
        plt.legend(); plt.grid(True); plt.tight_layout()

        # Use interactive Qt dialog instead of blocking plt.show()
        dlg = InteractivePlotWindow(fig, parent=self, title=language_manager.get('preview_chart'))
        dlg.exec_()

    def export_data(self, result):
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, language_manager.get('save_file'), '', 'CSV files (*.csv)')
            if save_path:
                results = result['results']
                T_film = result['T_film']
                T_a1 = result['T_a1']
                HC_VALUES = result['HC_VALUES']

                export_data_dict = {'T_film (°C)': T_film}
                for hc_index, hc_value in enumerate(HC_VALUES):
                    export_data_dict[f'Heating_Power_hc_{hc_value}'] = results[:, hc_index]

                df_export = pd.DataFrame(export_data_dict)
                df_export.to_csv(save_path, index=False)
                QMessageBox.information(self, language_manager.get('success'), f"{language_manager.get('saved_to')} {save_path}")
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"保存数据时出错: {e}")


class PowerComponentWindow(QDialog):
    def __init__(self, parent, file_paths: dict):
        super().__init__(parent)
        self.setWindowTitle(language_manager.get('power_components'))
        self.setFixedSize(550, 260)
        self.file_paths = file_paths.copy()
        self.calc_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # 等效导热/对流换热系数输入
        h_row = QHBoxLayout()
        h_label = QLabel("Equivalent heat transfer coefficient (W/m²·K):")
        self.h_input = QLineEdit("5.0")
        self.h_input.setValidator(QDoubleValidator(0.1, 100.0, 2))
        h_row.addWidget(h_label)
        h_row.addWidget(self.h_input)
        layout.addLayout(h_row)

        # 计算按钮
        self.calculate_btn = QPushButton("Calculate and plot power components")
        self.calculate_btn.clicked.connect(self.run_calculation)
        layout.addWidget(self.calculate_btn)

        # 导出按钮（计算完成后可用）
        self.export_btn = QPushButton("Export plot data (CSV)")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_data)
        layout.addWidget(self.export_btn)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.setStyleSheet(STYLE_SHEET)

    def run_calculation(self):
        try:
            h_cond = float(self.h_input.text().strip())
            if h_cond <= 0:
                raise ValueError("换热系数必须大于零")

            self.calculate_btn.setEnabled(False)
            self.status_label.setText("Calculating...")
            self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")

            from core.calculations import main_power_components_gui
            
            self.calc_thread = CalculationThread(
                main_power_components_gui,
                self.file_paths,
                h_cond_wm2k=h_cond,
                enable_natural_convection=False,
            )
            self.calc_thread.finished.connect(self.on_calculation_finished)
            self.calc_thread.error.connect(self.on_calculation_error)
            self.calc_thread.start()

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"无效的输入值: {e}")
            self.calculate_btn.setEnabled(True)
        except Exception as e:
            self.on_calculation_error(str(e))

    def on_calculation_finished(self, result):
        try:
            self.calculate_btn.setEnabled(True)
            if hasattr(self, 'export_btn'):
                self.export_btn.setEnabled(True)
            self._last_result = result

            self.status_label.setText("计算完成")
            self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
            
            self.plot_components(result)
            
        except Exception as e:
            self.on_calculation_error(f"绘图时出错: {e}")

    def plot_components(self, result):
        components = result['components']
        T_film = result['T_film']
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 绘制各分量曲线
        # Plot each component
        ax.plot(T_film, components['p_r'], 'r-', label='p_r (Outgoing Radiation)')
        ax.plot(T_film, components['p_a'], 'b-', label='p_a (Atmospheric Radiation)')
        if 'P_solar' in components:
            ax.plot(T_film, components['P_solar'], 'y--', alpha=0.7, label='P_solar (Solar Irradiance)')
        ax.plot(T_film, components['Q_solar'], 'y-', label='Q_solar (Solar Absorption)')
        ax.plot(T_film, components['P_phase'], 'm-', label='P_phase (Phase-Change Power)')

        # Convective heat flux decomposition
        if 'Q_nat' in components:
            ax.plot(T_film, components['Q_nat'], color='c', linestyle='--', label='Q_nat (Natural Convection)')
        if 'Q_cond' in components:
            ax.plot(T_film, components['Q_cond'], color='tab:orange', linestyle='--', label='Q_cond (Equivalent Conduction)')

        ax.plot(T_film, components['Q_conv'], 'g-', label='Q_conv = Q_nat + Q_cond')

        # Plot net power
        ax.plot(T_film, components['p_net'], 'k--', linewidth=2, label='p_net (Net Power)')
        
        # 添加零线
        ax.axhline(0, color='gray', linestyle='-', alpha=0.3)
        
        ax.set_xlabel('Film Temperature, T_film (°C)')
        ax.set_ylabel('Power Density (W/m²)')
        ax.set_title('Radiative Cooling Power Components vs. Film Temperature')
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.3)
        
        # 使用交互式绘图窗口显示
        dlg = InteractivePlotWindow(fig, parent=self, title='Power Component Curves')
        dlg.exec_()
        
    def export_data(self):
        """Export last computed power-component curves to CSV."""
        try:
            result = getattr(self, '_last_result', None)
            if result is None:
                QMessageBox.information(self, 'Info', 'No data to export. Please calculate first.')
                return

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                'Save CSV',
                '',
                'CSV files (*.csv)',
            )
            if not save_path:
                return

            components = result['components']
            T_film = result['T_film']

            export_dict = {'T_film (°C)': T_film}
            for key in [
                'p_r',
                'p_a',
                'P_solar',
                'Q_solar',
                'P_phase',
                'Q_nat',
                'Q_cond',
                'Q_conv',
                'p_net',
            ]:
                if key in components:
                    export_dict[key] = components[key]

            df = pd.DataFrame(export_dict)
            df.to_csv(save_path, index=False)
            QMessageBox.information(
                self,
                language_manager.get('success'),
                f"{language_manager.get('saved_to')} {save_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"Export failed: {e}")

    def on_calculation_error(self, error_msg: str):
        self.calculate_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"计算过程中出现错误: {error_msg}")
        self.status_label.setText("计算失败")
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")


class WindCoolingPlotWindow(QDialog):
    def __init__(self, parent, file_paths: dict):
        super().__init__(parent)
        self.setWindowTitle(language_manager.get('wind_cloud_title'))
        self.setFixedSize(550, 250)
        self.file_paths = file_paths.copy()
        self.calc_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Use S_solar from config.ini (no manual input)
        try:
            from core.config import load_config

            cfg = load_config(self.file_paths['config'])
            s_solar_cfg = float(cfg['S_solar'])
        except Exception:
            s_solar_cfg = None

        if s_solar_cfg is None:
            label_text = f"{language_manager.get('info')}: S_solar 将从 config.ini 自动读取"
        else:
            label_text = f"{language_manager.get('info')}: 当前太阳辐照度 S_solar = {s_solar_cfg:.2f} W/m² (来自 config.ini)"

        label = QLabel(label_text)
        label.setWordWrap(True)
        layout.addWidget(label)

        self.execute_btn = QPushButton(language_manager.get('generate_cloud_map'))
        self.execute_btn.clicked.connect(self.run_wind_cooling_plot)
        layout.addWidget(self.execute_btn)

        self.status_label = QLabel('')
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.setStyleSheet(STYLE_SHEET)

    def run_wind_cooling_plot(self):
        try:
            self.execute_btn.setEnabled(False)
            self.status_label.setText(language_manager.get('calculating_msg'))
            self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")

            # S_solar will be read from config.ini inside generate_wind_cooling_plot
            self.calc_thread = CalculationThread(
                generate_wind_cooling_plot, self.file_paths, S_solar=None, skip_dialog=True
            )
            self.calc_thread.finished.connect(self.on_plot_finished)
            self.calc_thread.error.connect(self.on_plot_error)
            self.calc_thread.start()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

    def on_plot_finished(self, result):
        self.execute_btn.setEnabled(True)
        self.status_label.setText(language_manager.get('calculation_complete'))
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")

        dialog = QDialog(self)
        dialog.setWindowTitle(language_manager.get('choose_action'))
        dialog.setFixedSize(350, 200)
        vbox = QVBoxLayout(dialog)

        preview_btn = QPushButton(language_manager.get('preview'))
        preview_btn.clicked.connect(lambda: [self.preview_wind_cooling_plot(result), dialog.accept()])
        vbox.addWidget(preview_btn)

        export_btn = QPushButton(language_manager.get('export_data'))
        export_btn.clicked.connect(lambda: [self.export_wind_cooling_data(result), dialog.accept()])
        vbox.addWidget(export_btn)

        cancel_btn = QPushButton(language_manager.get('cancel'))
        cancel_btn.clicked.connect(dialog.reject)
        vbox.addWidget(cancel_btn)

        dialog.setStyleSheet(STYLE_SHEET)
        dialog.exec_()

    def preview_wind_cooling_plot(self, result):
        try:
            from matplotlib.colors import LinearSegmentedColormap
            from core.config import load_config
            from core.physics import calculate_convection_coefficient

            delta_T_values = result['delta_T_values']
            emissivity_variable = result['emissivity_variable']
            wind = result['wind']

            # 兼容旧版本：如果结果中没有 h_conv，则根据当前 ΔT 与风速重算
            hc_values_matrix = result.get('hc_values_matrix')
            if hc_values_matrix is None:
                config = load_config(self.file_paths['config'])
                T_a1 = config['T_a1']
                T_a = T_a1 + 273.15
                hc_values_matrix = np.zeros_like(delta_T_values)
                for i, _ in enumerate(emissivity_variable):
                    for j, w in enumerate(wind):
                        dt = delta_T_values[i, j]
                        if np.isnan(dt):
                            hc_values_matrix[i, j] = np.nan
                        else:
                            hc_values_matrix[i, j] = calculate_convection_coefficient(w, dt, T_a)

            # 自定义蓝-白-红渐变色，和旧脚本保持一致风格
            colors = [(0, 'darkblue'), (0.25, 'blue'), (0.5, 'white'), (0.75, 'red'), (1, 'darkred')]
            cm = LinearSegmentedColormap.from_list('temp_diff', colors, N=100)

            # 读取 S_solar 以用于总标题
            try:
                cfg = load_config(self.file_paths['config'])
                S_solar = float(cfg.get('S_solar', 0.0))
            except Exception:
                S_solar = None

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            X, Y = np.meshgrid(wind, emissivity_variable)

            # 左：温度差云图
            cp1 = ax1.contourf(X, Y, delta_T_values, levels=100, cmap=cm, alpha=0.9)
            contours1 = ax1.contour(X, Y, delta_T_values, levels=10, colors='black', alpha=0.5, linewidths=0.5)
            ax1.clabel(contours1, inline=True, fontsize=8, fmt='%.1f')
            cbar1 = fig.colorbar(cp1, ax=ax1, pad=0.01)
            cbar1.set_label('ΔT (°C)', fontsize=12)
            ax1.set_xlabel('Wind speed (m/s)', fontsize=12)
            ax1.set_ylabel('Atmospheric emissivity', fontsize=12)
            ax1.set_title('Temperature Difference', fontsize=14)
            ax1.grid(True, linestyle='--', alpha=0.6)

            # 右：对流换热系数云图
            cp2 = ax2.contourf(X, Y, hc_values_matrix, levels=100, cmap='viridis', alpha=0.9)
            contours2 = ax2.contour(X, Y, hc_values_matrix, levels=10, colors='black', alpha=0.5, linewidths=0.5)
            ax2.clabel(contours2, inline=True, fontsize=8, fmt='%.1f')
            cbar2 = fig.colorbar(cp2, ax=ax2, pad=0.01)
            cbar2.set_label('h_conv (W/m²·K)', fontsize=12)
            ax2.set_xlabel('Wind speed (m/s)', fontsize=12)
            ax2.set_ylabel('Atmospheric emissivity', fontsize=12)
            ax2.set_title('Convection Coefficient', fontsize=14)
            ax2.grid(True, linestyle='--', alpha=0.6)

            if S_solar is not None:
                fig.suptitle(f'Wind Speed and Cooling Efficiency (S_solar = {S_solar:.1f} W/m²)', fontsize=16)

            fig.tight_layout()

            dlg = InteractivePlotWindow(fig, parent=self, title=language_manager.get('wind_cloud_title'))
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"绘图时出错: {e}")

    def export_wind_cooling_data(self, result):
        try:
            from core.config import load_config
            from core.physics import calculate_convection_coefficient
            import os

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                language_manager.get('save_results_file'),
                '',
                'Excel files (*.xlsx);;CSV files (*.csv)',
            )
            if not save_path:
                return

            delta_T_values = result['delta_T_values']
            emissivity_variable = result['emissivity_variable']
            wind = result['wind']

            # 同 preview，一并得到 h_conv 矩阵，兼容无 hc_values_matrix 的情况
            hc_values_matrix = result.get('hc_values_matrix')
            if hc_values_matrix is None:
                cfg = load_config(self.file_paths['config'])
                T_a1 = cfg['T_a1']
                T_a = T_a1 + 273.15
                hc_values_matrix = np.zeros_like(delta_T_values)
                for i, _ in enumerate(emissivity_variable):
                    for j, w in enumerate(wind):
                        dt = delta_T_values[i, j]
                        if np.isnan(dt):
                            hc_values_matrix[i, j] = np.nan
                        else:
                            hc_values_matrix[i, j] = calculate_convection_coefficient(w, dt, T_a)

            # 目标导出为带两个 sheet 的 Excel（与旧版保持功能一致）
            root, ext = os.path.splitext(save_path)
            if ext.lower() != '.xlsx':
                save_path = root + '.xlsx'

            df_temp = pd.DataFrame(
                delta_T_values,
                index=np.round(emissivity_variable, 3),
                columns=np.round(wind, 3),
            )
            df_temp.index.name = 'emissivity'
            df_temp.columns.name = 'wind_speed'

            df_hconv = pd.DataFrame(
                hc_values_matrix,
                index=np.round(emissivity_variable, 3),
                columns=np.round(wind, 3),
            )
            df_hconv.index.name = 'emissivity'
            df_hconv.columns.name = 'wind_speed'

            with pd.ExcelWriter(save_path) as writer:
                df_temp.to_excel(writer, sheet_name='Temperature_Difference')
                df_hconv.to_excel(writer, sheet_name='Convection_Coefficient')

            QMessageBox.information(
                self,
                language_manager.get('success'),
                f"{language_manager.get('saved_to')} {save_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"保存数据时出错: {e}")

    def on_plot_error(self, error_msg: str):
        self.execute_btn.setEnabled(True)
        QMessageBox.critical(self, language_manager.get('error'), f"计算过程中出现错误: {error_msg}")
        self.status_label.setText(language_manager.get('calculation_failed'))
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")

