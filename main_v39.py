import os
import sys
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLabel, QFileDialog, QMessageBox, QDialog, 
                              QLineEdit, QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
                              QHeaderView, QFrame, QScrollArea, QGroupBox, QProgressBar,
                              QComboBox, QCheckBox, QGridLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QObject
from PyQt5.QtGui import (QFont, QPalette, QColor, QIcon, QPixmap, QLinearGradient, 
                         QPainter, QBrush, QPen, QCursor, QGuiApplication)
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from scipy.interpolate import interp1d, PchipInterpolator
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import configparser
from itertools import cycle
import webbrowser
import tempfile
import re
import shutil

# 资源路径适配（开发环境 / PyInstaller onefile）
def res_path(*parts):
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.abspath('.')
    return os.path.join(base, *parts)

def external_default_dir():
    run_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath('.')
    return os.path.join(run_dir, 'default')

# 淡雅科研风格配色方案
COLORS = {
    'background': '#F5F7FA',      # 主背景 - 浅灰蓝
    'card': '#FFFFFF',            # 卡片背景 - 白色
    'primary_text': '#2C3E50',    # 主要文字 - 深灰蓝
    'secondary_text': '#7F8C8D',  # 次要文字 - 中灰
    'accent': '#3498DB',          # 强调色 - 淡蓝
    'success': '#27AE60',         # 成功色 - 淡绿
    'warning': '#F39C12',         # 警告色 - 淡橙
    'error': '#E74C3C',           # 错误色 - 淡红
    'border': '#E1E8ED',          # 边框 - 浅灰
    'hover': '#ECF0F1',           # 悬停 - 浅灰
    'light_bg': '#FAFBFC'         # 浅背景
}

# ========== 语言管理器类 ==========
class LanguageManager(QObject):
    """语言管理器，负责管理中英文切换"""
    language_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_language = 'zh'  # 默认中文
        self.translations = {
            'zh': {
                # 主窗口
                'main_title': '辐射制冷/制热计算工具',
                'select_files': '1：先选择所需的文件',
                'select_function': '2：请选择要执行的功能',
                'select_reflectance': '选择反射率文件',
                'select_emissivity': '选择发射率文件',
                'select_atm_transmittance': '选择大气透过率',
                'not_selected': '未选择',
                'energy_map': '节能地图绘制计算',
                'cooling_power': '辐射制冷功率计算',
                'heating_power': '辐射制热功率计算',
                'wind_cloud': '风速与制冷效率云图',
                'modify_params': '参数修改',
                'solar_efficiency': '光热转化效率计算',
                'file_converter': '输入文件处理',
                '语言': 'language',
                
                # 对话框标题
                'calculating': '计算中',
                'calculating_msg': '正在计算，请稍候...',
                'complete': '计算完成',
                'calculation_complete': '计算完成！',
                'calculation_failed': '计算失败！',
                'error': '错误',
                'success': '成功',
                'warning': '警告',
                'info': '提示',
                
                # 文件选择
                'select_file': '选择文件',
                'save_file': '保存文件',
                'file_selected': '已选择文件',
                'file_converted': '文件已转换',
                
                # 按钮文本
                'execute': '执行计算',
                'close': '关闭',
                'cancel': '取消',
                'save': '保存',
                'export': '导出数据',
                'export_csv': '导出数据到CSV',
                'preview': '预览结果图表',
                'plot_curve': '绘制曲线',
                'generate_cloud': '生成云图',
                'start_convert': '开始转换',
                
                # 计算相关
                'cooling_power_result': '冷却功率',
                'heating_power_result': '加热功率',
                'material_emissivity': '材料加权发射率',
                'solar_reflectance': '太阳光谱反射率',
                'visible_reflectance': '可见光谱反射率',
                'solar_absorptance': '太阳吸收率',
                'avg_emissivity': '平均发射率',
                'enable_interpolation': '启用插值',
                
                # 提示信息
                'select_all_files': '请确保已选择所有必要的文件',
                'missing_files': '缺少',
                'input_valid_number': '请输入有效的数值',
                'processing': '正在处理，请稍候...',
                'saved_to': '已保存到',
                'data_saved': '数据已保存',
                
                # Excel转换工具
                'file_processor': '输入文件处理',
                'file_processor_desc': '智能读取CSV、XLSX、TXT文件，自动清理并转换为软件支持的格式',
                'conversion_success': '处理成功！文件已保存为',
                'conversion_failed': '处理失败',
                'select_output_type': '选择输出类型',
                'reflectance_file': '反射率文件',
                'emissivity_file': '发射率文件',
                
                # 天气选项
                'clear': '晴朗',
                'cloudy': '少云',
                'select_atm_file': '请选择大气透过率文件：',
                
                # 风速云图
                'input_solar': '请输入太阳辐照度参数',
                'solar_irradiance': '太阳辐照度',
                
                # 配置编辑器
                'config_editor': '配置文件编辑器',
                'parameter': '参数',
                'value': '值',
                'description': '解释',
                'section_comment': '节注释',
                
                # 版权信息
                'copyright': '辐射制冷/制热计算工具 QQ群：767753318 - 联系作者',

                # 其他 UI 文本
                'map_params_calculation': '地图绘制参数计算',
                'map_plot_contact': '辐射制冷/制热节能地图绘制联系微信cuity_',
                'heating_power_calculation': '辐射制热功率计算',
                'wind_cloud_title': '风速与制冷效率云图',
                'generate_cloud_map': '生成云图',
                'select_file_to_process': '请选择要处理的文件',
                'file_selected_ready_to_process': '文件已选择，点击开始处理',
                'plot_chart': '绘图',
                'export_data': '导出数据',
                'choose_action': '选择操作',
                'preview_chart': '预览结果图表',
                'interactive_plot_title': '光热VS光照',
                'save_results': '保存结果',
                'save_results_file': '保存结果文件',
                'solar_irradiance_prompt': '请输入太阳辐照度 S_solar (单位: W/m²):',
                'emissivity_solar_cloud_title': '大气发射率-太阳光强云图',
            },
            'en': {
                # Main window
                'main_title': 'Radiation Cooling/Heating Calculator',
                'select_files': '1: Select Required Files',
                'select_function': '2: Select Function to Execute',
                'select_reflectance': 'Select Reflectance File',
                'select_emissivity': 'Select Emissivity File',
                'select_atm_transmittance': 'Select Atmospheric Transmittance',
                'not_selected': 'Not Selected',
                'energy_map': 'Energy Map Calculation',
                'cooling_power': 'Radiation Cooling Power',
                'heating_power': 'Radiation Heating Power',
                'wind_cloud': 'Wind Speed & Cooling Efficiency',
                'modify_params': 'Modify Parameters',
                'solar_efficiency': 'Solar-Thermal Efficiency',
                'file_converter': 'File Converter Tool',
                '语言': 'Language',
                
                # Dialog titles
                'calculating': 'Calculating',
                'calculating_msg': 'Calculating, please wait...',
                'complete': 'Complete',
                'calculation_complete': 'Calculation Complete!',
                'calculation_failed': 'Calculation Failed!',
                'error': 'Error',
                'success': 'Success',
                'warning': 'Warning',
                'info': 'Info',
                
                # File selection
                'select_file': 'Select File',
                'save_file': 'Save File',
                'file_selected': 'File Selected',
                'file_converted': 'File Converted',
                
                # Button texts
                'execute': 'Execute',
                'close': 'Close',
                'cancel': 'Cancel',
                'save': 'Save',
                'export': 'Export Data',
                'export_csv': 'Export to CSV',
                'preview': 'Preview Chart',
                'plot_curve': 'Plot Curve',
                'generate_cloud': 'Generate Cloud Map',
                'start_convert': 'Start Conversion',
                
                # Calculation related
                'cooling_power_result': 'Cooling Power',
                'heating_power_result': 'Heating Power',
                'material_emissivity': 'Material Weighted Emissivity',
                'solar_reflectance': 'Solar Spectral Reflectance',
                'visible_reflectance': 'Visible Spectral Reflectance',
                'solar_absorptance': 'Solar Absorptance',
                'avg_emissivity': 'Average Emissivity',
                'enable_interpolation': 'Enable Interpolation',
                
                # Messages
                'select_all_files': 'Please select all required files',
                'missing_files': 'Missing',
                'input_valid_number': 'Please enter a valid number',
                'processing': 'Processing, please wait...',
                'saved_to': 'Saved to',
                'data_saved': 'Data saved',
                
                # File processor
                'file_processor': 'Input File Processor',
                'file_processor_desc': 'Intelligently read CSV, XLSX, TXT files and convert to supported format',
                'conversion_success': 'Processing successful! File saved as',
                'conversion_failed': 'Processing failed',
                'select_output_type': 'Select Output Type',
                'reflectance_file': 'Reflectance File',
                'emissivity_file': 'Emissivity File',
                
                # Weather options
                'clear': 'Clear',
                'cloudy': 'Cloudy',
                'select_atm_file': 'Select atmospheric transmittance file:',
                
                # Wind cloud map
                'input_solar': 'Enter Solar Irradiance Parameter',
                'solar_irradiance': 'Solar Irradiance',
                
                # Config editor
                'config_editor': 'Configuration Editor',
                'parameter': 'Parameter',
                'value': 'Value',
                'description': 'Description',
                'section_comment': 'Section Comment',
                
                # Copyright
                'copyright': 'Radiative Cooling/Heating Calculator QQ Group: 767753318 - Contact Author',

                # Other UI text
                'map_params_calculation': 'Map Plotting Parameter Calculation',
                'map_plot_contact': 'For energy-saving maps of radiative cooling/heating, contact on WeChat: cuity_',
                'heating_power_calculation': 'Radiative Heating Power Calculation',
                'wind_cloud_title': 'Wind Speed & Cooling Efficiency Cloud Map',
                'generate_cloud_map': 'Generate Cloud Map',
                'select_file_to_process': 'Please select a file to process',
                'file_selected_ready_to_process': 'File selected, click to start processing',
                'plot_chart': 'Plot Chart',
                'export_data': 'Export Data',
                'choose_action': 'Choose Action',
                'preview_chart': 'Preview Result Chart',
                'interactive_plot_title': 'Solar-Thermal vs. Irradiance',
                'save_results': 'Save Results',
                'save_results_file': 'Save Results File',
                'solar_irradiance_prompt': 'Enter Solar Irradiance S_solar (in W/m²):',
                'emissivity_solar_cloud_title': 'Atmospheric Emissivity vs. Solar Irradiance Cloud Map'
            }
        }
    
    def set_language(self, language):
        """设置语言"""
        if language in ['zh', 'en']:
            self.current_language = language
            self.language_changed.emit(language)
    
    def get(self, key, default=None):
        """获取翻译文本"""
        return self.translations[self.current_language].get(key, default or key)
    
    def is_chinese(self):
        """检查当前是否为中文"""
        return self.current_language == 'zh'

# 创建全局语言管理器实例
language_manager = LanguageManager()

def safe_read_file(file_path, is_csv=False):
    """
    安全读取文件，自动检测编码并处理编码错误
    
    Args:
        file_path: 文件路径
        is_csv: 是否为CSV文件
    
    Returns:
        numpy array 或 pandas DataFrame
    """
    # 常见的编码列表，按优先级排序
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'ascii', 'latin1']
    
    for encoding in encodings:
        try:
            if is_csv:
                # 对于CSV文件，使用pandas读取
                df = pd.read_csv(file_path, encoding=encoding, sep=None, engine='python')
                return df.to_numpy()
            else:
                # 对于其他文件，先尝试用指定编码打开
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                
                # 将内容写入临时文件，然后用numpy读取
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(content)
                    temp_file_path = temp_file.name
                
                try:
                    data = np.loadtxt(temp_file_path)
                    os.unlink(temp_file_path)  # 删除临时文件
                    return data
                except:
                    os.unlink(temp_file_path)  # 确保删除临时文件
                    continue
                    
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            # 其他错误，继续尝试下一个编码
            continue
    
    # 如果所有编码都失败，尝试用错误忽略模式读取
    try:
        if is_csv:
            df = pd.read_csv(file_path, encoding='utf-8', errors='ignore', sep=None, engine='python')
            return df.to_numpy()
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # 手动解析数据
            data_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith(';'):
                    try:
                        values = [float(x) for x in line.split()]
                        if len(values) >= 2:  # 确保至少有两列数据
                            data_lines.append(values[:2])  # 只取前两列
                    except ValueError:
                        continue
            
            if data_lines:
                return np.array(data_lines)
            else:
                raise Exception("无法从文件中解析出有效数据")
                
    except Exception as e:
        raise Exception(f"无法读取文件 {file_path}: {str(e)}")

def validate_data_file(file_path, min_rows=10):
    """
    验证数据文件的基本格式
    
    Args:
        file_path: 文件路径
        min_rows: 最少行数
    
    Returns:
        bool: 是否有效
    """
    try:
        data = safe_read_file(file_path)
        if data.shape[0] < min_rows:
            return False
        if data.shape[1] < 2:
            return False
        return True
    except:
        return False

