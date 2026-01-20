## 更新日志 Changelog

**版本：vX.Y.Z**  
**发布日期：2026-01-20**

---

## 更新内容（中文）

1. **添加自然对流换热项**  
   - 在换热模型中加入自然对流换热项，对于较大的温差会额外增加传热能力。  
   - 在界面中可通过勾选/取消勾选来启用或关闭该项。

2. **完成材料对比节能效果计算模块**  
   - 实现材料之间节能效果的对比计算功能。  
   - 支持生成用于绘制节能地图的数据文件，便于后续数据可视化与区域分析。

3. **添加版本公告逻辑**  
   - 新版本发布时，在软件底部区域展示版本更新公告。  
   - 方便用户快速了解当前版本的新特性与修复内容。

4. **提升计算精度**  
   - 优化数值算法与计算流程，减少数值误差。  
   - 提高仿真与计算结果的可靠性和稳定性。

5. **添加相变功能**  
   - 支持在特定温度点设置相变功率。  
   - 在材料达到相变点时自动考虑相变潜热对能量收支的影响。

6. **添加功率分量显示/输出功能**  
   - 新增功率分量拆分与输出功能，便于分析不同热量来源与去向。  
   - 该功能需从命令行（CMD）方式启动程序使用；默认图形界面模式下不显示控制台调试栏。

7. **其他小改进**  
   - 若干微小功能优化与体验改进。  
   - 修复部分边界条件与极端场景下的潜在问题。

---

## Updates (English)

1. **Added natural convection heat transfer term**  
   - Introduced a natural convection term into the heat transfer model, providing additional heat transfer when the temperature difference is large.  
   - This term can be enabled or disabled via a checkbox in the interface.

2. **Completed energy-saving comparison for materials**  
   - Implemented the calculation module for comparing the energy-saving performance of different materials.  
   - Supports generating data used for plotting energy-saving maps, enabling regional analysis and visualization.

3. **Added version announcement logic**  
   - When a new version is released, an announcement bar is shown at the bottom of the application.  
   - Helps users quickly understand what’s new and what has been fixed in the current release.

4. **Improved calculation accuracy**  
   - Optimized numerical algorithms and calculation procedures to reduce numerical errors.  
   - Enhances the reliability and stability of simulation and calculation results.

5. **Added phase-change functionality**  
   - Allows specifying phase-change power at a designated phase-change temperature.  
   - Automatically accounts for latent heat effects at the phase-change point in the energy balance.

6. **Added power component feature**  
   - New feature for decomposing and inspecting different power components.  
   - This feature requires starting the program from the command line (CMD); by default, the GUI mode does not show a console debug panel.

7. **Minor improvements and tweaks**  
   - Various small feature enhancements and UX improvements.  
   - Fixed some potential issues under specific boundary conditions and extreme scenarios.

