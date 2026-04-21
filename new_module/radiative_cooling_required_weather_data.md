# 辐射制冷功率模型：建议下载的气象数据清单（MVP + 推荐扩展）

本清单面向**基于实时天气预测辐射制冷净功率**的建模/计算。

目标量通常为：
\[
P_\text{net}=P_\text{rad,out}-P_\text{rad,in}-P_\text{solar,abs}-P_\text{conv}-P_\text{latent}(可选)-P_\text{cond}(通常不由天气给出)
\]

其中：
- `rad,in` 主要由天空下行长波决定
- `solar,abs` 由地表下行短波与材料太阳吸收率决定
- `conv` 由2m温度与10m风速决定
- `latent` 取决于是否考虑蒸发/结露（需湿度/露点）

---

## 1. 最小可行数据集（MVP）

### 1.1 夜间净辐射制冷（不含太阳短波）
- **2m temperature**
  - 用于对流换热与环境温度 `T_air`
- **2m dewpoint temperature**
  - 用于表征湿度（水汽）并辅助估算天空辐射/结露风险
- **10m u-component of wind**
- **10m v-component of wind**
  - 合成风速 `U10 = sqrt(u10^2 + v10^2)` 用于对流换热系数
- **Surface thermal radiation downwards**
  - 地表下行长波 `L_down`，直接决定天空对器件的长波输入

### 1.2 白天净制冷（在夜间MVP基础上增加短波）
- **Surface solar radiation downwards**
  - 地表下行太阳短波 `S_down`，用于计算吸收太阳热 `S_abs = alpha_solar * S_down`

---

## 2. 推荐扩展数据集（提升精度/可解释性/鲁棒性）

### 2.0 风与近地湍流换热增强项（建议补充）
- **10m wind gust since previous post-processing**（可选）
- **Instantaneous 10m wind gust**（可选）
  - 阵风会放大瞬时对流换热；做分钟级/瞬时功率或极端工况评估时很有价值。
- **10m u-component of neutral wind**（可选）
- **10m v-component of neutral wind**（可选）
  - 用于更偏边界层中性的换热估计；一般有 `10m u/v` 已足够。

### 2.1 云对长波与短波的影响（强烈建议）
- **Total cloud cover**
  - 用于解释/修正下行长波与短波的变化；在缺少下行长波时可用于经验估算
- **Low cloud cover**
- **Medium cloud cover**
- **High cloud cover**
  - 分层云量可提升对下行长波与夜间制冷的刻画
- **Cloud base height**（可选）
  - 低云云底越低通常下行长波越强
- **Total column cloud liquid water**（可选）
- **Total column cloud ice water**（可选）
  - 云光学厚度/发射能力的更直接代理

### 2.2 清空辐射（用于分离“云效应”，可选）
- **Surface thermal radiation downward, clear sky**（可选）
- **Surface solar radiation downward, clear sky**（可选）
- **Surface net thermal radiation, clear sky**（可选）
- **Surface net solar radiation, clear sky**（可选）
  - 可用于构造特征：`all_sky - clear_sky` 表征云辐射强迫

### 2.3 湿度/水汽的更强指标（若可获取，建议优先）
- **Total column water vapour**
  - 比仅用2m露点更能表征大气整体水汽含量；对8–13μm大气窗口与天空下行长波影响显著

### 2.4 气压与近地层参数（可选）
- **Surface pressure**
  - 用于更严谨的湿度换算与空气性质估计
- **Mean sea level pressure**（一般不必，已下载Surface pressure可不选）

### 2.5 太阳辐射分量与反照率（可选，精细化白天模型）
- **Clear-sky direct solar radiation at surface**（可选）
- **Total sky direct solar radiation at surface**（可选）
  - 直射/散射分解、入射角相关建模时有帮助
- **Downward UV radiation at the surface**（可选）
  - 如果你单独关注UV段吸收/老化/或用更细波段短波吸收建模，可加入；否则 `Surface solar radiation downwards` 通常已足够。
- **UV visible albedo for direct radiation**（可选）
- **UV visible albedo for diffuse radiation**（可选）
- **Near IR albedo for direct radiation**（可选）
- **Near IR albedo for diffuse radiation**（可选）
  - 更偏地表能量收支；对“器件材料”反射率仍应以材料参数为主

---

## 3. 可用于质量控制/场景筛选（不直接进入主公式，但很实用）

- **Total precipitation** / **Large-scale precipitation** / **Convective precipitation** / 各类 rain rate
  - 用于标记降雨时段（雨会改变表面状态、云厚、湿度），可做剔除或单独建模
- **Snowfall / Snowmelt / Snow depth / Snow albedo**
  - 仅当器件在积雪环境工作时用于筛选/分组

---

## 4. 通常不建议为了“地面辐射制冷器件功率”而下载的变量（除非你的场景特殊）

这些变量要么与海洋/波浪/湖泊/垂直通量诊断相关，要么属于模式内部诊断通量，**对器件净功率建模不如直接使用上面清单**：

- 海浪/海洋波谱相关：Mean wave direction/period、Significant wave height、swell/wind waves 等
- 湖泊相关：Lake bottom temperature、Lake mix-layer 等
- 多数 Vertical integrals（各类水汽/能量/通量散度积分，除非你做大尺度环流研究）
- Soil/Ice 各层温度（除非你做与地面深层导热强耦合的地表能量平衡）
- 模式给出的湍流通量：Surface sensible heat flux、Surface latent heat flux（可作为对流/蒸发项的“参考”或监督信号，但做可解释物理模型时更常用 `T2m+U10` 自算）

---

## 5. 建议你最终下载的“字段集合”（可直接复制勾选）

### 5.1 必选（MVP）
- 2m temperature
- 2m dewpoint temperature
- 10m u-component of wind
- 10m v-component of wind
- Surface thermal radiation downwards
- Surface solar radiation downwards

### 5.2 强烈建议增加（推荐扩展）
- Total cloud cover
- Low cloud cover
- Medium cloud cover
- High cloud cover
- Surface pressure
- Total column water vapour
- Total precipitation（用于降雨时段筛选/剔除或单独建模）

### 5.3 可选（看你要不要做“清空/云效应分离”）
- Surface thermal radiation downward, clear sky
- Surface solar radiation downward, clear sky
- Surface net thermal radiation, clear sky
- Surface net solar radiation, clear sky
- Cloud base height
- Total column cloud liquid water
- Total column cloud ice water

---

## 6. 重要注意事项（下载与后续分析）

- **单位**：辐射量通常是 `J/m^2` 累积量或 `W/m^2` 瞬时量（不同数据集定义不同），下载后需要统一到同一时间步的平均功率。
- **时间对齐**：确保 `T2m、Td2m、U10/V10、SSRD、STRD、cloud` 在同一时间戳。
- **空间代表性**：再分析/预报格点的云与辐射对点位偏差可能较大，建议后续做站点观测校准（若有）。