def load_config(config_path):
    """加载并解析config.ini文件"""
    config = configparser.ConfigParser()
    try:
        config.read(config_path, encoding='utf-8')
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
        sys.exit(1)
    
    # 验证配置文件的必要部分和选项
    required_sections = ['GENERAL', 'EXPIRATION', 'PHYSICAL_CONSTANTS', 'CALCULATIONS']
    required_keys = {
        'GENERAL': ['DEFAULT_DIRECTORY', 'DECLARE_FILE'],
        'EXPIRATION': ['EXPIRATION_DATE', 'EMAIL_CONTACT'],
        'PHYSICAL_CONSTANTS': ['H', 'C', 'KB'],
        'CALCULATIONS': ['WAVELENGTH_RANGE', 'VISIABLE_RANGE','HC_VALUES', 'T_a1', 'T_filmmin', 'T_filmmax', 'T_filmmins', 'T_filmmaxs', 'S_solar']
    }
    
    for section in required_sections:
        if not config.has_section(section):
            print(f"配置文件缺少部分: [{section}]")
            sys.exit(1)
    
    for section, keys in required_keys.items():
        for key in keys:
            if not config.has_option(section, key):
                print(f"配置文件的 [{section}] 部分缺少选项: {key}")
                sys.exit(1)
    
    # GENERAL
    DEFAULT_DIRECTORY = config.get('GENERAL', 'DEFAULT_DIRECTORY')
    DECLARE_FILE = config.get('GENERAL', 'DECLARE_FILE')
    
    # EXPIRATION
    EXPIRATION_DATE_STR = config.get('EXPIRATION', 'EXPIRATION_DATE')
    EMAIL_CONTACT = config.get('EXPIRATION', 'EMAIL_CONTACT')
    try:
        EXPIRATION_DATE = datetime.datetime.strptime(EXPIRATION_DATE_STR, '%Y-%m-%d')
    except ValueError:
        print(f"配置文件中的 EXPIRATION_DATE 格式错误: {EXPIRATION_DATE_STR}. 应为 YYYY-MM-DD 格式。")
        sys.exit(1)
    
    # PHYSICAL_CONSTANTS
    try:
        H = config.getfloat('PHYSICAL_CONSTANTS', 'H')
        C = config.getfloat('PHYSICAL_CONSTANTS', 'C')
        KB = config.getfloat('PHYSICAL_CONSTANTS', 'KB')
    except ValueError as ve:
        print(f"配置文件中的物理常量格式错误: {ve}")
        sys.exit(1)
    C1 = 2 * H * (C ** 2)
    C2 = (H * C) / KB
    
    # CALCULATIONS
    T_a1 = config.getfloat('CALCULATIONS', 'T_a1')
    T_filmmin = config.getfloat('CALCULATIONS', 'T_filmmin')
    T_filmmax = config.getfloat('CALCULATIONS', 'T_filmmax')
    T_filmmins = config.getfloat('CALCULATIONS', 'T_filmmins')
    T_filmmaxs = config.getfloat('CALCULATIONS', 'T_filmmaxs')
    WAVELENGTH_RANGE_STR = config.get('CALCULATIONS', 'WAVELENGTH_RANGE')
    VISIABLE_RANGE_STR = config.get('CALCULATIONS', 'VISIABLE_RANGE')
    S_solar = config.get('CALCULATIONS', 'S_solar')
    try:
        WAVELENGTH_RANGE = [float(x.strip()) for x in WAVELENGTH_RANGE_STR.split(',')]
        if len(WAVELENGTH_RANGE) != 2:
            raise ValueError("WAVELENGTH_RANGE 应包含两个值: 起始波长和结束波长。")
    except ValueError as ve:
        print(f"配置文件中的 WAVELENGTH_RANGE 格式错误: {ve}")
        sys.exit(1)
    try:
        VISIABLE_RANGE = [float(x.strip()) for x in VISIABLE_RANGE_STR.split(',')]
        if len(VISIABLE_RANGE) != 2:
            raise ValueError("VISIABLE_RANGE 应包含两个值: 起始波长和结束波长。")
    except ValueError as ve:
        print(f"配置文件中的 VISIABLE_RANGE 格式错误: {ve}")
        sys.exit(1)
    
    HC_VALUES_STR = config.get('CALCULATIONS', 'HC_VALUES')
    try:
        HC_VALUES = [float(x.strip()) for x in HC_VALUES_STR.split(',')]
    except ValueError as ve:
        print(f"配置文件中的 HC_VALUES 格式错误: {ve}")
        sys.exit(1)
    
    return {
        'DEFAULT_DIRECTORY': DEFAULT_DIRECTORY,
        'DECLARE_FILE': DECLARE_FILE,
        'EXPIRATION_DATE': EXPIRATION_DATE,
        'EMAIL_CONTACT': EMAIL_CONTACT,
        'H': H,
        'C': C,
        'KB': KB,
        'C1': C1,
        'C2': C2,
        'WAVELENGTH_RANGE': WAVELENGTH_RANGE,
        'VISIABLE_RANGE': VISIABLE_RANGE,
        'HC_VALUES': HC_VALUES,
        'T_a1': T_a1,
        'T_filmmin': T_filmmin,
        'T_filmmax': T_filmmax,
        'T_filmmins': T_filmmins,
        'T_filmmaxs': T_filmmaxs,
        'S_solar': S_solar
    }

