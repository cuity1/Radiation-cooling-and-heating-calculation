"""PyQt config.ini editor."""

from __future__ import annotations

import os
import shutil
from datetime import datetime

import configparser

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import COLORS
from gui.widgets import STYLE_SHEET
from utils.path_utils import external_default_dir, res_path


def launch_config_editor_pyqt(parent) -> None:
    """Launch config.ini editor.

    In PyInstaller onefile, config should be edited in external writable default/ next to exe.
    """

    cfg_dir = external_default_dir()
    os.makedirs(cfg_dir, exist_ok=True)
    CONFIG_FILE = os.path.join(cfg_dir, 'config.ini')

    # If external config not exists, copy from embedded resources.
    if not os.path.exists(CONFIG_FILE):
        try:
            src_cfg = res_path('default', 'config.ini')
            if os.path.exists(src_cfg):
                shutil.copy(src_cfg, CONFIG_FILE)
        except Exception:
            pass

    if not os.path.exists(CONFIG_FILE):
        QMessageBox.critical(parent, '错误', f'未找到配置文件并且无法从内置资源复制：{CONFIG_FILE}')
        return

    dialog = QDialog(parent)
    dialog.setWindowTitle('Config.ini 编辑器')
    dialog.setGeometry(100, 100, 800, 600)

    layout = QVBoxLayout(dialog)

    tabs = QTabWidget()
    layout.addWidget(tabs)

    config = configparser.ConfigParser()
    config.optionxform = str

    comments: dict[str, dict] = {}
    current_section = None
    pending_comments: list[str] = []

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    pending_comments.clear()
                    continue
                if stripped.startswith('#') or stripped.startswith(';'):
                    comment = stripped.lstrip('#').lstrip(';').strip()
                    pending_comments.append(comment)
                elif stripped.startswith('[') and stripped.endswith(']'):
                    section = stripped[1:-1].strip()
                    current_section = section
                    comments.setdefault(section, {'comments': [], 'keys': {}})
                    if pending_comments:
                        comments[section]['comments'].extend(pending_comments)
                    pending_comments.clear()
                elif '=' in stripped and current_section is not None:
                    key = stripped.split('=', 1)[0].strip()
                    comments[current_section]['keys'].setdefault(key, [])
                    if pending_comments:
                        comments[current_section]['keys'][key].extend(pending_comments)
                    pending_comments.clear()
                else:
                    pending_comments.clear()
    except UnicodeDecodeError as e:
        QMessageBox.critical(dialog, '编码错误', f'无法使用 UTF-8 编码读取 {CONFIG_FILE} 文件。\n错误信息: {e}')
        return

    config.read(CONFIG_FILE, encoding='utf-8')

    entries: dict[tuple[str, str], QTableWidgetItem] = {}
    comment_entries: dict[tuple[str, str], QTableWidgetItem] = {}

    def create_section_widget(section: str):
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        sec_comments = comments.get(section, {}).get('comments', [])
        for comm in sec_comments:
            lbl = QLabel(f'# {comm}')
            lbl.setStyleSheet(f"color: {COLORS['secondary_text']}; font-style: italic;")
            scroll_layout.addWidget(lbl)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['参数', '值', '解释'])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

        row = 0
        for key, value in config.items(section):
            table.insertRow(row)

            key_item = QTableWidgetItem(key)
            table.setItem(row, 0, key_item)

            value_item = QTableWidgetItem(str(value))
            if key in ['C1', 'C2']:
                value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            else:
                entries[(section, key)] = value_item
            table.setItem(row, 1, value_item)

            key_comments = comments.get(section, {}).get('keys', {}).get(key, [])
            comment_text = ' ; '.join(key_comments) if key_comments else ''
            comment_item = QTableWidgetItem(comment_text)
            if key not in ['C1', 'C2']:
                comment_entries[(section, key)] = comment_item
            table.setItem(row, 2, comment_item)

            row += 1

        table.resizeColumnsToContents()
        scroll_layout.addWidget(table)

        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        return scroll

    for section in config.sections():
        scroll = create_section_widget(section)
        tabs.addTab(scroll, section)

    def validate_inputs() -> bool:
        for (section, key), item in entries.items():
            val = item.text().strip()
            if section == 'EXPIRATION' and key == 'EXPIRATION_DATE':
                try:
                    datetime.strptime(val, '%Y-%m-%d')
                except ValueError:
                    QMessageBox.critical(dialog, '输入错误', f'{key} 的格式应为 YYYY-MM-DD')
                    return False
            elif (
                key.startswith('T_')
                or key.startswith('HC_')
                or key.startswith('S_')
                or key.startswith('WAVELENGTH')
                or key in ['KB', 'H', 'C']
            ):
                try:
                    parts = [p.strip() for p in val.split(',')]
                    for part in parts:
                        if part:
                            float(part)
                except ValueError:
                    QMessageBox.critical(dialog, '输入错误', f'{key} 应为数值或数值列表（用逗号分隔）')
                    return False
        return True

    def save_config() -> None:
        if not validate_inputs():
            return

        backup_file = CONFIG_FILE + '.bak'
        try:
            shutil.copy(CONFIG_FILE, backup_file)
        except Exception as e:
            QMessageBox.critical(dialog, '备份失败', f'备份原文件失败：{e}')
            return

        for (section, key), item in entries.items():
            config.set(section, key, item.text().strip())

        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                for section in config.sections():
                    sec_comms = comments.get(section, {}).get('comments', [])
                    for comm in sec_comms:
                        f.write(f'# {comm}\n')
                    f.write(f'[{section}]\n')
                    for key, value in config.items(section):
                        if key in ['C1', 'C2']:
                            key_comms = comments.get(section, {}).get('keys', {}).get(key, [])
                            for comm in key_comms:
                                f.write(f'# {comm}\n')
                            f.write(f'{key} = {value}\n')
                            continue

                        explanation = ''
                        if (section, key) in comment_entries:
                            explanation = comment_entries[(section, key)].text().strip()
                        if explanation:
                            for part in [p.strip() for p in explanation.split(';') if p.strip()]:
                                f.write(f'# {part}\n')
                        f.write(f"{key} = {entries[(section, key)].text().strip()}\n")
                    f.write('\n')

            QMessageBox.information(dialog, '成功', '配置已成功保存。')
            dialog.accept()

        except Exception as e:
            QMessageBox.critical(dialog, '保存失败', f'保存配置文件失败：{e}\n尝试恢复备份文件。')
            try:
                shutil.copy(backup_file, CONFIG_FILE)
                QMessageBox.information(dialog, '恢复成功', '已恢复备份文件。')
            except Exception as restore_e:
                QMessageBox.critical(dialog, '恢复失败', f'恢复备份失败：{restore_e}')

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    save_btn = QPushButton('保存')
    save_btn.clicked.connect(save_config)

    cancel_btn = QPushButton('取消')
    cancel_btn.clicked.connect(dialog.reject)

    btn_layout.addWidget(save_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)

    dialog.setStyleSheet(STYLE_SHEET)
    dialog.exec_()

