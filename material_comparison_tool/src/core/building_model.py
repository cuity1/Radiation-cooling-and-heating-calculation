"""
建筑模型 - 定义固定的热区和围护结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np


@dataclass
class Material:
    """材料类（从外到内层叠）"""
    name: str
    thickness: float  # m
    conductivity: float  # W/m·K
    density: float  # kg/m³
    specific_heat: float  # J/kg·K
    solar_absorptance: float = 0.6  # 太阳吸收率（0-1），用于外表面
    emissivity: float = 0.9  # 红外发射率（0-1），用于长波辐射


@dataclass
class Construction:
    """构造类（多层材料）"""
    name: str
    layers: List[Material] = field(default_factory=list)
    
    def add_layer(self, material: Material):
        """添加材料层（从外到内）"""
        self.layers.append(material)
    
    def outer_material(self) -> Material | None:
        return self.layers[0] if self.layers else None
    
    def inner_material(self) -> Material | None:
        return self.layers[-1] if self.layers else None


@dataclass
class Surface:
    """表面类"""
    name: str
    zone: str  # 所属热区名称
    area: float  # m²
    orientation: str  # 'North', 'South', 'East', 'West', 'Roof', 'Floor'
    construction: Optional[Construction] = None
    # 若为 None 则使用构造外层材料的属性
    solar_absorptance: Optional[float] = None  # 太阳吸收率
    emissivity: Optional[float] = None  # 发射率
    
    # 计算结果
    temperature: float = 293.15  # K（初始值 20°C）
    # 内表面附加辐射通量（W/m2），用于吸收内部辐射与穿透太阳的辐射份额
    internal_radiative_flux: float = 0.0


@dataclass
class Zone:
    """热区类"""
    name: str
    volume: float  # m³
    area: float = 100  # m²（平面面积）
    occupancy_density: float = 0.05  # person/m²
    equipment_load: float = 10  # W/m²
    lighting_load: float = 5  # W/m²
    
    # 表面列表
    surfaces: List[Surface] = field(default_factory=list)
    
    # 计算结果
    temperature: float = 293.15  # K（初始值 20°C）
    cooling_load: float = 0  # W
    heating_load: float = 0  # W
    latent_load: float = 0  # W
    cooling_energy: float = 0  # J
    heating_energy: float = 0  # J
    surface_temperatures: Dict[str, float] = field(default_factory=dict)
    
    def add_surface(self, surface: Surface):
        """添加表面"""
        self.surfaces.append(surface)


class BuildingModel:
    """
    建筑模型 - 定义固定的建筑几何和热性能
    
    这是一个精简模型，包含：
    - 1 个主热区（办公室）
    - 4 个外墙（南、北、东、西）
    - 1 个屋顶
    - 1 个地板
    """
    
    def __init__(self, config: Dict):
        """
        初始化建筑模型
        
        参数：
            config: 配置字典
        """
        self.zones: List[Zone] = []
        self.constructions: Dict[str, Construction] = {}
        
        # 从配置创建建筑
        self._create_building_from_config(config)
    
    def _create_building_from_config(self, config: Dict):
        """从配置创建建筑"""
        # 创建预定义的构造
        self._create_constructions()
        
        # 创建热区
        for zone_config in config.get('zones', []):
            zone = self._create_zone_from_config(zone_config)
            self.zones.append(zone)
    
    def _create_constructions(self):
        """创建预定义的围护结构"""
        
        # 标准外墙（从外到内：砖 → 保温 → 混凝土）
        wall_standard = Construction('Wall_Standard')
        wall_standard.add_layer(Material('Brick', 0.1, 0.6, 1600, 840, solar_absorptance=0.6, emissivity=0.9))
        wall_standard.add_layer(Material('Insulation', 0.05, 0.04, 30, 840, solar_absorptance=0.5, emissivity=0.9))
        wall_standard.add_layer(Material('Concrete', 0.2, 1.4, 2300, 880, solar_absorptance=0.6, emissivity=0.9))
        self.constructions['Wall_Standard'] = wall_standard
        
        # 高性能外墙（从外到内：砖 → 高性能保温 → 混凝土）
        wall_high_performance = Construction('Wall_HighPerformance')
        wall_high_performance.add_layer(Material('Brick', 0.1, 0.6, 1600, 840, solar_absorptance=0.6, emissivity=0.9))
        wall_high_performance.add_layer(Material('Insulation_Premium', 0.1, 0.025, 25, 840, solar_absorptance=0.5, emissivity=0.9))
        wall_high_performance.add_layer(Material('Concrete', 0.2, 1.4, 2300, 880, solar_absorptance=0.6, emissivity=0.9))
        self.constructions['Wall_HighPerformance'] = wall_high_performance
        
        # 屋顶（从外到内：膜层 → 保温 → 混凝土）
        roof = Construction('Roof_Standard')
        roof.add_layer(Material('Membrane', 0.01, 0.2, 1000, 1000, solar_absorptance=0.7, emissivity=0.9))
        roof.add_layer(Material('Insulation', 0.1, 0.04, 30, 840, solar_absorptance=0.5, emissivity=0.9))
        roof.add_layer(Material('Concrete', 0.15, 1.4, 2300, 880, solar_absorptance=0.6, emissivity=0.9))
        self.constructions['Roof_Standard'] = roof
        
        # 地板（混凝土）
        floor = Construction('Floor_Standard')
        floor.add_layer(Material('Concrete', 0.2, 1.4, 2300, 880))
        self.constructions['Floor_Standard'] = floor
        
        # 玻璃窗
        window = Construction('Window_Standard')
        window.add_layer(Material('Glass', 0.006, 0.8, 2500, 840))
        self.constructions['Window_Standard'] = window
    
    def _create_zone_from_config(self, zone_config: Dict) -> Zone:
        """从配置创建热区"""
        zone = Zone(
            name=zone_config.get('name', 'Zone1'),
            volume=zone_config.get('volume', 500),
            area=zone_config.get('area', 100),
            occupancy_density=zone_config.get('occupancy_density', 0.05),
            equipment_load=zone_config.get('equipment_load', 10),
            lighting_load=zone_config.get('lighting_load', 5),
        )
        
        # 添加表面
        for surface_config in zone_config.get('surfaces', []):
            surface = self._create_surface_from_config(surface_config)
            zone.add_surface(surface)
        
        return zone
    
    def _create_surface_from_config(self, surface_config: Dict) -> Surface:
        """从配置创建表面"""
        construction_name = surface_config.get('construction', 'Wall_Standard')
        construction = self.constructions.get(construction_name)
        
        surface = Surface(
            name=surface_config.get('name', 'Surface'),
            zone=surface_config.get('zone', 'Zone1'),
            area=surface_config.get('area', 100),
            orientation=surface_config.get('orientation', 'South'),
            construction=construction,
            solar_absorptance=surface_config.get('solar_absorptance', 0.6),
            emissivity=surface_config.get('emissivity', 0.9),
        )
        
        return surface
    
    @staticmethod
    def create_default_building() -> 'BuildingModel':
        """
        创建默认建筑模型
        
        返回：
            包含 1 个热区和标准围护结构的建筑模型
        """
        config = {
            'zones': [
                {
                    'name': 'Zone1',
                    'volume': 500,
                    'area': 100,
                    'occupancy_density': 0.05,
                    'equipment_load': 10,
                    'lighting_load': 5,
                    'surfaces': [
                        {
                            'name': 'ExtWall_South',
                            'zone': 'Zone1',
                            'area': 100,
                            'orientation': 'South',
                            'construction': 'Wall_Standard',
                            'solar_absorptance': 0.6,
                            'emissivity': 0.9,
                        },
                        {
                            'name': 'ExtWall_North',
                            'zone': 'Zone1',
                            'area': 100,
                            'orientation': 'North',
                            'construction': 'Wall_Standard',
                            'solar_absorptance': 0.4,
                            'emissivity': 0.9,
                        },
                        {
                            'name': 'ExtWall_East',
                            'zone': 'Zone1',
                            'area': 80,
                            'orientation': 'East',
                            'construction': 'Wall_Standard',
                            'solar_absorptance': 0.6,
                            'emissivity': 0.9,
                        },
                        {
                            'name': 'ExtWall_West',
                            'zone': 'Zone1',
                            'area': 80,
                            'orientation': 'West',
                            'construction': 'Wall_Standard',
                            'solar_absorptance': 0.6,
                            'emissivity': 0.9,
                        },
                        {
                            'name': 'Roof',
                            'zone': 'Zone1',
                            'area': 150,
                            'orientation': 'Roof',
                            'construction': 'Roof_Standard',
                            'solar_absorptance': 0.7,
                            'emissivity': 0.9,
                        },
                        {
                            'name': 'Floor',
                            'zone': 'Zone1',
                            'area': 150,
                            'orientation': 'Floor',
                            'construction': 'Floor_Standard',
                            'solar_absorptance': 0.5,
                            'emissivity': 0.9,
                        },
                    ]
                }
            ]
        }
        
        return BuildingModel(config)
    
    def get_zone(self, zone_name: str) -> Optional[Zone]:
        """获取指定名称的热区"""
        for zone in self.zones:
            if zone.name == zone_name:
                return zone
        return None
    
    def get_total_area(self) -> float:
        """获取总建筑面积"""
        return sum(zone.area for zone in self.zones)
    
    def get_total_volume(self) -> float:
        """获取总建筑体积"""
        return sum(zone.volume for zone in self.zones)
    
    def print_summary(self):
        """打印建筑模型摘要"""
        print("\n" + "="*50)
        print("建筑模型摘要")
        print("="*50)
        print(f"热区数量: {len(self.zones)}")
        print(f"总面积: {self.get_total_area():.1f} m²")
        print(f"总体积: {self.get_total_volume():.1f} m³")
        print("\n热区详情:")
        for zone in self.zones:
            print(f"\n  {zone.name}:")
            print(f"    体积: {zone.volume:.1f} m³")
            print(f"    面积: {zone.area:.1f} m²")
            print(f"    人员密度: {zone.occupancy_density:.2f} person/m²")
            print(f"    设备负荷: {zone.equipment_load:.1f} W/m²")
            print(f"    照明负荷: {zone.lighting_load:.1f} W/m²")
            print(f"    表面数量: {len(zone.surfaces)}")
            for surface in zone.surfaces:
                print(f"      - {surface.name}: {surface.area:.1f} m² ({surface.orientation})")
        print("="*50 + "\n")

