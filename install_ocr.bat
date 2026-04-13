@echo off
chcp 65001 >nul
echo ==========================================
echo   Click Translator - OCR组件安装
echo ==========================================
echo.

echo [1/3] 安装Python OCR库...
pip install pytesseract Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [2/3] 下载Tesseract-OCR引擎...
echo 正在从GitHub下载，请稍候...
curl -L -o "%TEMP%\tesseract_installer.exe" "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"

echo.
echo [3/3] 运行Tesseract安装程序...
echo 请按提示完成安装，建议安装到默认路径
echo.
start /wait "" "%TEMP%\tesseract_installer.exe"

echo.
echo ==========================================
echo 安装完成！
echo 请重启 Click Translator 软件
echo ==========================================
pause
