"""
材料对比示例 - 聚焦辐射制冷：比较围护外层光学/热学参数（α/ε/λ）对 HVAC 能耗的影响

用法：
  python examples/compare_materials.py          # 默认启动 GUI 界面
  python examples/compare_materials.py --cli   # 使用命令行模式

说明：
- 仅修改围护"外层材料"的太阳吸收率(alpha)、红外发射率(emissivity)、导热系数(conductivity)。
- 太阳吸收率与发射率用于外表面能量平衡（短波得热、长波辐射散热），导热系数用于 U 值（通过传导影响室内负荷）。
- 天气：批量扫描项目/当前工作目录下的 weather/**/*.epw，预先计算“天气×场景”的总任务数，采用全局并行运行并汇总。
"""

import sys
import os
import json
import pandas as pd
import glob
import tempfile
import concurrent.futures as cf
from typing import List, Dict, Any, Optional
import time

# GUI: 按需导入，避免在无 PyQt5 环境下影响 CLI 使用
try:
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QTabWidget,
        QVBoxLayout,
        QHBoxLayout,
        QFormLayout,
        QLineEdit,
        QPushButton,
        QDoubleSpinBox,
        QFileDialog,
        QMessageBox,
        QGroupBox,
        QTextEdit,
        QCheckBox,
    )
    from PyQt5.QtCore import QThread, pyqtSignal, QUrl
    from PyQt5.QtGui import QDesktopServices, QCloseEvent
except Exception:  # pragma: no cover
    QApplication = None
    QThread = None
    pyqtSignal = None
    QDesktopServices = None
    QUrl = None


# 添加 src 目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core import SimulationEngine
import logging

