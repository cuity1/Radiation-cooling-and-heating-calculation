import os
import sys
import datetime
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import configparser
from itertools import cycle
from PIL import Image
import webbrowser
import time

# PyQt5 imports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QDialog, QLabel, QPushButton, 
                            QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QFileDialog, 
                            QMessageBox, QWidget, QTabWidget, QComboBox, QFrame, 
                            QScrollArea, QSizePolicy, QGroupBox, QProgressBar, QSplashScreen, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette, QPixmap, QLinearGradient, QPainter, QBrush, QPen, QCursor, QRadialGradient, QFontDatabase

# 全局样式表定义
GLOBAL_STYLE = """
QMainWindow, QDialog {
    background-color: #f4f7fa;
}

QLabel {
    color: #2c3e50;
    font-size: 12px;
}

QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #2c3e50;
    margin: 10px 0px;
}

QLabel#subtitle {
    font-size: 14px;
    color: #34495e;
    margin: 5px 0px;
}

QLabel#result {
    font-size: 14px;
    color: #2980b9;
    margin: 5px 0px;
    padding: 5px;
    background-color: rgba(236, 240, 241, 0.7);
    border-radius: 4px;
}

QLabel#status {
    color: #c0392b;
    font-weight: bold;
}

QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 30px;
}

QPushButton:hover {
    background-color: #2980b9;
}

QPushButton:pressed {
    background-color: #1a5276;
}

QPushButton:disabled {
    background-color: #bdc3c7;
    color: #7f8c8d;
}

QLineEdit {
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 5px;
    background-color: white;
    selection-background-color: #3498db;
}

QLineEdit:focus {
    border: 1px solid #3498db;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #bdc3c7;
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 15px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 5px;
    color: #2c3e50;
}

QTabWidget::pane {
    border: 1px solid #bdc3c7;
    background-color: white;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #ecf0f1;
    color: #7f8c8d;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 80px;
    padding: 8px;
}

QTabBar::tab:selected {
    background-color: white;
    color: #2c3e50;
    border: 1px solid #bdc3c7;
    border-bottom: none;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}

QTabBar::tab:hover {
    background-color: #d6dbdf;
}

QProgressBar {
    border: 1px solid #bdc3c7;
    border-radius: 3px;
    text-align: center;
    background-color: #ecf0f1;
}

QProgressBar::chunk {
    background-color: #3498db;
    width: 10px;
    margin: 0.5px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QWidget#scrollAreaWidgetContents {
    background-color: transparent;
}

QComboBox {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 5px;
    min-width: 6em;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-left-width: 1px;
    border-left-color: #bdc3c7;
    border-left-style: solid;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}

QComboBox::down-arrow {
    image: url(icons/arrow-down.png);
    width: 10px;
    height: 10px;
}

QComboBox QAbstractItemView {
    border: 1px solid #bdc3c7;
    selection-background-color: #3498db;
    selection-color: white;
    outline: 0;
}
"""

# 自定义动态按钮类
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
            # Show a pop-up window when a section is missing
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText(f"配置文件缺少部分: [{section}]")
            msg.setWindowTitle("配置文件错误")
            screen_geometry = QApplication.desktop().screenGeometry()
            x = (screen_geometry.width() - msg.width()) // 2
            msg.move(x, 300)
            msg.exec_()  # Display the message box
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
    expiration_date = datetime.datetime(2026, 6, 1)
    if current_date > expiration_date:
        QMessageBox.information(None, "过期通知", "此版本已过期，为了不影响计算精度，请进行版本更新。")
        url = "https://pan.baidu.com/s/1RwgC-En28zfwQtf9DOfw9A?pwd=USTC"
        webbrowser.open(url)
        sys.exit()
    else:
        print("仅需要有两个测试数据：涉及可见光波段的反射率和涉及大气窗口的发射率")
        print("软件会自动匹配对应波长，在txt文件中请不要出现任何汉字及英文！")

def select_file(parent, title, filetypes):
    """使用文件对话框选择文件"""
    options = QFileDialog.Options()
    file_filter = ";;".join([f"{desc} ({ext})" for desc, ext in filetypes])
    file_path, _ = QFileDialog.getOpenFileName(parent, title, "", file_filter, options=options)
    if not file_path:
        raise Exception("未选择文件")
    return file_path

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
    """插值光谱数据以匹配反射率波长点"""
    # 去除重复的波长
    unique_spec_wavelength, unique_indices = np.unique(spec_wavelength, return_index=True)
    unique_spec_values = spec_values[unique_indices]
    interp_func = interp1d(unique_spec_wavelength, unique_spec_values, kind='linear', fill_value="extrapolate")
    return interp_func(ref_wavelength)

def calculate_weighted_reflectance(reflectance, spectrum, wavelengths):
    """计算加权平均反射率"""
    numerator = np.trapz(reflectance * spectrum, wavelengths)
    denominator = np.trapz(spectrum, wavelengths)
    return numerator / denominator

def load_and_interpolate_emissivity(wavelength_csv, emissivity_txt, emissivity_atm_txt, wavelength_range=[8, 13]):
    """加载并插值发射率和大气发射率数据"""
    try:
        # 加载波长数据
        data_csv = pd.read_csv(wavelength_csv)
        X = data_csv.iloc[:, 0].to_numpy()

        # 加载样品发射率
        emissivity_data = pd.read_csv(emissivity_txt, delim_whitespace=True, header=None, names=['X2', 'emissivity'])
        if (emissivity_data['X2'] > 1000).any():
            emissivity_data['X2'] *= 0.001
        if (emissivity_data['emissivity'] > 2).any():
            emissivity_data['emissivity'] *= 0.01

        emissivity_interpolated = np.interp(X, emissivity_data['X2'], emissivity_data['emissivity'])
        # 加载大气透过率
        emissivity_atm_data = pd.read_csv(emissivity_atm_txt, delim_whitespace=True, header=None, names=['X3', 'emissivityatm'])
        emissivityatm_interpolated = np.interp(X, emissivity_atm_data['X3'], emissivity_atm_data['emissivityatm'])
        return X, emissivity_interpolated, emissivityatm_interpolated
    except Exception as e:
        raise Exception(f"加载发射率数据时出错: {e}")


def calculate_radiation_power(data1, data2, theta, wavelengths1, wavelengths2):
    """计算辐射功率"""
    tmat = data1[:, 1]  # 大气透过率
    with np.errstate(divide='ignore', invalid='ignore'):
        e_zmat = 1 - tmat ** (1. / np.cos(theta))  # 大气透过率
        e_zmat = np.nan_to_num(e_zmat, nan=0.0, posinf=0.0, neginf=0.0)
    e_smat = data2[:, 1]  # 薄膜发射率
    return e_zmat, e_smat

def create_declaration_file(default_directory, declare_file, email_contact):
    """在当前脚本所在的目录下创建声明文件。"""
    try:
        # 确保默认目录存在
        if not os.path.exists(default_directory):
            os.makedirs(default_directory)
        # 定义声明文件的路径
        file_path = os.path.join(default_directory, declare_file)
        
        # 定义文件内容
        content = f"""仅需要有两个测试数据：涉及可见光波段的反射率和涉及大气窗口的透过率。
在txt文件中仅出现数据，请不要存在任何汉字！软件会自动匹配数据
该软件免费分享，免费使用。如有疑问联系{email_contact}
诚信科研，使用此工具希望能够引用我的文章。"""
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f'声明文件已创建：{file_path}')
    except Exception as e:
        print(f'创建声明文件时出错: {e}')

def planck_lambda(wavelength, temperature):
    """
    计算黑体在给定波长和温度下的谱强度 I_BB(λ)。
    
    参数：
    wavelength (numpy.ndarray): 波长，单位为米。
    temperature (float): 温度，单位为开尔文。
    
    返回：
    numpy.ndarray: 黑体谱强度，单位为 W·sr^-1·m^-3。
    """
    h = 6.62607015e-34    # 普朗克常数，单位：J·s
    c = 3.0e8             # 光速，单位：m/s
    k = 1.380649e-23      # 玻尔兹曼常数，单位：J/K

    numerator = 2 * h * c**2
    denominator = (wavelength**5) * (np.exp((h * c) / (wavelength * k * temperature)) - 1)
    return numerator / denominator

def calculate_average_emissivity(wavelength, emissivity, temperature):
    """
    计算平均发射率。
    
    参数：
    wavelength (numpy.ndarray): 波长，单位为米。
    emissivity (numpy.ndarray): 发射率。
    temperature (float): 温度，单位为开尔文。
    
    返回：
    float: 平均发射率。
    """
    # 计算黑体谱强度

    # I_BB = planck_lambda(wavelength, temperature)
    I_BB = planck_lambda(wavelength, temperature)
    #I_BB = np.ones_like(I_BB) #黑体发射率减小
    # 计算分子和分母的积分
    
    numerator = np.trapz(I_BB * emissivity, wavelength)
    denominator = np.trapz(I_BB, wavelength)
    
    # 计算平均发射率
    average_emissivity = numerator / denominator

    return average_emissivity

def calculate_R_sol(file_paths, config):
    """Calculate the weighted average reflectance R_sol."""
    # Load reflectance data
    reflectance_data = load_reflectance(file_paths['reflectance'])
    
    # Load spectrum data
    spectrum_data = load_spectrum(file_paths['spectrum'])
    
    # Get wavelength range from config
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    
    # Filter wavelength range
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    
    # Interpolate spectrum data
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    
    # Calculate weighted average reflectance
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    
    return R_sol

