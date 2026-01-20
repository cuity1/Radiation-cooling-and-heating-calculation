"""
HVAC 系统模型 - 计算制冷/制热负荷和能耗
"""

from typing import Dict, Tuple
import numpy as np


class HVACSystem:
    """
    HVAC 系统模型
    
    主要功能：
    - 计算显热负荷
    - 计算潜热负荷
    - 计算能耗
    - 支持 COP 温度修正
    """
    
    def __init__(self, config: Dict):
        """
        初始化 HVAC 系统
        
        参数：
            config: 配置字典
        """
        # 设定温度
        self.cooling_setpoint = config.get('cooling_setpoint', 26) + 273.15  # 转换为 K
        self.heating_setpoint = config.get('heating_setpoint', 20) + 273.15  # 转换为 K
        self.humidity_setpoint = config.get('humidity_setpoint', 0.5)  # 相对湿度
        
        # COP 参数
        self.cop_cooling_ref = config.get('cop_cooling', 3.5)
        self.cop_heating_ref = config.get('cop_heating', 3.0)
        # COP 参考温度（输入按 °C 配置，这里统一转为 K）
        self.cop_ref_temp = float(config.get('cop_ref_temp', 35)) + 273.15  # K
        
        # 温度修正系数
        self.cop_temp_coeff_a = config.get('cop_temp_coeff_a', -0.01)
        self.cop_temp_coeff_b = config.get('cop_temp_coeff_b', 0.0001)
        
        # 部分负荷效率系数
        self.plr_coeff_a = config.get('plr_coeff_a', 0.125)
        self.plr_coeff_b = config.get('plr_coeff_b', 0.875)
        
        # 系统参数
        self.max_cooling_capacity = config.get('max_cooling_capacity', 50000)  # W
        self.max_heating_capacity = config.get('max_heating_capacity', 40000)  # W
        self.air_mass_flow = config.get('air_mass_flow', 2.0)  # kg/s
        
        # 物理常数
        self.air_cp = 1005  # J/kg·K
        self.latent_heat = 2500000  # J/kg（水的汽化热）
    
    def calculate_sensible_load(self, T_zone: float, T_cool_set: float, T_heat_set: float) -> float:
        """
        计算显热负荷
        
        Q_sens = ṁ_air * cp * (T_zone - T_setpoint)
        
        参数：
            T_zone: 室内温度 (K)
            T_cool_set: 制冷设定温度 (K)
            T_heat_set: 制热设定温度 (K)
            
        返回：
            显热负荷 (W)
            - 正值：需要制冷
            - 负值：需要制热
            - 0：在死区内
        """
        # 死区（不需要 HVAC）
        if T_heat_set <= T_zone <= T_cool_set:
            return 0
        
        # 制冷负荷
        if T_zone > T_cool_set:
            Q_sens = self.air_mass_flow * self.air_cp * (T_zone - T_cool_set)
            return Q_sens
        
        # 制热负荷
        if T_zone < T_heat_set:
            Q_sens = self.air_mass_flow * self.air_cp * (T_heat_set - T_zone)
            return -Q_sens  # 负值表示制热
        
        return 0
    
    def calculate_latent_load(self, humidity: float, humidity_setpoint: float) -> float:
        """
        计算潜热负荷
        
        Q_lat = ṁ_air * L_v * (W_zone - W_setpoint)
        
        参数：
            humidity: 室内相对湿度 (0-1)
            humidity_setpoint: 设定相对湿度 (0-1)
            
        返回：
            潜热负荷 (W)
        """
        if humidity > humidity_setpoint:
            # 需要除湿
            W_diff = humidity - humidity_setpoint
            Q_lat = self.air_mass_flow * self.latent_heat * W_diff * 0.01  # 简化
            return Q_lat
        
        return 0
    
    def calculate_energy(self, load: float, mode: str = 'cooling', dt: float = 3600.0, T_outdoor: float = None) -> float:
        """
        计算能耗（返回该时间步的能量，单位：J）
        
        电功率 P = Q / COP
        能量 E = P * dt = (Q / COP) * dt
        
        参数：
            load: 热负荷 (W)
            mode: 'cooling' 或 'heating'
            dt: 时间步长 (秒)，默认 3600 s（1 小时）
            T_outdoor: 室外空气温度 (K)，用于 COP 温度修正
            
        返回：
            能耗 (J)
        """
        if load <= 0:
            return 0.0
        
        # 获取 COP（考虑室外温度）
        if mode == 'cooling':
            cop = self.get_cop_cooling(T_outdoor)
            capacity = self.max_cooling_capacity
        else:
            cop = self.get_cop_heating(T_outdoor)
            capacity = self.max_heating_capacity
        
        # 计算部分负荷比
        plr = min(load / capacity, 1.0)
        
        # 应用部分负荷效率修正
        cop_part = cop * self._get_part_load_factor(plr)
        cop_part = max(cop_part, 0.1)  # 防止除零
        
        # 计算能耗（J）
        energy = (load / cop_part) * dt
        
        return energy
    
    def get_cop_cooling(self, T_outdoor: float = None) -> float:
        """
        获取制冷 COP（考虑温度修正）
        
        改进：使用更合理的温度修正系数
        制冷 COP 随室外温度升高而降低（约 2-3% per °C）
        
        参数：
            T_outdoor: 室外温度 (K)，如果为 None 使用参考值
            
        返回：
            COP 值
        """
        if T_outdoor is None:
            T_outdoor = self.cop_ref_temp
        
        T_outdoor = float(np.clip(T_outdoor, 250.0, 330.0))
        
        # 改进的温度修正（基于实际数据）
        # 制冷 COP 随室外温度升高而降低
        # 参考温度通常是 35°C (308.15 K)
        dT = T_outdoor - self.cop_ref_temp  # K
        
        # 使用更合理的二次多项式修正
        # 典型的空调：COP 随温度升高 1°C 下降约 2-3%
        cop = self.cop_cooling_ref * (1.0 - 0.02 * dT - 0.0005 * (dT ** 2))
        
        # 物理约束
        cop = float(np.clip(cop, 1.0, 6.0))
        
        return cop
    
    def get_cop_heating(self, T_outdoor: float = None) -> float:
        """
        获取制热 COP（考虑温度修正）
        
        改进：
        - 使用更合理的温度修正（加热 COP 随室外温度升高而升高）
        - 在低温区间（如 < -3°C）采用更陡峭的衰减
        
        参数：
            T_outdoor: 室外温度 (K)，如果为 None 使用参考值
            
        返回：
            COP 值
        """
        if T_outdoor is None:
            T_outdoor = self.cop_ref_temp
        
        T_outdoor = float(np.clip(T_outdoor, 250.0, 330.0))
        
        # 以 7°C (280.15 K) 作为制热参考温度
        ref_heat = 273.15 + 7.0
        dT = T_outdoor - ref_heat  # 室外温度相对参考温度的偏差（K）
        
        # 分段二次修正：
        # - 低温区（dT < -10 K）：性能快速衰减
        # - 过渡区（-10 K <= dT < 0）：线性衰减
        # - 正温区（dT >= 0）：缓慢上升
        if dT < -10.0:
            cop = self.cop_heating_ref * (1.0 + 0.04 * dT - 0.0010 * (dT ** 2))
        elif dT < 0.0:
            cop = self.cop_heating_ref * (1.0 + 0.03 * dT - 0.0006 * (dT ** 2))
        else:
            cop = self.cop_heating_ref * (1.0 + 0.015 * dT - 0.0003 * (dT ** 2))
        
        # 物理约束
        cop = float(np.clip(cop, 1.0, 5.0))
        
        return cop
    
    def _get_part_load_factor(self, plr: float) -> float:
        """
        获取部分负荷效率因子
        
        f(PLR) = a + b * PLR
        
        参数：
            plr: 部分负荷比 (0-1)
            
        返回：
            效率因子 (0-1)
        """
        if plr <= 0:
            return 0
        
        factor = self.plr_coeff_a + self.plr_coeff_b * plr
        
        # 确保因子在合理范围内
        factor = max(0.1, min(1.0, factor))
        
        return factor
    
    def calculate_total_load(self, sensible_load: float, latent_load: float) -> float:
        """
        计算总负荷（显热 + 潜热）
        
        参数：
            sensible_load: 显热负荷 (W)
            latent_load: 潜热负荷 (W)
            
        返回：
            总负荷 (W)
        """
        return np.sqrt(sensible_load**2 + latent_load**2)
    
    def get_system_summary(self) -> Dict:
        """获取 HVAC 系统摘要"""
        return {
            'cooling_setpoint_C': self.cooling_setpoint - 273.15,
            'heating_setpoint_C': self.heating_setpoint - 273.15,
            'humidity_setpoint': self.humidity_setpoint,
            'cop_cooling_ref': self.cop_cooling_ref,
            'cop_heating_ref': self.cop_heating_ref,
            'max_cooling_capacity_kW': self.max_cooling_capacity / 1000,
            'max_heating_capacity_kW': self.max_heating_capacity / 1000,
            'air_mass_flow_kg_s': self.air_mass_flow,
        }