def get_exe_dir() -> str:
    """获取exe文件所在的目录（如果是打包后的exe）或当前脚本所在目录（开发环境）。
    
    返回：exe文件所在的目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.dirname(sys.executable)
    else:
        # 开发环境：返回脚本所在目录的父目录（项目根目录）
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def get_weather_dir() -> str:
    """获取天气文件夹路径（位于exe文件旁边）。"""
    exe_dir = get_exe_dir()
    return os.path.join(exe_dir, 'weather')


def get_output_dir() -> str:
    """获取结果输出文件夹路径（位于exe文件旁边）。"""
    exe_dir = get_exe_dir()
    return os.path.join(exe_dir, 'output', 'comparison')


def find_epw_files() -> List[str]:
    """在以下位置查找所有 EPW 文件：
    1) <exe文件目录>/weather/**/*.epw（优先）
    2) <当前工作目录>/weather/**/*.epw
    3) <项目目录>/weather/**/*.epw（以本脚本为基准，开发环境）
    """
    epw_files: List[str] = []

    # 1) exe文件旁边的weather文件夹（优先）
    exe_weather = get_weather_dir()
    if os.path.isdir(exe_weather):
        epw_files.extend(glob.glob(os.path.join(exe_weather, '**', '*.epw'), recursive=True))

    # 2) 当前工作目录
    cwd_weather = os.path.join(os.getcwd(), 'weather')
    if os.path.isdir(cwd_weather):
        epw_files.extend(glob.glob(os.path.join(cwd_weather, '**', '*.epw'), recursive=True))

    # 3) 项目目录（以当前文件为基准，开发环境）
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    proj_weather = os.path.join(project_root, 'weather')
    if os.path.isdir(proj_weather):
        epw_files.extend(glob.glob(os.path.join(proj_weather, '**', '*.epw'), recursive=True))

    # 去重并排序
    epw_files = sorted(list(dict.fromkeys(epw_files)))
    return epw_files


def create_config_with_material(epw_path: str, sky_temp_weights: Optional[Dict[str, float]] = None) -> dict:
    """创建配置（材料属性由运行时注入；天气使用传入的 EPW 路径）
    
    参数：
        epw_path: EPW文件路径
        sky_temp_weights: 天空温度模型权重字典（可选）
    """
    config = {
        "simulation": {
            "start_month": 1,
            "start_day": 1,
            "end_month": 12,
            "end_day": 31,
            "timestep": 1,
            "warmup_days": int(os.environ.get('MATERIALS_WARMUP_DAYS', '7')),
            "use_epw_dates": True,
            "progress_interval_hours": 0
        },
        "building": {
            "zones": [
                {
                    "name": "Zone1",
                    "volume": 500,
                    "area": 100,
                    "occupancy_density": 0.05,
                    "equipment_load": 10,
                    "lighting_load": 5,
                    "surfaces": [
                        {"name": "ExtWall_South", "zone": "Zone1", "area": 100, "orientation": "South", "construction": "Wall_Standard"},
                        {"name": "ExtWall_North", "zone": "Zone1", "area": 100, "orientation": "North", "construction": "Wall_Standard"},
                        {"name": "ExtWall_East",  "zone": "Zone1", "area": 80,  "orientation": "East",  "construction": "Wall_Standard"},
                        {"name": "ExtWall_West",  "zone": "Zone1", "area": 80,  "orientation": "West",  "construction": "Wall_Standard"},
                        {"name": "Roof",          "zone": "Zone1", "area": 150, "orientation": "Roof",  "construction": "Roof_Standard"},
                        {"name": "Floor",         "zone": "Zone1", "area": 150, "orientation": "Floor", "construction": "Floor_Standard"}
                    ]
                }
            ]
        },
        "hvac": {
            "cooling_setpoint": 26,
            "heating_setpoint": 20,
            "humidity_setpoint": 0.5,
            "cop_cooling": 3.5,
            "cop_heating": 3.0,
            "cop_ref_temp": 35,
            "cop_temp_coeff_a": -0.01,
            "cop_temp_coeff_b": 0.0001,
            "plr_coeff_a": 0.125,
            "plr_coeff_b": 0.875,
            "max_cooling_capacity": 50000,
            "max_heating_capacity": 40000,
            "air_mass_flow": 2.0,
            "ventilation_ach": 0.2
        },
        "weather": {
            "epw_file": epw_path
        }
    }
    
    # 如果提供了天空温度权重，添加到配置中
    if sky_temp_weights is not None:
        config["simulation"]["sky_temp_weights"] = sky_temp_weights
    
    return config


def _apply_material_scenario(engine: SimulationEngine, wall: dict, roof: dict):
    """把场景材料参数应用到模型：仅修改外层材料的 α（吸收率）、ε（发射率）、λ（导热系数）。
    同时，为确保生效，也把对应 Surface 的 solar_absorptance/emissivity 设置为场景值（优先级高于材料）。
    """
    bm = engine.building_model
    # 墙体外层（例如抹灰/涂层/外饰面）
    wall_cons = bm.constructions.get('Wall_Standard')
    if wall_cons and wall_cons.layers:
        m = wall_cons.layers[0]  # 外层
        if 'alpha' in wall and wall['alpha'] is not None:
            m.solar_absorptance = float(wall['alpha'])
        if 'emissivity' in wall and wall['emissivity'] is not None:
            m.emissivity = float(wall['emissivity'])
        if 'conductivity' in wall and wall['conductivity'] is not None:
            m.conductivity = float(wall['conductivity'])
    # 屋面外层
    roof_cons = bm.constructions.get('Roof_Standard')
    if roof_cons and roof_cons.layers:
        m = roof_cons.layers[0]
        if 'alpha' in roof and roof['alpha'] is not None:
            m.solar_absorptance = float(roof['alpha'])
        if 'emissivity' in roof and roof['emissivity'] is not None:
            m.emissivity = float(roof['emissivity'])
        if 'conductivity' in roof and roof['conductivity'] is not None:
            m.conductivity = float(roof['conductivity'])

    # 直接在 Surface 层面也设置（保证被热平衡优先采纳）
    for z in bm.zones:
        for s in z.surfaces:
            if s.orientation in ['South', 'North', 'East', 'West']:
                if 'alpha' in wall and wall['alpha'] is not None:
                    s.solar_absorptance = float(wall['alpha'])
                if 'emissivity' in wall and wall['emissivity'] is not None:
                    s.emissivity = float(wall['emissivity'])
            elif s.orientation == 'Roof':
                if 'alpha' in roof and roof['alpha'] is not None:
                    s.solar_absorptance = float(roof['alpha'])
                if 'emissivity' in roof and roof['emissivity'] is not None:
                    s.emissivity = float(roof['emissivity'])


def _log_outer_layer_params(engine: SimulationEngine):
    """打印当前模型中墙/屋面外层材料的 α/ε/λ 参数，便于核对场景是否生效。"""
    bm = engine.building_model
    def fmt(val, nd=3):
        try:
            return f"{float(val):.{nd}f}"
        except Exception:
            return str(val)

    # 墙
    wall_cons = bm.constructions.get('Wall_Standard')
    if wall_cons and wall_cons.layers:
        wm = wall_cons.layers[0]
        print(f"    墙外层(材料): alpha={fmt(wm.solar_absorptance)}, eps={fmt(wm.emissivity)}, lambda={fmt(wm.conductivity)} W/mK")
    else:
        print("    墙外层: 未找到 Wall_Standard 或其外层材料")

    # 屋面
    roof_cons = bm.constructions.get('Roof_Standard')
    if roof_cons and roof_cons.layers:
        rm = roof_cons.layers[0]
        print(f"    屋面外层(材料): alpha={fmt(rm.solar_absorptance)}, eps={fmt(rm.emissivity)}, lambda={fmt(rm.conductivity)} W/mK")
    else:
        print("    屋面外层: 未找到 Roof_Standard 或其外层材料")

    # 同时打印 Surface 层面的实际生效（优先级更高）
    for z in bm.zones:
        for s in z.surfaces:
            if s.orientation in ['South','North','East','West','Roof']:
                a = getattr(s, 'solar_absorptance', None)
                e = getattr(s, 'emissivity', None)
                if a is not None or e is not None:
                    print(f"      Surface {s.name}({s.orientation}) 覆盖: alpha={fmt(a)}, eps={fmt(e)}")


def _get_outer_layer_params(engine: SimulationEngine):
    """返回当前模型墙/屋面外层材料的实际 α/ε/λ 参数（用于写入 CSV）"""
    bm = engine.building_model
    w_alpha=w_eps=w_lambda=None
    r_alpha=r_eps=r_lambda=None
    wall_cons = bm.constructions.get('Wall_Standard')
    if wall_cons and wall_cons.layers:
        wm = wall_cons.layers[0]
        w_alpha = getattr(wm, 'solar_absorptance', None)
        w_eps = getattr(wm, 'emissivity', None)
        w_lambda = getattr(wm, 'conductivity', None)
    roof_cons = bm.constructions.get('Roof_Standard')
    if roof_cons and roof_cons.layers:
        rm = roof_cons.layers[0]
        r_alpha = getattr(rm, 'solar_absorptance', None)
        r_eps = getattr(rm, 'emissivity', None)
        r_lambda = getattr(rm, 'conductivity', None)
    return {
        'Wall_Alpha': w_alpha, 'Wall_Eps': w_eps, 'Wall_Lambda_WmK': w_lambda,
        'Roof_Alpha': r_alpha, 'Roof_Eps': r_eps, 'Roof_Lambda_WmK': r_lambda,
    }


def _build_scenarios() -> List[Dict[str, Any]]:
    """构建默认对比场景。"""
    return [
        {
            'name': '基准（标准外墙+标准屋面）',
            'desc': '墙/屋面均按默认构造（墙α≈0.6, ε≈0.9；屋面α≈0.7, ε≈0.9）',
            'wall': { 'alpha': None, 'emissivity': None, 'conductivity': None },
            'roof': { 'alpha': None, 'emissivity': None, 'conductivity': None },
        },
        {
            'name': '（高反射+高发射）',
            'desc': 'α=0.1, ε=0.95（辐射制冷友好）；',
            'wall': { 'alpha': 0.1, 'emissivity': 0.95, 'conductivity': None },
            'roof': { 'alpha': 0.1, 'emissivity': 0.95, 'conductivity': None },
        },
        {
            'name': '（高吸收+高发射）',
            'desc': 'α=0.9, ε=0.95（辐射制热）；墙体不变',
            'wall': { 'alpha': 0.9, 'emissivity': 0.95, 'conductivity': None },
            'roof': { 'alpha': 0.9, 'emissivity': 0.95, 'conductivity': None },
        },
    ]


def _worker_one(epw_path: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
    """单个任务：在指定 EPW 下运行一个场景。"""
    logging.getLogger('core.weather_data').setLevel(logging.WARNING)
    logging.getLogger('core.simulation_engine').setLevel(logging.WARNING)

    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
    cfg = create_config_with_material(epw_path)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
        json.dump(cfg, tf, ensure_ascii=False, indent=2)
        cfg_path = tf.name

    try:
        engine = SimulationEngine(cfg_path)
        _apply_material_scenario(engine, scenario['wall'], scenario['roof'])
        engine.run_simulation()
        s = engine.get_summary()

        floor_area = sum(z.area for z in engine.building_model.zones) or 1e-6
        cool_MJ_m2 = s['total_cooling_energy_kWh'] * 3.6 / floor_area
        heat_MJ_m2 = s['total_heating_energy_kWh'] * 3.6 / floor_area
        hvac_MJ_m2 = (s['total_hvac_energy_kWh']) * 3.6 / floor_area

        mat_params = _get_outer_layer_params(engine)
        row = {
            'EPW': epw_name,
            'Scenario': scenario['name'],
            'Desc': scenario['desc'],
            **mat_params,
            'Total_Cooling_Energy_kWh': s['total_cooling_energy_kWh'],
            'Total_Heating_Energy_kWh': s['total_heating_energy_kWh'],
            'Total_HVAC_Energy_kWh': s['total_hvac_energy_kWh'],
            'Total_Cooling_MJ_per_m2': cool_MJ_m2,
            'Total_Heating_MJ_per_m2': heat_MJ_m2,
            'Total_HVAC_MJ_per_m2': hvac_MJ_m2,
            'Floor_Area_m2': floor_area,
            'Peak_Cooling_Load_kW': s['peak_cooling_load_kW'],
            'Peak_Heating_Load_kW': s['peak_heating_load_kW'],
        }
        return {'ok': True, 'row': row}

    except Exception as e:
        return {'ok': False, 'error': str(e), 'scenario': scenario.get('name'), 'epw': epw_path}

    finally:
        try:
            os.remove(cfg_path)
        except Exception:
            pass


def _convert_epw_to_utf8_if_needed(epw_path: str) -> str:
    """如果需要，将 EPW 文件转换为 UTF-8 编码。
    
    返回：原始路径（如果已经是 UTF-8）或临时 UTF-8 文件路径。
    """
    # 尝试检测文件编码
    epw_encodings = ['utf-8', 'latin-1', 'cp1252', 'gbk', 'gb2312']
    detected_encoding = None
    
    for enc in epw_encodings:
        try:
            with open(epw_path, 'r', encoding=enc) as f:
                f.read(1000)
            detected_encoding = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if detected_encoding is None:
        # 无法检测，假设是 latin-1（EPW 标准编码）
        detected_encoding = 'latin-1'
    
    # 如果已经是 UTF-8，直接返回原路径
    if detected_encoding == 'utf-8':
        return epw_path
    
    # 需要转换：创建临时 UTF-8 文件
    try:
        with open(epw_path, 'r', encoding=detected_encoding, errors='replace') as src:
            content = src.read()
        
        # 创建临时 UTF-8 文件
        temp_epw = tempfile.NamedTemporaryFile(mode='w', suffix='.epw', delete=False, encoding='utf-8')
        temp_epw.write(content)
        temp_epw.close()
        
        return temp_epw.name
    except Exception as e:
        # 转换失败，返回原路径（让 SimulationEngine 处理）
        return epw_path


def _worker_epw_batch(epw_path: str, scenarios: List[Dict[str, Any]], 
                     sky_temp_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """工作线程/进程任务：同一 EPW 下顺序运行多个场景，减少线程/进程和IO开销。
    
    参数：
        epw_path: EPW文件路径
        scenarios: 场景列表
        sky_temp_weights: 天空温度模型权重（可选）
    """
    import os as os_module
    import multiprocessing
    
    # 检查是否是进程还是线程
    try:
        process_name = multiprocessing.current_process().name
        worker_id = process_name
        worker_type = "进程"
    except Exception:
        # 如果 multiprocessing 不可用，使用线程信息
        import threading
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        worker_id = f"{thread_id} ({thread_name})"
        worker_type = "线程"
    
    print(f"[{worker_type} {worker_id}] 开始处理: {os_module.path.basename(epw_path)}")
    
    logging.getLogger('core.weather_data').setLevel(logging.WARNING)
    logging.getLogger('core.simulation_engine').setLevel(logging.WARNING)

    rows = []
    errors = []
    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
    cfg_path = None
    temp_epw_path = None
    actual_epw_path = epw_path  # 默认使用原始路径
    
    try:
        # 验证 EPW 文件是否存在
        if not os.path.exists(epw_path):
            raise FileNotFoundError(f"EPW 文件不存在: {epw_path}")
        
        # 尝试将 EPW 文件转换为 UTF-8（如果需要）
        temp_epw_path = _convert_epw_to_utf8_if_needed(epw_path)
        actual_epw_path = temp_epw_path if temp_epw_path != epw_path else epw_path
        
    except Exception as e:
        errors.append({
            'ok': False,
            'error': f"EPW 文件预处理失败: {str(e)}",
            'scenario': 'all',
            'epw': epw_path
        })
        if rows and not errors:
            return {'ok': True, 'rows': rows}
        elif rows and errors:
            return {'ok': True, 'rows': rows, 'partial_errors': errors}
        else:
            return {'ok': False, 'error': f'EPW 文件预处理失败: {str(e)}', 'epw': epw_path}
    
    try:
        for scenario in scenarios:
            cfg_path = None
            scenario_name = scenario.get('name', 'Unknown')
            try:
                # 使用转换后的 EPW 路径（如果是临时文件）或原始路径
                cfg = create_config_with_material(actual_epw_path, sky_temp_weights=sky_temp_weights)
                # 确保 JSON 配置文件使用 UTF-8 编码
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tf:
                    json.dump(cfg, tf, ensure_ascii=False, indent=2)
                    cfg_path = tf.name
                
                # 创建 SimulationEngine（它会在内部读取 EPW 文件）
                # 如果 SimulationEngine 内部使用 UTF-8 读取 EPW，可能会失败
                # 我们已经在上面验证了文件可读性，但实际读取可能仍会失败
                try:
                    engine = SimulationEngine(cfg_path)
                except (UnicodeDecodeError, UnicodeError) as ude:
                    # 编码错误：提供更详细的错误信息和解决建议
                    error_msg = (
                        f"EPW 文件编码错误 ({epw_path}): {str(ude)}\n"
                        f"EPW 文件可能使用了非 UTF-8 编码（如 GBK、Windows-1252 等）。\n"
                        f"建议：检查 EPW 文件编码，或使用支持多种编码的 EPW 文件。"
                    )
                    raise IOError(error_msg) from ude
                except Exception as e:
                    # 检查是否是编码相关的错误
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ['codec', 'decode', 'encoding', 'utf-8', 'utf8']):
                        error_msg = (
                            f"EPW 文件编码问题 ({epw_path}): {e}\n"
                            f"提示：EPW 文件可能使用了非 UTF-8 编码。"
                        )
                        raise IOError(error_msg) from e
                    raise
                
                _apply_material_scenario(engine, scenario['wall'], scenario['roof'])
                engine.run_simulation()
                s = engine.get_summary()
                floor_area = sum(z.area for z in engine.building_model.zones) or 1e-6
                cool_MJ_m2 = s['total_cooling_energy_kWh'] * 3.6 / floor_area
                heat_MJ_m2 = s['total_heating_energy_kWh'] * 3.6 / floor_area
                hvac_MJ_m2 = (s['total_hvac_energy_kWh']) * 3.6 / floor_area
                mat_params = _get_outer_layer_params(engine)
                row = {
                    'EPW': epw_name,
                    'Scenario': scenario['name'],
                    'Desc': scenario['desc'],
                    **mat_params,
                    'Total_Cooling_Energy_kWh': s['total_cooling_energy_kWh'],
                    'Total_Heating_Energy_kWh': s['total_heating_energy_kWh'],
                    'Total_HVAC_Energy_kWh': s['total_hvac_energy_kWh'],
                    'Total_Cooling_MJ_per_m2': cool_MJ_m2,
                    'Total_Heating_MJ_per_m2': heat_MJ_m2,
                    'Total_HVAC_MJ_per_m2': hvac_MJ_m2,
                    'Floor_Area_m2': floor_area,
                    'Peak_Cooling_Load_kW': s['peak_cooling_load_kW'],
                    'Peak_Heating_Load_kW': s['peak_heating_load_kW'],
                }
                rows.append(row)
                # 调试信息：显示成功计算的场景
                print(f"    [DEBUG] 场景 '{scenario_name}' 计算成功，已添加到结果")
            except Exception as e:
                import traceback
                error_msg = f"{scenario_name}: {str(e)}"
                error_detail = traceback.format_exc()
                errors.append({
                    'ok': False,
                    'error': error_msg,
                    'error_detail': error_detail,
                    'scenario': scenario_name,
                    'epw': epw_path
                })
                # 调试信息：显示失败的场景
                print(f"    [DEBUG] 场景 '{scenario_name}' 计算失败: {str(e)[:100]}")
            finally:
                if cfg_path:
                    try:
                        os.remove(cfg_path)
                    except Exception:
                        pass
    finally:
        # 清理临时 EPW 文件
        if temp_epw_path and temp_epw_path != epw_path:
            try:
                os.remove(temp_epw_path)
            except Exception:
                pass
    
    # 调试信息：显示每个 EPW 的计算结果
    try:
        process_name = multiprocessing.current_process().name
        worker_id = process_name
        worker_type = "进程"
    except Exception:
        import threading
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        worker_id = f"{thread_id} ({thread_name})"
        worker_type = "线程"
    
    print(f"  [{worker_type} {worker_id}] EPW {epw_name}: 成功 {len(rows)} 个场景，失败 {len(errors)} 个场景")
    if rows:
        print(f"    成功场景: {[r.get('Scenario', 'Unknown') for r in rows]}")
    if errors:
        print(f"    失败场景: {[e.get('scenario', 'Unknown') for e in errors]}")
    
    if rows and not errors:
        return {'ok': True, 'rows': rows}
    elif rows and errors:
        # 部分成功
        return {'ok': True, 'rows': rows, 'partial_errors': errors}
    else:
        # 全失败 - 返回详细错误信息
        if errors:
            error_summary = '; '.join([e.get('error', 'Unknown error') for e in errors[:3]])
            if len(errors) > 3:
                error_summary += f' ... (共 {len(errors)} 个错误)'
            return {
                'ok': False,
                'error': f'All scenarios failed for {epw_name}: {error_summary}',
                'errors': errors,
                'epw': epw_path
            }
        else:
            return {'ok': False, 'error': f'All scenarios failed for {epw_name} (no error details)', 'epw': epw_path}


def _run_all_tasks_parallel(epw_files: List[str], scenarios: List[Dict[str, Any]], max_workers: int) -> List[Dict[str, Any]]:
    """并行运行所有 (EPW, 场景) 组合，带动态超时和重试机制。
    
    返回结果列表，每个元素为 {'ok': bool, 'row': dict} 或 {'ok': False, 'error': str, ...}
    
    超时策略：
    - 默认超时：24000s（可通过 MATERIALS_TASK_TIMEOUT 覆盖）
    - 重试机制：失败任务自动重试 1 次
    
    注意：使用多线程而不是多进程，避免在Windows打包环境下创建多个GUI窗口。
    """
    # 构建所有任务：(epw_path, scenario)
    all_tasks = []
    for epw_path in epw_files:
        for scenario in scenarios:
            all_tasks.append((epw_path, scenario))
    
    total_tasks = len(all_tasks)
    print(f"\n总模拟任务数: {total_tasks} (天气文件数: {len(epw_files)}, 场景数: {len(scenarios)})")
    print(f"并行线程数: {max_workers}")

    try:
        timeout_sec = int(os.environ.get('MATERIALS_TASK_TIMEOUT', '24000'))
    except Exception:
        timeout_sec = 24000
    
    print(f"单任务超时: {timeout_sec}s (可通过 MATERIALS_TASK_TIMEOUT 环境变量覆盖)")
    
    results: List[Dict[str, Any]] = []
    failed_tasks = []  # 记录失败的任务用于重试
    
    # 使用线程池而不是进程池，避免在Windows打包环境下创建多个GUI窗口
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        # 第一轮：提交所有任务
        future_to_task = {}
        start_time = {}
        for epw_path, scenario in all_tasks:
            fut = ex.submit(_worker_one, epw_path, scenario)
            future_to_task[fut] = (epw_path, scenario)
            start_time[fut] = time.monotonic()
        
        pending = set(future_to_task.keys())
        completed_count = 0
        
        # 循环等待任务完成或超时
        while pending:
            done, not_done = cf.wait(pending, timeout=2.0, return_when=cf.FIRST_COMPLETED)
            
            # 处理已完成任务
            for fut in done:
                pending.remove(fut)
                epw_path, scenario = future_to_task[fut]
                epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                scenario_name = scenario.get('name', 'Unknown')
                try:
                    res = fut.result()
                    results.append(res)
                    completed_count += 1
                    if res.get('ok'):
                        print(f"  [{completed_count}/{total_tasks}] [OK] {epw_name} | {scenario_name}")
                    else:
                        # 失败的任务记录用于重试
                        failed_tasks.append((epw_path, scenario))
                        print(f"  [{completed_count}/{total_tasks}] [FAIL] {epw_name} | {scenario_name} | {res.get('error')}")
                except Exception as e:
                    failed_tasks.append((epw_path, scenario))
                    results.append({'ok': False, 'error': str(e), 'scenario': scenario_name, 'epw': epw_path})
                    completed_count += 1
                    print(f"  [{completed_count}/{total_tasks}] [ERROR] {epw_name} | {scenario_name} | {str(e)}")
            
            # 检查超时任务
            now = time.monotonic()
            timed_out = [f for f in not_done if (now - start_time.get(f, now)) > timeout_sec]
            for f in timed_out:
                pending.remove(f)
                epw_path, scenario = future_to_task[f]
                epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                scenario_name = scenario.get('name', 'Unknown')
                
                # 超时任务记录用于重试
                failed_tasks.append((epw_path, scenario))
                results.append({'ok': False, 'error': f'Task timeout after {timeout_sec}s', 'scenario': scenario_name, 'epw': epw_path})
                completed_count += 1
                # 尝试取消（若仍在队列中可取消，若已运行则无法取消）
                f.cancel()
                print(f"  [{completed_count}/{total_tasks}] [TIMEOUT] {epw_name} | {scenario_name}")
        
        # 第二轮：重试失败的任务（仅重试 1 次）
        if failed_tasks:
            print(f"\n开始重试 {len(failed_tasks)} 个失败任务……")
            retry_future_to_task = {}
            retry_start_time = {}
            for epw_path, scenario in failed_tasks:
                fut = ex.submit(_worker_one, epw_path, scenario)
                retry_future_to_task[fut] = (epw_path, scenario)
                retry_start_time[fut] = time.monotonic()
            
            retry_pending = set(retry_future_to_task.keys())
            retry_completed = 0
            
            while retry_pending:
                done, not_done = cf.wait(retry_pending, timeout=2.0, return_when=cf.FIRST_COMPLETED)
                
                for fut in done:
                    retry_pending.remove(fut)
                    epw_path, scenario = retry_future_to_task[fut]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    scenario_name = scenario.get('name', 'Unknown')
                    
                    # 移除之前的失败记录
                    results = [r for r in results if not (
                        r.get('epw') == epw_path and r.get('scenario') == scenario_name
                    )]
                    
                    try:
                        res = fut.result()
                        results.append(res)
                        retry_completed += 1
                        if res.get('ok'):
                            print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [OK] {epw_name} | {scenario_name}")
                        else:
                            results.append(res)
                            print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [FAIL] {epw_name} | {scenario_name}")
                    except Exception as e:
                        results.append({'ok': False, 'error': str(e), 'scenario': scenario_name, 'epw': epw_path})
                        retry_completed += 1
                        print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [ERROR] {epw_name} | {scenario_name}")
                
                # 检查重试超时
                now = time.monotonic()
                retry_timed_out = [f for f in not_done if (now - retry_start_time.get(f, now)) > timeout_sec]
                for f in retry_timed_out:
                    retry_pending.remove(f)
                    epw_path, scenario = retry_future_to_task[f]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    scenario_name = scenario.get('name', 'Unknown')
                    
                    # 移除之前的失败记录
                    results = [r for r in results if not (
                        r.get('epw') == epw_path and r.get('scenario') == scenario_name
                    )]
                    
                    results.append({'ok': False, 'error': f'Task timeout after {timeout_sec}s (retry)', 'scenario': scenario_name, 'epw': epw_path})
                    retry_completed += 1
                    f.cancel()
                    print(f"  [重试 {retry_completed}/{len(failed_tasks)}] [TIMEOUT] {epw_name} | {scenario_name}")
    
    return results


def _run_all_tasks_parallel_batch(
    epw_files: List[str],
    scenarios: List[Dict[str, Any]],
    max_workers: int,
    progress_cb: Optional[callable] = None,
    sky_temp_weights: Optional[Dict[str, float]] = None,
    use_multiprocessing: bool = False,
) -> List[Dict[str, Any]]:
    """并行运行EPW批次：每个线程/进程内顺序跑完该EPW下的所有场景，减少线程/IO开销。

    - progress_cb: 可选回调 progress_cb(completed, total, message)
    - sky_temp_weights: 天空温度模型权重（可选）
    - use_multiprocessing: 是否使用多进程（默认False，使用多线程）

    返回拍扁后的列表：[{ok:True,row:...}|{ok:False,error:...}]
    
    注意：
    - 默认使用多线程，避免在Windows打包环境下创建多个GUI窗口
    - 如果 use_multiprocessing=True，使用多进程以获得更好的CPU利用率，但需要确保子进程不会创建GUI
    """
    total_jobs = len(epw_files)
    import threading
    import multiprocessing
    
    # 检查是否应该使用多进程
    # 在 Windows 打包环境下，如果使用多进程，需要确保子进程不会创建 GUI
    if use_multiprocessing:
        # 检查是否是主进程
        if multiprocessing.current_process().name != 'MainProcess':
            # 子进程不应该创建 GUI，直接返回空结果
            # 这个检查在这里是多余的，因为子进程不会执行到这里
            # 但保留作为安全措施
            return []
        
        # 在 Windows 上，如果是打包后的 exe，需要 freeze_support
        if sys.platform.startswith('win') and getattr(sys, 'frozen', False):
            multiprocessing.freeze_support()
        
        print(f"\n总并行任务数(EPW数): {total_jobs}，每个任务包含 {len(scenarios)} 个场景")
        print(f"并行进程数: {max_workers}")
        print(f"CPU核心数: {os.cpu_count() or 1}")
        print(f"[提示] 使用多进程并行计算，子进程不会创建GUI窗口")
    else:
        print(f"\n总并行任务数(EPW数): {total_jobs}，每个任务包含 {len(scenarios)} 个场景")
        print(f"并行线程数: {max_workers}")
        print(f"CPU核心数: {os.cpu_count() or 1}")
        print(f"主线程ID: {threading.current_thread().ident}")
        print(f"[提示] 使用多线程并行计算，不会创建多个进程")

    try:
        timeout_sec = int(os.environ.get('MATERIALS_TASK_TIMEOUT', '24000'))
    except Exception:
        timeout_sec = 24000
    print(f"单任务超时: {timeout_sec}s (可通过 MATERIALS_TASK_TIMEOUT 覆盖)")

    flat_results: List[Dict[str, Any]] = []

    # 根据 use_multiprocessing 参数选择使用线程池或进程池
    try:
        if use_multiprocessing:
            # 使用进程池以获得更好的CPU利用率
            # 注意：子进程不会执行 GUI 相关代码，因为工作函数中不包含 GUI 创建代码
            executor_class = cf.ProcessPoolExecutor
        else:
            # 使用线程池，避免在Windows打包环境下创建多个GUI窗口
            executor_class = cf.ThreadPoolExecutor
        
        with executor_class(max_workers=max_workers) as ex:
            future_to_epw = {}
            start_time = {}
            for epw_path in epw_files:
                fut = ex.submit(_worker_epw_batch, epw_path, scenarios, sky_temp_weights)
                future_to_epw[fut] = epw_path
                start_time[fut] = time.monotonic()
            pending = set(future_to_epw.keys())
            completed = 0
            while pending:
                done, not_done = cf.wait(pending, timeout=2.0, return_when=cf.FIRST_COMPLETED)
                for fut in done:
                    pending.remove(fut)
                    epw_path = future_to_epw[fut]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    try:
                        res = fut.result()
                        completed += 1
                        if res.get('ok'):
                            rows = res.get('rows', [])
                            flat_results.extend({'ok': True, 'row': r} for r in rows)
                            # 显示当前并行状态
                            active_count = len(pending)
                            msg = f"[OK] {epw_name} | rows={len(rows)} | 剩余任务: {active_count}"
                            print(f"  [{completed}/{total_jobs}] {msg}")
                            if progress_cb:
                                progress_cb(completed, total_jobs, msg)
                            if 'partial_errors' in res:
                                cnt = len(res['partial_errors'])
                                warn = f"[WARN] {epw_name} 部分场景失败：{cnt}"
                                print(f"      {warn}")
                                if progress_cb:
                                    progress_cb(completed, total_jobs, warn)
                        else:
                            error_msg = res.get('error', 'Unknown error')
                            # 如果有详细错误信息，也打印出来
                            if 'errors' in res and res['errors']:
                                first_error = res['errors'][0]
                                if 'error_detail' in first_error:
                                    print(f"  [{completed}/{total_jobs}] [FAIL] {epw_name} | {error_msg}")
                                    print(f"      详细错误: {first_error.get('error_detail', '')[:200]}...")
                                else:
                                    print(f"  [{completed}/{total_jobs}] [FAIL] {epw_name} | {error_msg}")
                            else:
                                print(f"  [{completed}/{total_jobs}] [FAIL] {epw_name} | {error_msg}")
                            flat_results.append({'ok': False, 'error': error_msg, 'epw': epw_path, 'details': res.get('errors')})
                            if progress_cb:
                                progress_cb(completed, total_jobs, f"[FAIL] {epw_name} | {error_msg}")
                    except Exception as e:
                        completed += 1
                        flat_results.append({'ok': False, 'error': str(e), 'epw': epw_path})
                        msg = f"[ERROR] {epw_name} | {str(e)}"
                        print(f"  [{completed}/{total_jobs}] {msg}")
                        if progress_cb:
                            progress_cb(completed, total_jobs, msg)
                # 超时检查
                now = time.monotonic()
                timed_out = [f for f in not_done if (now - start_time.get(f, now)) > timeout_sec]
                for f in timed_out:
                    pending.remove(f)
                    epw_path = future_to_epw[f]
                    epw_name = os.path.splitext(os.path.basename(epw_path))[0]
                    flat_results.append({'ok': False, 'error': f'Task timeout after {timeout_sec}s', 'epw': epw_path})
                    print(f"  [TIMEOUT] {epw_name}")
    except KeyboardInterrupt:
        # 用户中断
        print("\n[中断] 用户中断了分析过程")
        if progress_cb:
            progress_cb(0, total_jobs, "[中断] 分析已被用户中断")
        raise
    except Exception as e:
        # 捕获所有异常，防止主进程退出
        import traceback
        error_msg = f"并行执行出错：{str(e)}\n{traceback.format_exc()}"
        print(f"\n[错误] {error_msg}")
        if progress_cb:
            progress_cb(0, total_jobs, f"[错误] {error_msg}")
        # 返回已收集的结果，而不是抛出异常
        return flat_results

    return flat_results


def run_material_comparison(scenarios: Optional[List[Dict[str, Any]]] = None, 
                           progress_cb: Optional[callable] = None,
                           sky_temp_weights: Optional[Dict[str, float]] = None,
                           use_multiprocessing: bool = True):
    """运行材料对比仿真（聚焦辐射制冷：α、ε、λ 参数对 HVAC 的影响）
    - 预先计算天气×建筑 的总模拟次数
    - 对所有 (天气, 场景) 组合进行全局并行
    - 汇总所有结果并按 EPW 分别输出对比表

    参数：
    - scenarios: 可选，自定义场景列表；为 None 时使用默认 _build_scenarios()
    - progress_cb: 进度回调函数
    - sky_temp_weights: 天空温度模型权重字典，格式：
        {
            'epw_ir': 1.0,      # EPW红外辐射模型权重
            'brunt': 0.4,       # Brunt模型权重
            'brutsaert': 0.3,   # Brutsaert模型权重
            'swinbank': 0.5     # Swinbank模型权重
        }
    """
    print("\n" + "="*70)
    print("材料对比分析 - 围护外层 α/ε/λ 对 HVAC 能耗的影响（全局并行）")
    print("="*70)

    # 对比场景（只改外层材料参数），None 表示保持默认
    if scenarios is None:
        scenarios = _build_scenarios()
    
    # 保存 scenarios 的副本，避免后续代码修改导致类型错误
    scenarios_original = scenarios.copy() if isinstance(scenarios, list) else scenarios

    # 收集天气文件
    epw_files = find_epw_files()
    if not epw_files:
        print("\n[WARN] 未找到任何 EPW（weather/ 目录）。将用虚拟天气数据演示一次。")
        epw_files = ['weather/nonexistent.epw']

    # 并行度设置（环境变量 MATERIALS_MAX_WORKERS 优先，其次根据任务数和 CPU 核数动态调整）
    try:
        env_workers = int(os.environ.get('MATERIALS_MAX_WORKERS', '0'))
    except Exception:
        env_workers = 0
    
    cpu_workers = os.cpu_count() or 1
    # 根据总任务数与CPU动态设定并行度（更充分利用CPU，同时避免过订阅）
    total_tasks = max(1, len(epw_files) * len(scenarios))
    
    if env_workers > 0:
        # 用户指定了并行度，使用用户指定的值（但不超过任务数）
        max_workers = max(1, min(env_workers, total_tasks))
    else:
        # 自动设置：至少使用CPU核心数，但不超过任务数
        # 如果EPW文件数少于CPU核心数，使用EPW文件数作为并行度（每个EPW一个进程）
        # 这样可以确保即使只有少量EPW文件也能并行
        if len(epw_files) > 0:
            # 每个EPW文件一个进程，最多不超过CPU核心数
            max_workers = min(len(epw_files), cpu_workers)
        else:
            max_workers = min(cpu_workers, total_tasks)
        
        # 确保至少为1
        max_workers = max(1, max_workers)

    # 计算总任务数
    total_tasks = len(epw_files) * len(scenarios)
    print(f"\n场景数: {len(scenarios)}")
    print(f"天气文件数: {len(epw_files)}")
    print(f"总模拟任务数: {total_tasks}")
    print(f"并行进程数: {max_workers} (可通过环境变量 MATERIALS_MAX_WORKERS 覆盖)")

    # 全局并行运行所有任务
    print("\n开始全局并行仿真……")
    if sky_temp_weights:
        print(f"使用自定义天空温度模型权重: {sky_temp_weights}")
    
    # 检查环境变量是否强制使用多进程
    env_use_mp = os.environ.get('MATERIALS_USE_MULTIPROCESSING', '0').lower() in ('1', 'true', 'yes')
    actual_use_mp = use_multiprocessing or env_use_mp
    
    res_list = _run_all_tasks_parallel_batch(
        epw_files,
        scenarios,
        max_workers,
        progress_cb=progress_cb,
        sky_temp_weights=sky_temp_weights,
        use_multiprocessing=actual_use_mp,
    )

    # 汇总所有结果
    all_rows = []
    failed_count = 0
    for res in res_list:
        if res.get('ok'):
            all_rows.append(res['row'])
        else:
            failed_count += 1

    print(f"\n仿真完成: 成功 {len(all_rows)} 个，失败 {failed_count} 个")
    
    # 调试信息：检查每个 EPW 的场景数量
    if all_rows:
        df_debug = pd.DataFrame(all_rows)
        print(f"\n[DEBUG] 结果统计:")
        print(f"  总行数: {len(df_debug)}")
        if 'EPW' in df_debug.columns:
            epw_counts = df_debug.groupby('EPW').size()
            print(f"  每个 EPW 的行数:")
            for epw, count in epw_counts.items():
                scenario_names = df_debug[df_debug['EPW'] == epw]['Scenario'].tolist()
                print(f"    {epw}: {count} 行 - 场景: {scenario_names}")
        if 'Scenario' in df_debug.columns:
            scenario_counts = df_debug.groupby('Scenario').size()
            print(f"  每个场景的行数:")
            for scenario, count in scenario_counts.items():
                print(f"    {scenario}: {count} 行")

    # 按 EPW 分组，分别输出对比表
    if all_rows:
        df_all = pd.DataFrame(all_rows)
        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        # 按 EPW 分组
        for epw_name, group in df_all.groupby('EPW'):
            print(f"\n[DEBUG] 处理 EPW: {epw_name}")
            print(f"  原始行数: {len(group)}")
            print(f"  场景列表: {group['Scenario'].tolist()}")
            
            # 按 scenarios 原顺序排序
            order = {sc['name']: i for i, sc in enumerate(scenarios_original)}
            group = group.sort_values(by='Scenario', key=lambda x: x.map(order))
            
            print(f"  排序后场景: {group['Scenario'].tolist()}")
            print(f"  最终输出行数: {len(group)}")

            # 选择基准：优先基准场景存在；缺失时不计算 Saving_%（避免误判）
            baseline_scenario_name = scenarios_original[0]['name']
            print(f"  查找基准场景: {baseline_scenario_name}")
            base_row = group[group['Scenario'] == baseline_scenario_name]
            print(f"  基准场景匹配行数: {len(base_row)}")
            if len(base_row) > 0:
                baseline = float(base_row.iloc[0]['Total_HVAC_Energy_kWh'])
                group = group.copy()
                group['Delta_Energy_kWh'] = group['Total_HVAC_Energy_kWh'] - baseline
                # 基线不为0时计算百分比
                if baseline > 0:
                    group['Saving_%'] = (baseline - group['Total_HVAC_Energy_kWh']) / baseline * 100
                else:
                    group['Saving_%'] = None
            else:
                # 基准缺失：仅输出绝对值与材料参数，不给出 Saving_%
                group = group.copy()
                group['Delta_Energy_kWh'] = None
                group['Saving_%'] = None
                print(f"  [WARN] {epw_name}: 基准场景缺失，已跳过 Saving_% 计算")

            out_epw = os.path.join(output_dir, f"{epw_name}_radiative_cooling_comparison.xlsx")
            group.to_excel(out_epw, index=False, engine='openpyxl')
            print(f"  [OK] {epw_name}: {out_epw}")

        # 汇总所有 EPW（输出数值节能：冷/热 MJ/m2；删除百分比 Saving_%）
        saving_rows = []
        baseline_scenario_name = scenarios_original[0]['name']  # 第一个场景是基准
        for _, group in df_all.groupby('EPW'):
            g = group.copy()
            # 基准行（优先按基准场景名，否则退回首行）
            baseline_row = g[g['Scenario'] == baseline_scenario_name]
            if len(baseline_row) > 0:
                base_cool = baseline_row.iloc[0]['Total_Cooling_MJ_per_m2']
                base_heat = baseline_row.iloc[0]['Total_Heating_MJ_per_m2']
            else:
                base_cool = g.iloc[0]['Total_Cooling_MJ_per_m2']
                base_heat = g.iloc[0]['Total_Heating_MJ_per_m2']
            # 数值节能（基准 - 当前），单位 MJ/m2
            g['Saving_cooling_energy_MJ_per_m2'] = base_cool - g['Total_Cooling_MJ_per_m2']
            g['Saving_heating_energy_MJ_per_m2'] = base_heat - g['Total_Heating_MJ_per_m2']
            # 删除不需要的列
            for col in ['Total_Cooling_Energy_kWh', 'Total_Heating_Energy_kWh', 'Saving_%']:
                if col in g.columns:
                    g = g.drop(columns=[col])
            saving_rows.append(g)
        df_saving = pd.concat(saving_rows, ignore_index=True)

        out_all = os.path.join(output_dir, 'material_radiative_cooling_comparison_all.xlsx')
        df_saving.to_excel(out_all, index=False, engine='openpyxl')
        print(f"\n[OK] 全部天气的汇总结果已保存：{out_all}")

    print("\n[OK] 材料对比分析完成！")
    return True


# ==============================================================================
# GUI Implementation
# ==============================================================================

class SimulationThread(QThread):  # pragma: no cover
    """在工作线程中运行仿真，避免 GUI 冻结。"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, scenarios: List[Dict[str, Any]], sky_temp_weights: Optional[Dict[str, float]] = None, use_multiprocessing: bool = False):
        super().__init__()
        self.scenarios = scenarios
        self.sky_temp_weights = sky_temp_weights
        self.use_multiprocessing = use_multiprocessing

    def run(self):
        """在工作线程中运行仿真"""
        try:
            # 运行对比
            try:
                run_material_comparison(
                    scenarios=self.scenarios,
                    progress_cb=self.progress.emit,
                    sky_temp_weights=self.sky_temp_weights,
                    use_multiprocessing=self.use_multiprocessing,
                )
                output_dir = get_output_dir()
                self.finished.emit(True, f"分析完成！结果已保存到 {output_dir} 目录。")
            except KeyboardInterrupt:
                # 用户中断
                self.finished.emit(False, "分析已被用户中断。")
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                error_msg = f"分析出错：{str(e)}\n\n详细错误信息：\n{error_detail}"
                self.finished.emit(False, error_msg)
        except Exception as e:
            # 最外层异常捕获，防止线程崩溃导致窗口关闭
            import traceback
            error_detail = traceback.format_exc()
            error_msg = f"发生未预期的错误：{str(e)}\n\n详细错误信息：\n{error_detail}"
            self.finished.emit(False, error_msg)


