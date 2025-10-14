# 🌡️ Radiative Cooling/Heating Calculator

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)](https://pypi.org/project/PyQt5/)
[![License](https://img.shields.io/badge/License-Academic-orange.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-3.5-red.svg)](https://github.com/yourusername/radiation-calculator)

> **Advanced Computational Tool for Thermal Radiation Analysis**

A sophisticated software package for calculating radiative cooling and heating power, designed for researchers and engineers in thermal management, building energy efficiency, and advanced material science.

---

## 📖 Overview

The Radiative Cooling/Heating Calculator provides accurate calculations of radiative heat transfer by incorporating:
- 🌅 Solar radiation (AM1.5G spectrum)
- 🌍 Atmospheric transparency windows (8-13 μm)
- 🔬 Material optical properties (spectral emissivity/reflectance)
- 💨 Convection effects (natural and forced)
- 📊 Multi-dimensional parametric analysis

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **❄️ Radiative Cooling** | Calculate cooling power using atmospheric transparency window with precise spectral integration |
| **🔥 Radiative Heating** | Compute heating power considering solar absorption and atmospheric downward radiation |
| **🗺️ Energy Mapping** | Generate energy efficiency maps for geographical and climate analysis |
| **💨 Convection Analysis** | Wind speed effects on cooling efficiency with Reynolds and Nusselt correlations |
| **📊 Data Visualization** | Interactive plots, contour maps, and 3D parametric surfaces |
| **🔧 Material Properties** | Customizable spectral emissivity and reflectance for various materials |
| **🌐 Multi-language** | Interface in Chinese and English with dynamic switching |
| **⚙️ Configuration Editor** | Built-in editor for modifying calculation parameters |

---

## 🔬 Physical Principles

### 1. Planck's Law of Blackbody Radiation

The spectral radiance of a blackbody at temperature $T$ is given by:

$$
I_{BB}(\lambda, T) = \frac{2hc^2}{\lambda^5} \frac{1}{e^{\frac{hc}{\lambda k_B T}} - 1}
$$

**Where:**
- $h = 6.626 \times 10^{-34}$ J·s (Planck's constant)
- $c = 2.998 \times 10^8$ m/s (speed of light)
- $k_B = 1.381 \times 10^{-23}$ J/K (Boltzmann constant)
- $\lambda$ = wavelength (m)
- $T$ = temperature (K)

### 2. Net Radiative Cooling Power

The net cooling power of a radiative cooler:

$$
P_{cool}(T) = P_{rad}(T) - P_{atm}(T_{amb}) - P_{solar} - P_{conv}
$$

#### a) Radiative Power (Upward)

$$
P_{rad}(T) = \int_0^{2\pi} d\phi \int_0^{\pi/2} \cos\theta \sin\theta \, d\theta \int_{\lambda_1}^{\lambda_2} \varepsilon(\lambda, \theta) I_{BB}(\lambda, T) \, d\lambda
$$

#### b) Atmospheric Radiation (Downward)

$$
P_{atm}(T_{amb}) = \int_0^{2\pi} d\phi \int_0^{\pi/2} \cos\theta \sin\theta \, d\theta \int_{\lambda_1}^{\lambda_2} \varepsilon(\lambda, \theta) \varepsilon_{atm}(\lambda, \theta) I_{BB}(\lambda, T_{amb}) \, d\lambda
$$

**Atmospheric emissivity** from Beer-Lambert law:

$$
\varepsilon_{atm}(\lambda, \theta) = 1 - \tau(\lambda)^{\sec\theta}
$$

#### c) Solar Absorption

$$
P_{solar} = \alpha_s \cdot I_{solar}
$$

**Solar absorptance** (weighted over AM1.5G spectrum):

$$
\alpha_s = 1 - R_{sol} = 1 - \frac{\int_{0.3}^{2.5} R(\lambda) I_{AM1.5}(\lambda) d\lambda}{\int_{0.3}^{2.5} I_{AM1.5}(\lambda) d\lambda}
$$

#### d) Convective Heat Transfer

$$
P_{conv} = h_c \cdot (T - T_{amb})
$$

### 3. Convection Coefficient Calculation

#### Natural Convection

**Rayleigh number:**

$$
Ra = \frac{g\beta \Delta T L^3}{\nu \alpha} = Gr \cdot Pr
$$

**Nusselt number:**

$$
Nu_{nat} = \begin{cases}
0.54 \cdot Ra^{1/4} & Ra < 10^7 \text{ (laminar)} \\
0.15 \cdot Ra^{1/3} & Ra > 10^7 \text{ (turbulent)}
\end{cases}
$$

#### Forced Convection

**Reynolds number:**

$$
Re = \frac{v L}{\nu}
$$

**Nusselt number:**

$$
Nu_{forced} = \begin{cases}
0.664 \cdot Re^{1/2} \cdot Pr^{1/3} & Re < 5 \times 10^5 \text{ (laminar)} \\
0.037 \cdot Re^{4/5} \cdot Pr^{1/3} & Re > 5 \times 10^5 \text{ (turbulent)}
\end{cases}
$$

#### Combined Convection (Churchill-Usagi Method)

$$
h_c = (h_{nat}^n + h_{forced}^n)^{1/n}, \quad n = 3
$$

### 4. Temperature-Weighted Average Emissivity

$$
\bar{\varepsilon}(T) = \frac{\int_{\lambda_1}^{\lambda_2} \varepsilon(\lambda) I_{BB}(\lambda, T) d\lambda}{\int_{\lambda_1}^{\lambda_2} I_{BB}(\lambda, T) d\lambda}
$$

---

## 🖥️ Computational Features

### Numerical Integration

| Method | Application | Accuracy |
|--------|-------------|----------|
| **Trapezoidal Rule** | Spectral integration | $O(\Delta\lambda^2)$ |
| **Brent's Method** | Root finding for equilibrium | Machine precision |
| **Linear Interpolation** | Spectral resampling | $O(\Delta\lambda)$ |
| **Minimize Scalar** | Optimization for solutions | Configurable tolerance |

### Integration Parameters

- **Angular Integration:** 100+ discrete points from 0° to 90°
- **Wavelength Integration:** User-defined spectral ranges with automatic interpolation
- **Convergence Criteria:** Iterative solving with $\Delta T < 0.01$ K

### Material Property Processing

- ✅ Automatic wavelength unit conversion (nm ↔ μm)
- ✅ Multi-encoding file support (UTF-8, GBK, GB2312)
- ✅ Spectral data validation and error handling
- ✅ Interpolation using `scipy.interpolate.interp1d`

---

## ⚙️ Installation

### System Requirements

```
Python >= 3.7
PyQt5 >= 5.15
numpy >= 1.19
scipy >= 1.5
pandas >= 1.1
matplotlib >= 3.3
openpyxl >= 3.0
```

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/yourusername/radiation-calculator.git
cd radiation-calculator

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Requirements File

Create `requirements.txt`:

```
PyQt5>=5.15.0
numpy>=1.19.0
scipy>=1.5.0
pandas>=1.1.0
matplotlib>=3.3.0
openpyxl>=3.0.0
configparser
pillow
```

---

## 📁 Required Data Files

All data files should be placed in the `default/` directory:

| File | Description | Format | Required Columns |
|------|-------------|--------|------------------|
| `config.ini` | Configuration parameters | INI | Multiple sections |
| `AM1.5.dll` | Standard solar spectrum (AM1.5G) | Excel | λ (μm), I (W/m²/μm) |
| `wavelength.csv` | Wavelength grid | CSV | λ (μm) |
| `reflectance.txt` | Material reflectance (0.3-2.5 μm) | TXT | λ (μm), R |
| `emissivity.txt` | Material emissivity (8-13 μm) | TXT | λ (μm), ε |
| `1.dll` | Atmospheric transmittance (clear) | Excel | λ (μm), τ |
| `2.dll` | Atmospheric transmittance (cloudy) | Excel | λ (μm), τ |

### Example Data Format

**reflectance.txt:**
```
0.3    0.95
0.4    0.94
0.5    0.93
...
2.5    0.90
```

**emissivity.txt:**
```
8.0    0.98
8.5    0.97
9.0    0.96
...
13.0   0.95
```

> **⚠️ Important:** Data files must contain only numerical values (no headers, no text). Use tab or space as delimiter.

---

## 🎯 Usage Guide

### 1. Basic Cooling Power Calculation

```python
# GUI Workflow:
1. Launch application: python main.py
2. Select reflectance file (visible to near-IR)
3. Select emissivity file (mid-IR atmospheric window)
4. Choose atmospheric conditions (1.dll or 2.dll)
5. Click "Radiation Cooling Power"
6. View results and export data
```

**Expected Output:**
- Cooling Power: `XXX.XX W/m²` at ambient temperature
- Solar Absorptance: `α_s`
- Average Emissivity: `ε_avg`
- Interactive plot: Cooling Power vs. ΔT

### 2. Energy Map Generation

```python
# For geographical energy modeling:
1. Prepare material property files
2. Click "Energy Map Calculation"
3. Obtain:
   - Material weighted emissivity (ε_8-13μm)
   - Solar spectral reflectance (R_0.3-2.5μm)
   - Visible spectral reflectance (R_0.4-0.7μm)
4. Use parameters in regional climate models
```

### 3. Wind Speed Analysis

```python
# Generate 2D parametric maps:
1. Load all required material files
2. Select "Wind Speed & Cooling Efficiency"
3. Input solar irradiance (e.g., 1000 W/m²)
4. View contour maps:
   - X-axis: Wind speed (0-5 m/s)
   - Y-axis: Atmospheric emissivity (0-1)
   - Color: Temperature difference or cooling power
```

### 4. Atmospheric Emissivity-Solar Irradiance Cloud

```python
# Comprehensive parametric study:
1. Click "Atmospheric Emissivity-Solar Irradiance Cloud"
2. Software generates 2D map:
   - X-axis: Atmospheric emissivity (0-1)
   - Y-axis: Solar irradiance (0-1000 W/m²)
   - Color: Net cooling power at ΔT=0
3. Export data to Excel with two sheets
```

---

## 📊 Output Parameters

### Calculated Values

| Parameter | Unit | Description |
|-----------|------|-------------|
| **P_cool** | W/m² | Net radiative cooling power at T_film = T_amb |
| **P_heat** | W/m² | Net radiative heating power |
| **α_solar** | - | Solar-weighted absorptance (0.3-2.5 μm) |
| **ε_avg** | - | Temperature-weighted emissivity (8-13 μm) |
| **R_sol** | - | Solar-weighted reflectance |
| **R_vis** | - | Visible-weighted reflectance (0.4-0.7 μm) |
| **h_c** | W/m²·K | Convection coefficient |

### Visualization Outputs

- 📈 **Line plots:** Cooling/heating power vs. temperature difference
- 🗺️ **Contour maps:** 2D parametric surfaces
- 📊 **Excel exports:** Tabulated data for further analysis
- 🎨 **Customizable plots:** Publication-quality figures

---

## 🔧 Advanced Features

### Configuration Editor

Edit calculation parameters through the GUI:

```ini
[PHYSICAL_CONSTANTS]
H = 6.62607015e-34      # Planck's constant (J·s)
C = 2.99792458e8        # Speed of light (m/s)
KB = 1.380649e-23       # Boltzmann constant (J/K)

[CALCULATIONS]
T_a1 = 25.0             # Ambient temperature (°C)
T_filmmin = -100.0      # Min film temperature (°C)
T_filmmax = 100.0       # Max film temperature (°C)
S_solar = 1000          # Solar irradiance (W/m²)
HC_VALUES = 5, 10, 15   # Convection coefficients (W/m²·K)
WAVELENGTH_RANGE = 0.3, 2.5    # Solar spectrum (μm)
VISIABLE_RANGE = 0.4, 0.7      # Visible spectrum (μm)
```

### File Converter Tool

Convert Excel files to TXT format:
- Automatically extracts first two columns
- Handles multiple encodings
- Validates data structure

### Multi-language Interface

Switch between Chinese and English:
- Real-time language switching
- All dialogs and messages translated
- Formulas remain in standard notation

---

## 📈 Validation & Accuracy

### Key Considerations

✅ **Spectral Resolution:** Higher resolution improves accuracy (recommend Δλ < 0.1 μm)

✅ **Angular Integration:** 100+ points ensure convergence (tested error < 0.5%)

✅ **Temperature Range:** Validated from -100°C to +100°C

✅ **Wavelength Coverage:** Critical ranges: Solar (0.3-2.5 μm), IR (8-13 μm)

### Assumptions & Limitations

⚠️ **Diffuse Surface:** Assumes Lambertian emission/reflection

⚠️ **Steady State:** Transient effects not included

⚠️ **1D Heat Transfer:** Edge effects neglected

⚠️ **Standard Atmosphere:** Uses MODTRAN-based profiles



---

## 🛠️ Troubleshooting

### Common Issues

**Problem:** "Cannot read file with any encoding"
```bash
Solution: Ensure file contains only numbers, no headers or text
Convert file to UTF-8 encoding: iconv -f GBK -t UTF-8 input.txt > output.txt
```

**Problem:** "Configuration file missing section"
```bash
Solution: Restore default config.ini from repository
Check all required sections: GENERAL, PHYSICAL_CONSTANTS, CALCULATIONS
```

**Problem:** Calculation results seem incorrect
```bash
Solution: 
1. Verify wavelength units (μm vs nm)
2. Check emissivity/reflectance ranges (0-1, not 0-100)
3. Ensure atmospheric transmittance file matches climate
4. Review temperature settings in config.ini
```

**Problem:** GUI doesn't display properly
```bash
Solution:
pip install --upgrade PyQt5
# On Linux, may need: sudo apt-get install python3-pyqt5
```

---

## 📚 References

1. **Raman, A. P., et al.** "Passive radiative cooling below ambient air temperature under direct sunlight." *Nature* 515.7528 (2014): 540-544. [DOI: 10.1038/nature13883](https://doi.org/10.1038/nature13883)

2. **Zhao, Dongliang, et al.** "Radiative sky cooling: Fundamental principles, materials, and applications." *Applied Physics Reviews* 6.2 (2019): 021306. [DOI: 10.1063/1.5087281](https://doi.org/10.1063/1.5087281)

3. **Zhai, Yao, et al.** "Scalable-manufactured randomized glass-polymer hybrid metamaterial for daytime radiative cooling." *Science* 355.6329 (2017): 1062-1066.

4. **Incropera, F. P., et al.** *Fundamentals of Heat and Mass Transfer*. 7th ed. Wiley, 2011.

5. **Bergman, T. L., et al.** *Introduction to Heat Transfer*. 6th ed. Wiley, 2011.

6. **Siegel, R., and J. R. Howell.** *Thermal Radiation Heat Transfer*. 5th ed. CRC Press, 2010.

7. **Modest, M. F.** *Radiative Heat Transfer*. 3rd ed. Academic Press, 2013.

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Add docstrings to all functions
- Include unit tests for new features
- Update documentation for API changes

---

## 📬 Contact & Support

**Author:** CTY  
**QQ Group:** 767753318  
**WeChat:** cuity_  
**Email:** Contact via QQ group  
**Repository:** [Gitee](https://gitee.com/cuity1999/Radiation-cooling-and-heating-calculation)

### Citation

If you use this software in your research, please cite:

```bibtex
NO INFORMATION
```

### Support the Project

⭐ Star this repository if you find it useful!  
🐛 Report bugs via [Issues](https://github.com/yourusername/radiation-calculator/issues)  
💡 Suggest features or improvements  
📖 Improve documentation

---

## 📄 License

This software is provided **free for academic and research purposes**. 

**Restrictions:**
- Commercial use requires explicit permission from the author
- Redistribution must include original attribution
- Modifications must be clearly documented

**Disclaimer:** This software is provided "as is" without warranty of any kind. The author is not liable for any damages arising from its use.

---

## 🎓 Educational Resources

### Recommended Reading

- **Radiative Cooling Fundamentals:** Start with Zhao et al. (2019) review paper
- **Heat Transfer Theory:** Chapters on radiation in Incropera & DeWitt
- **Atmospheric Physics:** MODTRAN atmospheric profiles and transmission
- **Material Science:** Spectral selectivity and metamaterials

### Tutorial Series

Coming soon: Video tutorials covering:
1. Basic setup and first calculation
2. Understanding spectral data requirements
3. Advanced parametric studies
4. Interpreting results for real applications

---

## 🔄 Version History

### Version 3.5 (Current)
- ✨ Added atmospheric emissivity-solar irradiance cloud map
- 🐛 Fixed convection coefficient calculation for mixed regime
- 🌐 Improved multi-language support
- 📊 Enhanced data export with Excel multi-sheet support
- ⚡ Performance optimization for large spectral datasets

### Version 3.0
- Added wind speed analysis with Churchill-Usagi correlation
- Implemented configuration editor
- Multi-language interface (Chinese/English)

### Version 2.0
- Added heating power calculation
- Improved spectral integration accuracy
- GUI redesign with modern aesthetics

### Version 1.0
- Initial release with basic cooling power calculation

---

## 🌟 Acknowledgments

Special thanks to:
- The thermal radiation research community
- PyQt5 and Python scientific computing ecosystem
- Contributors and users providing feedback
- Research groups sharing spectral data

---

<div align="center">

**Made with ❤️ for the thermal sciences community**

[⬆ Back to Top](#-radiative-coolingheating-calculator)

</div>
