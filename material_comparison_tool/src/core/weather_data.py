"""
天气数据处理 - 读取 EPW 文件和提供天气数据
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# 简单的EPW缓存，减少重复IO与解析
_EPW_CACHE = {}

class WeatherData:
    """
    天气数据处理器
    
    功能：
    - 读取 EPW 格式天气文件
    - 提供逐小时天气数据
    - 计算太阳位置和辐射
    """
    
    def __init__(self, epw_file: str, reference_year: Optional[int] = None):
        """
        初始化天气数据处理器
        
        参数：
            epw_file: EPW 文件路径
            reference_year: 参考年份（用于 SWERA 等多年混合数据源）
                           如果为 None，自动检测
        """
        self.epw_file = epw_file
        self.reference_year = reference_year
        self.data = None
        self.location_info = {}
        self.data_quality_issues = []
        
        # 读取 EPW 文件
        self._read_epw()
        
        logger.info(f"已加载天气数据：{self.location_info}")
        if self.data_quality_issues:
            for issue in self.data_quality_issues:
                logger.warning(f"数据质量警告: {issue}")
    
    def _read_epw(self):
        """读取 EPW 文件"""
        # 若已缓存该EPW，直接加载，避免重复IO与解析
        if self.epw_file in _EPW_CACHE:
            cached = _EPW_CACHE[self.epw_file]
            self.location_info = dict(cached['location_info'])
            self.data = cached['data']
            self.start_datetime = cached.get('start_datetime')
            self.end_datetime = cached.get('end_datetime')
            self.years = list(cached.get('years', []))
            self.annual_mean_dbt = cached.get('annual_mean_dbt', None)
            logger.info(f"从缓存加载EPW：{self.epw_file}")
            return

        try:
            # EPW 文件格式：前 8 行是元数据，从第 9 行开始是数据
            # 读取头部元数据（兼容 UTF-8 与 Latin-1）
            try:
                f = open(self.epw_file, 'r', encoding='utf-8')
                first_line = f.readline()
                if not first_line:
                    raise ValueError('EPW 文件空或无法读取')
            except Exception:
                # 回退到 latin1
                f = open(self.epw_file, 'r', encoding='latin1', errors='ignore')
                first_line = f.readline()
            try:
                location_line = first_line.strip().split(',')
                def _safe_float(idx, default=0.0):
                    try:
                        return float(location_line[idx])
                    except Exception:
                        return float(default)
                def _safe_str(idx, default=''):
                    try:
                        return location_line[idx]
                    except Exception:
                        return default
                self.location_info = {
                    'city': _safe_str(1),
                    'state': _safe_str(2),
                    'country': _safe_str(3),
                    'latitude': _safe_float(6, 0.0),
                    'longitude': _safe_float(7, 0.0),
                    'timezone': _safe_float(8, 0.0),
                    'elevation': _safe_float(9, 0.0),
                }
                # 跳过其他元数据行
                for _ in range(7):
                    f.readline()
            finally:
                try:
                    f.close()
                except Exception:
                    pass
            
            # 读取天气数据
            # EPW 数据列：Year, Month, Day, Hour, Minute, DBT, DPT, RH, AtmPres, 
            #            ExtHorzRad, ExtDirRad, GloHorzRad, DirNormRad, DifHorzRad, ...
            # EPW 标准包含 "Data Source and Uncertainty Flags" 在 Minute 之后
            column_names = [
                'Year', 'Month', 'Day', 'Hour', 'Minute', 'Source',
                'DBT', 'DPT', 'RH', 'AtmPres',
                'ExtHorzRad', 'ExtDirRad', 'HorzIR',
                'GloHorzRad', 'DirNormRad', 'DifHorzRad',
                'GloHorzIllum', 'DirNormIllum', 'DifHorzIllum', 'ZenithLum',
                'WindDir', 'WindSpeed', 'TotalSkyCover', 'OpaqueSkyCover',
                'Visibility', 'Ceiling', 'PresentWeatherObs', 'PresentWeatherCodes',
                'PrecipitableWater', 'AerosolOpticalDepth', 'SnowDepth', 'DaysSinceLastSnow',
                'Albedo', 'LiquidPrecipDepth', 'LiquidPrecipRate'
            ]
            
            # 读取尽可能多的列，至少覆盖到我们需要的指标（编码容错：优先 UTF-8，再回退 latin1）
            try:
                self.data = pd.read_csv(
                    self.epw_file,
                    skiprows=8,
                    header=None,
                    names=column_names,
                    usecols=range(len(column_names)),
                    low_memory=False,
                    encoding='utf-8'
                )
            except Exception:
                self.data = pd.read_csv(
                    self.epw_file,
                    skiprows=8,
                    header=None,
                    names=column_names,
                    usecols=range(len(column_names)),
                    low_memory=False,
                    encoding='latin1'
                )
            
            # 清洗关键字段类型
            for col in ['Year', 'Month', 'Day', 'Hour']:
                self.data[col] = pd.to_numeric(self.data[col], errors='coerce').astype('Int64')

            # EPW 的 Hour 范围为 1..24（小时末），这里构造"小时起始时刻"的时间戳：
            # DateTime = datetime(Year,Month,Day) + (Hour-1) 小时
            # 纠正异常取值：年<=0 用 2001 代替；月限定 1..12；日限定 1..31（之后由 pandas 校正到当月末）
            
            # 检测 SWERA 格式或多年混合数据
            is_swera = 'SWERA' in self.epw_file
            year_data = self.data['Year'].ffill().fillna(2001).astype(int)
            
            # 检查年份连续性（典型年数据如 IWEC/TMY 可能来自不同年份的拼接）
            year_changes = (year_data.diff().abs() > 0).sum()
            if year_changes > 0:
                self.data_quality_issues.append(
                    f"检测到 {int(year_changes)} 次年份变化，可能是典型年数据的多年拼接（IWEC/TMY/SWERA 等）"
                )
            
            # 判定是否需要统一参考年份：
            # 1) 明确 SWERA；或 2) 用户指定参考年；或 3) 年份变化次数>1；或 4) 年份取值个数>1
            need_unify_year = is_swera or (self.reference_year is not None) or (int(year_changes) > 1) or (year_data.nunique(dropna=True) > 1)
            if need_unify_year:
                ref_year = self.reference_year if self.reference_year is not None else 2005
                year_series = pd.Series([ref_year] * len(self.data), index=self.data.index)
                self.data_quality_issues.append(
                    f"统一参考年份处理：使用 {ref_year}（避免跨年跨度导致仿真周期>1年）"
                )
                logger.info(f"统一参考年份：{ref_year}")
            else:
                year_series = year_data.where(year_data > 0, 2001)
            
            month_series = self.data['Month'].ffill().fillna(1).astype(int).clip(1, 12)
            day_series = self.data['Day'].ffill().fillna(1).astype(int).clip(1, 31)

            base_date = pd.to_datetime(
                dict(year=year_series, month=month_series, day=day_series),
                errors='coerce'
            )
            hour_offset = pd.to_timedelta((self.data['Hour'].fillna(1) - 1).clip(lower=0, upper=23).astype(int), unit='h')
            self.data['DateTime'] = base_date + hour_offset

            # 数据清洗：相对湿度限制在 0-100%
            if 'RH' in self.data.columns:
                rh_out_of_range = (self.data['RH'] > 100).sum()
                if rh_out_of_range > 0:
                    self.data_quality_issues.append(
                        f"相对湿度超过 100%：{int(rh_out_of_range)} 条记录，已截断"
                    )
                    self.data['RH'] = self.data['RH'].clip(0, 100)

            # 丢弃无法解析的时间行，并按时间排序
            self.data = self.data.dropna(subset=['DateTime']).sort_values('DateTime').reset_index(drop=True)

            # 记录天气文件的时间范围
            self.start_datetime = pd.to_datetime(self.data['DateTime'].iloc[0]) if not self.data.empty else None
            self.end_datetime = pd.to_datetime(self.data['DateTime'].iloc[-1]) if not self.data.empty else None
            self.years = sorted(self.data['DateTime'].dt.year.unique().tolist()) if not self.data.empty else []
            # 年平均干球温度
            try:
                self.annual_mean_dbt = float(pd.to_numeric(self.data['DBT'], errors='coerce').mean())
            except Exception:
                self.annual_mean_dbt = None

            logger.info(f"成功读取 {len(self.data)} 行天气数据（时间戳已从 EPW 年月日+小时构造）")

            # 写入缓存，供后续同一进程内复用
            try:
                _EPW_CACHE[self.epw_file] = {
                    'location_info': dict(self.location_info),
                    'data': self.data,
                    'start_datetime': self.start_datetime,
                    'end_datetime': self.end_datetime,
                    'years': list(self.years),
                    'annual_mean_dbt': getattr(self, 'annual_mean_dbt', None)
                }
            except Exception:
                pass
            
        except FileNotFoundError:
            logger.error(f"找不到 EPW 文件：{self.epw_file}")
            # 创建虚拟天气数据用于测试
            self._create_dummy_weather()
        except Exception as e:
            logger.error(f"读取 EPW 文件出错：{e}")
            self._create_dummy_weather()
    
    def _create_dummy_weather(self):
        """创建虚拟天气数据用于测试"""
        logger.warning("使用虚拟天气数据")
        
        # 创建全年的虚拟天气数据
        dates = pd.date_range('2023-01-01', '2023-12-31 23:00', freq='h')
        
        # 生成温度数据（正弦波模拟季节变化）
        day_of_year = dates.dayofyear
        base_temp = 15 + 10 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
        daily_variation = 5 * np.sin(2 * np.pi * dates.hour / 24)
        temperature = base_temp + daily_variation
        
        # 生成太阳辐射数据
        hour_of_day = dates.hour
        solar_radiation = np.maximum(0, 800 * np.sin(np.pi * (hour_of_day - 6) / 12))
        
        # 生成相对湿度数据
        humidity = 50 + 20 * np.sin(2 * np.pi * (day_of_year - 1) / 365)
        
        # 生成风速数据
        wind_speed = 3 + 1 * np.sin(2 * np.pi * (day_of_year - 1) / 365)
        
        self.data = pd.DataFrame({
            'DateTime': dates,
            'DBT': temperature,
            'RH': humidity,
            'GloHorzRad': solar_radiation,
            'DirNormRad': solar_radiation * 0.8,
            'DifHorzRad': solar_radiation * 0.2,
            'WindSpeed': wind_speed,
            'AtmPres': 101325,
        })
        
        self.location_info = {
            'city': 'Default',
            'state': 'N/A',
            'country': 'Unknown',
            'latitude': 30.0,
            'longitude': 120.0,
            'timezone': 8.0,
            'elevation': 0,
        }
    
    def get_hourly_data(self, datetime_obj: datetime) -> Dict:
        """
        获取指定时刻的天气数据
        
        参数：
            datetime_obj: 日期时间对象
            
        返回：
            包含天气数据的字典
        """
        # 查找最接近的时刻
        idx = (self.data['DateTime'] - datetime_obj).abs().argmin()
        row = self.data.iloc[idx]
        
        # 修复：添加月份信息，用于季节性太阳辐射计算
        return {
            'temperature': float(row['DBT']),  # °C
            'humidity': float(row['RH']) / 100,  # 转换为 0-1
            'solar_radiation': float(row['GloHorzRad']),  # W/m²
            'direct_normal_radiation': float(row['DirNormRad']),  # W/m²
            'diffuse_horizontal_radiation': float(row['DifHorzRad']),  # W/m²
            'wind_speed': float(row['WindSpeed']),  # m/s
            'atmospheric_pressure': float(row['AtmPres']),  # Pa
            'infrared_sky_radiation': float(row['HorzIR']) if 'HorzIR' in self.data.columns and pd.notna(row['HorzIR']) else None,  # 近似 W/m²
            'dew_point': float(row['DPT']) if 'DPT' in self.data.columns and pd.notna(row['DPT']) else None,  # °C
            'total_sky_cover': float(row['TotalSkyCover']) if 'TotalSkyCover' in self.data.columns and pd.notna(row['TotalSkyCover']) else None,  # 0-10
            'month': int(row['Month']),  # 月份（1-12），用于季节性太阳辐射计算
            'datetime': pd.to_datetime(row['DateTime']),
            'latitude': float(self.location_info.get('latitude', 0.0)),
            'longitude': float(self.location_info.get('longitude', 0.0)),
            'timezone': float(self.location_info.get('timezone', 0.0)),
            'albedo': float(row['Albedo']) if 'Albedo' in self.data.columns and pd.notna(row['Albedo']) else 0.2,
            'annual_mean_temperature': float(getattr(self, 'annual_mean_dbt', np.nan)) if hasattr(self, 'annual_mean_dbt') and self.annual_mean_dbt is not None else None
        }
    
    def get_daily_data(self, date: datetime) -> pd.DataFrame:
        """
        获取指定日期的全天天气数据
        
        参数：
            date: 日期对象
            
        返回：
            包含该日全天数据的 DataFrame
        """
        day_data = self.data[
            (self.data['DateTime'].dt.year == date.year) &
            (self.data['DateTime'].dt.month == date.month) &
            (self.data['DateTime'].dt.day == date.day)
        ]
        
        return day_data
    
    def get_monthly_data(self, year: int, month: int) -> pd.DataFrame:
        """
        获取指定月份的天气数据
        
        参数：
            year: 年份
            month: 月份
            
        返回：
            包含该月全部数据的 DataFrame
        """
        month_data = self.data[
            (self.data['DateTime'].dt.year == year) &
            (self.data['DateTime'].dt.month == month)
        ]
        
        return month_data
    
    def get_annual_data(self) -> pd.DataFrame:
        """获取全年天气数据"""
        return self.data.copy()
    
    def calculate_solar_position(self, latitude: float, longitude: float, 
                                 datetime_obj: datetime) -> Dict:
        """
        计算太阳位置角
        
        参数：
            latitude: 纬度（度）
            longitude: 经度（度）
            datetime_obj: 日期时间对象
            
        返回：
            包含太阳高度角和方位角的字典
        """
        # 计算太阳赤纬
        day_of_year = datetime_obj.timetuple().tm_yday
        declination = 23.45 * np.sin(np.radians(360 * (day_of_year - 81) / 365))
        
        # 计算时角
        hour = datetime_obj.hour + datetime_obj.minute / 60
        hour_angle = 15 * (hour - 12)
        
        # 计算太阳高度角
        lat_rad = np.radians(latitude)
        decl_rad = np.radians(declination)
        hour_rad = np.radians(hour_angle)
        
        sin_h = (np.sin(lat_rad) * np.sin(decl_rad) + 
                 np.cos(lat_rad) * np.cos(decl_rad) * np.cos(hour_rad))
        altitude = np.degrees(np.arcsin(sin_h))
        
        # 计算太阳方位角
        cos_A = ((np.sin(decl_rad) * np.cos(lat_rad) - 
                  np.cos(decl_rad) * np.sin(lat_rad) * np.cos(hour_rad)) / 
                 np.cos(np.radians(altitude)))
        azimuth = np.degrees(np.arccos(np.clip(cos_A, -1, 1)))
        
        # 调整方位角（从南向西为正）
        if hour_angle < 0:
            azimuth = -azimuth
        
        return {
            'altitude': altitude,  # 太阳高度角（度）
            'azimuth': azimuth,    # 太阳方位角（度）
        }
    
    def get_statistics(self) -> Dict:
        """获取天气数据统计"""
        return {
            'temperature_min': float(self.data['DBT'].min()),
            'temperature_max': float(self.data['DBT'].max()),
            'temperature_mean': float(self.data['DBT'].mean()),
            'humidity_min': float(self.data['RH'].min()),
            'humidity_max': float(self.data['RH'].max()),
            'humidity_mean': float(self.data['RH'].mean()),
            'solar_radiation_max': float(self.data['GloHorzRad'].max()),
            'solar_radiation_mean': float(self.data['GloHorzRad'].mean()),
            'wind_speed_max': float(self.data['WindSpeed'].max()),
            'wind_speed_mean': float(self.data['WindSpeed'].mean()),
        }
    
    def print_summary(self):
        """打印天气数据摘要"""
        print("\n" + "="*50)
        print("天气数据摘要")
        print("="*50)
        print(f"位置: {self.location_info['city']}, {self.location_info['country']}")
        print(f"纬度: {self.location_info['latitude']:.2f}°")
        print(f"经度: {self.location_info['longitude']:.2f}°")
        print(f"海拔: {self.location_info['elevation']:.0f} m")
        print(f"\n数据统计:")
        stats = self.get_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value:.2f}")
        print("="*50 + "\n")
