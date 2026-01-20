# 打包说明

## 将应用程序打包为单个 exe 文件

### 方法一：使用批处理脚本（推荐）

直接双击运行 `build_exe.bat` 文件，脚本会自动：
1. 检查并安装 PyInstaller（如果未安装）
2. 执行打包命令
3. 生成单个 exe 文件

### 方法二：使用 PowerShell 脚本

在 PowerShell 中运行：
```powershell
.\build_exe.ps1
```

### 方法三：手动打包

1. 确保已安装 PyInstaller：
   ```bash
   pip install pyinstaller
   ```

2. 执行打包命令：
   ```bash
   pyinstaller RadiationCalc.spec --clean
   ```

3. 打包完成后，exe 文件位于 `dist\RadiationCalc.exe`

### 打包配置说明

`RadiationCalc.spec` 文件包含了打包配置：
- **单文件模式**：生成单个 exe 文件（onefile）
- **无控制台窗口**：GUI 应用程序，不显示控制台
- **包含资源文件**：自动包含 `default` 目录下的所有文件
- **隐藏导入**：包含所有必要的 Python 模块和依赖

### 注意事项

1. 首次打包可能需要较长时间，因为需要收集所有依赖
2. 生成的 exe 文件可能较大（通常 50-200MB），因为包含了 Python 解释器和所有依赖
3. 如果遇到缺少模块的错误，可以在 `RadiationCalc.spec` 的 `hiddenimports` 列表中添加
4. 打包后的 exe 文件可以独立运行，不需要安装 Python

### 常见问题

**Q: 打包时提示缺少某个模块**
A: 在 `RadiationCalc.spec` 的 `hiddenimports` 列表中添加该模块名称

**Q: exe 文件太大**
A: 这是正常的，因为包含了 Python 解释器和所有依赖。可以使用 UPX 压缩（已在配置中启用）

**Q: 运行时找不到资源文件**
A: 确保 `default` 目录下的所有文件都已包含在 `datas` 列表中

