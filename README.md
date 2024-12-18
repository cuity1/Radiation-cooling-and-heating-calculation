想看英文自己翻译
If you want to read English, please translate it yourself


# -代码执行逻辑如下：
-	
  - **外层循环**: 遍历所有对流换热系数 `H_conv`。
  - **内层循环**: 遍历所有薄膜温度 `T_s_current`。
  - **计算步骤**:
    1. **计算大气和薄膜的黑体辐射率**:
       - 使用普朗克定律计算不同波长和温度下的黑体辐射功率密度。
       - 处理指数溢出问题，防止计算时出现数值溢出。
    2. **计算波长间隔**:
       - 计算波长步长 `dlam1` 和 `dlam2`，用于数值积分。
    3. **计算薄膜的辐射功率密度**:
       - 结合发射率 `e_smat` 和波长间隔，计算辐射功率密度 `tempint_R3`。
       - 对波长和角度进行积分，得到总辐射功率 `p_r`。
    4. **计算大气的辐射功率密度**:
       - 结合大气发射率 `e_zmat` 和波长间隔，计算辐射功率密度 `tempint_R1`。
       - 对波长和角度进行积分，得到大气辐射功率 `p_a`。
    5. **计算对流换热功率**:
       - 使用牛顿冷却定律计算对流换热功率 `Q_conv`。
    6. **计算太阳辐照度功率**:
       - 计算太阳辐照度对材料的功率影响 `Q_solar`。
    7. **计算净辐射冷却功率**:
       - 综合所有功率，得到净冷却功率 `p_net`:
         \[
         P_{\text{net}} = P_r - P_a - Q_{\text{conv}} - Q_{\text{solar}}
         \]
    8. **存储结果**:
       - 将计算得到的净冷却功率存储在结果矩阵中。



代码主要分为两个主函数：`main_cooling_gui` 和 `main_heating_gui`，分别用于计算辐射冷却功率和辐射加热功率。本文将以 `main_cooling_gui` 为例，详细解释其计算逻辑，`main_heating_gui` 的逻辑与之类似。

## 1. **函数入口与必要文件检查**

### 1.1. 函数定义

```python
def main_cooling_gui(file_paths):
    """主程序逻辑"""
    ...
```

- **作用**: 这是主函数，负责协调整个辐射冷却功率的计算过程。
- **输入**: `file_paths`，一个包含必要文件路径的字典。

### 1.2. 检查必要文件是否已选择

```python
required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
for key in required_files:
    if key not in file_paths or not file_paths[key]:
        raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")
```

- **作用**: 确保所有必需的输入文件都已提供，否则抛出异常。
- **必要文件**:
  - `config`: 配置文件，包含各种参数。
  - `reflectance`: 反射率数据。
  - `spectrum`: 光谱数据。
  - `wavelength`: 波长数据。
  - `emissivity`: 薄膜发射率数据。
  - `atm_emissivity`: 大气发射率数据。

## 2. **加载配置文件与提取参数**

```python
config = load_config(file_paths['config'])

# 从配置中提取变量
DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
DECLARE_FILE = config['DECLARE_FILE']
EXPIRATION_DATE = config['EXPIRATION_DATE']
EMAIL_CONTACT = config['EMAIL_CONTACT']
H = config['H']
C = config['C']
KB = config['KB']
C1 = config['C1']
C2 = config['C2']
T_a1 = config['T_a1']
T_filmmin = config['T_filmmin']
T_filmmax = config['T_filmmax']
WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
VISIABLE_RANGE = config['VISIABLE_RANGE']
HC_VALUES = config['HC_VALUES']
S_solar = config['S_solar']
```

- **作用**: 从配置文件中加载并提取所需的参数，这些参数将在后续计算中使用。
- **关键参数**:
  - `H`: 对流换热系数（可能为多个值）。
  - `C1`, `C2`: 常数，通常与普朗克定律相关。
  - `T_a1`: 环境温度（摄氏度）。
  - `T_filmmin`, `T_filmmax`: 薄膜温度范围（摄氏度）。
  - `WAVELENGTH_RANGE`, `VISIABLE_RANGE`: 波长过滤范围。
  - `HC_VALUES`: 对流换热系数的多个取值。
  - `S_solar`: 太阳辐照度。

## 3. **过期检查**

```python
check_expiration(EXPIRATION_DATE, EMAIL_CONTACT)
```

- **作用**: 检查程序是否过期，可能用于授权控制或功能限制。

## 4. **加载与预处理数据**

### 4.1. 加载反射率与光谱数据

```python
reflectance_data = load_reflectance(file_paths['reflectance'])
spectrum_data = load_spectrum(file_paths['spectrum'])
```

