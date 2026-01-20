"""
主仿真引擎 - 协调各个模块进行逐小时仿真
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json
import logging

from .building_model import BuildingModel, Zone, Surface
from .heat_balance import HeatBalance

from .hvac_system import HVACSystem
from .weather_data import WeatherData
from .materials import MaterialDatabase

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimulationEngine:
    """
    精简 EnergyPlus 仿真引擎
    
    主要功能：
    - 时间步进控制
    - 各模块协调
    - 收敛性检查
    - 结果存储
    """
    
    def __init__(self, config_file: str):
        """
        初始化仿真引擎
        
        参数：
            config_file: 配置文件路径 (JSON)
        """
        self.config = self._load_config(config_file)
        
        # 初始化各个模块
        self.weather_data = WeatherData(self.config['weather']['epw_file'])
        self.building_model = BuildingModel(self.config['building'])
        vent_ach = self.config.get('hvac', {}).get('ventilation_ach', 0.2)
        # 天空温度模型权重（可选配置）
        sky_temp_weights = self.config.get('simulation', {}).get('sky_temp_weights', None)
        self.heat_balance = HeatBalance(self.building_model, ventilation_ach=vent_ach, 
                                        sky_temp_weights=sky_temp_weights)
        self.hvac_system = HVACSystem(self.config['hvac'])
        self.materials_db = MaterialDatabase()
        
        # 仿真参数（优先使用 EPW 中的日期范围）
        use_epw_dates = self.config['simulation'].get('use_epw_dates', True)
        years = getattr(self.weather_data, 'years', [])
        default_year = years[0] if years else 2001
        
        if use_epw_dates and getattr(self.weather_data, 'start_datetime', None) is not None:
            self.start_date = self.weather_data.start_datetime.to_pydatetime().replace(minute=0, second=0, microsecond=0)
            self.end_date = self.weather_data.end_datetime.to_pydatetime().replace(minute=0, second=0, microsecond=0)
        else:
            self.start_date = self._parse_date(
                default_year,
                self.config['simulation']['start_month'],
                self.config['simulation']['start_day']
            )
            self.end_date = self._parse_date(
                default_year,
                self.config['simulation']['end_month'],
                self.config['simulation']['end_day']
            )
        
        self.timestep = self.config['simulation'].get('timestep', 1)  # 小时
        
        # 结果存储
        self.results = {
            'hourly_loads': [],
            'zone_temperatures': [],
            'surface_temperatures': [],
            'weather_data': []
        }
        
        # 收敛性参数
        self.convergence_tolerance = 0.01  # K
        self.max_iterations = 10
        
        logger.info("仿真引擎初始化完成")
        
    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _parse_date(self, year: int, month: int, day: int) -> datetime:
        """解析日期，优先使用天气文件中的年份"""
        return datetime(year, month, day)
    
    def run_simulation(self) -> pd.DataFrame:
        """
        运行完整仿真
        
        返回：
            包含仿真结果的 DataFrame
        """
        logger.info(f"开始仿真：{self.start_date.date()} 至 {self.end_date.date()}")
        
        current_date = self.start_date
        hour_counter = 0  # 仅统计预热期后的有效小时
        
        # 预热期（前 7 天）
        warmup_days = self.config['simulation'].get('warmup_days', 7)
        warmup_end = self.start_date + timedelta(days=warmup_days)
        
        # 进度输出间隔（小时），默认每周一次
        progress_interval = self.config['simulation'].get('progress_interval_hours', 168)
        
        while current_date <= self.end_date:
            # 逐小时仿真
            for hour in range(0, 24, self.timestep):
                current_time = current_date.replace(hour=hour)
                
                # 更新天气数据
                weather = self.weather_data.get_hourly_data(current_time)
                
                # 计算热平衡
                for zone in self.building_model.zones:
                    self._calculate_zone_heat_balance(zone, weather, current_time)
                
                # 计算 HVAC 负荷
                for zone in self.building_model.zones:
                    self._calculate_hvac_load(zone, weather)
                
                # 存储结果（仅在预热期后）
                if current_date >= warmup_end:
                    self._store_results(current_time, hour_counter)
                    hour_counter += 1
                    # 进度输出（仅在有效小时>0且到达间隔时输出）
                    if progress_interval > 0 and hour_counter > 0 and (hour_counter % progress_interval == 0):
                        logger.info(f"已完成 {hour_counter} 小时有效仿真")
            
            current_date += timedelta(days=1)
        
        logger.info("仿真完成")
        
        # 转换为 DataFrame
        results_df = self._convert_results_to_dataframe()
        return results_df
    
    def _calculate_zone_heat_balance(self, zone: Zone, weather: Dict, current_time: datetime):
        """
        计算单个热区的热平衡
        
        参数：
            zone: 热区对象
            weather: 天气数据字典
            current_time: 当前时刻
        """
        # 迭代求解表面温度和室内温度
        for iteration in range(self.max_iterations):
            # 1. 计算围护结构表面温度
            for surface in zone.surfaces:
                self.heat_balance.calculate_surface_temperature(
                    surface, weather, zone.temperature
                )
            
            # 2. 计算室内温度
            old_temperature = zone.temperature
            self.heat_balance.calculate_zone_temperature(zone, weather)
            
            # 3. 检查收敛性
            temp_change = abs(zone.temperature - old_temperature)
            if temp_change < self.convergence_tolerance:
                break
        
        # 存储表面温度
        zone.surface_temperatures = {
            s.name: s.temperature for s in zone.surfaces
        }
    
    def _calculate_hvac_load(self, zone: Zone, weather: Dict):
        """
        计算 HVAC 负荷
        
        参数：
            zone: 热区对象
            weather: 天气数据字典
        """
        # 使用热平衡在设定温度下计算瞬时负荷（更物理、更稳定）
        T_cool = self.hvac_system.cooling_setpoint
        T_heat = self.hvac_system.heating_setpoint

        # 在设定温度下计算显热平衡，直接得到需要的负荷（不依赖自由漂移温度）
        Q_cool = self.heat_balance.compute_sensible_balance(zone, weather, T_cool)
        Q_heat = self.heat_balance.compute_sensible_balance(zone, weather, T_heat)

        # 负荷定义：在冷设定下净增热需要制冷；在热设定下净散热需要制热
        # 修复：正确处理符号，避免不必要的负号
        cooling_load = Q_cool if Q_cool > 0 else 0.0
        heating_load = float(max(0.0, -Q_heat))  # 修复：移除不必要的条件判断，直接取正值

        # 潜热负荷（简化）：基于相对湿度差
        latent_load = self.hvac_system.calculate_latent_load(
            weather.get('humidity', 0.5), self.hvac_system.humidity_setpoint
        )

        # 存储
        zone.cooling_load = float(cooling_load)
        zone.heating_load = float(heating_load)
        zone.latent_load = float(max(0.0, latent_load))

        # 计算该小时能耗（J）
        dt = 3600.0
        T_outdoor_K = float(weather.get('temperature', 25.0)) + 273.15
        zone.cooling_energy = self.hvac_system.calculate_energy(zone.cooling_load, 'cooling', dt=dt, T_outdoor=T_outdoor_K)
        zone.heating_energy = self.hvac_system.calculate_energy(zone.heating_load, 'heating', dt=dt, T_outdoor=T_outdoor_K)
    
    def _store_results(self, current_time: datetime, hour_counter: int):
        """存储仿真结果"""
        for zone in self.building_model.zones:
            # 逐小时负荷
            self.results['hourly_loads'].append({
                'Hour': hour_counter,
                'DateTime': current_time,
                'Zone': zone.name,
                'Cooling_Load_kW': zone.cooling_load / 1000,
                'Heating_Load_kW': zone.heating_load / 1000,
                'Latent_Load_kW': zone.latent_load / 1000,
                'Cooling_Energy_kWh': zone.cooling_energy / 3.6e6,  # J to kWh
                'Heating_Energy_kWh': zone.heating_energy / 3.6e6,  # J to kWh
                'Cooling_Energy_kWh_per_m2': (zone.cooling_energy / 3.6e6) / max(zone.area, 1e-6),
                'Heating_Energy_kWh_per_m2': (zone.heating_energy / 3.6e6) / max(zone.area, 1e-6),
                # MJ/m2 便于和强度指标对标：1 kWh = 3.6 MJ
                'Cooling_Energy_MJ_per_m2': (zone.cooling_energy / 3.6e6) * 3.6 / max(zone.area, 1e-6),
                'Heating_Energy_MJ_per_m2': (zone.heating_energy / 3.6e6) * 3.6 / max(zone.area, 1e-6),
                'HVAC_Energy_MJ_per_m2': ((zone.cooling_energy + zone.heating_energy) / 3.6e6) * 3.6 / max(zone.area, 1e-6)
            })
            
            # 室内温度
            self.results['zone_temperatures'].append({
                'Hour': hour_counter,
                'DateTime': current_time,
                'Zone': zone.name,
                'Indoor_Temp_C': zone.temperature - 273.15,
            })
            
            # 表面温度
            for surf_name, surf_temp in zone.surface_temperatures.items():
                self.results['surface_temperatures'].append({
                    'Hour': hour_counter,
                    'DateTime': current_time,
                    'Zone': zone.name,
                    'Surface': surf_name,
                    'Temperature_C': surf_temp - 273.15,
                })
    
    def _convert_results_to_dataframe(self) -> Dict[str, pd.DataFrame]:
        """将结果转换为 DataFrame"""
        return {
            'hourly_loads': pd.DataFrame(self.results['hourly_loads']),
            'zone_temperatures': pd.DataFrame(self.results['zone_temperatures']),
            'surface_temperatures': pd.DataFrame(self.results['surface_temperatures']),
        }
    
    def export_results(self, output_dir: str = 'output/results'):
        """
        导出仿真结果为 CSV 文件
        
        参数：
            output_dir: 输出目录
        """
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        results_df = self._convert_results_to_dataframe()
        
        # 导出逐小时负荷
        results_df['hourly_loads'].to_csv(
            f'{output_dir}/hourly_loads.csv', index=False
        )
        logger.info(f"已导出：{output_dir}/hourly_loads.csv")
        
        # 导出室内温度
        results_df['zone_temperatures'].to_csv(
            f'{output_dir}/zone_temperature.csv', index=False
        )
        logger.info(f"已导出：{output_dir}/zone_temperature.csv")
        
        # 导出表面温度
        results_df['surface_temperatures'].to_csv(
            f'{output_dir}/surface_temperature.csv', index=False
        )
        logger.info(f"已导出：{output_dir}/surface_temperature.csv")
        
        # 计算年度能耗统计
        annual_stats = self._calculate_annual_statistics(results_df)
        annual_stats.to_csv(
            f'{output_dir}/annual_energy.csv', index=False
        )
        logger.info(f"已导出：{output_dir}/annual_energy.csv")
    
    def _calculate_annual_statistics(self, results_df: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """计算年度能耗统计"""
        loads_df = results_df['hourly_loads']
        
        stats = []
        
        # 按热区统计
        for zone in self.building_model.zones:
            zone_data = loads_df[loads_df['Zone'] == zone.name]
            
            total_cooling = zone_data['Cooling_Energy_kWh'].sum()
            total_heating = zone_data['Heating_Energy_kWh'].sum()
            total_hvac = total_cooling + total_heating
            
            peak_cooling = zone_data['Cooling_Load_kW'].max()
            peak_heating = zone_data['Heating_Load_kW'].max()

            area = max(getattr(zone, 'area', 0.0), 1e-6)
            kwh_to_gj = 0.0036
            kwh_to_mj = 3.6

            stats.append({
                'Zone': zone.name,
                # 总量（GJ）
                'Total_Cooling_Energy_GJ': total_cooling * kwh_to_gj,
                'Total_Heating_Energy_GJ': total_heating * kwh_to_gj,
                'Total_HVAC_Energy_GJ': total_hvac * kwh_to_gj,
                # 强度（MJ/m2）
                'Total_Cooling_Energy_MJ_per_m2': (total_cooling * kwh_to_mj) / area,
                'Total_Heating_Energy_MJ_per_m2': (total_heating * kwh_to_mj) / area,
                'Total_HVAC_Energy_MJ_per_m2': (total_hvac * kwh_to_mj) / area,
                'Floor_Area_m2': area,
                # 负荷
                'Peak_Cooling_Load_kW': peak_cooling,
                'Peak_Heating_Load_kW': peak_heating,
                'Average_Cooling_Load_kW': zone_data['Cooling_Load_kW'].mean(),
                'Average_Heating_Load_kW': zone_data['Heating_Load_kW'].mean(),
            })
        
        return pd.DataFrame(stats)
    
    def get_summary(self) -> Dict:
        """获取仿真摘要"""
        results_df = self._convert_results_to_dataframe()
        loads_df = results_df['hourly_loads']
        
        summary = {
            'simulation_period': f"{self.start_date.date()} 至 {self.end_date.date()}",
            'total_hours': len(loads_df),
            'zones': len(self.building_model.zones),
            'total_cooling_energy_kWh': loads_df['Cooling_Energy_kWh'].sum(),
            'total_heating_energy_kWh': loads_df['Heating_Energy_kWh'].sum(),
            'total_hvac_energy_kWh': loads_df['Cooling_Energy_kWh'].sum() + loads_df['Heating_Energy_kWh'].sum(),
            'peak_cooling_load_kW': loads_df['Cooling_Load_kW'].max(),
            'peak_heating_load_kW': loads_df['Heating_Load_kW'].max(),
        }
        
        return summary


def run_simulation_from_config(config_file: str, output_dir: str = 'output/results'):
    """
    便捷函数：从配置文件运行仿真
    
    参数：
        config_file: 配置文件路径
        output_dir: 输出目录
    """
    engine = SimulationEngine(config_file)
    engine.run_simulation()
    engine.export_results(output_dir)
    
    summary = engine.get_summary()
    print("\n" + "="*50)
    print("仿真完成 - 年度能耗统计")
    print("="*50)
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    print("="*50)
    
    return engine

