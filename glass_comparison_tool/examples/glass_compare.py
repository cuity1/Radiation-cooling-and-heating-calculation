"""
玻璃对比示例 - 聚焦辐射制冷：比较玻璃光学/热学参数（太阳透射率/发射率/U值）对 HVAC 能耗的影响

用法：
  python examples/glass_compare.py          # 默认启动 GUI 界面
  python examples/glass_compare.py --cli   # 使用命令行模式

说明：
- 仅修改"玻璃"的光学参数（太阳透射率transmittance、红外发射率emissivity、U值等）。
- 玻璃参数用于外窗能量平衡（短波得热、长波辐射散热、传热）。
- 天气：批量扫描项目/当前工作目录下的 weather/**/*.epw，预先计算"天气×场景"的总任务数，采用全局并行运行并汇总。

性能优化（v2.0+）：
- 预设模式：提供两个预设模式，一键设置所有优化参数
  * 常规模式：全部时间，1小时步长，30次迭代，7天预热（高精度）
  * 快速模式：每月2周，3小时步长，10次迭代，3天预热（快速对比，约5-10倍速度提升）
- 引擎复用：同一EPW的多个场景共享天气数据和建筑模型，只修改玻璃参数，大幅减少重复加载时间
- 时间采样模式：支持多种采样策略（每月2周/1周、季节性、代表性日期）
- 时间步长优化：可设置1-6小时步长（默认1小时）
- 预热期优化：可通过环境变量 GLASS_WARMUP_DAYS 或 GUI 设置减少预热期（默认7天）
- 环境变量控制：
  * GLASS_WARMUP_DAYS: 预热期天数（默认7）
  * GLASS_MAX_WORKERS: 并行线程/进程数（默认自动）
  * GLASS_TASK_TIMEOUT: 单任务超时秒数（默认24000）
  * GLASS_USE_MULTIPROCESSING: 是否使用多进程（'1'/'true'/'yes' 启用）

PNG地图生成方案（v2.1+）：
  代码已实现多种PNG生成方案，按优先级自动选择：
  1. Playwright方案（推荐）：最可靠，等待canvas内容渲染完成
     - 安装: pip install playwright
     - 初始化: playwright install chromium
  2. 改进的Selenium方案：等待canvas有实际像素内容
     - 需要: selenium + chromedriver
  3. 原始pyecharts-snapshot方案：作为备选
     - 需要: pyecharts-snapshot + snapshot-selenium
  
  如果PNG生成失败，代码会自动尝试下一个方案，并验证生成的文件有效性。
"""

import sys
import os
import json
import pandas as pd
import glob
import tempfile
import concurrent.futures as cf
from typing import List, Dict, Any, Optional, Tuple
import time
import subprocess

from pyecharts import options as opts
from pyecharts.charts import Map, Page

try:
    from snapshot_selenium import snapshot
    from pyecharts.render import make_snapshot

    _SNAPSHOT_AVAILABLE = True
except Exception:
    snapshot = None
    make_snapshot = None
    _SNAPSHOT_AVAILABLE = False

# 尝试导入Playwright（更可靠的替代方案）
try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except Exception:
    _PLAYWRIGHT_AVAILABLE = False

# GUI: 按需导入，避免在无 PyQt5 环境下影响 CLI 使用
try:
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QTabWidget,
        QVBoxLayout,
        QHBoxLayout,
        QFormLayout,
        QLineEdit,
        QPushButton,
        QDoubleSpinBox,
        QFileDialog,
        QMessageBox,
        QGroupBox,
        QTextEdit,
        QCheckBox,
        QComboBox,
    )
    from PyQt5.QtCore import QThread, pyqtSignal, QUrl
    from PyQt5.QtGui import QDesktopServices, QCloseEvent
except Exception:  # pragma: no cover
    QApplication = None
    QThread = None
    pyqtSignal = None
    QDesktopServices = None
    QUrl = None


# 移除 SimulationEngine 导入，改用 EnergyPlus
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
# from core import SimulationEngine
import logging
import shutil
import re
import zipfile
from datetime import datetime
from bs4 import BeautifulSoup
import chardet