- **作用**: 加载反射率和光谱数据，通常为二维数组，包含波长和相应的数值。

### 4.2. 过滤波长范围

```python
ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)
```

- **作用**: 根据指定的波长范围（`WAVELENGTH_RANGE` 和 `VISIABLE_RANGE`）过滤反射率和光谱数据。
- **结果**:
  - `ref_wavelength`, `reflectance_values`: 在 `WAVELENGTH_RANGE` 范围内的反射率数据。
  - `spec_wavelength`, `spectrum_values`: 在 `WAVELENGTH_RANGE` 范围内的光谱数据。
  - `ref_wavelength1`, `reflectance_values1`: 在 `VISIABLE_RANGE` 范围内的反射率数据。
  - `spec_wavelength1`, `spectrum_values1`: 在 `VISIABLE_RANGE` 范围内的光谱数据。

### 4.3. 插值光谱数据

```python
interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)
```

- **作用**: 将光谱数据插值到反射率数据的波长点上，确保两者具有相同的波长基准，以便后续的加权平均计算。

### 4.4. 计算加权平均反射率

```python
R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
R_sol1 = calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)
```

- **作用**: 计算加权平均反射率，权重由光谱数据决定。
- **意义**: 反射率的加权平均值反映了材料在整个光谱范围内的综合反射特性，影响太阳辐照度的吸收率。

### 4.5. 加载并插值发射率数据

```python
X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
    file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
)
```

- **作用**: 加载波长、薄膜发射率和大气发射率数据，并进行插值处理，使其在相同波长点上对齐。

### 4.6. 组合数据

```python
data1 = np.column_stack((X, emissivityatm_interpolated))  # 大气透过率
data2 = np.column_stack((X, emissivity_interpolated))    # 薄膜发射率
data1[:, 0] *= 1000
data2[:, 0] *= 1000
```

- **作用**: 将波长与对应的发射率数据组合成二维数组，并将波长单位从米转换为纳米（乘以1000）。

## 5. **设置温度参数**

```python
T_a = T_a1 + 273.15  # 环境温度（K）
T_film = np.arange(T_filmmin, T_filmmax, 1)  # 薄膜温度（°C）
T_sll = T_film + 273.15  # 薄膜温度（K）
delta_T = T_a1 - T_film  # 温差
```

- **作用**: 
  - 将环境温度从摄氏度转换为开尔文。
  - 定义薄膜温度的范围，并转换为开尔文。
  - 计算环境温度与薄膜温度的温差。

## 6. **加载与计算平均发射率**

```python
data = np.loadtxt(file_paths['emissivity'])
wavelength_um = data[:, 0]      # 第一列为波长，单位：微米
emissivity = data[:, 1]         # 第二列为发射率
wavelength_m = wavelength_um * 1e-6  # 转换为米

avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)
```

- **作用**: 
  - 加载发射率数据，将波长从微米转换为米。
  - 计算平均发射率，通常基于普朗克定律的积分结果，反映材料在特定温度下的整体发射能力。

## 7. **角度设置与积分准备**

```python
theta1 = 0
theta2 = np.pi / 2  # 90度转为弧度

# 角度积分准备
tmat = data1[:, 1]  # 大气透过率
nth = len(tmat) + 1
dth = (theta2 - theta1) / (nth - 1)
theta = np.linspace(theta1, theta2 - dth, nth - 1)
```

- **作用**: 
  - 定义积分的角度范围，从0到90度（弧度表示）。
  - 计算角度步长 `dth`，并生成角度数组 `theta`。
  - 角度积分用于计算不同入射角度下的辐射功率。

## 8. **波长转换与发射率计算**

```python
lambda1 = data1[:, 0] * 1e-9
lambda2 = data2[:, 0] * 1e-9
e_zmat, e_smat = calculate_radiation_power(data1, data2, theta, lambda1, lambda2)
```

- **作用**: 
  - 将波长从纳米转换为米。
  - 计算材料和大气的辐射功率密度，涉及普朗克定律和发射率。

## 9. **太阳辐照度与吸收率计算**

```python
S_solar = float(S_solar)
alpha_s = 1 - R_sol
```

- **作用**: 
  - 确保太阳辐照度为浮点数。
  - 计算太阳光的吸收率 `alpha_s`，即材料吸收的太阳光比例。

## 10. **初始化结果矩阵**

```python
results = np.zeros((len(T_film), len(HC_VALUES)))
```

- **作用**: 
  - 创建一个二维数组，用于存储不同薄膜温度和对流换热系数下的净辐射冷却功率。

