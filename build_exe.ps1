# PowerShell 打包脚本
Write-Host "正在打包应用程序为单个 exe 文件..." -ForegroundColor Green
Write-Host ""

# 检查 PyInstaller 是否已安装
try {
    python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller not found"
    }
} catch {
    Write-Host "未找到 PyInstaller，正在安装..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "安装 PyInstaller 失败，请手动运行: pip install pyinstaller" -ForegroundColor Red
        Read-Host "按 Enter 键退出"
        exit 1
    }
}

Write-Host "开始打包..." -ForegroundColor Green
pyinstaller RadiationCalc.spec --clean

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "打包成功！" -ForegroundColor Green
    Write-Host "exe 文件位置: dist\RadiationCalc.exe" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "打包失败！" -ForegroundColor Red
}

Write-Host ""
Read-Host "按 Enter 键退出"

