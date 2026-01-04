"""Input file processor dialog."""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import language_manager
from gui.widgets import AnimatedButton, CardFrame, TitleLabel


class FileProcessorDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(550, 450)
        self.selected_file = None
        self.output_type = 'reflectance'

        language_manager.language_changed.connect(self.update_language)

        self.init_ui()
        self.update_language()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        self.title_label = TitleLabel('')
        layout.addWidget(self.title_label)

        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setStyleSheet('color: #7f8c8d; font-size: 14px;')
        layout.addWidget(self.desc_label)

        file_card = CardFrame()
        file_layout = QVBoxLayout(file_card)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)

        self.select_btn = AnimatedButton('')
        self.select_btn.clicked.connect(self.select_file)
        button_layout.addWidget(self.select_btn)

        self.convert_btn = AnimatedButton('')
        self.convert_btn.clicked.connect(self.convert_file)
        self.convert_btn.setEnabled(False)
        button_layout.addWidget(self.convert_btn)

        file_layout.addWidget(button_container)

        self.file_path_label = QLabel()
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setAlignment(Qt.AlignCenter)
        self.file_path_label.setStyleSheet('color: #3498db; font-size: 12px; padding: 10px;')
        file_layout.addWidget(self.file_path_label)

        type_container = QWidget()
        type_layout = QHBoxLayout(type_container)
        type_layout.setSpacing(15)

        self.type_label = QLabel('')
        self.type_label.setStyleSheet('font-size: 13px; font-weight: bold;')
        type_layout.addWidget(self.type_label)

        self.type_combo = QComboBox()
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()

        file_layout.addWidget(type_container)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        file_layout.addWidget(self.progress_bar)

        self.status_label = QLabel('')
        self.status_label.setObjectName('status')
        self.status_label.setAlignment(Qt.AlignCenter)
        file_layout.addWidget(self.status_label)

        layout.addWidget(file_card)

        button_layout_bottom = QHBoxLayout()
        button_layout_bottom.setSpacing(15)

        self.close_button = AnimatedButton('')
        self.close_button.clicked.connect(self.reject)
        button_layout_bottom.addWidget(self.close_button)

        layout.addLayout(button_layout_bottom)
        self.setLayout(layout)

    def on_type_changed(self, index: int):
        self.output_type = self.type_combo.itemData(index)

    def update_language(self):
        self.setWindowTitle(language_manager.get('file_processor'))
        self.title_label.setText(language_manager.get('file_processor'))
        self.desc_label.setText(language_manager.get('file_processor_desc'))
        self.select_btn.setText(language_manager.get('select_file'))
        self.convert_btn.setText(language_manager.get('start_convert'))
        self.close_button.setText(language_manager.get('close'))

        self.type_label.setText(language_manager.get('select_output_type') + ':')
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItem(language_manager.get('reflectance_file'), 'reflectance')
        self.type_combo.addItem(language_manager.get('emissivity_file'), 'emissivity')
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.output_type:
                self.type_combo.setCurrentIndex(i)
                break
        self.type_combo.blockSignals(False)

        if not self.selected_file:
            self.file_path_label.setText(
                '请选择要处理的文件' if language_manager.is_chinese() else 'Please select a file to process'
            )

    def select_file(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                language_manager.get('select_file'),
                '',
                'All Supported Files (*.csv *.xlsx *.xls *.txt);;CSV files (*.csv);;Excel files (*.xlsx *.xls);;Text files (*.txt);;All files (*.*)',
            )

            if file_path:
                self.selected_file = file_path
                filename = os.path.basename(file_path)
                selected_text = '已选择' if language_manager.is_chinese() else 'Selected'
                self.file_path_label.setText(f'{selected_text}: {filename}')
                self.file_path_label.setStyleSheet('color: #27ae60; font-size: 12px; padding: 10px;')
                self.convert_btn.setEnabled(True)
                ready_text = (
                    '文件已选择，点击开始处理'
                    if language_manager.is_chinese()
                    else 'File selected, click to start processing'
                )
                self.status_label.setText(ready_text)
                self.status_label.setStyleSheet('color: #2c3e50;')
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"{language_manager.get('error')}: {str(e)}")

    def clean_data(self, data):
        cleaned_rows = []

        for row in data:
            row_str = [str(cell) for cell in row]
            has_text = False
            for cell in row_str:
                if re.search(r'[\u4e00-\u9fff]', str(cell)):
                    has_text = True
                    break
                if re.search(r'[a-zA-Z]', str(cell)) and not re.match(r'^[\d\.\-\+eE]+$', str(cell)):
                    has_text = True
                    break

            if not has_text:
                numeric_values = []
                for cell in row_str:
                    try:
                        numeric_values.append(float(cell))
                    except (ValueError, TypeError):
                        numbers = re.findall(r'-?\d+\.?\d*[eE]?[+-]?\d*', str(cell))
                        if numbers:
                            numeric_values.append(float(numbers[0]))

                if len(numeric_values) >= 2:
                    cleaned_rows.append(numeric_values[:2])

        return np.array(cleaned_rows) if cleaned_rows else np.array([])

    def _normalize_number_token(self, token: str) -> float:
        s = token.strip()
        if s.endswith('%'):
            s = s[:-1]
        if ',' in s and '.' in s:
            s = s.replace(',', '')
        elif ',' in s and '.' not in s:
            s = s.replace(',', '.')
        return float(s)

    def parse_txt_file(self, file_path: str) -> np.ndarray:
        trans = str.maketrans(
            {
                '０': '0',
                '１': '1',
                '２': '2',
                '３': '3',
                '４': '4',
                '５': '5',
                '６': '6',
                '７': '7',
                '８': '8',
                '９': '9',
                '．': '.',
                '，': ',',
                '。': '.',
                '、': ' ',
                '－': '-',
                '—': '-',
                '～': '-',
                '‒': '-',
                '–': '-',
                '−': '-',
            }
        )
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'gb18030', 'latin1']
        number_pattern = re.compile(r"[-+]?\d*[\.,]?\d+(?:[eE][+-]?\d+)?%?")
        for encoding in encodings:
            try:
                rows = []
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    for raw_line in f:
                        line = raw_line.translate(trans)
                        tokens = number_pattern.findall(line)
                        if not tokens:
                            continue
                        vals = []
                        for tk in tokens:
                            try:
                                vals.append(self._normalize_number_token(tk))
                            except Exception:
                                continue
                            if len(vals) == 2:
                                break
                        if len(vals) >= 2:
                            rows.append(vals[:2])
                if rows:
                    return np.array(rows, dtype=float)
            except Exception:
                continue
        raise Exception('无法解析TXT文件中的数据（请确认至少包含两列数字）')

    def read_file(self, file_path: str):
        file_ext = Path(file_path).suffix.lower()

        try:
            if file_ext == '.csv':
                encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'gb18030']
                df = None
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, header=None)
                        break
                    except UnicodeDecodeError:
                        continue
                if df is None:
                    raise Exception(
                        '无法以任何编码读取CSV文件'
                        if language_manager.is_chinese()
                        else 'Cannot read CSV file with any encoding'
                    )
                return df.values

            if file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, header=None)
                return df.values

            if file_ext == '.txt':
                return self.parse_txt_file(file_path)

            raise Exception(
                f"不支持的文件格式: {file_ext}"
                if language_manager.is_chinese()
                else f"Unsupported file format: {file_ext}"
            )

        except Exception as e:
            error_msg = '读取文件失败' if language_manager.is_chinese() else 'Failed to read file'
            raise Exception(f"{error_msg}: {str(e)}")

    def _postprocess_output(self, data: np.ndarray, output_type: str):
        tips = []
        arr = np.asarray(data, dtype=float)
        if arr.ndim != 2 or arr.shape[1] < 2:
            raise Exception('数据至少需要两列')
        arr = arr[:, :2]

        mask = np.isfinite(arr).all(axis=1)
        arr = arr[mask]
        if arr.shape[0] == 0:
            raise Exception('没有有效的数据行')

        idx = np.argsort(arr[:, 0])
        arr = arr[idx]

        if arr.shape[0] > 1:
            _, uniq_idx = np.unique(arr[:, 0], return_index=True)
            arr = arr[uniq_idx]

        y = arr[:, 1]
        if np.nanmax(y) > 1.5:
            arr[:, 1] = y / 100.0
            tips.append('检测到百分比数据，已自动/100')

        arr[:, 1] = np.clip(arr[:, 1], 0.0, 1.0)

        x = arr[:, 0]
        if np.median(x) > 100:
            arr[:, 0] = x * 0.001
            tips.append('检测到波长像纳米，已转换为微米(÷1000)')

        return arr, tips

    def convert_file(self):
        if not self.selected_file:
            QMessageBox.critical(
                self,
                language_manager.get('error'),
                '请先选择文件' if language_manager.is_chinese() else 'Please select a file first',
            )
            return

        try:
            self.convert_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.status_label.setText(
                '正在读取文件...' if language_manager.is_chinese() else 'Reading file...'
            )
            QApplication.processEvents()

            data = self.read_file(self.selected_file)

            if data.size == 0 or data.shape[0] == 0:
                self.progress_bar.setVisible(False)
                self.convert_btn.setEnabled(True)
                QMessageBox.critical(
                    self,
                    language_manager.get('error'),
                    '文件为空或无法读取数据'
                    if language_manager.is_chinese()
                    else 'File is empty or cannot read data',
                )
                return

            self.status_label.setText(
                '正在清理数据...' if language_manager.is_chinese() else 'Cleaning data...'
            )
            QApplication.processEvents()

            cleaned_data = (
                self.clean_data(data)
                if not np.issubdtype(np.array(data).dtype, np.number)
                else np.array(data, dtype=float)
            )

            if cleaned_data.size == 0 or cleaned_data.shape[0] == 0:
                self.progress_bar.setVisible(False)
                self.convert_btn.setEnabled(True)
                QMessageBox.critical(
                    self,
                    language_manager.get('error'),
                    '清理后没有有效的数据行（至少需要两列数字）'
                    if language_manager.is_chinese()
                    else 'No valid data rows after cleaning (at least two numeric columns required)',
                )
                return

            output_data, tips = self._postprocess_output(cleaned_data[:, :2], self.output_type)
            if output_data.shape[0] < 5:
                self.progress_bar.setVisible(False)
                self.convert_btn.setEnabled(True)
                raise Exception('有效数据行过少(少于5行)')

            self.status_label.setText(
                '正在保存文件...' if language_manager.is_chinese() else 'Saving file...'
            )
            QApplication.processEvents()

            input_path = Path(self.selected_file)
            type_suffix = '_reflectance' if self.output_type == 'reflectance' else '_emissivity'
            output_path = input_path.parent / f"{input_path.stem}{type_suffix}.txt"

            np.savetxt(output_path, output_data, fmt='%.6f', delimiter=' ', encoding='utf-8')

            self.progress_bar.setVisible(False)
            self.convert_btn.setEnabled(True)

            tip_text = '；'.join(tips) if tips else '无格式矫正'
            success_msg = f"{language_manager.get('conversion_success')} {output_path.name}"
            self.status_label.setText(success_msg + (f"（{tip_text}）" if tips else ''))
            self.status_label.setStyleSheet('color: #27ae60; font-weight: bold;')

            msg_text = (
                f"文件已成功处理并保存为:\n{output_path}\n\n共处理 {len(output_data)} 行数据\n"
                f"{('格式矫正: ' + tip_text) if tips else ''}"
                if language_manager.is_chinese()
                else f"File successfully processed and saved as:\n{output_path}\n\nProcessed {len(output_data)} rows of data\n"
                f"{('Normalization: ' + tip_text) if tips else ''}"
            )
            QMessageBox.information(self, language_manager.get('success'), msg_text)

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.convert_btn.setEnabled(True)
            self.status_label.setText(language_manager.get('conversion_failed'))
            self.status_label.setStyleSheet('color: #e74c3c; font-weight: bold;')

            QMessageBox.critical(
                self,
                language_manager.get('error'),
                f"{language_manager.get('conversion_failed')}:\n{str(e)}",
            )