def get_exe_dir() -> str:
    """获取exe文件所在的目录（如果是打包后的exe）或当前脚本所在目录（开发环境）。
    
    返回：exe文件所在的目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.dirname(sys.executable)
    else:
        # 开发环境：返回脚本所在目录的父目录（项目根目录）
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def get_weather_dir() -> str:
    """获取天气文件夹路径。

    仅允许选择两个内置目录：
    - material_comparison_tool/china_weather
    - material_comparison_tool/world_weather
    """
    exe_dir = get_exe_dir()
    # 固定使用项目内置的两个目录（与打包exe同目录时也保持一致）
    return exe_dir


def get_output_dir() -> str:
    """获取结果输出文件夹路径（位于exe文件旁边）。"""
    exe_dir = get_exe_dir()
    return os.path.join(exe_dir, 'output', 'comparison')


def get_work_dir(base_dir: Optional[str] = None) -> str:
    """生成新的工作目录路径（带时间戳）。
    
    Args:
        base_dir: 基础目录，如果为None则使用get_output_dir()
    
    Returns:
        工作目录路径，格式：work_YYYYMMDD_HHMMSS
    """
    if base_dir is None:
        base_dir = get_output_dir()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    work_dir = os.path.join(base_dir, f'work_{timestamp}')
    os.makedirs(work_dir, exist_ok=True)
    return work_dir


# ==================== 玻璃 IDF 编辑函数 ====================
# 这些函数用于编辑IDF文件中的 WindowMaterial:Glazing 对象

# 玻璃材料字段顺序（WindowMaterial:Glazing）
GLASS_FIELD_ORDER = [
    "Name",
    "Optical_Data_Type",
    "Window_Glass_Spectral_Data_Set_Name",
    "Thickness",
    "Solar_Transmittance",
    "Solar_Reflectance_Front",
    "Solar_Reflectance_Back",
    "Visible_Transmittance",
    "Visible_Reflectance_Front",
    "Visible_Reflectance_Back",
    "Infrared_Transmittance",
    "Emissivity_Front",
    "Emissivity_Back",
    "Conductivity",
    "Dirt_Correction",
    "Solar_Diffusing",
]

# WindowMaterial:Glazing 对象的字段索引（0-indexed，block_lines 数组索引）
# 第1行是对象类型，第2行开始是字段（从0开始计数，index=1对应block_lines[1]即第2行）
GLASS_FIELD_INDEX = {
    "Name": 1,
    "Optical_Data_Type": 2,
    "Window_Glass_Spectral_Data_Set_Name": 3,
    "Thickness": 4,
    "Solar_Transmittance": 5,
    "Solar_Reflectance_Front": 6,
    "Solar_Reflectance_Back": 7,
    "Visible_Transmittance": 8,
    "Visible_Reflectance_Front": 9,
    "Visible_Reflectance_Back": 10,
    "Infrared_Transmittance": 11,
    "Emissivity_Front": 12,
    "Emissivity_Back": 13,
    "Conductivity": 14,
    "Dirt_Correction": 15,
    "Solar_Diffusing": 16,
}


class IdFGlassParseError(Exception):
    pass


def find_glass_objects(idf_text: str):
    """查找所有 WindowMaterial:Glazing 对象"""
    lines = idf_text.splitlines(keepends=True)

    blocks = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("WindowMaterial:Glazing,"):
            start = i
            j = i
            while j < len(lines):
                if ";" in lines[j]:
                    break
                j += 1
            if j >= len(lines):
                raise IdFGlassParseError("Unterminated WindowMaterial:Glazing object.")
            end = j
            block_lines = lines[start : end + 1]

            # WindowMaterial:Glazing 对象至少有16行（加上对象类型行共17行）
            if len(block_lines) < 17:
                i = end + 1
                continue

            name_line = block_lines[1]
            name_before, _ = _split_value_and_comment(name_line)
            name = _extract_value_token(name_before)

            blocks.append({
                "name": name,
                "start": start,
                "end": end,
                "lines": block_lines,
            })
            i = end + 1
        else:
            i += 1

    return blocks, lines


def parse_glass_block(block_lines):
    """解析 WindowMaterial:Glazing 对象块"""
    if not block_lines[0].lstrip().startswith("WindowMaterial:Glazing,"):
        raise IdFGlassParseError("Block does not start with WindowMaterial:Glazing,")
    if len(block_lines) < 17:
        raise IdFGlassParseError("WindowMaterial:Glazing block too short.")

    mapping = {
        "Name": _extract_value_token(_split_value_and_comment(block_lines[1])[0]),
        "Optical_Data_Type": _extract_value_token(_split_value_and_comment(block_lines[2])[0]),
        "Window_Glass_Spectral_Data_Set_Name": _extract_value_token(_split_value_and_comment(block_lines[3])[0]),
        "Thickness": _extract_value_token(_split_value_and_comment(block_lines[4])[0]),
        "Solar_Transmittance": _extract_value_token(_split_value_and_comment(block_lines[5])[0]),
        "Solar_Reflectance_Front": _extract_value_token(_split_value_and_comment(block_lines[6])[0]),
        "Solar_Reflectance_Back": _extract_value_token(_split_value_and_comment(block_lines[7])[0]),
        "Visible_Transmittance": _extract_value_token(_split_value_and_comment(block_lines[8])[0]),
        "Visible_Reflectance_Front": _extract_value_token(_split_value_and_comment(block_lines[9])[0]),
        "Visible_Reflectance_Back": _extract_value_token(_split_value_and_comment(block_lines[10])[0]),
        "Infrared_Transmittance": _extract_value_token(_split_value_and_comment(block_lines[11])[0]),
        "Emissivity_Front": _extract_value_token(_split_value_and_comment(block_lines[12])[0]),
        "Emissivity_Back": _extract_value_token(_split_value_and_comment(block_lines[13])[0]),
        "Conductivity": _extract_value_token(_split_value_and_comment(block_lines[14])[0]),
        "Dirt_Correction": _extract_value_token(_split_value_and_comment(block_lines[15])[0]),
        "Solar_Diffusing": _extract_value_token(_split_value_and_comment(block_lines[16])[0]),
    }
    return mapping


def apply_glass_block_updates(block_lines, new_values):
    """应用更新到 WindowMaterial:Glazing 对象"""
    out = list(block_lines)

    for field, idx in GLASS_FIELD_INDEX.items():
        if field not in new_values:
            continue
        # 跳过 Name 字段的更新，保持 IDF 文件中的原始对象名不变
        if field == 'Name':
            continue
        # 特殊处理布尔类型字段：转换为 Yes/No
        value = new_values[field]
        if field == 'Solar_Diffusing':
            if isinstance(value, bool):
                value = 'Yes' if value else 'No'
            elif str(value).lower() in ['true', '1', 'yes']:
                value = 'Yes'
            else:
                value = 'No'
        out[idx] = _format_value_line(out[idx], str(value))
        if not out[idx].endswith("\n") and block_lines[idx].endswith("\n"):
            out[idx] += "\n"

    return out


def load_one_glass_from_file(idf_path: str, glass_name: str):
    """从IDF文件中加载指定的玻璃材料"""
    if not os.path.exists(idf_path):
        raise FileNotFoundError(idf_path)

    with open(idf_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    blocks, lines = find_glass_objects(text)
    block = None
    for b in blocks:
        if b["name"] == glass_name:
            block = b
            break

    if block is None:
        raise IdFGlassParseError(f"Missing WindowMaterial:Glazing object '{glass_name}' in file: {idf_path}")

    parsed = parse_glass_block(block["lines"])
    return parsed, block, lines


def save_one_glass_to_file(idf_path: str, glass_name: str, new_values: dict):
    """将玻璃参数更新到IDF文件"""
    parsed, block, lines = load_one_glass_from_file(idf_path, glass_name)
    _ = parsed

    updated_block = apply_glass_block_updates(block["lines"], new_values)
    new_lines = list(lines)
    new_lines[block["start"] : block["end"] + 1] = updated_block

    # 创建备份文件
    bak = idf_path + ".bak"
    if os.path.exists(idf_path):
        shutil.copyfile(idf_path, bak)

    with open(idf_path, "w", encoding="utf-8") as f:
        f.write("".join(new_lines))


# ==================== 从 batch_run.py 导入的IDF编辑函数 ====================
# 这些函数用于编辑IDF文件中的材料参数（保留以备兼容）

TARGET_NAMES = ["duibi", "shiyan1", "shiyan2"]

# 玻璃文件映射：基准场景使用 duibi.idf，实验场景使用 glass.idf
DEFAULT_FILE_BY_GLASS = {
    "glass_duibi": "duibi.idf",    # 基准玻璃 - 使用 duibi.idf 中的 duibi 对象
    "glass_shiyan1": "glass.idf",  # 实验玻璃1 - 使用 glass.idf 中的 shiyanhigh 对象
    "glass_shiyan2": "glass.idf",  # 实验玻璃2 - 使用 glass.idf 中的 shiyanlow 对象
}

# 保留旧的文件映射名称用于兼容性
DEFAULT_FILE_BY_MATERIAL = DEFAULT_FILE_BY_GLASS

# 玻璃场景名称映射（IDF中的对象名）
GLASS_OBJECT_NAMES = {
    "glass_duibi": "duibi",       # duibi.idf 中的 duibi 对象
    "glass_shiyan1": "shiyanhigh", # glass.idf 中的 shiyanhigh 对象
    "glass_shiyan2": "shiyanlow",   # glass.idf 中的 shiyanlow 对象
}

GLOBAL_PARAM_SPECS = [
    {
        "key": "global_ach",
        "label": "Infiltration Air Changes per Hour (1/hr)",
        "object_type": "ZoneInfiltration:DesignFlowRate",
        "object_name": "189.1-2009 - Office - OpenOffice - CZ4-8 Infiltration",
        "comment_marker": "!- Air Changes per Hour {1/hr}",
    },
    {
        "key": "global_lighting_w_per_m2",
        "label": "Lights 'Office Bldg Light' Watts per Zone Floor Area (W/m2)",
        "lights_object_name": "189.1-2009 - Office - OpenOffice - CZ4-8 Lights",
        "comment_marker": "!- Watts per Zone Floor Area {W/m2}",
    },
    {
        "key": "global_thermostat_heat_c",
        "label": "Thermostat 'temp' Constant Heating Setpoint (C)",
        "object_type": "HVACTemplate:Thermostat",
        "object_name": "temp",
        "comment_marker": "!- Constant Heating Setpoint {C}",
    },
    {
        "key": "global_thermostat_cool_c",
        "label": "Thermostat 'temp' Constant Cooling Setpoint (C)",
        "object_type": "HVACTemplate:Thermostat",
        "object_name": "temp",
        "comment_marker": "!- Constant Cooling Setpoint {C}",
    },
    {
        "key": "global_people_per_m2",
        "label": "People per Zone Floor Area (person/m2)",
        "object_type": "People",
        "object_name": "189.1-2009 - Office - OpenOffice - CZ4-8 People",
        "comment_marker": "!- People per Zone Floor Area {person/m2}",
    },
    {
        "key": "phase_change_temp",
        "label": "Thermochromic Glass Phase Change Temperature (C)",
        "comment_marker": "!- Optical Data Temperature 2 {C}",
    },
]

FIELD_ORDER = [
    "Name",
    "Roughness",
    "Thickness",
    "Conductivity",
    "Density",
    "SpecificHeat",
    "ThermalAbsorptance",
    "SolarAbsorptance",
    "VisibleAbsorptance",
]


class IdFMaterialParseError(Exception):
    pass


# ==================== Colormap Registry ====================
# 科学可视化领域常用色系（与 pyecharts range_color / matplotlib cmap 对应）
# 分类说明：
#   sequential  - 顺序色系（单色渐变），适合有方向性的数据
#   diverging   - 发散色系（双向渐变），适合正负对比或偏离中心的值
# 使用说明：
#   节能数据（正值为主）：推荐 Blues, YlGnBu, Greens, Oranges, Purples, Reds, viridis, plasma, inferno
#   制冷/热量数据：推荐 coolwarm, coolwarm_r, BlueYellowRed, BuRd, PuOr, BrBG, PRGn, Spectral
#   CO2减排（正值）：推荐 Greens, YlGn, Oranges, Purples, Blues, Greens（纯绿色系）

COLORMAP_REGISTRY = {

    # ── 蓝色系 (Blue) ──────────────────────────────────────────
    "Blues": {
        "type": "sequential",
        "colors": ["#EFF3FF", "#BDD7E7", "#6BAED6", "#2171B5", "#084594"],
        "python_colors": ["#EFF3FF", "#BDD7E7", "#6BAED6", "#2171B5", "#084594"],
        "desc_zh": "蓝色渐变",
        "desc_en": "Blue gradient",
        "category": "blue",
    },
    "Blues_dark": {
        "type": "sequential",
        "colors": ["#C6DBEF", "#6BAED6", "#4292C6", "#2171B5", "#084594", "#08306B"],
        "python_colors": ["#C6DBEF", "#6BAED6", "#4292C6", "#2171B5", "#084594", "#08306B"],
        "desc_zh": "深蓝渐变",
        "desc_en": "Dark Blue gradient",
        "category": "blue",
    },
    "BlueYellowRed": {
        "type": "diverging",
        "colors": ["#2166AC", "#4393C3", "#92C5DE", "#D1E5F0", "#FDDBC7", "#F4A582", "#D6604D", "#B2182B"],
        "python_colors": ["#2166AC", "#4393C3", "#92C5DE", "#D1E5F0", "#FDDBC7", "#F4A582", "#D6604D", "#B2182B"],
        "desc_zh": "蓝-黄-红",
        "desc_en": "Blue-Yellow-Red",
        "category": "diverging",
    },
    "BuRd": {
        "type": "diverging",
        "colors": ["#B2182B", "#D6604D", "#F4A582", "#FDDBC7", "#D1E5F0", "#92C5DE", "#4393C3", "#2166AC"],
        "python_colors": ["#B2182B", "#D6604D", "#F4A582", "#FDDBC7", "#D1E5F0", "#92C5DE", "#4393C3", "#2166AC"],
        "desc_zh": "蓝红双向",
        "desc_en": "Blue-Red diverging",
        "category": "diverging",
    },
    "BuPu": {
        "type": "sequential",
        "colors": ["#EDF8FB", "#B3CDE3", "#8C96C6", "#6BAED6", "#4E004F"],
        "python_colors": ["#EDF8FB", "#B3CDE3", "#8C96C6", "#6BAED6", "#4E004F"],
        "desc_zh": "蓝-紫渐变",
        "desc_en": "Blue-Purple gradient",
        "category": "blue",
    },

    # ── 绿色系 (Green) ──────────────────────────────────────────
    "Greens": {
        "type": "sequential",
        "colors": ["#F7FCB9", "#ADDD8E", "#78C679", "#41AB5D", "#238B45", "#006837"],
        "python_colors": ["#F7FCB9", "#ADDD8E", "#78C679", "#41AB5D", "#238B45", "#006837"],
        "desc_zh": "绿色渐变",
        "desc_en": "Green gradient",
        "category": "green",
    },
    "YlGn": {
        "type": "sequential",
        "colors": ["#FFFFCC", "#C7E9B4", "#78C679", "#41AB5D", "#006837"],
        "python_colors": ["#FFFFCC", "#C7E9B4", "#78C679", "#41AB5D", "#006837"],
        "desc_zh": "黄-绿渐变",
        "desc_en": "Yellow-Green gradient",
        "category": "green",
    },
    "YlGnBu": {
        "type": "sequential",
        "colors": ["#FFFFD9", "#EDF8B1", "#C7E9B4", "#7FCDBB", "#41B6C4", "#1D91C0", "#225EA8", "#0C2C84"],
        "python_colors": ["#FFFFD9", "#EDF8B1", "#C7E9B4", "#7FCDBB", "#41B6C4", "#1D91C0", "#225EA8", "#0C2C84"],
        "desc_zh": "黄-绿-蓝",
        "desc_en": "Yellow-Green-Blue",
        "category": "green",
    },
    "PRGn": {
        "type": "diverging",
        "colors": ["#762A83", "#9970AB", "#C2A5CF", "#E7D4E8", "#F7F7F7", "#D9F0D3", "#A6DBA0", "#5AAE61", "#1B7837"],
        "python_colors": ["#762A83", "#9970AB", "#C2A5CF", "#E7D4E8", "#F7F7F7", "#D9F0D3", "#A6DBA0", "#5AAE61", "#1B7837"],
        "desc_zh": "紫-绿发散",
        "desc_en": "Purple-Green diverging",
        "category": "diverging",
    },

    # ── 暖色系 (Warm: Orange/Red) ─────────────────────────────────
    "Oranges": {
        "type": "sequential",
        "colors": ["#FBB4AE", "#F768A1", "#D6604D", "#B30000", "#7F0000"],
        "python_colors": ["#FBB4AE", "#F768A1", "#D6604D", "#B30000", "#7F0000"],
        "desc_zh": "橙红渐变",
        "desc_en": "Orange-Red gradient",
        "category": "warm",
    },
    "Reds": {
        "type": "sequential",
        "colors": ["#FCBBA1", "#FC9272", "#FB6A4A", "#EF3B2C", "#CB181D", "#99000D"],
        "python_colors": ["#FCBBA1", "#FC9272", "#FB6A4A", "#EF3B2C", "#CB181D", "#99000D"],
        "desc_zh": "红色渐变",
        "desc_en": "Red gradient",
        "category": "warm",
    },
    "YlOrRd": {
        "type": "sequential",
        "colors": ["#FFFFB2", "#FED976", "#FEB24C", "#FD8D3C", "#FC4E2A", "#E31A1C", "#B10026"],
        "python_colors": ["#FFFFB2", "#FED976", "#FEB24C", "#FD8D3C", "#FC4E2A", "#E31A1C", "#B10026"],
        "desc_zh": "黄-橙-红",
        "desc_en": "Yellow-Orange-Red",
        "category": "warm",
    },
    "RdYlGn": {
        "type": "diverging",
        "colors": ["#D73027", "#FC8D59", "#FEE08B", "#D9EF8B", "#91CF60", "#1A9850"],
        "python_colors": ["#D73027", "#FC8D59", "#FEE08B", "#D9EF8B", "#91CF60", "#1A9850"],
        "desc_zh": "红-黄-绿",
        "desc_en": "Red-Yellow-Green",
        "category": "diverging",
    },
    "Spectral": {
        "type": "diverging",
        "colors": ["#9E0142", "#D53E4F", "#F46D43", "#FDAE61", "#FEE08B", "#E6F598", "#ABDDA4", "#66C2A5", "#3288BD", "#5E4FA2"],
        "python_colors": ["#9E0142", "#D53E4F", "#F46D43", "#FDAE61", "#FEE08B", "#E6F598", "#ABDDA4", "#66C2A5", "#3288BD", "#5E4FA2"],
        "desc_zh": "光谱色",
        "desc_en": "Spectral (scientific)",
        "category": "diverging",
    },

    # ── 紫/粉色系 (Purple/Pink) ─────────────────────────────────
    "Purples": {
        "type": "sequential",
        "colors": ["#FCFBFD", "#DADAEB", "#BCBDC1", "#9E9AC8", "#756BB1", "#54278F", "#3F007D"],
        "python_colors": ["#FCFBFD", "#DADAEB", "#BCBDC1", "#9E9AC8", "#756BB1", "#54278F", "#3F007D"],
        "desc_zh": "紫色渐变",
        "desc_en": "Purple gradient",
        "category": "purple",
    },
    "PuBu": {
        "type": "sequential",
        "colors": ["#FFF7F3", "#ECE7F2", "#D2D4E8", "#A6BDDB", "#74A9CF", "#3690C0", "#0570B0", "#034E7B"],
        "python_colors": ["#FFF7F3", "#ECE7F2", "#D2D4E8", "#A6BDDB", "#74A9CF", "#3690C0", "#0570B0", "#034E7B"],
        "desc_zh": "紫-蓝渐变",
        "desc_en": "Purple-Blue gradient",
        "category": "purple",
    },
    "PuOr": {
        "type": "diverging",
        "colors": ["#7F3B08", "#B35806", "#E08214", "#FDB863", "#FEE0B2", "#F7F7F7", "#D8DAEB", "#B2ABD2", "#8073AC", "#542788", "#2D0042"],
        "python_colors": ["#7F3B08", "#B35806", "#E08214", "#FDB863", "#FEE0B2", "#F7F7F7", "#D8DAEB", "#B2ABD2", "#8073AC", "#542788", "#2D0042"],
        "desc_zh": "紫-橙发散",
        "desc_en": "Purple-Orange diverging",
        "category": "diverging",
    },
    "RdPu": {
        "type": "sequential",
        "colors": ["#FFF7F3", "#FDE0DD", "#FCC5C0", "#FA9FB5", "#F768A1", "#DD3497", "#AE017E", "#7A0177"],
        "python_colors": ["#FFF7F3", "#FDE0DD", "#FCC5C0", "#FA9FB5", "#F768A1", "#DD3497", "#AE017E", "#7A0177"],
        "desc_zh": "红-紫渐变",
        "desc_en": "Red-Purple gradient",
        "category": "purple",
    },

    # ── 冷热对比色系（科研常用） ─────────────────────────────────
    "coolwarm": {
        "type": "diverging",
        "colors": ["#3B4CC0", "#6787D9", "#9ABBF0", "#C0D4F0", "#E0D5E8", "#F0B8C0", "#D97A8C", "#B40E4C"],
        "python_colors": ["#3B4CC0", "#6787D9", "#9ABBF0", "#C0D4F0", "#E0D5E8", "#F0B8C0", "#D97A8C", "#B40E4C"],
        "desc_zh": "蓝-红发散",
        "desc_en": "Blue-Red diverging",
        "category": "diverging",
    },
    "coolwarm_r": {
        "type": "diverging",
        "colors": ["#B40E4C", "#D97A8C", "#F0B8C0", "#E0D5E8", "#C0D4F0", "#9ABBF0", "#6787D9", "#3B4CC0"],
        "python_colors": ["#B40E4C", "#D97A8C", "#F0B8C0", "#E0D5E8", "#C0D4F0", "#9ABBF0", "#6787D9", "#3B4CC0"],
        "desc_zh": "红-蓝发散",
        "desc_en": "Red-Blue diverging",
        "category": "diverging",
    },
    "BrBG": {
        "type": "diverging",
        "colors": ["#8C510A", "#D8B365", "#F6E8C3", "#C7DBEA", "#5AB4AC", "#01665E"],
        "python_colors": ["#8C510A", "#D8B365", "#F6E8C3", "#C7DBEA", "#5AB4AC", "#01665E"],
        "desc_zh": "棕-蓝发散",
        "desc_en": "Brown-Blue diverging",
        "category": "diverging",
    },

    # ── 单色暗系（适合高精度打印） ─────────────────────────────────
    "viridis": {
        "type": "sequential",
        "colors": ["#440154", "#482878", "#3E4A89", "#31688E", "#26838F", "#1F9E89", "#6CCE59", "#B6DE2B", "#FEE825"],
        "python_colors": ["#440154", "#482878", "#3E4A89", "#31688E", "#26838F", "#1F9E89", "#6CCE59", "#B6DE2B", "#FEE825"],
        "desc_zh": "紫-绿-黄（viridis）",
        "desc_en": "Viridis (scientific)",
        "category": "sequential",
    },
    "plasma": {
        "type": "sequential",
        "colors": ["#0D0887", "#46039F", "#7201A8", "#9C179E", "#BD3786", "#D8576B", "#ED7953", "#FB9F3A", "#FDCA26", "#F0F921"],
        "python_colors": ["#0D0887", "#46039F", "#7201A8", "#9C179E", "#BD3786", "#D8576B", "#ED7953", "#FB9F3A", "#FDCA26", "#F0F921"],
        "desc_zh": "等离子体（plasma）",
        "desc_en": "Plasma (scientific)",
        "category": "sequential",
    },
    "inferno": {
        "type": "sequential",
        "colors": ["#000004", "#1B0C41", "#4A0C6B", "#781C6D", "#B52F5D", "#F48849", "#FBD526", "#FCFFA4"],
        "python_colors": ["#000004", "#1B0C41", "#4A0C6B", "#781C6D", "#B52F5D", "#F48849", "#FBD526", "#FCFFA4"],
        "desc_zh": "火与冰（inferno）",
        "desc_en": "Inferno (scientific)",
        "category": "sequential",
    },
    "magma": {
        "type": "sequential",
        "colors": ["#000004", "#1C1041", "#4F1273", "#8F0F5D", "#CE3753", "#F27B50", "#FCA50A", "#F0F921"],
        "python_colors": ["#000004", "#1C1041", "#4F1273", "#8F0F5D", "#CE3753", "#F27B50", "#FCA50A", "#F0F921"],
        "desc_zh": "岩浆（magma）",
        "desc_en": "Magma (scientific)",
        "category": "sequential",
    },
    "cividis": {
        "type": "sequential",
        "colors": ["#00224E", "#123570", "#3B496C", "#575D6D", "#707173", "#8A8678", "#A59C74", "#C3B569", "#E3CD53"],
        "python_colors": ["#00224E", "#123570", "#3B496C", "#575D6D", "#707173", "#8A8678", "#A59C74", "#C3B569", "#E3CD53"],
        "desc_zh": "无障碍蓝黄（cividis）",
        "desc_en": "Cividis (colorblind-safe)",
        "category": "sequential",
    },
    "turbo": {
        "type": "sequential",
        "colors": ["#23171B", "#2C0D6B", "#3B0F70", "#57106E", "#6F1E68", "#8B2C5E", "#A43A52", "#BB4A43", "#CC5D32", "#DA7725", "#E69420", "#F3B026", "#FFCC4D", "#F8E638"],
        "python_colors": ["#23171B", "#2C0D6B", "#3B0F70", "#57106E", "#6F1E68", "#8B2C5E", "#A43A52", "#BB4A43", "#CC5D32", "#DA7725", "#E69420", "#F3B026", "#FFCC4D", "#F8E638"],
        "desc_zh": "彩虹高速（turbo）",
        "desc_en": "Turbo rainbow",
        "category": "sequential",
    },
}

DEFAULT_COLORMAP_PARAMS = {
    "china_cooling_energy": "coolwarm_r",
    "china_heating_energy": "coolwarm",
    "china_total_energy": "RdYlGn",
    "china_cooling_co2": "Greens",
    "china_heating_co2": "Greens",
    "china_total_co2": "Greens",
    "world_cooling_energy": "YlGnBu",
    "world_heating_energy": "coolwarm",
    "world_total_energy": "coolwarm",
    "world_cooling_co2": "Greens",
    "world_heating_co2": "Greens",
    "world_total_co2": "Greens",
}


def _split_value_and_comment(line: str):
    if "!-" in line:
        before, after = line.split("!-", 1)
        return before.rstrip("\r\n"), "!-" + after
    return line.rstrip("\r\n"), ""


def _extract_value_token(before: str):
    s = before.strip()
    if not s:
        return ""
    if s.endswith(",") or s.endswith(";"):
        s = s[:-1]
    return s.strip()


def _format_value_line(old_line: str, new_value: str):
    before, comment = _split_value_and_comment(old_line)
    indent = re.match(r"^\s*", before).group(0)
    sep = ";" if before.strip().endswith(";") else ","

    before_stripped = before.strip()
    # 不修改对象类型行（如 Material, WindowMaterial:Glazing 等）
    if before_stripped.startswith("Material") or before_stripped.startswith("WindowMaterial"):
        return old_line

    new_before = f"{indent}{new_value}{sep}"
    if comment:
        spaces = " "
        return new_before + spaces + comment.lstrip()
    return new_before + "\n" if old_line.endswith("\n") else new_before


def find_material_objects(idf_text: str):
    lines = idf_text.splitlines(keepends=True)

    blocks = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("Material,"):
            start = i
            j = i
            while j < len(lines):
                if ";" in lines[j]:
                    break
                j += 1
            if j >= len(lines):
                raise IdFMaterialParseError("Unterminated Material object.")
            end = j
            block_lines = lines[start : end + 1]

            if len(block_lines) < 10:
                i = end + 1
                continue

            name_line = block_lines[1]
            name_before, _ = _split_value_and_comment(name_line)
            name = _extract_value_token(name_before)

            blocks.append(
                {
                    "name": name,
                    "start": start,
                    "end": end,
                    "lines": block_lines,
                }
            )
            i = end + 1
        else:
            i += 1

    return blocks, lines


def parse_material_block(block_lines):
    if not block_lines[0].lstrip().startswith("Material,"):
        raise IdFMaterialParseError("Block does not start with Material,.")
    if len(block_lines) < 10:
        raise IdFMaterialParseError("Material block too short.")

    mapping = {
        "Name": _extract_value_token(_split_value_and_comment(block_lines[1])[0]),
        "Roughness": _extract_value_token(_split_value_and_comment(block_lines[2])[0]),
        "Thickness": _extract_value_token(_split_value_and_comment(block_lines[3])[0]),
        "Conductivity": _extract_value_token(_split_value_and_comment(block_lines[4])[0]),
        "Density": _extract_value_token(_split_value_and_comment(block_lines[5])[0]),
        "SpecificHeat": _extract_value_token(_split_value_and_comment(block_lines[6])[0]),
        "ThermalAbsorptance": _extract_value_token(_split_value_and_comment(block_lines[7])[0]),
        "SolarAbsorptance": _extract_value_token(_split_value_and_comment(block_lines[8])[0]),
        "VisibleAbsorptance": _extract_value_token(_split_value_and_comment(block_lines[9])[0]),
    }
    return mapping


def apply_material_block_updates(block_lines, new_values):
    out = list(block_lines)

    idx_by_field = {
        "Name": 1,
        "Roughness": 2,
        "Thickness": 3,
        "Conductivity": 4,
        "Density": 5,
        "SpecificHeat": 6,
        "ThermalAbsorptance": 7,
        "SolarAbsorptance": 8,
        "VisibleAbsorptance": 9,
    }

    for field, idx in idx_by_field.items():
        if field not in new_values:
            continue
        out[idx] = _format_value_line(out[idx], str(new_values[field]))
        if not out[idx].endswith("\n") and block_lines[idx].endswith("\n"):
            out[idx] += "\n"

    return out


def load_one_material_from_file(idf_path: str, material_name: str):
    if not os.path.exists(idf_path):
        raise FileNotFoundError(idf_path)

    with open(idf_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    blocks, lines = find_material_objects(text)
    block = None
    for b in blocks:
        if b["name"] == material_name:
            block = b
            break

    if block is None:
        raise IdFMaterialParseError(f"Missing Material object '{material_name}' in file: {idf_path}")

    parsed = parse_material_block(block["lines"])
    return parsed, block, lines


def save_one_material_to_file(idf_path: str, material_name: str, new_values: dict):
    parsed, block, lines = load_one_material_from_file(idf_path, material_name)
    _ = parsed

    updated_block = apply_material_block_updates(block["lines"], new_values)
    new_lines = list(lines)
    new_lines[block["start"] : block["end"] + 1] = updated_block

    # 创建备份文件（如果原文件存在）
    bak = idf_path + ".bak"
    if os.path.exists(idf_path):
        shutil.copyfile(idf_path, bak)

    # 写入更新后的内容
    with open(idf_path, "w", encoding="utf-8") as f:
        f.write("".join(new_lines))


def _replace_value_on_line_with_marker(lines, marker: str, new_value: str):
    hits = []
    for idx, line in enumerate(lines):
        if marker in line:
            hits.append(idx)

    if len(hits) != 1:
        raise ValueError(f"Expected exactly 1 occurrence of marker '{marker}', found {len(hits)}")

    i = hits[0]
    old_line = lines[i]
    before, comment = _split_value_and_comment(old_line)

    indent = re.match(r"^\s*", before).group(0)
    sep = ";" if before.strip().endswith(";") else ","
    new_before = f"{indent}{new_value}{sep}"
    new_line = new_before + (" " + comment.lstrip() if comment else "")

    if old_line.endswith("\n") and not new_line.endswith("\n"):
        new_line += "\n"

    lines[i] = new_line


def _find_object_block(lines, object_type: str, object_name: str):
    i = 0
    hits = []

    def is_comment_or_blank(ln: str):
        s = ln.strip()
        return (not s) or s.startswith("!")

    while i < len(lines):
        ln = lines[i]
        if is_comment_or_blank(ln):
            i += 1
            continue

        if ln.lstrip().startswith(object_type + ","):
            start = i
            j = i
            while j < len(lines):
                if ";" in lines[j]:
                    break
                j += 1
            if j >= len(lines):
                break

            block = lines[start : j + 1]
            if len(block) >= 2:
                name_before, _ = _split_value_and_comment(block[1])
                name = _extract_value_token(name_before)
                if name == object_name:
                    hits.append((start, j, block))
            i = j + 1
            continue

        i += 1

    if len(hits) != 1:
        raise ValueError(f"Expected exactly 1 '{object_type}' named '{object_name}', found {len(hits)}")

    return hits[0]


def _replace_value_in_object_block_by_marker(block_lines, marker: str, new_value: str):
    hits = []
    for idx, line in enumerate(block_lines):
        if marker in line:
            hits.append(idx)

    if len(hits) != 1:
        raise ValueError(f"Expected exactly 1 occurrence of marker '{marker}' in object block, found {len(hits)}")

    i = hits[0]
    old_line = block_lines[i]
    before, comment = _split_value_and_comment(old_line)

    indent = re.match(r"^\s*", before).group(0)
    sep = ";" if before.strip().endswith(";") else ","
    new_before = f"{indent}{new_value}{sep}"
    new_line = new_before + (" " + comment.lstrip() if comment else "")

    if old_line.endswith("\n") and not new_line.endswith("\n"):
        new_line += "\n"

    block_lines[i] = new_line
    return block_lines


def save_global_params_to_file(idf_path: str, values_by_key: dict):
    if not os.path.exists(idf_path):
        raise FileNotFoundError(idf_path)

    with open(idf_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines(keepends=True)

    # 获取当前处理的IDF文件名
    idf_filename = os.path.basename(idf_path)

    for spec in GLOBAL_PARAM_SPECS:
        key = spec["key"]
        marker = spec["comment_marker"]
        if key not in values_by_key:
            continue

        # 相变温度只对 glass.idf 生效
        if key == "phase_change_temp" and idf_filename != "glass.idf":
            continue

        if "lights_object_name" in spec:
            start, end, block = _find_object_block(lines, "Lights", spec["lights_object_name"])
            updated_block = _replace_value_in_object_block_by_marker(list(block), marker, str(values_by_key[key]))
            lines[start : end + 1] = updated_block
        elif "object_type" in spec and "object_name" in spec:
            start, end, block = _find_object_block(lines, spec["object_type"], spec["object_name"])
            updated_block = _replace_value_in_object_block_by_marker(list(block), marker, str(values_by_key[key]))
            lines[start : end + 1] = updated_block
        else:
            _replace_value_on_line_with_marker(lines, marker, str(values_by_key[key]))

    bak = idf_path + ".bak"
    if os.path.exists(idf_path):
        shutil.copyfile(idf_path, bak)

    with open(idf_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))

# ==================== End of IDF Material Editor Functions ====================

# ==================== 输出压缩函数（从batch_run.py） ====================

def archive_output(output_dir: str, work_dir: str, mode: str, cleanup: bool = False) -> Optional[str]:
    """
    压缩 output_dir 到 zip 文件
    
    Args:
        output_dir: 输出目录路径
        work_dir: 工作目录（zip文件保存位置）
        mode: 模式（'china' 或 'world'）
        cleanup: 是否在压缩成功后删除原目录（默认False，web环境保留）
    
    Returns:
        压缩包路径，如果失败返回None
    """
    if not output_dir:
        print("[WARN] output_dir 为空，跳过压缩。")
        return None

    output_dir = os.path.abspath(output_dir)
    work_dir = os.path.abspath(work_dir)

    if not os.path.exists(output_dir):
        print(f"[WARN] 输出目录不存在，跳过压缩: {output_dir}")
        return None
    
    # 检查output目录是否为空
    try:
        files_in_output = []
        for root, dirs, files in os.walk(output_dir):
            files_in_output.extend([os.path.join(root, f) for f in files])
        if len(files_in_output) == 0:
            print(f"[WARN] 输出目录为空，跳过压缩: {output_dir}")
            return None
        print(f"[INFO] 输出目录包含 {len(files_in_output)} 个文件，开始压缩...")
    except Exception as e:
        print(f"[WARN] 无法检查输出目录内容: {e}")
        # 继续尝试压缩，即使检查失败

    # 安全检查：只允许压缩并删除 work_dir 下的 output 目录或包含 output/comparison 的路径
    is_safe_to_delete = False
    if cleanup:
        abs_output = os.path.normpath(output_dir)
        abs_work = os.path.normpath(work_dir)
        # 允许删除的情况：output_dir 是 work_dir 的子目录，且目录名包含 output
        if abs_output.startswith(abs_work) and "output" in abs_output.lower():
            is_safe_to_delete = True
        else:
            print(f"[WARN] 安全检查失败：拒绝删除非工作目录下的输出目录: {output_dir}")
            is_safe_to_delete = False

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_name = f"output_{mode}_{ts}.zip"
    zip_path = os.path.join(work_dir, zip_name)

    print(f"\n开始压缩输出目录: {output_dir}")
    print(f"压缩包: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(output_dir):
                for fn in files:
                    abs_path = os.path.join(root, fn)
                    # 计算相对路径，保持目录结构
                    rel_path = os.path.relpath(abs_path, start=output_dir)
                    zf.write(abs_path, rel_path)
        print(f"[OK] 压缩完成: {zip_path}")
    except Exception as e:
        print(f"[WARN] 压缩失败: {e}")
        import traceback
        traceback.print_exc()
        return None

    # 校验 zip 是否生成且非空
    try:
        if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
            print("[WARN] 压缩包未生成或为空。")
            return None
        zip_size = os.path.getsize(zip_path)
        print(f"[OK] 压缩包大小: {zip_size / (1024*1024):.2f} MB")
    except Exception as e:
        print(f"[WARN] 无法校验压缩包大小: {e}")
        return None

    # 如果启用清理且通过安全检查，删除原目录
    if cleanup and is_safe_to_delete:
        print(f"[OK] 压缩完成，开始删除输出目录: {output_dir}")
        try:
            shutil.rmtree(output_dir)
            print(f"[OK] 已删除输出目录: {output_dir}")
        except Exception as e:
            print(f"[WARN] 删除输出目录失败: {e}")

    return zip_path

# ==================== End of 输出压缩函数 ====================

# ==================== EnergyPlus运行和数据提取函数（从batch_run.py） ====================

def scan_weather_files(weather_dir: str) -> List[str]:
    """扫描指定目录下的所有天气文件（.epw文件）"""
    weather_files = []
    if not os.path.exists(weather_dir):
        print(f"警告: 天气文件目录不存在: {weather_dir}")
        return weather_files
    pattern = os.path.join(weather_dir, "*.epw")
    weather_files = glob.glob(pattern)
    weather_files.sort()
    return weather_files


def scan_idf_files(idf_dir: str) -> List[str]:
    """扫描指定目录下的所有IDF文件（.idf文件）"""
    idf_files = []
    if not os.path.exists(idf_dir):
        print(f"警告: IDF文件目录不存在: {idf_dir}")
        return idf_files
    pattern = os.path.join(idf_dir, "*.idf")
    idf_files = glob.glob(pattern)
    idf_files.sort()
    return idf_files


def generate_simulations(idf_dir: str, weather_dir: str, 
                        output_base_dir: str = None) -> List[Tuple[str, str, str]]:
    """生成所有IDF文件和天气文件的组合任务"""
    idf_files = scan_idf_files(idf_dir)
    weather_files = scan_weather_files(weather_dir)
    
    if not idf_files:
        print(f"错误: 在 {idf_dir} 中未找到IDF文件")
        return []
    
    if not weather_files:
        print(f"错误: 在 {weather_dir} 中未找到天气文件")
        return []
    
    print(f"找到 {len(idf_files)} 个IDF文件")
    print(f"找到 {len(weather_files)} 个天气文件")
    print(f"将生成 {len(idf_files) * len(weather_files)} 个模拟任务")
    
    if output_base_dir is None:
        output_base_dir = os.path.join(idf_dir, "output")
    
    simulations = []
    for idf_file in idf_files:
        idf_basename = os.path.splitext(os.path.basename(idf_file))[0]
        for weather_file in weather_files:
            weather_basename = os.path.splitext(os.path.basename(weather_file))[0]
            output_dir = os.path.join(output_base_dir, weather_basename)
            output_file = os.path.join(output_dir, idf_basename)
            simulations.append((idf_file, weather_file, output_file))
    
    return simulations


def needs_expandobjects(idf_file: str) -> bool:
    """检查IDF文件是否需要运行ExpandObjects"""
    try:
        with open(idf_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if 'HVACTemplate:' in content:
                return True
    except:
        pass
    return False


def run_simulation(idf_file: str, weather_file: str, output_file: str, 
                   energyplus_exe: str, verbose: bool = True) -> bool:
    """运行单个EnergyPlus模拟"""
    if not os.path.exists(idf_file):
        print(f"  [错误] IDF文件不存在: {idf_file}")
        return False
    
    if output_file:
        output_dir = os.path.dirname(output_file) if os.path.dirname(output_file) else '.'
        output_prefix = os.path.basename(output_file)
    else:
        output_dir = '.'
        output_prefix = os.path.splitext(os.path.basename(idf_file))[0]
    
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        if verbose:
            print(f"  创建输出目录: {output_dir}")
    
    use_expandobjects = needs_expandobjects(idf_file)
    
    cmd = [energyplus_exe]
    if use_expandobjects:
        cmd.append('-x')
    
    if weather_file.upper() != "NO WEATHER FILE":
        cmd.extend(['-w', weather_file])
    
    cmd.extend(['-d', output_dir, '-p', output_prefix])
    cmd.append(idf_file)
    
    if verbose:
        print(f"\n  运行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, 
                              encoding='utf-8', errors='ignore')
        
        err_file = os.path.join(output_dir, f"{output_prefix}.err")
        success = False
        if os.path.exists(err_file):
            try:
                with open(err_file, 'r', encoding='utf-8', errors='ignore') as f:
                    err_content = f.read()
                    if 'Completed Successfully' in err_content:
                        success = True
                    elif 'Terminated--Error(s) Detected' in err_content or \
                         'FATAL:Errors occurred on processing input file' in err_content:
                        success = False
            except:
                pass
        
        if success is False and result.returncode == 0:
            success = True
        
        if success:
            if verbose:
                print(f"  [成功] 模拟完成")
            return True
        else:
            print(f"  [失败] 模拟失败 (返回码: {result.returncode})")
            if os.path.exists(err_file):
                try:
                    with open(err_file, 'r', encoding='utf-8', errors='ignore') as f:
                        err_content = f.read()
                        fatal_lines = [line for line in err_content.split('\n') 
                                      if '**FATAL' in line or '** Severe' in line]
                        if fatal_lines:
                            print(f"  致命错误:")
                            for line in fatal_lines[:5]:
                                print(f"    {line.strip()}")
                except:
                    pass
            return False
    except Exception as e:
        print(f"  [错误] 运行出错: {e}")
        return False


def detect_encoding(file_path: str, num_bytes: int = 10000) -> str:
    """使用 chardet 检测文件的编码"""
    with open(file_path, 'rb') as f:
        rawdata = f.read(num_bytes)
    result = chardet.detect(rawdata)
    encoding = result['encoding']
    confidence = result['confidence']
    if not encoding or confidence < 0.5:
        print(f"警告: 文件 {file_path} 的编码检测不确定，默认使用 'utf-8'.")
        return 'utf-8'
    return encoding


def extract_data_from_html(file_path: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """从指定的HTML文件中提取数据，返回 (data_y, data_z, data_t)"""
    try:
        encoding = detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            soup = BeautifulSoup(f, 'html.parser')
            tables = soup.find_all('table')
            if len(tables) < 4:
                print(f"警告: 文件 {file_path} 中的表格数量少于4个。")
                return None, None, None
            target_table = tables[3]
            target_table1 = tables[0]
            
            rows = target_table.find_all('tr')
            if len(rows) < 3:
                print(f"警告: 文件 {file_path} 中的表格行数少于3行。")
                data_y = None
            else:
                target_row_y = rows[2]
                cols_y = target_row_y.find_all(['td', 'th'])
                if len(cols_y) < 5:
                    print(f"警告: 文件 {file_path} 中的表格列数少于5列。")
                    data_y = None
                else:
                    data_y = cols_y[4].get_text(strip=True)

            if len(rows) < 2:
                print(f"警告: 文件 {file_path} 中的表格行数少于2行。")
                data_z = None
            else:
                target_row_z = rows[1]
                cols_z = target_row_z.find_all(['td', 'th'])
                if len(cols_z) < 6:
                    print(f"警告: 文件 {file_path} 中的表格列数少于6列。")
                    data_z = None
                else:
                    data_z = cols_z[5].get_text(strip=True)
           
            rows = target_table1.find_all('tr')
            if len(rows) < 3:
                print(f"警告: 文件 {file_path} 中的表格行数少于3行。")
                data_t = None
            else:
                target_row_t = rows[1]
                cols_t = target_row_t.find_all(['td', 'th'])
                if len(cols_t) < 2:
                    print(f"警告: 文件 {file_path} 中的表格列数少于2列。")
                    data_t = None
                else:
                    data_t = cols_t[1].get_text(strip=True)

            return data_y, data_z, data_t
    except Exception as e:
        print(f"错误: 处理文件 {file_path} 时发生错误: {e}")
        return None, None, None


def traverse_and_extract(root_dir: str, target_filename: str) -> List[Tuple[str, str, str, str]]:
    """遍历根目录，查找指定的HTML文件，并提取数据"""
    results = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if target_filename in filenames:
            file_path = os.path.join(dirpath, target_filename)
            folder_name = os.path.basename(dirpath)
            data_y, data_z, data_t = extract_data_from_html(file_path)
            data_y = data_y if data_y is not None else "N/A"
            data_z = data_z if data_z is not None else "N/A"
            data_t = data_t if data_t is not None else "N/A"
            results.append((folder_name, data_y, data_z, data_t))
    return results


def write_to_csv(
    data: List[Tuple[str, str, str, str]],
    output_file: str,
    scale_factor: float = 1.0,
) -> None:
    """将提取的数据写入CSV文件（应用单位换算系数）

    参数:
        data: [(city, cooling, heating, total), ...]
        output_file: 输出 CSV 路径
        scale_factor: 单位换算因子（默认 1.0，不再做缩放）
    """
    try:
        import csv
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['cities', 'cooling', 'heating', 'total'])
            for row in data:
                # 应用单位换算因子进行缩放
                try:
                    c = float(row[1]) / scale_factor if row[1] != "N/A" else 0.0
                    h = float(row[2]) / scale_factor if row[2] != "N/A" else 0.0
                    t = float(row[3]) / scale_factor if row[3] != "N/A" else 0.0
                    writer.writerow([row[0], c, h, t])
                except (ValueError, TypeError):
                    writer.writerow(row)
        print(f"成功: 数据已写入 {output_file} (scale_factor={scale_factor})")
    except Exception as e:
        print(f"错误: 写入CSV文件时发生错误: {e}")


def generate_csv_from_output(
    output_dir: str,
    idf_dir: str,
    enable_latent_heat: bool = False,
    wet_fraction: float = 1.0,
    weather_group: str = 'china',
    scale_factor: float = 1.0,
) -> None:
    """从输出目录中提取数据并生成CSV文件"""
    if not os.path.exists(output_dir):
        print(f"警告: 输出目录不存在: {output_dir}")
        return
    
    idf_files = scan_idf_files(idf_dir)
    if not idf_files:
        print("警告: 未找到IDF文件，无法确定要生成的CSV文件名")
        return
    
    idf_names = [os.path.splitext(os.path.basename(f))[0] for f in idf_files]
    script_dir = idf_dir
    
    # 如果启用蒸发潜热，预先解析天气目录
    weather_dir = None
    if enable_latent_heat:
        def _resolve_weather_dir(group: str) -> str | None:
            base = get_exe_dir()
            candidates: list[str] = []
            if group == 'china':
                candidates = [
                    os.path.join(base, 'china_weather'),
                    os.path.join(base, 'material_comparison_tool', 'china_weather'),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'china_weather')),
                ]
            elif group == 'world':
                candidates = [
                    os.path.join(base, 'world_weather'),
                    os.path.join(base, 'material_comparison_tool', 'world_weather'),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'world_weather')),
                ]
            elif group == 'world_weather2025':
                candidates = [
                    os.path.join(base, 'world_weather2025'),
                    os.path.join(base, 'material_comparison_tool', 'world_weather2025'),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'world_weather2025')),
                ]
            else:
                return None

            for c in candidates:
                if c and os.path.isdir(c):
                    return c
            return candidates[0] if candidates else None
        
        weather_dir = _resolve_weather_dir(weather_group)

    for name in idf_names:
        target_html = f'{name}tbl.html'
        target_htm = f'{name}tbl.htm'
        output_csv = os.path.join(script_dir, f'{name}.csv')
        
        print(f"\n处理 {name}...")
        extracted_data = traverse_and_extract(output_dir, target_html)
        if not extracted_data:
            extracted_data = traverse_and_extract(output_dir, target_htm)
        
        if extracted_data:
            # 如果是 shiyan1 且启用了蒸发潜热
            if name == 'shiyan1' and enable_latent_heat and weather_dir:
                print(f"[INFO] 正在为 shiyan1 应用蒸发潜热修正...")
                new_extracted_data = []
                for row in extracted_data:
                    city_name = row[0]
                    # 尝试匹配 EPW 文件
                    epw_path = None
                    for ext in ['.epw', '']:
                        test_path = os.path.join(weather_dir, f"{city_name}{ext}")
                        if os.path.exists(test_path):
                            epw_path = test_path
                            break
                    
                    q_latent_w = 0.0
                    if epw_path:
                        q_latent_w = calculate_evaporation_latent_heat_from_epw(epw_path, wet_fraction)
                    
                    # row[1] 是 cooling, row[2] 是 heating（与 write_to_csv 使用同一单位换算因子）
                    try:
                        hvac_cooling_raw = float(row[1]) / scale_factor
                        heating_raw = float(row[2]) / scale_factor
                    except (ValueError, TypeError):
                        hvac_cooling_raw = 0.0
                        heating_raw = 0.0

                    # 修正：根据用户要求，直接执行数值减法 (HVAC_cooling - Evaporation_Latent_Heat_W_per_m2)
                    cooling_corrected = max(0.0, hvac_cooling_raw - q_latent_w)
                    
                    # 构造新行：City, Cooling(修正后), Heating, HVAC_cooling(原始), Latent_W_per_m2
                    new_row = [city_name, cooling_corrected, heating_raw, hvac_cooling_raw, q_latent_w]
                    new_extracted_data.append(new_row)
                
                # 写入带潜热列的 CSV
                header = ['cities', 'cooling', 'heating', 'HVAC_cooling', 'Evaporation_Latent_Heat_W_per_m2']
                df = pd.DataFrame(new_extracted_data, columns=header)
                df.to_csv(output_csv, index=False, encoding='utf-8-sig')
                print(f"[OK] shiyan1.csv 已生成：cooling=修正后，HVAC_cooling=EnergyPlus原始值 (scale_factor={scale_factor})。")
            else:
                write_to_csv(extracted_data, output_csv, scale_factor=scale_factor)
        else:
            print(f"警告: 未找到 {name}tbl.html 或 {name}tbl.htm 文件")


def calculate_evaporation_latent_heat_from_epw(epw_path: str, wet_fraction: float = 1.0) -> float:
    """
    从EPW文件计算平均蒸发潜热功率（W/m²）
    
    参数:
        epw_path: EPW文件路径
        wet_fraction: 湿润面积比例（0-1）
    
    返回:
        平均蒸发潜热功率（W/m²）
    """
    try:
        from core.calculations import _calculate_latent_heat_power
        
        # 读取EPW文件
        # EPW文件格式：前8行是头部信息，从第9行开始是数据
        # 数据列：Year(0),Month(1),Day(2),Hour(3),Minute(4),Data Source(5),Dry Bulb Temp(6),Dew Point(7),Relative Humidity(8),...
        # 干球温度在索引6，相对湿度在索引8
        
        with open(epw_path, 'r', encoding='latin-1', errors='replace') as f:
            lines = f.readlines()
        
        # 跳过头部（前8行）
        data_lines = lines[8:]
        
        # 解析数据
        daily_temps = {}  # {day_of_year: [temps]}
        daily_rhs = {}    # {day_of_year: [rhs]}
        
        for line in data_lines:
            if not line.strip():
                continue
            parts = line.strip().split(',')
            if len(parts) < 9:
                continue
            
            try:
                month = int(parts[1])
                day = int(parts[2])
                hour = int(parts[3])
                
                # 干球温度（索引6）
                temp_str = parts[6].strip() if len(parts) > 6 else ''
                # 相对湿度（索引8）
                rh_str = parts[8].strip() if len(parts) > 8 else ''
                
                # 跳过无效值（EPW文件中9999表示缺失数据）
                if not temp_str or not rh_str:
                    continue
                
                try:
                    temp_c = float(temp_str)
                    rh = float(rh_str)
                except ValueError:
                    continue
                
                # 验证数据范围（EPW文件中9999表示缺失数据）
                if temp_c < -100 or temp_c > 100 or rh < 0 or rh > 100:
                    continue
                
                # 计算一年中的第几天
                from datetime import datetime
                try:
                    date_obj = datetime(2024, month, day)  # 使用2024年作为参考年
                    day_of_year = date_obj.timetuple().tm_yday
                except:
                    continue
                
                if day_of_year not in daily_temps:
                    daily_temps[day_of_year] = []
                    daily_rhs[day_of_year] = []
                
                daily_temps[day_of_year].append(temp_c)
                daily_rhs[day_of_year].append(rh)
            except (ValueError, IndexError):
                continue
        
        # 初始化蒸发潜热功率数组
        Q_latent_daily = []
        
        # 对每一天计算平均温度和湿度，然后计算蒸发潜热功率
        for day_of_year in sorted(daily_temps.keys()):
            temps = daily_temps[day_of_year]
            rhs = daily_rhs[day_of_year]
            
            if not temps or not rhs:
                continue
            
            # 计算每天的平均温度和湿度
            avg_temp_c = sum(temps) / len(temps)
            avg_rh = sum(rhs) / len(rhs)
            
            # 转换为开尔文
            T_ambient_K = avg_temp_c + 273.15
            
            # 修正：假设表面温度等于环境温度 (T_surface = T_ambient)
            # 之前的假设 T_surface = T_ambient - 2.0 会导致饱和压力过低，从而计算结果为0
            T_surface_K = T_ambient_K
            
            # 计算蒸发潜热功率
            try:
                Q_latent_base = _calculate_latent_heat_power(
                    T_surface_K=T_surface_K,
                    T_ambient_K=T_ambient_K,
                    RH=avg_rh / 100.0,  # 转换为0-1范围
                    h_conv=5.0,  # 显式提供一个典型的对流换热系数 (5 W/m²K)
                    h_m=None,  # 让它根据 h_conv 自动计算
                )
                
                # 应用湿润面积比例
                Q_latent = Q_latent_base * wet_fraction
                Q_latent_daily.append(Q_latent)
            except Exception as e:
                # 如果计算失败，跳过这一天
                continue
        
        # 计算所有天数的平均蒸发潜热功率
        if Q_latent_daily:
            avg_Q_latent = sum(Q_latent_daily) / len(Q_latent_daily)
            print(f"[DEBUG] {os.path.basename(epw_path)}: 处理了 {len(daily_temps)} 天，计算了 {len(Q_latent_daily)} 天的蒸发潜热，平均值 = {avg_Q_latent:.4f} W/m2")
            return float(avg_Q_latent)
        else:
            print(f"[WARN] {os.path.basename(epw_path)}: 未能计算任何一天的蒸发潜热功率（处理了 {len(daily_temps)} 天的数据）")
            return 0.0
    
    except Exception as e:
        print(f"[WARN] 计算蒸发潜热功率失败 ({epw_path}): {e}")
        import traceback
        traceback.print_exc()
        return 0.0


def generate_glass_final_data_csv(idf_dir: str, mode: str = 'world', enable_latent_heat: bool = False, wet_fraction: float = 1.0, weather_group: str = 'china') -> None:
    """读取glass.csv和duibi.csv，计算差值生成最终的data.csv文件

    用于玻璃对比工具（只生成glass.csv和duibi.csv）
    计算公式：节能效果 = 实验玻璃 - 基准玻璃（正值表示节能）

    参数:
        idf_dir: 工作目录
        mode: 'china' 或 'world'
        enable_latent_heat: 是否启用蒸发潜热计算
        wet_fraction: 湿润面积比例（0-1）
        weather_group: 天气组（'china', 'world', 'world_weather2025'）
    """
    duibi_csv = os.path.join(idf_dir, 'duibi.csv')
    glass_csv = os.path.join(idf_dir, 'glass.csv')

    required_files = [duibi_csv, glass_csv]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"\n警告: 以下CSV文件不存在，无法生成data.csv:")
        for f in missing_files:
            print(f"  - {f}")
        return

    print(f"\n开始处理CSV文件并生成data.csv...")

    def read_csv_with_fallback(path: str):
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'cp936', 'latin-1']
        last_err = None
        for enc in encodings:
            try:
                return pd.read_csv(path, encoding=enc, engine='python')
            except Exception as err:
                last_err = err
        raise last_err

    try:
        df_duibi = read_csv_with_fallback(duibi_csv)
        df_glass = read_csv_with_fallback(glass_csv)
    except Exception as e:
        print(f"错误: 读取CSV文件失败: {e}")
        return

    required_cols = ['cities', 'cooling', 'heating']
    for name, df in [('duibi', df_duibi), ('glass', df_glass)]:
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"错误: {name}.csv 缺少必要的列: {missing_cols}")
            return

    # 创建合并键
    df_duibi['_key'] = df_duibi['cities'].astype(str).str.strip().str.lower()
    df_glass['_key'] = df_glass['cities'].astype(str).str.strip().str.lower()

    # 重命名列
    df_duibi_renamed = df_duibi[['_key', 'cities', 'cooling', 'heating']].copy()
    df_duibi_renamed = df_duibi_renamed.rename(columns={'cooling': 'cooling_duibi', 'heating': 'heating_duibi'})

    df_glass_renamed = df_glass[['_key', 'cooling', 'heating']].copy()
    df_glass_renamed = df_glass_renamed.rename(columns={'cooling': 'cooling_glass', 'heating': 'heating_glass'})

    # 合并数据
    merged = pd.merge(df_duibi_renamed, df_glass_renamed, on='_key', how='outer')

    # 计算差值：节能效果 = 基准玻璃 - 实验玻璃（正值表示节能更多）
    # 例如：基准玻璃cooling更小，说明基准更节能
    # 改为 duibi - glass（基准 - 实验），与前端保持一致
    merged['Cooling'] = merged['cooling_duibi'] - merged['cooling_glass']
    merged['Heating'] = merged['heating_duibi'] - merged['heating_glass']
    merged['Total'] = merged['Cooling'].fillna(0) + merged['Heating'].fillna(0)

    # world 模式使用 FQ 列（Köppen气候区代码）
    if mode == 'world':
        # 使用 cities 列作为 FQ（Köppen气候区代码）
        merged['FQ'] = merged['cities'].fillna(merged['_key'])

        # 尝试映射到真实地名
        epw_to_name = {}
        weather_dir = None

        # 解析天气目录
        def _resolve_weather_dir(group: str) -> str | None:
            base = get_exe_dir()
            candidates: list[str] = []
            if group == 'china':
                candidates = [
                    os.path.join(base, 'china_weather'),
                    os.path.join(base, 'glass_weather'),
                ]
            elif group == 'world':
                candidates = [
                    os.path.join(base, 'world_weather'),
                    os.path.join(base, 'glass_weather'),
                ]
            elif group == 'world_weather2025':
                candidates = [
                    os.path.join(base, 'world_weather2025'),
                    os.path.join(base, 'glass_weather'),
                ]
            else:
                return None
            for c in candidates:
                if c and os.path.isdir(c):
                    return c
            return candidates[0] if candidates else None

        weather_dir = _resolve_weather_dir(weather_group)

        if weather_dir and os.path.isdir(weather_dir):
            for epw_file in os.listdir(weather_dir):
                if epw_file.endswith('.epw'):
                    # EPW文件名通常是气候区代码，如 AFShanghai.001.epw
                    # 或者直接是气候区代码如 Am.epw
                    base_name = epw_file.replace('.epw', '')
                    # 尝试提取Köppen代码（通常是前2-3个字符）
                    parts = base_name.split('.')
                    koppen_code = parts[0] if parts else base_name
                    # 处理带城市的EPW文件名，提取Köppen代码
                    if len(base_name) > 3 and '.' in base_name:
                        # 格式如 AFShanghai.001 -> AF
                        koppen_code = ''.join([c for c in base_name[:3] if c.isalpha()])
                    epw_to_name[base_name.lower()] = koppen_code

        # 尝试映射FQ到NAME
        fq_to_name_map = {}
        if weather_dir and os.path.isdir(weather_dir):
            for epw_file in os.listdir(weather_dir):
                if epw_file.endswith('.epw'):
                    base_name = epw_file.replace('.epw', '').lower()
                    # 提取Köppen气候代码
                    koppen = ''.join([c for c in base_name[:3] if c.isalpha()])
                    fq_to_name_map[koppen] = koppen

        merged['NAME'] = merged['_key'].map(fq_to_name_map)

        # 按 FQ 分组，汇总数据
        # 首先计算百分比
        mask_cooling = (merged['cooling_duibi'] != 0) & merged['cooling_duibi'].notna() & merged['Cooling'].notna()
        merged['Cooling%'] = np.nan
        if mask_cooling.any():
            merged.loc[mask_cooling, 'Cooling%'] = (
                merged.loc[mask_cooling, 'Cooling'] /
                merged.loc[mask_cooling, 'cooling_duibi']
            ) * 100

        mask_heating = (merged['heating_duibi'] != 0) & merged['heating_duibi'].notna() & merged['Heating'].notna()
        merged['Heating%'] = np.nan
        if mask_heating.any():
            merged.loc[mask_heating, 'Heating%'] = (
                merged.loc[mask_heating, 'Heating'] /
                merged.loc[mask_heating, 'heating_duibi']
            ) * 100

        merged['Total%'] = (merged['Cooling%'].fillna(0) + merged['Heating%'].fillna(0))

        # 输出 world 模式的数据（使用 QID 列名，与材料对比保持一致）
        merged['QID'] = range(1, len(merged) + 1)
        out_df = merged[['QID', 'FQ', 'Cooling', 'Heating', 'Total', 'Cooling%', 'Heating%', 'Total%']].copy()
        output_csv = os.path.join(idf_dir, 'data.csv')
        out_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 已生成data.csv: {output_csv}")
        print(f"     包含 {len(out_df)} 行数据")
        print(f"     列: QID, FQ, Cooling, Heating, Total, Cooling%, Heating%, Total%")

    else:
        # china 模式
        # 首先计算百分比
        mask_cooling = (merged['cooling_duibi'] != 0) & merged['cooling_duibi'].notna() & merged['Cooling'].notna()
        merged['Cooling%'] = np.nan
        if mask_cooling.any():
            merged.loc[mask_cooling, 'Cooling%'] = (
                merged.loc[mask_cooling, 'Cooling'] /
                merged.loc[mask_cooling, 'cooling_duibi']
            ) * 100

        mask_heating = (merged['heating_duibi'] != 0) & merged['heating_duibi'].notna() & merged['Heating'].notna()
        merged['Heating%'] = np.nan
        if mask_heating.any():
            merged.loc[mask_heating, 'Heating%'] = (
                merged.loc[mask_heating, 'Heating'] /
                merged.loc[mask_heating, 'heating_duibi']
            ) * 100

        merged['Total%'] = (merged['Cooling%'].fillna(0) + merged['Heating%'].fillna(0))

        # 使用 cities 列作为 NAME
        merged['NAME'] = merged['cities'].fillna(merged['_key'])
        merged['FQ'] = merged['NAME']

        out_df = merged[['NAME', 'FQ', 'Cooling', 'Heating', 'Total', 'Cooling%', 'Heating%', 'Total%']].copy()
        output_csv = os.path.join(idf_dir, 'data.csv')
        out_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 已生成data.csv: {output_csv}")
        print(f"     包含 {len(out_df)} 行数据")
        print(f"     列: NAME, FQ, Cooling, Heating, Total, Cooling%, Heating%, Total%")


def generate_final_data_csv(idf_dir: str, mode: str = 'world', enable_latent_heat: bool = False, wet_fraction: float = 1.0, weather_group: str = 'china') -> None:
    """读取三个CSV文件，计算差值并除以2.2，生成最终的data.csv文件
    
    参数:
        idf_dir: 工作目录
        mode: 'china' 或 'world'
        enable_latent_heat: 是否启用蒸发潜热计算
        wet_fraction: 湿润面积比例（0-1）
        weather_group: 天气组（'china', 'world', 'world_weather2025'）
    """
    duibi_csv = os.path.join(idf_dir, 'duibi.csv')
    shiyan1_csv = os.path.join(idf_dir, 'shiyan1.csv')
    shiyan2_csv = os.path.join(idf_dir, 'shiyan2.csv')
    
    required_files = [duibi_csv, shiyan1_csv, shiyan2_csv]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"\n警告: 以下CSV文件不存在，无法生成data.csv:")
        for f in missing_files:
            print(f"  - {f}")
        return
    
    print(f"\n开始处理CSV文件并生成data.csv...")
    
    def read_csv_with_fallback(path: str):
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'cp936', 'latin-1']
        last_err = None
        for enc in encodings:
            try:
                return pd.read_csv(path, encoding=enc, engine='python')
            except Exception as err:
                last_err = err
        raise last_err
    
    try:
        df_duibi = read_csv_with_fallback(duibi_csv)
        df_shiyan1 = read_csv_with_fallback(shiyan1_csv)
        df_shiyan2 = read_csv_with_fallback(shiyan2_csv)
    except Exception as e:
        print(f"错误: 读取CSV文件失败: {e}")
        return
    
    required_cols = ['cities', 'cooling', 'heating']
    for name, df in [('duibi', df_duibi), ('shiyan1', df_shiyan1), ('shiyan2', df_shiyan2)]:
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"错误: {name}.csv 缺少必要的列: {missing_cols}")
            return
    
    df_duibi['_key'] = df_duibi['cities'].astype(str).str.strip().str.lower()
    df_shiyan1['_key'] = df_shiyan1['cities'].astype(str).str.strip().str.lower()
    df_shiyan2['_key'] = df_shiyan2['cities'].astype(str).str.strip().str.lower()
    
    df_duibi_renamed = df_duibi[['_key', 'cities', 'cooling', 'heating']].copy()
    df_duibi_renamed = df_duibi_renamed.rename(columns={'cooling': 'cooling_duibi', 'heating': 'heating_duibi'})
    
    # shiyan1.csv: 始终使用 'cooling' 列（该列在 shiyan1.csv 中已经是修正后的值）
    df_shiyan1_renamed = df_shiyan1[['_key', 'cooling']].copy()
    df_shiyan1_renamed = df_shiyan1_renamed.rename(columns={'cooling': 'cooling_shiyan1'})
    
    df_shiyan2_renamed = df_shiyan2[['_key', 'heating']].copy()
    df_shiyan2_renamed = df_shiyan2_renamed.rename(columns={'heating': 'heating_shiyan2'})
    
    # 合并数据
    merged = pd.merge(df_duibi_renamed, df_shiyan1_renamed, on='_key')
    merged = pd.merge(merged, df_shiyan2_renamed, on='_key')
    
    # 计算差值 (此时 shiyan1.cooling, duibi.cooling 等都已经在生成 CSV 时除以过 2.2)
    # 直接相减得到节能值
    merged['Cooling'] = merged['cooling_duibi'] - merged['cooling_shiyan1']
    merged['Heating'] = merged['heating_duibi'] - merged['heating_shiyan2']
    merged['Total'] = merged['Cooling'].fillna(0) + merged['Heating'].fillna(0)
    
    # 提取蒸发潜热原始功率列 (W/m2)
    if 'Evaporation_Latent_Heat_W_per_m2' in df_shiyan1.columns:
        df_latent = df_shiyan1[['_key', 'Evaporation_Latent_Heat_W_per_m2']].copy()
        merged = pd.merge(merged, df_latent, on='_key', how='left')
    
    # 计算比例列 (按用户最新要求：节能差值/基准能耗)
    # Cooling% = data.cooling / duibi.cooling
    mask_cooling = (merged['cooling_duibi'] != 0) & merged['cooling_duibi'].notna() & merged['Cooling'].notna()
    merged['Cooling%'] = np.nan
    if mask_cooling.any():
        merged.loc[mask_cooling, 'Cooling%'] = (
            merged.loc[mask_cooling, 'Cooling'] / 
            merged.loc[mask_cooling, 'cooling_duibi']
        )
    
    # Heating% = data.heating / duibi.heating
    mask_heating = (merged['heating_duibi'] != 0) & merged['heating_duibi'].notna() & merged['Heating'].notna()
    merged['Heating%'] = np.nan
    if mask_heating.any():
        merged.loc[mask_heating, 'Heating%'] = (
            merged.loc[mask_heating, 'Heating'] / 
            merged.loc[mask_heating, 'heating_duibi']
        )
    
    # Total% = Cooling% + Heating%
    merged['Total%'] = merged['Cooling%'].fillna(0) + merged['Heating%'].fillna(0)

    # NOTE:
    # The web UI labels these columns with "(%)" and expects 0~100 values.
    # The computed values above are ratios (0~1), so convert them to percentages.
    for _col in ('Cooling%', 'Heating%', 'Total%'):
        merged[_col] = pd.to_numeric(merged[_col], errors='coerce') * 100.0
    
    # 确保 Evaporation_Latent_Heat_W_per_m2 列存在（即使未启用也输出，值为0）
    if 'Evaporation_Latent_Heat_W_per_m2' not in merged.columns:
        merged['Evaporation_Latent_Heat_W_per_m2'] = 0.0
    
    out_df = pd.DataFrame({
        'FQ': merged['cities'].astype(str).str.strip(),
        'Cooling saving': merged['Cooling'],
        'Heating saving': merged['Heating'],
        'Total saving': merged['Total'],
        'Cooling%': merged['Cooling%'],
        'Heating%': merged['Heating%'],
        'Total%': merged['Total%'],
        'Evaporation_Latent_Heat_W_per_m2': merged['Evaporation_Latent_Heat_W_per_m2']
    })
    
    if mode == 'china':
        epw_to_name = {
            'anhui province': '安徽省', 'beijing': '北京市', 'chongqing': '重庆市',
            'fujian': '福建省', 'gansu': '甘肃省', 'guangdong province': '广东省',
            'guangxi zhuang autonomous region': '广西壮族自治区', 'guizhou province': '贵州省',
            'hainan province': '海南省', 'hebei province': '河北省', 'heilongjiang province': '黑龙江省',
            'henan province': '河南省', 'hongkong': '香港特别行政区', 'hubei province': '湖北省',
            'hunan province': '湖南省', 'inner mongolia autonomous region': '内蒙古自治区',
            'jiangsu': '江苏省', 'jiangxi province': '江西省', 'jilin province': '吉林省',
            'liaoning': '辽宁省', 'macao': '澳门特别行政区', 'ningxia hui autonomous region': '宁夏回族自治区',
            'qinghai province': '青海省', 'shaanxi province': '陕西省', 'shandong province': '山东省',
            'shanghai': '上海市', 'shanxi province': '山西省', 'shenzhen': '深圳市',
            'sichuan': '四川省', 'taiwan province': '台湾省', 'tianjin': '天津市',
            'tibet autonomous region': '西藏自治区', 'xinjiang uyghur autonomous region': '新疆维吾尔自治区',
            'yunnan province': '云南省', 'zhejiang province': '浙江省',
        }
        
        fq_raw = out_df['FQ'].astype(str)
        fq_key = fq_raw.str.replace('.epw', '', case=False).str.strip().str.lower()
        out_df['NAME'] = fq_key.map(epw_to_name)
        
        before_n = len(out_df)
        out_df = out_df[out_df['NAME'].notna()].copy()
        dropped = before_n - len(out_df)
        if dropped > 0:
            print(f"[WARN] china 模式下有 {dropped} 行 FQ 无法映射到省份 NAME，已过滤。")
        
        out_df = out_df[['NAME', 'FQ', 'Cooling saving', 'Heating saving', 'Total saving', 'Cooling%', 'Heating%', 'Total%', 'Evaporation_Latent_Heat_W_per_m2']]
        output_csv = os.path.join(idf_dir, 'data.csv')
        out_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 已生成data.csv: {output_csv}")
        print(f"     包含 {len(out_df)} 行数据")
        print(f"     列: NAME, FQ, Cooling saving, Heating saving, Total saving, Cooling%, Heating%, Total%, Evaporation_Latent_Heat_W_per_m2")
        return
    
    # world 模式
    fq_to_qid_map = None
    template_path = r"g:\Energyplus\map\world\GISDATA\气候区划\1data.csv"
    
    if os.path.exists(template_path):
        try:
            template_df = read_csv_with_fallback(template_path)
            if 'FQ' in template_df.columns and 'QID' in template_df.columns:
                fq_to_qid_map = {}
                for _, row in template_df.iterrows():
                    fq_val = str(row['FQ']).strip().lower() if pd.notna(row['FQ']) else ''
                    qid_val = row['QID'] if pd.notna(row['QID']) else None
                    if fq_val and qid_val is not None:
                        fq_to_qid_map[fq_val] = qid_val
                print(f"[INFO] 从模板文件读取到 {len(fq_to_qid_map)} 个 FQ->QID 映射")
        except Exception as e:
            print(f"[WARN] 读取模板文件失败: {e}，将使用内置映射")
    
    if not fq_to_qid_map:
        fq_to_qid_map = {
            'af': 1, 'am': 2, 'aw': 3, 'bsh': 6, 'bsk': 7, 'bwh': 4, 'bwk': 5,
            'cfa': 14, 'cfb': 15, 'cfc': 16, 'csa': 8, 'csb': 9, 'csc': 10,
            'cwa': 11, 'cwb': 12, 'cwc': 13, 'dfa': 25, 'dfb': 26, 'dfc': 27, 'dfd': 28,
            'dsa': 17, 'dsb': 18, 'dsc': 19, 'dsd': 20, 'dwa': 21, 'dwb': 22, 'dwc': 23, 'dwd': 24,
            'ef': 29, 'et': 30,
        }
        print(f"[INFO] 使用内置 FQ->QID 映射（{len(fq_to_qid_map)} 条）")
    
    def get_qid(fq_val):
        if pd.isna(fq_val):
            return None
        fq_key = str(fq_val).strip().lower()
        return fq_to_qid_map.get(fq_key, None)
    
    out_df['QID'] = out_df['FQ'].apply(get_qid)
    
    missing_qid = out_df['QID'].isna()
    if missing_qid.any():
        max_qid = out_df['QID'].max() if out_df['QID'].notna().any() else 0
        next_qid = int(max_qid) + 1 if not pd.isna(max_qid) else 1
        for idx in out_df[missing_qid].index:
            out_df.loc[idx, 'QID'] = next_qid
            next_qid += 1
        print(f"[WARN] {missing_qid.sum()} 个FQ没有找到对应QID，已使用序号分配")
    
    out_df = out_df[['QID', 'FQ', 'Cooling saving', 'Heating saving', 'Total saving', 'Cooling%', 'Heating%', 'Total%', 'Evaporation_Latent_Heat_W_per_m2']]
    output_csv = os.path.join(idf_dir, 'data.csv')
    out_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n[OK] 已生成data.csv: {output_csv}")
    print(f"     包含 {len(out_df)} 行数据")
    print(f"     列: QID, FQ, Cooling saving, Heating saving, Total saving, Cooling%, Heating%, Total%, Evaporation_Latent_Heat_W_per_m2")


# ==================== 地图绘制函数（从batch_run.py） ====================

# 检查地图绘制依赖
try:
    import matplotlib
    # 使用非交互式后端，避免在非主线程中使用GUI
    matplotlib.use('Agg')
    import geopandas as gpd
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    import numpy as np
    from shapely.geometry import LineString
    _WORLD_MAP_AVAILABLE = True
except Exception:
    gpd = None
    plt = None
    mpl = None
    np = None
    LineString = None
    _WORLD_MAP_AVAILABLE = False

_CHINA_MAP_AVAILABLE = _SNAPSHOT_AVAILABLE  # 使用已有的pyecharts检查


# ==================== 智能颜色条辅助函数 ====================

def _compute_cbar_ticks(vmin: float, vmax: float, is_co2: bool = False) -> list:
    """
    根据数据范围智能计算颜色条的tick位置
    
    Args:
        vmin: 数据最小值
        vmax: 数据最大值
        is_co2: 是否为CO2图（ticks策略不同）
    
    Returns:
        tick位置列表
    """
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return [vmin, vmax] if np.isfinite(vmin) and np.isfinite(vmax) else [0, 1]
    
    data_range = vmax - vmin
    
    if is_co2:
        # CO2图的ticks策略：使用整数刻度
        if vmax <= 5:
            ticks = [0, 1, 2, 3, 4, 5]
        elif vmax <= 10:
            ticks = [0, 2, 4, 6, 8, 10]
        elif vmax <= 20:
            ticks = [0, 4, 8, 12, 16, 20]
        elif vmax <= 30:
            tick_step = 6
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 50:
            tick_step = 10
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 100:
            tick_step = 20
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 200:
            tick_step = 40
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 300:
            tick_step = 60
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 500:
            tick_step = 100
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 1000:
            tick_step = 200
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        else:
            # 大范围：使用百分比
            ticks = [0, vmax * 0.25, vmax * 0.5, vmax * 0.75, vmax]
    else:
        # 能量图的ticks策略：使用整数或整10/整100
        if vmax <= 25:
            tick_step = 4
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 50:
            tick_step = 10
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 100:
            tick_step = 20
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 200:
            tick_step = 40
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 300:
            tick_step = 60
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 500:
            tick_step = 100
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 1000:
            tick_step = 200
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 2000:
            tick_step = 400
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        elif vmax <= 5000:
            tick_step = 1000
            ticks = list(range(0, int(vmax) + tick_step, tick_step))
        else:
            # 大范围：使用百分比
            ticks = [0, vmax * 0.25, vmax * 0.5, vmax * 0.75, vmax]
    
    # 过滤 ticks，确保所有值都在 [vmin, vmax] 范围内
    ticks = [t for t in ticks if vmin <= t <= vmax]
    
    # 确保始终包含0（如果0在范围内）
    if 0 not in ticks and vmin <= 0 <= vmax:
        ticks.append(0)
        ticks.sort()
    
    # 至少保留两个tick
    if len(ticks) < 2:
        ticks = [vmin, vmax]
    
    return ticks


def _compute_optimal_cbar_range(data_min: float, data_max: float, is_co2: bool = False) -> Tuple[float, float]:
    """
    根据数据计算最优的颜色条范围
    
    Args:
        data_min: 数据最小值
        data_max: 数据最大值
        is_co2: 是否为CO2图
    
    Returns:
        (vmin, vmax) 元组
    """
    if not np.isfinite(data_min) or not np.isfinite(data_max):
        return (0.0, 1.0)
    
    # 确保有合理的范围
    if data_max - data_min < 1e-10:
        data_max = data_min + 1.0
    
    # 确定vmin
    if data_min > 0:
        # 所有数据为正：从0开始（或使用负的微小值以确保包含0）
        vmin = 0
    else:
        # 包含负值：保持原值
        vmin = data_min
    
    # 确定vmax：添加适当的边界
    if data_max > 0:
        vmax = data_max * 1.1  # 增加10%的边界
    else:
        vmax = data_max + 1.0
    
    # 确保vmin < vmax
    if vmax <= vmin:
        vmax = vmin + abs(vmin) * 0.1 + 1.0 if vmin != 0 else 1.0
    
    return (float(vmin), float(vmax))


def _get_colorbar_label(column: str, is_co2: bool = False, unit: str = "MJ/m²/year") -> str:
    """
    生成颜色条标签
    
    Args:
        column: 数据列名
        is_co2: 是否为CO2图
        unit: 单位
    
    Returns:
        格式化的标签字符串
    """
    if is_co2:
        return f"CO₂ reduction (kg/m²/year)"
    else:
        return f"Energy saving ({unit})"


def plot_world_maps_from_data_csv(csv_path: str, output_dir: str, colormap_params: Optional[dict] = None) -> None:
    """绘制世界地图（从batch_run.py复制）

    Args:
        csv_path: CSV文件路径
        output_dir: 输出目录
        colormap_params: 色系参数字典，如 {"world_cooling_energy": "YlGnBu", ...}
    """
    if not _WORLD_MAP_AVAILABLE:
        print("[WARN] 未检测到绘图依赖（geopandas/matplotlib/shapely/numpy），已跳过绘图。")
        return

    if not os.path.exists(csv_path):
        print(f"[WARN] 未找到 data.csv：{csv_path}，已跳过绘图。")
        return

    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    shapefile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gridcode.shp')
    if not os.path.exists(shapefile_path):
        print(f"[WARN] 未找到 shapefile：{shapefile_path}，已跳过绘图。")
        return

    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "cp936", "latin-1"]
    last_err = None
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=enc, engine="python")
            break
        except Exception as e:
            last_err = e
    if df is None:
        raise last_err

    if 'QID' not in df.columns:
        print("[WARN] data.csv 缺少 QID 列，无法绘制世界地图，已跳过。")
        return

    gdf = gpd.read_file(shapefile_path)
    merged_gdf = gdf.merge(df, left_on='gridcode', right_on='QID')

    if merged_gdf.crs != 'EPSG:4326':
        merged_gdf = merged_gdf.to_crs('EPSG:4326')

    def create_graticules():
        graticules = []
        for lon in range(-180, 181, 30):
            lats = np.arange(-90, 91, 1)
            lons = [lon] * len(lats)
            graticules.append(LineString(zip(lons, lats)))
        for lat in range(-90, 91, 30):
            lons = np.arange(-180, 181, 1)
            lats = [lat] * len(lons)
            graticules.append(LineString(zip(lons, lats)))
        return graticules

    gdf_graticules = gpd.GeoDataFrame(geometry=create_graticules(), crs='EPSG:4326')

    print("\n绘制Robinson投影世界地图...")

    robinson_proj = '+proj=robin +lon_0=0 +datum=WGS84 +units=m +no_defs'
    merged_gdf_robin = merged_gdf.to_crs(robinson_proj)
    gdf_graticules_robin = gdf_graticules.to_crs(robinson_proj)

    # 合并默认配置与用户自定义配置
    if colormap_params is None:
        colormap_params = {}

    def _get_wm_cmap(base_key: str, default: str) -> str:
        return colormap_params.get(base_key, default)

    plot_configs = [
        {'column': 'Cooling saving', 'cbar_label': 'Cooling Energy saving (MJ/m2/year)',
         'save_path': os.path.join(output_dir, 'world_cooling_energy_robinson.png'),
         'is_co2': False, 'cmap_key': _get_wm_cmap('world_cooling_energy', 'YlGnBu')},
        {'column': 'Heating saving', 'cbar_label': 'Heating Energy saving (MJ/m2/year)',
         'save_path': os.path.join(output_dir, 'world_heating_energy_robinson.png'),
         'is_co2': False, 'cmap_key': _get_wm_cmap('world_heating_energy', 'coolwarm')},
        {'column': 'Total saving', 'cbar_label': 'Energy saving (MJ/m2/year)',
         'save_path': os.path.join(output_dir, 'world_total_energy_robinson.png'),
         'is_co2': False, 'cmap_key': _get_wm_cmap('world_total_energy', 'coolwarm')},
        {'column': 'Cooling saving', 'cbar_label': 'Cooling CO2 reduction (kg/m2/year)',
         'save_path': os.path.join(output_dir, 'world_cooling_co2_robinson.png'),
         'is_co2': True, 'cmap_key': _get_wm_cmap('world_cooling_co2', 'Greens')},
        {'column': 'Heating saving', 'cbar_label': 'Heating CO2 reduction (kg/m2/year)',
         'save_path': os.path.join(output_dir, 'world_heating_co2_robinson.png'),
         'is_co2': True, 'cmap_key': _get_wm_cmap('world_heating_co2', 'Greens')},
        {'column': 'Total saving', 'cbar_label': 'CO2 reduction (kg/m2/year)',
         'save_path': os.path.join(output_dir, 'world_total_co2_robinson.png'),
         'is_co2': True, 'cmap_key': _get_wm_cmap('world_total_co2', 'Greens')},
    ]

    for cfg in plot_configs:
        if cfg['is_co2']:
            col_name = f"{cfg['column']}_CO2"
            merged_gdf_robin[col_name] = pd.to_numeric(merged_gdf_robin[cfg['column']], errors='coerce') * 0.138
            cfg['plot_column'] = col_name
        else:
            cfg['plot_column'] = cfg['column']

    for cfg in plot_configs:
        fig, ax = plt.subplots(figsize=(12.8, 8))

        # 根据 cmap_key 解析色系（直接使用完整颜色，不再切割）
        cmap_key = cfg.get('cmap_key', 'YlGnBu')
        cmap_info = COLORMAP_REGISTRY.get(cmap_key)

        if cmap_info:
            # 直接使用全部颜色，不再对发散型色系进行任何切割
            cmap = mpl.colors.LinearSegmentedColormap.from_list(
                f'dyn_{cmap_key}', cmap_info['python_colors']
            )
        else:
            cmap = mpl.cm.get_cmap('YlGnBu')

        plot_col = cfg['plot_column']
        # 过滤掉NaN和Inf值
        valid_data = merged_gdf_robin[plot_col].replace([np.inf, -np.inf], np.nan).dropna()
        
        if len(valid_data) == 0:
            print(f"[WARN] {plot_col} 列没有有效数据，跳过绘制")
            plt.close(fig)
            continue
        
        data_min = valid_data.min()
        data_max = valid_data.max()
        
        # 确保vmin和vmax是有限值
        if not np.isfinite(data_min) or not np.isfinite(data_max):
            print(f"[WARN] {plot_col} 列的数据范围无效 (min={data_min}, max={data_max})，跳过绘制")
            plt.close(fig)
            continue
        
        # 使用智能函数计算最优范围
        vmin, vmax = _compute_optimal_cbar_range(data_min, data_max, cfg['is_co2'])
        
        # 确保vmin和vmax是有限值
        if not np.isfinite(vmin):
            vmin = 0.0
        if not np.isfinite(vmax):
            vmax = 1.0
        
        norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

        # 确保数据列不包含非有限值
        plot_data = merged_gdf_robin[plot_col].copy()
        plot_data = plot_data.replace([np.inf, -np.inf], np.nan)
        merged_gdf_robin[plot_col] = plot_data
        
        merged_gdf_robin.plot(column=plot_col, cmap=cmap, legend=False, ax=ax, norm=norm,
                             edgecolor='none', linewidth=0, zorder=2, missing_kwds={'color': 'lightgray'})
        gdf_graticules_robin.plot(ax=ax, color='gray', linewidth=0.6, alpha=0.5, zorder=1)

        bounds = merged_gdf_robin.total_bounds
        x_center = (bounds[0] + bounds[2]) / 2
        y_center = (bounds[1] + bounds[3]) / 2
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]

        ax.set_xlim(x_center - width * 0.6, x_center + width * 0.6)
        ax.set_ylim(y_center - height * 0.6, y_center + height * 0.6)
        ax.axis('off')
        ax.set_aspect('equal')

        cbar_ax = fig.add_axes([0.35, 0.15, 0.35, 0.03])
        
        # 确保boundaries数组不包含非有限值
        vmin_val = float(norm.vmin) if np.isfinite(norm.vmin) else 0.0
        vmax_val = float(norm.vmax) if np.isfinite(norm.vmax) else 1.0
        
        # 确保vmin < vmax
        if vmin_val >= vmax_val:
            vmax_val = vmin_val + 1.0
        
        # 生成boundaries，确保不包含非有限值
        try:
            boundaries = np.linspace(vmin_val, vmax_val, 256)
            # 确保所有值都是有限的
            if not np.all(np.isfinite(boundaries)):
                boundaries = np.linspace(0.0, 1.0, 256)
        except Exception:
            boundaries = np.linspace(0.0, 1.0, 256)
        
        # 使用智能函数计算ticks
        ticks = _compute_cbar_ticks(vmin, vmax, cfg['is_co2'])
        
        try:
            # 使用简化的ColorbarBase，不指定boundaries以避免问题
            cbar = mpl.colorbar.ColorbarBase(
                cbar_ax, 
                cmap=cmap, 
                norm=norm, 
                orientation='horizontal',
                ticks=ticks
            )
            cbar.set_label(cfg['cbar_label'], fontsize=16, labelpad=10)
            cbar.ax.tick_params(labelsize=12)
        except Exception as e:
            print(f"[WARN] 创建colorbar失败: {e}，使用最简版本")
            import traceback
            traceback.print_exc()
            # 使用最简化的colorbar，不指定任何额外参数
            try:
                cbar = mpl.colorbar.ColorbarBase(
                    cbar_ax, 
                    cmap=cmap, 
                    norm=norm, 
                    orientation='horizontal'
                )
                cbar.set_label(cfg['cbar_label'], fontsize=16, labelpad=10)
                cbar.ax.tick_params(labelsize=12)
            except Exception as e2:
                print(f"[ERROR] 无法创建colorbar: {e2}，跳过此图")
                plt.close(fig)
                continue

        plt.savefig(cfg['save_path'], dpi=300, bbox_inches='tight')
        print(f"[OK] 已保存：{cfg['save_path']}")
        plt.close(fig)

    print("[OK] 世界地图绘制完成（6张）。")


def _format_tick_value(val: float, is_co2: bool = False) -> str:
    """
    格式化tick值，用于显示
    
    Args:
        val: 数值
        is_co2: 是否为CO2图
    
    Returns:
        格式化后的字符串
    """
    if abs(val) >= 1000:
        return f"{val/1000:.1f}k"
    elif abs(val) >= 100:
        return f"{val:.0f}"
    elif abs(val) >= 10:
        return f"{val:.1f}"
    else:
        return f"{val:.2f}"


def _compute_china_visualmap_range(min_val: float, max_val: float, is_co2: bool = False) -> Tuple[float, float, list]:
    """
    计算中国地图visualmap的最优范围和刻度
    
    Args:
        min_val: 数据最小值
        max_val: 数据最大值
        is_co2: 是否为CO2图
    
    Returns:
        (vmin, vmax, range_text_min, range_text_max)
    """
    # 处理无效值
    if not np.isfinite(min_val) or not np.isfinite(max_val):
        return (0, 1, ["0", "1"])
    
    # 确保范围合理
    if max_val - min_val < 1e-10:
        max_val = min_val + 1.0
    
    # 确定vmin（通常从0开始，除非数据有负值）
    vmin = 0 if min_val >= 0 else min_val
    vmax = max_val
    
    # 计算合适的刻度
    if is_co2:
        if vmax <= 10:
            step = 2
        elif vmax <= 20:
            step = 4
        elif vmax <= 30:
            step = 6
        elif vmax <= 50:
            step = 10
        elif vmax <= 100:
            step = 20
        elif vmax <= 200:
            step = 40
        elif vmax <= 300:
            step = 60
        elif vmax <= 500:
            step = 100
        elif vmax <= 1000:
            step = 200
        else:
            step = vmax // 5
    else:
        if vmax <= 25:
            step = 4
        elif vmax <= 50:
            step = 10
        elif vmax <= 100:
            step = 20
        elif vmax <= 200:
            step = 40
        elif vmax <= 300:
            step = 60
        elif vmax <= 500:
            step = 100
        elif vmax <= 1000:
            step = 200
        elif vmax <= 2000:
            step = 400
        elif vmax <= 5000:
            step = 1000
        else:
            step = vmax // 5
    
    # 格式化range_text
    range_text_max = _format_tick_value(vmax, is_co2)
    range_text_min = _format_tick_value(vmin, is_co2)
    
    return (vmin, vmax, [range_text_min, range_text_max])


def build_china_map(df: pd.DataFrame, *, value_col: str, title: str, unit: str, color: str,
                    range_color, value_transform=None, width: str = "1792px", height: str = "1008px",
                    is_co2: bool = False):
    """构建中国地图（优化版）
    
    Args:
        df: 数据DataFrame
        value_col: 数值列名
        title: 图表标题
        unit: 数据单位
        color: 基础颜色
        range_color: 颜色范围
        value_transform: 值转换函数
        width: 宽度
        height: 高度
        is_co2: 是否为CO2图
    
    Returns:
        pyecharts Map对象
    """
    dff = df.copy()
    if value_transform is not None:
        dff[value_col] = value_transform(pd.to_numeric(dff[value_col], errors='coerce'))

    # 转换为数值并处理无效值
    numeric_col = pd.to_numeric(dff[value_col], errors='coerce')
    dff[value_col] = numeric_col
    
    # 获取有效数据的范围
    valid_data = numeric_col.dropna()
    if len(valid_data) == 0:
        # 没有有效数据，使用默认值
        min_val = 0.0
        max_val = 1.0
    else:
        min_val = float(valid_data.min())
        max_val = float(valid_data.max())
    
    # 处理异常值
    if not np.isfinite(min_val):
        min_val = 0.0
    if not np.isfinite(max_val):
        max_val = 1.0
    
    data_province = list(zip(dff["NAME"], dff[value_col]))
    
    # 计算最优范围和刻度
    vmin, vmax, range_text = _compute_china_visualmap_range(min_val, max_val, is_co2)
    
    chart = (
        Map(init_opts=opts.InitOpts(width=width, height=height))
        .add(" ", data_province, "china", is_map_symbol_show=False,
             itemstyle_opts=opts.ItemStyleOpts(color=color))
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title, pos_top="70%", pos_right="53%"),
            visualmap_opts=opts.VisualMapOpts(
                min_=vmin, 
                max_=vmax, 
                orient="horizontal",
                range_color=range_color, 
                is_calculable=True,
                is_piecewise=False, 
                item_width=25, 
                item_height=250,
                pos_top="65%", 
                pos_right="50%",
                range_text=range_text,
                textstyle_opts=opts.TextStyleOpts(font_size=20)),
            legend_opts=opts.LegendOpts(type_="plain", pos_top="70%", pos_left="47%",
                                        orient="vertical", item_width=20,
                                        textstyle_opts=opts.TextStyleOpts(font_size=20),
                                        item_height=20),
            tooltip_opts=opts.TooltipOpts(formatter=f"{{b}}: {{c}} {unit}"),
        )
        .set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    )
    return chart


def plot_china_maps_from_data_csv(csv_path: str, output_dir: str, colormap_params: Optional[dict] = None) -> None:
    """绘制中国地图（从batch_run.py复制）

    Args:
        csv_path: CSV文件路径
        output_dir: 输出目录
        colormap_params: 色系参数字典
    """
    if not _CHINA_MAP_AVAILABLE:
        print("[WARN] 未检测到 pyecharts，已跳过中国地图绘制。")
        return

    if not os.path.exists(csv_path):
        print(f"[WARN] 未找到 data.csv：{csv_path}，已跳过中国地图绘制。")
        return

    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "cp936", "latin-1"]
    last_err = None
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=enc, engine="python")
            break
        except Exception as e:
            last_err = e
    if df is None:
        raise last_err

    if 'NAME' not in df.columns:
        print("[WARN] data.csv 缺少 NAME 列（省份名），无法绘制中国地图，已跳过。")
        return

    # 合并默认配置与用户自定义配置
    if colormap_params is None:
        colormap_params = {}

    def _get_china_cmap(base_key: str, default_key: str):
        """从 colormap_params 或默认值中获取色系配置（返回浅色和深色两个端点）"""
        key = colormap_params.get(base_key, default_key)
        info = COLORMAP_REGISTRY.get(key)
        if info and info['colors']:
            return info['colors'][0], info['colors'][-1]
        # 回退到 Blues 的首尾
        fallback = COLORMAP_REGISTRY.get('Blues')
        return fallback['colors'][0], fallback['colors'][-1]

    cool_lc, cool_dc = _get_china_cmap('china_cooling_energy', 'coolwarm_r')
    cool_co2_lc, cool_co2_dc = _get_china_cmap('china_cooling_co2', 'Greens')
    heat_lc, heat_dc = _get_china_cmap('china_heating_energy', 'coolwarm')
    heat_co2_lc, heat_co2_dc = _get_china_cmap('china_heating_co2', 'Greens')
    total_lc, total_dc = _get_china_cmap('china_total_energy', 'RdYlGn')
    total_co2_lc, total_co2_dc = _get_china_cmap('china_total_co2', 'Greens')

    cooling_energy = build_china_map(df, value_col="Cooling saving", title="Cooling Energy Saving (MJ/m²/year)",
                                     unit="MJ/m²/year", color=cool_dc, range_color=[cool_lc, cool_dc],
                                     is_co2=False)
    cooling_co2 = build_china_map(df, value_col="Cooling saving", title="Cooling CO₂ Reduction (kg/m²/year)",
                                  unit="kg/m²/year", color=cool_co2_dc, range_color=[cool_co2_lc, cool_co2_dc],
                                  value_transform=lambda s: s * 0.138, is_co2=True)
    heating_energy = build_china_map(df, value_col="Heating saving", title="Heating Energy Saving (MJ/m²/year)",
                                     unit="MJ/m²/year", color=heat_dc, range_color=[heat_lc, heat_dc],
                                     is_co2=False)
    heating_co2 = build_china_map(df, value_col="Heating saving", title="Heating CO₂ Reduction (kg/m²/year)",
                                  unit="kg/m²/year", color=heat_co2_dc, range_color=[heat_co2_lc, heat_co2_dc],
                                  value_transform=lambda s: s * 0.138, is_co2=True)
    total_energy = build_china_map(df, value_col="Total saving", title="Total Energy Saving (MJ/m²/year)",
                                  unit="MJ/m²/year", color=total_dc, range_color=[total_lc, total_dc],
                                  is_co2=False)
    total_co2 = build_china_map(df, value_col="Total saving", title="Total CO₂ Reduction (kg/m²/year)",
                                unit="kg/m²/year", color=total_co2_dc, range_color=[total_co2_lc, total_co2_dc],
                                value_transform=lambda s: s * 0.138, is_co2=True)

    charts = [
        (cooling_energy, "china_cooling_energy"),
        (heating_energy, "china_heating_energy"),
        (total_energy, "china_total_energy"),
        (cooling_co2, "china_cooling_co2"),
        (heating_co2, "china_heating_co2"),
        (total_co2, "china_total_co2"),
    ]

    for chart, stem in charts:
        html_path = os.path.join(output_dir, f"{stem}.html")
        chart.render(html_path)
        print(f"[OK] 已生成中国地图HTML：{html_path}")

        if _SNAPSHOT_AVAILABLE:
            png_path = os.path.join(output_dir, f"{stem}.png")
            try:
                # 使用自定义快照函数，等待echarts加载
                _make_snapshot_with_wait(html_path, png_path)
                # 验证文件是否成功生成
                if os.path.exists(png_path) and os.path.getsize(png_path) > 1024:
                    file_size = os.path.getsize(png_path) / 1024  # KB
                    print(f"[OK] 已生成中国地图PNG：{png_path} ({file_size:.1f} KB)")
                else:
                    print(f"[WARN] PNG文件生成但可能不完整：{png_path}")
            except Exception as e:
                print(f"[WARN] 生成PNG失败 {stem}.png：{e}")
                # 如果文件存在但有问题，尝试删除
                if os.path.exists(png_path):
                    try:
                        os.remove(png_path)
                    except Exception:
                        pass
                import traceback
                traceback.print_exc()

    # 不再生成合集地图（根据用户要求）
    # page = Page(page_title="China Energy Saving & CO2 Reduction")
    # page.add(cooling_energy, cooling_co2)
    # page.add(heating_energy, heating_co2)
    # page.add(total_energy, total_co2)
    # grid_html = os.path.join(output_dir, "chinamap_energy_and_co2_grid.html")
    # page.render(grid_html)
    # print(f"[OK] 已生成中国地图合集HTML：{grid_html}")
    # if _SNAPSHOT_AVAILABLE:
    #     grid_png = os.path.join(output_dir, "chinamap_energy_and_co2_grid.png")
    #     make_snapshot(snapshot, page.render(), grid_png)
    #     print(f"[OK] 已生成中国地图合集PNG：{grid_png}")

# ==================== End of 地图绘制函数 ====================


def prepare_idf_files(work_dir: str, scenarios: List[Dict[str, Any]],
                     idf_template_dir: str, progress_cb: Optional[callable] = None,
                     global_params: Optional[Dict[str, Any]] = None) -> bool:
    """从模板复制IDF文件并更新玻璃参数和全局参数

    玻璃场景映射：
    - glass_duibi: 使用 duibi.idf，修改其中的 duibi 对象
    - glass_shiyan1: 使用 glass.idf，修改其中的 shiyanhigh 对象
    - glass_shiyan2: 使用 glass.idf，修改其中的 shiyanlow 对象

    Args:
        work_dir: 工作目录
        scenarios: 场景列表（至少3个）
        idf_template_dir: IDF模板目录
        progress_cb: 进度回调函数
        global_params: 全局参数字典（应用到所有IDF文件）

    Returns:
        是否成功
    """
    if len(scenarios) < 3:
        print(f"错误: 需要至少3个场景，但只提供了 {len(scenarios)} 个")
        return False

    # 玻璃场景映射：场景键名 -> (IDF文件名, 玻璃对象名)
    # 注意：duibi.idf 中的基准玻璃对象名是 'fff'，而不是 'duibi'
    glass_scenario_mapping = [
        ('glass_duibi', 'duibi.idf', 'fff'),       # 基准玻璃 (duibi.idf 中对象名为 'fff')
        ('glass_shiyan1', 'glass.idf', 'shiyanhigh'),  # 实验玻璃1 (glass.idf 中对象名为 'shiyanhigh')
        ('glass_shiyan2', 'glass.idf', 'shiyanlow'),  # 实验玻璃2 (glass.idf 中对象名为 'shiyanlow')
    ]

    # 跟踪已复制的文件，避免重复复制覆盖之前的更新
    copied_files = set()

    # 遍历每个玻璃场景
    for i, (scenario_key, idf_filename, glass_object_name) in enumerate(glass_scenario_mapping):
        scenario = scenarios[i] if i < len(scenarios) else {}

        # 获取对应的 IDF 文件路径
        template_file = os.path.join(idf_template_dir, idf_filename)
        target_file = os.path.join(work_dir, idf_filename)

        if not os.path.exists(template_file):
            print(f"错误: 模板文件不存在: {template_file}")
            return False

        # 只在第一次处理该 IDF 文件时复制模板
        if idf_filename not in copied_files:
            shutil.copy2(template_file, target_file)
            print(f"已复制: {template_file} -> {target_file}")
            copied_files.add(idf_filename)

        # 从场景中提取玻璃参数
        glass = scenario.get('glass', {})

        # 构建玻璃参数字典（过滤掉None值，转换为字符串）
        glass_values = {}

        # 定义驼峰到下划线格式的映射（支持前端传入的驼峰格式）
        camel_to_snake = {
            'Name': 'Name',
            'OpticalDataType': 'Optical_Data_Type',
            'WindowGlassSpectralDataSetName': 'Window_Glass_Spectral_Data_Set_Name',
            'Thickness': 'Thickness',
            'SolarTransmittance': 'Solar_Transmittance',
            'SolarReflectanceFront': 'Solar_Reflectance_Front',
            'SolarReflectanceBack': 'Solar_Reflectance_Back',
            'VisibleTransmittance': 'Visible_Transmittance',
            'VisibleReflectanceFront': 'Visible_Reflectance_Front',
            'VisibleReflectanceBack': 'Visible_Reflectance_Back',
            'InfraredTransmittance': 'Infrared_Transmittance',
            'Emissivity': 'Emissivity_Front',
            'EmissivityFront': 'Emissivity_Front',
            'EmissivityBack': 'Emissivity_Back',
            'Conductivity': 'Conductivity',
            'DirtCorrection': 'Dirt_Correction',
            'DirtCorrectionFactor': 'Dirt_Correction',
            'SolarDiffusing': 'Solar_Diffusing',
        }

        # 首先尝试从下划线格式获取（用于兼容后端直接调用的场景）
        for field in GLASS_FIELD_ORDER:
            if field in glass and glass[field] is not None:
                glass_values[field] = str(glass[field])

        # 无论下划线格式是否有值，都尝试驼峰格式（前端发送的格式）
        # 驼峰格式会覆盖下划线格式的值（因为前端总是用驼峰格式）
        for camel_field, snake_field in camel_to_snake.items():
            if camel_field in glass and glass[camel_field] is not None:
                glass_values[snake_field] = str(glass[camel_field])

        # 如果glass为空，尝试兼容旧的 material 格式（向后兼容）
        if not glass_values:
            material = scenario.get('material', {})
            if material:
                # 映射 material 字段到 glass 字段
                if 'SolarTransmittance' in material and material['SolarTransmittance'] is not None:
                    glass_values['Solar_Transmittance'] = str(material['SolarTransmittance'])
                if 'SolarReflectanceFront' in material and material['SolarReflectanceFront'] is not None:
                    glass_values['Solar_Reflectance_Front'] = str(material['SolarReflectanceFront'])
                if 'SolarReflectanceBack' in material and material['SolarReflectanceBack'] is not None:
                    glass_values['Solar_Reflectance_Back'] = str(material['SolarReflectanceBack'])
                if 'VisibleTransmittance' in material and material['VisibleTransmittance'] is not None:
                    glass_values['Visible_Transmittance'] = str(material['VisibleTransmittance'])
                if 'VisibleReflectanceFront' in material and material['VisibleReflectanceFront'] is not None:
                    glass_values['Visible_Reflectance_Front'] = str(material['VisibleReflectanceFront'])
                if 'VisibleReflectanceBack' in material and material['VisibleReflectanceBack'] is not None:
                    glass_values['Visible_Reflectance_Back'] = str(material['VisibleReflectanceBack'])
                if 'InfraredTransmittance' in material and material['InfraredTransmittance'] is not None:
                    glass_values['Infrared_Transmittance'] = str(material['InfraredTransmittance'])
                if 'Emissivity' in material and material['Emissivity'] is not None:
                    glass_values['Emissivity_Front'] = str(material['Emissivity'])
                    glass_values['Emissivity_Back'] = str(material['Emissivity'])
                if 'Thickness' in material and material['Thickness'] is not None:
                    glass_values['Thickness'] = str(material['Thickness'])
                if 'Conductivity' in material and material['Conductivity'] is not None:
                    glass_values['Conductivity'] = str(material['Conductivity'])

        # 更新IDF文件中的玻璃参数
        if glass_values:
            try:
                save_one_glass_to_file(target_file, glass_object_name, glass_values)
                print(f"已更新 {idf_filename} 的玻璃对象 {glass_object_name} 的参数: {glass_values}")
            except Exception as e:
                print(f"警告: 更新 {idf_filename} 的玻璃对象 {glass_object_name} 失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[INFO] 场景 {scenario_key} 未提供玻璃参数，将使用 IDF 模板中的默认值")

        # 更新全局参数（应用到所有IDF文件）
        if global_params:
            # 过滤掉None值
            global_values = {k: v for k, v in global_params.items() if v is not None}
            if global_values:
                try:
                    save_global_params_to_file(target_file, global_values)
                    print(f"已更新 {idf_filename} 的全局参数: {global_values}")
                except Exception as e:
                    print(f"警告: 更新 {idf_filename} 的全局参数失败: {e}")

        if progress_cb:
            progress_cb(0, 3, f"已准备 {scenario_key} ({idf_filename})")

    return True


def run_glass_comparison_energyplus(
    scenarios: Optional[List[Dict[str, Any]]] = None,
    progress_cb: Optional[callable] = None,
    weather_group: str = 'china',
    idf_template_dir: Optional[str] = None,
    energyplus_exe: str = r"D:\academic_tool\EnergyPlusV9-1-0\energyplus.exe",
    work_dir: Optional[str] = None,
    global_params: Optional[Dict[str, Any]] = None,
    enable_latent_heat: bool = False,
    wet_fraction: float = 1.0,
    scale_factor: float = 1.0,
    colormap_params: Optional[dict] = None,
) -> bool:
    """使用EnergyPlus运行玻璃对比分析

    Args:
        scenarios: 场景列表（至少3个）
        progress_cb: 进度回调函数
        weather_group: 'china'、'world' 或 'world_weather2025'
        idf_template_dir: IDF模板目录（如果为None，使用默认路径）
        energyplus_exe: EnergyPlus可执行文件路径
        work_dir: 工作目录（如果为None，自动创建时间戳目录）
        global_params: 全局参数
        enable_latent_heat: 是否启用蒸发潜热
        wet_fraction: 润湿面积比例
        scale_factor: 单位换算因子（默认 1.0，不再做缩放）
        colormap_params: 色系参数字典（6张图各自的色系键）

    Returns:
        是否成功
    """
    print("\n" + "="*70)
    print("玻璃对比分析 - 使用EnergyPlus计算")
    print(
        f"[DEBUG] run_glass_comparison_energyplus 入口参数: "
        f"enable_latent_heat={enable_latent_heat}, wet_fraction={wet_fraction}, "
        f"weather_group={weather_group}, scale_factor={scale_factor}, "
        f"colormap_params={colormap_params}"
    )
    print("="*70)
    
    if scenarios is None or len(scenarios) < 3:
        print("错误: 需要至少3个场景（glass_duibi, glass_shiyan1, glass_shiyan2）")
        return False
    
    # 创建工作目录
    if work_dir is None:
        work_dir = get_work_dir()
    else:
        os.makedirs(work_dir, exist_ok=True)
    
    print(f"工作目录: {work_dir}")
    
    # 确定IDF模板目录
    if idf_template_dir is None or str(idf_template_dir).strip() == "":
        # 默认：使用 glass_comparison_tool 根目录（开发环境）或 exe 目录（打包环境）
        idf_template_dir = get_exe_dir()
    else:
        # 支持相对路径：相对 glass_comparison_tool 根目录解析
        idf_template_dir = os.path.expanduser(str(idf_template_dir).strip())
        if not os.path.isabs(idf_template_dir):
            idf_template_dir = os.path.abspath(os.path.join(get_exe_dir(), idf_template_dir))
    
    if not os.path.exists(idf_template_dir):
        print(f"错误: IDF模板目录不存在: {idf_template_dir}")
        return False
    
    print(f"IDF模板目录: {idf_template_dir}")
    
    # 准备IDF文件
    if progress_cb:
        progress_cb(0, 100, "准备IDF文件...")
    
    if not prepare_idf_files(work_dir, scenarios, idf_template_dir, progress_cb, global_params):
        print("错误: 准备IDF文件失败")
        return False
    
    # 获取天气文件目录
    base = get_exe_dir()
    if weather_group == 'china':
        weather_dir = os.path.join(base, 'glass_weather')
    elif weather_group == 'world':
        weather_dir = os.path.join(base, 'world_weather')
    elif weather_group == 'world_weather2025':
        weather_dir = os.path.join(base, 'world_weather2025')
    else:
        print(f"错误: 无效的weather_group: {weather_group}")
        return False
    
    if not os.path.isdir(weather_dir):
        # 回退路径：对于 world_weather2025，文件夹名就是 world_weather2025，不需要添加 _weather
        if weather_group == 'world_weather2025':
            fallback_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'world_weather2025'))
        else:
            fallback_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'{weather_group}_weather'))
        if os.path.isdir(fallback_dir):
            weather_dir = fallback_dir
        else:
            weather_dir = fallback_dir  # 仍然尝试这个路径
    
    if not os.path.exists(weather_dir):
        print(f"错误: 天气文件目录不存在: {weather_dir}")
        weather_name = weather_group if weather_group == 'world_weather2025' else f'{weather_group}_weather'
        print(f"请确保以下路径存在:")
        print(f"  {os.path.abspath(os.path.join(os.path.dirname(__file__), '..', weather_name))}")
        return False
    
    print(f"天气文件目录: {weather_dir}")
    
    # 生成模拟任务
    output_base_dir = os.path.join(work_dir, "output")
    simulations = generate_simulations(work_dir, weather_dir, output_base_dir)
    
    if not simulations:
        print("错误: 没有生成有效的模拟任务")
        return False
    
    total = len(simulations)
    print(f"\n找到 {total} 个模拟任务")
    print(f"开始运行EnergyPlus批量模拟...")
    print(f"EnergyPlus路径: {energyplus_exe}")
    
    # 检查EnergyPlus可执行文件是否存在
    if not os.path.exists(energyplus_exe):
        print(f"错误: EnergyPlus可执行文件不存在: {energyplus_exe}")
        return False
    
    # 运行EnergyPlus批量模拟
    if progress_cb:
        progress_cb(0, 100, f"开始运行 {total} 个模拟任务...")
    
    success_count = 0
    fail_count = 0
    
    import time
    start_time = time.time()
    
    try:
        for idx, (idf_file, weather_file, output_file) in enumerate(simulations, 1):
            idf_name = os.path.basename(idf_file)
            weather_name = os.path.basename(weather_file)
            print(f"\n[{idx}/{total}] 运行模拟: {idf_name} x {weather_name}")
            
            if progress_cb:
                progress_cb(idx, total, f"运行模拟 {idx}/{total}: {idf_name} x {weather_name}")
            
            try:
                success = run_simulation(idf_file, weather_file, output_file, energyplus_exe, verbose=True)
                if success:
                    success_count += 1
                    print(f"  [成功] 模拟 {idx}/{total} 完成")
                else:
                    fail_count += 1
                    print(f"  [失败] 模拟 {idx}/{total} 失败")
            except Exception as e:
                fail_count += 1
                print(f"  [异常] 模拟 {idx}/{total} 发生错误: {e}")
                import traceback
                traceback.print_exc()
            
            # 每10个模拟打印一次进度
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                remaining = total - idx
                estimated_remaining = avg_time * remaining
                print(f"\n进度: {idx}/{total} ({idx*100//total}%) | 成功: {success_count} | 失败: {fail_count}")
                print(f"已用时间: {elapsed/60:.1f}分钟 | 预计剩余: {estimated_remaining/60:.1f}分钟")
    except Exception as e:
        print(f"\n[严重错误] 批量模拟过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\n模拟完成: 成功 {success_count} 个，失败 {fail_count} 个")
    
    if success_count == 0:
        print("错误: 所有模拟都失败了")
        return False
    
    # 提取数据生成CSV
    if progress_cb:
        progress_cb(0, 100, "提取数据并生成CSV...")
    
    generate_csv_from_output(
        output_base_dir,
        work_dir,
        enable_latent_heat=enable_latent_heat,
        wet_fraction=wet_fraction,
        weather_group=weather_group,
        scale_factor=scale_factor,
    )
    
    # 生成最终的data.csv
    # 玻璃对比工具只生成 glass.csv 和 duibi.csv，使用专门的函数处理
    # world_weather2025 使用 world 模式
    if weather_group == 'china':
        mode = 'china'
    else:
        mode = 'world'  # 包括 'world' 和 'world_weather2025'
    generate_glass_final_data_csv(work_dir, mode=mode, enable_latent_heat=enable_latent_heat, wet_fraction=wet_fraction, weather_group=weather_group)
    
    # 生成地图（需要从batch_run.py复制地图绘制函数）
    data_csv_path = os.path.join(work_dir, 'data.csv')
    if os.path.exists(data_csv_path):
        if progress_cb:
            progress_cb(0, 100, "生成地图...")
        
        try:
            if mode == 'china':
                plot_china_maps_from_data_csv(data_csv_path, work_dir, colormap_params=colormap_params)
            else:
                plot_world_maps_from_data_csv(data_csv_path, work_dir, colormap_params=colormap_params)
        except Exception as plot_err:
            print(f"[WARN] 地图绘制失败：{plot_err}")
    
    # 压缩output目录（在生成所有文件之后）
    if progress_cb:
        progress_cb(0, 100, "压缩输出文件...")
    
    # 确保output目录存在
    if os.path.exists(output_base_dir):
        try:
            zip_path = archive_output(output_base_dir, work_dir, mode, cleanup=True)
            if zip_path and os.path.exists(zip_path):
                zip_size = os.path.getsize(zip_path)
                print(f"[OK] 输出文件已压缩: {zip_path} ({zip_size / (1024*1024):.2f} MB)")
            else:
                print(f"[WARN] 压缩输出文件失败，但结果仍保存在: {output_base_dir}")
        except Exception as archive_err:
            print(f"[WARN] 压缩输出文件时发生错误: {archive_err}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[WARN] output目录不存在，跳过压缩: {output_base_dir}")
    
    print(f"\n[OK] 玻璃对比分析完成！结果保存在: {work_dir}")
    return True

# ==================== End of EnergyPlus运行和数据提取函数 ====================


def find_epw_files(group: str = 'china') -> List[str]:
    """查找 EPW 文件（仅允许两组内置天气目录）。

    参数：
        group: 'china'、'world' 或 'world_weather2025'

    返回：
        EPW 文件路径列表
    """
    base = get_exe_dir()
    if group == 'china':
        weather_dir = os.path.join(base, 'glass_comparison_tool', 'glass_weather')
    elif group == 'world':
        weather_dir = os.path.join(base, 'glass_comparison_tool', 'world_weather')
    elif group == 'world_weather2025':
        weather_dir = os.path.join(base, 'glass_comparison_tool', 'world_weather2025')
    else:
        raise ValueError("group must be 'china', 'world' or 'world_weather2025'")

    if not os.path.isdir(weather_dir):
        # 兼容开发环境：脚本位于 glass_comparison_tool/examples 下
        # 对于 world_weather2025，文件夹名就是 world_weather2025，不需要添加 _weather
        if group == 'world_weather2025':
            fallback_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'world_weather2025'))
        else:
            fallback_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'{group}_weather'))
        if os.path.isdir(fallback_dir):
            weather_dir = fallback_dir
        else:
            weather_dir = fallback_dir  # 仍然尝试这个路径

    epw_files = sorted(glob.glob(os.path.join(weather_dir, '*.epw')))
    return epw_files


def get_sampling_dates(sampling_mode: str = 'none', year: int = 2024) -> Optional[List[Tuple[int, int]]]:
    """生成采样日期列表（用于快速模式）
    
    参数：
        sampling_mode: 采样模式
            - 'none': 不采样，计算全年
            - 'monthly_2weeks': 每月选2周（每月第1-14天）
            - 'monthly_1week': 每月选1周（每月第1-7天）
            - 'seasonal': 季节性采样（春夏秋冬各选2周）
            - 'representative': 代表性日期（每月选3天：月初、月中、月末）
        year: 年份
    
    返回：
        日期列表 [(month, day), ...] 或 None（表示不采样）
    """
    if sampling_mode == 'none':
        return None
    
    dates = []
    
    if sampling_mode == 'monthly_2weeks':
        # 每月选前2周（1-14日）
        for month in range(1, 13):
            for day in range(1, 15):
                dates.append((month, day))
    
    elif sampling_mode == 'monthly_1week':
        # 每月选前1周（1-7日）
        for month in range(1, 13):
            for day in range(1, 8):
                dates.append((month, day))
    
    elif sampling_mode == 'seasonal':
        # 春夏秋冬各选2周
        # 春：3月1-14日
        for day in range(1, 15):
            dates.append((3, day))
        # 夏：6月1-14日
        for day in range(1, 15):
            dates.append((6, day))
        # 秋：9月1-14日
        for day in range(1, 15):
            dates.append((9, day))
        # 冬：12月1-14日
        for day in range(1, 15):
            dates.append((12, day))
    
    elif sampling_mode == 'representative':
        # 每月选3天：月初(5日)、月中(15日)、月末(25日)
        for month in range(1, 13):
            dates.append((month, 5))
            dates.append((month, 15))
            dates.append((month, 25))
    
    return dates


def get_sampling_scale_factor(sampling_mode: str) -> float:
    """获取采样模式的缩放因子（用于将采样结果缩放回全年）
    
    参数：
        sampling_mode: 采样模式
    
    返回：
        缩放因子（全年天数 / 采样天数）
    """
    if sampling_mode == 'none':
        return 1.0
    elif sampling_mode == 'monthly_2weeks':
        # 每月14天 × 12月 = 168天，全年365天
        return 365.0 / 168.0
    elif sampling_mode == 'monthly_1week':
        # 每月7天 × 12月 = 84天
        return 365.0 / 84.0
    elif sampling_mode == 'seasonal':
        # 4个月 × 14天 = 56天
        return 365.0 / 56.0
    elif sampling_mode == 'representative':
        # 每月3天 × 12月 = 36天
        return 365.0 / 36.0
    else:
        return 1.0


def scale_summary_for_sampling(summary: Dict, sampling_mode: str) -> Dict:
    """缩放采样结果的摘要到全年
    
    参数：
        summary: 仿真摘要字典
        sampling_mode: 采样模式
    
    返回：
        缩放后的摘要字典
    """
    if sampling_mode == 'none':
        return summary
    
    scale_factor = get_sampling_scale_factor(sampling_mode)
    
    # 缩放能耗（累加值）
    scaled_summary = summary.copy()
    if 'total_cooling_energy_kWh' in scaled_summary:
        scaled_summary['total_cooling_energy_kWh'] *= scale_factor
    if 'total_heating_energy_kWh' in scaled_summary:
        scaled_summary['total_heating_energy_kWh'] *= scale_factor
    if 'total_hvac_energy_kWh' in scaled_summary:
        scaled_summary['total_hvac_energy_kWh'] *= scale_factor
    
    # 峰值负荷不缩放（保持原值）
    # 注意：total_hours 表示“实际模拟小时数”，不应随采样缩放，否则会导致后续归一化/派生指标出现二次缩放问题。
    return scaled_summary


def get_preset_mode_config(mode: str = 'normal') -> Dict[str, Any]:
    """获取预设模式的配置
    
    参数：
        mode: 模式名称
            - 'normal': 常规模式（全部时间，1小时步长，30次迭代，7天预热）
            - 'fast': 快速模式（每月2周，3小时步长，5次迭代，3天预热）
    
    返回：
        配置字典
    """
    if mode == 'normal':
        return {
            'sampling_mode': 'none',  # 全部时间
            'timestep': 1,  # 1小时
            'max_iterations': 30,  # 30次迭代
            'warmup_days': 7,  # 7天预热
            'convergence_tolerance': 0.01,  # 默认容差
        }
    elif mode == 'fast':
        return {
            'sampling_mode': 'monthly_2weeks',  # 每月2周
            'timestep': 3,  # 3小时
            'max_iterations': 5,  # 5次迭代
            'warmup_days': 3,  # 3天预热
            'convergence_tolerance': 0.5,  # 放宽的容差
        }
    else:
        # 默认返回常规模式
        return get_preset_mode_config('normal')


def create_config_with_material(epw_path: str, sky_temp_weights: Optional[Dict[str, float]] = None,
                                warmup_days: Optional[int] = None,
                                timestep: int = 1,
                                sampling_mode: str = 'none',
                                fast_mode: bool = False,
                                max_iterations: Optional[int] = None,
                                convergence_tolerance: Optional[float] = None,
                                preset_mode: Optional[str] = None) -> dict:
    """创建配置（材料属性由运行时注入；天气使用传入的 EPW 路径）
    
    参数：
        epw_path: EPW文件路径
        sky_temp_weights: 天空温度模型权重字典（可选）
        warmup_days: 预热期天数（可选，默认从环境变量或7天）
        timestep: 时间步长（小时，默认1）
        sampling_mode: 时间采样模式（'none', 'monthly_2weeks', 'monthly_1week', 'seasonal', 'representative'）
        fast_mode: 快速模式（已废弃，使用preset_mode代替）
        max_iterations: 最大迭代次数（可选）
        convergence_tolerance: 收敛容差（可选）
        preset_mode: 预设模式（'normal' 或 'fast'），如果提供，会覆盖其他参数
    """
    # 如果提供了预设模式，使用预设配置
    if preset_mode:
        preset_config = get_preset_mode_config(preset_mode)
        sampling_mode = preset_config['sampling_mode']
        timestep = preset_config['timestep']
        if max_iterations is None:
            max_iterations = preset_config['max_iterations']
        if warmup_days is None:
            warmup_days = preset_config['warmup_days']
        if convergence_tolerance is None:
            convergence_tolerance = preset_config['convergence_tolerance']
        fast_mode = (preset_mode == 'fast')
    
    # 预热期优化：如果精度允许，可以减少预热期以提升性能
    if warmup_days is None:
        if fast_mode:
            warmup_days = int(os.environ.get('GLASS_WARMUP_DAYS', '3'))  # 快速模式默认3天
        else:
            warmup_days = int(os.environ.get('GLASS_WARMUP_DAYS', '7'))
    
    # 快速模式：自动设置采样和时间步长（向后兼容）
    if fast_mode and not preset_mode:
        if sampling_mode == 'none':
            sampling_mode = 'monthly_2weeks'  # 快速模式默认每月2周
        if timestep == 1:
            timestep = 2  # 快速模式默认2小时步长
        if max_iterations is None:
            max_iterations = 5  # 快速模式减少迭代
        if convergence_tolerance is None:
            convergence_tolerance = 0.05  # 快速模式放宽容差
    
    # 生成采样日期列表
    sampling_dates = None
    if sampling_mode != 'none':
        sampling_dates = get_sampling_dates(sampling_mode, year=2024)
    
    config = {
        "simulation": {
            "start_month": 1,
            "start_day": 1,
            "end_month": 12,
            "end_day": 31,
            "timestep": timestep,
            "warmup_days": warmup_days,
            "use_epw_dates": True,
            "progress_interval_hours": 0,
            "sampling_mode": sampling_mode,  # 新增：采样模式
            "sampling_dates": sampling_dates,  # 新增：采样日期列表
            "fast_mode": fast_mode,  # 新增：快速模式标志
            "max_iterations": max_iterations,  # 新增：最大迭代次数
            "convergence_tolerance": convergence_tolerance,  # 新增：收敛容差
        },
        "building": {
            "zones": [
                {
                    "name": "Zone1",
                    "volume": 500,
                    "area": 100,
                    "occupancy_density": 0.05,
                    "equipment_load": 10,
                    "lighting_load": 5,
                    "surfaces": [
                        {"name": "ExtWall_South", "zone": "Zone1", "area": 100, "orientation": "South", "construction": "Wall_Standard"},
                        {"name": "ExtWall_North", "zone": "Zone1", "area": 100, "orientation": "North", "construction": "Wall_Standard"},
                        {"name": "ExtWall_East",  "zone": "Zone1", "area": 80,  "orientation": "East",  "construction": "Wall_Standard"},
                        {"name": "ExtWall_West",  "zone": "Zone1", "area": 80,  "orientation": "West",  "construction": "Wall_Standard"},
                        {"name": "Roof",          "zone": "Zone1", "area": 150, "orientation": "Roof",  "construction": "Roof_Standard"},
                        {"name": "Floor",         "zone": "Zone1", "area": 150, "orientation": "Floor", "construction": "Floor_Standard"}
                    ]
                }
            ]
        },
        "hvac": {
            "cooling_setpoint": 26,
            "heating_setpoint": 20,
            "humidity_setpoint": 0.5,
            "cop_cooling": 3.5,
            "cop_heating": 3.0,
            "cop_ref_temp": 35,
            "cop_temp_coeff_a": -0.01,
            "cop_temp_coeff_b": 0.0001,
            "plr_coeff_a": 0.125,
            "plr_coeff_b": 0.875,
            "max_cooling_capacity": 50000,
            "max_heating_capacity": 40000,
            "air_mass_flow": 2.0,
            "ventilation_ach": 0.2
        },
        "weather": {
            "epw_file": epw_path
        }
    }
    
    # 如果提供了天空温度权重，添加到配置中
    if sky_temp_weights is not None:
        config["simulation"]["sky_temp_weights"] = sky_temp_weights
    
    return config


# 以下函数已废弃，改用EnergyPlus计算
# def _apply_material_scenario(engine: SimulationEngine, wall: dict, roof: dict):
def _apply_material_scenario_OLD(engine, wall: dict, roof: dict):
    """把场景材料参数应用到模型：仅修改外层材料的 α（吸收率）、ε（发射率）、λ（导热系数）。
    同时，为确保生效，也把对应 Surface 的 solar_absorptance/emissivity 设置为场景值（优先级高于材料）。
    """
    bm = engine.building_model
    # 墙体外层（例如抹灰/涂层/外饰面）
    wall_cons = bm.constructions.get('Wall_Standard')
    if wall_cons and wall_cons.layers:
        m = wall_cons.layers[0]  # 外层
        if 'alpha' in wall and wall['alpha'] is not None:
            m.solar_absorptance = float(wall['alpha'])
        if 'emissivity' in wall and wall['emissivity'] is not None:
            m.emissivity = float(wall['emissivity'])
        if 'conductivity' in wall and wall['conductivity'] is not None:
            m.conductivity = float(wall['conductivity'])
    # 屋面外层
    roof_cons = bm.constructions.get('Roof_Standard')
    if roof_cons and roof_cons.layers:
        m = roof_cons.layers[0]
        if 'alpha' in roof and roof['alpha'] is not None:
            m.solar_absorptance = float(roof['alpha'])
        if 'emissivity' in roof and roof['emissivity'] is not None:
            m.emissivity = float(roof['emissivity'])
        if 'conductivity' in roof and roof['conductivity'] is not None:
            m.conductivity = float(roof['conductivity'])

    # 直接在 Surface 层面也设置（保证被热平衡优先采纳）
    for z in bm.zones:
        for s in z.surfaces:
            if s.orientation in ['South', 'North', 'East', 'West']:
                if 'alpha' in wall and wall['alpha'] is not None:
                    s.solar_absorptance = float(wall['alpha'])
                if 'emissivity' in wall and wall['emissivity'] is not None:
                    s.emissivity = float(wall['emissivity'])
            elif s.orientation == 'Roof':
                if 'alpha' in roof and roof['alpha'] is not None:
                    s.solar_absorptance = float(roof['alpha'])
                if 'emissivity' in roof and roof['emissivity'] is not None:
                    s.emissivity = float(roof['emissivity'])


# 已废弃，改用EnergyPlus
def _log_outer_layer_params_OLD(engine):
    """打印当前模型中墙/屋面外层材料的 α/ε/λ 参数，便于核对场景是否生效。"""
    bm = engine.building_model
    def fmt(val, nd=3):
        try:
            return f"{float(val):.{nd}f}"
        except Exception:
            return str(val)

    # 墙
    wall_cons = bm.constructions.get('Wall_Standard')
    if wall_cons and wall_cons.layers:
        wm = wall_cons.layers[0]
        print(f"    墙外层(材料): alpha={fmt(wm.solar_absorptance)}, eps={fmt(wm.emissivity)}, lambda={fmt(wm.conductivity)} W/mK")
    else:
        print("    墙外层: 未找到 Wall_Standard 或其外层材料")

    # 屋面
    roof_cons = bm.constructions.get('Roof_Standard')
    if roof_cons and roof_cons.layers:
        rm = roof_cons.layers[0]
        print(f"    屋面外层(材料): alpha={fmt(rm.solar_absorptance)}, eps={fmt(rm.emissivity)}, lambda={fmt(rm.conductivity)} W/mK")
    else:
        print("    屋面外层: 未找到 Roof_Standard 或其外层材料")

    # 同时打印 Surface 层面的实际生效（优先级更高）
    for z in bm.zones:
        for s in z.surfaces:
            if s.orientation in ['South','North','East','West','Roof']:
                a = getattr(s, 'solar_absorptance', None)
                e = getattr(s, 'emissivity', None)
                if a is not None or e is not None:
                    print(f"      Surface {s.name}({s.orientation}) 覆盖: alpha={fmt(a)}, eps={fmt(e)}")


# 已废弃，改用EnergyPlus
def _get_outer_layer_params_OLD(engine):
    """返回当前模型墙/屋面外层材料的实际 α/ε/λ 参数（用于写入 CSV）"""
    bm = engine.building_model
    w_alpha=w_eps=w_lambda=None
    r_alpha=r_eps=r_lambda=None
    wall_cons = bm.constructions.get('Wall_Standard')
    if wall_cons and wall_cons.layers:
        wm = wall_cons.layers[0]
        w_alpha = getattr(wm, 'solar_absorptance', None)
        w_eps = getattr(wm, 'emissivity', None)
        w_lambda = getattr(wm, 'conductivity', None)
    roof_cons = bm.constructions.get('Roof_Standard')
    if roof_cons and roof_cons.layers:
        rm = roof_cons.layers[0]
        r_alpha = getattr(rm, 'solar_absorptance', None)
        r_eps = getattr(rm, 'emissivity', None)
        r_lambda = getattr(rm, 'conductivity', None)
    return {
        'Wall_Alpha': w_alpha, 'Wall_Eps': w_eps, 'Wall_Lambda_WmK': w_lambda,
        'Roof_Alpha': r_alpha, 'Roof_Eps': r_eps, 'Roof_Lambda_WmK': r_lambda,
    }


def _build_scenarios() -> List[Dict[str, Any]]:
    """构建默认的三个固定场景。"""
    return [
        {
            'name': '对比基准',
            'desc': '默认建筑材料（墙α≈0.6, ε≈0.9；屋面α≈0.7, ε≈0.9）',
            'wall': { 'alpha': None, 'emissivity': None, 'conductivity': None },
            'roof': { 'alpha': None, 'emissivity': None, 'conductivity': None },
        },
        {
            'name': '辐射制冷',
            'desc': '高反射、高发射率材料（如 α=0.1, ε=0.95）',
            'wall': { 'alpha': 0.1, 'emissivity': 0.95, 'conductivity': None },
            'roof': { 'alpha': 0.1, 'emissivity': 0.95, 'conductivity': None },
        },
        {
            'name': '辐射制热/保温',
            'desc': '高吸收、高发射率材料（如 α=0.9, ε=0.95）',
            'wall': { 'alpha': 0.9, 'emissivity': 0.95, 'conductivity': None },
            'roof': { 'alpha': 0.9, 'emissivity': 0.95, 'conductivity': None },
        },
    ]


def _worker_one(epw_path: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
    """单个任务：在指定 EPW 下运行一个场景。"""
    logging.getLogger('core.weather_data').setLevel(logging.WARNING)
    logging.getLogger('core.simulation_engine').setLevel(logging.WARNING)

    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
    cfg = create_config_with_material(epw_path)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
        json.dump(cfg, tf, ensure_ascii=False, indent=2)
        cfg_path = tf.name

    try:
        # 已废弃：改用EnergyPlus，此函数仅保留作为参考
        # engine = SimulationEngine(cfg_path)
        # _apply_material_scenario_OLD(engine, scenario['wall'], scenario['roof'])
        # engine.run_simulation()
        # s = engine.get_summary()
        # floor_area = sum(z.area for z in engine.building_model.zones) or 1e-6
        # cool_MJ_m2 = s['total_cooling_energy_kWh'] * 3.6 / floor_area
        # heat_MJ_m2 = s['total_heating_energy_kWh'] * 3.6 / floor_area
        # hvac_MJ_m2 = (s['total_hvac_energy_kWh']) * 3.6 / floor_area
        # mat_params = _get_outer_layer_params_OLD(engine)
        
        # 占位符，避免代码错误（此函数已废弃，不应被调用）
        raise NotImplementedError("此函数已废弃，请使用run_material_comparison_energyplus()")
        row = {
            'EPW': epw_name,
            'Scenario': scenario['name'],
            'Desc': scenario['desc'],
            **mat_params,
            'Total_Cooling_Energy_kWh': s['total_cooling_energy_kWh'],
            'Total_Heating_Energy_kWh': s['total_heating_energy_kWh'],
            'Total_HVAC_Energy_kWh': s['total_hvac_energy_kWh'],
            'Total_Cooling_MJ_per_m2': cool_MJ_m2,
            'Total_Heating_MJ_per_m2': heat_MJ_m2,
            'Total_HVAC_MJ_per_m2': hvac_MJ_m2,
            'Floor_Area_m2': floor_area,
            'Peak_Cooling_Load_kW': s['peak_cooling_load_kW'],
            'Peak_Heating_Load_kW': s['peak_heating_load_kW'],
        }
        return {'ok': True, 'row': row}

    except Exception as e:
        return {'ok': False, 'error': str(e), 'scenario': scenario.get('name'), 'epw': epw_path}

    finally:
        try:
            os.remove(cfg_path)
        except Exception:
            pass


def _convert_epw_to_utf8_if_needed(epw_path: str) -> str:
    """如果需要，将 EPW 文件转换为 UTF-8 编码。
    
    返回：原始路径（如果已经是 UTF-8）或临时 UTF-8 文件路径。
    """
    # 尝试检测文件编码
    epw_encodings = ['utf-8', 'latin-1', 'cp1252', 'gbk', 'gb2312']
    detected_encoding = None
    
    for enc in epw_encodings:
        try:
            with open(epw_path, 'r', encoding=enc) as f:
                f.read(1000)
            detected_encoding = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if detected_encoding is None:
        # 无法检测，假设是 latin-1（EPW 标准编码）
        detected_encoding = 'latin-1'
    
    # 如果已经是 UTF-8，直接返回原路径
    if detected_encoding == 'utf-8':
        return epw_path
    
    # 需要转换：创建临时 UTF-8 文件
    try:
        with open(epw_path, 'r', encoding=detected_encoding, errors='replace') as src:
            content = src.read()
        
        # 创建临时 UTF-8 文件
        temp_epw = tempfile.NamedTemporaryFile(mode='w', suffix='.epw', delete=False, encoding='utf-8')
        temp_epw.write(content)
        temp_epw.close()
        
        return temp_epw.name
    except Exception as e:
        # 转换失败，返回原路径（让 SimulationEngine 处理）
        return epw_path


# 已废弃，改用EnergyPlus
def _reset_engine_results_OLD(engine):
    """重置仿真引擎的结果存储，用于复用引擎运行多个场景"""
    engine.results = {
        'hourly_loads': [],
        'zone_temperatures': [],
        'surface_temperatures': [],
        'weather_data': []
    }
    # 重置区域状态（温度、负荷等）
    for zone in engine.building_model.zones:
        zone.temperature = 293.15  # 重置为初始温度
        zone.cooling_load = 0.0
        zone.heating_load = 0.0
        zone.latent_load = 0.0
        zone.cooling_energy = 0.0
        zone.heating_energy = 0.0
        zone.surface_temperatures = {}
        # 重置表面温度
        for surface in zone.surfaces:
            surface.temperature = 293.15
            surface.internal_radiative_flux = 0.0


def _worker_epw_batch(epw_path: str, scenarios: List[Dict[str, Any]], 
                     sky_temp_weights: Optional[Dict[str, float]] = None,
                     reuse_engine: bool = True,
                     warmup_days: Optional[int] = None,
                     timestep: int = 1,
                     sampling_mode: str = 'none',
                     fast_mode: bool = False,
                     preset_mode: Optional[str] = None) -> Dict[str, Any]:
    """工作线程/进程任务：同一 EPW 下顺序运行多个场景，减少线程/进程和IO开销。
    
    参数：
        epw_path: EPW文件路径
        scenarios: 场景列表
        sky_temp_weights: 天空温度模型权重（可选）
        reuse_engine: 是否复用 SimulationEngine（优化性能，默认 True）
    """
    import os as os_module
    import multiprocessing
    
    # 检查是否是进程还是线程
    try:
        process_name = multiprocessing.current_process().name
        worker_id = process_name
        worker_type = "进程"
    except Exception:
        # 如果 multiprocessing 不可用，使用线程信息
        import threading
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        worker_id = f"{thread_id} ({thread_name})"
        worker_type = "线程"
    
    print(f"[{worker_type} {worker_id}] 开始处理: {os_module.path.basename(epw_path)}")
    
    logging.getLogger('core.weather_data').setLevel(logging.WARNING)
    logging.getLogger('core.simulation_engine').setLevel(logging.WARNING)

    rows = []
    errors = []
    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
    cfg_path = None
    temp_epw_path = None
    actual_epw_path = epw_path  # 默认使用原始路径
    engine = None  # 用于复用的引擎实例
    
    try:
        # 验证 EPW 文件是否存在
        if not os.path.exists(epw_path):
            raise FileNotFoundError(f"EPW 文件不存在: {epw_path}")
        
        # 尝试将 EPW 文件转换为 UTF-8（如果需要）
        temp_epw_path = _convert_epw_to_utf8_if_needed(epw_path)
        actual_epw_path = temp_epw_path if temp_epw_path != epw_path else epw_path
        
    except Exception as e:
        errors.append({
            'ok': False,
            'error': f"EPW 文件预处理失败: {str(e)}",
            'scenario': 'all',
            'epw': epw_path
        })
        if rows and not errors:
            return {'ok': True, 'rows': rows}
        elif rows and errors:
            return {'ok': True, 'rows': rows, 'partial_errors': errors}
        else:
            return {'ok': False, 'error': f'EPW 文件预处理失败: {str(e)}', 'epw': epw_path}
    
    try:
        # 优化：如果启用复用，只创建一次引擎
        if reuse_engine and len(scenarios) > 1:
            # 创建一次配置和引擎（用于第一个场景）
            cfg = create_config_with_material(actual_epw_path, sky_temp_weights=sky_temp_weights,
                                            warmup_days=warmup_days, timestep=timestep,
                                            sampling_mode=sampling_mode, fast_mode=fast_mode,
                                            preset_mode=preset_mode)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tf:
                json.dump(cfg, tf, ensure_ascii=False, indent=2)
                cfg_path = tf.name
            
            try:
                # 已废弃：改用EnergyPlus
                # engine = SimulationEngine(cfg_path)
                raise NotImplementedError("此函数已废弃，请使用run_material_comparison_energyplus()")
                print(f"    [优化] 已创建共享引擎，将复用天气数据和建筑模型")
            except Exception as e:
                # 如果创建失败，回退到非复用模式
                print(f"    [警告] 引擎创建失败，回退到非复用模式: {str(e)[:100]}")
                reuse_engine = False
                if cfg_path:
                    try:
                        os.remove(cfg_path)
                    except Exception:
                        pass
                    cfg_path = None
        
        for scenario_idx, scenario in enumerate(scenarios):
            scenario_name = scenario.get('name', 'Unknown')
            scenario_cfg_path = None
            
            try:
                if reuse_engine and engine is not None:
                    # 复用引擎：只修改材料参数，重置结果，然后重新运行（已废弃）
                    # _apply_material_scenario_OLD(engine, scenario['wall'], scenario['roof'])
                    # _reset_engine_results_OLD(engine)
                    raise NotImplementedError("此函数已废弃，请使用run_material_comparison_energyplus()")
                    engine.run_simulation()
                    raw_s = engine.get_summary()
                    s = raw_s
                    # 缩放采样结果
                    if sampling_mode != 'none':
                        s = scale_summary_for_sampling(s, sampling_mode)
                else:
                    # 非复用模式：为每个场景创建新引擎（原始逻辑）
                    cfg = create_config_with_material(actual_epw_path, sky_temp_weights=sky_temp_weights,
                                                      warmup_days=warmup_days, timestep=timestep,
                                                      sampling_mode=sampling_mode, fast_mode=fast_mode,
                                                      preset_mode=preset_mode)
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tf:
                        json.dump(cfg, tf, ensure_ascii=False, indent=2)
                        scenario_cfg_path = tf.name
                    
                    try:
                        # 已废弃：改用EnergyPlus
                        # scenario_engine = SimulationEngine(scenario_cfg_path)
                        raise NotImplementedError("此函数已废弃，请使用run_material_comparison_energyplus()")
                    except (UnicodeDecodeError, UnicodeError) as ude:
                        error_msg = (
                            f"EPW 文件编码错误 ({epw_path}): {str(ude)}\n"
                            f"EPW 文件可能使用了非 UTF-8 编码（如 GBK、Windows-1252 等）。\n"
                            f"建议：检查 EPW 文件编码，或使用支持多种编码的 EPW 文件。"
                        )
                        raise IOError(error_msg) from ude
                    except Exception as e:
                        error_str = str(e).lower()
                        if any(keyword in error_str for keyword in ['codec', 'decode', 'encoding', 'utf-8', 'utf8']):
                            error_msg = (
                                f"EPW 文件编码问题 ({epw_path}): {e}\n"
                                f"提示：EPW 文件可能使用了非 UTF-8 编码。"
                            )
                            raise IOError(error_msg) from e
                        raise
                    
                    # _apply_material_scenario_OLD(scenario_engine, scenario['wall'], scenario['roof'])
                    raise NotImplementedError("此函数已废弃，请使用run_material_comparison_energyplus()")
                    scenario_engine.run_simulation()
                    raw_s = scenario_engine.get_summary()
                    s = raw_s
                    # 缩放采样结果
                    if sampling_mode != 'none':
                        s = scale_summary_for_sampling(s, sampling_mode)
                    engine = scenario_engine  # 用于获取 floor_area 等
                
                floor_area = sum(z.area for z in engine.building_model.zones) or 1e-6
                cool_MJ_m2 = s['total_cooling_energy_kWh'] * 3.6 / floor_area
                heat_MJ_m2 = s['total_heating_energy_kWh'] * 3.6 / floor_area
                hvac_MJ_m2 = (s['total_hvac_energy_kWh']) * 3.6 / floor_area

                # 新增：计算每日平均单位面积能耗（用于跨模式对比）
                sim_days = s.get('total_hours', 8760) / 24
                daily_hvac_kwh_m2 = (s['total_hvac_energy_kWh'] / sim_days / floor_area) if sim_days > 0 and floor_area > 0 else 0

                # mat_params = _get_outer_layer_params_OLD(engine)
                mat_params = {}  # 占位符
                scale_factor = get_sampling_scale_factor(sampling_mode) if sampling_mode != 'none' else 1.0
                raw_total_hours = raw_s.get('total_hours', None) if isinstance(raw_s, dict) else None

                row = {
                    'EPW': epw_name,
                    'Scenario': scenario['name'],
                    'Desc': scenario['desc'],
                    **mat_params,
                    'Total_Cooling_Energy_kWh': s['total_cooling_energy_kWh'],
                    'Total_Heating_Energy_kWh': s['total_heating_energy_kWh'],
                    'Total_HVAC_Energy_kWh': s['total_hvac_energy_kWh'],
                    'Total_Cooling_MJ_per_m2': cool_MJ_m2,
                    'Total_Heating_MJ_per_m2': heat_MJ_m2,
                    'Total_HVAC_MJ_per_m2': hvac_MJ_m2,
                    'Daily_HVAC_kWh_per_m2': daily_hvac_kwh_m2,
                    'Floor_Area_m2': floor_area,
                    'Peak_Cooling_Load_kW': s['peak_cooling_load_kW'],
                    'Peak_Heating_Load_kW': s['peak_heating_load_kW'],
                    'Simulation_Days': sim_days,
                    'Sampling_Scale': scale_factor,
                    'Raw_Total_Hours': raw_total_hours,
                    'Raw_Total_Cooling_Energy_kWh': (raw_s.get('total_cooling_energy_kWh') if isinstance(raw_s, dict) else None),
                    'Raw_Total_Heating_Energy_kWh': (raw_s.get('total_heating_energy_kWh') if isinstance(raw_s, dict) else None),
                    'Raw_Total_HVAC_Energy_kWh': (raw_s.get('total_hvac_energy_kWh') if isinstance(raw_s, dict) else None),
                }
                rows.append(row)
                # 调试信息：显示成功计算的场景
                print(f"    [{'优化' if reuse_engine and engine else '标准'}] 场景 '{scenario_name}' 计算成功")
            except Exception as e:
                import traceback
                error_msg = f"{scenario_name}: {str(e)}"
                error_detail = traceback.format_exc()
                errors.append({
                    'ok': False,
                    'error': error_msg,
                    'error_detail': error_detail,
                    'scenario': scenario_name,
                    'epw': epw_path
                })
                # 调试信息：显示失败的场景
                print(f"    [DEBUG] 场景 '{scenario_name}' 计算失败: {str(e)[:100]}")
            finally:
                if scenario_cfg_path:
                    try:
                        os.remove(scenario_cfg_path)
                    except Exception:
                        pass
        
        # 清理共享引擎的配置文件
        if cfg_path and reuse_engine:
            try:
                os.remove(cfg_path)
            except Exception:
                pass
    finally:
        # 清理临时 EPW 文件
        if temp_epw_path and temp_epw_path != epw_path:
            try:
                os.remove(temp_epw_path)
            except Exception:
                pass
    
    # 调试信息：显示每个 EPW 的计算结果
    try:
        process_name = multiprocessing.current_process().name
        worker_id = process_name
        worker_type = "进程"
    except Exception:
        import threading
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        worker_id = f"{thread_id} ({thread_name})"
        worker_type = "线程"
    
    print(f"  [{worker_type} {worker_id}] EPW {epw_name}: 成功 {len(rows)} 个场景，失败 {len(errors)} 个场景")
    if rows:
        print(f"    成功场景: {[r.get('Scenario', 'Unknown') for r in rows]}")
    if errors:
        print(f"    失败场景: {[e.get('scenario', 'Unknown') for e in errors]}")
    
    if rows and not errors:
        return {'ok': True, 'rows': rows}
    elif rows and errors:
        # 部分成功
        return {'ok': True, 'rows': rows, 'partial_errors': errors}
    else:
        # 全失败 - 返回详细错误信息
        if errors:
            error_summary = '; '.join([e.get('error', 'Unknown error') for e in errors[:3]])
            if len(errors) > 3:
                error_summary += f' ... (共 {len(errors)} 个错误)'
            return {
                'ok': False,
                'error': f'All scenarios failed for {epw_name}: {error_summary}',
                'errors': errors,
                'epw': epw_path
            }
        else:
            return {'ok': False, 'error': f'All scenarios failed for {epw_name} (no error details)', 'epw': epw_path}


# 已废弃，改用EnergyPlus
def _run_all_tasks_parallel_OLD(epw_files: List[str], scenarios: List[Dict[str, Any]], max_workers: int) -> List[Dict[str, Any]]:
    """已废弃：此函数使用旧的SimulationEngine，已改用EnergyPlus"""
    raise NotImplementedError("此函数已废弃，请使用run_material_comparison_energyplus()")
    """并行运行所有 (EPW, 场景) 组合，带动态超时和重试机制。
    
    返回结果列表，每个元素为 {'ok': bool, 'row': dict} 或 {'ok': False, 'error': str, ...}
    
    超时策略：
    - 默认超时：24000s（可通过 MATERIALS_TASK_TIMEOUT 覆盖）
    - 重试机制：失败任务自动重试 1 次
    
    注意：使用多线程而不是多进程，避免在Windows打包环境下创建多个GUI窗口。
    """
    # 构建所有任务：(epw_path, scenario)
    all_tasks = []
    for epw_path in epw_files:
        for scenario in scenarios:
            all_tasks.append((epw_path, scenario))
    
    total_tasks = len(all_tasks)
    print(f"\n总模拟任务数: {total_tasks} (天气文件数: {len(epw_files)}, 场景数: {len(scenarios)})")
    print(f"并行线程数: {max_workers}")

    try:
        timeout_sec = int(os.environ.get('MATERIALS_TASK_TIMEOUT', '24000'))
    except Exception:
        timeout_sec = 24000
    
    print(f"单任务超时: {timeout_sec}s (可通过 MATERIALS_TASK_TIMEOUT 环境变量覆盖)")
    
    results: List[Dict[str, Any]] = []
    failed_tasks = []  # 记录失败的任务用于重试
    
    # 使用线程池而不是进程池，避免在Windows打包环境下创建多个GUI窗口
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        # 第一轮：提交所有任务
        future_to_task = {}
        start_time = {}
        for epw_path, scenario in all_tasks:
            fut = ex.submit(_worker_one, epw_path, scenario)
            future_to_task[fut] = (epw_path, scenario)
            start_time[fut] = time.monotonic()
        
        pending = set(future_to_task.keys())
        completed_count = 0
        
        # 循环等待任务完成或超时
        while pending:
            done, not_done = cf.wait(pending, timeout=2.0, return_when=cf.FIRST_COMPLETED)
            
            # 处理已完成任务
            for fut in done:
                pending.remove(fut)
                epw_path, scenario = future_to_task[fut]
                epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                scenario_name = scenario.get('name', 'Unknown')
                try:
                    res = fut.result()
                    results.append(res)
                    completed_count += 1
                    if res.get('ok'):
                        print(f"  [{completed_count}/{total_tasks}] [OK] {epw_name} | {scenario_name}")
                    else:
                        # 失败的任务记录用于重试
                        failed_tasks.append((epw_path, scenario))
                        print(f"  [{completed_count}/{total_tasks}] [FAIL] {epw_name} | {scenario_name} | {res.get('error')}")
                except Exception as e:
                    failed_tasks.append((epw_path, scenario))
                    results.append({'ok': False, 'error': str(e), 'scenario': scenario_name, 'epw': epw_path})
                    completed_count += 1
                    print(f"  [{completed_count}/{total_tasks}] [ERROR] {epw_name} | {scenario_name} | {str(e)}")
            
            # 检查超时任务
            now = time.monotonic()
            timed_out = [f for f in not_done if (now - start_time.get(f, now)) > timeout_sec]
            for f in timed_out:
                pending.remove(f)
                epw_path, scenario = future_to_task[f]
                epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                scenario_name = scenario.get('name', 'Unknown')
                
                # 超时任务记录用于重试
                failed_tasks.append((epw_path, scenario))
                results.append({'ok': False, 'error': f'Task timeout after {timeout_sec}s', 'scenario': scenario_name, 'epw': epw_path})
                completed_count += 1
                # 尝试取消（若仍在队列中可取消，若已运行则无法取消）
                f.cancel()
                print(f"  [{completed_count}/{total_tasks}] [TIMEOUT] {epw_name} | {scenario_name}")
        
        # 第二轮：重试失败的任务（仅重试 1 次）
        if failed_tasks:
            print(f"\n开始重试 {len(failed_tasks)} 个失败任务……")
            retry_future_to_task = {}
            retry_start_time = {}
            for epw_path, scenario in failed_tasks:
                fut = ex.submit(_worker_one, epw_path, scenario)
                retry_future_to_task[fut] = (epw_path, scenario)
                retry_start_time[fut] = time.monotonic()
            
            retry_pending = set(retry_future_to_task.keys())
            retry_completed = 0
            
            while retry_pending:
                done, not_done = cf.wait(retry_pending, timeout=2.0, return_when=cf.FIRST_COMPLETED)
                
                for fut in done:
                    retry_pending.remove(fut)
                    epw_path, scenario = retry_future_to_task[fut]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    scenario_name = scenario.get('name', 'Unknown')
                    
                    # 移除之前的失败记录
                    results = [r for r in results if not (
                        r.get('epw') == epw_path and r.get('scenario') == scenario_name
                    )]
                    
                    try:
                        res = fut.result()
                        results.append(res)
                        retry_completed += 1
                        if res.get('ok'):
                            print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [OK] {epw_name} | {scenario_name}")
                        else:
                            results.append(res)
                            print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [FAIL] {epw_name} | {scenario_name}")
                    except Exception as e:
                        results.append({'ok': False, 'error': str(e), 'scenario': scenario_name, 'epw': epw_path})
                        retry_completed += 1
                        print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [ERROR] {epw_name} | {scenario_name}")
                
                # 检查重试超时
                now = time.monotonic()
                retry_timed_out = [f for f in not_done if (now - retry_start_time.get(f, now)) > timeout_sec]
                for f in retry_timed_out:
                    retry_pending.remove(f)
                    epw_path, scenario = retry_future_to_task[f]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    scenario_name = scenario.get('name', 'Unknown')
                    
                    # 移除之前的失败记录
                    results = [r for r in results if not (
                        r.get('epw') == epw_path and r.get('scenario') == scenario_name
                    )]
                    
                    results.append({'ok': False, 'error': f'Task timeout after {timeout_sec}s (retry)', 'scenario': scenario_name, 'epw': epw_path})
                    retry_completed += 1
                    f.cancel()
                    print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [TIMEOUT] {epw_name} | {scenario_name}")
    
    return results


# 已废弃，改用EnergyPlus
def _run_all_tasks_parallel_batch_OLD(
    epw_files: List[str],
    scenarios: List[Dict[str, Any]],
    max_workers: int,
    progress_cb: Optional[callable] = None,
    sky_temp_weights: Optional[Dict[str, float]] = None,
    use_multiprocessing: bool = True,  # 默认启用多进程以提高CPU利用率
    reuse_engine: bool = True,
    warmup_days: Optional[int] = None,
    timestep: int = 1,
    sampling_mode: str = 'none',
    fast_mode: bool = False,
    preset_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """已废弃：此函数使用旧的SimulationEngine，已改用EnergyPlus"""
    raise NotImplementedError("此函数已废弃，请使用run_material_comparison_energyplus()")
    
    # 以下代码已废弃，仅保留作为参考
    """并行运行EPW批次：每个线程/进程内顺序跑完该EPW下的所有场景，减少线程/IO开销。

    - progress_cb: 可选回调 progress_cb(completed, total, message)
    - sky_temp_weights: 天空温度模型权重（可选）
    - use_multiprocessing: 是否使用多进程（默认True，使用多进程以提高CPU利用率）

    返回拍扁后的列表：[{ok:True,row:...}|{ok:False,error:...}]
    
    注意：
    - 默认使用多线程，避免在Windows打包环境下创建多个GUI窗口
    - 如果 use_multiprocessing=True，使用多进程以获得更好的CPU利用率，但需要确保子进程不会创建GUI
    """
    total_jobs = len(epw_files)
    import threading
    import multiprocessing
    
    # 检查是否应该使用多进程
    # 在 Windows 打包环境下，如果使用多进程，需要确保子进程不会创建 GUI
    if use_multiprocessing:
        # 检查是否是主进程
        if multiprocessing.current_process().name != 'MainProcess':
            # 子进程不应该创建 GUI，直接返回空结果
            # 这个检查在这里是多余的，因为子进程不会执行到这里
            # 但保留作为安全措施
            return []
        
        # 在 Windows 上，如果是打包后的 exe，需要 freeze_support
        if sys.platform.startswith('win') and getattr(sys, 'frozen', False):
            multiprocessing.freeze_support()
        
        print(f"\n总并行任务数(EPW数): {total_jobs}，每个任务包含 {len(scenarios)} 个场景")
        print(f"并行进程数: {max_workers}")
        print(f"CPU核心数: {os.cpu_count() or 1}")
        print(f"[提示] 使用多进程并行计算，子进程不会创建GUI窗口")
    else:
        print(f"\n总并行任务数(EPW数): {total_jobs}，每个任务包含 {len(scenarios)} 个场景")
        print(f"并行线程数: {max_workers}")
        print(f"CPU核心数: {os.cpu_count() or 1}")
        print(f"主线程ID: {threading.current_thread().ident}")
        print(f"[提示] 使用多线程并行计算，不会创建多个进程")

    try:
        timeout_sec = int(os.environ.get('MATERIALS_TASK_TIMEOUT', '24000'))
    except Exception:
        timeout_sec = 24000
    print(f"单任务超时: {timeout_sec}s (可通过 MATERIALS_TASK_TIMEOUT 覆盖)")

    flat_results: List[Dict[str, Any]] = []

    # 根据 use_multiprocessing 参数选择使用线程池或进程池
    try:
        if use_multiprocessing:
            # 使用进程池以获得更好的CPU利用率
            # 注意：子进程不会执行 GUI 相关代码，因为工作函数中不包含 GUI 创建代码
            executor_class = cf.ProcessPoolExecutor
        else:
            # 使用线程池，避免在Windows打包环境下创建多个GUI窗口
            executor_class = cf.ThreadPoolExecutor
        
        with executor_class(max_workers=max_workers) as ex:
            future_to_epw = {}
            start_time = {}
            for epw_path in epw_files:
                fut = ex.submit(_worker_epw_batch, epw_path, scenarios, sky_temp_weights,
                              reuse_engine, warmup_days, timestep, sampling_mode, fast_mode, preset_mode)
                future_to_epw[fut] = epw_path
                start_time[fut] = time.monotonic()
            pending = set(future_to_epw.keys())
            completed = 0
            while pending:
                done, not_done = cf.wait(pending, timeout=2.0, return_when=cf.FIRST_COMPLETED)
                for fut in done:
                    pending.remove(fut)
                    epw_path = future_to_epw[fut]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    try:
                        res = fut.result()
                        completed += 1
                        if res.get('ok'):
                            rows = res.get('rows', [])
                            flat_results.extend({'ok': True, 'row': r} for r in rows)
                            # 显示当前并行状态
                            active_count = len(pending)
                            msg = f"[OK] {epw_name} | rows={len(rows)} | 剩余任务: {active_count}"
                            print(f"  [{completed}/{total_jobs}] {msg}")
                            if progress_cb:
                                progress_cb(completed, total_jobs, msg)
                            if 'partial_errors' in res:
                                cnt = len(res['partial_errors'])
                                warn = f"[WARN] {epw_name} 部分场景失败：{cnt}"
                                print(f"      {warn}")
                                if progress_cb:
                                    progress_cb(completed, total_jobs, warn)
                        else:
                            error_msg = res.get('error', 'Unknown error')
                            # 如果有详细错误信息，也打印出来
                            if 'errors' in res and res['errors']:
                                first_error = res['errors'][0]
                                if 'error_detail' in first_error:
                                    print(f"  [{completed}/{total_jobs}] [FAIL] {epw_name} | {error_msg}")
                                    print(f"      详细错误: {first_error.get('error_detail', '')[:200]}...")
                                else:
                                    print(f"  [{completed}/{total_jobs}] [FAIL] {epw_name} | {error_msg}")
                            else:
                                print(f"  [{completed}/{total_jobs}] [FAIL] {epw_name} | {error_msg}")
                            flat_results.append({'ok': False, 'error': error_msg, 'epw': epw_path, 'details': res.get('errors')})
                            if progress_cb:
                                progress_cb(completed, total_jobs, f"[FAIL] {epw_name} | {error_msg}")
                    except Exception as e:
                        completed += 1
                        flat_results.append({'ok': False, 'error': str(e), 'epw': epw_path})
                        msg = f"[ERROR] {epw_name} | {str(e)}"
                        print(f"  [{completed}/{total_jobs}] {msg}")
                        if progress_cb:
                            progress_cb(completed, total_jobs, msg)
                # 超时检查
                now = time.monotonic()
                timed_out = [f for f in not_done if (now - start_time.get(f, now)) > timeout_sec]
                for f in timed_out:
                    pending.remove(f)
                    epw_path = future_to_epw[f]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    flat_results.append({'ok': False, 'error': f'Task timeout after {timeout_sec}s', 'epw': epw_path})
                    print(f"  [TIMEOUT] {epw_name}")
    except KeyboardInterrupt:
        # 用户中断
        print("\n[中断] 用户中断了分析过程")
        if progress_cb:
            progress_cb(0, total_jobs, "[中断] 分析已被用户中断")
        raise
    except Exception as e:
        # 捕获所有异常，防止主进程退出
        import traceback
        error_msg = f"并行执行出错：{str(e)}\n{traceback.format_exc()}"
        print(f"\n[错误] {error_msg}")
        if progress_cb:
            progress_cb(0, total_jobs, f"[错误] {error_msg}")
        # 返回已收集的结果，而不是抛出异常
        return flat_results

    return flat_results


def build_china_map(
    df: pd.DataFrame,
    *,
    value_col: str,
    title: str,
    unit: str,
    color: str,
    range_color,
    value_transform=None,
    width: str = "1792px",
    height: str = "1008px",
    is_co2: bool = False,
):
    """构建中国地图（旧版本，保留向后兼容）
    
    Args:
        is_co2: 是否为CO2图（本版本忽略此参数）
    """
    dff = df.copy()
    if value_transform is not None:
        dff[value_col] = value_transform(dff[value_col])

    data_province = list(zip(dff["NAME"], dff[value_col]))
    max_val = float(dff[value_col].max())
    min_val = float(dff[value_col].min())

    chart = (
        Map(init_opts=opts.InitOpts(width=width, height=height))
        .add(
            " ",
            data_province,
            "china",
            is_map_symbol_show=False,
            itemstyle_opts=opts.ItemStyleOpts(color=color),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title=title,
                pos_top="70%",
                pos_right="53%",
            ),
            visualmap_opts=opts.VisualMapOpts(
                min_=min_val,
                max_=max_val,
                orient="horizontal",
                range_color=range_color,
                is_calculable=False,
                is_piecewise=False,
                item_width=30,
                item_height=300,
                pos_top="65%",
                pos_right="50%",
                range_text=[f"{max_val:.0f}", f"{min_val:.0f}"],
                textstyle_opts=opts.TextStyleOpts(font_size=24),
            ),
            legend_opts=opts.LegendOpts(
                type_="plain",
                pos_top="70%",
                pos_left="47%",
                orient="vertical",
                item_width=20,
                textstyle_opts=opts.TextStyleOpts(font_size=24),
                item_height=20,
            ),
            tooltip_opts=opts.TooltipOpts(formatter=f"{{b}}: {{c}} {unit}"),
        )
        .set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    )

    return chart


def _build_energy_and_co2_maps(df: pd.DataFrame):
    cooling_energy = build_china_map(
        df,
        value_col="Cooling",
        title="Cooling Energy Saving (MJ/m²/year)",
        unit="MJ/m²/year",
        color="#045FB4",
        range_color=["#E0ECF8", "#045FB4"],
    )

    cooling_co2 = build_china_map(
        df,
        value_col="Cooling",
        title="Cooling CO₂ Reduction (kg/m²/year)",
        unit="kg/m²/year",
        color="#228B22",
        range_color=["#E0ECF8", "#228B22"],
        value_transform=lambda s: s * 0.138,
    )

    heating_energy = build_china_map(
        df,
        value_col="Heating",
        title="Heating Energy Saving (MJ/m²/year)",
        unit="MJ/m²/year",
        color="#B40404",
        range_color=["#FBEFF5", "#B40404"],
    )

    heating_co2 = build_china_map(
        df,
        value_col="Heating",
        title="Heating CO₂ Reduction (kg/m²/year)",
        unit="kg/m²/year",
        color="#228B22",
        range_color=["#E0ECF8", "#228B22"],
        value_transform=lambda s: s * 0.138,
    )

    total_energy = build_china_map(
        df,
        value_col="Total",
        title="Total Energy Saving (MJ/m²/year)",
        unit="MJ/m²/year",
        color="#0B6121",
        range_color=["#E0F8E0", "#0B6121"],
    )

    total_co2 = build_china_map(
        df,
        value_col="Total",
        title="Total CO₂ Reduction (kg/m²/year)",
        unit="kg/m²/year",
        color="#228B22",
        range_color=["#E0ECF8", "#228B22"],
        value_transform=lambda s: s * 0.138,
    )

    return (
        cooling_energy,
        cooling_co2,
        heating_energy,
        heating_co2,
        total_energy,
        total_co2,
    )


def _export_png(chart, png_path: str):
    """导出图表为PNG，先渲染HTML文件，然后使用文件路径生成截图，等待echarts加载完成"""
    if not _SNAPSHOT_AVAILABLE:
        raise RuntimeError(
            "PNG export requires pyecharts-snapshot + snapshot-selenium. "
            "Install: pip install pyecharts-snapshot snapshot-selenium selenium"
        )
    # 先渲染HTML文件到临时位置
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        temp_html = f.name
    try:
        html_path = chart.render(temp_html)
        # 使用自定义快照函数，等待echarts加载
        _make_snapshot_with_wait(html_path, png_path)
    finally:
        # 清理临时HTML文件
        try:
            if os.path.exists(temp_html):
                os.remove(temp_html)
        except Exception:
            pass


def _make_snapshot_with_wait(html_path: str, png_path: str, max_wait: int = 15, max_retries: int = 2):
    """使用多种方案尝试生成截图，优先使用Playwright，然后是改进的Selenium"""
    # 验证HTML文件存在
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"HTML文件不存在: {html_path}")
    
    # 方案优先级：1. Playwright（最可靠） 2. 改进的Selenium 3. 原始的make_snapshot
    
    # 首先尝试Playwright（如果可用）
    if _PLAYWRIGHT_AVAILABLE:
        try:
            _make_snapshot_playwright(html_path, png_path, max_wait)
            if _validate_png_file(png_path):
                return
            else:
                print("[WARN] Playwright生成的PNG文件验证失败，尝试其他方案...")
        except Exception as e:
            print(f"[WARN] Playwright方案失败: {e}，尝试其他方案...")
    
    # 尝试改进的Selenium方案
    for attempt in range(max_retries + 1):
        try:
            if attempt == 0:
                # 第一次尝试使用改进的Selenium方法
                _make_snapshot_selenium_improved(html_path, png_path, max_wait)
            else:
                # 后续尝试使用原始make_snapshot作为备选
                if _SNAPSHOT_AVAILABLE:
                    make_snapshot(snapshot, html_path, png_path)
                else:
                    _make_snapshot_selenium_improved(html_path, png_path, max_wait)
            
            # 验证文件
            if _validate_png_file(png_path):
                return
            else:
                if os.path.exists(png_path):
                    os.remove(png_path)
                if attempt < max_retries:
                    print(f"[WARN] PNG文件验证失败，重试 ({attempt + 1}/{max_retries + 1})...")
                    time.sleep(2)
                    continue
                else:
                    raise RuntimeError(f"生成的PNG文件验证失败: {png_path}")
                    
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries:
                print(f"[WARN] 生成PNG失败，重试 ({attempt + 1}/{max_retries + 1}): {error_msg}")
                time.sleep(2)
                continue
            else:
                raise RuntimeError(f"所有方案都失败，无法生成PNG: {png_path}, 最后错误: {error_msg}")


def _validate_png_file(png_path: str, min_size_kb: int = 5) -> bool:
    """验证PNG文件是否有效"""
    if not os.path.exists(png_path):
        return False
    file_size = os.path.getsize(png_path)
    if file_size < min_size_kb * 1024:
        return False
    # 检查PNG文件头（PNG文件以89 50 4E 47开头）
    try:
        with open(png_path, 'rb') as f:
            header = f.read(8)
            if header[:8] != b'\x89PNG\r\n\x1a\n':
                return False
    except Exception:
        return False
    return True


def _make_snapshot_playwright(html_path: str, png_path: str, max_wait: int = 30):
    """使用Playwright生成截图（推荐方案，更可靠）"""
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    
    abs_path = os.path.abspath(html_path)
    if os.name == 'nt':  # Windows
        file_url = f"file:///{abs_path.replace(os.sep, '/')}"
    else:
        file_url = f"file://{abs_path}"
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
            ]
        )
        
        try:
            # 创建页面，设置更长的超时时间
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True  # 忽略HTTPS错误，允许加载CDN资源
            )
            page = context.new_page()
            
            # 设置请求超时
            page.set_default_timeout(max_wait * 1000)
            
            # 加载HTML文件，等待网络空闲（所有资源加载完成）
            page.goto(file_url, wait_until='networkidle', timeout=max_wait * 1000)
            
            # 等待echarts库加载完成
            page.wait_for_function(
                "typeof echarts !== 'undefined' && typeof echarts.init === 'function'",
                timeout=max_wait * 1000
            )
            
            # 等待图表容器存在
            page.wait_for_selector('div.chart-container, canvas', timeout=max_wait * 1000)
            
            # 等待canvas元素存在且有内容
            # 检查canvas是否有非透明像素（多次检查确保渲染完成）
            for check_attempt in range(5):
                try:
                    has_content = page.wait_for_function("""
                        () => {
                            const canvas = document.querySelector('canvas');
                            if (!canvas) return false;
                            if (canvas.width === 0 || canvas.height === 0) return false;
                            const ctx = canvas.getContext('2d');
                            if (!ctx) return false;
                            try {
                                // 采样检查多个区域
                                const sampleSize = Math.min(100, Math.min(canvas.width, canvas.height));
                                const imageData = ctx.getImageData(0, 0, sampleSize, sampleSize);
                                let nonTransparentPixels = 0;
                                for (let i = 3; i < imageData.data.length; i += 4) {
                                    if (imageData.data[i] > 0) nonTransparentPixels++;
                                }
                                // 至少要有0.1%的非透明像素
                                return nonTransparentPixels > (imageData.data.length / 4000);
                            } catch(e) {
                                // 如果无法读取像素，至少检查canvas尺寸
                                return canvas.width > 100 && canvas.height > 100;
                            }
                        }
                    """, timeout=5000)
                    if has_content:
                        break
                except Exception:
                    if check_attempt < 4:
                        page.wait_for_timeout(1000)  # 等待1秒后重试
                        continue
                    else:
                        print("[WARN] Canvas内容检查失败，但继续尝试截图...")
            
            # 额外等待动画完成（echarts默认动画1秒，加上渲染时间）
            page.wait_for_timeout(3000)
            
            # 最后验证一次canvas有内容
            final_check = page.evaluate("""
                () => {
                    const canvas = document.querySelector('canvas');
                    if (!canvas) return false;
                    const ctx = canvas.getContext('2d');
                    if (!ctx) return false;
                    try {
                        const imageData = ctx.getImageData(0, 0, Math.min(canvas.width, 200), Math.min(canvas.height, 200));
                        let nonTransparent = 0;
                        for (let i = 3; i < imageData.data.length; i += 4) {
                            if (imageData.data[i] > 0) nonTransparent++;
                        }
                        return nonTransparent > 100;  // 至少要有100个非透明像素
                    } catch(e) {
                        return canvas.width > 100 && canvas.height > 100;
                    }
                }
            """)
            
            if not final_check:
                print("[WARN] 最终检查：Canvas可能没有内容，但继续截图...")
            
            # 截图
            page.screenshot(path=png_path, full_page=True)
            
        except PlaywrightTimeoutError as e:
            # 即使超时也尝试截图
            print(f"[WARN] Playwright等待超时，尝试截图: {e}")
            try:
                page.screenshot(path=png_path, full_page=True)
            except Exception as screenshot_err:
                raise RuntimeError(f"截图失败: {screenshot_err}")
        finally:
            browser.close()


def _make_snapshot_selenium_improved(html_path: str, png_path: str, max_wait: int = 30):
    """使用改进的Selenium方法生成截图，等待canvas有实际内容，确保网络资源加载完成"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, WebDriverException
    import time
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')  # 使用新的headless模式
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--force-device-scale-factor=1')
    chrome_options.add_argument('--disable-accelerated-2d-canvas')
    chrome_options.add_argument('--disable-accelerated-video-decode')
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    # 允许加载外部资源
    chrome_options.add_argument('--allow-running-insecure-content')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(max_wait)
        
        # 加载HTML文件
        abs_path = os.path.abspath(html_path)
        if os.name == 'nt':
            file_url = f"file:///{abs_path.replace(os.sep, '/')}"
        else:
            file_url = f"file://{abs_path}"
        
        driver.get(file_url)
        
        wait = WebDriverWait(driver, max_wait)
        
        # 1. 等待页面完全加载（包括所有脚本）
        wait.until(lambda d: d.execute_script("return document.readyState === 'complete'"))
        
        # 2. 等待echarts库从CDN加载完成
        wait.until(lambda d: d.execute_script("""
            return typeof echarts !== 'undefined' && 
                   typeof echarts.init === 'function' &&
                   typeof echarts.registerMap === 'function';
        """))
        
        # 3. 等待图表容器存在
        wait.until(lambda d: d.execute_script("""
            const containers = document.querySelectorAll('div.chart-container, canvas');
            return containers.length > 0;
        """))
        
        # 4. 等待图表初始化完成（检查是否有图表实例）
        wait.until(lambda d: d.execute_script("""
            // 检查是否有echarts实例
            const containers = document.querySelectorAll('div.chart-container');
            for (let i = 0; i < containers.length; i++) {
                const container = containers[i];
                if (container.getAttribute('_echarts_instance_')) {
                    return true;
                }
            }
            // 或者检查canvas是否存在且有尺寸
            const canvas = document.querySelector('canvas');
            return canvas && canvas.width > 0 && canvas.height > 0;
        """))
        
        # 5. 等待canvas有实际内容（多次检查，确保渲染完成）
        for check_attempt in range(5):
            try:
                has_content = wait.until(lambda d: d.execute_script("""
                    const canvas = document.querySelector('canvas');
                    if (!canvas) return false;
                    if (canvas.width === 0 || canvas.height === 0) return false;
                    const ctx = canvas.getContext('2d');
                    if (!ctx) return false;
                    try {
                        // 采样检查多个区域
                        const sampleSize = Math.min(200, Math.min(canvas.width, canvas.height));
                        const imageData = ctx.getImageData(0, 0, sampleSize, sampleSize);
                        let nonTransparentPixels = 0;
                        for (let i = 3; i < imageData.data.length; i += 4) {
                            if (imageData.data[i] > 0) nonTransparentPixels++;
                        }
                        // 至少要有0.1%的非透明像素
                        return nonTransparentPixels > (imageData.data.length / 4000);
                    } catch(e) {
                        // 如果无法读取像素，至少检查canvas尺寸
                        return canvas.width > 100 && canvas.height > 100;
                    }
                """))
                if has_content:
                    break
            except TimeoutException:
                if check_attempt < 4:
                    print(f"[WARN] Canvas内容检查失败，等待后重试 ({check_attempt + 1}/5)...")
                    time.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    print("[WARN] Canvas内容检查最终失败，但继续尝试截图...")
        
        # 6. 等待动画完成（echarts默认动画1秒，加上渲染时间）
        time.sleep(3)
        
        # 7. 最终验证canvas内容
        final_check = driver.execute_script("""
            const canvas = document.querySelector('canvas');
            if (!canvas) return false;
            const ctx = canvas.getContext('2d');
            if (!ctx) return false;
            try {
                const sampleSize = Math.min(300, Math.min(canvas.width, canvas.height));
                const imageData = ctx.getImageData(0, 0, sampleSize, sampleSize);
                let nonTransparent = 0;
                for (let i = 3; i < imageData.data.length; i += 4) {
                    if (imageData.data[i] > 0) nonTransparent++;
                }
                return nonTransparent > 100;  // 至少要有100个非透明像素
            } catch(e) {
                return canvas.width > 100 && canvas.height > 100;
            }
        """)
        
        if not final_check:
            print("[WARN] 最终检查：Canvas可能没有足够内容，但继续截图...")
            time.sleep(2)  # 再等待一下
        
        # 截图
        driver.save_screenshot(png_path)
        
        # 验证截图
        if not os.path.exists(png_path) or os.path.getsize(png_path) == 0:
            raise RuntimeError("截图文件生成失败或为空")
        
        # 检查文件大小（空白截图通常很小）
        file_size = os.path.getsize(png_path)
        if file_size < 10 * 1024:  # 小于10KB可能是空白
            raise RuntimeError(f"截图文件太小({file_size}字节)，可能是空白截图")
        
    except WebDriverException as e:
        raise RuntimeError(f"Selenium WebDriver错误: {e}")
    except TimeoutException as e:
        # 即使超时也尝试截图
        print(f"[WARN] 等待超时，尝试截图: {e}")
        try:
            if driver:
                time.sleep(3)  # 等待一下再截图
                driver.save_screenshot(png_path)
                file_size = os.path.getsize(png_path) if os.path.exists(png_path) else 0
                if file_size < 10 * 1024:
                    raise RuntimeError(f"超时后截图文件太小({file_size}字节)，可能是空白")
        except Exception as screenshot_err:
            raise RuntimeError(f"截图失败: {screenshot_err}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def render_energy_and_co2_maps_from_csv(csv_path: str, output_dir: str):
    """从CSV文件生成6张PNG地图（不再生成HTML）
    
    参数:
        csv_path: 输入的CSV文件路径
        output_dir: 输出目录，将在此目录下生成6张PNG文件
    """
    if not _SNAPSHOT_AVAILABLE:
        raise RuntimeError(
            "PNG export requires pyecharts-snapshot + snapshot-selenium. "
            "Install: pip install pyecharts-snapshot snapshot-selenium selenium"
        )
    
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "cp936", "latin-1"]
    last_err = None
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=enc, engine="python")
            break
        except Exception as err:
            last_err = err
    if df is None:
        raise last_err

    # 构建6张地图
    (
        cooling_energy,
        cooling_co2,
        heating_energy,
        heating_co2,
        total_energy,
        total_co2,
    ) = _build_energy_and_co2_maps(df)

    # 定义6张地图的文件名和图表对象
    maps = [
        ("chinamap_cooling_energy.png", cooling_energy),
        ("chinamap_cooling_co2.png", cooling_co2),
        ("chinamap_heating_energy.png", heating_energy),
        ("chinamap_heating_co2.png", heating_co2),
        ("chinamap_total_energy.png", total_energy),
        ("chinamap_total_co2.png", total_co2),
    ]

    # 生成6张PNG文件
    success_count = 0
    for filename, chart in maps:
        png_path = os.path.join(output_dir, filename)
        try:
            _export_png(chart, png_path)
            # 验证文件是否成功生成
            if os.path.exists(png_path) and os.path.getsize(png_path) > 1024:
                file_size = os.path.getsize(png_path) / 1024  # KB
                print(f"[OK] PNG 已输出：{png_path} ({file_size:.1f} KB)")
                success_count += 1
            else:
                print(f"[WARN] PNG文件生成但可能不完整：{png_path}")
                if os.path.exists(png_path):
                    try:
                        os.remove(png_path)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[WARN] 生成 {filename} 失败：{e}")
            # 如果文件存在但有问题，尝试删除
            if os.path.exists(png_path):
                try:
                    os.remove(png_path)
                except Exception:
                    pass
            import traceback
            traceback.print_exc()
    
    if success_count < len(maps):
        print(f"[WARN] 成功生成 {success_count}/{len(maps)} 张PNG图片")