class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        plt.style.use('ggplot')  # 使用 ggplot 风格提升图表外观
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor('#f4f7fa')  # 设置图表背景颜色
        self.axes = fig.add_subplot(111)
        super(MatplotlibCanvas, self).__init__(fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("辐射制冷/制热计算工具")
        self.setMinimumSize(800, 600)
        
        # 创建图标文件夹
        if not os.path.exists('icons'):
            os.makedirs('icons')
        
        # 设置全局样式表
        self.setStyleSheet(GLOBAL_STYLE)
        
        self.file_paths = {
            'config': 'default/config.ini',  # 固定配置文件路径
            'spectrum': 'default/AM1.5.dll', # 固定太阳辐照AM1.5文件路径
            'wavelength': 'default/wavelength.csv'
        }
        
        # 加载配置文件并进行过期检查
        try:
            self.config = load_config(self.file_paths['config'])
            check_expiration(self.config['EXPIRATION_DATE'], self.config['EMAIL_CONTACT'])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"初始化时出错: {e}")
            self.close()
            sys.exit(1)
        
        self.init_ui()
    
    def init_ui(self):
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = TitleLabel("辐射制冷/制热计算工具")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        main_layout.addWidget(title_label)
        
        # 文件选择部分
        file_card = CardFrame()
        file_layout = QVBoxLayout(file_card)
        
        file_title = QLabel("1：先选择所需的文件")
        file_title.setObjectName("subtitle")
        file_layout.addWidget(file_title)
        
        # 文件选择按钮组
        file_buttons_layout = QHBoxLayout()
        file_buttons_layout.setSpacing(15)
        
        # 反射率文件按钮
        reflectance_btn_container = QWidget()
        reflectance_layout = QVBoxLayout(reflectance_btn_container)
        reflectance_layout.setContentsMargins(0, 0, 0, 0)
        
        reflectance_icon = QLabel()
        reflectance_icon.setPixmap(self.get_icon_pixmap("document", "#3498db"))
        reflectance_icon.setAlignment(Qt.AlignCenter)
        reflectance_layout.addWidget(reflectance_icon)
        
        self.reflectance_button = AnimatedButton("选择反射率文件")
        self.reflectance_button.clicked.connect(self.select_reflectance)
        reflectance_layout.addWidget(self.reflectance_button)
        
        self.reflectance_status = QLabel("未选择")
        self.reflectance_status.setAlignment(Qt.AlignCenter)
        reflectance_layout.addWidget(self.reflectance_status)
        
        file_buttons_layout.addWidget(reflectance_btn_container)
        
        # 发射率文件按钮
        emissivity_btn_container = QWidget()
        emissivity_layout = QVBoxLayout(emissivity_btn_container)
        emissivity_layout.setContentsMargins(0, 0, 0, 0)
        
        emissivity_icon = QLabel()
        emissivity_icon.setPixmap(self.get_icon_pixmap("document", "#e74c3c"))
        emissivity_icon.setAlignment(Qt.AlignCenter)
        emissivity_layout.addWidget(emissivity_icon)
        
        self.emissivity_button = AnimatedButton("选择发射率文件")
        self.emissivity_button.clicked.connect(self.select_emissivity)
        emissivity_layout.addWidget(self.emissivity_button)
        
        self.emissivity_status = QLabel("未选择")
        self.emissivity_status.setAlignment(Qt.AlignCenter)
        emissivity_layout.addWidget(self.emissivity_status)
        
        file_buttons_layout.addWidget(emissivity_btn_container)
        
        # 大气透过率按钮
        atm_btn_container = QWidget()
        atm_layout = QVBoxLayout(atm_btn_container)
        atm_layout.setContentsMargins(0, 0, 0, 0)
        
        atm_icon = QLabel()
        atm_icon.setPixmap(self.get_icon_pixmap("cloud", "#2ecc71"))
        atm_icon.setAlignment(Qt.AlignCenter)
        atm_layout.addWidget(atm_icon)
        
        self.atm_emissivity_button = AnimatedButton("选择大气透过率")
        self.atm_emissivity_button.clicked.connect(self.select_atm_emissivity)
        atm_layout.addWidget(self.atm_emissivity_button)
        
        self.atm_status = QLabel("未选择")
        self.atm_status.setAlignment(Qt.AlignCenter)
        atm_layout.addWidget(self.atm_status)
        
        file_buttons_layout.addWidget(atm_btn_container)
        
        file_layout.addLayout(file_buttons_layout)
        main_layout.addWidget(file_card)
        
        # 功能选择部分
        function_card = CardFrame()
        function_layout = QVBoxLayout(function_card)
        
        function_title = QLabel("2：请选择要执行的功能")
        function_title.setObjectName("subtitle")
        function_layout.addWidget(function_title)
        
        # 功能按钮网格
        function_grid = QGridLayout()
        function_grid.setSpacing(15)
        
        # 功能按钮
        calculating_button = AnimatedButton("节能地图绘制计算")
        calculating_button.clicked.connect(self.open_calculating)
        function_grid.addWidget(calculating_button, 0, 0)
        
        cooling_button = AnimatedButton("辐射制冷功率计算")
        cooling_button.clicked.connect(self.open_cooling)
        function_grid.addWidget(cooling_button, 0, 1)
        
        heating_button = AnimatedButton("辐射制热功率计算")
        heating_button.clicked.connect(self.open_heating)
        function_grid.addWidget(heating_button, 1, 0)
        
        yuntu_button = AnimatedButton("风速与制冷效率云图")
        yuntu_button.clicked.connect(self.open_yuntu)
        function_grid.addWidget(yuntu_button, 1, 1)
        
        config_button = AnimatedButton("参数修改")
        config_button.clicked.connect(self.launch_config_editor)
        function_grid.addWidget(config_button, 2, 0)
        
        heating_vs_solar_button = AnimatedButton("光热转化效率计算")
        heating_vs_solar_button.clicked.connect(self.open_heating_vs_solar)
        function_grid.addWidget(heating_vs_solar_button, 2, 1)
        
        function_layout.addLayout(function_grid)
        main_layout.addWidget(function_card)
        
        # 设置底部版权信息
        copyright_label = QLabel(f"© {datetime.datetime.now().year} 辐射制冷/制热计算工具 QQ群：767753318 - 联系作者: {self.config['EMAIL_CONTACT']}")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #95a5a6; font-size: 13px;")
        main_layout.addWidget(copyright_label)
    
    def get_icon_pixmap(self, icon_type, color_hex):
        """生成简单的SVG图标并返回QPixmap"""
        size = 48
        if icon_type == "document":
            svg = f"""
            <svg width="{size}" height="{size}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path fill="{color_hex}" d="M14,2H6C4.9,2,4,2.9,4,4v16c0,1.1,0.9,2,2,2h12c1.1,0,2-0.9,2-2V8L14,2z M16,18H8v-2h8V18z M16,14H8v-2h8V14z M13,9V3.5L18.5,9H13z"/>
            </svg>
            """
        elif icon_type == "cloud":
            svg = f"""
            <svg width="{size}" height="{size}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path fill="{color_hex}" d="M19.35,10.04C18.67,6.59,15.64,4,12,4C9.11,4,6.6,5.64,5.35,8.04C2.34,8.36,0,10.91,0,14c0,3.31,2.69,6,6,6h13c2.76,0,5-2.24,5-5C24,12.36,21.95,10.22,19.35,10.04z"/>
            </svg>
            """
        else:  # 默认图标
            svg = f"""
            <svg width="{size}" height="{size}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <circle fill="{color_hex}" cx="12" cy="12" r="10"/>
            </svg>
            """
        
        pixmap = QPixmap()
        pixmap.loadFromData(bytes(svg, 'utf-8'))
        return pixmap
    
    def select_reflectance(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择反射率文件", "", "Text files (*.txt)"
            )
            if file_path:
                self.file_paths['reflectance'] = file_path
                self.reflectance_status.setText(os.path.basename(file_path))
                self.reflectance_status.setStyleSheet("color: #27ae60;")
                QMessageBox.information(self, "提示", f"已选择反射率文件: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def select_emissivity(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择发射率文件", "", "Text files (*.txt)"
            )
            if file_path:
                self.file_paths['emissivity'] = file_path
                self.emissivity_status.setText(os.path.basename(file_path))
                self.emissivity_status.setStyleSheet("color: #27ae60;")
                QMessageBox.information(self, "提示", f"已选择发射率文件: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def select_atm_emissivity(self):
        try:
            # 创建对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("选择大气透过率文件")
            dialog.setFixedSize(400, 250)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #f4f7fa;
                }
                QLabel {
                    color: #2c3e50;
                    font-size: 14px;
                    margin-bottom: 10px;
                }
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-weight: bold;
                    min-height: 40px;
                    min-width: 150px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1a5276;
                }
            """)
            
            layout = QVBoxLayout()
            layout.setSpacing(15)
            layout.setContentsMargins(30, 30, 30, 30)
            
            label = QLabel("请选择大气透过率文件：")
            label.setFont(QFont("Arial", 14))
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(20)
            
            sunny_layout = QVBoxLayout()
            sunny_icon = QLabel()
            sunny_icon.setPixmap(self.get_icon_pixmap("cloud", "#f39c12"))
            sunny_icon.setAlignment(Qt.AlignCenter)
            sunny_layout.addWidget(sunny_icon)
            
            btn_1 = AnimatedButton("晴朗")
            btn_1.clicked.connect(lambda: self.set_atm_file('1.dll', dialog))
            sunny_layout.addWidget(btn_1)
            btn_layout.addLayout(sunny_layout)
            
            cloudy_layout = QVBoxLayout()
            cloudy_icon = QLabel()
            cloudy_icon.setPixmap(self.get_icon_pixmap("cloud", "#7f8c8d"))
            cloudy_icon.setAlignment(Qt.AlignCenter)
            cloudy_layout.addWidget(cloudy_icon)
            
            btn_2 = AnimatedButton("少云")
            btn_2.clicked.connect(lambda: self.set_atm_file('2.dll', dialog))
            cloudy_layout.addWidget(btn_2)
            btn_layout.addLayout(cloudy_layout)
            
            layout.addLayout(btn_layout)
            dialog.setLayout(layout)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def set_atm_file(self, filename, dialog):
        self.file_paths['atm_emissivity'] = os.path.join('default', filename)
        self.atm_status.setText(filename)
        self.atm_status.setStyleSheet("color: #27ae60;")
        dialog.accept()
    
    def check_all_files(self, required_keys):
        """检查所有必需的文件是否已选择"""
        missing = [key for key in required_keys if key not in self.file_paths or not self.file_paths[key]]
        if missing:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{', '.join(missing)}")
    
    def open_calculating(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            dialog = CalculatingDialog(self, self.file_paths)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def open_cooling(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            dialog = CoolingDialog(self, self.file_paths)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def open_heating(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            dialog = HeatingDialog(self, self.file_paths)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def open_yuntu(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            dialog = WindCoolingPlotDialog(self, self.file_paths)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def launch_config_editor(self):
        try:
            editor = ConfigEditorDialog(self)
            editor.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
    
    def open_heating_vs_solar(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            
            # 显示进度对话框
            progress_dialog = ProgressDialog("计算中", "正在计算光热与光照关系，请稍候...", self)
            progress_dialog.show()
            QApplication.processEvents()
            
            # 执行计算
            main_theoretical_heating_vs_solar(self.file_paths)
            
            # 关闭进度对话框
            progress_dialog.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

class CoolingDialog(QDialog):
    def __init__(self, parent, file_paths):
        super().__init__(parent)
        self.setWindowTitle("辐射制冷功率计算")
        self.setFixedSize(600, 400)
        self.file_paths = file_paths.copy()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = TitleLabel("辐射制冷功率计算")
        layout.addWidget(title_label)
        
        # 说明文本
        info_label = QLabel("点击下方按钮开始计算辐射制冷功率。计算过程可能需要几分钟，请耐心等待。")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 结果卡片
        result_card = CardFrame()
        result_layout = QVBoxLayout(result_card)
        
        # 执行按钮
        self.execute_button = AnimatedButton("执行计算")
        self.execute_button.clicked.connect(self.run_cooling)
        result_layout.addWidget(self.execute_button, alignment=Qt.AlignCenter)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为持续转动
        self.progress_bar.setVisible(False)
        result_layout.addWidget(self.progress_bar)
        
        # 结果标签
        self.result_label = QLabel("")
        self.result_label.setObjectName("result")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setMinimumHeight(100)
        result_layout.addWidget(self.result_label)
        
        layout.addWidget(result_card)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        close_button = AnimatedButton("关闭")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def run_cooling(self):
        try:
            # 禁用执行按钮并显示进度条
            self.execute_button.setEnabled(False)
            self.status_label.setText("正在计算，请稍候...")
            self.progress_bar.setVisible(True)
            QApplication.processEvents()  # 确保UI更新
            
            # 执行计算
            avg_emissivity, R_sol, R_sol1, Power_0 = main_cooling_gui(self.file_paths)
            
            # 更新状态和结果
            self.status_label.setText("计算完成！")
            self.progress_bar.setVisible(False)
            
            # 设置美化后的结果显示
            result_html = f"""
            <div style="text-align: center; padding: 10px;">
                <div style="font-size: 18px; font-weight: bold; color: #2980b9; margin-bottom: 15px;">计算结果</div>
                <div style="font-size: 16px; color: #27ae60; margin-bottom: 5px;">冷却功率 = {Power_0:.4f} W/m²</div>
            </div>
            """
            self.result_label.setText(result_html)
            self.execute_button.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算过程中出现错误: {e}")
            self.status_label.setText("计算失败！")
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)

class CalculatingDialog(QDialog):
    def __init__(self, parent, file_paths):
        super().__init__(parent)
        self.setWindowTitle("地图绘制参数计算")
        self.setFixedSize(600, 400)
        self.file_paths = file_paths.copy()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title_label = TitleLabel("节能地图绘制计算")
        layout.addWidget(title_label)
        
        # 说明文本
        info_label = QLabel("点击下方按钮开始计算节能地图绘制所需的参数。")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 结果卡片
        result_card = CardFrame()
        result_layout = QVBoxLayout(result_card)
        
        # 执行按钮
        self.execute_button = AnimatedButton("执行计算")
        self.execute_button.clicked.connect(self.run_calculating)
        result_layout.addWidget(self.execute_button, alignment=Qt.AlignCenter)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为持续转动
        self.progress_bar.setVisible(False)
        result_layout.addWidget(self.progress_bar)
        
        # 结果标签
        self.result_label = QLabel("")
        self.result_label.setObjectName("result")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setMinimumHeight(120)
        result_layout.addWidget(self.result_label)
        
        layout.addWidget(result_card)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        close_button = AnimatedButton("关闭")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def run_calculating(self):
        try:
            # 禁用执行按钮并显示进度条
            self.execute_button.setEnabled(False)
            self.status_label.setText("正在计算，请稍候...")
            self.progress_bar.setVisible(True)
            QApplication.processEvents()  # 确保UI更新
            
            # 执行计算
            avg_emissivity, R_sol, R_sol1 = main_calculating_gui(self.file_paths)
            
            # 更新状态和结果
            self.status_label.setText("计算完成！")
            self.progress_bar.setVisible(False)
            
            # 设置美化后的结果显示
            result_html = f"""
            <div style="text-align: center; padding: 8px;">
                <div style="font-size: 18px; font-weight: bold; color: #2980b9; margin-bottom: 8px;">计算结果</div>
                <div style="font-size: 14px; color: #2c3e50; margin-bottom: 5px;">材料加权发射率 = <span style="color: #27ae60; font-weight: bold;">{avg_emissivity:.4f}</span></div>
                <div style="font-size: 14px; color: #2c3e50; margin-bottom: 5px;">太阳光谱反射率 = <span style="color: #27ae60; font-weight: bold;">{R_sol:.4f}</span></div>
                <div style="font-size: 14px; color: #2c3e50; margin-bottom: 5px;">可见光谱反射率 = <span style="color: #27ae60; font-weight: bold;">{R_sol1:.4f}</span></div>
                <div style="font-size: 12px; color: #e74c3c; margin-bottom: 5px;">节能地图绘制联系微信 cuity_</div>
            </div>
            """
            self.result_label.setWordWrap(True)
            self.result_label.setText(result_html)
            self.execute_button.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算过程中出现错误: {e}")
            self.status_label.setText("计算失败！")
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)

class HeatingDialog(QDialog):
    def __init__(self, parent, file_paths):
        super().__init__(parent)
        self.setWindowTitle("辐射制热功率计算")
        self.setFixedSize(600, 400)
        self.file_paths = file_paths.copy()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = TitleLabel("辐射制热功率计算")
        layout.addWidget(title_label)
        
        # 说明文本
        info_label = QLabel("点击下方按钮开始计算辐射制热功率。计算过程可能需要几分钟，请耐心等待。")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 结果卡片
        result_card = CardFrame()
        result_layout = QVBoxLayout(result_card)
        
        # 执行按钮
        self.execute_button = AnimatedButton("执行计算")
        self.execute_button.clicked.connect(self.run_heating)
        result_layout.addWidget(self.execute_button, alignment=Qt.AlignCenter)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为持续转动
        self.progress_bar.setVisible(False)
        result_layout.addWidget(self.progress_bar)
        
        # 结果标签
        self.result_label = QLabel("")
        self.result_label.setObjectName("result")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setMinimumHeight(100)
        result_layout.addWidget(self.result_label)
        
        layout.addWidget(result_card)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        close_button = AnimatedButton("关闭")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def run_heating(self):
        try:
            # 禁用执行按钮并显示进度条
            self.execute_button.setEnabled(False)
            self.status_label.setText("正在计算，请稍候...")
            self.progress_bar.setVisible(True)
            QApplication.processEvents()  # 确保UI更新
            
            # 执行计算
            Power_0 = main_heating_gui(self.file_paths)
            
            # 更新状态和结果
            self.status_label.setText("计算完成！")
            self.progress_bar.setVisible(False)
            
            # 设置美化后的结果显示
            result_html = f"""
            <div style="text-align: center; padding: 10px;">
                <div style="font-size: 18px; font-weight: bold; color: #2980b9; margin-bottom: 15px;">计算结果</div>
                <div style="font-size: 16px; color: #e74c3c; margin-bottom: 5px;">加热功率 = {Power_0:.4f} W/m²</div>
            </div>
            """
            self.result_label.setText(result_html)
            self.execute_button.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算过程中出现错误: {e}")
            self.status_label.setText("计算失败！")
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)

class WindCoolingPlotDialog(QDialog):
    def __init__(self, parent, file_paths):
        super().__init__(parent)
        self.setWindowTitle("风速与制冷效率云图")
        self.setFixedSize(600, 300)
        self.file_paths = file_paths.copy()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = TitleLabel("风速与制冷效率云图")
        layout.addWidget(title_label)
        
        # 输入区域
        input_card = CardFrame()
        input_card.setMinimumHeight(180) 
        input_layout = QVBoxLayout(input_card)
        
        input_title = QLabel("请输入太阳辐照度参数")
        input_title.setObjectName("subtitle")
        input_title.setAlignment(Qt.AlignCenter)
        input_layout.addWidget(input_title)
        
        # 输入框部分
        input_form = QHBoxLayout()
        input_form.setSpacing(10)
        
        label = QLabel("太阳辐照度 S_solar (W/m²):")
        input_form.addWidget(label)
        
        self.s_solar_entry = QLineEdit()
        self.s_solar_entry.setPlaceholderText("例如: 1000")
        input_form.addWidget(self.s_solar_entry)
        
        input_layout.addLayout(input_form)
        
        # 执行按钮
        self.execute_button = AnimatedButton("生成云图")
        self.execute_button.clicked.connect(self.run_wind_cooling_plot)
        input_layout.addWidget(self.execute_button, alignment=Qt.AlignCenter)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        input_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为持续转动
        self.progress_bar.setVisible(False)
        input_layout.addWidget(self.progress_bar)
        
        layout.addWidget(input_card)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        close_button = AnimatedButton("关闭")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def run_wind_cooling_plot(self):
        try:
            # 获取输入值
            s_solar_str = self.s_solar_entry.text()
            S_solar = float(s_solar_str)
            
            # 禁用执行按钮并显示进度条
            self.execute_button.setEnabled(False)
            self.status_label.setText("正在计算，请稍候...")
            self.progress_bar.setVisible(True)
            QApplication.processEvents()  # 确保UI更新
            
            # 执行计算
            generate_wind_cooling_plot(self.file_paths, S_solar)
            
            # 更新状态
            self.status_label.setText("计算完成！")
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)
        except ValueError:
            QMessageBox.critical(self, "错误", "请输入有效的太阳辐照度数值")
            self.execute_button.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算过程中出现错误: {e}")
            self.status_label.setText("计算失败！")
            self.progress_bar.setVisible(False)
            self.execute_button.setEnabled(True)

class ConfigEditorDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Config.ini 编辑器")
        self.setMinimumSize(800, 600)
        
        self.CONFIG_FILE = 'default/config.ini'
        if not os.path.exists(self.CONFIG_FILE):
            QMessageBox.critical(self, "错误", f"找不到 {self.CONFIG_FILE} 文件。")
            self.reject()
            return
        
        # 初始化配置解析器，不转换键为小写
        self.config = configparser.ConfigParser()
        self.config.optionxform = str
        
        # 用于保存注释信息
        self.comments = {}
        
        # 解析文件提取注释
        self.parse_config_with_comments()
        
        # 使用 configparser 读取配置
        self.config.read(self.CONFIG_FILE, encoding='utf-8')
        
        # 存储可编辑项的 Entry 控件
        self.entries = {}
        self.comment_entries = {}
        
        self.init_ui()
    
    def parse_config_with_comments(self):
        current_section = None
        pending_comments = []
        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
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
                        self.comments.setdefault(section, {'comments': [], 'keys': {}})
                        if pending_comments:
                            self.comments[section]['comments'].extend(pending_comments)
                        pending_comments.clear()
                    elif '=' in stripped and current_section is not None:
                        key = stripped.split('=', 1)[0].strip()
                        self.comments[current_section]['keys'].setdefault(key, [])
                        if pending_comments:
                            self.comments[current_section]['keys'][key].extend(pending_comments)
                        pending_comments.clear()
                    else:
                        pending_comments.clear()
        except UnicodeDecodeError as e:
            QMessageBox.critical(self, "编码错误", f"无法使用 UTF-8 编码读取 {self.CONFIG_FILE} 文件。\n错误信息: {e}")
            self.reject()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = TitleLabel("配置文件编辑器")
        layout.addWidget(title_label)
        
        # 创建选项卡小部件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                background-color: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                color: #7f8c8d;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 80px;
                padding: 8px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-bottom: none;
            }
            QTabBar::tab:!selected {
                margin-top: 2px;
            }
            QTabBar::tab:hover {
                background-color: #d6dbdf;
            }
        """)
        
        # 为每个配置节创建选项卡
        for section in self.config.sections():
            tab = QWidget()
            self.create_section_tab(tab, section)
            self.tab_widget.addTab(tab, section)
        
        layout.addWidget(self.tab_widget)
        
        # 添加底部按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        save_button = AnimatedButton("保存")
        save_button.clicked.connect(self.save_config)
        button_layout.addWidget(save_button)
        
        cancel_button = AnimatedButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def create_section_tab(self, parent, section):
        # 创建滚动区域
        scroll_area = QScrollArea(parent)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # 创建内容控件
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        layout = QGridLayout(content_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        row = 0
        
        # 显示节前注释
        sec_comments = self.comments.get(section, {}).get('comments', [])
        if sec_comments:
            comment_box = QGroupBox("节注释")
            comment_layout = QVBoxLayout(comment_box)
            
            for comm in sec_comments:
                comment_label = QLabel(f"# {comm}")
                comment_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
                comment_layout.addWidget(comment_label)
            
            layout.addWidget(comment_box, row, 0, 1, 3)
            row += 1
        
        # 列标题
        header_layout = QHBoxLayout()
        
        param_label = QLabel("参数")
        param_label.setFont(QFont("Arial", 10, QFont.Bold))
        param_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(param_label)
        
        value_label = QLabel("值")
        value_label.setFont(QFont("Arial", 10, QFont.Bold))
        value_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(value_label)
        
        desc_label = QLabel("解释")
        desc_label.setFont(QFont("Arial", 10, QFont.Bold))
        desc_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(desc_label)
        
        layout.addLayout(header_layout, row, 0, 1, 3)
        row += 1
        
        # 添加分割线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #bdc3c7;")
        layout.addWidget(separator, row, 0, 1, 3)
        row += 1
        
        # 添加配置项
        for key, value in self.config.items(section):
            key_comments = self.comments.get(section, {}).get('keys', {}).get(key, [])
            comment_text = " ; ".join(key_comments) if key_comments else ""
            
            entry_container = QWidget()
            entry_layout = QHBoxLayout(entry_container)
            entry_layout.setContentsMargins(0, 0, 0, 0)
            
            # 对于只读的常量，直接显示标签
            if key in ['C1', 'C2']:
                key_label = QLabel(key)
                key_label.setFixedWidth(100)
                key_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
                entry_layout.addWidget(key_label)
                
                value_label = QLabel(value)
                value_label.setStyleSheet("color: #7f8c8d;")
                entry_layout.addWidget(value_label)
                
                comment_label = QLabel(comment_text)
                comment_label.setStyleSheet("color: #95a5a6; font-style: italic;")
                entry_layout.addWidget(comment_label)
            else:
                # 参数名标签
                key_label = QLabel(key)
                key_label.setFixedWidth(100)
                key_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
                entry_layout.addWidget(key_label)
                
                # 值的编辑框
                value_edit = QLineEdit(value)
                value_edit.setStyleSheet("""
                    QLineEdit {
                        border: 1px solid #bdc3c7;
                        border-radius: 4px;
                        padding: 5px;
                        background-color: white;
                    }
                    QLineEdit:focus {
                        border: 1px solid #3498db;
                    }
                """)
                entry_layout.addWidget(value_edit)
                self.entries[(section, key)] = value_edit
                
                # 解释的编辑框
                comment_edit = QLineEdit(comment_text)
                comment_edit.setStyleSheet("""
                    QLineEdit {
                        border: 1px solid #bdc3c7;
                        border-radius: 4px;
                        padding: 5px;
                        background-color: white;
                        font-style: italic;
                        color: #7f8c8d;
                    }
                    QLineEdit:focus {
                        border: 1px solid #3498db;
                    }
                """)
                entry_layout.addWidget(comment_edit)
                self.comment_entries[(section, key)] = comment_edit
            
            layout.addWidget(entry_container, row, 0, 1, 3)
            row += 1
        
        # 设置主布局
        main_layout = QVBoxLayout(parent)
        main_layout.addWidget(scroll_area)
    
    def validate_inputs(self):
        """验证输入数据"""
        for (section, key), entry in self.entries.items():
            val = entry.text().strip()
            if section == 'EXPIRATION' and key == 'EXPIRATION_DATE':
                try:
                    datetime.datetime.strptime(val, '%Y-%m-%d')
                except ValueError:
                    QMessageBox.critical(self, "输入错误", f"{key} 的格式应为 YYYY-MM-DD")
                    return False
            elif key.startswith('T_') or key.startswith('HC_') or key.startswith('S_') \
                 or key.startswith('WAVELENGTH') or key in ['KB', 'H', 'C']:
                try:
                    parts = [p.strip() for p in val.split(',')]
                    for part in parts:
                        if part:
                            float(part)
                except ValueError:
                    QMessageBox.critical(self, "输入错误", f"{key} 应为数值或数值列表（用逗号分隔）")
                    return False
        return True
    
    def save_config(self):
        """保存配置文件"""
        if not self.validate_inputs():
            return
        
        # 显示进度对话框
        progress_dialog = ProgressDialog("保存中", "正在保存配置文件...", self)
        progress_dialog.show()
        QApplication.processEvents()
        
        # 备份原文件
        backup_file = self.CONFIG_FILE + '.bak'
        try:
            import shutil
            shutil.copy(self.CONFIG_FILE, backup_file)
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "备份失败", f"备份原文件失败：{e}")
            return
        
        # 更新 config 对象中的值
        for (section, key), entry in self.entries.items():
            self.config.set(section, key, entry.text().strip())
        
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                for section in self.config.sections():
                    # 写入节级注释
                    sec_comms = self.comments.get(section, {}).get('comments', [])
                    for comm in sec_comms:
                        f.write(f"# {comm}\n")
                    f.write(f"[{section}]\n")
                    # 遍历该节的每个键
                    for key, value in self.config.items(section):
                        if key in ['C1', 'C2']:
                            key_comms = self.comments.get(section, {}).get('keys', {}).get(key, [])
                            for comm in key_comms:
                                f.write(f"# {comm}\n")
                            f.write(f"{key} = {value}\n")
                        else:
                            explanation = ""
                            if (section, key) in self.comment_entries:
                                explanation = self.comment_entries[(section, key)].text().strip()
                            if explanation:
                                for part in [p.strip() for p in explanation.split(';') if p.strip()]:
                                    f.write(f"# {part}\n")
                            f.write(f"{key} = {self.entries[(section, key)].text().strip()}\n")
                    f.write("\n")
            progress_dialog.close()
            QMessageBox.information(self, "成功", "配置已成功保存。")
            self.accept()
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "保存失败", f"保存配置文件失败：{e}\n尝试恢复备份文件。")
            try:
                import shutil
                shutil.copy(backup_file, self.CONFIG_FILE)
                QMessageBox.information(self, "恢复成功", "已恢复备份文件。")
            except Exception as restore_e:
                QMessageBox.critical(self, "恢复失败", f"恢复备份失败：{restore_e}")

