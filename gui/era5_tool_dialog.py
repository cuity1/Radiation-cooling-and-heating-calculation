"""ERA5 radiative cooling tool dialog."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.era5_rc_tool import (
    Era5ComputeParams,
    Era5DownloadParams,
    compute_radiative_cooling_from_merged_csv,
    download_era5_to_dir,
    merge_weather_csvs,
)
from gui.i18n import COLORS, language_manager
from gui.widgets import STYLE_SHEET


def _safe_float(text: str, default: float) -> float:
    try:
        return float(str(text).strip())
    except (ValueError, TypeError):
        return default


class Era5ToolDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("原位辐射制冷/光热实验")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(STYLE_SHEET)

        # Define the fixed output directory
        self.base_output_dir = os.path.join(os.getcwd(), "output")
        Path(self.base_output_dir).mkdir(parents=True, exist_ok=True)

        self._init_ui()
        self._connect_signals()
        self.retranslate_ui()

        # Fixed output dir shown to user
        self.output_dir_edit.setText(self.base_output_dir)

        # Connect language change signal
        language_manager.language_changed.connect(self.retranslate_ui)

    def _set_busy(self, busy: bool):
        state = False if busy else True
        for b in (getattr(self, 'init_btn', None), getattr(self, 'download_btn', None), getattr(self, 'merge_btn', None), getattr(self, 'compute_btn', None)):
            if b is not None:
                b.setEnabled(state)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Download section
        download_group = QGroupBox()
        download_layout = QFormLayout()
        download_group.setLayout(download_layout)

        # Date range
        date_layout = QHBoxLayout()
        self.start_date_edit = QLineEdit("2025-07-01")
        self.start_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.end_date_edit = QLineEdit("2025-07-02")
        self.end_date_edit.setPlaceholderText("YYYY-MM-DD")
        date_layout.addWidget(QLabel("从"))
        date_layout.addWidget(self.start_date_edit)
        date_layout.addWidget(QLabel("到"))
        date_layout.addWidget(self.end_date_edit)
        date_layout.addStretch()
        download_layout.addRow("日期范围:", date_layout)

        # Location
        loc_layout = QHBoxLayout()
        self.lon_edit = QLineEdit("117.2695")
        self.lon_edit.setPlaceholderText("经度 (度)")
        self.lat_edit = QLineEdit("31.8369")
        self.lat_edit.setPlaceholderText("纬度 (度)")
        self.tz_edit = QLineEdit("8.0")
        self.tz_edit.setPlaceholderText("时区 (小时)")
        loc_layout.addWidget(QLabel("经度:"))
        loc_layout.addWidget(self.lon_edit)
        loc_layout.addWidget(QLabel("纬度:"))
        loc_layout.addWidget(self.lat_edit)
        loc_layout.addWidget(QLabel("时区:"))
        loc_layout.addWidget(self.tz_edit)
        download_layout.addRow("测试位置:", loc_layout)

        # Output directory (fixed)
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        output_layout.addWidget(self.output_dir_edit)
        download_layout.addRow("存放目录:", output_layout)

        # Download buttons
        self.init_btn = QPushButton("初始化")
        self.download_btn = QPushButton("下载天气数据")
        self.merge_btn = QPushButton("合并CSV")
        self.merge_btn.setEnabled(False)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.init_btn)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.merge_btn)
        download_layout.addRow("", btn_layout)

        # Material parameters
        params_group = QGroupBox()
        params_layout = QFormLayout()
        params_group.setLayout(params_layout)

        self.eps_edit = QLineEdit("0.98")
        self.rho_solar_edit = QLineEdit("0.91")
        self.sky_view_edit = QLineEdit("1.0")
        self.export_figures_cb = QCheckBox("导出图表")
        self.export_figures_cb.setChecked(True)

        params_layout.addRow("发射率 (ε):", self.eps_edit)
        params_layout.addRow("太阳反射率 (ρ_solar):", self.rho_solar_edit)
        params_layout.addRow("天空视角系数 (0-1):", self.sky_view_edit)
        params_layout.addRow("", self.export_figures_cb)

        # Compute button
        self.compute_btn = QPushButton("计算辐射制冷")
        self.compute_btn.setEnabled(False)
        params_layout.addRow("", self.compute_btn)

        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {COLORS['light_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
            }}
            """
        )

        # Add widgets to main layout
        layout.addWidget(download_group)
        layout.addWidget(params_group)
        layout.addWidget(QLabel("日志输出:"))
        layout.addWidget(self.log_text)

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.view_results_btn = QPushButton("查看结果")
        button_box.addButton(self.view_results_btn, QDialogButtonBox.ActionRole)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _connect_signals(self):
        self.init_btn.clicked.connect(self._on_init_clicked)
        self.download_btn.clicked.connect(self._on_download_clicked)
        self.merge_btn.clicked.connect(self._on_merge_clicked)
        self.compute_btn.clicked.connect(self._on_compute_clicked)
        self.view_results_btn.clicked.connect(self._open_results_dir)

    def _log(self, message: str):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def _open_results_dir(self):
        path = self.base_output_dir
        try:
            os.makedirs(path, exist_ok=True)
            if os.name == 'nt':
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                QMessageBox.information(self, "提示", f"请手动打开目录: {path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))


    def _on_init_clicked(self):
        reply = QMessageBox.question(
            self,
            "确认初始化",
            f"确定要清空 output 文件夹内容吗？\n{self.base_output_dir}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._set_busy(True)
            self._log("开始初始化：清空 output 文件夹...")
            base = Path(self.base_output_dir)
            if base.exists() and base.is_dir():
                for p in base.iterdir():
                    try:
                        if p.is_dir():
                            import shutil

                            shutil.rmtree(p)
                        else:
                            p.unlink()
                    except Exception as e:
                        self._log(f"删除失败: {p} -> {e}")

            base.mkdir(parents=True, exist_ok=True)
            Path(base / "weather").mkdir(parents=True, exist_ok=True)
            Path(base / "results").mkdir(parents=True, exist_ok=True)
            Path(base / "figures").mkdir(parents=True, exist_ok=True)

            # Reset state
            self.merge_btn.setEnabled(False)
            self.compute_btn.setEnabled(False)
            if hasattr(self, 'merged_csv'):
                delattr(self, 'merged_csv')
            self.weather_dir = str(base / "weather")

            self._log("初始化完成")
        finally:
            self._set_busy(False)

    def _on_download_clicked(self):
        try:
            start_date = self.start_date_edit.text().strip()
            end_date = self.end_date_edit.text().strip()
            lon = _safe_float(self.lon_edit.text(), 0.0)
            lat = _safe_float(self.lat_edit.text(), 0.0)
            tz_offset = _safe_float(self.tz_edit.text(), 8.0)
            output_dir = os.path.join(self.base_output_dir, "weather")

            if not all([start_date, end_date]):
                QMessageBox.warning(self, "输入错误", "请填写开始和结束日期")
                return


            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                QMessageBox.warning(self, "输入错误", "经度必须在-180到180之间，纬度必须在-90到90之间")
                return

            params = Era5DownloadParams(
                start_date=start_date,
                end_date=end_date,
                lon=lon,
                lat=lat,
                tz_offset_hours=tz_offset,
            )

            self.worker = DownloadWorker(params, output_dir)
            self.worker.log_signal.connect(self._log)
            self.worker.finished_signal.connect(self._on_download_finished)
            self.worker.error_signal.connect(self._on_worker_error)
            self.worker.start()

            self.download_btn.setEnabled(False)
            self._log(f"开始查询 {start_date} 到 {end_date} 的天气数据...该过程将不超过1小时")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"下载失败: {e}")
            self._log(f"错误: {e}")

    def _on_download_finished(self, output_file: str):
        self.download_btn.setEnabled(True)
        self.merge_btn.setEnabled(True)
        self._log(f"下载完成")
        self._log("如果天气下载完成，请点击'天气准备完毕'，然后进行下一步")

        # Store the weather directory for later use (fixed under output)
        self.weather_dir = os.path.join(self.base_output_dir, "weather")

    def _on_merge_clicked(self):
        if not hasattr(self, 'weather_dir') or not self.weather_dir:
            QMessageBox.warning(self, "错误", "请先下载天气数据")
            return

        try:
            output_csv = os.path.join(self.base_output_dir, "weather", "era5_merged.csv")
            self.merge_worker = MergeWorker(self.weather_dir, output_csv)
            self.merge_worker.log_signal.connect(self._log)
            self.merge_worker.finished_signal.connect(self._on_merge_finished)
            self.merge_worker.error_signal.connect(self._on_worker_error)
            self.merge_worker.start()

            self.merge_btn.setEnabled(False)
            self._log("正在合并CSV文件...")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"合并失败: {e}")
            self._log(f"错误: {e}")

    def _on_merge_finished(self, output_csv: str):
        self.merge_btn.setEnabled(True)
        self.compute_btn.setEnabled(True)
        self.merged_csv = output_csv
        self._log(f"合并完成: {output_csv}")
        self._log("请设置材料参数并点击'开始原位测试'按钮")

    def _on_compute_clicked(self):
        if not hasattr(self, 'merged_csv') or not os.path.exists(self.merged_csv):
            QMessageBox.warning(self, "错误", "请先合并CSV文件")
            return

        try:
            eps = _safe_float(self.eps_edit.text(), 0.98)
            rho_solar = _safe_float(self.rho_solar_edit.text(), 0.91)
            sky_view = _safe_float(self.sky_view_edit.text(), 1.0)
            export_figures = self.export_figures_cb.isChecked()

            if not (0 <= eps <= 1 and 0 <= rho_solar <= 1 and 0 <= sky_view <= 1):
                raise ValueError("发射率、太阳反射率和天空视角系数必须在0到1之间")

            output_dir = os.path.join(self.base_output_dir, "results")
            os.makedirs(output_dir, exist_ok=True)
            output_csv = os.path.join(output_dir, "radiative_cooling_results.csv")
            
            params = Era5ComputeParams(
                eps=eps,
                rho_solar=rho_solar,
                sky_view=sky_view,
            )

            self.compute_worker = ComputeWorker(
                self.merged_csv, output_csv, params, export_figures
            )
            self.compute_worker.log_signal.connect(self._log)
            self.compute_worker.finished_signal.connect(self._on_compute_finished)
            self.compute_worker.error_signal.connect(self._on_worker_error)
            self.compute_worker.start()

            self.compute_btn.setEnabled(False)
            self._log("开始原位测试...")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算失败: {e}")
            self._log(f"错误: {e}")

    def _on_compute_finished(self, output_csv: str):
        self.compute_btn.setEnabled(True)
        self._log(f"计算完成，结果已保存到: {output_csv}")
        
        # Show a message box with the results
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("计算完成")
        msg.setText("辐射制冷计算已完成")
        msg.setInformativeText(f"结果已保存到:\n{output_csv}")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def _on_worker_error(self, error_msg: str):
        self.download_btn.setEnabled(True)
        self.merge_btn.setEnabled(True)
        self.compute_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", error_msg)
        self._log(f"错误: {error_msg}")

    def retranslate_ui(self):
        # Update any text that needs translation here
        pass