## 11. **净辐射冷却功率的计算**

```python
for hc_index, H_conv in enumerate(HC_VALUES):
    print(f'Processing convection heat transfer coefficient: {H_conv} W/m²·K')
    for i, T_s_current in enumerate(T_sll):
        ...
        # 计算净辐射冷却功率
        p_net = p_r - p_a - Q_conv - Q_solar

        # 存储结果
        results[i, hc_index] = p_net
```

- **作用**: 
  - **外层循环**: 遍历所有对流换热系数 `H_conv`。
  - **内层循环**: 遍历所有薄膜温度 `T_s_current`。
  - **计算步骤**:
    1. **计算大气和薄膜的黑体辐射率**:
       - 使用普朗克定律计算不同波长和温度下的黑体辐射功率密度。
       - 处理指数溢出问题，防止计算时出现数值溢出。
    2. **计算波长间隔**:
       - 计算波长步长 `dlam1` 和 `dlam2`，用于数值积分。
    3. **计算薄膜的辐射功率密度**:
       - 结合发射率 `e_smat` 和波长间隔，计算辐射功率密度 `tempint_R3`。
       - 对波长和角度进行积分，得到总辐射功率 `p_r`。
    4. **计算大气的辐射功率密度**:
       - 结合大气发射率 `e_zmat` 和波长间隔，计算辐射功率密度 `tempint_R1`。
       - 对波长和角度进行积分，得到大气辐射功率 `p_a`。
    5. **计算对流换热功率**:
       - 使用牛顿冷却定律计算对流换热功率 `Q_conv`。
    6. **计算太阳辐照度功率**:
       - 计算太阳辐照度对材料的功率影响 `Q_solar`。
    7. **计算净辐射冷却功率**:
       - 综合所有功率，得到净冷却功率 `p_net`:
         \[
         P_{\text{net}} = P_r - P_a - Q_{\text{conv}} - Q_{\text{solar}}
         \]
    8. **存储结果**:
       - 将计算得到的净冷却功率存储在结果矩阵中。

## 12. **绘制结果图**

```python
plt.figure(figsize=(10, 6))

num_lines = len(HC_VALUES)

# 使用色图 'tab10' 提供最多10种不同颜色
cmap = plt.get_cmap('tab10')
colors = [cmap(i % cmap.N) for i in range(num_lines)]

# 定义可循环的线型
linestyles = cycle(['-', '--', '-.', ':'])

T_film_diff = T_film - T_a1  # 温差

for hc_index in range(num_lines):
    color = colors[hc_index]
    linestyle = next(linestyles)  # 循环使用线型
    plt.plot(T_film_diff, results[:, hc_index], color=color, linestyle=linestyle, linewidth=2,
            label=f'h_c={HC_VALUES[hc_index]} W m⁻² K⁻¹')

plt.xlabel('T_{film} - T_{ambient} (°C)', fontsize=12)
plt.ylabel('Cooling Power (W m⁻²)', fontsize=12)
plt.title('Radiative cooling power vs film temperature difference', fontsize=14)
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
```

- **作用**: 
  - 绘制薄膜温度差与净辐射冷却功率的关系图。
  - 每条曲线对应一个对流换热系数，使用不同的颜色和线型区分。

## 13. **保存结果到CSV**

```python
print("请填写保存结果文件路径")
root = tk.Tk()
root.withdraw()
save_file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                              title="保存文件",
                                              filetypes=[("CSV files", "*.csv")])
root.destroy()
if save_file_path:
    try:
        export_data = {'T_film_diff (°C)': T_film_diff}
        for hc_index, hc_value in enumerate(HC_VALUES):
            export_data[f'Cooling_Power_hc_{hc_value}'] = results[:, hc_index]
        df_export = pd.DataFrame(export_data)
        df_export.to_csv(save_file_path, index=False)
        print(f'插值并保存完成！文件保存为 {save_file_path}')
    except Exception as e:
        print(f"保存结果时出错: {e}")
else:
    print("未选择保存文件路径，程序退出。")
```

- **作用**: 
  - 提示用户选择保存结果的CSV文件路径。
  - 将温度差和对应的净冷却功率数据保存为CSV文件，便于后续分析和记录。

## 14. **创建声明文件**

```python
create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)
return avg_emissivity, R_sol, R_sol1
```

- **作用**: 
  - 创建一个声明文件，可能包含版权信息、使用说明或其他相关声明。
  - 返回平均发射率和加权反射率的值。

## 15. **关键计算步骤的详细解析**

### 15.1. **普朗克黑体辐射定律的应用**

