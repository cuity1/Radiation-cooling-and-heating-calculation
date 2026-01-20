"""
材料数据库 - 存储常见建筑材料的热性能参数
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Material:
    """材料类"""
    name: str
    conductivity: float  # W/m·K
    density: float  # kg/m³
    specific_heat: float  # J/kg·K
    thickness: float = 0.1  # m（默认厚度）
    
    def __str__(self):
        return f"{self.name} (λ={self.conductivity} W/m·K, ρ={self.density} kg/m³)"


class MaterialDatabase:
    """
    材料数据库
    
    包含常见建筑材料的热性能参数
    """
    
    def __init__(self):
        """初始化材料数据库"""
        self.materials: Dict[str, Material] = {}
        self._populate_database()
    
    def _populate_database(self):
        """填充数据库"""
        
        # 混凝土类
        self.add_material(Material(
            name='Concrete',
            conductivity=1.4,
            density=2300,
            specific_heat=880
        ))
        
        self.add_material(Material(
            name='Lightweight_Concrete',
            conductivity=0.5,
            density=1200,
            specific_heat=840
        ))
        
        # 砖类
        self.add_material(Material(
            name='Brick',
            conductivity=0.6,
            density=1600,
            specific_heat=840
        ))
        
        self.add_material(Material(
            name='Hollow_Brick',
            conductivity=0.3,
            density=1000,
            specific_heat=840
        ))
        
        # 保温材料
        self.add_material(Material(
            name='Insulation_Standard',
            conductivity=0.04,
            density=30,
            specific_heat=840
        ))
        
        self.add_material(Material(
            name='Insulation_Premium',
            conductivity=0.025,
            density=25,
            specific_heat=840
        ))
        
        self.add_material(Material(
            name='Mineral_Wool',
            conductivity=0.035,
            density=80,
            specific_heat=840
        ))
        
        self.add_material(Material(
            name='Polystyrene',
            conductivity=0.03,
            density=20,
            specific_heat=1400
        ))
        
        self.add_material(Material(
            name='Polyurethane',
            conductivity=0.025,
            density=30,
            specific_heat=1400
        ))
        
        # 玻璃
        self.add_material(Material(
            name='Glass',
            conductivity=0.8,
            density=2500,
            specific_heat=840
        ))
        
        self.add_material(Material(
            name='Double_Glass',
            conductivity=0.15,  # 有空气层
            density=2500,
            specific_heat=840
        ))
        
        # 金属
        self.add_material(Material(
            name='Aluminum',
            conductivity=160,
            density=2700,
            specific_heat=900
        ))
        
        self.add_material(Material(
            name='Steel',
            conductivity=50,
            density=7850,
            specific_heat=490
        ))
        
        # 木材
        self.add_material(Material(
            name='Wood',
            conductivity=0.15,
            density=600,
            specific_heat=1600
        ))
        
        self.add_material(Material(
            name='Plywood',
            conductivity=0.12,
            density=500,
            specific_heat=1500
        ))
        
        # 膜材料
        self.add_material(Material(
            name='Membrane',
            conductivity=0.2,
            density=1000,
            specific_heat=1000
        ))
        
        self.add_material(Material(
            name='Asphalt',
            conductivity=0.7,
            density=2100,
            specific_heat=920
        ))
        
        # 石膏板
        self.add_material(Material(
            name='Gypsum_Board',
            conductivity=0.16,
            density=750,
            specific_heat=1090
        ))
        
        # 陶土
        self.add_material(Material(
            name='Ceramic_Tile',
            conductivity=1.0,
            density=2300,
            specific_heat=840
        ))
        
        # 土壤
        self.add_material(Material(
            name='Soil',
            conductivity=1.5,
            density=1600,
            specific_heat=1600
        ))
        
        # 空气层（等效）
        self.add_material(Material(
            name='Air_Layer_10mm',
            conductivity=0.026,
            density=1.2,
            specific_heat=1005
        ))
    
    def add_material(self, material: Material):
        """
        添加材料到数据库
        
        参数：
            material: 材料对象
        """
        self.materials[material.name] = material
    
    def get_material(self, name: str) -> Optional[Material]:
        """
        获取材料
        
        参数：
            name: 材料名称
            
        返回：
            材料对象，如果不存在返回 None
        """
        return self.materials.get(name)
    
    def list_materials(self) -> List[str]:
        """获取所有材料名称列表"""
        return list(self.materials.keys())
    
    def print_catalog(self):
        """打印材料目录"""
        print("\n" + "="*70)
        print("建筑材料数据库")
        print("="*70)
        print(f"{'材料名称':<25} {'导热系数':<12} {'密度':<12} {'比热':<12}")
        print(f"{'':25} {'W/m·K':<12} {'kg/m³':<12} {'J/kg·K':<12}")
        print("-"*70)
        
        for name, material in sorted(self.materials.items()):
            print(f"{name:<25} {material.conductivity:<12.3f} "
                  f"{material.density:<12.1f} {material.specific_heat:<12.1f}")
        
        print("="*70 + "\n")
    
    def get_material_properties(self, name: str) -> Dict:
        """
        获取材料属性字典
        
        参数：
            name: 材料名称
            
        返回：
            材料属性字典
        """
        material = self.get_material(name)
        if material is None:
            return {}
        
        return {
            'name': material.name,
            'conductivity': material.conductivity,
            'density': material.density,
            'specific_heat': material.specific_heat,
            'thermal_diffusivity': material.conductivity / (material.density * material.specific_heat),
        }
    
    def compare_materials(self, names: List[str]) -> Dict:
        """
        对比多个材料的热性能
        
        参数：
            names: 材料名称列表
            
        返回：
            对比结果字典
        """
        comparison = {}
        
        for name in names:
            material = self.get_material(name)
            if material:
                comparison[name] = {
                    'conductivity': material.conductivity,
                    'density': material.density,
                    'specific_heat': material.specific_heat,
                    'thermal_resistance_per_cm': 0.01 / material.conductivity,  # 1 cm 厚度的热阻
                }
        
        return comparison


# 预定义的标准构造
class StandardConstructions:
    """标准围护结构定义"""
    
    @staticmethod
    def get_standard_wall() -> List[Material]:
        """标准外墙（混凝土 + 保温 + 砖）"""
        db = MaterialDatabase()
        return [
            db.get_material('Concrete'),
            db.get_material('Insulation_Standard'),
            db.get_material('Brick'),
        ]
    
    @staticmethod
    def get_high_performance_wall() -> List[Material]:
        """高性能外墙（更厚的保温）"""
        db = MaterialDatabase()
        return [
            db.get_material('Concrete'),
            db.get_material('Insulation_Premium'),
            db.get_material('Brick'),
        ]
    
    @staticmethod
    def get_roof() -> List[Material]:
        """标准屋顶"""
        db = MaterialDatabase()
        return [
            db.get_material('Concrete'),
            db.get_material('Insulation_Standard'),
            db.get_material('Membrane'),
        ]
    
    @staticmethod
    def get_floor() -> List[Material]:
        """标准地板"""
        db = MaterialDatabase()
        return [
            db.get_material('Concrete'),
        ]
    
    @staticmethod
    def get_window() -> List[Material]:
        """标准窗户"""
        db = MaterialDatabase()
        return [
            db.get_material('Double_Glass'),
        ]


# 示例用法
if __name__ == '__main__':
    # 创建数据库
    db = MaterialDatabase()
    
    # 打印目录
    db.print_catalog()
    
    # 获取单个材料
    concrete = db.get_material('Concrete')
    print(f"混凝土属性：{db.get_material_properties('Concrete')}")
    
    # 对比材料
    comparison = db.compare_materials(['Insulation_Standard', 'Insulation_Premium', 'Polystyrene'])
    print("\n保温材料对比：")
    for name, props in comparison.items():
        print(f"{name}:")
        print(f"  导热系数: {props['conductivity']} W/m·K")
        print(f"  1cm 热阻: {props['thermal_resistance_per_cm']:.4f} m²·K/W")

