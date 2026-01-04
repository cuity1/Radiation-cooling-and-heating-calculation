"""Configuration loading and expiration checks."""

from __future__ import annotations

import configparser
import datetime
import sys
import webbrowser

from PyQt5.QtWidgets import QMessageBox

from gui.i18n import language_manager


def load_config(config_path: str) -> dict:
    """加载并解析config.ini文件"""
    config = configparser.ConfigParser()
    try:
        config.read(config_path, encoding='utf-8')
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
        sys.exit(1)

    required_sections = ['GENERAL', 'EXPIRATION', 'PHYSICAL_CONSTANTS', 'CALCULATIONS']
    required_keys = {
        'GENERAL': ['DEFAULT_DIRECTORY', 'DECLARE_FILE'],
        'EXPIRATION': ['EXPIRATION_DATE', 'EMAIL_CONTACT'],
        'PHYSICAL_CONSTANTS': ['H', 'C', 'KB'],
        'CALCULATIONS': [
            'WAVELENGTH_RANGE',
            'VISIABLE_RANGE',
            'HC_VALUES',
            'T_a1',
            'T_filmmin',
            'T_filmmax',
            'T_filmmins',
            'T_filmmaxs',
            'S_solar',
        ],
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

    DEFAULT_DIRECTORY = config.get('GENERAL', 'DEFAULT_DIRECTORY')
    DECLARE_FILE = config.get('GENERAL', 'DECLARE_FILE')

    EXPIRATION_DATE_STR = config.get('EXPIRATION', 'EXPIRATION_DATE')
    EMAIL_CONTACT = config.get('EXPIRATION', 'EMAIL_CONTACT')
    try:
        EXPIRATION_DATE = datetime.datetime.strptime(EXPIRATION_DATE_STR, '%Y-%m-%d')
    except ValueError:
        print(
            f"配置文件中的 EXPIRATION_DATE 格式错误: {EXPIRATION_DATE_STR}. 应为 YYYY-MM-DD 格式。"
        )
        sys.exit(1)

    try:
        H = config.getfloat('PHYSICAL_CONSTANTS', 'H')
        C = config.getfloat('PHYSICAL_CONSTANTS', 'C')
        KB = config.getfloat('PHYSICAL_CONSTANTS', 'KB')
    except ValueError as ve:
        print(f"配置文件中的物理常量格式错误: {ve}")
        sys.exit(1)

    C1 = 2 * H * (C**2)
    C2 = (H * C) / KB

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
            raise ValueError('WAVELENGTH_RANGE 应包含两个值: 起始波长和结束波长。')
    except ValueError as ve:
        print(f"配置文件中的 WAVELENGTH_RANGE 格式错误: {ve}")
        sys.exit(1)

    try:
        VISIABLE_RANGE = [float(x.strip()) for x in VISIABLE_RANGE_STR.split(',')]
        if len(VISIABLE_RANGE) != 2:
            raise ValueError('VISIABLE_RANGE 应包含两个值: 起始波长和结束波长。')
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
        'S_solar': S_solar,
    }


def check_expiration(expiration_date: datetime.datetime, email_contact: str) -> None:
    """检查程序是否过期"""
    current_date = datetime.datetime.now()
    if current_date > expiration_date:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(language_manager.get('warning'))
        msg.setText(
            'This version has expired. Please update to ensure calculation accuracy.'
            if language_manager.current_language == 'en'
            else '此版本已过期，为了不影响计算精度，请进行版本更新。'
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        url = 'https://wwja.lanzoue.com/b0knk1xve'
        webbrowser.open(url)
        sys.exit()

    if language_manager.current_language == 'en':
        print(
            'Only two test datasets are required: reflectance in visible band and emissivity in atmospheric window'
        )
        print(
            'The software will match wavelengths automatically. Please do NOT include any Chinese/English characters in txt files!'
        )
    else:
        print('仅需要有两个测试数据：涉及可见光波段的反射率和涉及大气窗口的发射率')
        print('软件会自动匹配对应波长，在txt文件中请不要出现任何汉字及英文！')