```python
u_b1ams1 = 1e9 * (lambda1 ** 5) * (np.exp(C2 / (lambda1 * T_a)) - 1)
u_bs1 = C1 / u_b1ams1
```

- **作用**: 
  - 计算大气的黑体辐射功率密度。
  - 公式来源于普朗克定律：
    \[
    u(\lambda, T) = \frac{2\pi hc^2}{\lambda^5} \cdot \frac{1}{e^{\frac{hc}{\lambda k_B T}} - 1}
    \]
  - 在代码中，`C1` 和 `C2` 代表常数的组合，具体值取决于配置文件。

### 15.2. **辐射功率密度的计算**

#### 材料的辐射功率密度

```python
tempint_R3 = u_bs * e_smat * dlam2
int_R3am = np.sum(tempint_R3)
tempint_Rt3 = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth * int_R3am
int_Rth3 = np.sum(tempint_Rt3)
p_r = int_Rth3
```

- **作用**: 
  - 计算材料的总辐射功率 `p_r`。
  - 考虑发射率 `e_smat` 和波长间隔 `dlam2`。
  - 使用数值积分方法，结合角度和波长进行积分。

#### 大气的辐射功率密度

```python
tempint_R1 = u_bs1 * e_smat * e_zmat * dlam1
int_R1am = np.sum(tempint_R1)
tempint_Rt1 = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth * int_R1am
int_Rth1 = np.sum(tempint_Rt1)
p_a = int_Rth1
```

- **作用**: 
  - 计算大气对材料的辐射吸收功率 `p_a`。
  - 考虑大气发射率 `e_zmat` 和薄膜发射率 `e_smat`，以及波长间隔 `dlam1`。
  - 使用数值积分方法，结合角度和波长进行积分。

### 15.3. **对流换热功率的计算**

```python
Q_conv = H_conv * (T_a1 - T_film[i])
```

- **作用**: 
  - 使用牛顿冷却定律计算对流换热功率 `Q_conv`：
    \[
    Q_{\text{conv}} = h_c \cdot (T_{\text{ambient}} - T_{\text{film}})
    \]
  - 其中，`h_c` 是对流换热系数，`T_a1` 是环境温度，`T_film[i]` 是当前薄膜温度。

### 15.4. **太阳辐照度功率的计算**

```python
Q_solar = alpha_s * S_solar
```

- **作用**: 
  - 计算太阳辐照度对材料的功率影响 `Q_solar`：
    \[
    Q_{\text{solar}} = \alpha_s \cdot S_{\text{solar}}
    \]
  - 其中，`alpha_s` 是太阳光吸收率，`S_solar` 是太阳辐照度。

### 15.5. **净辐射冷却功率的计算**

```python
p_net = p_r - p_a - Q_conv - Q_solar
```

- **作用**: 
  - 综合所有功率，计算净冷却功率 `p_net`：
    \[
    P_{\text{net}} = P_r - P_a - Q_{\text{conv}} - Q_{\text{solar}}
    \]
  - 其中：
    - \( P_r \): 材料的辐射功率。
    - \( P_a \): 大气的辐射功率。
    - \( Q_{\text{conv}} \): 对流换热功率。
    - \( Q_{\text{solar}} \): 太阳辐照度功率。

## 16. **总结**

### 16.1. **冷却计算逻辑概述**

1. **数据准备**:
   - 加载并预处理反射率、光谱、发射率等数据。
   - 过滤波长范围，插值数据，确保数据在相同波长点上对齐。
   
2. **参数设置**:
   - 定义环境温度、薄膜温度范围、对流换热系数等关键参数。
   
3. **功率计算**:
   - 使用普朗克定律计算材料和大气的辐射功率密度。
   - 通过数值积分计算总辐射功率 \( P_r \) 和 \( P_a \)。
   - 计算对流换热功率 \( Q_{\text{conv}} \) 和太阳辐照度功率 \( Q_{\text{solar}} \)。
   - 综合所有功率，得到净冷却功率 \( P_{\text{net}} \)。
   
4. **结果输出**:
   - 将计算结果存储在结果矩阵中。
   - 绘制温度差与净冷却功率的关系图。
   - 保存结果到CSV文件，创建声明文件。

### 16.2. **加热计算逻辑**

`main_heating_gui` 函数的逻辑与 `main_cooling_gui` 类似，但在功率计算上有细微差别，具体如下：

- **净加热功率计算**:
  \[
  P_{\text{heat}} = Q_{\text{solar}} + P_a + Q_{\text{conv}} - P_r
  \]
- **意义**: 
  - 考虑太阳辐照度、大气辐射和对流换热对材料的加热作用，减去材料自身的辐射冷却作用。

