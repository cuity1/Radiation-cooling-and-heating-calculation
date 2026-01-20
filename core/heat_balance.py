# -*- coding: utf-8 -*-
"""
热平衡计算模块
计算围护结构表面温度和室内空气温度
"""

import numpy as np
from typing import Dict, Tuple, Optional, List, TypedDict
from .building_model import Zone, Surface, Construction
from .materials import MaterialDatabase
import math


class HeatBalance:
    """
    热平衡计算器
    
    主要功能：
    - 计算外表面温度
    - 计算内表面温度
    - 计算室内空气温度
    - 计算各种热传递过程
    """
    
    def __init__(self, building_model, ventilation_ach: float = 0.2, 
                 sky_temp_weights: Optional[Dict[str, float]] = None):
        """
        初始化热平衡计算器
        
        参数：
            building_model: 建筑模型对象
            ventilation_ach: 换气次数 ACH (1/h)，作为显式配置，默认 0.2
            sky_temp_weights: 天空温度模型权重字典，格式：
                {
                    'epw_ir': 1.0,      # EPW红外辐射模型权重
                    'brunt': 0.4,       # Brunt模型权重
                    'brutsaert': 0.3,   # Brutsaert模型权重
                    'swinbank': 0.5     # Swinbank模型权重
                }
        """
        self.building_model = building_model
        self.materials_db = MaterialDatabase()
        # 通风换气次数（1/h）
        try:
            self.ventilation_ach = float(max(0.0, ventilation_ach))
        except Exception:
            self.ventilation_ach = 0.2
        
        # 物理常数
        self.stefan_boltzmann = 5.67e-8  # W/m²·K⁴
        self.air_density = 1.2  # kg/m³
        self.air_cp = 1005  # J/kg·K
        self.air_viscosity = 1.81e-5  # Pa·s
        self.air_thermal_conductivity = 0.026  # W/m·K
        
        # 天空温度模型权重（可配置）
        if sky_temp_weights is None:
            self.sky_temp_weights = {
                'epw_ir': 1.0,
                'brunt': 0.4,
                'brutsaert': 0.3,
                'swinbank': 0.5
            }
        else:
            self.sky_temp_weights = {
                'epw_ir': float(sky_temp_weights.get('epw_ir', 1.0)),
                'brunt': float(sky_temp_weights.get('brunt', 0.4)),
                'brutsaert': float(sky_temp_weights.get('brutsaert', 0.3)),
                'swinbank': float(sky_temp_weights.get('swinbank', 0.5))
            }
        
        # 仿真参数
        self.sky_temp_offset = 12  # K（天空温度偏差）
        self.convergence_tolerance = 0.005  # K，更严格
        self.max_iterations = 30  # 更多迭代提升稳定性
        self.zone_thermal_mass_factor = 30  # 保留配置但不再使用放大因子（改为实际热容）
    
    def _effective_sky_temperature(self, weather: Dict, T_outK: float) -> float:
        """
        基于天气数据估算有效天空温度（K）
        改进：使用加权平均并更严格的物理夹取
        """
        TaK = float(np.clip(T_outK, 200.0, 330.0))
        TdpC = weather.get('dew_point', None)
        N = weather.get('total_sky_cover', None)  # 0-10 → 0..1
        Nf = None
        try:
            if N is not None:
                Nf = float(N) / 10.0
        except Exception:
            Nf = None

        candidates: List[float] = []
        weights: List[float] = []

        # 1) EPW 水平红外辐射（最可信）
        L_sky = weather.get('infrared_sky_radiation', None)
        try:
            if L_sky is not None and float(L_sky) > 1.0:
                Tsky_ir = (float(L_sky) / self.stefan_boltzmann) ** 0.25
                candidates.append(float(Tsky_ir))
                weights.append(self.sky_temp_weights['epw_ir'])
        except Exception:
            pass

        # 水汽压 e（kPa）用于发射率模型
        e_kPa = None
        try:
            if TdpC is not None:
                e_hPa = 6.112 * 10 ** (7.5 * float(TdpC) / (237.7 + float(TdpC)))
                e_kPa = float(e_hPa) / 10.0
        except Exception:
            e_kPa = None

        # 2) Brunt（以露点近似）
        try:
            if TdpC is not None:
                e_hPa2 = 6.112 * 10 ** (7.5 * float(TdpC) / (237.7 + float(TdpC)))
                eps_clear_brunt = 0.51 + 0.066 * float(np.sqrt(max(e_hPa2, 0.0)))
                eps_clear_brunt = float(np.clip(eps_clear_brunt, 0.2, 1.0))
                eps_sky_brunt = eps_clear_brunt * (1.0 + 0.22 * (Nf ** 2)) if Nf is not None else eps_clear_brunt
                Tsky_brunt = (eps_sky_brunt ** 0.25) * TaK
                candidates.append(float(Tsky_brunt))
                weights.append(self.sky_temp_weights['brunt'])
        except Exception:
            pass

        # 3) Brutsaert（晴空发射率）
        try:
            if e_kPa is not None and e_kPa > 0.0:
                eps_clear_bruts = 1.24 * (e_kPa / max(TaK, 1.0)) ** (1.0 / 7.0)
            else:
                eps_clear_bruts = 0.72
            eps_clear_bruts = float(np.clip(eps_clear_bruts, 0.2, 1.0))
            eps_sky_bruts = eps_clear_bruts * (1.0 + 0.22 * (Nf ** 2)) if Nf is not None else eps_clear_bruts
            Tsky_bruts = (eps_sky_bruts ** 0.25) * TaK
            candidates.append(float(Tsky_bruts))
            weights.append(self.sky_temp_weights['brutsaert'])
        except Exception:
            pass

        # 4) Swinbank（晴空参考）
        try:
            L_clear = 5.31e-8 * (TaK ** 6)
            Tsky_swin = (L_clear / self.stefan_boltzmann) ** 0.25
            if Nf is not None:
                eps_clear = L_clear / (self.stefan_boltzmann * (TaK ** 4))
                eps_sky = eps_clear * (1.0 + 0.22 * (Nf ** 2))
                Tsky_swin = (eps_sky ** 0.25) * TaK
            candidates.append(float(Tsky_swin))
            weights.append(self.sky_temp_weights['swinbank'])
        except Exception:
            pass

        if not candidates:
            return TaK

        if len(candidates) == 1:
            Tsky = candidates[0]
        else:
            total_w = sum(weights) if sum(weights) > 0 else len(candidates)
            if total_w == 0:
                Tsky = float(np.median(candidates))
            else:
                weights = [w / total_w for w in weights]
                Tsky = float(sum(c * w for c, w in zip(candidates, weights)))

        # 更严格的物理约束：通常 T_sky 在 T_out-40K 到 T_out-2K 之间
        Tsky = float(np.clip(Tsky, TaK - 40.0, TaK - 2.0))
        return Tsky

    def _radiative_environment_temperature(self, orientation: str, T_skyK: float, T_outK: float) -> float:
        """
        计算围护外表所见的有效辐射环境温度（K）
        改进：使用通用视因子公式 F_sky = (1+cosβ)/2, F_ground=(1-cosβ)/2
        其中 β 为表面倾角（0=水平朝天，90=垂直，180=朝地）。
        """
        beta, _ = self._surface_tilt_azimuth(orientation)
        F_sky = 0.5 * (1.0 + float(np.cos(float(beta))))
        F_sky = float(np.clip(F_sky, 0.0, 1.0))
        T_ground = float(np.clip(T_outK, 200.0, 330.0))
        T_env4 = F_sky * (T_skyK ** 4) + (1.0 - F_sky) * (T_ground ** 4)
        T_env = float(np.clip(T_env4 ** 0.25, 150.0, 340.0))
        return T_env

    def calculate_surface_temperature(self, surface: Surface, weather: Dict, T_zone: float) -> float:
        """
        计算表面温度（稳定的线性化迭代）
        
        外表面热平衡（线性化处理长波辐射）：
        (h_ext + h_rad_ext + U) * T_ext = h_ext*T_out + h_rad_ext*T_sky + α*I_solar + U*T_zone
        其中 h_rad_ext = 4 * ε * σ * Tm^3，Tm 为代表温度（T_sky 与 T_ext 的均值并加以夹取）
        
        参数：
            surface: 表面对象
            weather: 天气数据字典
            T_zone: 室内温度 (K)
            
        返回：
            表面温度 (K)
        """
        # 基本温度（K）并夹取到合理范围，避免数值发散
        T_out = float(weather['temperature']) + 273.15
        T_zone = float(np.clip(T_zone, 250.0, 330.0))
        T_out = float(np.clip(T_out, 200.0, 330.0))
        # 使用天气文件推导的有效天空温度（优先 EPW 的水平红外辐射，其次露点+云量经验式）
        T_sky = self._effective_sky_temperature(weather, T_out)
        T_sky = float(np.clip(T_sky, 150.0, 330.0))
        
        # 材料导热等效系数（不含内外表面膜阻）
        U_cond = max(0.05, min(self._calculate_u_cond(surface.construction), 10.0))
        
        # 对地板使用地温边界：无风致对流、无太阳，辐射环境为地温
        ori_lower = (surface.orientation or '').lower()
        if ori_lower == 'floor':
            ann_mean = weather.get('annual_mean_temperature', None)
            if ann_mean is not None:
                T_groundK = float(ann_mean) + 273.15  # 以年平均干球近似地温
            else:
                T_groundK = T_out  # 回退
            # 外表面对流：极弱自然对流近似
            h_ext = 0.5
            I_solar = 0.0
            T_env_rad = T_groundK
        else:
            # 外表对流
            h_ext = self._calculate_exterior_convection_coefficient(
                float(weather.get('wind_speed', 2.0)), surface.orientation
            )
            h_ext = max(2.0, min(h_ext, 50.0))
            # 太阳辐射（W/m2），方向修正
            I_solar = float(self._calculate_surface_solar_radiation(surface, weather))
            I_solar = max(0.0, I_solar)
            # 有效外部辐射环境温度（根据朝向综合天空/地面）
            T_env_rad = self._radiative_environment_temperature(surface.orientation, T_sky, T_out)
        
        # 初值：外表面温度取室外空气温度
        T_ext = T_out
        relax = 0.3  # 松弛因子，提升稳定性
        # 先估一个内表面温度（初值=室温）
        h_int0 = self._calculate_interior_convection_coefficient(surface.orientation)
        inner_mat0 = surface.construction.inner_material() if surface.construction else None
        eps_in0 = (inner_mat0.emissivity if inner_mat0 and hasattr(inner_mat0, 'emissivity') else 0.9)
        h_rad_in0 = 4.0 * eps_in0 * self.stefan_boltzmann * float(np.clip(T_zone, 250.0, 330.0))**3
        h_rad_in0 = float(np.clip(h_rad_in0, 0.1, 10.0))
        h_in_tot_prev = max(0.1, h_int0 + h_rad_in0)
        T_int_prev = float(T_zone)
        for _ in range(30):
            # 从构造外层材料获取光学性质（若表面未显式设置）
            outer_mat = surface.construction.outer_material() if surface.construction else None
            emiss = float(surface.emissivity if hasattr(surface, 'emissivity') and surface.emissivity is not None else (outer_mat.emissivity if outer_mat else 0.9))
            alpha = float(surface.solar_absorptance if hasattr(surface, 'solar_absorptance') and surface.solar_absorptance is not None else (outer_mat.solar_absorptance if outer_mat else 0.6))

            # 线性化长波辐射（外表）
            # 使用 T_ext 作为代表温度 Tm，并采用严格线性化：
            # q_rad ≈ h_rad * (T_ext - T_env_lin)，其中
            # h_rad = 4 ε σ Tm^3；T_env_lin = (T_env^4 - Tm^4) / (4 Tm^3) + Tm
            Tm = float(np.clip(T_ext, 200.0, 330.0))
            h_rad_ext = 4.0 * emiss * self.stefan_boltzmann * (Tm ** 3)
            h_rad_ext = float(np.clip(h_rad_ext, 0.1, 20.0))
            # 环境等效温度（综合天空/地面）已在循环外计算为 T_env_rad
            T_env_lin = ((T_env_rad ** 4 - Tm ** 4) / (4.0 * (Tm ** 3))) + Tm
            T_env_lin = float(np.clip(T_env_lin, 150.0, 330.0))

            # 室内总换热系数（对流+辐射线性化），辐射取 4εσT_zone^3
            dT_int_iter = abs(T_zone - T_ext)
            h_int = self._calculate_interior_convection_coefficient(surface.orientation, dT=dT_int_iter)
            inner_mat = surface.construction.inner_material() if surface.construction else None
            eps_in = (inner_mat.emissivity if inner_mat and hasattr(inner_mat, 'emissivity') else 0.9)
            h_rad_in = 4.0 * eps_in * self.stefan_boltzmann * float(np.clip(T_zone, 250.0, 330.0))**3
            h_rad_in = float(np.clip(h_rad_in, 0.1, 10.0))
            h_in_tot = max(0.1, h_int + h_rad_in)

            # 外端线性方程，等效将传导端简化为 U_eq 与 T_zone 相连
            U_eq = (U_cond * h_in_tot) / (h_in_tot + U_cond)
            # 内表辐射通量对外表能量平衡的等效项：q_eq = (U_cond/(h_in_tot+U_cond))*q_int
            q_int = float(getattr(surface, 'internal_radiative_flux', 0.0) or 0.0)
            q_eq = (U_cond / max(h_in_tot + U_cond, 1e-6)) * q_int
            denom = h_ext + h_rad_ext + U_eq
            rhs = h_ext * T_out + h_rad_ext * T_env_lin + alpha * I_solar + U_eq * T_zone - q_eq
            T_new = rhs / max(denom, 1e-6)

            # 松弛与夹取
            T_new = (1.0 - relax) * T_ext + relax * T_new
            T_new = float(np.clip(T_new, 230.0, 340.0))

            if abs(T_new - T_ext) < self.convergence_tolerance:
                T_ext = T_new
                break
            T_ext = T_new

        # 由外表得到内表：h_in_tot*(T_int - T_zone) + U_cond*(T_int - T_ext) = 0
        # → T_int = (h_in_tot*T_zone + U_cond*T_ext)/(h_in_tot + U_cond)
        dT_int_final = abs(T_zone - T_ext)
        h_int = self._calculate_interior_convection_coefficient(surface.orientation, dT=dT_int_final)
        inner_mat = surface.construction.inner_material() if surface.construction else None
        eps_in = (inner_mat.emissivity if inner_mat and hasattr(inner_mat, 'emissivity') else 0.9)
        h_rad_in = 4.0 * eps_in * self.stefan_boltzmann * float(np.clip(T_zone, 250.0, 330.0))**3
        h_rad_in = float(np.clip(h_rad_in, 0.1, 10.0))
        h_in_tot = max(0.1, h_int + h_rad_in)
        # 加入内表面附加辐射通量（W/m2），使能量平衡为：
        # h_in_tot*(T_int - T_zone) + U_cond*(T_int - T_ext) + q_int = 0
        # → T_int = (h_in_tot*T_zone + U_cond*T_ext - q_int)/(h_in_tot+U_cond)
        q_int = float(getattr(surface, 'internal_radiative_flux', 0.0) or 0.0)
        T_int = (h_in_tot * T_zone + U_cond * T_ext - q_int) / max(h_in_tot + U_cond, 1e-6)
        T_int = float(np.clip(T_int, 230.0, 340.0))

        # 将用于室内换热计算的温度写入表面温度
        surface.temperature = T_int
        return T_int
    
    def calculate_zone_temperature(self, zone: Zone, weather: Dict) -> float:
        """
        计算室内空气温度（自由漂移，仅用于无空调时的近似）
        改进：使用实际建筑热容（空气+围护有效热容）而非人为放大系数。
        """
        # 计算各热源（以当前 zone.temperature 为基准）
        Q_solar = self._calculate_solar_gain(zone, weather)
        # 仅将一部分穿透太阳得热计入空气（其余视为辐射先加热表面）
        Q_solar_conv = 0.2 * Q_solar
        Q_conv = self._calculate_convection_heat(zone)
        # 室内长波辐射用于表面温度平衡，不直接计入空气平衡
        # Q_rad = self._calculate_radiation_heat(zone)
        Q_internal = self._calculate_internal_heat(zone)  # 已为显热对流部分
        Q_ventilation = self._calculate_ventilation_heat(zone, weather)
        Q_total = Q_solar_conv + Q_conv + Q_internal + Q_ventilation
        
        # 时间步长（秒）
        dt = 3600.0
        
        # 实际热容估算：
        # - 空气热容：ρ_air * V * cp
        # - 建筑有效热容：按体积折算的等效质量（经验：50 kg/m3），比热取 880 J/kgK（混凝土）
        C_air = self.air_density * float(zone.volume) * self.air_cp  # J/K
        effective_mass = float(zone.volume) * 50.0  # kg
        C_building = effective_mass * 880.0  # J/K
        C_total = max(1.0, C_air + C_building)
        
        dT = Q_total * dt / C_total
        # 仅做安全夹取，避免极端不稳定；不再使用人为 2 K 限制
        dT = float(np.clip(dT, -5.0, 5.0))
        zone.temperature = float(np.clip(zone.temperature + dT, 250.0, 330.0))
        return zone.temperature

    def _split_internal_loads(self, zone: Zone) -> Tuple[float, float, float]:
        """返回 (Q_internal_conv, Q_internal_rad, Q_internal_lat)"""""
        occupancy = float(zone.occupancy_density) * float(zone.area)
        # 人员显热约 75 W/人，其中 50% 对流、50% 辐射；潜热另算（此处忽略或返回）
        Q_occ_sens = occupancy * 75.0
        Q_occ_conv = 0.5 * Q_occ_sens
        Q_occ_rad = 0.5 * Q_occ_sens
        # 设备：50% 对流、50% 辐射（简化）
        Q_equip = float(zone.area) * float(zone.equipment_load)
        Q_equip_conv = 0.5 * Q_equip
        Q_equip_rad = 0.5 * Q_equip
        # 照明：38% 对流、62% 辐射（ASHRAE 典型）
        Q_light = float(zone.area) * float(zone.lighting_load)
        Q_light_conv = 0.38 * Q_light
        Q_light_rad = 0.62 * Q_light
        Q_conv = Q_occ_conv + Q_equip_conv + Q_light_conv
        Q_rad = Q_occ_rad + Q_equip_rad + Q_light_rad
        Q_lat = 0.0
        return float(Q_conv), float(Q_rad), float(Q_lat)

    def _distribute_internal_radiation(self, zone: Zone, Q_internal_rad: float, Q_solar_rad: float):
        """将室内辐射热均匀分配到内表面，设置 internal_radiative_flux (W/m2)"""
        total_rad = max(0.0, float(Q_internal_rad) + float(Q_solar_rad))
        # 总内表面积
        A = sum(max(0.0, s.area) for s in zone.surfaces)
        flux = (total_rad / max(A, 1e-6)) if total_rad > 0 else 0.0
        for s in zone.surfaces:
            s.internal_radiative_flux = float(flux)

    def compute_sensible_balance(self, zone: Zone, weather: Dict, T_zoneK: float) -> float:
        """
        以指定的室内温度 T_zoneK 计算热区的瞬时显热平衡（不考虑 HVAC）。
        返回 Q_total (W)：为正表示区内增热（需要制冷），为负表示区内散热（需要制热）。
        本函数会用 T_zoneK 更新每个围护表面的温度（用于随后输出和对流/辐射计算）。
        """
        # 在目标温度下，先计算太阳透过量与内部负荷分配
        Q_solar_total = self._calculate_solar_gain(zone, weather)
        Q_solar_conv = 0.2 * Q_solar_total
        Q_solar_rad = 0.8 * Q_solar_total
        Q_int_conv, Q_int_rad, _ = self._split_internal_loads(zone)
        # 在每个时间步开始先清零内表辐射通量
        for s in zone.surfaces:
            s.internal_radiative_flux = 0.0
        self._distribute_internal_radiation(zone, Q_int_rad, Q_solar_rad)

        # 以目标温度计算各围护表面温度（包含分配的内表辐射通量）
        for surface in zone.surfaces:
            self.calculate_surface_temperature(surface, weather, T_zoneK)
        
        # 计算各项热量分量（在 T_zoneK 下）
        T_prev = zone.temperature
        zone.temperature = T_zoneK
        Q_conv = self._calculate_convection_heat(zone)
        Q_ventilation = self._calculate_ventilation_heat(zone, weather)
        zone.temperature = T_prev  # 还原
        
        # 显热平衡：对流 + 通风 + 内部对流 + 太阳对流
        Q_total = Q_conv + Q_ventilation + Q_int_conv + Q_solar_conv
        return float(Q_total)
    
    def _calculate_exterior_convection_coefficient(self, wind_speed: float, orientation: str) -> float:
        """
        改进的外表面对流系数计算
        - 自然对流：基于 Rayleigh/Nusselt 相关式
        - 强制对流：方向相关的经验式
        - 组合：h = (h_nat^3 + h_wind^3)^(1/3)
        """
        wind_speed = float(max(0.0, wind_speed))
        # 自然对流参数
        L = 1.0  # m，特征长度
        dT = 5.0  # K，代表性温差
        g = 9.81
        nu = 1.5e-5  # m2/s
        Pr = 0.71
        beta = 1.0 / 300.0
        Ra = g * beta * dT * (L ** 3) / (nu * (nu / Pr))
        # 竖直面相关式（Churchill and Chu）
        if Ra < 1e9:
            Nu_nat = 0.68 + 0.67 * (Ra ** 0.25) / (1.0 + (0.492 / Pr) ** (9.0/16.0)) ** (4.0/9.0)
        else:
            Nu_nat = 0.825 + 0.387 * (Ra ** (1.0/6.0)) / (1.0 + (0.492 / Pr) ** (9.0/16.0)) ** (8.0/27.0)
        k_air = 0.026
        h_nat = float(np.clip(Nu_nat * k_air / L, 0.5, 8.0))
        # 强制对流（方向相关）
        ori = (orientation or '').lower()
        if ori == 'roof':
            c_wind, n_wind = 3.0, 0.6
        elif ori == 'floor':
            c_wind, n_wind = 2.0, 0.6
        else:
            c_wind, n_wind = 3.94, 0.6
        h_wind = float(np.clip(c_wind * (wind_speed ** n_wind), 0.0, 50.0))
        # 组合
        h_ext = (h_nat ** 3 + h_wind ** 3) ** (1.0 / 3.0)
        return float(np.clip(h_ext, 2.0, 50.0))
    
    def _calculate_interior_convection_coefficient(self, surface_orientation: str, dT: Optional[float] = None) -> float:
        """
        改进的内表面对流系数
        - 当提供 dT 时，使用基于 Rayleigh/Nusselt 的相关式
        - 否则回退到典型常数
        """
        # 回退：未提供温差则返回典型值
        if dT is None:
            if surface_orientation in ['North', 'South', 'East', 'West']:
                return 3.0
            if surface_orientation == 'Roof':
                return 4.0
            if surface_orientation == 'Floor':
                return 2.0
            return 3.0
        
        dT = float(max(0.1, abs(dT)))
        L = 1.0
        g = 9.81
        nu = 1.5e-5
        Pr = 0.71
        beta = 1.0 / 300.0
        Ra = g * beta * dT * (L ** 3) / (nu * (nu / Pr))
        ori = (surface_orientation or '').lower()
        if ori == 'roof':
            # 水平面，向上加热
            if Ra < 1e9:
                Nu = 0.54 * (Ra ** 0.25)
            else:
                Nu = 0.15 * (Ra ** (1.0/3.0))
        elif ori == 'floor':
            # 水平面，向下加热
            if Ra < 1e9:
                Nu = 0.27 * (Ra ** 0.25)
            else:
                Nu = 0.075 * (Ra ** (1.0/3.0))
        else:
            # 竖直面（Churchill and Chu）
            if Ra < 1e9:
                Nu = 0.68 + 0.67 * (Ra ** 0.25) / (1.0 + (0.492 / Pr) ** (9.0/16.0)) ** (4.0/9.0)
            else:
                Nu = 0.825 + 0.387 * (Ra ** (1.0/6.0)) / (1.0 + (0.492 / Pr) ** (9.0/16.0)) ** (8.0/27.0)
        h_int = float(np.clip(Nu * 0.026 / L, 1.0, 10.0))
        return h_int
    
    def _calculate_surface_solar_radiation(self, surface: Surface, weather: Dict) -> float:
        """
        计算倾斜面太阳辐射（W/m²）：采用简化的各向同性天空模型 + 地面反射
        I = DNI*cos(theta_i) + DHI*(1+cosβ)/2 + GHI*albedo*(1-cosβ)/2
        其中 cos(theta_i) 通过太阳位置与面倾角/方位角计算。
        缺测时回退到季节性方向系数近似。
        """
        # 地板不受太阳直接/漫反/地面反射（模型为室外地坪），统一按0处理
        if (surface.orientation or '').lower() == 'floor':
            return 0.0
        
        GHI = float(max(0.0, weather.get('solar_radiation', 0.0)))
        DNI = float(max(0.0, weather.get('direct_normal_radiation', 0.0)))
        DHI = float(max(0.0, weather.get('diffuse_horizontal_radiation', 0.0)))
        albedo = float(max(0.0, min(weather.get('albedo', 0.2), 0.9)))
        
        # 若必要的时间/地理信息缺失，则使用季节性方向系数回退
        has_geo = ('datetime' in weather and 'latitude' in weather and 'longitude' in weather and 'timezone' in weather)
        if not has_geo:
            # 改进的季节性方向系数（基于太阳高度角的月平均值）
            total_radiation = GHI
            current_month = weather.get('month', 6)
            if current_month in [12, 1, 2]:  # 冬季：太阳高度角最低
                direction_factor = {'South': 1.5, 'North': 0.1, 'East': 0.7, 'West': 0.7, 'Roof': 0.6, 'Floor': 0.0}
            elif current_month in [3, 4, 5]:  # 春季：过渡
                direction_factor = {'South': 1.2, 'North': 0.3, 'East': 0.9, 'West': 0.9, 'Roof': 0.9, 'Floor': 0.0}
            elif current_month in [6, 7, 8]:  # 夏季：太阳高度角最高
                direction_factor = {'South': 0.7, 'North': 0.5, 'East': 0.6, 'West': 0.6, 'Roof': 1.3, 'Floor': 0.0}
            else:  # 秋季：过渡
                direction_factor = {'South': 1.2, 'North': 0.2, 'East': 0.8, 'West': 0.8, 'Roof': 1.0, 'Floor': 0.0}
            factor = direction_factor.get(surface.orientation, 0.5)
            return total_radiation * factor
        
        # 基于太阳位置的计算
        dt = weather['datetime']
        lat = float(weather.get('latitude', 0.0))
        lon = float(weather.get('longitude', 0.0))
        tz = float(weather.get('timezone', 0.0))
        
        # 太阳位置（弧度）
        alpha, az = self._solar_alt_az(dt, lat, lon, tz)  # α: 地平高度角，az: 方位角（从北顺时针）
        if alpha <= 0:
            return 0.0
        
        # 面倾角与方位角
        beta, az_surf = self._surface_tilt_azimuth(surface.orientation)
        # 夹取
        beta = float(np.clip(beta, 0.0, np.pi))
        
        # 入射角余弦（以水平坐标系公式：cosθi = cosθz cosβ + sinθz sinβ cos(A - As)）
        theta_z = (np.pi / 2.0) - alpha
        cos_theta_i = np.cos(theta_z) * np.cos(beta) + np.sin(theta_z) * np.sin(beta) * np.cos(az - az_surf)
        cos_theta_i = float(max(0.0, cos_theta_i))
        
        # 若DNI缺失，基于 GHI/DHI 与太阳高度估算
        csz = float(max(1e-3, np.cos(theta_z)))
        if DNI <= 0.0:
            DNI = max(0.0, (GHI - DHI) / csz)
        
        I_beam = DNI * cos_theta_i
        I_diff = DHI * (1.0 + np.cos(beta)) * 0.5
        I_refl = GHI * albedo * (1.0 - np.cos(beta)) * 0.5
        I_surface = float(max(0.0, I_beam) + max(0.0, I_diff) + max(0.0, I_refl))
        return I_surface

    def _surface_tilt_azimuth(self, orientation: str) -> Tuple[float, float]:
        """将模型朝向转为（倾角β[rad]，方位角A_s[rad]，从北顺时针）。Roof=水平，Walls=垂直，Floor不受太阳。
        North=0°, East=90°, South=180°, West=270°
        """
        ori = (orientation or '').lower()
        if ori == 'roof':
            return 0.0, 0.0
        if ori == 'floor':
            return np.pi, 0.0  # 不用于太阳，返回β=180°
        if ori == 'north':
            return np.pi/2, 0.0
        if ori == 'east':
            return np.pi/2, np.deg2rad(90.0)
        if ori == 'south':
            return np.pi/2, np.deg2rad(180.0)
        if ori == 'west':
            return np.pi/2, np.deg2rad(270.0)
        # 默认按垂直南向
        return np.pi/2, np.deg2rad(180.0)

    def _solar_alt_az(self, dt, lat_deg: float, lon_deg: float, tz_hours: float) -> Tuple[float, float]:
        """简化太阳位置：返回（高度角α[rad]，方位角A[rad]，从北顺时针）。
        采用 Duffie & Beckman 近似：
        - 赤纬：Fourier 近似
        - 时间方程：近似
        - 太阳时角：基于经度与时区
        精度满足本模型用途。
        """
        lat = np.deg2rad(lat_deg)
        n = dt.timetuple().tm_yday
        # 日角
        gamma = 2.0 * np.pi * (n - 1) / 365.0
        # 赤纬（弧度）
        delta = (0.006918
                 - 0.399912 * np.cos(gamma)
                 + 0.070257 * np.sin(gamma)
                 - 0.006758 * np.cos(2*gamma)
                 + 0.000907 * np.sin(2*gamma)
                 - 0.002697 * np.cos(3*gamma)
                 + 0.00148  * np.sin(3*gamma))
        # 时间方程（分钟）
        EoT = 229.18 * (0.000075
                        + 0.001868 * np.cos(gamma)
                        - 0.032077 * np.sin(gamma)
                        - 0.014615 * np.cos(2*gamma)
                        - 0.040849 * np.sin(2*gamma))
        # 本地经度（度），时区中心经度
        Lst = 15.0 * tz_hours
        # 时间修正（分钟）
        time_offset = EoT + 4.0 * (lon_deg - Lst)
        # 真太阳时（小时）
        true_solar_time = dt.hour + dt.minute/60.0 + dt.second/3600.0 + time_offset/60.0
        # 时角（弧度），正西负东：从太阳中午起每小时15°
        H = np.deg2rad(15.0 * (true_solar_time - 12.0))
        
        # 太阳高度角
        sin_alpha = np.sin(lat) * np.sin(delta) + np.cos(lat) * np.cos(delta) * np.cos(H)
        alpha = float(np.arcsin(np.clip(sin_alpha, -1.0, 1.0)))
        if alpha <= 0:
            return 0.0, 0.0
        # 方位角（从北顺时针）
        cos_az = (np.sin(delta) - np.sin(alpha) * np.sin(lat)) / (np.cos(alpha) * np.cos(lat) + 1e-9)
        cos_az = float(np.clip(cos_az, -1.0, 1.0))
        az0 = float(np.arccos(cos_az))  # 0..π，需用时角判断东西
        az = az0 if (np.sin(H) >= 0) else (2.0 * np.pi - az0)
        return alpha, az
    
    def _calculate_solar_gain(self, zone: Zone, weather: Dict) -> float:
        """
        计算进入热区的太阳得热（仅透过透明围护结构的部分）。
        注意：不应把不透明围护结构吸收的太阳辐射直接算作室内得热，
        它应作用在外表面能量平衡并通过传导进入。
        这里仅对“窗”（construction 名称包含 "Window"）计算透射得热，
        采用简化的太阳透射率 tau_solar（默认 0.6）。
        """
        tau_solar = 0.6  # 简化的太阳透射率
        Q_solar = 0.0
        for surface in zone.surfaces:
            cons_name = surface.construction.name if surface.construction else ''
            if 'window' in cons_name.lower():
                I_surface = max(0.0, self._calculate_surface_solar_radiation(surface, weather))
                Q_solar += surface.area * tau_solar * I_surface
        return float(Q_solar)
    
    def _calculate_convection_heat(self, zone: Zone) -> float:
        """
        计算对流换热
        
        Q_conv = Σ(h_i * A_i * (T_surf_i - T_zone))
        
        参数：
            zone: 热区对象
            
        返回：
            对流换热 (W)
        """
        Q_conv = 0
        
        for surface in zone.surfaces:
            dT_local = abs(surface.temperature - zone.temperature)
            h_int = self._calculate_interior_convection_coefficient(surface.orientation, dT=dT_local)
            Q_conv += h_int * surface.area * (surface.temperature - zone.temperature)
        
        return Q_conv
    
    def _calculate_radiation_heat(self, zone: Zone) -> float:
        """
        计算长波辐射换热
        
        Q_rad = Σ(h_rad_i * A_i * (T_surf_i - T_zone))
        
        其中 h_rad = ε * σ * (T_surf² + T_zone²) * (T_surf + T_zone)
        
        参数：
            zone: 热区对象
            
        返回：
            辐射换热 (W)
        """
        Q_rad = 0
        
        for surface in zone.surfaces:
            # 温度夹取避免数值不稳定
            Ts = float(np.clip(surface.temperature, 230.0, 340.0))
            Tz = float(np.clip(zone.temperature, 230.0, 340.0))
            # 线性化室内长波辐射换热系数，并进行限制
            h_rad = (surface.emissivity * self.stefan_boltzmann *
                     (Ts**2 + Tz**2) * (Ts + Tz))
            h_rad = float(np.clip(h_rad, 0.1, 10.0))
            
            Q_rad += h_rad * surface.area * (Ts - Tz)
        
        return Q_rad
    
    def _calculate_internal_heat(self, zone: Zone) -> float:
        """
        计算内部热源（仅显热部分，潜热不计入此处）
        
        Q_internal_sensible = Q_occ_sens + Q_equip_sens + Q_light_sens
        
        参数：
            zone: 热区对象
            
        返回：
            内部显热 (W)
        """
        # 人员：总热约100 W/人，其中显热约 60~75 W（取 75 W）
        occupancy = float(zone.occupancy_density) * float(zone.area)
        Q_occ_sens = occupancy * 75.0
        
        # 设备：多数为显热，取 90% 作为显热
        Q_equip_sens = float(zone.area) * float(zone.equipment_load) * 0.9
        
        # 照明：近似全部为显热
        Q_light_sens = float(zone.area) * float(zone.lighting_load)
        
        Q_internal = Q_occ_sens + Q_equip_sens + Q_light_sens
        
        return float(Q_internal)
    
    def _calculate_ventilation_heat(self, zone: Zone, weather: Dict) -> float:
        """
        计算通风换热
        
        Q_vent = ṁ_vent * cp * (T_out - T_zone)
        其中 ṁ_vent = ρ * Vdot，ρ 采用现场气象的理想气体密度 ρ = p / (R·T)
        
        参数：
            zone: 热区对象
            weather: 天气数据字典
            
        返回：
            通风换热 (W)
        """
        T_out = float(weather['temperature']) + 273.15
        p_out = float(weather.get('atmospheric_pressure', 101325.0))  # Pa，EPW 通常为站压
        R_air = 287.058  # J/kg·K
        # 采用现场密度，必要时夹取
        rho_out = float(np.clip(p_out / max(R_air * T_out, 1e-3), 0.6, 1.6))
        
        # 通风空气流量（显式配置的换气次数 ACH）
        air_change_rate = float(getattr(self, 'ventilation_ach', 0.2))  # 1/h
        volume_flow = zone.volume * air_change_rate / 3600.0  # m³/s
        mass_flow = rho_out * volume_flow  # kg/s
        
        Q_vent = mass_flow * self.air_cp * (T_out - zone.temperature)
        
        return float(Q_vent)
    
    def _calculate_u_value(self, construction: Construction) -> float:
        """
        计算围护结构传热系数 U 值（含内外表面膜阻的传统估算）
        目前仅供兼容，新的表面求解改用 _calculate_u_cond（纯导热项）。
        """
        if construction is None:
            return 0.5  # 默认值
        R_ext = 1 / 25  # 假设 h_ext = 25 W/m²·K
        R_int = 1 / 8   # 假设 h_int = 8 W/m²·K
        R_materials = 0.0
        for material in construction.layers:
            k = max(0.01, float(material.conductivity))
            d = max(1e-4, float(material.thickness))
            R_materials += d / k
        R_total = R_ext + R_materials + R_int
        U = 1.0 / max(R_total, 1e-6)
        return float(np.clip(U, 0.05, 10.0))

    def _calculate_u_cond(self, construction: Construction) -> float:
        """
        仅材料导热等效传热系数（不含内外表面膜阻），用于外表/内表联合线性化时的等效U。
        U_cond = 1 / Σ(d_i/λ_i)
        """
        if construction is None or not construction.layers:
            return 1.0
        Rm = 0.0
        for material in construction.layers:
            k = max(0.01, float(material.conductivity))
            d = max(1e-4, float(material.thickness))
            Rm += d / k
        U = 1.0 / max(Rm, 1e-6)
        return float(np.clip(U, 0.05, 10.0))
    
    def get_zone_heat_summary(self, zone: Zone, weather: Dict) -> Dict:
        """
        获取热区热平衡摘要
        
        参数：
            zone: 热区对象
            weather: 天气数据字典
            
        返回：
            包含各热源的字典
        """
        return {
            'solar_gain': self._calculate_solar_gain(zone, weather),
            'convection': self._calculate_convection_heat(zone),
            'radiation': self._calculate_radiation_heat(zone),
            'internal': self._calculate_internal_heat(zone),
            'ventilation': self._calculate_ventilation_heat(zone, weather),
            'zone_temperature': zone.temperature - 273.15,
        }