def calculate_convection_coefficient(wind_speed, delta_T, T_a, L_char=1.0):
    """
    计算考虑自然对流和强制对流的对流换热系数
    
    Parameters:
    wind_speed: 风速 (m/s)
    delta_T: 温度差 (K)
    T_a: 环境温度 (K)
    L_char: 特征长度 (m)，默认1.0m
    
    Returns:
    h_conv: 对流换热系数 (W/m²·K)
    """
    # 空气物性参数（在环境温度下）
    T_film = T_a + delta_T / 2  # 膜温度
    
    # 空气物性参数的温度相关性（简化模型）
    rho = 1.225 * (273.15 / T_film)  # 密度 kg/m³
    mu = 1.81e-5 * (T_film / 273.15)**0.7  # 动力粘度 Pa·s
    k_air = 0.024 * (T_film / 273.15)**0.8  # 导热系数 W/m·K
    cp = 1005  # 比热容 J/kg·K
    nu = mu / rho  # 运动粘度 m²/s
    alpha = k_air / (rho * cp)  # 热扩散率 m²/s
    Pr = nu / alpha  # 普朗特数
    
    # 重力加速度和体积膨胀系数
    g = 9.81  # m/s²
    beta = 1 / T_film  # 理想气体的体积膨胀系数 1/K
    
    # 自然对流计算
    if abs(delta_T) > 0.1:  # 只有当温度差足够大时才考虑自然对流
        Ra = g * beta * abs(delta_T) * L_char**3 / (nu * alpha)  # 瑞利数
        
        # 水平平板自然对流 (适用于辐射制冷板)
        if Ra < 1e7:  # 层流
            Nu_nat = 0.54 * Ra**0.25
        else:  # 湍流
            Nu_nat = 0.15 * Ra**(1/3)
        
        h_natural = Nu_nat * k_air / L_char
    else:
        h_natural = 0
    
    # 强制对流计算
    if wind_speed > 0.1:  # 只有当风速足够大时才考虑强制对流
        Re = wind_speed * L_char / nu  # 雷诺数
        
        # 平板强制对流
        if Re < 5e5:  # 层流
            Nu_forced = 0.664 * Re**0.5 * Pr**(1/3)
        else:  # 湍流
            Nu_forced = 0.037 * Re**0.8 * Pr**(1/3)
        
        h_forced = Nu_forced * k_air / L_char
    else:
        h_forced = 0
    
    # 混合对流：自然对流和强制对流的组合
    # 使用Churchill-Usagi方法
    n = 3  # 指数，通常取3或4
    h_conv = (h_natural**n + h_forced**n)**(1/n)
    
    return max(h_conv, 1.0)  # 设置最小值防止数值问题


