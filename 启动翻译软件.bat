@echo off
chcp 65001 >nul
echo 正在启动 Click Translator...
cd /d "%~dp0"
python translator.py
if errorlevel 1 (
    echo.
    echo 启动失败，请检查依赖是否安装完整:
    echo pip install -r requirements.txt
    pause
)