def check_expiration(expiration_date, email_contact):
    """检查程序是否过期"""
    current_date = datetime.datetime.now()
    if current_date > expiration_date:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(language_manager.get('warning'))
        # fallback if you don't want to add more keys
        msg.setText(
            'This version has expired. Please update to ensure calculation accuracy.'
            if language_manager.current_language == 'en'
            else '此版本已过期，为了不影响计算精度，请进行版本更新。'
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        url = "https://wwja.lanzoue.com/b0knk1xve"
        webbrowser.open(url)
        sys.exit()
    else:
        if language_manager.current_language == 'en':
            print('Only two test datasets are required: reflectance in visible band and emissivity in atmospheric window')
            print('The software will match wavelengths automatically. Please do NOT include any Chinese/English characters in txt files!')
        else:
            print("仅需要有两个测试数据：涉及可见光波段的反射率和涉及大气窗口的发射率")
            print("软件会自动匹配对应波长，在txt文件中请不要出现任何汉字及英文！")

def load_reflectance(file_path):
    """加载反射率数据"""
    try:
        data = pd.read_csv(file_path, sep=None, engine='python').to_numpy()
        if (data[:,0]>100).any():
            data[:,0] *= 0.001
        if (data[:,1]>2).any():
            data[:,1] *= 0.01
            print('数值缩放成功')
        return data
    except Exception as e:
        raise Exception(f"加载反射率数据时出错: {e}")

def load_spectrum(file_path):
    """加载光谱数据"""
    try:
        return pd.read_excel(file_path).to_numpy()
    except Exception as e:
        raise Exception(f"加载光谱数据时出错: {e}")

def filter_wavelength(data, wavelength_idx, value_idx, wavelength_range):
    """过滤指定波长范围内的数据"""
    wavelengths = data[:, wavelength_idx]
    values = data[:, value_idx]
    valid = (wavelengths >= wavelength_range[0]) & (wavelengths <= wavelength_range[1])
    return wavelengths[valid], values[valid]

def interpolate_spectrum(ref_wavelength, spec_wavelength, spec_values):
    """插值光谱数据以匹配反射率波长点（谨慎策略）
    - 去重、排序
    - 使用PCHIP单调保持插值以避免振铃/过冲
    - 禁止外推：区间外使用边界值（防止偏离趋势）
    """
    # 清理无效值
    mask = np.isfinite(spec_wavelength) & np.isfinite(spec_values)
    x = np.asarray(spec_wavelength)[mask]
    y = np.asarray(spec_values)[mask]
    if x.size < 2:
        raise ValueError("光谱数据点不足，无法插值")
    # 去重并保证严格递增
    x_unique, idx = np.unique(x, return_index=True)
    y_unique = y[idx]
    if x_unique.size < 2:
        raise ValueError("光谱数据唯一波长点不足，无法插值")
    # 构建PCHIP插值器（区间外不外推）
    interp = PchipInterpolator(x_unique, y_unique, extrapolate=False)
    ref_wavelength = np.asarray(ref_wavelength)
    y_new = interp(ref_wavelength)
    # 区间外用边界值填充
    left_mask = ref_wavelength < x_unique[0]
    right_mask = ref_wavelength > x_unique[-1]
    y_new[left_mask] = y_unique[0]
    y_new[right_mask] = y_unique[-1]
    # 防止数值抖动导致的微小负值
    y_new = np.where(y_new < 0, 0.0, y_new)
    return y_new

def interpolate_reflectance(target_wavelength, ref_wavelength, reflectance_values):
    """插值反射率数据以匹配目标波长点"""
    # 去除重复的波长并确保单调递增
    unique_ref_wavelength, unique_indices = np.unique(ref_wavelength, return_index=True)
    unique_reflectance = reflectance_values[unique_indices]
    
    # 确保数据是单调递增的
    sort_indices = np.argsort(unique_ref_wavelength)
    sorted_wavelength = unique_ref_wavelength[sort_indices]
    sorted_values = unique_reflectance[sort_indices]
    
    # 检查数据有效性
    if len(sorted_wavelength) < 2:
        raise ValueError("反射率数据点不足，无法进行插值")
    
    # 检查是否有无效值
    if np.any(np.isnan(sorted_values)) or np.any(np.isinf(sorted_values)):
        raise ValueError("反射率数据包含无效值（NaN或Inf）")
    
    # 使用interp1d进行插值，bounds_error=False允许外推，fill_value使用边界值
    interp_func = interp1d(sorted_wavelength, sorted_values, kind='linear',
                           bounds_error=False, fill_value=(sorted_values[0], sorted_values[-1]))
    
    return interp_func(target_wavelength)

def calculate_weighted_reflectance(reflectance, spectrum, wavelengths):
    """计算加权平均反射率"""
    numerator = np.trapz(reflectance * spectrum, wavelengths)
    denominator = np.trapz(spectrum, wavelengths)
    return numerator / denominator

def load_and_interpolate_emissivity(wavelength_csv, emissivity_txt, emissivity_atm_txt, wavelength_range=[8, 13]):
    """加载并插值发射率和大气发射率数据（谨慎策略）
    - 对输入x进行排序、去重
    - Y值自动规范到[0,1]（>2 视为百分比/100）
    - 插值使用np.interp（区间外采用边界值，不外推）
    """
    try:
        data_csv = pd.read_csv(wavelength_csv)
        X = data_csv.iloc[:, 0].to_numpy()

        # 材料发射率
        emis_df = pd.read_csv(emissivity_txt, delim_whitespace=True, header=None, names=['X2', 'emissivity'])
        if (emis_df['X2'] > 1000).any():
            emis_df['X2'] *= 0.001
        y = emis_df['emissivity'].astype(float).to_numpy()
        if np.nanmax(y) > 2:
            y = y / 100.0
        y = np.clip(y, 0.0, 1.0)
        x = emis_df['X2'].astype(float).to_numpy()
        # 去NaN/Inf并排序去重
        m = np.isfinite(x) & np.isfinite(y)
        x, y = x[m], y[m]
        if x.size < 2:
            raise Exception("材料发射率数据点不足，无法插值")
        idx = np.argsort(x)
        x, y = x[idx], y[idx]
        xu, uniq_idx = np.unique(x, return_index=True)
        yu = y[uniq_idx]
        emissivity_interpolated = np.interp(X, xu, yu)

        # 大气发射率
        atm_df = pd.read_csv(emissivity_atm_txt, delim_whitespace=True, header=None, names=['X3', 'emissivityatm'])
        xa = atm_df['X3'].astype(float).to_numpy()
        ya = atm_df['emissivityatm'].astype(float).to_numpy()
        ya = np.clip(ya, 0.0, 1.0)
        m2 = np.isfinite(xa) & np.isfinite(ya)
        xa, ya = xa[m2], ya[m2]
        if (xa > 1000).any():
            xa = xa * 0.001
        if xa.size < 2:
            raise Exception("大气发射率数据点不足，无法插值")
        idx2 = np.argsort(xa)
        xa, ya = xa[idx2], ya[idx2]
        xau, uniq_idx2 = np.unique(xa, return_index=True)
        yau = ya[uniq_idx2]
        emissivityatm_interpolated = np.interp(X, xau, yau)

        return X, emissivity_interpolated, emissivityatm_interpolated
    except Exception as e:
        raise Exception(f"加载发射率数据时出错: {e}")

def calculate_radiation_power(data1, data2, theta, wavelengths1, wavelengths2):
    """计算辐射功率"""
    tmat = data1[:, 1]
    with np.errstate(divide='ignore', invalid='ignore'):
        e_zmat = 1 - tmat ** (1. / np.cos(theta))
        e_zmat = np.nan_to_num(e_zmat, nan=0.0, posinf=0.0, neginf=0.0)
    e_smat = data2[:, 1]
    return e_zmat, e_smat

def create_declaration_file(default_directory, declare_file, email_contact):
    """在当前脚本所在的目录下创建声明文件。"""
    try:
        if not os.path.exists(default_directory):
            os.makedirs(default_directory)
        file_path = os.path.join(default_directory, declare_file)
        
        content = f"""仅需要有两个测试数据：涉及可见光波段的反射率和涉及大气窗口的透过率。
在txt文件中仅出现数据，请不要存在任何汉字！软件会自动匹配数据
该软件免费分享，免费使用。如有疑问联系{email_contact}
诚信科研，使用此工具希望能够引用我的文章。"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f'声明文件已创建：{file_path}')
    except Exception as e:
        print(f'创建声明文件时出错: {e}')

# UI组件类
class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        # 先初始化颜色，再创建动画对象
        self._normal_color = QColor("#3498db")
        self._hover_color = QColor("#2980b9")
        self._pressed_color = QColor("#1a5276")
        self._current_color = self._normal_color
        
        self._animation = QPropertyAnimation(self, b"background_color")
        self._animation.setDuration(200)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    @pyqtProperty(QColor)
    def background_color(self):
        return self._current_color

    @background_color.setter
    def background_color(self, color):
        self._current_color = color
        self.setStyleSheet(f"""
            background-color: {color.name()};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 30px;
        """)

    def enterEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._hover_color)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._normal_color)
        self._animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._animation.stop()
            self._animation.setStartValue(self._current_color)
            self._animation.setEndValue(self._pressed_color)
            self._animation.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._animation.stop()
            self._animation.setStartValue(self._current_color)
            self._animation.setEndValue(self._hover_color if self.underMouse() else self._normal_color)
            self._animation.start()
        super().mouseReleaseEvent(event)

# 自定义标题标签类
class TitleLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("title")
        self.setAlignment(Qt.AlignCenter)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

# 自定义卡片样式框架
class CardFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            CardFrame {
                background-color: white;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

# 自定义进度对话框
class ProgressDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(300, 100)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout()
        
        self.message_label = QLabel(message)
        layout.addWidget(self.message_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为持续转动
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def update_language(self):
        """更新语言"""
        # 如果对话框正在显示，更新标题和消息
        pass

# 计算线程类
class CalculationThread(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)  # 进度信号
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

# 样式表
STYLE_SHEET = f"""
    QMainWindow {{
        background-color: {COLORS['background']};
    }}
    QWidget {{
        background-color: {COLORS['background']};
        color: {COLORS['primary_text']};
    }}
    QGroupBox {{
        font-weight: bold;
        border: 2px solid {COLORS['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 12px;
        background-color: {COLORS['card']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {COLORS['accent']};
    }}
    QPushButton {{
        background-color: {COLORS['accent']};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-size: 12px;
        font-weight: 500;
        min-width: 120px;
    }}
    QPushButton:hover {{
        background-color: #2980B9;
    }}
    QPushButton:pressed {{
        background-color: #21618C;
    }}
    QLabel {{
        color: {COLORS['primary_text']};
    }}
    QLineEdit, QTextEdit {{
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        padding: 6px;
        background-color: {COLORS['card']};
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 2px solid {COLORS['accent']};
    }}
    QTabWidget::pane {{
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        background-color: {COLORS['card']};
    }}
    QTabBar::tab {{
        background-color: {COLORS['light_bg']};
        color: {COLORS['secondary_text']};
        padding: 8px 16px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {COLORS['card']};
        color: {COLORS['accent']};
        font-weight: bold;
    }}
"""

# Matplotlib画布类
class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

class InteractivePlotWindow(QDialog):
    """交互式绘图窗口，支持轴范围调整、元素拖动和动态交互"""
    
    def __init__(self, fig, parent=None, title="Interactive Plot"):
        super().__init__(parent)
        self.fig = fig
        self.title = title
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)
        
        # 存储所有axes和可拖动元素
        self.axes_list = fig.get_axes()
        self.draggable_elements = []
        self.drag_data = None
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 创建控制面板
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # 创建matplotlib画布
        self.canvas = FigureCanvas(fig)
        main_layout.addWidget(self.canvas)
        
        # 添加matplotlib工具栏
        self.toolbar = NavigationToolbar(self.canvas, self)
        main_layout.addWidget(self.toolbar)
        
        # 设置可拖动元素
        self.setup_draggable_elements()
        
        # 连接事件
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        
        # 刷新画布
        self.canvas.draw()
    
    def create_control_panel(self):
        """创建控制面板，用于调整轴范围"""
        panel = QGroupBox("Axis Range Control")
        layout = QGridLayout()
        
        # 子图选择（如果有多个子图）
        if len(self.axes_list) > 1:
            layout.addWidget(QLabel("Select Subplot:"), 0, 0)
            self.axes_combo = QComboBox()
            for i, ax in enumerate(self.axes_list):
                title = ax.get_title() or f"Subplot {i+1}"
                self.axes_combo.addItem(title)
            self.axes_combo.currentIndexChanged.connect(self.update_axis_display)
            layout.addWidget(self.axes_combo, 0, 1, 1, 2)
        else:
            self.axes_combo = None
        
        row_offset = 1 if len(self.axes_list) > 1 else 0
        
        # X轴控制
        layout.addWidget(QLabel("X-axis Range:"), row_offset, 0)
        self.xmin_input = QLineEdit()
        self.xmax_input = QLineEdit()
        self.xmin_input.setPlaceholderText("Min")
        self.xmax_input.setPlaceholderText("Max")
        layout.addWidget(self.xmin_input, row_offset, 1)
        layout.addWidget(QLabel("to"), row_offset, 2)
        layout.addWidget(self.xmax_input, row_offset, 3)
        x_apply_btn = QPushButton("Apply X-axis")
        x_apply_btn.clicked.connect(self.apply_x_limits)
        layout.addWidget(x_apply_btn, row_offset, 4)
        x_auto_btn = QPushButton("Auto X-axis")
        x_auto_btn.clicked.connect(self.auto_x_limits)
        layout.addWidget(x_auto_btn, row_offset, 5)
        
        # Y轴控制
        layout.addWidget(QLabel("Y-axis Range:"), row_offset + 1, 0)
        self.ymin_input = QLineEdit()
        self.ymax_input = QLineEdit()
        self.ymin_input.setPlaceholderText("Min")
        self.ymax_input.setPlaceholderText("Max")
        layout.addWidget(self.ymin_input, row_offset + 1, 1)
        layout.addWidget(QLabel("to"), row_offset + 1, 2)
        layout.addWidget(self.ymax_input, row_offset + 1, 3)
        y_apply_btn = QPushButton("Apply Y-axis")
        y_apply_btn.clicked.connect(self.apply_y_limits)
        layout.addWidget(y_apply_btn, row_offset + 1, 4)
        y_auto_btn = QPushButton("Auto Y-axis")
        y_auto_btn.clicked.connect(self.auto_y_limits)
        layout.addWidget(y_auto_btn, row_offset + 1, 5)
        
        # 拖动模式开关
        self.drag_mode_checkbox = QCheckBox("Enable Element Dragging")
        self.drag_mode_checkbox.setChecked(True)
        layout.addWidget(self.drag_mode_checkbox, row_offset + 2, 0, 1, 3)
        
        # 重置按钮
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.reset_view)
        layout.addWidget(reset_btn, row_offset + 2, 3, 1, 3)
        
        # 初始化轴范围显示
        self.update_axis_display()
        
        panel.setLayout(layout)
        return panel
    
    def get_current_axes(self):
        """获取当前选中的axes"""
        if self.axes_combo:
            idx = self.axes_combo.currentIndex()
            return self.axes_list[idx] if idx < len(self.axes_list) else self.axes_list[0]
        return self.axes_list[0] if self.axes_list else None
    
    def update_axis_display(self):
        """更新轴范围显示"""
        ax = self.get_current_axes()
        if ax:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            self.xmin_input.setText(f"{xlim[0]:.2f}")
            self.xmax_input.setText(f"{xlim[1]:.2f}")
            self.ymin_input.setText(f"{ylim[0]:.2f}")
            self.ymax_input.setText(f"{ylim[1]:.2f}")
    
    def apply_x_limits(self):
        """应用X轴范围"""
        try:
            xmin = float(self.xmin_input.text())
            xmax = float(self.xmax_input.text())
            if xmin >= xmax:
                QMessageBox.warning(self, "Warning", "X-axis minimum must be less than maximum")
                return
            ax = self.get_current_axes()
            if ax:
                ax.set_xlim(xmin, xmax)
                self.canvas.draw()
        except ValueError:
            QMessageBox.warning(self, "Warning", "Please enter a valid number")
    
    def apply_y_limits(self):
        """应用Y轴范围"""
        try:
            ymin = float(self.ymin_input.text())
            ymax = float(self.ymax_input.text())
            if ymin >= ymax:
                QMessageBox.warning(self, "Warning", "Y-axis minimum must be less than maximum")
                return
            ax = self.get_current_axes()
            if ax:
                ax.set_ylim(ymin, ymax)
                self.canvas.draw()
        except ValueError:
            QMessageBox.warning(self, "Warning", "Please enter a valid number")
    
    def auto_x_limits(self):
        """自动设置X轴范围"""
        ax = self.get_current_axes()
        if ax:
            ax.relim()
            ax.autoscale(axis='x')
            self.update_axis_display()
            self.canvas.draw()
    
    def auto_y_limits(self):
        """自动设置Y轴范围"""
        ax = self.get_current_axes()
        if ax:
            ax.relim()
            ax.autoscale(axis='y')
            self.update_axis_display()
            self.canvas.draw()
    
    def reset_view(self):
        """重置视图"""
        ax = self.get_current_axes()
        if ax:
            ax.relim()
            ax.autoscale()
            self.update_axis_display()
            self.canvas.draw()
    
    def setup_draggable_elements(self):
        """设置可拖动元素（图例、文本等）"""
        for ax in self.axes_list:
            # 获取图例并启用拖动
            legend = ax.get_legend()
            if legend:
                legend.set_draggable(True, update='loc')
                self.draggable_elements.append(legend)
            
            # 获取所有文本元素并设置为可拖动
            for text in ax.texts:
                # 检查文本是否使用axes坐标（transform=ax.transAxes）
                if hasattr(text, '_transform'):
                    text.set_picker(True)
                    self.draggable_elements.append(text)
    
    def on_press(self, event):
        """鼠标按下事件"""
        if not self.drag_mode_checkbox.isChecked():
            return
        
        if event.inaxes is None:
            return
        
        # 检查是否点击了可拖动元素
        for element in self.draggable_elements:
            if isinstance(element, plt.Legend):
                # 图例使用matplotlib内置的拖动
                continue
            elif isinstance(element, plt.Text):
                # 检查是否点击了文本
                if hasattr(element, 'contains'):
                    contains, _ = element.contains(event)
                    if contains:
                        # 获取文本的transform类型
                        trans = element.get_transform()
                        if trans == event.inaxes.transAxes:
                            # axes坐标（0-1范围）
                            pos = element.get_position()
                            self.drag_data = {
                                'element': element,
                                'x0': event.x,
                                'y0': event.y,
                                'pos0': pos,
                                'transform': 'axes'
                            }
                        else:
                            # 数据坐标
                            self.drag_data = {
                                'element': element,
                                'x0': event.xdata,
                                'y0': event.ydata,
                                'pos0': element.get_position(),
                                'transform': 'data'
                            }
                        break
    
    def on_release(self, event):
        """鼠标释放事件"""
        self.drag_data = None
    
    def on_motion(self, event):
        """鼠标移动事件"""
        if not self.drag_mode_checkbox.isChecked():
            return
        
        if self.drag_data is None:
            return
        
        element = self.drag_data['element']
        
        # 文本拖动处理
        if isinstance(element, plt.Text):
            if self.drag_data['transform'] == 'axes':
                # axes坐标拖动（0-1范围）
                if event.inaxes:
                    # 计算像素偏移
                    dx_pixel = event.x - self.drag_data['x0']
                    dy_pixel = event.y - self.drag_data['y0']
                    
                    # 转换为axes坐标偏移
                    bbox = event.inaxes.bbox
                    dx_axes = dx_pixel / bbox.width
                    dy_axes = -dy_pixel / bbox.height  # 注意Y轴方向
                    
                    # 更新位置
                    pos0 = self.drag_data['pos0']
                    new_pos = (pos0[0] + dx_axes, pos0[1] + dy_axes)
                    element.set_position(new_pos)
                    self.canvas.draw_idle()
            else:
                # 数据坐标拖动
                if event.inaxes and event.xdata is not None and event.ydata is not None:
                    element.set_position((event.xdata, event.ydata))
                    self.canvas.draw_idle()

# 直接内置所有用于计算的函数，避免依赖 backup.py

def calculate_R_sol(file_paths, config):
    """Calculate the weighted average reflectance R_sol."""
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    return R_sol


def planck_lambda(wavelength, temperature):
    """
    计算黑体在给定波长和温度下的谱强度 I_BB(λ)。
    wavelength (numpy.ndarray): 波长，单位为米。
    temperature (float): 温度，单位为开尔文。
    返回：numpy.ndarray: 黑体谱强度，单位为 W·sr^-1·m^-3。
    """
    h = 6.62607015e-34
    c = 3.0e8
    k = 1.380649e-23
    numerator = 2 * h * c**2
    denominator = (wavelength**5) * (np.exp((h * c) / (wavelength * k * temperature)) - 1)
    return numerator / denominator


def calculate_average_emissivity(wavelength, emissivity, temperature):
    """计算平均发射率。wavelength单位为米"""
    I_BB = planck_lambda(wavelength, temperature)
    numerator = np.trapz(I_BB * emissivity, wavelength)
    denominator = np.trapz(I_BB, wavelength)
    average_emissivity = numerator / denominator
    return average_emissivity


def calculate_convection_coefficient(wind_speed, delta_T, T_a, L_char=1.0):
    """
    计算考虑自然对流和强制对流的对流换热系数（Churchill-Usagi 混合法）
    返回值单位：W/(m²·K)
    """
    T_film = max(150.0, T_a + delta_T / 2)
    rho = 1.225 * (273.15 / T_film)
    mu = 1.81e-5 * (T_film / 273.15)**0.7
    k_air = 0.024 * (T_film / 273.15)**0.8
    cp = 1005
    nu = mu / rho
    alpha = k_air / (rho * cp)
    Pr = max(0.68, min(0.75, nu / alpha))
    g = 9.81
    beta = 1.0 / T_film
    if abs(delta_T) > 1e-3:
        Ra = max(1e-9, g * beta * abs(delta_T) * L_char**3 / (nu * alpha))
        if Ra < 1e7:
            Nu_nat = 0.54 * Ra**0.25
        else:
            Nu_nat = 0.15 * Ra**(1/3)
        h_natural = Nu_nat * k_air / L_char
    else:
        h_natural = 0.0
    if wind_speed > 1e-3:
        Re = max(1.0, wind_speed * L_char / nu)
        if Re < 5e5:
            Nu_forced = 0.664 * Re**0.5 * Pr**(1/3)
        else:
            Nu_forced = 0.037 * Re**0.8 * Pr**(1/3)
        h_forced = Nu_forced * k_air / L_char
    else:
        h_forced = 0.0
    n = 3
    h_conv = (h_natural**n + h_forced**n)**(1/n)
    return max(1.0, float(h_conv))


def generate_wind_cooling_plot(file_paths, S_solar, skip_dialog=False):
    import numpy as np
    import matplotlib.pyplot as plt
    from scipy.optimize import brentq, minimize_scalar
    import pandas as pd
    config = load_config(file_paths['config'])
    T_a1 = config['T_a1']
    T_a = T_a1 + 273.15
    XMIN = -100
    XMAX = 300
    sigma = 5.670374419e-8
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]
    emissivity = data[:, 1]
    wavelength_m = wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)
    emissivitys = avg_emissivity
    alpha_s = 1 - R_sol
    def p_net_equation(delta_T, emissivity_atm, wind_speed):
        H = calculate_convection_coefficient(wind_speed, delta_T, T_a)
        T_s = T_a + delta_T
        return emissivitys * sigma * (T_s**4 - emissivity_atm * T_a**4) + H * delta_T - alpha_s * S_solar
    emissivity_variable = np.linspace(0, 1, num=50)
    wind = np.linspace(0, 5, num=50)
    delta_T_values = np.zeros((len(emissivity_variable), len(wind)))
    def find_approximate_solution(emissivity_atm, wind_speed, delta_T_min, delta_T_max):
        result = minimize_scalar(lambda dt: abs(p_net_equation(dt, emissivity_atm, wind_speed)),
                                 bounds=(delta_T_min, delta_T_max), method='bounded')
        if result.success:
            return result.x
        else:
            return np.nan
    for i, emissivity_atm in enumerate(emissivity_variable):
        for j, wind_speed in enumerate(wind):
            try:
                delta_T_solution = brentq(p_net_equation, XMIN, XMAX, args=(emissivity_atm, wind_speed))
                delta_T_values[i, j] = delta_T_solution
            except ValueError:
                approx_solution = find_approximate_solution(emissivity_atm, wind_speed, XMIN, XMAX)
                delta_T_values[i, j] = approx_solution
    if skip_dialog:
        return {
            'delta_T_values': delta_T_values,
            'emissivity_variable': emissivity_variable,
            'wind': wind
        }
    fig, ax = plt.subplots(figsize=(10, 8))
    X_mesh, Y_mesh = np.meshgrid(wind, emissivity_variable)
    cp = ax.contourf(X_mesh, Y_mesh, delta_T_values, levels=100, cmap='viridis')
    fig.colorbar(cp, ax=ax, label='ΔT (°C)')
    ax.set_xlabel('Wind (m/s)')
    ax.set_ylabel('Atomosphere emissivity')
    fig.tight_layout()
    plt.show()
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw()
    save_file_path = filedialog.asksaveasfilename(defaultextension=".csv", title="保存结果文件", filetypes=[("CSV files", "*.csv")])
    root.destroy()
    if save_file_path:
        import pandas as pd
        df_matrix = pd.DataFrame(delta_T_values, index=emissivity_variable, columns=np.round(wind, 3))
        df_matrix.index.name = 'emissivity'
        df_matrix.columns.name = 'wind'
        df_matrix.to_csv(save_file_path)
        print(f'结果已保存到 {save_file_path}')


def main_theoretical_heating_vs_solar(file_paths, skip_dialog=False):
    import numpy as np
    import matplotlib.pyplot as plt
    import pandas as pd
    import tkinter as tk
    from tkinter import filedialog
    config = load_config(file_paths['config'])
    C1 = config['C1']; C2 = config['C2']
    T_a_range = np.linspace(-100, 100, num=21)
    S_solar_range = np.linspace(0, 1200, num=49)
    R_sol = calculate_R_sol(file_paths, config)
    alpha_s = 1 - R_sol
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000; data2[:, 0] *= 1000
    theta1 = 0; theta2 = np.pi / 2; nth = 100; dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2, nth)
    angle_factor = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth
    lambda1 = data1[:, 0] * 1e-9; lambda2 = data2[:, 0] * 1e-9
    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1
    results = np.zeros((len(T_a_range), len(S_solar_range)))
    for i, Ta in enumerate(T_a_range):
        T = Ta + 273.15
        exponent_film = np.minimum(C2 / (lambda2 * T), 700)
        u_b1ams = 1e9 * (lambda2 ** 5) * (np.exp(exponent_film) - 1)
        u_bs = C1 / u_b1ams
        tempint_R3 = u_bs * data2[:, 1] * dlam2
        int_R3am = np.sum(tempint_R3)
        p_r = int_R3am * np.sum(angle_factor)
        exponent_a = np.minimum(C2 / (lambda1 * T), 700)
        u_b1ams1 = 1e9 * (lambda1 ** 5) * (np.exp(exponent_a) - 1)
        u_bs1 = C1 / u_b1ams1
        e_zmat_avg = np.mean(1 - np.power(data1[:, 1], 1 / np.cos(theta.mean())))
        tempint_R1 = u_bs1 * data2[:, 1] * e_zmat_avg * dlam1
        int_R1am = np.sum(tempint_R1)
        p_a = int_R1am * np.sum(angle_factor)
        for j, S in enumerate(S_solar_range):
            Q_solar = alpha_s * S
            p_heat = Q_solar + p_a - p_r
            results[i, j] = p_heat
    if skip_dialog:
        return {'results': results, 'T_a_range': T_a_range, 'S_solar_range': S_solar_range}
    fig, ax = plt.subplots(figsize=(8, 6))
    for i, Ta in enumerate(T_a_range):
        ax.plot(S_solar_range, results[i, :], label=f"Ta = {Ta:.0f}°C", linewidth=2)
    ax.set_xlabel("Solar Irradiance (W/m²)", fontsize=12)
    ax.set_ylabel("Net Radiative Heating Power (W/m²)", fontsize=12)
    ax.set_title("Theoretical radiation heating power and solar irradiance relationship \n (film temperature=ambient temperature, Δ T=0)", fontsize=14)
    ax.legend(); ax.grid(True); fig.tight_layout(); plt.show()
    root = tk.Tk(); root.withdraw()
    save_file_path = filedialog.asksaveasfilename(defaultextension=".csv", title="保存结果", filetypes=[("CSV files", "*.csv")])
    root.destroy()
    if save_file_path:
        df = pd.DataFrame(results, index=[f"{Ta:.0f}" for Ta in T_a_range], columns=np.round(S_solar_range, 2))
        df.index.name = "Ambient Temperature°C"; df.columns.name = "Solar Irradiance (W/m²)"
        df.to_csv(save_file_path); print(f"结果已保存到 {save_file_path}")


def main_cooling_gui(file_paths, skip_dialog=False):
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")
    config = load_config(file_paths['config'])
    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EXPIRATION_DATE = config['EXPIRATION_DATE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']
    C1 = config['C1']; C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']; T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    VISIABLE_RANGE = config['VISIABLE_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = config['S_solar']
    check_expiration(EXPIRATION_DATE, EMAIL_CONTACT)
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    R_sol1 = calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000; data2[:, 0] *= 1000
    T_a = T_a1 + 273.15
    T_film = np.arange(T_filmmin, T_filmmax, 1)
    T_sll = T_film + 273.15
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]; emissivity = data[:, 1]
    wavelength_m = wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)
    theta1 = 0; theta2 = np.pi / 2
    tmat = data1[:, 1]
    nth = len(tmat) + 1
    dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2 - dth, nth - 1)
    lambda1 = data1[:, 0] * 1e-9; lambda2 = data2[:, 0] * 1e-9
    e_zmat, e_smat = calculate_radiation_power(data1, data2, theta, lambda1, lambda2)
    S_solar = float(S_solar)
    alpha_s = 1 - R_sol
    results = np.zeros((len(T_film), len(HC_VALUES)))
    for hc_index, H_conv in enumerate(HC_VALUES):
        for i, T_s_current in enumerate(T_sll):
            try:
                u_b1ams1 = 1e9 * (lambda1 ** 5) * (np.exp(C2 / (lambda1 * (T_a))) - 1)
                u_bs1 = C1 / u_b1ams1
            except OverflowError:
                u_bs1 = np.zeros_like(lambda1)
            try:
                u_b1ams = 1e9 * (lambda2 ** 5) * (np.exp(C2 / (lambda2 * (T_s_current))) - 1)
                u_bs = C1 / u_b1ams
            except OverflowError:
                u_bs = np.zeros_like(lambda2)
            dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
            dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1
            tempint_R3 = u_bs * e_smat * dlam2
            int_R3am = np.sum(tempint_R3)
            tempint_Rt3 = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth * int_R3am
            int_Rth3 = np.sum(tempint_Rt3)
            p_r = int_Rth3
            tempint_R1 = u_bs1 * e_smat * e_zmat * dlam1
            int_R1am = np.sum(tempint_R1)
            tempint_Rt1 = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth * int_R1am
            int_Rth1 = np.sum(tempint_Rt1)
            p_a = int_Rth1
            Q_conv = H_conv * (T_a1 - T_film[i])
            Q_solar = alpha_s * S_solar
            if (T_s_current > 273.15):
                p_net = p_r - p_a - Q_conv - Q_solar
            else:
                p_net = p_r - p_a - Q_conv - Q_solar

            # 打印详细的功率分量
            print(f"--- T_film: {T_film[i]:.2f}°C, H_conv: {H_conv:.2f} W/m²K ---")
            print(f"  p_r (向外辐射): {p_r:.4f} W/m²")
            print(f"  p_a (大气辐射): {p_a:.4f} W/m²")
            print(f"  Q_conv (对流换热): {Q_conv:.4f} W/m²")
            print(f"  Q_solar (太阳吸收): {Q_solar:.4f} W/m²")
            print(f"  p_net (净制冷功率): {p_net:.4f} W/m²")
            print("-" * 50 + "\n")
            results[i, hc_index] = p_net
    idx_zero_diff = np.argmin(np.abs(T_film - T_a1))
    cooling_power_zero_diff = results[idx_zero_diff, :]
    if skip_dialog:
        create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
        return {
            'avg_emissivity': avg_emissivity,
            'R_sol': R_sol,
            'R_sol1': R_sol1,
            'Power_0': cooling_power_zero_diff[0],
            'results': results,
            'T_film': T_film,
            'T_a1': T_a1,
            'HC_VALUES': HC_VALUES
        }
    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
    return avg_emissivity, R_sol, R_sol1, cooling_power_zero_diff[0]


def main_calculating_gui(file_paths):
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")
    config = load_config(file_paths['config'])
    EXPIRATION_DATE = config['EXPIRATION_DATE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']
    C1 = config['C1']; C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']; T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    VISIABLE_RANGE = config['VISIABLE_RANGE']
    check_expiration(EXPIRATION_DATE, EMAIL_CONTACT)
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    R_sol1 = calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000; data2[:, 0] *= 1000
    T_a = T_a1 + 273.15
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]; emissivity = data[:, 1]
    wavelength_m = wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)
    return avg_emissivity, R_sol, R_sol1


def main_heating_gui(file_paths, skip_dialog=False):
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")
    config = load_config(file_paths['config'])
    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EXPIRATION_DATE = config['EXPIRATION_DATE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']
    C1 = config['C1']; C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmins']; T_filmmax = config['T_filmmaxs']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = float(config['S_solar'])
    check_expiration(EXPIRATION_DATE, EMAIL_CONTACT)
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000; data2[:, 0] *= 1000
    T_a = T_a1 + 273.15
    T_film = np.arange(T_filmmin, T_filmmax, 1)
    T_sll = T_film + 273.15
    theta1 = 0; theta2 = 90 * np.pi / 180
    nth = 14102
    dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2 - dth, nth - 1).reshape(-1, 1)
    nth -= 1
    lambda1 = data1[:, 0] * 1e-9
    lambda2 = data2[:, 0] * 1e-9
    tmat = data1[:, 1]
    e_zmat = 1 - np.power(tmat, 1 / np.cos(theta))
    e_smat = data2[:, 1]
    alpha_s = 1 - R_sol
    results = np.zeros((len(T_film), len(HC_VALUES)))
    sin_theta = np.sin(theta)
    cos_theta = np.cos(theta)
    angle_factor = 2 * np.pi * sin_theta * cos_theta * dth
    for hc_index, H in enumerate(HC_VALUES):
        for i, T_s_current in enumerate(T_sll):
            exponent_a = C2 / (lambda1 * T_a)
            exponent_a = np.where(exponent_a > 700, 700, exponent_a)
            u_b1ams1 = 1e9 * (lambda1 ** 5) * (np.exp(exponent_a) - 1)
            u_bs1 = C1 / u_b1ams1
            exponent_film = C2 / (lambda2 * T_s_current)
            exponent_film = np.where(exponent_film > 700, 700, exponent_film)
            u_b1ams = 1e9 * (lambda2 ** 5) * (np.exp(exponent_film) - 1)
            u_bs = C1 / u_b1ams
            dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
            dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1
            tempint_R3 = u_bs * e_smat * dlam2
            int_R3am = np.sum(tempint_R3)
            tempint_Rt3 = angle_factor * int_R3am
            int_Rth3 = np.sum(tempint_Rt3)
            p_r = int_Rth3
            tempint_R1 = u_bs1 * e_smat * e_zmat * dlam1
            int_R1am = np.sum(tempint_R1, axis=1)
            tempint_Rt1 = angle_factor.flatten() * int_R1am
            int_Rth1 = np.sum(tempint_Rt1)
            p_a = int_Rth1
            Q_conv_cond = H * (T_a1 - T_film[i])
            Q_solar = alpha_s * S_solar
            p_heat = Q_solar + p_a + Q_conv_cond - p_r
            results[i, hc_index] = p_heat
    idx_zero_diff = np.argmin(np.abs(T_film - T_a1))
    heating_power_zero_diff = results[idx_zero_diff, :]
    if skip_dialog:
        create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
        return {
            'Power_0': heating_power_zero_diff[0],
            'results': results,
            'T_film': T_film,
            'T_a1': T_a1,
            'HC_VALUES': HC_VALUES
        }
    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
    return heating_power_zero_diff[0]

# PyQt主窗口类
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # language
        language_manager.language_changed.connect(self.on_language_changed)

        self.setWindowTitle(language_manager.get('main_title'))
        self.setGeometry(100, 100, 600, 700)
        self.file_paths = {
            'config': (os.path.join(external_default_dir(), 'config.ini') if os.path.exists(os.path.join(external_default_dir(), 'config.ini')) else res_path('default', 'config.ini')),
            'spectrum': res_path('default', 'AM1.5.xlsx'),
            'wavelength': res_path('default', 'wavelength.csv')
        }
        
        # 加载配置文件并进行过期检查
        try:
            config = load_config(self.file_paths['config'])
            check_expiration(config['EXPIRATION_DATE'], config['EMAIL_CONTACT'])
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"{language_manager.get('calculation_failed')}: {e}")
            sys.exit(1)
        
        self.init_ui()
        self.retranslate_ui()
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
        # sync with current language
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

        # keep function buttons so we can retranslate
        self.func_buttons = []
        funcs = [
            ("energy_map", "🗺️ ", self.open_calculating),
            ("cooling_power", "❄️ ", self.open_cooling),
            ("heating_power", "🔥 ", self.open_heating),
            ("wind_cloud", "📈 ", self.open_yuntu),
            ("solar_efficiency", "☀️ ", self.open_heating_vs_solar),
            ("modify_params", "⚙️ ", self.launch_config_editor),
            ("file_converter", "📄 ", self.open_file_processor),
            ("select_atm_transmittance", "🌤️ ", self.open_emissivity_solar_cloud)
        ]

        for key, prefix, func in funcs:
            btn = QPushButton()
            btn.clicked.connect(func)
            self.func_layout.addWidget(btn)
            self.func_buttons.append((btn, key, prefix))

        self.func_group.setLayout(self.func_layout)
        layout.addWidget(self.func_group)

        # 状态栏
        self.statusBar().showMessage(language_manager.get('info'))
        self.statusBar().setStyleSheet(f"background-color: {COLORS['light_bg']}; color: {COLORS['secondary_text']};")
        
        # 应用样式
        self.setStyleSheet(STYLE_SHEET)

    def _on_language_combo_changed(self, idx):
        lang = self.language_combo.itemData(idx)
        if lang:
            language_manager.set_language(lang)

    def on_language_changed(self, lang):
        # keep combo in sync
        if hasattr(self, 'language_combo'):
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(0 if lang == 'zh' else 1)
            self.language_combo.blockSignals(False)
        self.retranslate_ui()

    def retranslate_ui(self):
        # window + title
        self.setWindowTitle(language_manager.get('main_title'))
        if hasattr(self, 'title_label'):
            self.title_label.setText(language_manager.get('main_title'))

        # group titles
        if hasattr(self, 'file_group'):
            self.file_group.setTitle(language_manager.get('select_files'))
        if hasattr(self, 'func_group'):
            self.func_group.setTitle(language_manager.get('select_function'))

        # file buttons
        if hasattr(self, 'reflectance_btn'):
            self.reflectance_btn.setText(f"📄 {language_manager.get('select_reflectance')}")
        if hasattr(self, 'emissivity_btn'):
            self.emissivity_btn.setText(f"📊 {language_manager.get('select_emissivity')}")
        if hasattr(self, 'atm_emissivity_btn'):
            self.atm_emissivity_btn.setText(f"🌤️ {language_manager.get('select_atm_transmittance')}")

        # function buttons
        if hasattr(self, 'func_buttons'):
            for btn, key, prefix in self.func_buttons:
                btn.setText(f"{prefix}{language_manager.get(key)}")

        # status bar
        try:
            self.statusBar().showMessage(language_manager.get('info'))
        except Exception:
            pass
    
    def select_reflectance(self):
        file_path, _ = QFileDialog.getOpenFileName(self, language_manager.get('select_reflectance'), "", "Text files (*.txt)")
        if file_path:
            self.file_paths['reflectance'] = file_path
            QMessageBox.information(self, language_manager.get('info'), f"{language_manager.get('file_selected')}:\n{file_path}")
    
    def select_emissivity(self):
        file_path, _ = QFileDialog.getOpenFileName(self, language_manager.get('select_emissivity'), "", "Text files (*.txt)")
        if file_path:
            self.file_paths['emissivity'] = file_path
            QMessageBox.information(self, language_manager.get('info'), f"{language_manager.get('file_selected')}:\n{file_path}")
    
    def select_atm_emissivity(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(language_manager.get('select_atm_transmittance'))
        dialog.setFixedSize(400, 500)
        layout = QVBoxLayout(dialog)
        
        label = QLabel(language_manager.get('select_atm_file'))
        layout.addWidget(label)
        
        # 获取 default 目录中的所有 dll 文件
        default_dir = res_path('default')
        dll_files = []
        try:
            if os.path.exists(default_dir):
                dll_files = sorted([f for f in os.listdir(default_dir) if f.endswith('.dll')])
        except Exception as e:
            print(f"读取 default 目录失败: {e}")
        
        # 如果没有找到 dll 文件，使用默认选项
        if not dll_files:
            dll_files = ['1.dll', '2.dll']
        
        # 创建可滚动的按钮区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        button_widget = QWidget()
        button_layout = QVBoxLayout(button_widget)
        button_layout.setSpacing(5)
        
        # 为每个 dll 文件创建按钮
        for dll_file in dll_files:
            # 获取文件名（不含扩展名）作为显示标签
            file_label = dll_file.replace('.dll', '')
            
            # 为不同的文件类型添加不同的图标
            if '晴' in file_label or 'clear' in file_label.lower() or file_label == '1':
                emoji = "☀️"
            elif '云' in file_label or 'cloud' in file_label.lower() or file_label == '2':
                emoji = "☁️"
            elif '雾' in file_label or 'fog' in file_label.lower():
                emoji = "🌫️"
            elif '城市' in file_label or 'urban' in file_label.lower():
                emoji = "🏙️"
            elif '农村' in file_label or 'rural' in file_label.lower():
                emoji = "🌾"
            elif '海' in file_label or 'sea' in file_label.lower():
                emoji = "🌊"
            elif '污' in file_label or 'polluted' in file_label.lower():
                emoji = "⚠️"
            else:
                emoji = "📄"
            
            btn = QPushButton(f"{emoji} {file_label}")
            btn.setMinimumHeight(35)
            btn.clicked.connect(lambda checked, fn=dll_file: self._select_atm_file(fn, dialog))
            button_layout.addWidget(btn)
        
        button_layout.addStretch()
        scroll_area.setWidget(button_widget)
        layout.addWidget(scroll_area)
        
        dialog.exec_()
    
    def _select_atm_file(self, file_name, dialog):
        self.file_paths['atm_emissivity'] = res_path('default', file_name)
        dialog.accept()
        file_label = file_name.replace('.dll', '')
        QMessageBox.information(self, language_manager.get('info'), f"{language_manager.get('file_selected')}: {file_label}")
    
    def check_all_files(self, required_keys):
        missing = [key for key in required_keys if key not in self.file_paths or not self.file_paths[key]]
        if missing:
            raise Exception(f"{language_manager.get('select_all_files')}. {language_manager.get('missing_files')}: {', '.join(missing)}")
    
    def open_cooling(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            CoolingWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))
    
    def open_calculating(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            CalculatingWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))
    
    def open_heating(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            HeatingWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))
    
    def open_yuntu(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            WindCoolingPlotWindow(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))
    
    def open_heating_vs_solar(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            # 使用线程执行计算
            self.calc_thread = CalculationThread(main_theoretical_heating_vs_solar, self.file_paths, skip_dialog=True)
            
            def on_finished(result):
                # 先在主线程重建图表（避免使用后台线程创建的 Figure）
                try:
                    results = result['results']
                    T_a_range = result['T_a_range']
                    S_solar_range = result['S_solar_range']

                    # 在主线程中创建图表
                    fig, ax = plt.subplots(figsize=(8, 6))
                    for i, Ta in enumerate(T_a_range):
                        ax.plot(S_solar_range, results[i, :], label=f"Ta = {Ta:.0f}°C", linewidth=2)
                    ax.set_xlabel("Solar Irradiance (W/m²)", fontsize=12)
                    ax.set_ylabel("Net Radiative Heating Power (W/m²)", fontsize=12)
                    ax.set_title("Theoretical radiation heating power and solar irradiance relationship\n(film temperature=ambient temperature, ΔT=0)", fontsize=14)
                    ax.legend()
                    ax.grid(True)
                    fig.tight_layout()

                    dlg = InteractivePlotWindow(fig, parent=self, title="光热VS光照")
                    dlg.exec_()
                except Exception as e:
                    QMessageBox.warning(self, "提示", f"显示图表时出错：{e}")
                
                # 再提供保存CSV的对话框
                try:
                    save_path, _ = QFileDialog.getSaveFileName(self, "保存结果", "", "CSV files (*.csv)")
                    if save_path:
                        df = pd.DataFrame(
                            results,
                            index=[f"{Ta:.0f}" for Ta in T_a_range],
                            columns=np.round(S_solar_range, 2)
                        )
                        df.index.name = "Ambient Temperature°C"
                        df.columns.name = "Solar Irradiance (W/m²)"
                        df.to_csv(save_path)
                        QMessageBox.information(self, "成功", f"结果已保存到 {save_path}")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存数据时出错: {e}")
            
            def on_error(error_msg):
                QMessageBox.critical(self, "错误", f"计算过程中出现错误: {error_msg}")
            
            self.calc_thread.finished.connect(on_finished)
            self.calc_thread.error.connect(on_error)
            self.calc_thread.start()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))
    
    def launch_config_editor(self):
        launch_config_editor_pyqt(self)
    
    def open_file_processor(self):
        """打开文件处理工具"""
        FileProcessorDialog(self).exec_()
    
    def open_emissivity_solar_cloud(self):
        """打开大气发射率-太阳光强云图"""
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            EmissivitySolarCloudDialog(self, self.file_paths).exec_()
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), str(e))

# 计算窗口基类
class CalculationWindow(QDialog):
    def __init__(self, parent, file_paths, title_key_or_text):
        super().__init__(parent)
        language_manager.language_changed.connect(self.on_language_changed)
        self._title_key_or_text = title_key_or_text
        self.setWindowTitle(self._tr_title())
        self.setFixedSize(550, 350)
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
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        self.result_label = QLabel("")
        self.result_label.setStyleSheet(f"color: {COLORS['primary_text']}; font-size: 12px;")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        
        self.setStyleSheet(STYLE_SHEET)
        self.retranslate_ui()
    
    def run_calculation(self):
        pass  # 子类实现
    
    def _tr_title(self):
        # allow passing translation key (preferred) or raw text (fallback)
        key = self._title_key_or_text
        if isinstance(key, str) and key in language_manager.translations.get(language_manager.current_language, {}):
            return language_manager.get(key)
        return key

    def on_language_changed(self, lang):
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(self._tr_title())
        self.execute_btn.setText(language_manager.get('execute'))

    def on_calculation_finished(self, result):
        """计算完成回调"""
        self.execute_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(language_manager.get('calculation_complete'))
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
    
    def on_calculation_error(self, error_msg):
        """计算错误回调"""
        self.execute_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, language_manager.get('error'), 
                           f"{language_manager.get('calculation_failed')}: {error_msg}")
        self.status_label.setText(language_manager.get('calculation_failed'))
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")

class CoolingWindow(CalculationWindow):
    def __init__(self, parent, file_paths):
        super().__init__(parent, file_paths, 'cooling_power')
    
    def run_calculation(self):
        self.execute_btn.setEnabled(False)
        self.status_label.setText("正在计算，请稍候...")
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        # 使用线程执行计算
        self.calc_thread = CalculationThread(main_cooling_gui, self.file_paths, skip_dialog=True)
        self.calc_thread.finished.connect(self.on_calculation_finished)
        self.calc_thread.error.connect(self.on_calculation_error)
        self.calc_thread.start()
    
    def on_calculation_finished(self, result):
        """计算完成回调"""
        super().on_calculation_finished(result)
        Power_0 = result['Power_0']
        self.result_label.setText(f"冷却功率 = {Power_0:.4f} W/m²")
        
        # 显示绘图和导出对话框
        self.show_result_dialog(result, 'cooling')
    
    def show_result_dialog(self, result, calc_type):
        """显示结果操作对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle(language_manager.get('choose_action'))
        dialog.setFixedSize(300, 200)
        layout = QVBoxLayout(dialog)
        
        plot_btn = QPushButton(language_manager.get('plot_chart'))
        plot_btn.clicked.connect(lambda: [self.plot_results(result), dialog.accept()])
        layout.addWidget(plot_btn)
        
        export_btn = QPushButton(language_manager.get('export_data'))
        export_btn.clicked.connect(lambda: [self.export_data(result), dialog.accept()])
        layout.addWidget(export_btn)
        
        cancel_btn = QPushButton(language_manager.get('cancel'))
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)
        
        dialog.setStyleSheet(STYLE_SHEET)
        dialog.exec_()
    
    def plot_results(self, result):
        """绘制结果图"""
        from itertools import cycle
        results = result['results']
        T_film = result['T_film']
        T_a1 = result['T_a1']
        HC_VALUES = result['HC_VALUES']
        
        plt.figure(figsize=(10, 6))
        num_lines = len(HC_VALUES)
        cmap = plt.get_cmap('tab10')
        colors = [cmap(i % cmap.N) for i in range(num_lines)]
        linestyles = cycle(['-', '--', '-.', ':'])
        
        T_film_diff = T_film - T_a1
        
        for hc_index in range(num_lines):
            color = colors[hc_index]
            linestyle = next(linestyles)
            plt.plot(T_film_diff, results[:, hc_index], color=color, linestyle=linestyle, 
                    linewidth=2, label=f'h_c={HC_VALUES[hc_index]} W m⁻² K⁻¹')
        
        plt.xlabel('T_{film} - T_{ambient} (°C)', fontsize=12)
        plt.ylabel('Cooling Power (W m⁻²)', fontsize=12)
        plt.title('Radiative cooling power vs film temperature difference', fontsize=14)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
    
    def export_data(self, result):
        """导出数据"""
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "CSV files (*.csv)")
            if save_path:
                results = result['results']
                T_film = result['T_film']
                T_a1 = result['T_a1']
                HC_VALUES = result['HC_VALUES']
                
                export_data_dict = {'T_film_diff (°C)': T_film - T_a1}
                for hc_index, hc_value in enumerate(HC_VALUES):
                    export_data_dict[f'Cooling_Power_hc_{hc_value}'] = results[:, hc_index]
                
                df_export = pd.DataFrame(export_data_dict)
                df_export.to_csv(save_path, index=False)
                QMessageBox.information(self, "成功", f"数据已保存到 {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存数据时出错: {e}")

class CalculatingWindow(CalculationWindow):
    def __init__(self, parent, file_paths):
        super().__init__(parent, file_paths, 'map_params_calculation')
    
    def run_calculation(self):
        self.execute_btn.setEnabled(False)
        self.status_label.setText(language_manager.get('calculating_msg'))
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        # 使用线程执行计算
        self.calc_thread = CalculationThread(main_calculating_gui, self.file_paths)
        self.calc_thread.finished.connect(self.on_calculation_finished)
        self.calc_thread.error.connect(self.on_calculation_error)
        self.calc_thread.start()
    
    def on_calculation_finished(self, result):
        """计算完成回调"""
        super().on_calculation_finished(result)
        avg_emissivity, R_sol, R_sol1 = result
        self.result_label.setText(
            f"{language_manager.get('avg_emissivity')} = {avg_emissivity:.4f}\n"
            f"{language_manager.get('solar_reflectance')} = {R_sol:.4f}\n"
            f"{language_manager.get('visible_reflectance')} = {R_sol1:.4f}\n"
            f"{language_manager.get('map_plot_contact')}"
        )

class HeatingWindow(CalculationWindow):
    def __init__(self, parent, file_paths):
        super().__init__(parent, file_paths, 'heating_power_calculation')
    
    def run_calculation(self):
        self.execute_btn.setEnabled(False)
        self.status_label.setText(language_manager.get('calculating_msg'))
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        # 使用线程执行计算
        self.calc_thread = CalculationThread(main_heating_gui, self.file_paths, skip_dialog=True)
        self.calc_thread.finished.connect(self.on_calculation_finished)
        self.calc_thread.error.connect(self.on_calculation_error)
        self.calc_thread.start()
    
    def on_calculation_finished(self, result):
        """计算完成回调"""
        super().on_calculation_finished(result)
        Power_0 = result['Power_0']
        self.result_label.setText(f"{language_manager.get('heating_power_result')} = {Power_0:.4f} W/m²")
        
        # 显示绘图和导出对话框
        self.show_result_dialog(result, 'heating')
    
    def show_result_dialog(self, result, calc_type):
        """显示结果操作对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle(language_manager.get('choose_action'))
        dialog.setFixedSize(300, 200)
        layout = QVBoxLayout(dialog)
        
        plot_btn = QPushButton(language_manager.get('plot_chart'))
        plot_btn.clicked.connect(lambda: [self.plot_results(result), dialog.accept()])
        layout.addWidget(plot_btn)
        
        export_btn = QPushButton(language_manager.get('export_data'))
        export_btn.clicked.connect(lambda: [self.export_data(result), dialog.accept()])
        layout.addWidget(export_btn)
        
        cancel_btn = QPushButton(language_manager.get('cancel'))
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)
        
        dialog.setStyleSheet(STYLE_SHEET)
        dialog.exec_()
    
    def plot_results(self, result):
        """绘制结果图"""
        from itertools import cycle
        results = result['results']
        T_film = result['T_film']
        T_a1 = result['T_a1']
        HC_VALUES = result['HC_VALUES']
        
        plt.figure(figsize=(10, 6))
        num_lines = len(HC_VALUES)
        cmap = plt.get_cmap('tab10')
        colors = [cmap(i % cmap.N) for i in range(num_lines)]
        linestyles = cycle(['-', '--', '-.', ':'])
        
        T_film_diff = T_film - T_a1
        
        for hc_index in range(num_lines):
            color = colors[hc_index]
            linestyle = next(linestyles)
            plt.plot(T_film_diff, results[:, hc_index], color=color, linestyle=linestyle, 
                    linewidth=2, label=f'h_c={HC_VALUES[hc_index]} W m⁻² K⁻¹')
        
        plt.xlabel('T_{film} - T_{ambient} (°C)', fontsize=12)
        plt.ylabel('Heating Power (W m⁻²)', fontsize=12)
        plt.title('Radiative Heating power vs film temperature difference', fontsize=14)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
    
    def export_data(self, result):
        """导出数据"""
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "CSV files (*.csv)")
            if save_path:
                results = result['results']
                T_film = result['T_film']
                T_a1 = result['T_a1']
                HC_VALUES = result['HC_VALUES']
                
                export_data_dict = {'T_film_diff (°C)': T_film - T_a1}
                for hc_index, hc_value in enumerate(HC_VALUES):
                    export_data_dict[f'Heating_Power_hc_{hc_value}'] = results[:, hc_index]
                
                df_export = pd.DataFrame(export_data_dict)
                df_export.to_csv(save_path, index=False)
                QMessageBox.information(self, "成功", f"数据已保存到 {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存数据时出错: {e}")

class WindCoolingPlotWindow(QDialog):
    def __init__(self, parent, file_paths):
        super().__init__(parent)
        self.setWindowTitle("风速与制冷效率云图")
        self.setFixedSize(500, 250)
        self.file_paths = file_paths.copy()
        self.calc_thread = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        label = QLabel("请输入太阳辐照度 S_solar (单位: W/m²):")
        layout.addWidget(label)
        
        self.s_solar_entry = QLineEdit()
        layout.addWidget(self.s_solar_entry)
        
        self.execute_btn = QPushButton("生成云图")
        self.execute_btn.clicked.connect(self.run_wind_cooling_plot)
        layout.addWidget(self.execute_btn)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        self.setStyleSheet(STYLE_SHEET)
    
    def run_wind_cooling_plot(self):
        try:
            S_solar = float(self.s_solar_entry.text())
            self.execute_btn.setEnabled(False)
            self.status_label.setText("正在计算，请稍候...")
            self.status_label.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
            
            # 使用线程执行计算
            self.calc_thread = CalculationThread(generate_wind_cooling_plot, self.file_paths, S_solar, skip_dialog=True)
            self.calc_thread.finished.connect(self.on_plot_finished)
            self.calc_thread.error.connect(self.on_plot_error)
            self.calc_thread.start()
        except ValueError:
            QMessageBox.critical(self, "错误", "请输入有效的太阳辐照度数值")
    
    def on_plot_finished(self, result):
        """绘图计算完成回调"""
        self.execute_btn.setEnabled(True)
        self.status_label.setText("计算完成！")
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: bold;")
        
        # 弹出操作选择对话框：预览图表 / 导出数据
        dialog = QDialog(self)
        dialog.setWindowTitle("选择操作")
        dialog.setFixedSize(300, 200)
        vbox = QVBoxLayout(dialog)
        
        preview_btn = QPushButton("预览结果图表")
        preview_btn.clicked.connect(lambda: [self.preview_wind_cooling_plot(result), dialog.accept()])
        vbox.addWidget(preview_btn)
        
        export_btn = QPushButton("导出数据")
        export_btn.clicked.connect(lambda: [self.export_wind_cooling_data(result), dialog.accept()])
        vbox.addWidget(export_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        vbox.addWidget(cancel_btn)
        
        dialog.setStyleSheet(STYLE_SHEET)
        dialog.exec_()
    
    def preview_wind_cooling_plot(self, result):
        """在主线程预览风速与制冷效率云图"""
        try:
            delta_T_values = result['delta_T_values']
            emissivity_variable = result['emissivity_variable']
            wind = result['wind']
            
            fig, ax = plt.subplots(figsize=(10, 8))
            X, Y = np.meshgrid(wind, emissivity_variable)
            contourf = ax.contourf(X, Y, delta_T_values, levels=50, cmap='viridis')
            cbar = fig.colorbar(contourf, ax=ax, pad=0.02)
            cbar.set_label('ΔT (°C)')
            ax.set_xlabel('Wind (m/s)')
            ax.set_ylabel('Emissivity')
            ax.set_title('Wind vs Cooling Efficiency (ΔT) Cloud Map')
            ax.grid(True, linestyle='--', alpha=0.3)
            fig.tight_layout()
            
            dlg = InteractivePlotWindow(fig, parent=self, title='风速与制冷效率云图')
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"绘图时出错: {e}")
    
    def export_wind_cooling_data(self, result):
        """导出风速与制冷效率云图数据为CSV"""
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, "保存结果文件", "", "CSV files (*.csv)")
            if save_path:
                delta_T_values = result['delta_T_values']
                emissivity_variable = result['emissivity_variable']
                wind = result['wind']
                
                df_matrix = pd.DataFrame(delta_T_values, index=emissivity_variable, columns=np.round(wind, 3))
                df_matrix.index.name = 'emissivity'
                df_matrix.columns.name = 'wind'
                df_matrix.to_csv(save_path)
                QMessageBox.information(self, "成功", f"结果已保存到 {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存数据时出错: {e}")
    
    def on_plot_error(self, error_msg):
        """绘图计算错误回调"""
        self.execute_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"计算过程中出现错误: {error_msg}")
        self.status_label.setText("计算失败！")
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")

class FileProcessorDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(550, 450)
        self.selected_file = None
        self.output_type = 'reflectance'  # 'reflectance' or 'emissivity'
        
        language_manager.language_changed.connect(self.update_language)
        
        self.init_ui()
        self.update_language()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        self.title_label = TitleLabel("")
        layout.addWidget(self.title_label)
        
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        layout.addWidget(self.desc_label)
        
        file_card = CardFrame()
        file_layout = QVBoxLayout(file_card)
        
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)
        
        self.select_btn = AnimatedButton("")
        self.select_btn.clicked.connect(self.select_file)
        button_layout.addWidget(self.select_btn)
        
        self.convert_btn = AnimatedButton("")
        self.convert_btn.clicked.connect(self.convert_file)
        self.convert_btn.setEnabled(False)
        button_layout.addWidget(self.convert_btn)
        
        file_layout.addWidget(button_container)
        
        self.file_path_label = QLabel()
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setAlignment(Qt.AlignCenter)
        self.file_path_label.setStyleSheet("color: #3498db; font-size: 12px; padding: 10px;")
        file_layout.addWidget(self.file_path_label)
        
        # 输出类型选择
        type_container = QWidget()
        type_layout = QHBoxLayout(type_container)
        type_layout.setSpacing(15)
        
        self.type_label = QLabel("")
        self.type_label.setStyleSheet("font-size: 13px; font-weight: bold;")
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
        
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        file_layout.addWidget(self.status_label)
        
        layout.addWidget(file_card)
        
        button_layout_bottom = QHBoxLayout()
        button_layout_bottom.setSpacing(15)
        
        self.close_button = AnimatedButton("")
        self.close_button.clicked.connect(self.reject)
        button_layout_bottom.addWidget(self.close_button)
        
        layout.addLayout(button_layout_bottom)
        self.setLayout(layout)
    
    def on_type_changed(self, index):
        """输出类型改变"""
        self.output_type = self.type_combo.itemData(index)
    
    def update_language(self):
        """更新语言"""
        self.setWindowTitle(language_manager.get('file_processor'))
        self.title_label.setText(language_manager.get('file_processor'))
        self.desc_label.setText(language_manager.get('file_processor_desc'))
        self.select_btn.setText(language_manager.get('select_file'))
        self.convert_btn.setText(language_manager.get('start_convert'))
        self.close_button.setText(language_manager.get('close'))
        
        # 更新输出类型标签和下拉框
        self.type_label.setText(language_manager.get('select_output_type') + ":")
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItem(language_manager.get('reflectance_file'), 'reflectance')
        self.type_combo.addItem(language_manager.get('emissivity_file'), 'emissivity')
        # 恢复之前的选择
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.output_type:
                self.type_combo.setCurrentIndex(i)
                break
        self.type_combo.blockSignals(False)
        
        if not self.selected_file:
            self.file_path_label.setText("请选择要处理的文件" if language_manager.is_chinese() else "Please select a file to process")
    
    def select_file(self):
        """选择文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                language_manager.get('select_file'),
                "",
                "All Supported Files (*.csv *.xlsx *.xls *.txt);;CSV files (*.csv);;Excel files (*.xlsx *.xls);;Text files (*.txt);;All files (*.*)"
            )
            
            if file_path:
                self.selected_file = file_path
                filename = os.path.basename(file_path)
                selected_text = "已选择" if language_manager.is_chinese() else "Selected"
                self.file_path_label.setText(f"{selected_text}: {filename}")
                self.file_path_label.setStyleSheet("color: #27ae60; font-size: 12px; padding: 10px;")
                self.convert_btn.setEnabled(True)
                ready_text = "文件已选择，点击开始处理" if language_manager.is_chinese() else "File selected, click to start processing"
                self.status_label.setText(ready_text)
                self.status_label.setStyleSheet("color: #2c3e50;")
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), f"{language_manager.get('error')}: {str(e)}")
    
    def clean_data(self, data):
        """清理数据：删除所有中英文字符，仅保留数字行"""
        cleaned_rows = []
        
        for row in data:
            # 将行转换为字符串列表
            row_str = [str(cell) for cell in row]
            # 检查是否包含中英文字符
            has_text = False
            for cell in row_str:
                # 检查是否包含中文字符
                if re.search(r'[\u4e00-\u9fff]', str(cell)):
                    has_text = True
                    break
                # 检查是否包含英文字母（排除科学计数法中的e/E）
                if re.search(r'[a-zA-Z]', str(cell)) and not re.match(r'^[\d\.\-\+eE]+$', str(cell)):
                    has_text = True
                    break
            
            # 如果行中没有中英文字符，尝试提取数字
            if not has_text:
                numeric_values = []
                for cell in row_str:
                    try:
                        # 尝试转换为浮点数
                        val = float(cell)
                        numeric_values.append(val)
                    except (ValueError, TypeError):
                        # 如果转换失败，尝试从字符串中提取数字
                        numbers = re.findall(r'-?\d+\.?\d*[eE]?[+-]?\d*', str(cell))
                        if numbers:
                            numeric_values.append(float(numbers[0]))
                
                # 如果提取到至少两个数字，保留这一行
                if len(numeric_values) >= 2:
                    cleaned_rows.append(numeric_values[:2])  # 只保留前两个数字
        
        return np.array(cleaned_rows) if cleaned_rows else np.array([])
    
    def _normalize_number_token(self, token: str) -> float:
        """将包含逗号/点/科学计数/百分号的数字字符串规范为 float
        规则：
        - 同时包含','和'.' -> 认为','是千分位，去掉所有','
        - 仅包含','且不含'.' -> 将','视为小数点，全部替换为'.'
        - 移除结尾的百分号'%'（不自动除以100，留给后续流程判断缩放）
        - 其他保持不变
        """
        s = token.strip()
        # 去除百分号，不做缩放
        if s.endswith('%'):
            s = s[:-1]
        if ',' in s and '.' in s:
            s = s.replace(',', '')
        elif ',' in s and '.' not in s:
            s = s.replace(',', '.')
        return float(s)

    def parse_txt_file(self, file_path):
        """鲁棒解析TXT：逐行提取数字，忽略中英文与其他符号，仅保留每行前两列数字
        - 自动兼容中文标点（，。）、全角字符与Unicode减号
        - 自动容错编码（utf-8/gbk/...）
        """
        # 全角到半角映射，以及中文标点替换
        trans = str.maketrans({
            '０':'0','１':'1','２':'2','３':'3','４':'4','５':'5','６':'6','７':'7','８':'8','９':'9',
            '．':'.','，':',','。':'.','、':' ', '－':'-','—':'-','～':'-','‒':'-','–':'-','−':'-'
        })
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
        raise Exception("无法解析TXT文件中的数据（请确认至少包含两列数字）")

    def read_file(self, file_path):
        """智能读取文件（支持CSV、XLSX、TXT）"""
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
                    error_msg = "无法以任何编码读取CSV文件" if language_manager.is_chinese() else "Cannot read CSV file with any encoding"
                    raise Exception(error_msg)
                return df.values
                
            elif file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, header=None)
                return df.values
                
            elif file_ext == '.txt':
                # 对TXT使用鲁棒行解析，忽略中文/英文/符号
                return self.parse_txt_file(file_path)
            else:
                error_msg = f"不支持的文件格式: {file_ext}" if language_manager.is_chinese() else f"Unsupported file format: {file_ext}"
                raise Exception(error_msg)
            
        except Exception as e:
            error_msg = "读取文件失败" if language_manager.is_chinese() else "Failed to read file"
            raise Exception(f"{error_msg}: {str(e)}")
    
    def _postprocess_output(self, data: np.ndarray, output_type: str):
        """对解析出的两列数据进行规范化：
        - 去NaN/Inf
        - 去重复x、按x排序
        - 检测小数/百分比，自动把第二列规范到[0,1]
        - 检测波长单位，nm->µm（若x中位数>100）
        - 将y裁剪到[0,1]
        返回 处理后的数据 与 文本提示列表
        """
        tips = []
        arr = np.asarray(data, dtype=float)
        if arr.ndim != 2 or arr.shape[1] < 2:
            raise Exception("数据至少需要两列")
        arr = arr[:, :2]
        # 去NaN/Inf
        mask = np.isfinite(arr).all(axis=1)
        arr = arr[mask]
        # 去重复x
        if arr.shape[0] == 0:
            raise Exception("没有有效的数据行")
        # 按x排序
        idx = np.argsort(arr[:, 0])
        arr = arr[idx]
        # 去重（保留第一条）
        if arr.shape[0] > 1:
            uniq_x, uniq_idx = np.unique(arr[:, 0], return_index=True)
            arr = arr[uniq_idx]
        # 百分比/比例检测
        y = arr[:, 1]
        if np.nanmax(y) > 1.5:
            arr[:, 1] = y / 100.0
            tips.append("检测到百分比数据，已自动/100")
        # y裁剪到[0,1]
        arr[:, 1] = np.clip(arr[:, 1], 0.0, 1.0)
        # 波长单位：若大部分x>100，视为nm -> µm
        x = arr[:, 0]
        if np.median(x) > 100:
            arr[:, 0] = x * 0.001
            tips.append("检测到波长像纳米，已转换为微米(÷1000)")
        return arr, tips

    def convert_file(self):
        """处理文件"""
        if not self.selected_file:
            error_msg = "请先选择文件" if language_manager.is_chinese() else "Please select a file first"
            QMessageBox.critical(self, language_manager.get('error'), error_msg)
            return
        
        try:
            self.convert_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            reading_msg = "正在读取文件..." if language_manager.is_chinese() else "Reading file..."
            self.status_label.setText(reading_msg)
            QApplication.processEvents()
            
            # 读取文件
            data = self.read_file(self.selected_file)
            
            if data.size == 0 or data.shape[0] == 0:
                self.progress_bar.setVisible(False)
                self.convert_btn.setEnabled(True)
                error_msg = "文件为空或无法读取数据" if language_manager.is_chinese() else "File is empty or cannot read data"
                QMessageBox.critical(self, language_manager.get('error'), error_msg)
                return
            
            cleaning_msg = "正在清理数据..." if language_manager.is_chinese() else "Cleaning data..."
            self.status_label.setText(cleaning_msg)
            QApplication.processEvents()
            
            # 清理数据：删除中英文字符，仅保留数字行（若read_file已是数值，会原样返回）
            cleaned_data = self.clean_data(data) if not np.issubdtype(np.array(data).dtype, np.number) else np.array(data, dtype=float)
            
            if cleaned_data.size == 0 or cleaned_data.shape[0] == 0:
                self.progress_bar.setVisible(False)
                self.convert_btn.setEnabled(True)
                error_msg = "清理后没有有效的数据行（至少需要两列数字）" if language_manager.is_chinese() else "No valid data rows after cleaning (at least two numeric columns required)"
                QMessageBox.critical(self, language_manager.get('error'), error_msg)
                return
            
            # 只保留前两列并规范化
            output_data, tips = self._postprocess_output(cleaned_data[:, :2], self.output_type)
            if output_data.shape[0] < 5:
                self.progress_bar.setVisible(False)
                self.convert_btn.setEnabled(True)
                raise Exception("有效数据行过少(少于5行)")
            
            saving_msg = "正在保存文件..." if language_manager.is_chinese() else "Saving file..."
            self.status_label.setText(saving_msg)
            QApplication.processEvents()
            
            # 保存文件
            input_path = Path(self.selected_file)
            type_suffix = "_reflectance" if self.output_type == 'reflectance' else "_emissivity"
            output_path = input_path.parent / f"{input_path.stem}{type_suffix}.txt"
            
            # 保存为空格分隔的TXT文件（软件支持的格式）
            np.savetxt(
                output_path,
                output_data,
                fmt='%.6f',  # 保留6位小数
                delimiter=' ',  # 空格分隔
                encoding='utf-8'
            )
            
            self.progress_bar.setVisible(False)
            self.convert_btn.setEnabled(True)
            
            tip_text = ("；".join(tips)) if tips else ("无格式矫正")
            success_msg = f"{language_manager.get('conversion_success')} {output_path.name}"
            self.status_label.setText(success_msg + (f"（{tip_text}）" if tips else ""))
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            
            msg_text = f"文件已成功处理并保存为:\n{output_path}\n\n共处理 {len(output_data)} 行数据\n{('格式矫正: ' + tip_text) if tips else ''}" if language_manager.is_chinese() else f"File successfully processed and saved as:\n{output_path}\n\nProcessed {len(output_data)} rows of data\n{('Normalization: ' + tip_text) if tips else ''}"
            QMessageBox.information(self, language_manager.get('success'), msg_text)
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.convert_btn.setEnabled(True)
            self.status_label.setText(language_manager.get('conversion_failed'))
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            
            error_msg = f"{language_manager.get('conversion_failed')}:\n{str(e)}"
            QMessageBox.critical(self, language_manager.get('error'), error_msg)