def generate_wind_cooling_plot(file_paths, S_solar):
    """生成风速与制冷效率云图"""
    from scipy.optimize import brentq, minimize_scalar
    
    # 加载配置文件
    config = load_config(file_paths['config'])
    
    # 环境温度
    T_a1 = config['T_a1']
    T_a = T_a1 + 273.15  # 绝对温度 K
    XMIN = -100  # 寻找解析域
    XMAX = 300
    sigma = 5.670374419e-8 
    emissivity_variable = np.linspace(0, 1, num=50)  # 发射率从0.1到0.9
    wind = np.linspace(0, 5, num=50)  # 风速
    
    avg_emissivity, R_sol, R_sol1 = main_calculating_gui(file_paths)
    alpha_s = 1 - R_sol  # 吸收率

    # 初始化存储温度差和对流换热系数的数组
    delta_T_values = np.zeros((len(emissivity_variable), len(wind)))
    hc_values_matrix = np.zeros((len(emissivity_variable), len(wind)))

    # 定义净辐射冷却功率为零时的方程
    def p_net_equation(delta_T, emissivity, wind_speed):
        # 根据当前温度差和风速计算对流换热系数
        h_conv = calculate_convection_coefficient(wind_speed, delta_T, T_a)
        T_s = T_a + delta_T
        return avg_emissivity * sigma * T_s**4 - emissivity * sigma * T_a**4 + h_conv * delta_T - alpha_s * S_solar

    # 定义寻找近似解的函数
    def find_approximate_solution(emissivity, wind_speed, delta_T_min, delta_T_max):
        # 使用 minimize_scalar 寻找使 |p_net| 最小的 delta_T
        result = minimize_scalar(lambda delta_T: abs(p_net_equation(delta_T, emissivity, wind_speed)),
                                bounds=(delta_T_min, delta_T_max),
                                method='bounded')
        if result.success:
            return result.x
        else:
            return np.nan  # 如果优化失败，返回 NaN

    # 对于每个发射率和风速，求解对应的温度差 delta_T
    for i, emissivity in enumerate(emissivity_variable):
        for j, wind_speed in enumerate(wind):
            try:
                # 使用迭代方法求解，因为h_conv依赖于delta_T
                # 初始猜测
                delta_T_guess = -10.0
                
                # 迭代求解
                for iteration in range(10):  # 最多迭代10次
                    h_conv = calculate_convection_coefficient(wind_speed, delta_T_guess, T_a)
                    
                    # 使用当前的h_conv求解delta_T
                    def p_net_fixed_h(delta_T):
                        T_s = T_a + delta_T
                        return avg_emissivity * sigma * T_s**4 - emissivity * sigma * T_a**4 + h_conv * delta_T - alpha_s * S_solar
                    
                    try:
                        delta_T_new = brentq(p_net_fixed_h, XMIN, XMAX)
                    except ValueError:
                        # 如果brentq失败，使用minimize_scalar
                        result = minimize_scalar(lambda delta_T: abs(p_net_fixed_h(delta_T)),
                                               bounds=(XMIN, XMAX), method='bounded')
                        delta_T_new = result.x if result.success else np.nan
                        break
                    
                    # 检查收敛性
                    if abs(delta_T_new - delta_T_guess) < 0.01:  # 收敛判据
                        break
                    
                    delta_T_guess = delta_T_new
                
                delta_T_values[i, j] = delta_T_new
                hc_values_matrix[i, j] = calculate_convection_coefficient(wind_speed, delta_T_new, T_a)
                
            except (ValueError, RuntimeError):
                # 如果所有方法都失败，使用近似解
                approx_solution = find_approximate_solution(emissivity, wind_speed, XMIN, XMAX)
                delta_T_values[i, j] = approx_solution
                if not np.isnan(approx_solution):
                    hc_values_matrix[i, j] = calculate_convection_coefficient(wind_speed, approx_solution, T_a)
                else:
                    hc_values_matrix[i, j] = np.nan

    # 自定义颜色映射，提高云图的视觉效果
    from matplotlib.colors import LinearSegmentedColormap
    
    # 定义一个蓝-白-红的渐变颜色映射
    colors = [(0, 'darkblue'), (0.25, 'blue'), (0.5, 'white'), (0.75, 'red'), (1, 'darkred')]
    cmap_name = 'temp_diff'
    cm = LinearSegmentedColormap.from_list(cmap_name, colors, N=100)
    
    # 设置Matplotlib的风格和字体
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.family': 'Arial',
        'font.size': 12,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'figure.titlesize': 16,
        'figure.figsize': (12, 10),
        'figure.dpi': 120
    })
    
    # 创建子图
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    X_mesh, Y_mesh = np.meshgrid(wind, emissivity_variable)
    
    # 绘制温度差云图
    cp1 = ax1.contourf(X_mesh, Y_mesh, delta_T_values, levels=100, cmap=cm, alpha=0.9)
    contours1 = ax1.contour(X_mesh, Y_mesh, delta_T_values, levels=10, colors='black', alpha=0.5, linewidths=0.5)
    ax1.clabel(contours1, inline=True, fontsize=8, fmt='%.1f')
    
    cbar1 = fig.colorbar(cp1, ax=ax1, pad=0.01)
    cbar1.set_label('ΔT (°C)', fontsize=12, weight='bold')
    
    ax1.set_xlabel('Wind speed (m/s)', fontsize=12, weight='bold')
    ax1.set_ylabel('Atmospheric emissivity', fontsize=12, weight='bold')
    ax1.set_title('Temperature Difference', fontsize=14, weight='bold')
    ax1.grid(True, linestyle='--', alpha=0.6)
    
    # 绘制对流换热系数云图
    cp2 = ax2.contourf(X_mesh, Y_mesh, hc_values_matrix, levels=100, cmap='viridis', alpha=0.9)
    contours2 = ax2.contour(X_mesh, Y_mesh, hc_values_matrix, levels=10, colors='black', alpha=0.5, linewidths=0.5)
    ax2.clabel(contours2, inline=True, fontsize=8, fmt='%.1f')
    
    cbar2 = fig.colorbar(cp2, ax=ax2, pad=0.01)
    cbar2.set_label('h_conv (W/m²·K)', fontsize=12, weight='bold')
    
    ax2.set_xlabel('Wind speed (m/s)', fontsize=12, weight='bold')
    ax2.set_ylabel('Atmospheric emissivity', fontsize=12, weight='bold')
    ax2.set_title('Convection Coefficient', fontsize=14, weight='bold')
    ax2.grid(True, linestyle='--', alpha=0.6)
    
    # 添加总标题
    fig.suptitle(f'Wind Speed and Cooling Efficiency Analysis (S_solar = {S_solar} W/m²)', 
                fontsize=16, weight='bold', y=0.95)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    plt.show(block=False)
    plt.pause(5)
    plt.close(fig)
    
    # 保存到 CSV
    options = QFileDialog.Options()
    save_file_path, _ = QFileDialog.getSaveFileName(
        None, "保存结果文件", "", "CSV files (*.csv)", options=options
    )
    
    if save_file_path:
        # 保存温度差数据
        df_temp = pd.DataFrame(delta_T_values, index=np.round(emissivity_variable, 3), columns=np.round(wind, 3))
        df_temp.index.name = 'emissivity'
        df_temp.columns.name = 'wind_speed'
        
        # 保存对流换热系数数据
        df_hconv = pd.DataFrame(hc_values_matrix, index=np.round(emissivity_variable, 3), columns=np.round(wind, 3))
        df_hconv.index.name = 'emissivity'
        df_hconv.columns.name = 'wind_speed'
        
        # 使用多个工作表保存
        with pd.ExcelWriter(save_file_path.replace('.csv', '.xlsx')) as writer:
            df_temp.to_excel(writer, sheet_name='Temperature_Difference')
            df_hconv.to_excel(writer, sheet_name='Convection_Coefficient')
        
        print(f'结果已保存到 {save_file_path.replace(".csv", ".xlsx")}')
        print('包含两个工作表：Temperature_Difference 和 Convection_Coefficient')

