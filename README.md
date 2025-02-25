# 辐射制冷与加热功率计算

> **ATTENTION**  
> This software only supports Simplified Chinese

## 下载链接

- **懒得看版本**：下载链接如下  
  （快速通道, 密码 `1234`）：[https://wwja.lanzoue.com/b0knk1xve](https://wwja.lanzoue.com/b0knk1xve)

- **魔法通道**：  
  [GitHub Releases](https://github.com/cuity1/Radiation-cooling-and-heating-calculation/releases/tag/releases)

- **QQ群交流**：  

[点击链接加入群聊【辐射制冷青椒交流群】](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=jFVhTIuH2_MxUv8UH6NkoMeV3pXX4eJg&authKey=Zv0lhgtkheyCAD5b2LmHRef2vxcqkFdoJY5rHxxs93oSSANdwxbezu%2BGOXOqiLfO&noverify=0&group_code=767753318)

> **温馨提示**  
> 源代码写的很烂，已经上传，最好别让我发现有倒狗，不然不再更新优化

---

## 项目简介

本项目主要用于计算辐射制冷与加热功率，核心包括两个主函数：
- `main_cooling_gui`：计算辐射冷却功率
- `main_heating_gui`：计算辐射加热功率

下面以 `main_cooling_gui` 为例，详细解释其计算逻辑，其它部分逻辑类似。

---

## 代码执行逻辑

- **外层循环**: 遍历所有对流换热系数 `H_conv`。
- **内层循环**: 遍历所有薄膜温度 `T_s_current`。
- **计算步骤**:
  1. **计算大气和薄膜的黑体辐射率**  
     使用普朗克定律计算不同波长和温度下的黑体辐射功率密度，并处理指数溢出问题。
  2. **计算波长间隔**  
     计算波长步长 `dlam1` 和 `dlam2`，用于数值积分。
  3. **计算薄膜的辐射功率密度**  
     结合发射率 `e_smat` 和波长间隔，计算辐射功率密度 `tempint_R3`，再对波长和角度进行积分得到总辐射功率 `p_r`。
  4. **计算大气的辐射功率密度**  
     结合大气发射率 `e_zmat` 和波长间隔，计算辐射功率密度 `tempint_R1`，积分后得到大气辐射功率 `p_a`。
  5. **计算对流换热功率**  
     使用牛顿冷却定律计算对流换热功率 `Q_conv`。
  6. **计算太阳辐照度功率**  
     计算太阳辐照度对材料的功率影响 `Q_solar`。
  7. **计算净辐射冷却功率**  
     综合各项功率，计算净冷却功率：
     \[
     P_{\text{net}} = P_r - P_a - Q_{\text{conv}} - Q_{\text{solar}}
     \]
  8. **存储结果**  
     将计算得到的净冷却功率存储在结果矩阵中。

---

## 详细代码说明

### 1. 函数入口与必要文件检查

```python
def main_cooling_gui(file_paths):
    """主程序逻辑"""
    # 检查必要文件是否已选择
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")
    ...
