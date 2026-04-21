# 高海拔地区辐射制冷节能效果分析报告

## 问题描述

1. **高海拔地区辐射制冷节能效果差**
2. **不同地区效果差异过于明显**

## 根本原因分析

### 1. 高海拔地区问题

#### 1.1 天空温度计算未考虑海拔修正

**问题位置**：
- `core/heat_balance.py` 的 `_effective_sky_temperature()` 方法
- `material_comparison_tool/src/core/heat_balance.py` 的 `_effective_sky_temperature()` 方法

**问题描述**：
- 当前使用的天空温度模型（Brunt、Brutsaert、Swinbank）都是基于**海平面**的经验公式
- 这些模型没有考虑**海拔高度对大气压的影响**
- 高海拔地区大气压降低，大气层变薄，导致：
  - 大气向下长波辐射减少
  - 天空有效发射率降低
  - 天空温度应该更低（有利于辐射制冷）

**当前代码问题**：
```python
# 当前代码中虽然读取了 elevation 和 atmospheric_pressure
# 但在天空温度计算中完全没有使用
def _effective_sky_temperature(self, weather: Dict, T_outK: float) -> float:
    # 只使用了露点温度、云量等，没有使用海拔或大气压
    TdpC = weather.get('dew_point', None)
    # ... 没有使用 weather.get('elevation') 或 weather.get('atmospheric_pressure')
```

#### 1.2 大气压对水汽压的影响

**问题描述**：
- 高海拔地区大气压降低，即使露点温度相同，实际水汽压也会降低
- 当前水汽压计算只基于露点温度，没有考虑大气压修正：
  ```python
  e_hPa = 6.112 * 10 ** (7.5 * float(TdpC) / (237.7 + float(TdpC)))
  ```
- 这会导致高海拔地区的水汽压被高估，进而高估天空发射率

#### 1.3 大气压对大气辐射的影响

**物理原理**：
- 大气向下长波辐射与大气柱中的水汽、CO₂等温室气体含量相关
- 高海拔地区大气柱变薄，温室气体总量减少，大气向下长波辐射减少
- 标准大气压模型：P = P₀ × (1 - L×h/T₀)^(g×M/(R×L))
  - 其中 P₀ = 101325 Pa（海平面标准大气压）
  - L = 0.0065 K/m（温度递减率）
  - h = 海拔高度（m）
  - T₀ = 288.15 K（海平面标准温度）

### 2. 地图可视化问题

#### 2.1 颜色映射范围问题

**问题位置**：
- `material_comparison_tool/examples/compare_materials.py` 的 `build_china_map()` 函数

**问题描述**：
```python
max_val = float(dff[value_col].max())
min_val = float(dff[value_col].min())
```
- 直接使用数据的最小值和最大值作为颜色映射范围
- 如果某些地区（如高海拔、干燥地区）的节能效果特别差（接近0或负值），会导致：
  - 整个颜色范围被拉伸
  - 其他地区的差异看起来更明显
  - 无法清晰展示不同地区的相对差异

**建议改进**：
1. 使用分位数（如5%和95%）作为颜色范围，避免极端值影响
2. 使用对称的颜色范围（如以0为中心），更好地展示正负差异
3. 添加多个颜色映射方案供选择

## 修复方案

### 方案1：在天空温度计算中添加海拔修正

#### 1.1 修正大气发射率模型

在 Brunt、Brutsaert 模型中添加海拔修正因子：

```python
def _altitude_correction_factor(self, elevation: float) -> float:
    """
    计算海拔修正因子，用于修正大气发射率模型
    
    参数：
        elevation: 海拔高度（m）
    
    返回：
        修正因子（0-1之间），海拔越高，因子越小
    """
    # 使用标准大气模型计算相对大气压
    P0 = 101325.0  # 海平面标准大气压 (Pa)
    L = 0.0065  # 温度递减率 (K/m)
    T0 = 288.15  # 海平面标准温度 (K)
    g = 9.80665  # 重力加速度 (m/s²)
    M = 0.0289644  # 干空气摩尔质量 (kg/mol)
    R = 8.31447  # 通用气体常数 (J/(mol·K))
    
    h = max(0.0, float(elevation))
    # 标准大气压模型
    P = P0 * (1 - L * h / T0) ** (g * M / (R * L))
    P = max(20000.0, min(P0, P))  # 限制在合理范围
    
    # 相对大气压（归一化到0-1）
    relative_pressure = P / P0
    
    # 大气发射率修正：假设发射率与大气压的平方根成正比
    # 这是一个简化的模型，实际关系更复杂
    correction = np.sqrt(relative_pressure)
    
    return float(np.clip(correction, 0.3, 1.0))
```