class SimpleHVACSystem(HVACSystem):
    """
    简化 HVAC 系统 - 不考虑温度修正和部分负荷效率
    """
    
    def get_cop_cooling(self, T_outdoor: float = None) -> float:
        """获取制冷 COP（常数）"""
        return self.cop_cooling_ref
    
    def get_cop_heating(self, T_outdoor: float = None) -> float:
        """获取制热 COP（常数）"""
        return self.cop_heating_ref
    
    def _get_part_load_factor(self, plr: float) -> float:
        """获取部分负荷效率因子（常数）"""
        return 1.0


class VariableRefrigerantFlowSystem(HVACSystem):
    """
    变频冷媒流量系统 - 更高的部分负荷效率
    """
    
    def __init__(self, config: Dict):
        """初始化 VRF 系统"""
        super().__init__(config)
        # VRF 系统通常有更好的部分负荷效率
        self.plr_coeff_a = 0.05  # 更低的最小效率
        self.plr_coeff_b = 0.95  # 更高的负荷相关系数
    
    def _get_part_load_factor(self, plr: float) -> float:
        """VRF 系统的部分负荷效率"""
        if plr <= 0:
            return 0
        
        # VRF 系统在低负荷下效率更高
        factor = self.plr_coeff_a + self.plr_coeff_b * plr
        factor = max(0.05, min(1.0, factor))
        
        return factor


class HeatPumpSystem(HVACSystem):
    """
    热泵系统 - 制热效率更高
    """
    
    def __init__(self, config: Dict):
        """初始化热泵系统"""
        super().__init__(config)
        # 热泵系统制热 COP 通常更高
        self.cop_heating_ref = config.get('cop_heating', 4.0)
    
    def get_cop_heating(self, T_outdoor: float = None) -> float:
        """获取制热 COP（热泵）"""
        if T_outdoor is None:
            T_outdoor = self.cop_ref_temp
        
        # 热泵制热 COP 随室外温度下降而下降
        dT = T_outdoor - self.cop_ref_temp
        
        # 使用更陡峭的温度修正曲线
        cop = self.cop_heating_ref * (1 + self.cop_temp_coeff_a * 1.5 * dT + 
                                       self.cop_temp_coeff_b * 1.5 * dT**2)
        
        cop = max(0.5, cop)
        
        return cop

