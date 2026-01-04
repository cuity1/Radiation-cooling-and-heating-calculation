"""Internationalization / theme constants."""

from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal


# 淡雅科研风格配色方案
COLORS = {
    'background': '#F5F7FA',
    'card': '#FFFFFF',
    'primary_text': '#2C3E50',
    'secondary_text': '#7F8C8D',
    'accent': '#3498DB',
    'success': '#27AE60',
    'warning': '#F39C12',
    'error': '#E74C3C',
    'border': '#E1E8ED',
    'hover': '#ECF0F1',
    'light_bg': '#FAFBFC',
}


class LanguageManager(QObject):
    """语言管理器，负责管理中英文切换"""

    language_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.current_language = 'zh'
        self.translations = {
            'zh': {
                # 主窗口
                'main_title': '辐射制冷/制热计算工具',
                'select_files': '1：先选择所需的文件',
                'select_function': '2：请选择要执行的功能',
                'select_reflectance': '选择反射率文件',
                'select_emissivity': '选择发射率文件',
                'select_atm_transmittance': '选择大气透过率',
                'emissivity_solar_cloud': '大气发射率-太阳光强云图',
                'power_components': '功率分量曲线图',
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

                # 调试
                'debug_print': '打印详细功率分量',

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

                # 精度
                'calculation_precision': '计算精度',
                'precision_low': '低 (快速)',
                'precision_medium': '中 (推荐)',
                'precision_high': '高 (精确)',

                # 相变
                'phase_temp': '相变温度 (°C)',
                'phase_power': '相变功率 (W/m²)',
                'phase_width': '相变展宽 (°C)',

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
                'emissivity_solar_cloud': 'Atmospheric Emissivity - Solar Irradiance Cloud Map',
                'power_components': 'Power Component Curves',
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

                # Debug
                'debug_print': 'Print detailed power terms',

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

                # Precision
                'calculation_precision': 'Calculation Precision',
                'precision_low': 'Low (Fast)',
                'precision_medium': 'Medium (Recommended)',
                'precision_high': 'High (Accurate)',

                # Phase change
                'phase_temp': 'Phase Temp (°C)',
                'phase_power': 'Phase Power (W/m²)',
                'phase_width': 'Phase Transition Width (°C)',

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
                'emissivity_solar_cloud_title': 'Atmospheric Emissivity vs. Solar Irradiance Cloud Map',
            },
        }

    def set_language(self, language: str) -> None:
        if language in ['zh', 'en']:
            self.current_language = language
            self.language_changed.emit(language)

    def get(self, key: str, default=None):
        return self.translations[self.current_language].get(key, default or key)

    def is_chinese(self) -> bool:
        return self.current_language == 'zh'


language_manager = LanguageManager()