#### 1.2 修正水汽压计算

考虑大气压对水汽压的影响：

```python
def _calculate_vapor_pressure(self, dew_point: float, atmospheric_pressure: float) -> float:
    """
    计算水汽压，考虑大气压修正
    
    参数：
        dew_point: 露点温度 (°C)
        atmospheric_pressure: 大气压 (Pa)
    
    返回：
        水汽压 (hPa)
    """
    # 标准饱和水汽压（基于露点温度）
    e_sat_hPa = 6.112 * 10 ** (7.5 * dew_point / (237.7 + dew_point))
    
    # 大气压修正：实际水汽压 = 饱和水汽压 × (实际大气压 / 标准大气压)
    P0 = 101325.0  # 海平面标准大气压 (Pa)
    e_actual_hPa = e_sat_hPa * (atmospheric_pressure / P0)
    
    return float(np.clip(e_actual_hPa, 0.0, 100.0))
```

#### 1.3 在天空温度计算中应用修正

修改 `_effective_sky_temperature()` 方法：

```python
def _effective_sky_temperature(self, weather: Dict, T_outK: float) -> float:
    """
    基于天气数据估算有效天空温度（K）
    改进：添加海拔/大气压修正
    """
    TaK = float(np.clip(T_outK, 200.0, 330.0))
    
    # 获取海拔和大气压
    elevation = weather.get('elevation', 0.0)
    atmospheric_pressure = weather.get('atmospheric_pressure', 101325.0)
    
    # 计算海拔修正因子
    altitude_factor = self._altitude_correction_factor(elevation)
    
    # ... 现有的天空温度计算代码 ...
    
    # 在计算发射率时应用海拔修正
    eps_clear_brunt = 0.51 + 0.066 * sqrt_e
    eps_clear_brunt = eps_clear_brunt * altitude_factor  # 应用海拔修正
    eps_clear_brunt = float(np.clip(eps_clear_brunt, 0.15, 1.0))
    
    # 类似地修正 Brutsaert 和 Swinbank 模型
    # ...
```

### 方案2：改进地图可视化

#### 2.1 使用分位数作为颜色范围

```python
def build_china_map(
    df: pd.DataFrame,
    *,
    value_col: str,
    title: str,
    unit: str,
    color: str,
    range_color,
    value_transform=None,
    width: str = "1792px",
    height: str = "1008px",
    use_percentile: bool = True,  # 新增参数
    percentile_low: float = 5.0,   # 新增参数
    percentile_high: float = 95.0,  # 新增参数
):
    dff = df.copy()
    if value_transform is not None:
        dff[value_col] = value_transform(dff[value_col])

    data_province = list(zip(dff["NAME"], dff[value_col]))
    
    # 使用分位数或直接使用最小最大值
    if use_percentile:
        max_val = float(dff[value_col].quantile(percentile_high / 100.0))
        min_val = float(dff[value_col].quantile(percentile_low / 100.0))
    else:
        max_val = float(dff[value_col].max())
        min_val = float(dff[value_col].min())
    
    # ... 其余代码保持不变 ...
```

#### 2.2 添加对称颜色范围选项

对于有正负值的指标（如净节能），使用对称范围：

```python
def build_china_map(
    # ... 参数 ...
    symmetric_range: bool = False,  # 新增参数：是否使用对称范围
):
    # ...
    if symmetric_range:
        abs_max = max(abs(max_val), abs(min_val))
        max_val = abs_max
        min_val = -abs_max
    # ...
```

## 实施优先级

1. **高优先级**：在天空温度计算中添加海拔修正（方案1）
   - 直接影响高海拔地区的计算准确性
   - 是导致高海拔地区效果差的根本原因

2. **中优先级**：改进地图可视化（方案2）
   - 改善用户体验
   - 但不影响计算结果的准确性

## 预期效果

实施方案1后：
- 高海拔地区的天空温度会更低（更接近实际情况）
- 辐射制冷节能效果会提高
- 不同地区之间的差异会更合理

实施方案2后：
- 地图颜色分布更均匀
- 极端值不会过度影响可视化效果
- 更容易识别不同地区的相对差异
