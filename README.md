# 辐射制冷与加热功率计算


> **写在前面**  
> V3.1版本修复了筛选机制
> V3.5版本对数据选取进行了识别，不会出现编码报错了，使用更多的积分点，获得更加准确的冷却功率（相对于之前变动在1%之内，旧版本没有必要重新计算）
> 下一步将会纳入更多的大气数据，我希望大家能够向我提供当地的大气透过率数据。



> **ATTENTION**  
> This software supports English now


## 下载链接

- **懒得看版本**：下载链接如下  
链接: https://pan.baidu.com/s/1RwgC-En28zfwQtf9DOfw9A?pwd=USTC 提取码: USTC 
--来自百度网盘超级会员v5的分享

- **魔法通道**：  
[  [GitHub Releases](https://github.com/cuity1/Radiation-cooling-and-heating-calculation/releases/tag/releases)](https://github.com/cuity1/Radiation-cooling-and-heating-calculation/releases)

- **QQ群交流**：  

[点击链接加入群聊【辐射制冷青椒交流群】](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=jFVhTIuH2_MxUv8UH6NkoMeV3pXX4eJg&authKey=Zv0lhgtkheyCAD5b2LmHRef2vxcqkFdoJY5rHxxs93oSSANdwxbezu%2BGOXOqiLfO&noverify=0&group_code=767753318)

> **温馨提示**  
> 源代码写的很烂，已经上传，最好别让我发现有倒狗，不然不再更新优化

---

## 项目简介

本项目主要用于计算辐射制冷与加热功率，核心包括两个主函数：
- `main_cooling_gui`：计算辐射冷却功率
- `main_heating_gui`：计算辐射加热功率
# 辐射制冷/制热计算工具使用说明书
# Radiative Cooling/Heating Tool User Manual

## 目录 (Contents)

1. [概述 (Overview)](#概述-overview)
2. [安装 (Installation)](#安装-installation)
3. [主界面介绍 (Main Interface)](#主界面介绍-main-interface)
4. [文件选择 (File Selection)](#文件选择-file-selection)
5. [功能模块 (Function Modules)](#功能模块-function-modules)
   - [节能地图绘制计算 (Energy Saving Map)](#节能地图绘制计算-energy-saving-map)
   - [辐射制冷功率计算 (Cooling Power Calculation)](#辐射制冷功率计算-cooling-power-calculation)
   - [辐射制热功率计算 (Heating Power Calculation)](#辐射制热功率计算-heating-power-calculation)
   - [风速与制冷效率云图 (Wind Speed vs. Cooling Efficiency Cloud Map)](#风速与制冷效率云图-wind-speed-vs-cooling-efficiency-cloud-map)
   - [参数修改 (Parameter Modification)](#参数修改-parameter-modification)
   - [光热转化效率计算 (Photothermal Efficiency Calculation)](#光热转化效率计算-photothermal-efficiency-calculation)
6. [数据格式要求 (Data Format Requirements)](#数据格式要求-data-format-requirements)
7. [常见问题 (FAQ)](#常见问题-faq)
8. [技术支持 (Technical Support)](#技术支持-technical-support)

## 概述 (Overview)

辐射制冷/制热计算工具是一款专为材料科学和能源领域研究人员设计的软件。它提供了全面的辐射制冷与制热性能分析功能，帮助用户计算材料的太阳光谱反射率、红外发射率以及在不同环境条件下的制冷/制热性能。

The Radiative Cooling/Heating Tool is software designed for researchers in materials science and energy fields. It provides comprehensive analysis of radiative cooling and heating performance, helping users calculate solar spectral reflectance, infrared emissivity, and cooling/heating performance under different environmental conditions.

## 安装 (Installation)

本软件无需专门安装，可直接运行可执行文件启动。首次运行时，软件会自动创建必要的文件夹结构和默认配置文件。

This software does not require specialized installation and can be launched directly by running the executable file. Upon first launch, the software will automatically create the necessary folder structure and default configuration files.

### 系统要求 (System Requirements)

- 操作系统：Windows 7/8/10/11
- 内存：2GB 以上
- 硬盘空间：50MB 以上

- Operating System: Windows 7/8/10/11
- Memory: 2GB or higher
- Disk Space: 50MB or higher

## 主界面介绍 (Main Interface)

软件启动后将显示主界面，主界面分为以下几个部分：

1. **标题区域**：显示软件名称
2. **文件选择区域**：用于选择反射率、发射率和大气透过率数据文件
3. **功能区域**：提供各种计算和分析功能的按钮
4. **状态栏**：显示软件版权和联系信息

After launching the software, the main interface will be displayed, which is divided into the following sections:

1. **Title Area**: Displays the software name
2. **File Selection Area**: For selecting reflectance, emissivity, and atmospheric transmittance data files
3. **Function Area**: Provides buttons for various calculation and analysis functions
4. **Status Bar**: Displays software copyright and contact information

## 文件选择 (File Selection)

在使用任何功能前，您需要先选择相关数据文件：

Before using any function, you need to select the relevant data files:

### 选择反射率文件 (Select Reflectance File)

1. 点击"选择反射率文件"按钮
2. 在弹出的文件对话框中选择包含反射率数据的文本文件（.txt格式）
3. 文件格式要求：两列数据，第一列为波长（微米或纳米），第二列为反射率值（0-1之间或0-100%）

1. Click the "Select Reflectance File" button
2. Choose a text file containing reflectance data (.txt format) in the file dialog
3. File format requirements: two columns of data, the first column for wavelength (in micrometers or nanometers), the second column for reflectance values (between 0-1 or 0-100%)

### 选择发射率文件 (Select Emissivity File)

1. 点击"选择发射率文件"按钮
2. 在弹出的文件对话框中选择包含发射率数据的文本文件（.txt格式）
3. 文件格式要求：两列数据，第一列为波长（微米或纳米），第二列为发射率值（0-1之间或0-100%）

1. Click the "Select Emissivity File" button
2. Choose a text file containing emissivity data (.txt format) in the file dialog
3. File format requirements: two columns of data, the first column for wavelength (in micrometers or nanometers), the second column for emissivity values (between 0-1 or 0-100%)

### 选择大气透过率 (Select Atmospheric Transmittance)

1. 点击"选择大气透过率"按钮
2. 在弹出的对话框中，您可以选择不同的大气条件：
   - "晴朗"：适用于晴天条件下的大气透过率
   - "少云"：适用于有少量云层时的大气透过率

1. Click the "Select Atmospheric Transmittance" button
2. In the dialog that appears, you can choose different atmospheric conditions:
   - "Clear Sky": For atmospheric transmittance under clear sky conditions
   - "Few Clouds": For atmospheric transmittance with a small amount of cloud cover

## 功能模块 (Function Modules)

本软件提供了六种主要功能，在选择了所需文件后，您可以使用以下功能：

The software provides six main functions. After selecting the required files, you can use the following features:

### 节能地图绘制计算 (Energy Saving Map)

该功能用于计算材料的关键光学参数，为绘制节能地图提供数据。

This function is used to calculate the key optical parameters of the material, providing data for energy saving map generation.

**操作步骤 (Operation Steps):**
1. 点击"节能地图绘制计算"按钮
2. 软件将自动计算以下参数：
   - 材料加权发射率
   - 太阳光谱反射率
   - 可见光谱反射率
3. 计算结果将显示在界面上

1. Click the "Energy Saving Map" button
2. The software will automatically calculate the following parameters:
   - Material weighted emissivity
   - Solar spectral reflectance
   - Visible spectral reflectance
3. The calculation results will be displayed on the interface

### 辐射制冷功率计算 (Cooling Power Calculation)

该功能用于计算材料在特定环境条件下的辐射制冷功率。

This function is used to calculate the radiative cooling power of the material under specific environmental conditions.

**操作步骤 (Operation Steps):**
1. 点击"辐射制冷功率计算"按钮
2. 软件将进行复杂的计算，可能需要几分钟时间
3. 计算完成后，将显示冷却功率结果
4. 您可以选择：
   - 预览冷却功率曲线：显示不同温差下的冷却功率变化
   - 导出数据到CSV：将计算结果保存为CSV文件，以便进一步分析

1. Click the "Cooling Power Calculation" button
2. The software will perform complex calculations, which may take several minutes
3. After calculation, the cooling power result will be displayed
4. You can choose to:
   - Preview the cooling power curve: Shows cooling power changes at different temperature differences
   - Export data to CSV: Save calculation results as a CSV file for further analysis

### 辐射制热功率计算 (Heating Power Calculation)

该功能用于计算材料在特定环境条件下的辐射制热功率。

This function is used to calculate the radiative heating power of the material under specific environmental conditions.

**操作步骤 (Operation Steps):**
1. 点击"辐射制热功率计算"按钮
2. 软件将进行复杂的计算，可能需要几分钟时间
3. 计算完成后，将显示加热功率结果
4. 您可以选择：
   - 绘制制热功率曲线：显示不同温差下的制热功率变化
   - 导出数据到CSV：将计算结果保存为CSV文件，以便进一步分析

1. Click the "Heating Power Calculation" button
2. The software will perform complex calculations, which may take several minutes
3. After calculation, the heating power result will be displayed
4. You can choose to:
   - Plot the heating power curve: Shows heating power changes at different temperature differences
   - Export data to CSV: Save calculation results as a CSV file for further analysis

### 风速与制冷效率云图 (Wind Speed vs. Cooling Efficiency Cloud Map)

该功能用于分析风速对制冷效率的影响，并生成可视化云图。
对于外部流动的对流换热，通常有以下情况：

自然对流（无风或风速很小时）：

对于垂直平板：Nu = 0.59 * Ra^0.25 (层流) 或 Nu = 0.1 * Ra^0.33 (湍流)
对于水平平板：Nu = 0.54 * Ra^0.25 (层流) 或 Nu = 0.15 * Ra^0.33 (湍流)
强制对流（有风时）
对于平板：Nu = 0.664 * Re^0.5 * Pr^0.33 (层流) 或 Nu = 0.037 * Re^0.8 * Pr^0.33 (湍流)
混合对流：
当自然对流和强制对流都存在时，通常使用：h_total = sqrt(h_natural^n + h_forced^n)，其中n通常取3或4

*所用到的公式：*
层流强制对流：Nu = 0.664 × Re^0.5 × Pr^0.33
湍流强制对流：Nu = 0.037 × Re^0.8 × Pr^0.33
自然对流：Nu = 0.54 × Ra^0.25 (层流) 或 0.15 × Ra^0.33 (湍流)
混合对流：h_total = (h_natural³ + h_forced³)^(1/3)

This function is used to analyze the impact of wind speed on cooling efficiency and generate a visualization cloud map.

**操作步骤 (Operation Steps):**
1. 点击"风速与制冷效率云图"按钮
2. 在弹出的对话框中输入太阳辐照度参数（单位：W/m²）
3. 点击"生成云图"按钮
4. 软件将计算并显示风速与大气发射率对温差的影响的云图
5. 计算完成后，您可以保存结果数据到CSV文件

1. Click the "Wind Speed vs. Cooling Efficiency Cloud Map" button
2. Enter the solar irradiance parameter (unit: W/m²) in the dialog box
3. Click the "Generate Cloud Map" button
4. The software will calculate and display a cloud map showing the influence of wind speed and atmospheric emissivity on temperature difference
5. After calculation, you can save the result data to a CSV file

### 参数修改 (Parameter Modification)

该功能允许用户修改软件的配置参数。

This function allows users to modify the configuration parameters of the software.

**操作步骤 (Operation Steps):**
1. 点击"参数修改"按钮
2. 在弹出的对话框中，您可以修改各种参数，如：
   - 波长范围
   - 物理常数
   - 环境温度
   - 其他计算参数
3. 修改完成后，点击"保存"按钮应用更改

1. Click the "Parameter Modification" button
2. In the dialog box, you can modify various parameters, such as:
   - Wavelength range
   - Physical constants
   - Ambient temperature
   - Other calculation parameters
3. After modification, click the "Save" button to apply the changes

### 光热转化效率计算 (Photothermal Efficiency Calculation)

该功能用于计算材料在不同环境温度下的光热转化效率与太阳辐照度的关系。

This function is used to calculate the relationship between photothermal conversion efficiency and solar irradiance at different ambient temperatures.

**操作步骤 (Operation Steps):**
1. 点击"光热转化效率计算"按钮
2. 软件将自动计算在环境温度从-100°C到100°C范围内，材料的理论辐射制热功率与太阳辐照度之间的关系
3. 计算完成后，将显示关系曲线图
4. 您可以选择保存结果数据到CSV文件

1. Click the "Photothermal Efficiency Calculation" button
2. The software will automatically calculate the relationship between theoretical radiative heating power and solar irradiance in the ambient temperature range from -100°C to 100°C
3. After calculation, the relationship curve will be displayed
4. You can choose to save the result data to a CSV file

## 数据格式要求 (Data Format Requirements)

为确保软件正常工作，您的数据文件需要满足以下格式要求：

To ensure the software works properly, your data files need to meet the following format requirements:

### 反射率文件 (Reflectance File)
- 纯文本格式（.txt）
- 两列数据：波长和反射率
- 波长单位可以是微米或纳米（软件会自动识别并转换）
- 反射率值可以是0-1之间或0-100%（软件会自动识别并转换）
- 不含标题行或其他文字说明

- Plain text format (.txt)
- Two columns of data: wavelength and reflectance
- Wavelength unit can be in micrometers or nanometers (software will automatically recognize and convert)
- Reflectance values can be between 0-1 or 0-100% (software will automatically recognize and convert)
- No header row or other text descriptions

### 发射率文件 (Emissivity File)
- 纯文本格式（.txt）
- 两列数据：波长和发射率
- 波长单位可以是微米或纳米（软件会自动识别并转换）
- 发射率值可以是0-1之间或0-100%（软件会自动识别并转换）
- 不含标题行或其他文字说明

- Plain text format (.txt)
- Two columns of data: wavelength and emissivity
- Wavelength unit can be in micrometers or nanometers (software will automatically recognize and convert)
- Emissivity values can be between 0-1 or 0-100% (software will automatically recognize and convert)
- No header row or other text descriptions

### 数据示例 (Data Examples)

**反射率文件示例 (Reflectance File Example):**
```
0.3 0.85
0.4 0.87
0.5 0.89
0.6 0.90
0.7 0.92
...
```

**发射率文件示例 (Emissivity File Example):**
```
5.0 0.90
6.0 0.91
7.0 0.92
8.0 0.93
9.0 0.95
...
```

## 常见问题 (FAQ)

### 1. 软件显示"未选择文件"错误怎么办？
确保您已经选择了所有必需的文件：反射率文件、发射率文件和大气透过率。每个按钮下方的状态文本应该显示"已选择文件"而不是"未选择"。

### 1. What should I do if the software shows a "File not selected" error?
Make sure you have selected all the required files: reflectance file, emissivity file, and atmospheric transmittance. The status text under each button should display "Selected" instead of "Not selected".

### 2. 计算结果为什么显示异常值？
请检查您的数据文件格式是否正确。确保文件中只包含数值数据，没有标题行或文字说明。另外，检查数值范围是否合理，比如反射率和发射率应在0-1之间或0-100%之间。

### 2. Why does the calculation result show abnormal values?
Please check if your data file format is correct. Make sure the file contains only numerical data, without header rows or text descriptions. Also, check if the value range is reasonable, for example, reflectance and emissivity should be between 0-1 or 0-100%.

### 3. 如何调整环境温度等参数？
使用"参数修改"功能，您可以调整环境温度、波长范围和其他计算参数。

### 3. How to adjust parameters such as ambient temperature?
Use the "Parameter Modification" function, you can adjust ambient temperature, wavelength range, and other calculation parameters.

### 4. 软件计算速度较慢怎么办？
辐射计算涉及复杂的物理模型和数值积分，因此某些功能（如制冷/制热功率计算）可能需要较长时间。请耐心等待计算完成。

### 4. What if the software calculates slowly?
Radiation calculations involve complex physical models and numerical integration, so some functions (such as cooling/heating power calculation) may take longer. Please wait patiently for the calculation to complete.

### 5. 如何解释风速与制冷效率云图？
云图中的颜色表示不同风速和大气发射率组合下的温差（ΔT）。颜色越深的区域表示制冷效果越好。等值线标注了具体的温差值。

### 5. How to interpret the Wind Speed vs. Cooling Efficiency Cloud Map?
The colors in the cloud map represent the temperature difference (ΔT) under different combinations of wind speed and atmospheric emissivity. Darker colored areas indicate better cooling effects. Contour lines mark specific temperature difference values.

### 6. 我该如何修改指定大气窗口波段？
可以通过修改wavelength.csv，更改大气窗口波段从而更改需要拟合的大气透过率和样品发射率。

## 技术支持 (Technical Support)

如果您在使用过程中遇到任何问题，或有任何建议，请联系软件开发者：

If you encounter any problems during use, or have any suggestions, please contact the software developer:

邮箱：config.ini文件中EMAIL_CONTACT字段指定的邮箱地址

Email: The email address specified in the EMAIL_CONTACT field of the config.ini file

**备注：该软件为免费分享软件，如果使用此工具进行研究，希望能够引用开发者的相关文章。**
https://pubs.acs.org/doi/10.1021/acs.nanolett.4c03139
**Note: This software is shared for free. If you use this tool for research, please cite the developer's relevant articles.**