class ScenarioTab(QWidget):  # pragma: no cover
    """单个场景的 Tab 页面，包含墙/屋面参数输入。"""

    def __init__(self, scenario: Dict[str, Any], is_baseline: bool = False):
        super().__init__()
        self.is_baseline = is_baseline

        # 确保 scenario 是字典类型
        if not isinstance(scenario, dict):
            raise TypeError(f"ScenarioTab 需要字典类型的 scenario，但得到 {type(scenario)}: {scenario}")

        layout = QVBoxLayout(self)

        meta_group = QGroupBox("场景信息")
        meta_layout = QFormLayout()
        self.name_edit = QLineEdit(scenario.get('name', ''))
        self.desc_edit = QLineEdit(scenario.get('desc', ''))
        meta_layout.addRow("场景名称:", self.name_edit)
        meta_layout.addRow("场景描述:", self.desc_edit)
        meta_group.setLayout(meta_layout)
        layout.addWidget(meta_group)

        self.wall_widgets = self._create_material_widgets(scenario.get('wall', {}), defaults=(0.6, 0.9, 1.0))
        wall_group = self._wrap_material_group("墙体外层", self.wall_widgets)
        layout.addWidget(wall_group)

        self.roof_widgets = self._create_material_widgets(scenario.get('roof', {}), defaults=(0.7, 0.9, 1.0))
        roof_group = self._wrap_material_group("屋面外层", self.roof_widgets)
        layout.addWidget(roof_group)

        layout.addStretch(1)

        if self.is_baseline:
            self.name_edit.setText("基准")
            self.name_edit.setReadOnly(True)
            self.desc_edit.setText("默认材料参数，用作对比基线")
            for w in (*self.wall_widgets, *self.roof_widgets):
                w.setEnabled(False)

    def _create_material_widgets(self, values: Dict[str, Any], defaults: tuple):
        alpha_default, eps_default, cond_default = defaults

        # 安全获取值：如果为 None 则使用默认值
        alpha_val = values.get('alpha')
        if alpha_val is None:
            alpha_val = alpha_default
        eps_val = values.get('emissivity')
        if eps_val is None:
            eps_val = eps_default
        cond_val = values.get('conductivity')
        if cond_val is None:
            cond_val = cond_default

        alpha_check = QCheckBox("修改 α (0-1)")
        alpha_spin = QDoubleSpinBox()
        alpha_spin.setDecimals(3)
        alpha_spin.setRange(0.0, 1.0)
        alpha_spin.setSingleStep(0.05)
        alpha_check.setChecked(values.get('alpha') is not None)
        alpha_spin.setValue(float(alpha_val))
        alpha_spin.setEnabled(alpha_check.isChecked())
        alpha_check.toggled.connect(alpha_spin.setEnabled)

        eps_check = QCheckBox("修改 ε (0-1)")
        eps_spin = QDoubleSpinBox()
        eps_spin.setDecimals(3)
        eps_spin.setRange(0.0, 1.0)
        eps_spin.setSingleStep(0.05)
        eps_check.setChecked(values.get('emissivity') is not None)
        eps_spin.setValue(float(eps_val))
        eps_spin.setEnabled(eps_check.isChecked())
        eps_check.toggled.connect(eps_spin.setEnabled)

        cond_check = QCheckBox("修改 λ (W/mK)")
        cond_spin = QDoubleSpinBox()
        cond_spin.setDecimals(3)
        cond_spin.setRange(0.01, 10.0)
        cond_spin.setSingleStep(0.1)
        cond_check.setChecked(values.get('conductivity') is not None)
        cond_spin.setValue(float(cond_val))
        cond_spin.setEnabled(cond_check.isChecked())
        cond_check.toggled.connect(cond_spin.setEnabled)

        return (alpha_check, alpha_spin, eps_check, eps_spin, cond_check, cond_spin)

    def _wrap_material_group(self, title: str, widgets: tuple) -> QGroupBox:
        alpha_check, alpha_spin, eps_check, eps_spin, cond_check, cond_spin = widgets
        group = QGroupBox(title)
        form = QFormLayout()
        form.addRow(alpha_check, alpha_spin)
        form.addRow(eps_check, eps_spin)
        form.addRow(cond_check, cond_spin)
        group.setLayout(form)
        return group

    def _read_material(self, widgets: tuple) -> Dict[str, Any]:
        alpha_check, alpha_spin, eps_check, eps_spin, cond_check, cond_spin = widgets
        return {
            'alpha': float(alpha_spin.value()) if alpha_check.isChecked() else None,
            'emissivity': float(eps_spin.value()) if eps_check.isChecked() else None,
            'conductivity': float(cond_spin.value()) if cond_check.isChecked() else None,
        }

    def get_scenario(self) -> Dict[str, Any]:
        """从 UI 控件中提取场景配置。"""
        return {
            'name': self.name_edit.text().strip(),
            'desc': self.desc_edit.text().strip(),
            'wall': self._read_material(self.wall_widgets),
            'roof': self._read_material(self.roof_widgets),
        }