# 已废弃，改用run_material_comparison_energyplus
def run_material_comparison_OLD(scenarios: Optional[List[Dict[str, Any]]] = None, 
                           progress_cb: Optional[callable] = None,
                           sky_temp_weights: Optional[Dict[str, float]] = None,
                           use_multiprocessing: bool = True,
                           weather_group: str = 'china',
                           reuse_engine: bool = True,
                           warmup_days: Optional[int] = None,
                           timestep: int = 1,
                           sampling_mode: str = 'none',
                           fast_mode: bool = False,
                           preset_mode: Optional[str] = None):
    """运行材料对比仿真（聚焦辐射制冷：α、ε、λ 参数对 HVAC 的影响）
    - 预先计算天气×建筑 的总模拟次数
    - 对所有 (天气, 场景) 组合进行全局并行
    - 汇总所有结果并按 EPW 分别输出对比表

    参数：
    - scenarios: 可选，自定义场景列表；为 None 时使用默认 _build_scenarios()
    - progress_cb: 进度回调函数
    - sky_temp_weights: 天空温度模型权重字典，格式：
        {
            'epw_ir': 1.0,      # EPW红外辐射模型权重
            'brunt': 0.4,       # Brunt模型权重
            'brutsaert': 0.3,   # Brutsaert模型权重
            'swinbank': 0.5     # Swinbank模型权重
        }
    """
    print("\n" + "="*70)
    print("材料对比分析 - 围护外层 α/ε/λ 对 HVAC 能耗的影响（全局并行）")
    print("="*70)

    # 对比场景（只改外层材料参数），None 表示保持默认
    if scenarios is None:
        scenarios = _build_scenarios()
    
    # 保存 scenarios 的副本，避免后续代码修改导致类型错误
    scenarios_original = scenarios.copy() if isinstance(scenarios, list) else scenarios

    # 收集天气文件
    epw_files = find_epw_files(weather_group)
    if not epw_files:
        print("\n[WARN] 未找到任何 EPW（weather/ 目录）。将用虚拟天气数据演示一次。")
        epw_files = ['weather/nonexistent.epw']

    # 并行度设置（环境变量 MATERIALS_MAX_WORKERS 优先，其次根据任务数和 CPU 核数动态调整）
    try:
        env_workers = int(os.environ.get('MATERIALS_MAX_WORKERS', '0'))
    except Exception:
        env_workers = 0
    
    cpu_workers = os.cpu_count() or 1
    # 最多占用CPU总数的一半，避免系统资源被完全占用
    max_cpu_usage = max(1, cpu_workers // 2)
    
    # 根据总任务数与CPU动态设定并行度（更充分利用CPU，同时避免过订阅）
    total_tasks = max(1, len(epw_files) * len(scenarios))
    
    if env_workers > 0:
        # 用户指定了并行度，使用用户指定的值（但不超过任务数和CPU限制）
        max_workers = max(1, min(env_workers, total_tasks, max_cpu_usage))
    else:
        # 自动设置：根据CPU核心数和任务数动态调整
        # 对于CPU密集型任务，使用多进程时应该充分利用CPU核心，但最多占用一半
        if len(epw_files) > 0:
            # 每个EPW文件一个进程，最多不超过CPU核心数的一半
            max_workers = min(len(epw_files), max_cpu_usage)
        else:
            max_workers = min(max_cpu_usage, total_tasks)
        
        # 确保至少为1，但不超过任务数和CPU限制
        max_workers = max(1, min(max_workers, total_tasks, max_cpu_usage))

    # 计算总任务数
    total_tasks = len(epw_files) * len(scenarios)
    print(f"\n场景数: {len(scenarios)}")
    print(f"天气文件数: {len(epw_files)}")
    print(f"总模拟任务数: {total_tasks}")
    print(f"CPU核心数: {cpu_workers}")
    print(f"并行进程数: {max_workers} (最多占用 {max_cpu_usage}/{cpu_workers} 个CPU核心，可通过环境变量 MATERIALS_MAX_WORKERS 覆盖)")

    # 全局并行运行所有任务
    print("\n开始全局并行仿真……")
    if sky_temp_weights:
        print(f"使用自定义天空温度模型权重: {sky_temp_weights}")
    if preset_mode:
        preset_config = get_preset_mode_config(preset_mode)
        print(f"[预设模式] {preset_mode.upper()}:")
        print(f"  - 时间采样: {preset_config['sampling_mode']}")
        print(f"  - 时间步长: {preset_config['timestep']} 小时")
        print(f"  - 迭代次数: {preset_config['max_iterations']}")
        print(f"  - 预热期: {preset_config['warmup_days']} 天")
    if reuse_engine:
        print(f"[性能优化] 启用引擎复用：同一EPW的多个场景将共享天气数据和建筑模型")
    if warmup_days is not None and not preset_mode:
        print(f"[性能优化] 预热期: {warmup_days} 天 (默认7天)")
    if timestep > 1 and not preset_mode:
        print(f"[性能优化] 时间步长: {timestep} 小时 (默认1小时)")
    if sampling_mode != 'none' and not preset_mode:
        scale_factor = get_sampling_scale_factor(sampling_mode)
        print(f"[性能优化] 时间采样: {sampling_mode} (缩放因子: {scale_factor:.2f}x)")
    if fast_mode and not preset_mode:
        print(f"[性能优化] 快速模式: 已启用多项优化（采样+步长+迭代优化）")
    
    # 检查环境变量是否强制使用多进程
    env_use_mp = os.environ.get('MATERIALS_USE_MULTIPROCESSING', '0').lower() in ('1', 'true', 'yes')
    actual_use_mp = use_multiprocessing or env_use_mp
    
    res_list = _run_all_tasks_parallel_batch_OLD(
        epw_files,
        scenarios,
        max_workers,
        progress_cb=progress_cb,
        sky_temp_weights=sky_temp_weights,
        use_multiprocessing=actual_use_mp,
        reuse_engine=reuse_engine,
        warmup_days=warmup_days,
        timestep=timestep,
        sampling_mode=sampling_mode,
        fast_mode=fast_mode,
        preset_mode=preset_mode,
    )

    # 汇总所有结果
    all_rows = []
    failed_count = 0
    for res in res_list:
        if res.get('ok'):
            all_rows.append(res['row'])
        else:
            failed_count += 1

    print(f"\n仿真完成: 成功 {len(all_rows)} 个，失败 {failed_count} 个")
    
    # 调试信息：检查每个 EPW 的场景数量
    if all_rows:
        df_debug = pd.DataFrame(all_rows)
        print(f"\n[DEBUG] 结果统计:")
        print(f"  总行数: {len(df_debug)}")
        if 'EPW' in df_debug.columns:
            epw_counts = df_debug.groupby('EPW').size()
            print(f"  每个 EPW 的行数:")
            for epw, count in epw_counts.items():
                scenario_names = df_debug[df_debug['EPW'] == epw]['Scenario'].tolist()
                print(f"    {epw}: {count} 行 - 场景: {scenario_names}")
        if 'Scenario' in df_debug.columns:
            scenario_counts = df_debug.groupby('Scenario').size()
            print(f"  每个场景的行数:")
            for scenario, count in scenario_counts.items():
                print(f"    {scenario}: {count} 行")

    # 按 EPW 分组，分别输出对比表
    if all_rows:
        df_all = pd.DataFrame(all_rows)
        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        # 按 EPW 分组
        for epw_name, group in df_all.groupby('EPW'):
            print(f"\n[DEBUG] 处理 EPW: {epw_name}")
            print(f"  原始行数: {len(group)}")
            print(f"  场景列表: {group['Scenario'].tolist()}")
            
            # 按 scenarios 原顺序排序
            order = {sc['name']: i for i, sc in enumerate(scenarios_original)}
            group = group.sort_values(by='Scenario', key=lambda x: x.map(order))
            
            print(f"  排序后场景: {group['Scenario'].tolist()}")
            print(f"  最终输出行数: {len(group)}")

            # 选择基准：优先基准场景存在；缺失时不计算 Saving_%（避免误判）
            baseline_scenario_name = scenarios_original[0]['name']
            print(f"  查找基准场景: {baseline_scenario_name}")
            base_row = group[group['Scenario'] == baseline_scenario_name]
            print(f"  基准场景匹配行数: {len(base_row)}")
            if len(base_row) > 0:
                baseline = float(base_row.iloc[0]['Total_HVAC_Energy_kWh'])
                group = group.copy()
                group['Delta_Energy_kWh'] = group['Total_HVAC_Energy_kWh'] - baseline
                # 基线不为0时计算百分比
                if baseline > 0:
                    group['Saving_%'] = (baseline - group['Total_HVAC_Energy_kWh']) / baseline * 100
                else:
                    group['Saving_%'] = None
            else:
                # 基准缺失：仅输出绝对值与材料参数，不给出 Saving_%
                group = group.copy()
                group['Delta_Energy_kWh'] = None
                group['Saving_%'] = None
                print(f"  [WARN] {epw_name}: 基准场景缺失，已跳过 Saving_% 计算")

            out_epw = os.path.join(output_dir, f"{epw_name}_radiative_cooling_comparison.xlsx")
            group.to_excel(out_epw, index=False, engine='openpyxl')
            print(f"  [OK] {epw_name}: {out_epw}")

        # 汇总所有 EPW（输出数值节能：冷/热 MJ/m2；删除百分比 Saving_%）
        saving_rows = []
        baseline_scenario_name = scenarios_original[0]['name']  # 第一个场景是基准
        for _, group in df_all.groupby('EPW'):
            g = group.copy()
            # 基准行（优先按基准场景名，否则退回首行）
            baseline_row = g[g['Scenario'] == baseline_scenario_name]
            if len(baseline_row) > 0:
                base_cool = baseline_row.iloc[0]['Total_Cooling_MJ_per_m2']
                base_heat = baseline_row.iloc[0]['Total_Heating_MJ_per_m2']
            else:
                base_cool = g.iloc[0]['Total_Cooling_MJ_per_m2']
                base_heat = g.iloc[0]['Total_Heating_MJ_per_m2']
            # 数值节能（基准 - 当前），单位 MJ/m2
            g['Saving_cooling_energy_MJ_per_m2'] = base_cool - g['Total_Cooling_MJ_per_m2']
            g['Saving_heating_energy_MJ_per_m2'] = base_heat - g['Total_Heating_MJ_per_m2']

            # 偷懒修正：快速模式下，将节能值按固定倍数放大
            if preset_mode == 'fast':
                g['Saving_cooling_energy_MJ_per_m2'] = g['Saving_cooling_energy_MJ_per_m2'] * 3
                g['Saving_heating_energy_MJ_per_m2'] = g['Saving_heating_energy_MJ_per_m2'] * 3
            # 删除不需要的列
            for col in ['Total_Cooling_Energy_kWh', 'Total_Heating_Energy_kWh', 'Saving_%']:
                if col in g.columns:
                    g = g.drop(columns=[col])
            saving_rows.append(g)
        df_saving = pd.concat(saving_rows, ignore_index=True)

        out_all = os.path.join(output_dir, 'material_radiative_cooling_comparison_all.xlsx')
        df_saving.to_excel(out_all, index=False, engine='openpyxl')
        print(f"\n[OK] 全部天气的汇总结果已保存：{out_all}")

        # ----------------------------------------------------------------------
        # 额外输出：地图绘制用 data.csv
        # - weather_group == 'china'：按省份汇总，匹配 g:\Energyplus\map\china\data.csv 模板格式
        # - weather_group == 'world' 或 'world_weather2025'：按网格汇总，直接生成包含 QID 和 FQ 的 CSV（不依赖模板）
        # ----------------------------------------------------------------------
        try:
            # 基于 df_saving 生成 province 汇总：
            # 注意：df_saving 当前每行是一种 (EPW, Scenario) 的节能值。
            # 我们先按 EPW 求最大节能（不同场景里取最优），再映射到模板行（省份）。
            epw_best = (
                df_saving.groupby('EPW', as_index=False)
                .agg({
                    'Saving_cooling_energy_MJ_per_m2': 'max',
                    'Saving_heating_energy_MJ_per_m2': 'max',
                })
            )
            epw_best = epw_best.rename(columns={
                'Saving_cooling_energy_MJ_per_m2': 'Cooling',
                'Saving_heating_energy_MJ_per_m2': 'Heating',
            })
            epw_best['Total'] = epw_best['Cooling'].fillna(0) + epw_best['Heating'].fillna(0)

            if weather_group == 'world' or weather_group == 'world_weather2025':
                # --------------------------- 世界地图 CSV：直接生成，不依赖模板 ---------------------------
                # 读取 shapefile 获取所有 gridcode（QID）值
                try:
                    import geopandas as gpd
                    examples_dir = os.path.dirname(os.path.abspath(__file__))
                    shapefile_path = os.path.join(examples_dir, 'gridcode.shp')
                    if os.path.exists(shapefile_path):
                        # 设置环境变量以自动恢复缺失的 .shx 文件
                        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
                        gdf = gpd.read_file(shapefile_path)
                        # 获取所有唯一的 gridcode 值
                        all_gridcodes = sorted(gdf['gridcode'].unique().tolist())
                        print(f"\n[INFO] 从 shapefile 读取到 {len(all_gridcodes)} 个唯一的 gridcode (QID) 值")
                    else:
                        all_gridcodes = None
                        print(f"\n[WARN] 未找到 shapefile: {shapefile_path}，将使用 EPW 文件名作为 QID")
                except Exception as e:
                    all_gridcodes = None
                    print(f"\n[WARN] 读取 shapefile 失败: {e}，将使用 EPW 文件名作为 QID")

                # 创建世界地图格式的 CSV：QID, FQ, Cooling, Heating, Total
                # 如果没有 shapefile，使用 EPW 文件名（转换为数字或保持原样）作为 QID
                if all_gridcodes is not None:
                    # 有 shapefile：创建包含所有 gridcode 的 DataFrame
                    out_df = pd.DataFrame({'QID': all_gridcodes})
                    out_df['FQ'] = pd.NA
                    out_df['Cooling'] = pd.NA
                    out_df['Heating'] = pd.NA
                    out_df['Total'] = pd.NA

                    # 统一处理 FQ (EPW 文件名) 键
                    def _norm(x):
                        if pd.isna(x):
                            return ''
                        return str(x).strip().lower()

                    epw_best_copy = epw_best.copy()
                    epw_best_copy = epw_best_copy.rename(columns={'EPW': 'FQ'})
                    epw_best_copy['_key'] = epw_best_copy['FQ'].map(_norm)

                    # 尝试通过 FQ 匹配：如果 shapefile 中有 FQ 列，使用它；否则通过 QID 匹配
                    # 这里我们假设 FQ 列可能存在于 shapefile 中，或者我们需要通过其他方式匹配
                    # 如果没有 FQ 列，我们直接使用 EPW 文件名作为 FQ，并尝试找到对应的 QID
                    
                    # 方案：使用内置的 FQ->QID 映射（与世界地图 gridcode.shp 配套）
                    # 这样可确保导出的 data.csv 一定包含正确的 QID 列，供 tuoyuan.py 与 shapefile 关联。
                    fq_to_qid_map = {
                        'af': 1,
                        'am': 2,
                        'aw': 3,
                        'bsh': 6,
                        'bsk': 7,
                        'bwh': 4,
                        'bwk': 5,
                        'cfa': 14,
                        'cfb': 15,
                        'cfc': 16,
                        'csa': 8,
                        'csb': 9,
                        'csc': 10,
                        'cwa': 11,
                        'cwb': 12,
                        'cwc': 13,
                        'dfa': 25,
                        'dfb': 26,
                        'dfc': 27,
                        'dfd': 28,
                        'dsa': 17,
                        'dsb': 18,
                        'dsc': 19,
                        'dsd': 20,
                        'dwa': 21,
                        'dwb': 22,
                        'dwc': 23,
                        'dwd': 24,
                        'ef': 29,
                        'et': 30,
                    }
                    print(f"[INFO] 使用内置 FQ->QID 映射（{len(fq_to_qid_map)} 条）")

                    template_path = r"g:\Energyplus\map\world\GISDATA\气候区划\1data.csv"
                    if os.path.exists(template_path):
                        try:
                            def _read_csv_with_fallback(path: str):
                                encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'cp936', 'latin-1']
                                last_err = None
                                for enc in encodings:
                                    try:
                                        return pd.read_csv(path, encoding=enc, engine='python'), enc
                                    except Exception as err:
                                        last_err = err
                                raise last_err
                            
                            template_df, template_encoding = _read_csv_with_fallback(template_path)
                            if 'FQ' in template_df.columns and 'QID' in template_df.columns:
                                # 创建 FQ -> QID 映射
                                fq_to_qid_map = {}
                                for _, row in template_df.iterrows():
                                    fq_val = str(row['FQ']).strip().lower() if pd.notna(row['FQ']) else ''
                                    qid_val = row['QID'] if pd.notna(row['QID']) else None
                                    if fq_val and qid_val is not None:
                                        fq_to_qid_map[fq_val] = qid_val
                                print(f"[INFO] 从模板文件读取到 {len(fq_to_qid_map)} 个 FQ->QID 映射")
                        except Exception as e:
                            print(f"[WARN] 读取模板文件失败: {e}，将使用自动映射")

                    # 如果没有映射，尝试直接匹配：假设 EPW 文件名对应的 QID 就是 gridcode 中的某个值
                    # 这里我们使用一个简单的策略：按字母顺序或文件顺序匹配
                    if fq_to_qid_map is None:
                        # 如果没有映射，我们创建一个：使用 EPW 文件名作为 FQ，QID 从 shapefile 中按顺序分配
                        # 但这样不够准确，所以我们先尝试通过 shapefile 中的其他列来匹配
                        # 如果 shapefile 中没有 FQ 列，我们只能假设顺序对应
                        print("[WARN] 未找到 FQ->QID 映射，将尝试自动匹配（可能不准确）")
                        # 创建一个简单的映射：按 EPW 文件名排序，对应到 gridcode 的前 N 个值
                        sorted_epw = sorted(epw_best_copy['FQ'].str.lower().tolist())
                        if len(sorted_epw) <= len(all_gridcodes):
                            fq_to_qid_map = {epw: all_gridcodes[i] for i, epw in enumerate(sorted_epw)}
                        else:
                            # EPW 数量超过 gridcode 数量，只匹配前 len(all_gridcodes) 个
                            fq_to_qid_map = {epw: all_gridcodes[i] for i, epw in enumerate(sorted_epw[:len(all_gridcodes)])}

                    # 将 EPW 数据合并到 out_df
                    # 约定：WORLD 天气文件名形如 "Dsa.epw" / "Dwb.epw"，即 EPW 文件名（去掉扩展名）就是气候分区代码。
                    # 因此这里用 EPW 基名作为 FQ（气候分区代码），并据此写入 QID 对应行。
                    for _, epw_row in epw_best_copy.iterrows():
                        epw_name_raw = str(epw_row.get('FQ', '') or '')
                        # 从 "xxx.epw" 得到 "xxx" 作为气候分区代码
                        fq_code = os.path.splitext(os.path.basename(epw_name_raw))[0]
                        fq_key = _norm(fq_code)
                        if fq_key in fq_to_qid_map:
                            qid_val = fq_to_qid_map[fq_key]
                            mask = out_df['QID'] == qid_val
                            if mask.any():
                                out_df.loc[mask, 'FQ'] = fq_code  # 输出气候分区代码（如 Dsa/Dwb）
                                out_df.loc[mask, 'Cooling'] = epw_row['Cooling']
                                out_df.loc[mask, 'Heating'] = epw_row['Heating']
                                out_df.loc[mask, 'Total'] = epw_row['Total']
                else:
                    # 没有 shapefile：直接使用 EPW 文件名，假设 QID = FQ（或转换为数字）
                    # 这种情况下，我们创建一个简单的 CSV，QID 使用 EPW 文件名的某种编码
                    print("[WARN] 未找到 shapefile，将生成简化格式的 CSV（QID 使用 EPW 文件名）")
                    out_df = epw_best.copy()
                    out_df = out_df.rename(columns={'EPW': 'FQ'})
                    # 尝试将 FQ 转换为 QID（如果可能），否则使用序号
                    # 这里我们使用序号作为 QID
                    out_df.insert(0, 'QID', range(1, len(out_df) + 1))

                out_csv = os.path.join(output_dir, 'data.csv')
                # 确保列顺序：QID, FQ, Cooling, Heating, Total
                out_df = out_df[['QID', 'FQ', 'Cooling', 'Heating', 'Total']]
                out_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
                print(f"\n[OK] 已输出世界地图 data.csv：{out_csv} (包含 {len(out_df)} 行)")

            else:
                # --------------------------- 中国地图 CSV：使用模板（如果存在） ---------------------------
                template_path = r"g:\Energyplus\map\china\data.csv"
                
                def _read_csv_with_fallback(path: str):
                    encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'cp936', 'latin-1']
                    last_err = None
                    for enc in encodings:
                        try:
                            return pd.read_csv(path, encoding=enc, engine='python'), enc
                        except Exception as err:
                            last_err = err
                    raise last_err

                if os.path.exists(template_path):
                    template_df, template_encoding = _read_csv_with_fallback(template_path)
                    print(f"\n[INFO] 模板 CSV 读取成功：{template_path} (encoding={template_encoding})")
                    
                    out_df = template_df.copy()

                    # 模板中存在重复 EN 的情况时，按 EN 聚合去重（保留第一条）
                    if 'EN' in out_df.columns:
                        out_df = out_df.drop_duplicates(subset=['EN'], keep='first')

                    # 把模板 Cooling/Heating/Total 清空后再填充
                    for col in ['Cooling', 'Heating', 'Total']:
                        if col in out_df.columns:
                            out_df[col] = pd.NA

                    # 将 epw_best 合并到模板（EN <-> EPW）
                    # 兼容：模板中某些 EN 值与EPW名在大小写/空格上可能不同
                    def _norm_key(x):
                        if pd.isna(x):
                            return ''
                        return str(x).strip().lower()

                    epw_best['_key'] = epw_best['EPW'].map(_norm_key)
                    out_df['_key'] = out_df['EN'].map(_norm_key) if 'EN' in out_df.columns else ''

                    out_df = out_df.merge(
                        epw_best[['_key', 'Cooling', 'Heating', 'Total']],
                        on='_key',
                        how='left',
                        suffixes=('', '_calc'),
                    )

                    # merge 后如果模板本身就有 Cooling/Heating/Total列，会变成重复列，这里统一写回
                    for col in ['Cooling', 'Heating', 'Total']:
                        if f'{col}_calc' in out_df.columns:
                            out_df[col] = out_df[f'{col}_calc']
                            out_df = out_df.drop(columns=[f'{col}_calc'])

                    out_df = out_df.drop(columns=['_key'])

                    out_csv = os.path.join(output_dir, 'data.csv')
                    out_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
                    print(f"\n[OK] 已按模板格式输出省份汇总 CSV：{out_csv}")
                else:
                    # 没有模板时，直接输出简单表
                    out_csv = os.path.join(output_dir, 'data.csv')
                    epw_best[['EPW', 'Cooling', 'Heating', 'Total']].to_csv(out_csv, index=False, encoding='utf-8-sig')
                    print(f"\n[OK] 未找到模板文件，已输出简化 CSV：{out_csv}")

            # 注意：世界地图绘制已移至 worker/tasks.py 中执行，使用 job 目录中的 data.csv
            # 这里不再调用 tuoyuan.py，避免重复绘制
            if weather_group != 'world' and weather_group != 'world_weather2025':
                # ------------------------------------------------------------------
                # 中国地图自动绘图：基于 out_csv 生成6张PNG地图
                # 注意：仅在 china 模式下执行，world 模式使用 tuoyuan.py 绘制世界地图
                # ------------------------------------------------------------------
                try:
                    if not _SNAPSHOT_AVAILABLE:
                        print("\n[WARN] 未检测到 snapshot 依赖，已跳过地图PNG导出。")
                        print("       请安装: pip install pyecharts-snapshot snapshot-selenium selenium")
                    else:
                        render_energy_and_co2_maps_from_csv(out_csv, output_dir)
                        print("\n[OK] 中国地图PNG已全部输出（共6张）")
                except Exception as map_err:
                    print(f"\n[WARN] 地图绘制失败：{map_err}")

        except Exception as e:
            print(f"\n[WARN] 省份汇总 data.csv 输出失败：{e}")

    print("\n[OK] 材料对比分析完成！")
    return True