def main_theoretical_heating_vs_solar(file_paths):
    """
    计算并绘制：在环境温度 Ta 从 -100°C 到 100°C（薄膜与环境温度相同，ΔT=0）条件下，
    理论辐射制热功率与太阳辐照度 S_solar 之间的关系。
    """
    # 加载配置文件及关键参数
    config = load_config(file_paths['config'])
    C1 = config['C1']
    C2 = config['C2']
    
    # 定义环境温度范围（单位：°C）以及太阳辐照度范围（W/m²）
    T_a_range = np.linspace(-100, 100, num=21)  # 例如：0,10,20,...,60°C
    S_solar_range = np.linspace(0, 1200, num=49)  # 从 0 到 1200 W/m²

    # 计算太阳光谱加权反射率（R_sol）
    R_sol = calculate_R_sol(file_paths, config)
    alpha_s = 1 - R_sol

    # 加载并插值发射率数据
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    # 组装数据：data1 对应大气（透过率），data2 对应薄膜（发射率）
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    # 按原代码处理：波长先乘以 1000（转换为 nm），后面再转为 m
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    # 设置角度积分参数：积分角度范围 0 到 90°（以弧度计）
    theta1 = 0
    theta2 = np.pi / 2
    nth = 100  # 角度离散点数（可根据需要调整）
    dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2, nth)
    # 角度积分因子：2π * sinθ cosθ dθ
    angle_factor = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth

    # 波长（单位 m）：转换 data1 和 data2 第一列（原单位 nm 转为 m）
    lambda1 = data1[:, 0] * 1e-9
    lambda2 = data2[:, 0] * 1e-9
    # 近似波长间隔
    if len(data1) > 1:
        dlam1 = data1[1, 0] - data1[0, 0]
    else:
        dlam1 = 1
    if len(data2) > 1:
        dlam2 = data2[1, 0] - data2[0, 0]
    else:
        dlam2 = 1

    # 初始化结果矩阵：行对应不同环境温度，列对应不同太阳辐照度
    results = np.zeros((len(T_a_range), len(S_solar_range)))

    # 对每个环境温度 Ta（单位 °C）计算辐射积分项（薄膜和大气均在温度 T = Ta+273.15 下）
    for i, Ta in enumerate(T_a_range):
        T = Ta + 273.15  # 转换为开尔文

        # ----- 计算薄膜自发辐射 p_r -----
        # 计算薄膜对应的黑体谱函数（Planck公式），注意防止溢出
        exponent_film = C2 / (lambda2 * T)
        exponent_film = np.minimum(exponent_film, 700)
        u_b1ams = 1e9 * (lambda2 ** 5) * (np.exp(exponent_film) - 1)
        u_bs = C1 / u_b1ams
        # 薄膜辐射功率积分：对波长积分后再乘以角度积分因子（积分近似为乘以 sum(angle_factor)）
        tempint_R3 = u_bs * data2[:, 1] * dlam2
        int_R3am = np.sum(tempint_R3)
        p_r = int_R3am * np.sum(angle_factor)

        # ----- 计算大气反向辐射 p_a -----
        exponent_a = C2 / (lambda1 * T)
        exponent_a = np.minimum(exponent_a, 700)
        u_b1ams1 = 1e9 * (lambda1 ** 5) * (np.exp(exponent_a) - 1)
        u_bs1 = C1 / u_b1ams1
        # 大气"发射率"通常与透过率有关，这里采用近似：平均大气有效发射率
        # e_zmat = 1 - tmat^(1/cosθ)；这里对所有角度取平均近似
        e_zmat_avg = np.mean(1 - np.power(data1[:, 1], 1 / np.cos(theta.mean())))
        tempint_R1 = u_bs1 * data2[:, 1] * e_zmat_avg * dlam1
        int_R1am = np.sum(tempint_R1)
        p_a = int_R1am * np.sum(angle_factor)

        # 对于给定环境温度下，p_r 和 p_a均不随 S_solar 变化，因此净制热功率为：
        # P_heat = Q_solar + p_a - p_r，其中 Q_solar = alpha_s * S_solar
        for j, S in enumerate(S_solar_range):
            Q_solar = alpha_s * S
            p_heat = Q_solar + p_a - p_r
            results[i, j] = p_heat

    # 设置Matplotlib的风格和字体
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.family': 'Arial',
        'font.size': 12,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'figure.titlesize': 16,
        'figure.figsize': (10, 8),
        'figure.dpi': 120
    })
    
    # 绘制结果图：横轴为太阳辐照度，纵轴为净辐射制热功率，不同曲线对应不同 Ta
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 创建颜色映射以便于区分不同温度线
    cmap = plt.get_cmap('viridis')
    colors = [cmap(i/len(T_a_range)) for i in range(len(T_a_range))]
    
    for i, Ta in enumerate(T_a_range):
        ax.plot(S_solar_range, results[i, :], label=f"T = {Ta:.0f}°C", 
                color=colors[i], linewidth=2)
    
    # 添加Baseline
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.5, label='Baseline')
    
    # 添加标题和标签
    ax.set_xlabel("Solar irradiance (W/m²)", fontsize=14, weight='bold')
    ax.set_ylabel("Net radiant heating power (W/m²)", fontsize=14, weight='bold')
    ax.set_title("Theoretical radiation heating power VS. Solar irradiance\n",
                fontsize=16, weight='bold', pad=20)
    
    # 添加网格
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # 设置图例
    # 为了避免图例太拥挤，只显示部分温度
    temp_indices = np.linspace(0, len(T_a_range)-1, 7, dtype=int)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend([handles[i] for i in temp_indices] + [handles[-1]], 
              [labels[i] for i in temp_indices] + [labels[-1]], 
              loc='best', framealpha=0.7, fontsize=10)
    
    
    plt.tight_layout()
    plt.show(block=False)
    plt.pause(5)
    plt.close(fig) 

    # 允许用户选择保存计算结果到 CSV 文件
    options = QFileDialog.Options()
    save_file_path, _ = QFileDialog.getSaveFileName(
        None, "保存结果", "", "CSV files (*.csv)", options=options
    )
    
    if save_file_path:
        # 构造 DataFrame，行索引为环境温度，列为太阳辐照度
        df = pd.DataFrame(
            results,
            index=[f"{Ta:.0f}" for Ta in T_a_range],
            columns=np.round(S_solar_range, 2)
        )
        df.index.name = "Ambient Temperature°C"
        df.columns.name = "Solar Irradiance (W/m²)"
        df.to_csv(save_file_path)
        print(f"结果已保存到 {save_file_path}")

