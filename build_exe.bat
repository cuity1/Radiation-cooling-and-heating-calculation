@echo off
chcp 65001 >nul
echo 正在打包应用程序为单个 exe 文件...
echo.

REM 检查 PyInstaller 是否已安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo 错误: 未找到 PyInstaller，正在安装...
    pip install pyinstaller
    if errorlevel 1 (
        echo 安装 PyInstaller 失败，请手动运行: pip install pyinstaller
        pause
        exit /b 1
    )
)

echo 开始打包...

REM 始终使用当前虚拟环境的 python 来运行 PyInstaller，避免 pyinstaller.exe launcher 因路径/环境异常无法创建进程
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m PyInstaller RadiationCalc.spec --clean

if errorlevel 1 (
    echo.
    echo 打包失败！
    pause
    exit /b 1
) else (
    echo.
    echo 打包成功！
    echo exe 文件位置: dist\RadiationCalc.exe
    echo.
    pause
)