# PyQt配置编辑器
def launch_config_editor_pyqt(parent):
    import configparser
    import os
    import shutil
    from datetime import datetime
    
    # 在 onefile 环境下，编辑器应操作可写位置的 config.ini（exe 同目录的 default/）
    cfg_dir = external_default_dir()
    os.makedirs(cfg_dir, exist_ok=True)
    CONFIG_FILE = os.path.join(cfg_dir, 'config.ini')

    # 如果外部 config 不存在，则尝试从内置资源复制一份出来，便于用户编辑
    if not os.path.exists(CONFIG_FILE):
        try:
            src_cfg = res_path('default', 'config.ini')
            if os.path.exists(src_cfg):
                shutil.copy(src_cfg, CONFIG_FILE)
        except Exception:
            pass

    if not os.path.exists(CONFIG_FILE):
        QMessageBox.critical(parent, "错误", f"未找到配置文件并且无法从内置资源复制：{CONFIG_FILE}")
        return
    
    dialog = QDialog(parent)
    dialog.setWindowTitle("Config.ini 编辑器")
    dialog.setGeometry(100, 100, 800, 600)
    
    layout = QVBoxLayout(dialog)
    
    # 选项卡
    tabs = QTabWidget()
    layout.addWidget(tabs)
    
    config = configparser.ConfigParser()
    config.optionxform = str
    
    # 解析注释
    comments = {}
    current_section = None
    pending_comments = []
    
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
        QMessageBox.critical(dialog, "编码错误", f"无法使用 UTF-8 编码读取 {CONFIG_FILE} 文件。\n错误信息: {e}")
        return
    
    config.read(CONFIG_FILE, encoding='utf-8')
    entries = {}
    comment_entries = {}
    
    def create_section_widget(section):
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 显示节注释
        sec_comments = comments.get(section, {}).get('comments', [])
        for comm in sec_comments:
            lbl = QLabel(f"# {comm}")
            lbl.setStyleSheet(f"color: {COLORS['secondary_text']}; font-style: italic;")
            scroll_layout.addWidget(lbl)
        
        # 表格
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["参数", "值", "解释"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        
        row = 0
        for key, value in config.items(section):
            table.insertRow(row)
            
            key_item = QTableWidgetItem(key)
            table.setItem(row, 0, key_item)
            
            if key in ['C1', 'C2']:
                value_item = QTableWidgetItem(str(value))
                value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row, 1, value_item)
            else:
                value_item = QTableWidgetItem(str(value))
                table.setItem(row, 1, value_item)
                entries[(section, key)] = value_item
            
            key_comments = comments.get(section, {}).get('keys', {}).get(key, [])
            comment_text = " ; ".join(key_comments) if key_comments else ""
            comment_item = QTableWidgetItem(comment_text)
            if key not in ['C1', 'C2']:
                comment_entries[(section, key)] = comment_item
            table.setItem(row, 2, comment_item)
            
            row += 1
        
        table.resizeColumnsToContents()
        scroll_layout.addWidget(table)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        return scroll, entries, comment_entries
    
    all_entries = {}
    all_comment_entries = {}
    
    for section in config.sections():
        scroll, section_entries, section_comments = create_section_widget(section)
        tabs.addTab(scroll, section)
        all_entries.update(section_entries)
        all_comment_entries.update(section_comments)
    
    entries = all_entries
    comment_entries = all_comment_entries
    
    def validate_inputs():
        for (section, key), item in entries.items():
            val = item.text().strip()
            if section == 'EXPIRATION' and key == 'EXPIRATION_DATE':
                try:
                    datetime.strptime(val, '%Y-%m-%d')
                except ValueError:
                    QMessageBox.critical(dialog, "输入错误", f"{key} 的格式应为 YYYY-MM-DD")
                    return False
            elif key.startswith('T_') or key.startswith('HC_') or key.startswith('S_') \
                 or key.startswith('WAVELENGTH') or key in ['KB', 'H', 'C']:
                try:
                    parts = [p.strip() for p in val.split(',')]
                    for part in parts:
                        if part:
                            float(part)
                except ValueError:
                    QMessageBox.critical(dialog, "输入错误", f"{key} 应为数值或数值列表（用逗号分隔）")
                    return False
        return True
    
    def save_config():
        if not validate_inputs():
            return
        
        backup_file = CONFIG_FILE + '.bak'
        try:
            shutil.copy(CONFIG_FILE, backup_file)
        except Exception as e:
            QMessageBox.critical(dialog, "备份失败", f"备份原文件失败：{e}")
            return
        
        for (section, key), item in entries.items():
            config.set(section, key, item.text().strip())
        
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                for section in config.sections():
                    sec_comms = comments.get(section, {}).get('comments', [])
                    for comm in sec_comms:
                        f.write(f"# {comm}\n")
                    f.write(f"[{section}]\n")
                    for key, value in config.items(section):
                        if key in ['C1', 'C2']:
                            key_comms = comments.get(section, {}).get('keys', {}).get(key, [])
                            for comm in key_comms:
                                f.write(f"# {comm}\n")
                            f.write(f"{key} = {value}\n")
                        else:
                            explanation = ""
                            if (section, key) in comment_entries:
                                explanation = comment_entries[(section, key)].text().strip()
                            if explanation:
                                for part in [p.strip() for p in explanation.split(';') if p.strip()]:
                                    f.write(f"# {part}\n")
                            f.write(f"{key} = {entries[(section, key)].text().strip()}\n")
                    f.write("\n")
            QMessageBox.information(dialog, "成功", "配置已成功保存。")
            dialog.accept()
        except Exception as e:
            QMessageBox.critical(dialog, "保存失败", f"保存配置文件失败：{e}\n尝试恢复备份文件。")
            try:
                shutil.copy(backup_file, CONFIG_FILE)
                QMessageBox.information(dialog, "恢复成功", "已恢复备份文件。")
            except Exception as restore_e:
                QMessageBox.critical(dialog, "恢复失败", f"恢复备份失败：{restore_e}")
    
    # 按钮
    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    save_btn = QPushButton("保存")
    save_btn.clicked.connect(save_config)
    cancel_btn = QPushButton("取消")
    cancel_btn.clicked.connect(dialog.reject)
    btn_layout.addWidget(save_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)
    
    dialog.setStyleSheet(STYLE_SHEET)
    dialog.exec_()