class MaterialConfigGUI(QMainWindow):  # pragma: no cover
    """材料参数对比 GUI 主窗口。"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("材料辐射节能效果对比工具")
        self.setGeometry(500, 100, 700, 850)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # 并行计算配置组
        parallel_group = QGroupBox("并行计算配置")
        parallel_layout = QFormLayout()
        
        self.use_multiprocessing_checkbox = QCheckBox("使用多进程（提高CPU利用率，但可能在某些环境下不稳定）")
        self.use_multiprocessing_checkbox.setToolTip(
            "启用多进程并行计算可以获得更好的CPU利用率，特别是在多核CPU上。\n"
            "默认已启用多进程；如果在某些环境下遇到问题，可以手动关闭。\n"
            "如在打包的 Windows 环境中出现多窗口异常，可尝试取消此选项。"
        )
        # 默认开启多进程
        self.use_multiprocessing_checkbox.setChecked(True)
        parallel_layout.addRow("", self.use_multiprocessing_checkbox)
        
        parallel_group.setLayout(parallel_layout)
        self.layout.addWidget(parallel_group)
        
        # 天空温度模型权重配置组
        weights_group = QGroupBox("天空温度模型权重配置（你最好清楚你在设置什么）")
        weights_layout = QFormLayout()
        
        self.weight_epw_spin = QDoubleSpinBox()
        self.weight_epw_spin.setDecimals(2)
        self.weight_epw_spin.setRange(0.0, 10.0)
        self.weight_epw_spin.setSingleStep(0.1)
        self.weight_epw_spin.setValue(1.0)
        epw_tooltip = (
            "EPW红外辐射模型权重（默认：1.0，最高优先级）\n\n"
            "【用途】基于EPW天气文件中的水平红外辐射数据（HorzIR）直接计算天空温度。\n"
            "这是最可靠的方法，因为使用的是实测或模拟的红外辐射数据。\n\n"
            "【计算方法】使用Stefan-Boltzmann定律反推：\n"
            "T_sky = (L_sky / σ)^0.25\n"
            "其中 L_sky 为EPW文件中的HorzIR值（W/m²），σ = 5.67×10⁻⁸ W/m²·K⁴\n\n"
            "【适用场景】当EPW文件包含有效的HorzIR数据时（通常>1.0 W/m²），此模型最准确。\n"
            "建议保持较高权重（≥1.0），因为这是最直接的测量数据。\n\n"
            "【注意事项】如果EPW文件缺少HorzIR数据或数值异常，此模型不会被调用。"
        )
        self.weight_epw_spin.setToolTip(epw_tooltip)
        weights_layout.addRow("EPW红外辐射模型:", self.weight_epw_spin)
        
        self.weight_brunt_spin = QDoubleSpinBox()
        self.weight_brunt_spin.setDecimals(2)
        self.weight_brunt_spin.setRange(0.0, 10.0)
        self.weight_brunt_spin.setSingleStep(0.1)
        self.weight_brunt_spin.setValue(0.4)
        brunt_tooltip = (
            "Brunt模型权重（默认：0.4）\n\n"
            "【用途】基于露点温度计算水汽压，然后估算天空有效发射率，进而计算天空温度。\n"
            "该模型考虑了大气中水汽对长波辐射的吸收和发射作用。\n\n"
            "【计算方法】\n"
            "1. 从露点温度计算水汽压：e = 6.112 × 10^(7.5×Tdp/(237.7+Tdp)) hPa\n"
            "2. 计算晴空发射率：ε_clear = 0.51 + 0.066 × √e\n"
            "3. 考虑云量修正：ε_sky = ε_clear × (1 + 0.22×N²)，N为云量（0-1）\n"
            "4. 计算天空温度：T_sky = (ε_sky)^0.25 × T_air\n\n"
            "【适用场景】适用于有露点温度数据的地区，能较好反映水汽对辐射制冷的影响。\n"
            "在湿度较高的地区，此模型对辐射制冷效率的估算较为重要。\n\n"
            "【注意事项】需要EPW文件包含有效的露点温度（DPT）数据。"
        )
        self.weight_brunt_spin.setToolTip(brunt_tooltip)
        weights_layout.addRow("Brunt模型:", self.weight_brunt_spin)
        
        self.weight_brutsaert_spin = QDoubleSpinBox()
        self.weight_brutsaert_spin.setDecimals(2)
        self.weight_brutsaert_spin.setRange(0.0, 10.0)
        self.weight_brutsaert_spin.setSingleStep(0.1)
        self.weight_brutsaert_spin.setValue(0.3)
        brutsaert_tooltip = (
            "Brutsaert模型权重（默认：0.3）\n\n"
            "【用途】基于水汽压和空气温度计算晴空有效发射率，用于估算天空温度。\n"
            "这是另一种考虑水汽影响的经验模型，与Brunt模型互补。\n\n"
            "【计算方法】\n"
            "1. 从露点温度计算水汽压 e（kPa）\n"
            "2. 计算晴空发射率：ε_clear = 1.24 × (e/T_air)^(1/7)\n"
            "   如果水汽压不可用，使用默认值 ε_clear = 0.72\n"
            "3. 考虑云量修正：ε_sky = ε_clear × (1 + 0.22×N²)\n"
            "4. 计算天空温度：T_sky = (ε_sky)^0.25 × T_air\n\n"
            "【适用场景】适用于需要估算水汽对天空发射率影响的场景。\n"
            "在干燥地区，此模型可能比Brunt模型更稳定。\n\n"
            "【注意事项】需要有效的露点温度或水汽压数据。如果数据缺失，会使用默认发射率0.72。"
        )
        self.weight_brutsaert_spin.setToolTip(brutsaert_tooltip)
        weights_layout.addRow("Brutsaert模型:", self.weight_brutsaert_spin)
        
        self.weight_swinbank_spin = QDoubleSpinBox()
        self.weight_swinbank_spin.setDecimals(2)
        self.weight_swinbank_spin.setRange(0.0, 10.0)
        self.weight_swinbank_spin.setSingleStep(0.1)
        self.weight_swinbank_spin.setValue(0.5)
        swinbank_tooltip = (
            "Swinbank模型权重（默认：0.5）\n\n"
            "【用途】基于空气温度的经验公式计算晴空长波辐射，然后反推天空温度。\n"
            "这是一个不依赖水汽数据的简化模型，作为其他模型的参考基准。\n\n"
            "【计算方法】\n"
            "1. 计算晴空长波辐射：L_clear = 5.31×10⁻⁸ × T_air⁶ (W/m²)\n"
            "2. 如果云量数据可用，计算天空发射率：\n"
            "   ε_clear = L_clear / (σ × T_air⁴)\n"
            "   ε_sky = ε_clear × (1 + 0.22×N²)\n"
            "3. 计算天空温度：T_sky = (ε_sky)^0.25 × T_air\n"
            "   或直接从辐射反推：T_sky = (L_clear/σ)^0.25\n\n"
            "【适用场景】当缺少水汽数据时，此模型可作为基础估算。\n"
            "适用于快速估算或作为其他模型的对比基准。\n\n"
            "【注意事项】此模型不直接考虑水汽影响，在湿度变化大的地区可能不够准确。\n"
            "但优点是只需要空气温度数据，适用性广。"
        )
        self.weight_swinbank_spin.setToolTip(swinbank_tooltip)
        weights_layout.addRow("Swinbank模型:", self.weight_swinbank_spin)
        
        # 重置按钮
        reset_weights_btn = QPushButton("重置为默认值")
        reset_weights_btn.clicked.connect(self.reset_weights)
        weights_layout.addRow("", reset_weights_btn)
        
        weights_group.setLayout(weights_layout)
        self.layout.addWidget(weights_group)

        # 场景 Tab
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # 场景管理按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加场景")
        self.add_btn.clicked.connect(lambda: self.add_scenario_tab())
        self.remove_btn = QPushButton("移除当前场景")
        self.remove_btn.clicked.connect(self.remove_current_tab)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        self.layout.addLayout(btn_layout)

        # 加载/保存配置
        io_layout = QHBoxLayout()
        self.load_btn = QPushButton("加载配置")
        self.load_btn.clicked.connect(self.load_scenarios)
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_scenarios)
        io_layout.addWidget(self.load_btn)
        io_layout.addWidget(self.save_btn)
        self.layout.addLayout(io_layout)

        # 打开文件夹按钮
        folder_layout = QHBoxLayout()
        self.open_weather_btn = QPushButton("打开天气文件夹")
        self.open_weather_btn.clicked.connect(self.open_weather_folder)
        self.open_output_btn = QPushButton("打开结果输出文件夹")
        self.open_output_btn.clicked.connect(self.open_output_folder)
        folder_layout.addWidget(self.open_weather_btn)
        folder_layout.addWidget(self.open_output_btn)
        self.layout.addLayout(folder_layout)

        # 运行
        self.run_btn = QPushButton("运行对比分析")
        self.run_btn.setStyleSheet("font-size: 16px; padding: 10px;")
        self.run_btn.clicked.connect(self.run_analysis)
        self.layout.addWidget(self.run_btn)

        # 日志输出
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.layout.addWidget(self.log_box)

        # 加载默认场景
        self.load_default_scenarios()

    def reset_weights(self):
        """重置权重为默认值"""
        self.weight_epw_spin.setValue(1.0)
        self.weight_brunt_spin.setValue(0.4)
        self.weight_brutsaert_spin.setValue(0.3)
        self.weight_swinbank_spin.setValue(0.5)
        self.log("权重已重置为默认值")
    
    def get_sky_temp_weights(self) -> Dict[str, float]:
        """获取当前设置的天空温度模型权重"""
        return {
            'epw_ir': float(self.weight_epw_spin.value()),
            'brunt': float(self.weight_brunt_spin.value()),
            'brutsaert': float(self.weight_brutsaert_spin.value()),
            'swinbank': float(self.weight_swinbank_spin.value())
        }
    
    def log(self, message: str):
        self.log_box.append(message)
        QApplication.processEvents() # 强制刷新

    def load_default_scenarios(self):
        self.tabs.clear()
        default_scenarios = _build_scenarios()
        for i, sc in enumerate(default_scenarios):
            self.add_scenario_tab(sc, is_baseline=(i == 0))

    def add_scenario_tab(self, scenario: Optional[Dict[str, Any]] = None, is_baseline: bool = False):
        if scenario is None:
            # 创建一个空场景
            scenario = {
                'name': f"新场景 {self.tabs.count() + 1}",
                'desc': '',
                'wall': {'alpha': None, 'emissivity': None, 'conductivity': None},
                'roof': {'alpha': None, 'emissivity': None, 'conductivity': None},
            }
        
        # 确保 scenario 是字典类型
        if not isinstance(scenario, dict):
            raise TypeError(f"scenario 必须是字典类型，但得到 {type(scenario)}")
        
        tab = ScenarioTab(scenario, is_baseline=is_baseline)
        self.tabs.addTab(tab, scenario.get('name', '未命名场景'))
        self.tabs.setCurrentWidget(tab)

    def remove_current_tab(self):
        if self.tabs.count() > 1:
            current_index = self.tabs.currentIndex()
            if current_index > 0: # 不允许删除基准
                self.tabs.removeTab(current_index)
            else:
                QMessageBox.warning(self, "警告", "不能删除基准场景。")
        else:
            QMessageBox.warning(self, "警告", "至少需要一个场景。")

    def save_scenarios(self):
        scenarios = [self.tabs.widget(i).get_scenario() for i in range(self.tabs.count())]
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(scenarios, f, ensure_ascii=False, indent=2)
            self.log(f"配置已保存到: {path}")

    def load_scenarios(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                scenarios = json.load(f)
            self.tabs.clear()
            for i, sc in enumerate(scenarios):
                self.add_scenario_tab(sc, is_baseline=(i == 0))
            self.log(f"从 {path} 加载了 {len(scenarios)} 个场景。")

    def run_analysis(self):
        """运行分析"""
        try:
            self.run_btn.setEnabled(False)
            self.log_box.clear()
            self.log("开始分析...")
            
            # 检查天气文件
            epw_files = find_epw_files()
            if not epw_files:
                QMessageBox.warning(self, "警告", "未找到天气文件（EPW文件）。\n\n请确保weather文件夹中有.epw文件。\n\n点击'打开天气文件夹'按钮可以查看天气文件夹位置。")
                self.run_btn.setEnabled(True)
                return
            
            # 获取天空温度模型权重
            sky_temp_weights = self.get_sky_temp_weights()
            self.log(f"天空温度模型权重: EPW={sky_temp_weights['epw_ir']:.2f}, "
                    f"Brunt={sky_temp_weights['brunt']:.2f}, "
                    f"Brutsaert={sky_temp_weights['brutsaert']:.2f}, "
                    f"Swinbank={sky_temp_weights['swinbank']:.2f}")

            scenarios = []
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                scenarios.append(tab.get_scenario())
            
            if not scenarios:
                QMessageBox.warning(self, "警告", "请至少添加一个场景。")
                self.run_btn.setEnabled(True)
                return

            # 显示并行计算信息
            import os
            cpu_count = os.cpu_count() or 1
            total_tasks = len(epw_files) * len(scenarios)
            # 计算并行度（与run_material_comparison中的逻辑一致）
            if len(epw_files) > 0:
                max_workers = min(len(epw_files), cpu_count)
            else:
                max_workers = min(cpu_count, total_tasks)
            max_workers = max(1, max_workers)
            
            self.log(f"\n并行计算信息:")
            self.log(f"  天气文件数: {len(epw_files)}")
            self.log(f"  场景数: {len(scenarios)}")
            self.log(f"  总任务数: {total_tasks}")
            self.log(f"  CPU核心数: {cpu_count}")
            self.log(f"  并行线程数: {max_workers}")
            if max_workers > 1:
                self.log(f"  ✓ 将使用 {max_workers} 个线程并行计算")
            else:
                self.log(f"  ⚠ 仅使用 1 个线程（建议：增加天气文件数来启用并行）")
            self.log(f"  请耐心等待")
            self.log("")

            # 获取是否使用多进程
            use_multiprocessing = self.use_multiprocessing_checkbox.isChecked()
            
            # 创建并启动线程
            self.thread = SimulationThread(scenarios, sky_temp_weights=sky_temp_weights, use_multiprocessing=use_multiprocessing)
            self.thread.progress.connect(self.update_progress)
            self.thread.finished.connect(self.on_analysis_finished)
            # 确保线程在完成后自动清理
            self.thread.finished.connect(lambda: setattr(self, 'thread', None))
            self.thread.start()
        except Exception as e:
            import traceback
            error_msg = f"启动分析失败：{str(e)}\n{traceback.format_exc()}"
            QMessageBox.critical(self, "错误", error_msg)
            self.log(error_msg)
            self.run_btn.setEnabled(True)

    def update_progress(self, completed: int, total: int, message: str):
        self.log(f"进度: {completed}/{total} - {message}")

    def on_analysis_finished(self, success: bool, message: str):
        """分析完成回调"""
        try:
            self.log(message)
            if success:
                QMessageBox.information(self, "完成", message)
            else:
                # 错误消息可能很长，使用详细信息对话框
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setWindowTitle("错误")
                msg_box.setText("分析过程中发生错误")
                msg_box.setDetailedText(message)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec_()
        except Exception as e:
            # 防止回调中的异常导致窗口关闭
            import traceback
            error_msg = f"处理完成回调时出错：{str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)
            QMessageBox.warning(self, "警告", f"处理完成回调时出错：{str(e)}")
        finally:
            self.run_btn.setEnabled(True)

    def open_weather_folder(self):
        """打开天气文件夹"""
        weather_dir = get_weather_dir()
        if not os.path.exists(weather_dir):
            # 如果文件夹不存在，创建它
            try:
                os.makedirs(weather_dir, exist_ok=True)
                self.log(f"已创建天气文件夹: {weather_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法创建天气文件夹:\n{weather_dir}\n错误: {e}")
                return
        
        # 使用系统默认的文件管理器打开文件夹
        if QDesktopServices is not None:
            url = QUrl.fromLocalFile(weather_dir)
            if QDesktopServices.openUrl(url):
                self.log(f"已打开天气文件夹: {weather_dir}")
            else:
                QMessageBox.warning(self, "警告", f"无法打开天气文件夹:\n{weather_dir}")
        else:
            # 备用方案：使用subprocess
            import subprocess
            import platform
            try:
                if platform.system() == 'Windows':
                    os.startfile(weather_dir)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', weather_dir])
                else:  # Linux
                    subprocess.Popen(['xdg-open', weather_dir])
                self.log(f"已打开天气文件夹: {weather_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法打开天气文件夹:\n{weather_dir}\n错误: {e}")

    def open_output_folder(self):
        """打开结果输出文件夹"""
        output_dir = get_output_dir()
        if not os.path.exists(output_dir):
            # 如果文件夹不存在，创建它
            try:
                os.makedirs(output_dir, exist_ok=True)
                self.log(f"已创建结果输出文件夹: {output_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法创建结果输出文件夹:\n{output_dir}\n错误: {e}")
                return
        
        # 使用系统默认的文件管理器打开文件夹
        if QDesktopServices is not None:
            url = QUrl.fromLocalFile(output_dir)
            if QDesktopServices.openUrl(url):
                self.log(f"已打开结果输出文件夹: {output_dir}")
            else:
                QMessageBox.warning(self, "警告", f"无法打开结果输出文件夹:\n{output_dir}")
        else:
            # 备用方案：使用subprocess
            import subprocess
            import platform
            try:
                if platform.system() == 'Windows':
                    os.startfile(output_dir)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.Popen(['open', output_dir])
                else:  # Linux
                    subprocess.Popen(['xdg-open', output_dir])
                self.log(f"已打开结果输出文件夹: {output_dir}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法打开结果输出文件夹:\n{output_dir}\n错误: {e}")

    def closeEvent(self, event):
        """窗口关闭事件处理：确保线程正确清理"""
        # 如果线程正在运行，等待其完成
        if hasattr(self, 'thread') and self.thread is not None:
            if self.thread.isRunning():
                # 线程正在运行，可以选择等待完成或请求停止
                # 这里我们等待线程完成（最多等待5秒）
                if not self.thread.wait(5000):
                    # 如果5秒内未完成，记录警告但继续关闭窗口
                    self.log("警告：计算线程仍在运行，窗口将关闭，但计算可能继续在后台进行")
                else:
                    self.log("计算线程已安全退出")
            # 清理线程引用
            self.thread = None
        
        # 调用父类的closeEvent以正常关闭窗口
        super().closeEvent(event)


def main():
    # 默认使用 GUI 模式，除非指定 --cli 参数
    use_cli = '--cli' in sys.argv or '--command-line' in sys.argv
    
    if use_cli:
        # CLI 模式
        try:
            run_material_comparison()
            return 0
        except Exception as e:
            print(f"\n[FAIL] 分析出错: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
    else:
        # 默认 GUI 模式
        if QApplication is None:
            print("[ERROR] PyQt5 未安装，无法启动 GUI。", file=sys.stderr)
            print("请运行以下命令安装 PyQt5：", file=sys.stderr)
            print("  pip install PyQt5", file=sys.stderr)
            print("\n或者使用命令行模式运行：", file=sys.stderr)
            print("  python compare_materials.py --cli", file=sys.stderr)
            return 1
        
        app = QApplication(sys.argv)
        gui = MaterialConfigGUI()
        gui.show()
        return app.exec_()


    # 注意：由于改用多线程而不是多进程，不再需要 pickle 序列化
    # 工作函数可以直接在线程中调用，无需特殊处理

if __name__ == '__main__':
    # 只有在直接运行脚本时才执行 main()
    # 如果是从其他模块导入的（如从 gui.subwindows 导入），不会执行这里
    
    # 在 Windows 打包环境下，需要防止子进程创建 GUI 窗口
    # 检查是否是主进程（通过 multiprocessing.current_process().name）
    import multiprocessing
    
    # 只有在主进程中才创建 GUI
    # 子进程不应该执行 GUI 相关代码
    if multiprocessing.current_process().name == 'MainProcess':
        # 在 Windows 上，如果是打包后的 exe，可能需要 freeze_support
        # 但只有在确实需要使用多进程时才调用（通过环境变量控制）
        if sys.platform.startswith('win') and getattr(sys, 'frozen', False):
            # 检查是否启用了多进程（通过环境变量）
            use_mp = os.environ.get('MATERIALS_USE_MULTIPROCESSING', '0').lower() in ('1', 'true', 'yes')
            if use_mp:
                multiprocessing.freeze_support()
        
        exit(main())
    else:
        # 子进程不应该创建 GUI 窗口
        # 如果意外执行到这里，直接退出
        pass