def main_calculating_gui(file_paths):
    """主程序逻辑"""
    # 检查必要的文件是否已选择
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    # 加载配置文件
    config = load_config(file_paths['config'])

    # 从配置中提取变量
    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EXPIRATION_DATE = config['EXPIRATION_DATE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']
    H = config['H']
    C = config['C']
    KB = config['KB']
    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']
    T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    VISIABLE_RANGE = config['VISIABLE_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = config['S_solar']

    # 检查过期
    check_expiration(EXPIRATION_DATE, EMAIL_CONTACT)

    # 加载反射率数据
    reflectance_data = load_reflectance(file_paths['reflectance'])

    # 加载光谱数据
    spectrum_data = load_spectrum(file_paths['spectrum'])

    # 过滤波长范围
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)
    
    # 插值光谱数据
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)
    
    # 计算加权平均反射率
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    R_sol1 = calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)

    # 加载并插值发射率数据
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    # 组合数据
    data1 = np.column_stack((X, emissivityatm_interpolated))  # 大气透过率
    data2 = np.column_stack((X, emissivity_interpolated))    # 薄膜发射率
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000
    
    # 设置温度参数
    T_a = T_a1 + 273.15  # 环境温度（K）
    

    X = X * 1e-6  # 转换为米

    # 计算平均发射率
    avg_emissivity = calculate_average_emissivity(X, emissivity_interpolated, T_a)

    # 创建声明文件
    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
    
    return avg_emissivity, R_sol, R_sol1

