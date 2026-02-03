<!--
  README is bilingual (中文/English).
  GitHub does not support real "button" toggles in pure Markdown.
  This README uses a GitHub-friendly language switcher via anchor links.
-->

<div align="center">

# Radiative Cooling & Heating Calculator

# 辐射制冷/制热计算器

**A research-grade tool to compute radiative cooling/heating power from spectral optical data and atmospheric models**  \
**面向科研的辐射制冷/制热功率计算工具：基于材料光谱与大气模型进行精确积分计算**

**FOR  online use ：http://radiative.top:5188
网页端功能更齐全、更加智能：http://radiative.top:5188  /**
<a href="#english"><strong>English</strong></a> • <a href="#chinese"><strong>中文</strong></a>

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15%2B-green.svg)](https://pypi.org/project/PyQt5/)
[![License](https://img.shields.io/badge/License-Academic-orange.svg)](LICENSE)

<div align="left">
## English

### What is this?
This repository provides a **PyQt-based GUI** and **Python core library** for computing:

- **Net radiative cooling power** (daytime/nighttime)
- **Net radiative heating power**
- **Solar-weighted reflectance / absorptance** (AM1.5 spectrum)
- **Temperature-weighted average emissivity**
- **Convection (natural + forced, Churchill–Usagi blending)**
- Parameter sweeps and plot-ready power decomposition

The implementation is designed to be practical for materials research (spectral selectivity), thermal management, and building energy applications.

**FOR  online use ：http://radiative.top:5188
网页端功能更齐全、更加智能：http://radiative.top:5188  /**
### Download
- Baidu Netdisk: https://pan.baidu.com/s/1RwgC-En28zfwQtf9DOfw9A?pwd=USTC
- GitHub Releases: https://github.com/cuity1/Radiation-cooling-and-heating-calculation/releases

Community group:
- QQ group: http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=jFVhTIuH2_MxUv8UH6NkoMeV3pXX4eJg&authKey=Zv0lhgtkheyCAD5b2LmHRef2vxcqkFdoJY5rHxxs93oSSANdwxbezu%2BGOXOqiLfO&noverify=0&group_code=767753318

---

## Project structure

```
.
├─ core/                   # Non-GUI computational core (physics + spectrum + integrations)
│  ├─ calculations.py       # High-level calculation entry points used by GUI
│  ├─ physics.py            # Physical models (Planck, emissivity avg, convection)
│  ├─ spectrum.py           # Data loading + interpolation + weighted integrals
│  ├─ plots.py              # Plot helpers (if used)
│  └─ ...
├─ gui/                     # PyQt GUI, dialogs, threads, i18n
├─ default/                 # Default datasets (AM1.5, wavelength grid, atmos profiles, config)
├─ main.py / main_Qt.py     # Launchers
└─ README.md
```

---

## Quick start

### 1) Environment
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux:
#   source venv/bin/activate
pip install -r requirements.txt
```

> If `requirements.txt` is not present in your fork, install the typical stack: `numpy scipy pandas matplotlib openpyxl PyQt5`.

### 2) Run GUI
```bash
python main.py
```

---

## Inputs & data conventions

Most computations depend on **six files** (selected in the GUI):

| Key | Typical file | Meaning |
|---|---|---|
| `config` | `default/config.ini` | constants, wavelength ranges, temperature ranges, h-values, etc. |
| `reflectance` | (txt/csv) | spectral reflectance R(λ) (solar band) |
| `spectrum` | `default/AM1.5.xlsx` | solar spectrum I(λ) |
| `wavelength` | `default/Wavelength.csv` | wavelength grid for IR window interpolation |
| `emissivity` | (txt) | material emissivity ε(λ) (IR window) |
| `atm_emissivity` | (txt / *.dll in default) | atmospheric transmittance/emissivity data |

**Important:**
- Reflectance/emissivity values should be in **[0,1]**. The loader will scale common “percent” inputs (0–100) down.
- Wavelength units are auto-handled in several loaders (e.g., nm → μm) but keep files consistent whenever possible.

---

## Computational logic (module-by-module)

This section maps the **code modules** to the **math** actually implemented in this repository, and clarifies the sign conventions.

### 1) Solar-weighted reflectance (R_sol) — `core/spectrum.py` + `core/calculations.py`

**Where in code**
- `core/calculations.py::calculate_R_sol()`
- `core/spectrum.py::calculate_weighted_reflectance()`
- Interpolation: `core/spectrum.py::interpolate_spectrum()` (PCHIP, no extrapolation)

**Math**
Given reflectance $R(\lambda)$ and solar spectrum $I(\lambda)$ on the same grid:

$$
R_{\mathrm{sol}}=\frac{\int_{\lambda_1}^{\lambda_2} R(\lambda)\, I(\lambda)\, d\lambda}{\int_{\lambda_1}^{\lambda_2} I(\lambda)\, d\lambda}
$$

Then the solar absorptance used in the cooling/heating balance is:

$$
\alpha_s = 1 - R_{\mathrm{sol}}
$$

Notes:
- Wavelength ranges come from `config.ini`: `WAVELENGTH_RANGE` (solar band), and `VISIABLE_RANGE` for visible-only weighted metrics.

---

### 2) Temperature-weighted average emissivity — `core/physics.py`

**Where in code**
- `core/physics.py::planck_lambda()`
- `core/physics.py::calculate_average_emissivity()`

**Math**
Using Planck spectral radiance (as implemented):

$$
I_{\mathrm{BB}}(\lambda, T)=\frac{2 h c^2}{\lambda^5}\,\frac{1}{\exp\!\left(\frac{h c}{\lambda k_B T}\right)-1}
$$

Average emissivity weighted by the blackbody spectrum:

$$
\bar{\varepsilon}(T)=\frac{\int \varepsilon(\lambda)\, I_{\mathrm{BB}}(\lambda, T)\, d\lambda}{\int I_{\mathrm{BB}}(\lambda, T)\, d\lambda}
$$

Numerical integration uses trapezoidal integration (`np.trapezoid` / `np.trapz`).

---

### 3) Angular integration grid — `core/calculations.py::_build_angle_grid`

**Where in code**
- `_build_angle_grid(angle_steps)`

The code discretizes the hemisphere $\theta\in[0,\pi/2)$ with:

- $d\theta$ uniform
- solid-angle factor (Lambertian weighting):

$$
\mathrm{angle\_factor}=2\pi\,\sin\theta\,\cos\theta\, d\theta
$$

This factor is later multiplied by the spectral integral to obtain hemispherical power.

---

### 4) Radiative terms: surface emission and atmospheric back radiation — `core/calculations.py::_radiative_terms`

**Where in code**
- `_planck_spectral_exitance()` (numerically stable exponent cap)
- `_radiative_terms()`

**Atmosphere model used**
Atmospheric “effective emissivity” is computed from transmittance $\tau(\lambda)$ (named `tmat` in code) via:

$$
\varepsilon_{\mathrm{atm}}(\lambda,\theta)=1-\tau(\lambda)^{\sec\theta}
$$

**Surface → space term**
The code computes (discretized form):

$$
P_{\mathrm{rad}}(T_s)=\int_{\Omega} \cos\theta\, d\Omega\;\int \varepsilon_s(\lambda)\, I_{\mathrm{BB}}(\lambda, T_s)\, d\lambda
$$

**Atmosphere → surface term**

$$
P_{\mathrm{atm}}(T_a)=\int_{\Omega} \cos\theta\, d\Omega\;\int \varepsilon_s(\lambda)\,\varepsilon_{\mathrm{atm}}(\lambda,\theta)\, I_{\mathrm{BB}}(\lambda, T_a)\, d\lambda
$$

In code, these are `p_r` and `p_a` respectively.

---

### 5) Convection (natural + forced) — `core/physics.py::calculate_convection_coefficient`

**Where in code**
- `core/physics.py::calculate_convection_coefficient()`

This function estimates air properties and applies common flat-plate correlations:

Natural convection:
- $Ra = g\beta |\Delta T| L^3/(\nu\alpha)$
- $Nu_{\mathrm{nat}} = 0.54\, Ra^{1/4}$ (laminar, $Ra<10^7$)
- $Nu_{\mathrm{nat}} = 0.15\, Ra^{1/3}$ (turbulent)

Forced convection:
- $Re = vL/\nu$
- $Nu_{\mathrm{forced}} = 0.664\, Re^{1/2} Pr^{1/3}$ (laminar)
- $Nu_{\mathrm{forced}} = 0.037\, Re^{4/5} Pr^{1/3}$ (turbulent)

Churchill–Usagi blending (implemented):

$$
h = \left(h_{\mathrm{nat}}^n + h_{\mathrm{forced}}^n\right)^{1/n},\quad n=3
$$

The function returns a minimum of 1.0 W/(m²·K) for numerical stability.

---

### 6) Net cooling power balance — `core/calculations.py::main_cooling_gui`

**Where in code**
- `main_cooling_gui()`

At each film temperature `T_film` (°C) with ambient `T_a1` (°C):

- `p_r`: surface radiative emission (W/m²)
- `p_a`: atmospheric downward radiation absorbed by surface (W/m²)
- `Q_solar = α_s * S_solar`
- `Q_conv` is implemented using the sign convention:

$$
Q_{\mathrm{conv}} = h_{\mathrm{total}}\,(T_{\mathrm{amb}}-T_{\mathrm{film}})
$$

and the net cooling power is computed as:

$$
P_{\mathrm{net}} = p_r - p_a - Q_{\mathrm{conv}} - Q_{\mathrm{solar}} + P_{\mathrm{phase}}
$$

Where optional `P_phase` adds extra cooling power above a phase-change trigger temperature (see `_phase_power`).

**What is reported as “Power_0”**
The code extracts the index closest to `T_film == T_amb` and reports $P_{\mathrm{net}}(\Delta T\approx 0)$.

---

### 7) Net heating power balance — `core/calculations.py::main_heating_gui`

**Where in code**
- `main_heating_gui()`

Heating mode is computed as the “opposite” balance:

$$
P_{\mathrm{heat}} = Q_{\mathrm{solar}} + p_a + Q_{\mathrm{conv}} - p_r - P_{\mathrm{phase}}
$$

So a larger solar absorption and atmospheric back radiation increases heating power.

---

## Outputs

Typical outputs exposed in GUI and/or returned from `skip_dialog=True` include:

- `R_sol`: solar-weighted reflectance
- `R_sol1`: visible-weighted reflectance
- `avg_emissivity`: temperature-weighted average emissivity
- `results`: power matrix vs. film temperature and convection coefficients
- `Power_0`: power at ΔT ≈ 0

---

## Citation / Academic use
If you use this tool in research, please cite relevant radiative cooling literature and acknowledge the repository.
(1) Cui, T.; Zheng, Y.; Cai, W.; Qi, L.; Wang, J.; Yang, W.; Song, W.; Hu, Y.; Zhu, J. Quantum to Device AI-Guided Passivation Paradigm for All-Weather Ultrastable MXene Based Photothermal Converter. Advanced Materials 2026, e19482.
(2) Cui, T.; Zhao, Y.; Zheng, Y.; Qi, L.; Cai, W.; Wang, J.; Nie, S.; Song, W.; Hu, Y.; Yang, W.; Zhu, J. Mie-Resonant Thermochromic Safe Architectures for All-Season Radiative Thermal Management. Advanced Energy Materials 2026, e06717.

---

## License
Academic / research use. See `LICENSE` (if present) and the project statements in `default/计算与文章发表声明.txt`.

---

## Chinese

### 项目简介
本仓库提供一个 **PyQt 图形界面 + Python 核心计算库**，用于计算：

- **辐射净制冷功率**（白天/夜间）
- **辐射净制热功率**
- **太阳光谱加权反射率 / 吸收率**（AM1.5）
- **黑体谱加权平均发射率**
- **自然对流 + 强制对流（Churchill–Usagi 混合法）**
- 参数扫描与功率分量分解（便于画图/发文章）

该实现面向材料光谱选择性设计、热管理与建筑节能等科研应用。
**FOR  online use ：http://radiative.top:5188
网页端功能更齐全、更加智能：http://radiative.top:5188  /**
### 下载
- 百度网盘： https://pan.baidu.com/s/1RwgC-En28zfwQtf9DOfw9A?pwd=USTC
- GitHub Releases： https://github.com/cuity1/Radiation-cooling-and-heating-calculation/releases

交流群：
- QQ 群： http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=jFVhTIuH2_MxUv8UH6NkoMeV3pXX4eJg&authKey=Zv0lhgtkheyCAD5b2LmHRef2vxcqkFdoJY5rHxxs93oSSANdwxbezu%2BGOXOqiLfO&noverify=0&group_code=767753318

---

## 目录结构

```
.
├─ core/                   # 非GUI计算核心（物理模型 + 光谱处理 + 数值积分）
│  ├─ calculations.py       # GUI调用的高层计算入口
│  ├─ physics.py            # 物理模型（普朗克定律、平均发射率、对流换热系数）
│  ├─ spectrum.py           # 数据读取/插值/光谱加权积分
│  ├─ plots.py              # 绘图工具（如使用）
│  └─ ...
├─ gui/                     # PyQt 界面、对话框、线程、i18n
├─ default/                 # 默认数据（AM1.5、波长网格、大气数据、配置文件）
├─ main.py / main_Qt.py     # 启动入口
└─ README.md
```

---

## 快速开始

### 1）安装环境
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

> 若仓库中没有提供 `requirements.txt`，一般需要：`numpy scipy pandas matplotlib openpyxl PyQt5`。

### 2）运行程序
```bash
python main.py
```

---

## 输入文件与数据约定

大部分计算依赖 GUI 选择的 **6 个文件**：

| Key | 常见文件 | 含义 |
|---|---|---|
| `config` | `default/config.ini` | 常数、波段范围、温度范围、对流系数列表等 |
| `reflectance` | (txt/csv) | 材料反射率 R(λ)（太阳波段） |
| `spectrum` | `default/AM1.5.xlsx` | 太阳光谱 I(λ) |
| `wavelength` | `default/Wavelength.csv` | 大气窗口插值用的波长网格 |
| `emissivity` | (txt) | 材料发射率 ε(λ)（大气窗口） |
| `atm_emissivity` | (txt / *.dll) | 大气透过率/等效发射率数据 |

注意：
- 反射率/发射率应在 **[0,1]**。程序会对常见的百分数输入（0–100）进行缩放。
- 若波长单位混用（nm/μm），部分读取函数会自动处理，但建议文件本身保持一致。

---

## 计算逻辑（按模块拆解）

下面将仓库中的 **模块** 与 **实际实现的计算公式/符号约定** 一一对应，便于复现实验与论文写作。

### 1）太阳光谱加权反射率 R_sol — `core/spectrum.py` + `core/calculations.py`

代码位置：
- `core/calculations.py::calculate_R_sol()`
- `core/spectrum.py::calculate_weighted_reflectance()`
- 光谱插值：`core/spectrum.py::interpolate_spectrum()`（PCHIP，避免振铃；区间外用边界值）

公式：

$$
R_{\mathrm{sol}}=\frac{\int_{\lambda_1}^{\lambda_2} R(\lambda)\, I(\lambda)\, d\lambda}{\int_{\lambda_1}^{\lambda_2} I(\lambda)\, d\lambda}
$$

太阳吸收率：

$$
\alpha_s = 1 - R_{\mathrm{sol}}
$$

其中波段来自 `config.ini` 的 `WAVELENGTH_RANGE`（太阳波段）与 `VISIABLE_RANGE`（可见光波段）。

---

### 2）黑体谱加权平均发射率 — `core/physics.py`

代码位置：
- `core/physics.py::planck_lambda()`
- `core/physics.py::calculate_average_emissivity()`

普朗克定律（代码实现形式）：

$$
I_{\mathrm{BB}}(\lambda, T)=\frac{2 h c^2}{\lambda^5}\,\frac{1}{\exp\!\left(\frac{h c}{\lambda k_B T}\right)-1}
$$

加权平均发射率：

$$
\bar{\varepsilon}(T)=\frac{\int \varepsilon(\lambda)\, I_{\mathrm{BB}}(\lambda, T)\, d\lambda}{\int I_{\mathrm{BB}}(\lambda, T)\, d\lambda}
$$

数值积分使用梯形积分（`np.trapezoid/np.trapz`）。

---

### 3）角度积分离散 — `core/calculations.py::_build_angle_grid`

半球积分采用 $\theta\in[0,\pi/2)$ 的均匀步长离散，并使用 Lambertian 权重：

$$
\mathrm{angle\_factor}=2\pi\,\sin\theta\,\cos\theta\, d\theta
$$

---

### 4）辐射分量：向外辐射与大气回辐射 — `core/calculations.py::_radiative_terms`

大气等效发射率（由透过率得到）：

$$
\varepsilon_{\mathrm{atm}}(\lambda,\theta)=1-\tau(\lambda)^{\sec\theta}
$$

向外辐射（表面 → 太空）：

$$
P_{\mathrm{rad}}(T_s)=\int_{\Omega} \cos\theta\, d\Omega\;\int \varepsilon_s(\lambda)\, I_{\mathrm{BB}}(\lambda, T_s)\, d\lambda
$$

大气回辐射（大气 → 表面）：

$$
P_{\mathrm{atm}}(T_a)=\int_{\Omega} \cos\theta\, d\Omega\;\int \varepsilon_s(\lambda)\,\varepsilon_{\mathrm{atm}}(\lambda,\theta)\, I_{\mathrm{BB}}(\lambda, T_a)\, d\lambda
$$

在代码中分别对应 `p_r` 与 `p_a`。

---

### 5）对流换热系数（自然+强制）— `core/physics.py::calculate_convection_coefficient`

自然对流：
- $Ra = g\beta |\Delta T| L^3/(\nu\alpha)$
- $Nu_{\mathrm{nat}} = 0.54\,Ra^{1/4}$（层流）/ $0.15\,Ra^{1/3}$（湍流）

强制对流：
- $Re = vL/\nu$
- $Nu_{\mathrm{forced}} = 0.664\,Re^{1/2}Pr^{1/3}$（层流）/ $0.037\,Re^{4/5}Pr^{1/3}$（湍流）

混合（Churchill–Usagi）：

$$
h = \left(h_{\mathrm{nat}}^n + h_{\mathrm{forced}}^n\right)^{1/n},\quad n=3
$$

程序为了数值稳定返回最小值 1.0 W/(m²·K)。

---

### 6）净制冷功率 — `core/calculations.py::main_cooling_gui`

每个膜温 `T_film` 对应：
- `p_r`：向外辐射
- `p_a`：大气回辐射
- $Q_{\mathrm{solar}}=\alpha_s\, S_{\mathrm{solar}}$

对流项使用约定：

$$
Q_{\mathrm{conv}} = h_{\mathrm{total}}\,(T_{\mathrm{amb}}-T_{\mathrm{film}})
$$

净制冷功率：

$$
P_{\mathrm{net}} = p_r - p_a - Q_{\mathrm{conv}} - Q_{\mathrm{solar}} + P_{\mathrm{phase}}
$$

其中 $P_{\mathrm{phase}}$ 为可选相变附加功率（见 `_phase_power`：超过相变温度后线性爬升并平台）。

“Power_0” 为 $T_{\mathrm{film}}\approx T_{\mathrm{amb}}$（即 $\Delta T\approx 0$）时的净功率。

---

### 7）净制热功率 — `core/calculations.py::main_heating_gui`

制热模式计算：

$$
P_{\mathrm{heat}} = Q_{\mathrm{solar}} + p_a + Q_{\mathrm{conv}} - p_r - P_{\mathrm{phase}}
$$

太阳吸收与大气回辐射越大，制热功率越高。

---

## 输出参数
GUI/接口通常给出：

- `R_sol`：太阳加权反射率
- `R_sol1`：可见光加权反射率
- `avg_emissivity`：黑体谱加权平均发射率
- `results`：功率矩阵（膜温 × 对流系数组）
- `Power_0`：ΔT≈0 时功率

---

<<<<<<< HEAD
## 推荐引用的参考文献（如果您使用了该工具，希望您能够引用下面的参考文献）
(1) Cui, T.; Zheng, Y.; Cai, W.; Qi, L.; Wang, J.; Yang, W.; Song, W.; Hu, Y.; Zhu, J. Quantum to Device AI-Guided Passivation Paradigm for All-Weather Ultrastable MXene Based Photothermal Converter. Advanced Materials 2026, e19482.
(2) Cui, T.; Zhao, Y.; Zheng, Y.; Qi, L.; Cai, W.; Wang, J.; Nie, S.; Song, W.; Hu, Y.; Yang, W.; Zhu, J. Mie-Resonant Thermochromic Safe Architectures for All-Season Radiative Thermal Management. Advanced Energy Materials 2026, e06717.

=======
## 参考文献（建议）
- Raman, A. P., et al. *Nature* (2014)
- Zhao, D., et al. *Applied Physics Reviews* (2019)
>>>>>>> parent of 836f680 (update)

---

<div align="center">

<a href="#radiative-cooling--heating-calculator">Back to top</a> • <a href="#radiative-cooling--heating-calculator">返回顶部</a>

</div>

<!-- anchors -->
<a id="english"></a>
<a id="chinese"></a>
