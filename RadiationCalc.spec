# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 获取项目根目录
# PyInstaller 执行时，当前工作目录通常是项目根目录
# 如果 main.py 在项目根目录，这里应该指向项目根目录
project_root = os.path.abspath('.')

# 收集所有需要的数据文件
datas = [
    ('default', 'default'),  # 将整个 default 目录包含进去
    ('material_comparison_tool', 'material_comparison_tool'),  # 将整个 material_comparison_tool 目录包含进去
]

# 收集所有需要包含的 Python 模块
hiddenimports = [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'numpy',
    'pandas',
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends.backend_qt5agg',
    'scipy',
    'openpyxl',  # 用于读取 Excel 文件
    'gui',
    'gui.i18n',
    'gui.main_window',
    'gui.subwindows',
    'gui.dialogs',
    'gui.config_editor',
    'gui.emissivity_cloud',
    'gui.file_processor',
    'gui.threads',
    'gui.widgets',
    'gui.windows',
    'core',
    'core.building_model',
    'core.calculations',
    'core.config',
    'core.heat_balance',
    'core.hvac_system',
    'core.materials',
    'core.physics',
    'core.plots',
    'core.simulation_engine',
    'core.spectrum',
    'core.theoretical',
    'core.weather_data',
    'utils',
    'utils.io_utils',
    'utils.path_utils',
]

a = Analysis(
    ['main.py'],
    pathex=[project_root],  # 添加项目根目录到搜索路径
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RadiationCalc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 如果有图标文件，可以在这里指定路径，例如: 'icons/app.ico'
)