class EmissivitySolarCloudDialog(QDialog):
    """大气发射率-太阳光强云图对话框"""
    def __init__(self, parent, file_paths):
        super().__init__(parent)
        self.file_paths = file_paths.copy()
        self.setFixedSize(600, 300)
        
        language_manager.language_changed.connect(self.update_language)
        
        self.init_ui()
        self.update_language()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.title_label = TitleLabel("")
        layout.addWidget(self.title_label)
        
        input_card = CardFrame()
        input_card.setMinimumHeight(150)
        input_layout = QVBoxLayout(input_card)
        
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignCenter)
        input_layout.addWidget(self.info_label)
        
        self.execute_button = AnimatedButton("")
        self.execute_button.clicked.connect(self.run_cloud_calculation)
        input_layout.addWidget(self.execute_button, alignment=Qt.AlignCenter)
        
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        input_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        input_layout.addWidget(self.progress_bar)
        
        layout.addWidget(input_card)
        
        button_layout = QHBoxLayout()
        self.close_button = AnimatedButton("")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def update_language(self):
        """更新语言"""
        title = "大气发射率-太阳光强云图" if language_manager.is_chinese() else "Atmospheric Emissivity - Solar Irradiance Cloud Map"
        self.setWindowTitle(title)
        self.title_label.setText(title)
        
        info = ("点击下方按钮生成云图\n"
                "横轴：大气发射率 (0-1)\n"
                "纵轴：太阳光强 (0-1000 W/m²)\n"
                "颜色：辐射制冷功率 (W/m²)") if language_manager.is_chinese() else \
               ("Click button to generate cloud map\n"
                "X-axis: Atmospheric emissivity (0-1)\n"
                "Y-axis: Solar irradiance (0-1000 W/m²)\n"
                "Color: Cooling power (W/m²)")
        self.info_label.setText(info)
        
        self.execute_button.setText(language_manager.get('generate_cloud'))
        self.close_button.setText(language_manager.get('close'))
    
    def run_cloud_calculation(self):
        """执行云图计算"""
        try:
            self.execute_button.setEnabled(False)
            self.status_label.setText(language_manager.get('calculating_msg'))
            self.progress_bar.setVisible(True)
            QApplication.processEvents()
            
            # 调用计算函数
            generate_emissivity_solar_cloud(self.file_paths)
            
            self.status_label.setText(language_manager.get('calculation_complete'))
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, language_manager.get('error'), 
                                f"{language_manager.get('error')}: {e}")
            self.status_label.setText(language_manager.get('calculation_failed'))
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)