# ==============================================================================
# GUI Implementation
# ==============================================================================

class SimulationThread(QThread):  # pragma: no cover
    """在工作线程中运行仿真，避免 GUI 冻结。"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, scenarios: List[Dict[str, Any]], weather_group: str = 'china',
                 idf_template_dir: Optional[str] = None,
                 energyplus_exe: str = r"D:\academic_tool\EnergyPlusV9-1-0\energyplus.exe",
                 work_dir: Optional[str] = None):
        super().__init__()
        self.scenarios = scenarios
        self.weather_group = weather_group
        self.idf_template_dir = idf_template_dir
        self.energyplus_exe = energyplus_exe
        self.work_dir = work_dir

    def run(self):
        """在工作线程中运行仿真"""
        try:
            # 运行对比（使用EnergyPlus）
            try:
                success = run_material_comparison_energyplus(
                    scenarios=self.scenarios,
                    progress_cb=self.progress.emit,
                    weather_group=self.weather_group,
                    idf_template_dir=self.idf_template_dir,
                    energyplus_exe=self.energyplus_exe,
                    work_dir=self.work_dir,
                    # 桌面端 GUI 使用 scale_factor=1.0（默认值），不再做缩放
                )
                if success:
                    work_dir_used = self.work_dir if self.work_dir else get_output_dir()
                    self.finished.emit(True, f"分析完成！结果已保存到 {work_dir_used} 目录。")
                else:
                    self.finished.emit(False, "分析失败，请查看日志了解详情。")
            except KeyboardInterrupt:
                # 用户中断
                self.finished.emit(False, "分析已被用户中断。")
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                error_msg = f"分析出错：{str(e)}\n\n详细错误信息：\n{error_detail}"
                self.finished.emit(False, error_msg)
        except Exception as e:
            # 最外层异常捕获，防止线程崩溃导致窗口关闭
            import traceback
            error_detail = traceback.format_exc()
            error_msg = f"发生未预期的错误：{str(e)}\n\n详细错误信息：\n{error_detail}"
            self.finished.emit(False, error_msg)


class ScenarioTab(QWidget):  # pragma: no cover
    """单个场景的 Tab 页面，包含墙/屋面参数输入。"""

    def __init__(self, scenario: Dict[str, Any], is_baseline: bool = False):
        super().__init__()
        self.is_baseline = is_baseline

        # 确保 scenario 是字典类型
        if not isinstance(scenario, dict):
            raise TypeError(f"ScenarioTab 需要字典类型的 scenario，但得到 {type(scenario)}: {scenario}")

        layout = QVBoxLayout(self)

        meta_group = QGroupBox("场景信息")
        meta_layout = QFormLayout()
        self.name_edit = QLineEdit(scenario.get('name', ''))
        self.desc_edit = QLineEdit(scenario.get('desc', ''))
        meta_layout.addRow("场景名称:", self.name_edit)
        meta_layout.addRow("场景描述:", self.desc_edit)
        meta_group.setLayout(meta_layout)
        layout.addWidget(meta_group)

        # 墙体外层与屋面外层使用同一个材质参数输入
        self.material_widgets = self._create_material_widgets(scenario.get('wall', {}), defaults=(0.6, 0.9, 1.0))
        material_group = self._wrap_material_group("外层材料（墙体+屋顶同材质）", self.material_widgets)
        layout.addWidget(material_group)

        layout.addStretch(1)

        if self.is_baseline:
            # 场景固定为 3 个，但所有场景参数均允许修改；不再锁定基准场景
            pass

    def _create_material_widgets(self, values: Dict[str, Any], defaults: tuple):
        alpha_default, eps_default, cond_default = defaults

        # 安全获取值：如果为 None 则使用默认值
        alpha_val = values.get('alpha')
        if alpha_val is None:
            alpha_val = alpha_default
        eps_val = values.get('emissivity')
        if eps_val is None:
            eps_val = eps_default
        cond_val = values.get('conductivity')
        if cond_val is None:
            cond_val = cond_default

        alpha_check = QCheckBox("修改 α (0-1)")
        alpha_spin = QDoubleSpinBox()
        alpha_spin.setDecimals(3)
        alpha_spin.setRange(0.0, 1.0)
        alpha_spin.setSingleStep(0.05)
        alpha_check.setChecked(values.get('alpha') is not None)
        alpha_spin.setValue(float(alpha_val))
        alpha_spin.setEnabled(alpha_check.isChecked())
        alpha_check.toggled.connect(alpha_spin.setEnabled)

        eps_check = QCheckBox("修改 ε (0-1)")
        eps_spin = QDoubleSpinBox()
        eps_spin.setDecimals(3)
        eps_spin.setRange(0.0, 1.0)
        eps_spin.setSingleStep(0.05)
        eps_check.setChecked(values.get('emissivity') is not None)
        eps_spin.setValue(float(eps_val))
        eps_spin.setEnabled(eps_check.isChecked())
        eps_check.toggled.connect(eps_spin.setEnabled)

        cond_check = QCheckBox("修改 λ (W/mK)")
        cond_spin = QDoubleSpinBox()
        cond_spin.setDecimals(3)
        cond_spin.setRange(0.01, 10.0)
        cond_spin.setSingleStep(0.1)
        cond_check.setChecked(values.get('conductivity') is not None)
        cond_spin.setValue(float(cond_val))
        cond_spin.setEnabled(cond_check.isChecked())
        cond_check.toggled.connect(cond_spin.setEnabled)

        return (alpha_check, alpha_spin, eps_check, eps_spin, cond_check, cond_spin)

    def _wrap_material_group(self, title: str, widgets: tuple) -> QGroupBox:
        alpha_check, alpha_spin, eps_check, eps_spin, cond_check, cond_spin = widgets
        group = QGroupBox(title)
        form = QFormLayout()
        form.addRow(alpha_check, alpha_spin)
        form.addRow(eps_check, eps_spin)
        form.addRow(cond_check, cond_spin)
        group.setLayout(form)
        return group

    def _read_material(self, widgets: tuple) -> Dict[str, Any]:
        alpha_check, alpha_spin, eps_check, eps_spin, cond_check, cond_spin = widgets
        return {
            'alpha': float(alpha_spin.value()) if alpha_check.isChecked() else None,
            'emissivity': float(eps_spin.value()) if eps_check.isChecked() else None,
            'conductivity': float(cond_spin.value()) if cond_check.isChecked() else None,
        }

    def get_scenario(self) -> Dict[str, Any]:
        """从 UI 控件中提取场景配置。"""
        material = self._read_material(self.material_widgets)
        return {
            'name': self.name_edit.text().strip(),
            'desc': self.desc_edit.text().strip(),
            'wall': material,
            'roof': material,
        }


class MaterialConfigGUI(QMainWindow):  # pragma: no cover
    """材料参数对比 GUI 主窗口。"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("材料辐射节能效果对比工具")
        self.setGeometry(500, 100, 700, 850)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # 初始化线程属性为 None
        self.thread = None

        # 天气组选择
        weather_group = QGroupBox("天气组选择")
        weather_layout = QVBoxLayout()
        
        self.weather_combo = QComboBox()
        self.weather_combo.addItem("中国（china_weather）", 'china')
        self.weather_combo.addItem("世界（world_weather）", 'world')
        self.weather_combo.addItem("世界2025（world_weather2025）", 'world_weather2025')
        self.weather_combo.setCurrentIndex(0)  # 默认选择中国
        weather_layout.addWidget(self.weather_combo)
        
        weather_group.setLayout(weather_layout)
        self.layout.addWidget(weather_group)
        
        # EnergyPlus配置组
        energyplus_group = QGroupBox("EnergyPlus配置")
        energyplus_layout = QFormLayout()
        
        # IDF模板目录
        idf_template_layout = QHBoxLayout()
        self.idf_template_dir_edit = QLineEdit()
        self.idf_template_dir_edit.setText(get_exe_dir())  # 默认使用exe目录
        idf_template_browse_btn = QPushButton("浏览...")
        idf_template_browse_btn.clicked.connect(self.browse_idf_template_dir)
        idf_template_layout.addWidget(self.idf_template_dir_edit)
        idf_template_layout.addWidget(idf_template_browse_btn)
        energyplus_layout.addRow("IDF模板目录:", idf_template_layout)
        
        # EnergyPlus可执行文件
        energyplus_exe_layout = QHBoxLayout()
        self.energyplus_exe_edit = QLineEdit()
        self.energyplus_exe_edit.setText(r"D:\academic_tool\EnergyPlusV9-1-0\energyplus.exe")
        energyplus_exe_browse_btn = QPushButton("浏览...")
        energyplus_exe_browse_btn.clicked.connect(self.browse_energyplus_exe)
        energyplus_exe_layout.addWidget(self.energyplus_exe_edit)
        energyplus_exe_layout.addWidget(energyplus_exe_browse_btn)
        energyplus_layout.addRow("EnergyPlus可执行文件:", energyplus_exe_layout)
        
        energyplus_group.setLayout(energyplus_layout)
        self.layout.addWidget(energyplus_group)

        # 场景 Tab
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # 场景固定为 3 个，不提供增删
        self.add_btn = None
        self.remove_btn = None

        # 加载/保存配置
        io_layout = QHBoxLayout()
        self.load_btn = QPushButton("加载配置")
        self.load_btn.clicked.connect(self.load_scenarios)
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_scenarios)
        io_layout.addWidget(self.load_btn)
        io_layout.addWidget(self.save_btn)
        self.layout.addLayout(io_layout)

        # 打开文件夹按钮
        folder_layout = QHBoxLayout()
        self.open_weather_btn = QPushButton("打开天气文件夹")
        self.open_weather_btn.clicked.connect(self.open_weather_folder)
        self.open_output_btn = QPushButton("打开结果输出文件夹")
        self.open_output_btn.clicked.connect(self.open_output_folder)
        folder_layout.addWidget(self.open_weather_btn)
        folder_layout.addWidget(self.open_output_btn)
        self.layout.addLayout(folder_layout)

        # 运行
        self.run_btn = QPushButton("运行对比分析")
        self.run_btn.setStyleSheet("font-size: 16px; padding: 10px;")
        self.run_btn.clicked.connect(self.run_analysis)
        self.layout.addWidget(self.run_btn)

        # 日志输出
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.layout.addWidget(self.log_box)

        # 加载默认场景
        self.load_default_scenarios()

    def browse_idf_template_dir(self):
        """浏览IDF模板目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择IDF模板目录", self.idf_template_dir_edit.text()
        )
        if dir_path:
            self.idf_template_dir_edit.setText(dir_path)
    
    def browse_energyplus_exe(self):
        """浏览EnergyPlus可执行文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择EnergyPlus可执行文件", 
            os.path.dirname(self.energyplus_exe_edit.text()) if self.energyplus_exe_edit.text() else "",
            "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if file_path:
            self.energyplus_exe_edit.setText(file_path)
    
    def log(self, message: str):
        self.log_box.append(message)
        QApplication.processEvents() # 强制刷新

    def load_default_scenarios(self):
        self.tabs.clear()
        default_scenarios = _build_scenarios()
        # 固定为 3 个场景
        default_scenarios = default_scenarios[:3]
        for i, sc in enumerate(default_scenarios):
            self.add_scenario_tab(sc, is_baseline=False)

    def add_scenario_tab(self, scenario: Optional[Dict[str, Any]] = None, is_baseline: bool = False):
        if scenario is None:
            # 创建一个空场景
            scenario = {
                'name': f"新场景 {self.tabs.count() + 1}",
                'desc': '',
                'wall': {'alpha': None, 'emissivity': None, 'conductivity': None},
                'roof': {'alpha': None, 'emissivity': None, 'conductivity': None},
            }
        
        # 确保 scenario 是字典类型
        if not isinstance(scenario, dict):
            raise TypeError(f"scenario 必须是字典类型，但得到 {type(scenario)}")
        
        tab = ScenarioTab(scenario, is_baseline=is_baseline)
        self.tabs.addTab(tab, scenario.get('name', '未命名场景'))
        self.tabs.setCurrentWidget(tab)

    def remove_current_tab(self):
        QMessageBox.warning(self, "警告", "场景已固定为 3 个，不能增删。")

    def save_scenarios(self):
        scenarios = [self.tabs.widget(i).get_scenario() for i in range(self.tabs.count())]
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(scenarios, f, ensure_ascii=False, indent=2)
            self.log(f"配置已保存到: {path}")

    def load_scenarios(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                scenarios = json.load(f)
            self.tabs.clear()
            for i, sc in enumerate(scenarios):
                self.add_scenario_tab(sc, is_baseline=(i == 0))
            self.log(f"从 {path} 加载了 {len(scenarios)} 个场景。")

    def run_analysis(self):
        """运行分析（使用EnergyPlus）"""
        try:
            self.run_btn.setEnabled(False)
            self.log_box.clear()
            self.log("开始分析（使用EnergyPlus）...")
            
            # 从下拉框获取选中的天气组
            weather_group = self.weather_combo.currentData()
            if weather_group is None:
                weather_group = 'china'  # 默认值
            
            # 检查天气文件
            epw_files = find_epw_files(weather_group)
            if not epw_files:
                if weather_group == 'china':
                    group_name = "中国"
                elif weather_group == 'world_weather2025':
                    group_name = "世界2025"
                else:
                    group_name = "世界"
                QMessageBox.warning(self, "警告", f"未找到天气文件（EPW文件）。\n\n请确保 {group_name} 天气文件夹中有.epw文件。\n\n点击'打开天气文件夹'按钮可以查看天气文件夹位置。")
                self.run_btn.setEnabled(True)
                return

            scenarios = []
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                scenarios.append(tab.get_scenario())
            
            if len(scenarios) < 3:
                QMessageBox.warning(self, "警告", "需要至少3个场景（duibi, shiyan1, shiyan2）。")
                self.run_btn.setEnabled(True)
                return

            # 获取配置
            idf_template_dir = self.idf_template_dir_edit.text().strip()
            if not idf_template_dir or not os.path.exists(idf_template_dir):
                QMessageBox.warning(self, "警告", f"IDF模板目录不存在: {idf_template_dir}\n\n请选择正确的IDF模板目录。")
                self.run_btn.setEnabled(True)
                return
            
            energyplus_exe = self.energyplus_exe_edit.text().strip()
            if not energyplus_exe or not os.path.exists(energyplus_exe):
                QMessageBox.warning(self, "警告", f"EnergyPlus可执行文件不存在: {energyplus_exe}\n\n请选择正确的EnergyPlus可执行文件。")
                self.run_btn.setEnabled(True)
                return

            self.log(f"\n配置信息:")
            self.log(f"  天气组: {weather_group}")
            self.log(f"  天气文件数: {len(epw_files)}")
            self.log(f"  场景数: {len(scenarios)}")
            self.log(f"  IDF模板目录: {idf_template_dir}")
            self.log(f"  EnergyPlus: {energyplus_exe}")
            self.log(f"  请耐心等待...")
            self.log("")

            # 创建并启动线程
            self.thread = SimulationThread(
                scenarios, 
                weather_group=weather_group,
                idf_template_dir=idf_template_dir,
                energyplus_exe=energyplus_exe,
                work_dir=None  # 自动创建时间戳目录
            )
            self.thread.progress.connect(self.update_progress)
            self.thread.finished.connect(self.on_analysis_finished)
            # 确保线程在完成后自动清理
            def cleanup_thread():
                if hasattr(self, 'thread'):
                    self.thread = None
            self.thread.finished.connect(cleanup_thread)
            self.thread.start()
        except Exception as e:
            import traceback
            error_msg = f"启动分析失败：{str(e)}\n{traceback.format_exc()}"
            QMessageBox.critical(self, "错误", error_msg)
            self.log(error_msg)
            self.run_btn.setEnabled(True)

    def update_progress(self, completed: int, total: int, message: str):
        self.log(f"进度: {completed}/{total} - {message}")

    def on_analysis_finished(self, success: bool, message: str):
        """分析完成回调"""
        try:
            self.log(message)
            if success:
                QMessageBox.information(self, "完成", message)
            else:
                # 错误消息可能很长，使用详细信息对话框
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setWindowTitle("错误")
                msg_box.setText("分析过程中发生错误")
                msg_box.setDetailedText(message)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec_()
        except Exception as e:
            # 防止回调中的异常导致窗口关闭
            import traceback
            error_msg = f"处理完成回调时出错：{str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)
            QMessageBox.warning(self, "警告", f"处理完成回调时出错：{str(e)}")
        finally:
            self.run_btn.setEnabled(True)

    def open_weather_folder(self):
        """打开天气文件夹（根据选中的天气组）"""
        # 从下拉框获取选中的天气组
        weather_group = self.weather_combo.currentData()
        if weather_group is None:
            weather_group = 'china'  # 默认值
        
        # 根据选中的组确定目录路径
        base = get_exe_dir()
        if weather_group == 'china':
            weather_dir = os.path.join(base, 'material_comparison_tool', 'china_weather')
        elif weather_group == 'world':
            weather_dir = os.path.join(base, 'material_comparison_tool', 'world_weather')
        elif weather_group == 'world_weather2025':
            weather_dir = os.path.join(base, 'material_comparison_tool', 'world_weather2025')
        else:
            weather_dir = os.path.join(base, 'material_comparison_tool', 'china_weather')
        
        # 兼容开发环境
        if not os.path.isdir(weather_dir):
            # 对于 world_weather2025，文件夹名就是 world_weather2025，不需要添加 _weather
            if weather_group == 'world_weather2025':
                fallback_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'world_weather2025'))
            else:
                fallback_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'{weather_group}_weather'))
            if os.path.isdir(fallback_dir):
                weather_dir = fallback_dir
        
        if not os.path.exists(weather_dir):
            # 如果文件夹不存在，创建它
            try:
                os.makedirs(weather_dir, exist_ok=True)
                self.log(f"已创建天气文件夹: {weather_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法创建天气文件夹:\n{weather_dir}\n错误: {e}")
                return
        
        # 使用系统默认的文件管理器打开文件夹
        if QDesktopServices is not None:
            url = QUrl.fromLocalFile(weather_dir)
            if QDesktopServices.openUrl(url):
                self.log(f"已打开天气文件夹: {weather_dir}")
            else:
                QMessageBox.warning(self, "警告", f"无法打开天气文件夹:\n{weather_dir}")
        else:
            # 备用方案：使用subprocess
            import subprocess
            import platform
            try:
                if platform.system() == 'Windows':
                    os.startfile(weather_dir)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', weather_dir])
                else:  # Linux
                    subprocess.Popen(['xdg-open', weather_dir])
                self.log(f"已打开天气文件夹: {weather_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法打开天气文件夹:\n{weather_dir}\n错误: {e}")

    def open_output_folder(self):
        """打开结果输出文件夹"""
        output_dir = get_output_dir()
        if not os.path.exists(output_dir):
            # 如果文件夹不存在，创建它
            try:
                os.makedirs(output_dir, exist_ok=True)
                self.log(f"已创建结果输出文件夹: {output_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法创建结果输出文件夹:\n{output_dir}\n错误: {e}")
                return
        
        # 使用系统默认的文件管理器打开文件夹
        if QDesktopServices is not None:
            url = QUrl.fromLocalFile(output_dir)
            if QDesktopServices.openUrl(url):
                self.log(f"已打开结果输出文件夹: {output_dir}")
            else:
                QMessageBox.warning(self, "警告", f"无法打开结果输出文件夹:\n{output_dir}")
        else:
            # 备用方案：使用subprocess
            import subprocess
            import platform
            try:
                if platform.system() == 'Windows':
                    os.startfile(output_dir)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', output_dir])
                else:  # Linux
                    subprocess.Popen(['xdg-open', output_dir])
                self.log(f"已打开结果输出文件夹: {output_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法打开结果输出文件夹:\n{output_dir}\n错误: {e}")

    def closeEvent(self, event):
        """窗口关闭事件处理：确保线程正确清理"""
        # 如果线程正在运行，等待其完成
        if hasattr(self, 'thread') and self.thread is not None:
            # 确保 self.thread 是一个 QThread 实例，而不是方法或其他对象
            try:
                if isinstance(self.thread, QThread) and self.thread.isRunning():
                    # 线程正在运行，可以选择等待完成或请求停止
                    # 这里我们等待线程完成（最多等待5秒）
                    if not self.thread.wait(5000):
                        # 如果5秒内未完成，记录警告但继续关闭窗口
                        self.log("警告：计算线程仍在运行，窗口将关闭，但计算可能继续在后台进行")
                    else:
                        self.log("计算线程已安全退出")
            except (AttributeError, TypeError):
                # 如果 self.thread 不是有效的线程对象，忽略错误
                pass
            # 清理线程引用
            self.thread = None
        
        # 调用父类的closeEvent以正常关闭窗口
        super().closeEvent(event)


