@echo off
chcp 65001 >nul
title Click Translator 打包工具
echo.
echo ========================================
echo   Click Translator 打包工具
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python
    pause
    exit /b 1
)

echo [OK] Python 已安装
echo.
echo 正在安装打包工具 pyinstaller...
python -m pip install pyinstaller -q

echo.
echo 开始打包...
python build_exe.py

echo.
echo ========================================
echo 打包完成！
echo ========================================
echo.
echo 输出文件: dist\ClickTranslator.exe
echo.
pause