def main_cooling_gui(file_paths):
    """主程序逻辑"""
    # 检查必要的文件是否已选择
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    # 加载配置文件
    config = load_config(file_paths['config'])

    # 从配置中提取变量
    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EXPIRATION_DATE = config['EXPIRATION_DATE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']
    H = config['H']
    C = config['C']
    KB = config['KB']
    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']
    T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    VISIABLE_RANGE = config['VISIABLE_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = config['S_solar']

    # 检查过期
    check_expiration(EXPIRATION_DATE, EMAIL_CONTACT)

    # 加载反射率数据
    reflectance_data = load_reflectance(file_paths['reflectance'])

    # 加载光谱数据
    spectrum_data = load_spectrum(file_paths['spectrum'])

    # 过滤波长范围
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)
    
    # 插值光谱数据
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)
    
    # 计算加权平均反射率
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    R_sol1 = calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)

    # 加载并插值发射率数据
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    
    # 组合数据
    data1 = np.column_stack((X, emissivityatm_interpolated))  # 大气透过率
    data2 = np.column_stack((X, emissivity_interpolated))    # 薄膜发射率
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000
    
    # 设置温度参数
    T_a = T_a1 + 273.15  # 环境温度（K）
    T_film = np.arange(T_filmmin, T_filmmax, 1)  # 薄膜温度（°C）
    T_sll = T_film + 273.15  # 薄膜温度（K）
    delta_T = T_a1 - T_film  # 温差
    
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]      # 第一列为波长，单位：微米
    emissivity = data[:, 1]         # 第二列为发射率
    wavelength_m = wavelength_um * 1e-6  # 转换为米

    # 计算平均发射率
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)
    
    # 角度设置
    theta1 = 0
    theta2 = np.pi / 2  # 90度转为弧度
    
    # 角度积分准备
    tmat = data1[:, 1]  # 大气透过率
    nth = len(tmat) + 1
    dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2 - dth, nth - 1)
    
    # 波长转换为米
    lambda1 = data1[:, 0] * 1e-9
    lambda2 = data2[:, 0] * 1e-9
    
    # 计算发射率
    e_zmat, e_smat = calculate_radiation_power(data1, data2, theta, lambda1, lambda2)
    
    # 获取太阳辐照度
    S_solar = float(S_solar)
    
    # 计算薄膜的太阳光波段吸收率
    alpha_s = 1 - R_sol
    
    # 初始化结果矩阵
    results = np.zeros((len(T_film), len(HC_VALUES)))
    
    # 计算净辐射冷却功率
    for hc_index, H_conv in enumerate(HC_VALUES):
        print(f'Processing convection heat transfer coefficient: {H_conv} W/m²K')
        for i, T_s_current in enumerate(T_sll):
            # 大气和薄膜的黑体辐射率
            try:
                u_b1ams1 = 1e9 * (lambda1 ** 5) * (np.exp(C2 / (lambda1 * T_a)) - 1)
                u_bs1 = C1 / u_b1ams1
            except OverflowError:
                u_bs1 = np.zeros_like(lambda1)
            
            try:
                u_b1ams = 1e9 * (lambda2 ** 5) * (np.exp(C2 / (lambda2 * T_s_current)) - 1)
                u_bs = C1 / u_b1ams
            except OverflowError:
                u_bs = np.zeros_like(lambda2)
    
            # 波长间隔
            dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
            dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1
    
            # 薄膜的辐射功率密度和积分
            tempint_R3 = u_bs * e_smat * dlam2
            int_R3am = np.sum(tempint_R3)
            tempint_Rt3 = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth * int_R3am
            int_Rth3 = np.sum(tempint_Rt3)
            p_r = int_Rth3
    
            # 大气的辐射功率密度和积分
            tempint_R1 = u_bs1 * e_smat * e_zmat * dlam1
            int_R1am = np.sum(tempint_R1)
            tempint_Rt1 = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth * int_R1am
            int_Rth1 = np.sum(tempint_Rt1)
            p_a = int_Rth1
    
            # 对流换热功率
            Q_conv = H_conv * (T_a1 - T_film[i])
    
            # 太阳辐照度功率
            Q_solar = alpha_s * S_solar
    
            # 净辐射冷却功率
            p_net = p_r - p_a - Q_conv - Q_solar

            # 存储结果
            results[i, hc_index] = p_net
            
    # 找到 T_film 最接近 T_a1 的索引
    idx_zero_diff = np.argmin(np.abs(T_film - T_a1))
    cooling_power_zero_diff = results[idx_zero_diff, :]  # 该行对应所有 H_conv 的冷却功率

    def plot_results():
        """绘制结果图表"""
        # 设置Matplotlib的风格和字体
        plt.style.use('seaborn-v0_8-whitegrid')
        plt.rcParams.update({
            'font.family': 'Arial',
            'font.size': 12,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'figure.titlesize': 16,
            'figure.figsize': (10, 8),
            'figure.dpi': 120
        })
        
        fig, ax = plt.subplots(figsize=(10, 7))
        
        num_lines = len(HC_VALUES)
        
        # 使用更好的颜色方案
        cmap = plt.cm.viridis
        colors = [cmap(i/num_lines) for i in range(num_lines)]
        
        # 定义可循环的线型
        linestyles = cycle(['-', '--', '-.', ':'])
        
        T_film_diff = T_film - T_a1  # 温差
        
        for hc_index in range(num_lines):
            color = colors[hc_index]
            linestyle = next(linestyles)  # 循环使用线型
            ax.plot(T_film_diff, results[:, hc_index], color=color, linestyle=linestyle, linewidth=2,
                   label=f'h_c = {HC_VALUES[hc_index]} W/(m²K)')
        
        # 添加零冷却功率线
        ax.axhline(y=0, color='red', linestyle='-', alpha=0.5, linewidth=1)
        
        # 添加标签和标题
        ax.set_xlabel('ΔT (T_{film} - T_{ambient}) (°C)', fontsize=14, weight='bold')
        ax.set_ylabel('Cooling Power (W/m²)', fontsize=14, weight='bold')
        ax.set_title('Radiation cooling power vs. Film temperature difference', fontsize=16, weight='bold', pad=20)
        
        # 添加图例
        ax.legend(loc='best', frameon=True, framealpha=0.7)
        
        # 添加网格
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # 添加注释信息
        props = dict(boxstyle='round', facecolor='white', alpha=0.7)
        info_text = f"""
        Ambient temperature: {T_a1} °C
        Solar irradiance: {S_solar} W/m²
        """
        ax.text(0.02, 0.02, info_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='bottom', bbox=props)
        
        plt.tight_layout()
        plt.show(block=False)
        plt.pause(5)          # 保持图形显示5秒
        plt.close('all') 

    def export_data():
        """导出数据到CSV文件"""
        try:
            options = QFileDialog.Options()
            export_file_path, _ = QFileDialog.getSaveFileName(
                None, "保存文件", "", "CSV files (*.csv)", options=options
            )
            
            if export_file_path:
                export_data_dict = {'T_film_diff (°C)': T_film - T_a1}
                for hc_index, hc_value in enumerate(HC_VALUES):
                    export_data_dict[f'Cooling_Power_hc_{hc_value}'] = results[:, hc_index]
                df_export = pd.DataFrame(export_data_dict)
                df_export.to_csv(export_file_path, index=False)
                QMessageBox.information(None, "成功", f"插值并保存完成！文件保存为 {export_file_path}")
            else:
                QMessageBox.warning(None, "取消", "未选择保存文件路径。")
        except Exception as e:
            QMessageBox.critical(None, "错误", f"保存结果时出错: {e}")

    # 创建结果操作对话框
    dialog = QDialog()
    dialog.setWindowTitle("选择操作")
    dialog.setFixedSize(400, 300)
    dialog.setStyleSheet(GLOBAL_STYLE)
    
    dialog_layout = QVBoxLayout()
    dialog_layout.setSpacing(20)
    dialog_layout.setContentsMargins(20, 20, 20, 20)
    
    # 标题
    title_label = TitleLabel("计算完成")
    dialog_layout.addWidget(title_label)
    
    # 结果信息
    result_info = QLabel(f"冷却功率: {cooling_power_zero_diff[0]:.4f} W/m²")
    result_info.setObjectName("result")
    result_info.setAlignment(Qt.AlignCenter)
    dialog_layout.addWidget(result_info)
    
    # 操作按钮
    button_card = CardFrame()
    button_layout = QVBoxLayout(button_card)
    
    plot_button = AnimatedButton("预览冷却功率曲线")
    plot_button.clicked.connect(lambda: [plot_results() ])
    button_layout.addWidget(plot_button)
    
    export_button = AnimatedButton("导出数据到CSV")
    export_button.clicked.connect(lambda: [export_data()])
    button_layout.addWidget(export_button)
    
    cancel_button = AnimatedButton("关闭")
    cancel_button.clicked.connect(dialog.reject)
    button_layout.addWidget(cancel_button)
    
    dialog_layout.addWidget(button_card)
    
    dialog.setLayout(dialog_layout)
    dialog.exec_()
    
    # 创建声明文件
    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
    
    return avg_emissivity, R_sol, R_sol1, cooling_power_zero_diff[0]