class Worker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.error_signal.emit(str(e))

    def _run(self):
        raise NotImplementedError


class DownloadWorker(Worker):
    def __init__(self, params: Era5DownloadParams, output_dir: str):
        super().__init__()
        self.params = params
        self.output_dir = output_dir

    def _run(self):
        from pathlib import Path

        # Ensure output directory exists
        output_dir = Path(self.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Download ERA5 data
        output_file = download_era5_to_dir(self.params, str(output_dir))
        self.log_signal.emit(f"下载完成: {output_file}")
        self.finished_signal.emit(str(output_file))


class MergeWorker(Worker):
    def __init__(self, weather_dir: str, output_csv: str):
        super().__init__()
        self.weather_dir = weather_dir
        self.output_csv = output_csv

    def _run(self):
        from pathlib import Path

        # Merge weather CSVs
        output_path = merge_weather_csvs(self.weather_dir, self.output_csv)
        self.log_signal.emit(f"合并完成: {output_path}")
        self.finished_signal.emit(str(output_path))


class ComputeWorker(Worker):
    def __init__(
        self,
        input_csv: str,
        output_csv: str,
        params: Era5ComputeParams,
        export_figures: bool = True,
    ):
        super().__init__()
        self.input_csv = input_csv
        self.output_csv = output_csv
        self.params = params
        self.export_figures = export_figures

    def _run(self):
        from pathlib import Path

        # Compute radiative cooling
        output_dir = str(Path(self.output_csv).parent)
        figures_dir = str(Path(output_dir) / "figures")
        
        self.log_signal.emit("开始计算辐射制冷...")
        
        df = compute_radiative_cooling_from_merged_csv(
            self.input_csv,
            out_csv=self.output_csv,
            params=self.params,
            export_figures=self.export_figures,
            figures_dir=figures_dir if self.export_figures else None,
        )
        
        self.log_signal.emit(f"计算完成，结果已保存到: {self.output_csv}")
        if self.export_figures:
            self.log_signal.emit(f"图表已导出到: {figures_dir}")
        
        self.finished_signal.emit(str(self.output_csv))