def generate_emissivity_solar_cloud(file_paths):
    """
    生成大气发射率-太阳光强云图
    横轴：大气发射率 (0-1)
    纵轴：太阳光强 (0-1000 W/m²)
    颜色：辐射制冷功率 (W/m²)
    """
    from scipy.optimize import minimize_scalar
    
    # 加载配置
    config = load_config(file_paths['config'])
    T_a1 = config['T_a1']
    T_a = T_a1 + 273.15  # 环境温度（K）
    sigma = 5.670374419e-8
    
    # 计算材料参数
    print("正在计算材料参数...")
    avg_emissivity, R_sol, R_sol1 = main_calculating_gui(file_paths)
    alpha_s = 1 - R_sol  # 太阳吸收率
    
    print(f"材料平均发射率: {avg_emissivity:.4f}")
    print(f"太阳吸收率: {alpha_s:.4f}")
    
    # 定义计算网格
    atm_emissivity_range = np.linspace(0, 1, 51)  # 大气发射率：0-100%
    solar_irradiance_range = np.linspace(0, 1000, 51)  # 太阳光强：0-1000 W/m²
    
    # 初始化结果矩阵
    cooling_power_matrix = np.zeros((len(solar_irradiance_range), len(atm_emissivity_range)))
    
    # 固定对流换热系数（可以根据需要调整）
    h_conv = 5.0  # W/(m²·K)
    
    print("开始计算云图数据...")
    
    # 计算每个点的辐射制冷功率
    for i, S_solar in enumerate(solar_irradiance_range):
        for j, emissivity_atm in enumerate(atm_emissivity_range):
            # 在薄膜温度等于环境温度时（ΔT=0）计算
            T_film = T_a  # 薄膜温度等于环境温度
            
            # 太阳辐射吸收
            P_solar = alpha_s * S_solar
            
            # 薄膜向外辐射（使用材料发射率）
            P_rad_out = avg_emissivity * sigma * T_film**4
            
            # 大气向下辐射（使用大气发射率）
            P_rad_in = avg_emissivity * emissivity_atm * sigma * T_a**4
            
            # 对流换热（ΔT=0时为0）
            P_conv = 0  # 因为温度相同
            
            # 净制冷功率
            P_cooling = P_rad_out - P_rad_in - P_solar + P_conv
            
            cooling_power_matrix[i, j] = P_cooling
        
        # 显示进度
        if (i + 1) % 10 == 0:
            print(f"进度: {(i+1)/len(solar_irradiance_range)*100:.0f}%")
    
    print("计算完成，正在绘制云图...")
    
    # 绘制云图
    from matplotlib.colors import LinearSegmentedColormap
    
    # 设置样式
    try:
        plt.style.use('seaborn-v0_8-whitegrid')
    except:
        try:
            plt.style.use('seaborn-whitegrid')
        except:
            pass
    
    plt.rcParams.update({
        'font.family': 'Arial',
        'font.size': 12,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'figure.figsize': (12, 10),
        'figure.dpi': 120
    })
    
    # 创建颜色映射（蓝-白-红）
    colors = [(0, 'navy'), (0.3, 'blue'), (0.5, 'white'), (0.7, 'red'), (1, 'darkred')]
    cmap = LinearSegmentedColormap.from_list('cooling_power', colors, N=256)
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(12, 9))
    
    # 创建网格
    X, Y = np.meshgrid(atm_emissivity_range, solar_irradiance_range)
    
    # 绘制填充等高线
    contourf = ax.contourf(X, Y, cooling_power_matrix, levels=50, cmap=cmap, alpha=0.9)
    
    # 绘制等高线
    contours = ax.contour(X, Y, cooling_power_matrix, levels=10, colors='black', 
                          alpha=0.4, linewidths=0.8)
    ax.clabel(contours, inline=True, fontsize=9, fmt='%.0f')
    
    # 添加颜色条
    cbar = fig.colorbar(contourf, ax=ax, pad=0.02)
    cbar.set_label('Cooling Power (W/m²)', fontsize=13, weight='bold')
    
    # 设置标签
    ax.set_xlabel('Atmospheric Emissivity', fontsize=13, weight='bold')
    ax.set_ylabel('Solar Irradiance (W/m²)', fontsize=13, weight='bold')
    ax.set_title(f'Radiative Cooling Power Cloud Map\n'
                 f'Material Emissivity: {avg_emissivity:.3f}, Solar Absorptance: {alpha_s:.3f}\n'
                 f'Ambient Temperature: {T_a1}°C, ΔT = 0°C',
                 fontsize=15, weight='bold', pad=15)
    
    # 添加网格
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # 添加零功率线（如果存在）
    try:
        zero_contour = ax.contour(X, Y, cooling_power_matrix, levels=[0], 
                                  colors='lime', linewidths=2.5, linestyles='--')
        # 检查是否有等高线（兼容不同matplotlib版本）
        if hasattr(zero_contour, 'collections') and len(zero_contour.collections) > 0:
            ax.clabel(zero_contour, inline=True, fontsize=10, fmt='Zero Line')
        elif hasattr(zero_contour, 'allsegs') and len(zero_contour.allsegs) > 0 and len(zero_contour.allsegs[0]) > 0:
            ax.clabel(zero_contour, inline=True, fontsize=10, fmt='Zero Line')
    except Exception:
        # 如果绘制零功率线失败，忽略错误继续执行
        pass
    
    # 添加信息框
    props = dict(boxstyle='round', facecolor='white', alpha=0.8)
    info_text = f"""Parameter Info:
- Emissivity: {avg_emissivity:.3f}
- Absorptance: {alpha_s:.3f}
- Ambient T: {T_a1}°C
- Film T = Ambient T"""
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes, 
            fontsize=10, verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    
    # 使用交互式窗口显示图表
    dialog = InteractivePlotWindow(fig, parent=None, title='Radiation Cooling Power Cloud Map')
    dialog.exec_()
    
    # 保存数据
    print("正在保存数据...")
    options = QFileDialog.Options()
    save_file_path, _ = QFileDialog.getSaveFileName(
        None, 
        "保存结果文件" if language_manager.is_chinese() else "Save Result File", 
        "", 
        "Excel files (*.xlsx)", 
        options=options
    )
    
    if save_file_path:
        # 创建DataFrame
        df = pd.DataFrame(
            cooling_power_matrix,
            index=np.round(solar_irradiance_range, 2),
            columns=np.round(atm_emissivity_range, 3)
        )
        df.index.name = 'Solar_Irradiance_W/m2'
        df.columns.name = 'Atmospheric_Emissivity'
        
        # 保存到Excel
        with pd.ExcelWriter(save_file_path) as writer:
            df.to_excel(writer, sheet_name='Cooling_Power')
            
            # 添加参数说明表
            params_df = pd.DataFrame({
                'Parameter': ['Material Emissivity', 'Solar Absorptance', 'Ambient Temperature (°C)', 
                             'Film Temperature (°C)', 'Delta T (°C)'],
                'Value': [f'{avg_emissivity:.4f}', f'{alpha_s:.4f}', f'{T_a1:.1f}', 
                         f'{T_a1:.1f}', '0.0']
            })
            params_df.to_excel(writer, sheet_name='Parameters', index=False)
        
        print(f'结果已保存到: {save_file_path}')
        QMessageBox.information(
            None, 
            language_manager.get('success'),
            f"{language_manager.get('data_saved')}: {save_file_path}"
        )

# 主程序入口
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion样式以获得更好的跨平台外观
    
    # 设置应用调色板
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS['background']))
    palette.setColor(QPalette.WindowText, QColor(COLORS['primary_text']))
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