def main_heating_gui(file_paths):
    """主程序逻辑"""
    # 检查必要的文件是否已选择
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    # 加载配置文件
    config = load_config(file_paths['config'])

    # 从配置中提取变量
    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EXPIRATION_DATE = config['EXPIRATION_DATE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']
    H = config['H']
    C = config['C']
    KB = config['KB']
    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmins']
    T_filmmax = config['T_filmmaxs']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = config['S_solar']

    # 检查过期
    check_expiration(EXPIRATION_DATE, EMAIL_CONTACT)

    # 加载反射率数据
    reflectance_data = load_reflectance(file_paths['reflectance'])

    # 加载光谱数据
    spectrum_data = load_spectrum(file_paths['spectrum'])

    # 过滤波长范围
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    # 插值光谱数据
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    S_solar = float(S_solar)
    
    # 计算加权平均反射率
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
  
    # 加载并插值发射率数据
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )

    # 组合数据
    data1 = np.column_stack((X, emissivityatm_interpolated))  # 大气透过率
    data2 = np.column_stack((X, emissivity_interpolated))    # 薄膜发射率
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    # 设置温度参数
    T_a = T_a1 + 273.15  # Convert to Kelvin

    # Thin film temperature range
    T_film = np.arange(T_filmmin, T_filmmax, 1)  # 30°C to 60°C
    T_sll = T_film + 273.15  # Convert to Kelvin

    # Temperature difference
    delta_T = T_a1 - T_film  # Not used further in the code

    # Angle settings
    theta1 = 0
    theta2 = 90 * np.pi / 180  # Convert degrees to radians

    # Angle integration parameters
    nth = 14102  # Number of discretization points
    dth = (theta2 - theta1) / (nth - 1)  # Angular step size
    theta = np.linspace(theta1, theta2 - dth, nth - 1).reshape(-1, 1)  # Column vector
    nth -= 1  # Adjust nth

    # Wavelength conversion to meters
    lambda1 = data1[:, 0] * 1e-9  # Atmospheric wavelengths
    lambda2 = data2[:, 0] * 1e-9  # Thin film wavelengths

    # Atmospheric transmittance and emissivity
    tmat = data1[:, 1]  # Atmospheric transmittance
    # To avoid division by zero in cosine, ensure theta does not include pi/2 exactly
    e_zmat = 1 - np.power(tmat, 1 / np.cos(theta))  # Atmospheric emissivity

    # Thin film emissivity
    e_smat = data2[:, 1]  # Thin film emissivity

    # Solar irradiance parameters
    alpha_s = 1 - R_sol  # Solar absorption rate

    # Initialize results array
    results = np.zeros((len(T_film), len(HC_VALUES)))

    # Precompute angle-related factors for integration
    sin_theta = np.sin(theta)  # sin(theta)
    cos_theta = np.cos(theta)  # cos(theta)
    angle_factor = 2 * np.pi * sin_theta * cos_theta * dth  # Integration factor

    # Main Calculation Loop
    for hc_index, H in enumerate(HC_VALUES):
        print(f'Processing convection heat transfer coefficient: {H} W/m²·K')
        for i, T_s_current in enumerate(T_sll):
            # Calculate atmospheric blackbody radiation using Planck's law
            exponent_a = C2 / (lambda1 * T_a)
            # Handle potential overflow in exponential
            exponent_a = np.where(exponent_a > 700, 700, exponent_a)  # Prevent overflow
            u_b1ams1 = 1e9 * (lambda1 ** 5) * (np.exp(exponent_a) - 1)
            u_bs1 = C1 / u_b1ams1

            # Calculate thin film blackbody radiation using Planck's law
            exponent_film = C2 / (lambda2 * T_s_current)
            # Handle potential overflow in exponential
            exponent_film = np.where(exponent_film > 700, 700, exponent_film)  # Prevent overflow
            u_b1ams = 1e9 * (lambda2 ** 5) * (np.exp(exponent_film) - 1)
            u_bs = C1 / u_b1ams

            # Wavelength intervals
            dlam1 = data1[1, 0] - data1[0, 0]  # Atmospheric wavelength interval
            dlam2 = data2[1, 0] - data2[0, 0]  # Thin film wavelength interval

            # Radiation power density for thin film
            tempint_R3 = u_bs * e_smat * dlam2  # Element-wise multiplication
            int_R3am = np.sum(tempint_R3)  # Integral over wavelength
            tempint_Rt3 = angle_factor * int_R3am  # Element-wise multiplication with angle factor
            int_Rth3 = np.sum(tempint_Rt3)  # Integral over angle
            p_r = int_Rth3  # Radiative power

            # Radiation power density for atmosphere
            tempint_R1 = u_bs1 * e_smat * e_zmat * dlam1  # Element-wise multiplication
            int_R1am = np.sum(tempint_R1, axis=1)  # Integral over wavelength for each angle
            tempint_Rt1 = angle_factor.flatten() * int_R1am  # Element-wise multiplication with angle factor
            int_Rth1 = np.sum(tempint_Rt1)  # Integral over angle
            p_a = int_Rth1  # Atmospheric radiative power

            # Convection heat transfer
            Q_conv_cond = H * (T_a1 - T_film[i])  # Convection power

            # Solar irradiance power
            Q_solar = alpha_s * S_solar  # Solar power

            # Net heating power
            p_heat = Q_solar + p_a + Q_conv_cond - p_r

            # Store the result
            results[i, hc_index] = p_heat
    
    # 找到 T_film 最接近 T_a1 的索引
    idx_zero_diff = np.argmin(np.abs(T_film - T_a1))
    heating_power_zero_diff = results[idx_zero_diff, :]  # 该行对应所有 H_conv 的制热功率

    def plot_heating_results():
        """绘制制热结果图表"""
        # 设置Matplotlib的风格和字体
        plt.style.use('seaborn-v0_8-whitegrid')
        plt.rcParams.update({
            'font.family': 'Arial',
            'font.size': 12,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'figure.titlesize': 16,
            'figure.figsize': (10, 8),
            'figure.dpi': 120
        })
        
        fig, ax = plt.subplots(figsize=(10, 7))
        
        num_lines = len(HC_VALUES)
        
        # 使用暖色调(红色系)颜色方案
        cmap = plt.cm.autumn
        colors = [cmap(i/num_lines) for i in range(num_lines)]
        
        # 定义可循环的线型
        linestyles = cycle(['-', '--', '-.', ':'])
        
        T_film_diff = T_film - T_a1  # 温差
        
        for hc_index in range(num_lines):
            color = colors[hc_index]
            linestyle = next(linestyles)  # 循环使用线型
            ax.plot(T_film_diff, results[:, hc_index], color=color, linestyle=linestyle, linewidth=2,
                   label=f'h_c = {HC_VALUES[hc_index]} W/(m²·K)')
        
        # 添加零制热功率线
        ax.axhline(y=0, color='blue', linestyle='-', alpha=0.5, linewidth=1)
        
        # 添加标签和标题
        ax.set_xlabel('ΔT (T_{film} - T_{ambient}) (°C)', fontsize=14, weight='bold')
        ax.set_ylabel('Heating Power (W/m²)', fontsize=14, weight='bold')
        ax.set_title('Radiation heating power vs. Film temperature', fontsize=16, weight='bold', pad=20)
        
        # 添加图例
        ax.legend(loc='best', frameon=True, framealpha=0.7)
        
        # 添加网格
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # 添加注释信息
        props = dict(boxstyle='round', facecolor='white', alpha=0.7)
        info_text = f"""
        Ambient temperature: {T_a1} °C
        Solar irradiance: {S_solar} W/m²
        """
        ax.text(0.02, 0.02, info_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='bottom', bbox=props)
        
        plt.tight_layout()
        plt.show(block=False)
        plt.pause(5)         
        plt.close('all') 

    def export_heating_data():
        """导出制热数据到CSV文件"""
        try:
            options = QFileDialog.Options()
            export_file_path, _ = QFileDialog.getSaveFileName(
                None, "保存文件", "", "CSV files (*.csv)", options=options
            )
            
            if export_file_path:
                export_data = {'T_film_diff (°C)': T_film - T_a1}
                for hc_index, hc_value in enumerate(HC_VALUES):
                    export_data[f'Heating_Power_hc_{hc_value}'] = results[:, hc_index]
                df_export = pd.DataFrame(export_data)
                df_export.to_csv(export_file_path, index=False)
                QMessageBox.information(None, "成功", f"保存完成！文件保存为 {export_file_path}")
            else:
                QMessageBox.warning(None, "取消", "未选择保存文件路径。")
        except Exception as e:
            QMessageBox.critical(None, "错误", f"保存结果时出错: {e}")

    # 创建结果操作对话框
    dialog = QDialog()
    dialog.setWindowTitle("选择操作")
    dialog.setFixedSize(400, 300)
    dialog.setStyleSheet(GLOBAL_STYLE)
    
    dialog_layout = QVBoxLayout()
    dialog_layout.setSpacing(20)
    dialog_layout.setContentsMargins(20, 20, 20, 20)
    
    # 标题
    title_label = TitleLabel("计算完成")
    dialog_layout.addWidget(title_label)
    
    # 结果信息
    result_info = QLabel(f"加热功率: {heating_power_zero_diff[0]:.4f} W/m²")
    result_info.setObjectName("result")
    result_info.setAlignment(Qt.AlignCenter)
    dialog_layout.addWidget(result_info)
    
    # 操作按钮
    button_card = CardFrame()
    button_layout = QVBoxLayout(button_card)
    
    plot_button = AnimatedButton("绘制制热功率曲线")
    plot_button.clicked.connect(lambda: [plot_heating_results()])
    button_layout.addWidget(plot_button)
    
    export_button = AnimatedButton("导出数据到CSV")
    export_button.clicked.connect(lambda: [export_heating_data()])
    button_layout.addWidget(export_button)
    
    cancel_button = AnimatedButton("关闭")
    cancel_button.clicked.connect(dialog.reject)
    button_layout.addWidget(cancel_button)
    
    dialog_layout.addWidget(button_card)
    
    dialog.setLayout(dialog_layout)
    dialog.exec_()
    
    # 创建声明文件
    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
    
    return heating_power_zero_diff[0]

def create_splash_screen():
    """创建启动画面"""
    # 创建渐变背景
    splash_pixmap = QPixmap(600, 400)
    
    # 填充渐变色
    painter = QPainter(splash_pixmap)
    gradient = QLinearGradient(0, 0, 0, 400)
    gradient.setColorAt(0.0, QColor("#3498db"))
    gradient.setColorAt(1.0, QColor("#2c3e50"))
    painter.fillRect(0, 0, 600, 400, gradient)
    
    # 添加标题文本
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Arial", 24, QFont.Bold)
    painter.setFont(font)
    painter.drawText(100, 160, 500, 50, Qt.AlignCenter, "辐射制冷/制热计算工具")
    
    # 添加副标题
    painter.setPen(QColor(220, 220, 220))
    font = QFont("Arial", 12)
    painter.setFont(font)
    painter.drawText(100, 200, 400, 30, Qt.AlignCenter, "版本 3.0 - By CTY")
    
    # 添加底部版权信息
    painter.setPen(QColor(200, 200, 200, 180))
    font = QFont("Arial", 9)
    painter.setFont(font)
    current_year = datetime.datetime.now().year
    painter.drawText(100, 350, 400, 30, Qt.AlignCenter, f"© {current_year} 辐射计算工具")
    
    painter.end()
    
    splash = QSplashScreen(splash_pixmap)
    splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    
    return splash

def main():
    """程序入口函数"""
    app = QApplication(sys.argv)
    
    # 加载字体
    QFontDatabase.addApplicationFont("fonts/Roboto-Regular.ttf")
    QFontDatabase.addApplicationFont("fonts/Roboto-Bold.ttf")
    
    # 创建并显示启动画面
    splash = create_splash_screen()
    splash.show()
    
    # 模拟加载过程
    for i in range(1, 101):
        splash.showMessage(f"正在加载... {i}%", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
        app.processEvents()
        QTimer.singleShot(20, lambda: None)  # 简单延迟
        time.sleep(0.01)
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    # 关闭启动画面
    splash.finish(window)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()