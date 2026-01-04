"""Spectrum/reflectance/emissivity loading and interpolation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from scipy.interpolate import interp1d, PchipInterpolator


def load_reflectance(file_path: str) -> np.ndarray:
    """加载反射率数据"""
    try:
        data = pd.read_csv(file_path, sep=None, engine='python').to_numpy()
        if (data[:, 0] > 100).any():
            data[:, 0] *= 0.001
        if (data[:, 1] > 2).any():
            data[:, 1] *= 0.01
            print('数值缩放成功')
        return data
    except Exception as e:
        raise Exception(f"加载反射率数据时出错: {e}")


def load_spectrum(file_path: str) -> np.ndarray:
    """加载光谱数据"""
    try:
        return pd.read_excel(file_path).to_numpy()
    except Exception as e:
        raise Exception(f"加载光谱数据时出错: {e}")


def filter_wavelength(
    data: np.ndarray, 
    wavelength_idx: int, 
    value_idx: int, 
    wavelength_range: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """过滤指定波长范围内的数据"""
    wavelengths = data[:, wavelength_idx]
    values = data[:, value_idx]
    valid = (wavelengths >= wavelength_range[0]) & (wavelengths <= wavelength_range[1])
    return wavelengths[valid], values[valid]


def interpolate_spectrum(
    ref_wavelength: np.ndarray, 
    spec_wavelength: np.ndarray, 
    spec_values: np.ndarray
) -> np.ndarray:
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


def interpolate_reflectance(
    target_wavelength: np.ndarray, 
    ref_wavelength: np.ndarray, 
    reflectance_values: np.ndarray
) -> np.ndarray:
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
    interp_func = interp1d(
        sorted_wavelength, 
        sorted_values, 
        kind='linear',
        bounds_error=False, 
        fill_value=(sorted_values[0], sorted_values[-1])
    )
    
    return interp_func(target_wavelength)


def _trapz(y, x):
    """Compatibility wrapper: use numpy.trapz if available, else trapezoid."""
    if hasattr(np, 'trapz'):
        return np.trapz(y, x)
    return np.trapezoid(y, x)


def calculate_weighted_reflectance(
    reflectance: np.ndarray, 
    spectrum: np.ndarray, 
    wavelengths: np.ndarray
) -> float:
    """计算加权平均反射率"""
    numerator = _trapz(reflectance * spectrum, wavelengths)
    denominator = _trapz(spectrum, wavelengths)
    return numerator / denominator


def load_and_interpolate_emissivity(
    wavelength_csv: str, 
    emissivity_txt: str, 
    emissivity_atm_txt: str, 
    wavelength_range: tuple[float, float] = (8, 13)
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """加载并插值发射率和大气发射率数据
    
    Args:
        wavelength_csv: 波长文件路径 (CSV)
        emissivity_txt: 发射率文件路径 (TXT)
        emissivity_atm_txt: 大气发射率文件路径 (TXT)
        wavelength_range: 波长范围 (微米)
        
    Returns:
        tuple: (wavelengths, emissivity, emissivity_atm)
    """
    try:
        # 加载波长数据
        data_csv = pd.read_csv(wavelength_csv)
        X = data_csv.iloc[:, 0].to_numpy()

        # 加载材料发射率
        emis_df = pd.read_csv(
            emissivity_txt, 
            delim_whitespace=True, 
            header=None, 
            names=['X2', 'emissivity']
        )
        
        # 处理波长单位转换（微米转米）
        if (emis_df['X2'] > 1000).any():
            emis_df['X2'] *= 0.001
            
        y = emis_df['emissivity'].astype(float).to_numpy()
        
        # 归一化发射率到[0,1]范围
        if np.nanmax(y) > 2:
            y = y / 100.0
        y = np.clip(y, 0.0, 1.0)
        
        x = emis_df['X2'].astype(float).to_numpy()
        
        # 清理无效值并排序去重
        m = np.isfinite(x) & np.isfinite(y)
        x, y = x[m], y[m]
        if x.size < 2:
            raise ValueError("材料发射率数据点不足，无法插值")
            
        idx = np.argsort(x)
        x, y = x[idx], y[idx]
        xu, uniq_idx = np.unique(x, return_index=True)
        yu = y[uniq_idx]
        
        # 插值到目标波长
        emissivity_interpolated = np.interp(X, xu, yu)

        # 加载大气发射率
        atm_df = pd.read_csv(
            emissivity_atm_txt, 
            delim_whitespace=True, 
            header=None, 
            names=['X3', 'emissivityatm']
        )
        
        xa = atm_df['X3'].astype(float).to_numpy()
        ya = atm_df['emissivityatm'].astype(float).to_numpy()
        ya = np.clip(ya, 0.0, 1.0)
        
        # 清理无效值
        m2 = np.isfinite(xa) & np.isfinite(ya)
        xa, ya = xa[m2], ya[m2]
        
        # 处理波长单位
        if (xa > 1000).any():
            xa = xa * 0.001
            
        if xa.size < 2:
            raise ValueError("大气发射率数据点不足，无法插值")
            
        idx2 = np.argsort(xa)
        xa, ya = xa[idx2], ya[idx2]
        xau, uniq_idx2 = np.unique(xa, return_index=True)
        yau = ya[uniq_idx2]
        
        # 插值到目标波长
        emissivityatm_interpolated = np.interp(X, xau, yau)

        return X, emissivity_interpolated, emissivityatm_interpolated
        
    except Exception as e:
        raise Exception(f"加载发射率数据时出错: {e}")


def calculate_radiation_power(
    data1: np.ndarray, 
    data2: np.ndarray, 
    theta: float, 
    wavelengths1: np.ndarray, 
    wavelengths2: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """计算辐射功率
    
    Args:
        data1: 透射率数据 (N,2) [wavelength, transmittance]
        data2: 发射率数据 (M,2) [wavelength, emissivity]
        theta: 入射角 (弧度)
        wavelengths1: 透射率波长
        wavelengths2: 发射率波长
        
    Returns:
        tuple: (e_zmat, e_smat) 有效发射率
    """
    tmat = data1[:, 1]
    with np.errstate(divide='ignore', invalid='ignore'):
        e_zmat = 1 - tmat ** (1.0 / np.cos(theta))
        e_zmat = np.nan_to_num(e_zmat, nan=0.0, posinf=0.0, neginf=0.0)
    e_smat = data2[:, 1]
    return e_zmat, e_smat