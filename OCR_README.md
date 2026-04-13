# OCR截图翻译 安装说明

## 功能介绍

现在 Click Translator 支持 **截图+OCR识别** 翻译了！

适用场景：
- 图片中的文字
- PDF扫描件
- 某些软件UI中的文字（选不中的）
- 视频字幕
- 游戏内文字

## 安装步骤

### 方法一：一键安装（推荐）

双击运行 `install_ocr.bat`，按提示完成安装。

### 方法二：手动安装

1. **安装Python库**
   ```bash
   pip install pytesseract Pillow
   ```

2. **下载并安装Tesseract-OCR**
   - 下载地址：https://github.com/UB-Mannheim/tesseract/releases
   - 下载 `tesseract-ocr-w64-setup-xxx.exe`
   - 双击安装，记住安装路径（默认：`C:\Program Files\Tesseract-OCR`）

3. **配置环境变量（可选）**
   如果Tesseract没装到默认路径，修改 `translator.py` 开头：
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'你的安装路径\tesseract.exe'
   ```

## 使用方法

1. 启动 Click Translator
2. 点击「开始监听」
3. **如果文字能选中**：正常选中 → 双击翻译
4. **如果文字选不中**：直接在文字上双击，软件会自动截图识别并翻译

## 注意事项

- OCR识别需要一定时间，可能会比选中文本稍慢
- 截图区域是鼠标周围 150x150 像素的正方形
- 英文识别最准确，中文需要安装中文语言包
- 如果识别不准确，可以调整截图区域大小（在代码中修改 `size` 参数）
