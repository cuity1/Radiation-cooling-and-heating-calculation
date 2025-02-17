import os
import sys
import datetime
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel, Label, Button
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import configparser
from itertools import cycle
from PIL import Image, ImageTk
import webbrowser
# 保证matplotlib在GUI中正常显示
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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
    expiration_date = datetime.datetime(2026, 6, 1)
    if current_date > expiration_date:
        messagebox.showinfo("过期通知", "此版本已过期，为了不影响计算精度，请进行版本更新。")
        url = "https://wwja.lanzoue.com/b0knk1xve"
        webbrowser.open(url)
        input("按回车键退出程序...")
        sys.exit()
    else:
        print("仅需要有两个测试数据：涉及可见光波段的反射率和涉及大气窗口的发射率")
        print("软件会自动匹配对应波长，在txt文件中请不要出现任何汉字及英文！")

def select_file(title, filetypes):
    """使用文件对话框选择文件"""
    file_path = filedialog.askopenfilename(title=title, filetypes=filetypes)
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

def load_and_interpolate_emissivity(wavelength_csv, emissivity_txt, emissivity_atm_txt):
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
诚信科研，使用此工具请引用参考文献: 
T. Cui, E. H. Ang, Y. Zheng, W. Cai, J. Wang, Y. Hu, J. Zhu, Nano Lett. 2024, acs.nanolett.4c03139。"""
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f'声明文件已创建：{file_path}')
    except Exception as e:
        print(f'创建声明文件时出错: {e}')

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("辐射制冷/制热计算工具")
        self.geometry("500x600")
        self.file_paths = {
            'config': 'default/config.ini',  # 固定配置文件路径
            'spectrum': 'default/AM1.5.dll' , # 固定太阳辐照AM1.5文件路径
            'wavelength':'default/wavelength.csv'
        }
        
        # 加载配置文件并进行过期检查
        try:
            config = load_config(self.file_paths['config'])
            check_expiration(config['EXPIRATION_DATE'], config['EMAIL_CONTACT'])
        except Exception as e:
            messagebox.showerror("错误", f"初始化时出错: {e}")
            self.destroy()
            sys.exit(1)
        
        self.create_widgets()

    def create_widgets(self):
        self.minsize(400, 600)  # 设置最小窗口大小
        self.resizable(False, False)  # 禁止调整窗口大小
        
        tk.Label(self, text="1：先选择所需的文件(解压目录中):", font=("Arial", 12)).pack(pady=10)

        self.reflectance_button = tk.Button(self, text="选择反射率文件", command=self.select_reflectance)
        self.reflectance_button.pack(pady=5)

        # self.wavelength_button = tk.Button(self, text="选择大气窗口波长", command=self.select_wavelength)
        # self.wavelength_button.pack(pady=5)

        self.emissivity_button = tk.Button(self, text="选择发射率文件", command=self.select_emissivity)
        self.emissivity_button.pack(pady=5)

        self.atm_emissivity_button = tk.Button(self, text="选择大气透过率", command=self.select_atm_emissivity)
        self.atm_emissivity_button.pack(pady=5)

        tk.Label(self, text="2：请选择要执行的功能:", font=("Arial", 14)).pack(pady=20)
        tk.Button(self, text="辐射制冷功率计算", font=("Arial", 12), width=20, command=self.open_cooling).pack(pady=5)
        tk.Button(self, text="辐射制热功率计算", font=("Arial", 12), width=20, command=self.open_heating).pack(pady=5)
        tk.Button(self, text="风速与制冷效率云图", font=("Arial", 12), width=20, command=self.open_yuntu).pack(pady=5)
        tk.Button(self, text="参数修改", font=("Arial", 12), width=20, command=self.launch).pack(pady=5)
        tk.Button(self, text="光热VS光照", font=("Arial", 12), width=20, command=self.open_heating_vs_solar).pack(pady=5)

    def open_heating_vs_solar(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            main_theoretical_heating_vs_solar(self.file_paths)
        except Exception as e:
            messagebox.showerror("错误", str(e))
    def launch(self):
        launch_config_editor()
    def select_reflectance(self):
        self.file_paths['reflectance'] = filedialog.askopenfilename(
            title="选择反射率文件",
            filetypes=[("Text files", "*.txt")]
        )
        if self.file_paths['reflectance']:
            messagebox.showinfo("提示", f"已选择反射率文件: {self.file_paths['reflectance']}")

    def open_yuntu(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            WindCoolingPlotWindow(self, self.file_paths)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # def select_wavelength(self):
    #     self.file_paths['wavelength'] = filedialog.askopenfilename(
    #         title="选择大气窗口波长文件",
    #         filetypes=[("CSV files", "*.csv")]
    #     )
        # if self.file_paths['wavelength']:
        #     messagebox.showinfo("提示", f"已选择波长文件: {self.file_paths['wavelength']}")

    def select_emissivity(self):
        self.file_paths['emissivity'] = filedialog.askopenfilename(
            title="选择发射率文件",
            filetypes=[("Text files", "*.txt")]
        )
        if self.file_paths['emissivity']:
            messagebox.showinfo("提示", f"已选择发射率文件: {self.file_paths['emissivity']}")

    def select_atm_emissivity(self):
        # 创建一个新的顶级窗口
        top = tk.Toplevel(self)
        top.title("选择大气透过率文件")
        top.geometry("300x150")
        top.resizable(False, False)  # 禁止调整窗口大小

        def select_file(file_name):
            self.file_paths['atm_emissivity'] = os.path.join('default', file_name)
            top.destroy()

        label = tk.Label(top, text="请选择大气透过率文件：", font=("Arial", 12))
        label.pack(pady=10)

        btn_1978 = tk.Button(top, text="晴朗", width=10, command=lambda: select_file('1.dll'))
        btn_1978.pack(pady=5)

        btn_2024 = tk.Button(top, text="少云", width=10, command=lambda: select_file('2.dll'))
        btn_2024.pack(pady=5)

        # 使窗口居中
        top.update_idletasks()
        width = top.winfo_width()
        height = top.winfo_height()
        x = (top.winfo_screenwidth() // 2) - (width // 2)
        y = (top.winfo_screenheight() // 2) - (height // 2)
        top.geometry(f'{width}x{height}+{x}+{y}')

        # 禁用父窗口，直到自定义消息框被关闭
        top.grab_set()
        self.wait_window(top)
    
    def open_cooling(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            CoolingWindow(self, self.file_paths)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def open_heating(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity'])
            HeatingWindow(self, self.file_paths)
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def open_reflectance(self):
        try:
            self.check_all_files(['config', 'reflectance', 'spectrum'])
            ReflectanceWindow(self, self.file_paths)
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def check_all_files(self, required_keys):
        """检查所有必需的文件是否已选择"""
        missing = [key for key in required_keys if key not in self.file_paths or not self.file_paths[key]]
        if missing:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{', '.join(missing)}")

class CoolingWindow(tk.Toplevel):
    def __init__(self, master, file_paths):
        super().__init__(master)
        self.title("辐射制冷功率计算")
        self.geometry("500x300+300+200")
        self.file_paths = file_paths.copy()
        self.create_widgets()

    def create_widgets(self):
        self.execute_button = tk.Button(self, text="执行计算", command=self.run_cooling)
        self.execute_button.pack(pady=20)

        # 显示计算状态
        self.status_label = tk.Label(self, text="", fg="red")
        self.status_label.pack()

        # 显示计算结果
        self.result_label = tk.Label(self, text="", font=("Arial", 12), fg="blue")
        self.result_label.pack(pady=10)

    def run_cooling(self):
        try:
            # 设置计算状态
            self.status_label.config(text="正在计算，请稍候...")
            self.update()

            # 调用主计算函数，传递 self 作为 parent
            avg_emissivity, R_sol, R_sol1,Power_0 = main_cooling_gui(self.file_paths)

            # 更新状态和结果
            self.status_label.config(text="计算完成！")
            self.result_label.config(
                text=f"材料平均发射率  = {avg_emissivity:.4f}\n"
                     f"太阳光谱反射率 = {R_sol:.4f}\n"
                     f"可见光谱反射率 = {R_sol1:.4f}\n"
                     f"冷却功率 = {Power_0:.4f}W/m²"
            )
        except Exception as e:
            messagebox.showerror("错误", f"计算过程中出现错误: {e}", parent=self)
            self.status_label.config(text="计算失败！")

class HeatingWindow(tk.Toplevel):
    def __init__(self, master, file_paths):
        super().__init__(master)
        self.title("辐射制热功率计算")
        self.geometry("500x200+300+200")
        self.file_paths = file_paths.copy()
        self.create_widgets()

    def create_widgets(self):
        self.execute_button = tk.Button(self, text="执行计算", command=self.run_heating)
        self.execute_button.pack(pady=20)

        # 显示计算状态
        self.status_label = tk.Label(self, text="", fg="red")
        self.status_label.pack()

        # 显示计算结果
        self.result_label = tk.Label(self, text="", font=("Arial", 12), fg="blue")
        self.result_label.pack(pady=10)

    def run_heating(self):
        try:
            # 设置计算状态
            self.status_label.config(text="正在计算，请稍候...")
            self.update()

            # 调用主计算函数，传递 self 作为 parent
            main_heating_gui(self.file_paths)

            # 更新状态
            self.status_label.config(text="计算完成！")
        except Exception as e:
            messagebox.showerror("错误", f"计算过程中出现错误: {e}")
            self.status_label.config(text="计算失败！")

class WindCoolingPlotWindow(tk.Toplevel):
    def __init__(self, master, file_paths):
        super().__init__(master)
        self.title("风速与制冷效率云图")
        self.geometry("500x200+300+200")
        self.file_paths = file_paths.copy()
        self.create_widgets()

    def create_widgets(self):
        # Entry for S_solar
        tk.Label(self, text="请输入太阳辐照度 S_solar (单位: W/m²):").pack(pady=5)
        self.s_solar_entry = tk.Entry(self)
        self.s_solar_entry.pack(pady=5)

        self.execute_button = tk.Button(self, text="生成云图", command=self.run_wind_cooling_plot)
        self.execute_button.pack(pady=20)

        # 显示计算状态
        self.status_label = tk.Label(self, text="", fg="red")
        self.status_label.pack()

    def run_wind_cooling_plot(self):
        try:
            # 获取 S_solar
            S_solar_str = self.s_solar_entry.get()
            S_solar = float(S_solar_str)
            # 设置计算状态
            self.status_label.config(text="正在计算，请稍候...")
            self.update()

            # 调用计算函数
            generate_wind_cooling_plot(self.file_paths, S_solar)

            # 更新状态
            self.status_label.config(text="计算完成！")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的太阳辐照度数值")
        except Exception as e:
            messagebox.showerror("错误", f"计算过程中出现错误: {e}")
            self.status_label.config(text="计算失败！")

def generate_wind_cooling_plot(file_paths, S_solar):
    import numpy as np
    import matplotlib.pyplot as plt
    from scipy.optimize import brentq, minimize_scalar
    import pandas as pd  # 新增：导入 pandas 库

    # 加载配置文件
    config = load_config(file_paths['config'])
    # 环境温度
    T_a1 = config['T_a1']
    T_a = T_a1 + 273.15  # 绝对温度 K
    XMIN = -100 #寻找解析域
    XMAX = 300
    # 物理常数
    sigma = 5.670374419e-8  # Stefan-Boltzmann 常数 W·m⁻²·K⁻⁴

    # 加载反射率数据
    reflectance_data = load_reflectance(file_paths['reflectance'])

    # 加载光谱数据
    spectrum_data = load_spectrum(file_paths['spectrum'])

    # 过滤波长范围
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    # 插值光谱数据
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)

    # 计算加权平均反射率
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)

    # 加载并插值发射率数据
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )

    # 计算平均发射率
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]      # 第一列为波长，单位：微米
    emissivity = data[:, 1]         # 第二列为发射率
    wavelength_m = wavelength_um * 1e-6  # 转换为米
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)

    emissivitys = avg_emissivity

    # 反射率和吸收率
    alpha_s = 1 - R_sol  # 吸收率
    tc = emissivitys
    # 大气发射率

    # 定义发射率和对流换热系数的范围
    emissivity_variable = np.linspace(0, 1, num=50)  # 发射率从0.0到1.0

    wind = np.linspace(0, 0.5, num=50)  # 风速
    hccc = wind**0.6 *18.3
    hc_values = hccc + tc
    # 初始化存储温度差的数组
    delta_T_values = np.zeros((len(emissivity_variable), len(hc_values)))

    # 定义净辐射冷却功率为零时的方程
    def p_net_equation(delta_T, emissivity, H):
        T_s = T_a + delta_T
        return emissivitys * sigma * T_s**4 - emissivity * sigma * T_a**4 + H * delta_T - alpha_s * S_solar

    # 定义寻找近似解的函数
    def find_approximate_solution(emissivity, H, delta_T_min, delta_T_max):
        # 使用 minimize_scalar 寻找使 |p_net| 最小的 delta_T
        result = minimize_scalar(lambda delta_T: abs(p_net_equation(delta_T, emissivity, H)),
                                 bounds=(delta_T_min, delta_T_max),
                                 method='bounded')
        if result.success:
            return result.x
        else:
            return np.nan  # 如果优化失败，返回 NaN

    # 对于每个发射率和对流换热系数，求解对应的温度差 delta_T
    for i, emissivity in enumerate(emissivity_variable):
        for j, H in enumerate(hc_values):
            try:
                # 设置 delta_T 的求解范围，根据物理情况调整
                delta_T_solution = brentq(p_net_equation,XMIN, XMAX, args=(emissivity, H))
                delta_T_values[i, j] = delta_T_solution
            except ValueError:
                # 如果 brentq 无法找到解，使用 minimize_scalar 寻找近似解
                approx_solution = find_approximate_solution(emissivity, H, XMIN, XMAX)
                delta_T_values[i, j] = approx_solution
                #pass

    # 保存到 CSV
    # 让用户选择保存文件路径

    # 绘制云图
    X_mesh, Y_mesh = np.meshgrid(wind, emissivity_variable)
    plt.figure(figsize=(10, 8))
    cp = plt.contourf(X_mesh, Y_mesh, delta_T_values, levels=100, cmap='viridis')
    plt.colorbar(cp, label='ΔT (°C)')
    plt.xlabel('Wind (m/s)')
    plt.ylabel('Atomosphere emissivity')
    plt.tight_layout()
    plt.show()
    root = tk.Tk()
    root.withdraw()
    save_file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                  title="保存结果文件",
                                                  filetypes=[("CSV files", "*.csv")])
    root.destroy()
    if save_file_path:
        df_matrix = pd.DataFrame(delta_T_values, index=emissivity_variable, columns=np.round(wind, 3))
        df_matrix.index.name = 'emissivity'
        df_matrix.columns.name = 'wind'
        df_matrix.to_csv(save_file_path)
        print(f'结果已保存到 {save_file_path}')

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
    I_BB = planck_lambda(wavelength, temperature)
    # 计算分子和分母的积分
    numerator = np.trapz(I_BB * emissivity, wavelength)
    denominator = np.trapz(I_BB, wavelength)
    
    # 计算平均发射率
    average_emissivity = numerator / denominator
    print('numerator')
    print(numerator)
    print("denominator")
    print(denominator)
    return average_emissivity



def main_theoretical_heating_vs_solar(file_paths):
    """
    计算并绘制：在环境温度 Ta 从 -100°C 到 100°C（薄膜与环境温度相同，ΔT=0）条件下，
    理论辐射制热功率与太阳辐照度 S_solar 之间的关系。
    """
    import numpy as np
    import matplotlib.pyplot as plt
    import pandas as pd
    import tkinter as tk
    from tkinter import filedialog

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
        # 大气“发射率”通常与透过率有关，这里采用近似：平均大气有效发射率
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

    # 绘制结果图：横轴为太阳辐照度，纵轴为净辐射制热功率，不同曲线对应不同 Ta
    plt.figure(figsize=(8, 6))
    for i, Ta in enumerate(T_a_range):
        plt.plot(S_solar_range, results[i, :], label=f"Ta = {Ta:.0f}°C", linewidth=2)
    plt.xlabel("Solar Irradiance (W/m²)", fontsize=12)
    plt.ylabel("Net Radiative Heating Power (W/m²)", fontsize=12)
    plt.title("Theoretical radiation heating power and solar irradiance relationship \n (film temperature=ambient temperature, Δ T=0)", fontsize=14)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 允许用户选择保存计算结果到 CSV 文件
    root = tk.Tk()
    root.withdraw()
    save_file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        title="保存结果",
        filetypes=[("CSV files", "*.csv")]
    )
    root.destroy()
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


    #计算平均发射率
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
        print(f'Processing convection heat transfer coefficient: {H_conv} W/m²·K')
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
    # 查找温度差值为0时的冷却功率
    # 找到 T_film 最接近 T_a1 的索引
    idx_zero_diff = np.argmin(np.abs(T_film - T_a1))
    cooling_power_zero_diff = results[idx_zero_diff, :]  # 该行对应所有 H_conv 的冷却功率

    # 准备返回值，包括温度差值为0时的冷却功率
    # 使用字典将 H_conv 与对应的冷却功率关联起来
    cooling_power_zero_diff_dict = {f'HC_{HC_VALUES[i]}': cooling_power_zero_diff[i] for i in range(len(HC_VALUES))}
    
    # 绘制结果图
    def plot_results():
        plt.figure(figsize=(10, 6))

        num_lines = len(HC_VALUES)

        # 使用色图 'tab10' 提供最多10种不同颜色
        cmap = plt.get_cmap('tab10')
        colors = [cmap(i % cmap.N) for i in range(num_lines)]

        # 定义可循环的线型
        linestyles = cycle(['-', '--', '-.', ':'])

        T_film_diff = T_film - T_a1  # 温差

        for hc_index in range(num_lines):
            color = colors[hc_index]
            linestyle = next(linestyles)  # 循环使用线型
            plt.plot(T_film_diff, results[:, hc_index], color=color, linestyle=linestyle, linewidth=2,
                     label=f'h_c={HC_VALUES[hc_index]} W m⁻² K⁻¹')

        plt.xlabel('T_{film} - T_{ambient} (°C)', fontsize=12)
        plt.ylabel('Cooling Power (W m⁻²)', fontsize=12)
        plt.title('Radiative cooling power vs film temperature difference', fontsize=14)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    # 定义导出数据函数
    def export_data():
        try:
            export_file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                            title="保存文件",
                                                            filetypes=[("CSV files", "*.csv")])
            if export_file_path:
                export_data_dict = {'T_film_diff (°C)': T_film - T_a1}
                for hc_index, hc_value in enumerate(HC_VALUES):
                    export_data_dict[f'Cooling_Power_hc_{hc_value}'] = results[:, hc_index]
                df_export = pd.DataFrame(export_data_dict)
                df_export.to_csv(export_file_path, index=False)
                messagebox.showinfo("成功", f"插值并保存完成！文件保存为 {export_file_path}")
            else:
                messagebox.showwarning("取消", "未选择保存文件路径。")
        except Exception as e:
            messagebox.showerror("错误", f"保存结果时出错: {e}")

    # 创建主对话框窗口
    dialog = tk.Tk()
    dialog.title("选择操作")
    dialog.geometry("300x150")
    dialog.resizable(False, False)

    # 设置窗口居中
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f"+{x}+{y}")

    # 创建并放置按钮
    plot_button = tk.Button(dialog, text="绘图", width=15, command=lambda: [plot_results(), dialog.destroy()])
    export_button = tk.Button(dialog, text="导出数据", width=15, command=lambda: [export_data(), dialog.destroy()])
    cancel_button = tk.Button(dialog, text="取消", width=15, command=dialog.destroy)

    plot_button.pack(pady=10)
    export_button.pack(pady=10)
    cancel_button.pack(pady=10)
    dialog = tk.Tk()
    dialog.geometry("400x100")
    dialog.title("这个窗口只是在跪求大佬引我文章")
    # 运行对话框
    # 创建声明文件
    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
    return avg_emissivity, R_sol, R_sol1,cooling_power_zero_diff[0]




    



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

    # Convection heat transfer coefficients

    # Initialize results array
    results = np.zeros((len(T_film), len(HC_VALUES)))

    # Precompute angle-related factors for integration
    sin_theta = np.sin(theta)  # sin(theta)
    cos_theta = np.cos(theta)  # cos(theta)
    angle_factor = 2 * np.pi * sin_theta * cos_theta * dth  # Integration factor

    # ----------------------------
    # Main Calculation Loop
    # ----------------------------

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

        print(f'Completed for hc = {H} W/m²·K')

    # ----------------------------
    # Plotting
    # ----------------------------
    plt.figure(figsize=(10, 6))

    num_lines = len(HC_VALUES)

    # 使用色图 'tab10' 提供最多10种不同颜色
    cmap = plt.get_cmap('tab10')
    colors = [cmap(i % cmap.N) for i in range(num_lines)]

    # 定义可循环的线型
    linestyles = cycle(['-', '--', '-.', ':'])

    T_film_diff = T_film - T_a1  # 温差

    for hc_index in range(num_lines):
        color = colors[hc_index]
        linestyle = next(linestyles)  # 循环使用线型
        plt.plot(T_film_diff, results[:, hc_index], color=color, linestyle=linestyle, linewidth=2,
                label=f'h_c={HC_VALUES[hc_index]} W m⁻² K⁻¹')

    plt.xlabel('T_{film} - T_{ambient} (°C)', fontsize=12)
    plt.ylabel('Heating Power (W m⁻²)', fontsize=12)
    plt.title('Radiative Heating power vs film temperature difference', fontsize=14)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    # 保存结果到CSV
    print("请填写保存结果文件路径")
    root = tk.Tk()
    root.withdraw()
    save_file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                 title="保存文件",
                                                 filetypes=[("CSV files", "*.csv")])
    root.destroy()
    if save_file_path:
        try:
            export_data = {'T_film_diff (°C)': T_film_diff}
            for hc_index, hc_value in enumerate(HC_VALUES):
                export_data[f'Heating_Power_hc_{hc_value}'] = results[:, hc_index]
            df_export = pd.DataFrame(export_data)
            df_export.to_csv(save_file_path, index=False)
            print(f'保存完成！文件保存为 {save_file_path}')
        except Exception as e:
            print(f"保存结果时出错: {e}")
    else:
        print("未选择保存文件路径，程序退出。")
    
    # 创建声明文件
    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
def launch_config_editor():
    import tkinter as tk
    from tkinter import ttk, messagebox
    import configparser, os, shutil
    from datetime import datetime

    CONFIG_FILE = 'default/config.ini'
    if not os.path.exists(CONFIG_FILE):
        messagebox.showerror("错误", f"找不到 {CONFIG_FILE} 文件。")
        return

    root = tk.Tk()
    root.title("Config.ini 编辑器")
    
    # 初始化配置解析器，不转换键为小写
    config = configparser.ConfigParser()
    config.optionxform = str
    # 用于保存注释信息： { 节: { 'comments': [...], 'keys': { key: [...] } } }
    comments = {}
    
    # 解析文件提取注释并关联到对应的节和键
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
        messagebox.showerror("编码错误", f"无法使用 UTF-8 编码读取 {CONFIG_FILE} 文件。\n错误信息: {e}")
        root.destroy()
        return

    # 使用 configparser 读取配置（注释部分已单独解析）
    config.read(CONFIG_FILE, encoding='utf-8')
    
    # 存储可编辑项的 Entry 控件
    entries = {}
    comment_entries = {}
    
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True)
    
    def create_section(parent, section):
        row = 0
        # 显示节前注释（只读标签）
        sec_comments = comments.get(section, {}).get('comments', [])
        for comm in sec_comments:
            lbl = ttk.Label(parent, text=f"# {comm}", foreground='grey',
                            font=('Arial', 9, 'italic'), wraplength=400, justify='left')
            lbl.grid(row=row, column=0, columnspan=3, sticky='w', padx=5, pady=(5,0))
            row += 1
        # 列标题
        ttk.Label(parent, text="参数", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Label(parent, text="值", font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky='w', padx=5, pady=5)
        ttk.Label(parent, text="解释", font=('Arial', 10, 'bold')).grid(row=row, column=2, sticky='w', padx=5, pady=5)
        row += 1
        
        for key, value in config.items(section):
            key_comments = comments.get(section, {}).get('keys', {}).get(key, [])
            comment_text = " ; ".join(key_comments) if key_comments else ""
            # 对于只读的常量（示例中 C1 和 C2），直接显示标签
            if key in ['C1', 'C2']:
                ttk.Label(parent, text=key).grid(row=row, column=0, sticky='w', padx=5, pady=5)
                ttk.Label(parent, text=value).grid(row=row, column=1, sticky='w', padx=5, pady=5)
                ttk.Label(parent, text=comment_text, foreground='grey').grid(row=row, column=2, sticky='w', padx=5, pady=5)
                row += 1
                continue
            # 参数名标签
            ttk.Label(parent, text=key).grid(row=row, column=0, sticky='w', padx=5, pady=5)
            # 值的编辑框
            entry = ttk.Entry(parent, width=50)
            entry.insert(0, value)
            entry.grid(row=row, column=1, padx=5, pady=5)
            entries[(section, key)] = entry
            # 解释的编辑框
            comm_entry = ttk.Entry(parent, width=50)
            comm_entry.insert(0, comment_text)
            comm_entry.grid(row=row, column=2, padx=5, pady=5)
            comment_entries[(section, key)] = comm_entry
            row += 1

    # 为每个配置节创建选项卡
    for section in config.sections():
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=section)
        create_section(frame, section)
    
    def validate_inputs():
        """
        示例验证：
         - EXPIRATION 节下的 EXPIRATION_DATE 必须符合 YYYY-MM-DD 格式；
         - 键名前缀为 T_、HC_、S_、WAVELENGTH 或部分特定键要求为数值或数值列表。
        """
        for (section, key), entry in entries.items():
            val = entry.get().strip()
            if section == 'EXPIRATION' and key == 'EXPIRATION_DATE':
                try:
                    datetime.strptime(val, '%Y-%m-%d')
                except ValueError:
                    messagebox.showerror("输入错误", f"{key} 的格式应为 YYYY-MM-DD")
                    return False
            elif key.startswith('T_') or key.startswith('HC_') or key.startswith('S_') \
                 or key.startswith('WAVELENGTH') or key in ['KB', 'H', 'C']:
                try:
                    parts = [p.strip() for p in val.split(',')]
                    for part in parts:
                        if part:
                            float(part)
                except ValueError:
                    messagebox.showerror("输入错误", f"{key} 应为数值或数值列表（用逗号分隔）")
                    return False
        return True

    def save_config():
        if not validate_inputs():
            return
        # 备份原文件
        backup_file = CONFIG_FILE + '.bak'
        try:
            shutil.copy(CONFIG_FILE, backup_file)
        except Exception as e:
            messagebox.showerror("备份失败", f"备份原文件失败：{e}")
            return
        
        # 更新 config 对象中的值（只更新可编辑项）
        for (section, key), entry in entries.items():
            config.set(section, key, entry.get().strip())
        
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                for section in config.sections():
                    # 写入节级注释（如果存在）
                    sec_comms = comments.get(section, {}).get('comments', [])
                    for comm in sec_comms:
                        f.write(f"# {comm}\n")
                    f.write(f"[{section}]\n")
                    # 遍历该节的每个键
                    for key, value in config.items(section):
                        if key in ['C1', 'C2']:
                            key_comms = comments.get(section, {}).get('keys', {}).get(key, [])
                            for comm in key_comms:
                                f.write(f"# {comm}\n")
                            f.write(f"{key} = {value}\n")
                        else:
                            explanation = ""
                            if (section, key) in comment_entries:
                                explanation = comment_entries[(section, key)].get().strip()
                            if explanation:
                                for part in [p.strip() for p in explanation.split(';') if p.strip()]:
                                    f.write(f"# {part}\n")
                            f.write(f"{key} = {entries[(section, key)].get().strip()}\n")
                    f.write("\n")
            messagebox.showinfo("成功", "配置已成功保存。")
        except Exception as e:
            messagebox.showerror("保存失败", f"保存配置文件失败：{e}\n尝试恢复备份文件。")
            try:
                shutil.copy(backup_file, CONFIG_FILE)
                messagebox.showinfo("恢复成功", "已恢复备份文件。")
            except Exception as restore_e:
                messagebox.showerror("恢复失败", f"恢复备份失败：{restore_e}")

    # 底部按钮区
    button_frame = ttk.Frame(root)
    button_frame.pack(fill='x', padx=10, pady=10)
    ttk.Button(button_frame, text="保存", command=save_config).pack(side='right', padx=5)
    ttk.Button(button_frame, text="取消", command=root.destroy).pack(side='right', padx=5)

    root.mainloop()

# 主程序入口
def main():
    # 在主程序启动时进行过期检查
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()