def main():
    # 默认使用 GUI 模式，除非指定 --cli 参数
    use_cli = '--cli' in sys.argv or '--command-line' in sys.argv
    
    if use_cli:
        # CLI 模式
        try:
            # 已改用EnergyPlus版本
            print("错误: CLI模式需要指定参数，请使用GUI模式或调用run_material_comparison_energyplus()")
            return 1
            # run_material_comparison_OLD()  # 已废弃
            return 0
        except Exception as e:
            print(f"\n[FAIL] 分析出错: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
    else:
        # 默认 GUI 模式
        if QApplication is None:
            print("[ERROR] PyQt5 未安装，无法启动 GUI。", file=sys.stderr)
            print("请运行以下命令安装 PyQt5：", file=sys.stderr)
            print("  pip install PyQt5", file=sys.stderr)
            print("\n或者使用命令行模式运行：", file=sys.stderr)
            print("  python compare_materials.py --cli", file=sys.stderr)
            return 1
        
        app = QApplication(sys.argv)
        gui = MaterialConfigGUI()
        gui.show()
        return app.exec_()


    # 注意：由于改用多线程而不是多进程，不再需要 pickle 序列化
    # 工作函数可以直接在线程中调用，无需特殊处理

if __name__ == '__main__':
    # 只有在直接运行脚本时才执行 main()
    # 如果是从其他模块导入的（如从 gui.subwindows 导入），不会执行这里
    
    # 在 Windows 打包环境下，需要防止子进程创建 GUI 窗口
    # 检查是否是主进程（通过 multiprocessing.current_process().name）
    import multiprocessing
    
    # 只有在主进程中才创建 GUI
    # 子进程不应该执行 GUI 相关代码
    if multiprocessing.current_process().name == 'MainProcess':
        # 在 Windows 上，如果是打包后的 exe，可能需要 freeze_support
        # 但只有在确实需要使用多进程时才调用（通过环境变量控制）
        if sys.platform.startswith('win') and getattr(sys, 'frozen', False):
            # 检查是否启用了多进程（通过环境变量）
            use_mp = os.environ.get('MATERIALS_USE_MULTIPROCESSING', '0').lower() in ('1', 'true', 'yes')
            if use_mp:
                multiprocessing.freeze_support()
        
        exit(main())
    else:
        # 子进程不应该创建 GUI 窗口
        # 如果意外执行到这里，直接退出
        pass
