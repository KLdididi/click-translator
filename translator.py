"""
Click Translator - 点击即翻译桌面工具
支持：鼠标双击触发取词 / 右键菜单触发翻译 / 悬浮翻译结果窗口
"""

import sys
import os
import time
import threading
import ctypes
import pyautogui
from PIL import ImageGrab
import win32api
import win32con
import win32gui
import win32clipboard

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSystemTrayIcon, QMenu, QAction, QFrame,
    QSizeGrip, QComboBox, QCheckBox, QSlider, QSpinBox,
    QGroupBox, QScrollArea, QRubberBand
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QPoint, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtProperty, QSize
)
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QIcon, QPixmap, QPainter,
    QLinearGradient, QBrush, QPen, QCursor
)
from pynput import mouse, keyboard
import requests
import json
import urllib.parse
import html

# OCR支持 - 截图翻译
OCR_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    pass

# 截图选择区域支持
SCREENSHOT_AVAILABLE = False
try:
    from PIL import ImageDraw
    SCREENSHOT_AVAILABLE = True
except ImportError:
    pass

# ─────────────────────────────────────────────
# 翻译引擎
# ─────────────────────────────────────────────
class TranslatorEngine:
    """多引擎翻译 - 腾讯(免费) / 有道(免费) / Google(需VPN) / Bing(免费) / 百度(需Key)"""

    def __init__(self):
        self.engine = "tencent"  # tencent / youdao / google / bing / baidu
        self.target_lang = "zh-CN"
        self.baidu_appid = ""
        self.baidu_secret = ""

    def translate(self, text: str) -> dict:
        """返回 {text, from_lang, to_lang, engine, error}"""
        text = text.strip()
        if not text or len(text) > 2000:
            return {"error": "文本为空或过长"}
        last_err = ""
        for attempt in range(2):  # 最多重试1次
            try:
                if self.engine == "tencent":
                    return self._tencent(text)
                elif self.engine == "youdao":
                    return self._youdao(text)
                elif self.engine == "google":
                    return self._google(text)
                elif self.engine == "bing":
                    return self._bing(text)
                elif self.engine == "baidu":
                    return self._baidu(text)
            except requests.exceptions.ConnectionError:
                last_err = "网络连接失败，请检查网络"
                time.sleep(0.8)
            except requests.exceptions.Timeout:
                last_err = "翻译请求超时，请稍后重试"
                time.sleep(1.0)
            except Exception as e:
                err = str(e)
                # 提供友好提示
                if "401" in err or "403" in err:
                    last_err = "认证失败，翻译服务可能需要更新"
                elif "429" in err:
                    last_err = "请求过于频繁，请稍后再试"
                elif "ret_code" in err:
                    last_err = f"翻译接口错误: {err}"
                else:
                    last_err = f"翻译失败: {err}"
                break  # 非网络错误不重试
        return {"error": last_err}

    def _tencent(self, text: str) -> dict:
        """腾讯翻译（transmart，国内直连，完全免费，无需Key）"""
        lang_map = {
            "zh-CN": "zh", "zh-TW": "zh", "en": "en",
            "ja": "ja", "ko": "ko", "fr": "fr", "de": "de",
            "es": "es", "ru": "ru"
        }
        to_lang = lang_map.get(self.target_lang, "zh")
        url = "https://transmart.qq.com/api/imt"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Referer": "https://transmart.qq.com/"
        }
        payload = {
            "header": {
                "fn": "auto_translation",
                "client_key": "browser-chrome-120.0.0-Windows%2010-4E76C2B1"
            },
            "type": "plain",
            "model_category": "normal",
            "source": {"lang": "auto", "text_list": [text]},
            "target": {"lang": to_lang}
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if data.get("header", {}).get("ret_code") != "succ":
            raise Exception("腾讯翻译接口错误: " + str(data.get("header", {}).get("ret_code")))
        translated = "\n".join(data.get("auto_translation", []))
        from_lang = data.get("src_lang", "auto")
        return {
            "text": translated,
            "from_lang": from_lang,
            "to_lang": self.target_lang,
            "engine": "腾讯",
            "error": None
        }

    def _youdao(self, text: str) -> dict:
        """有道翻译非官方接口（国内直连，无需Key）"""
        import hashlib, time as _time, random
        ts = str(int(_time.time() * 1000))
        salt = ts + str(random.randint(0, 9))
        # 截取关键部分
        if len(text) > 20:
            key_str = text[:10] + str(len(text)) + text[-10:]
        else:
            key_str = text
        sign_str = "fanyideskweb" + key_str + salt + "Ygy_4c=r#e#4EX^NUGUc5"
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        # 语言代码映射
        lang_map = {
            "zh-CN": "zh-CHS", "zh-TW": "zh-CHT", "en": "en",
            "ja": "ja", "ko": "ko", "fr": "fr", "de": "de",
            "es": "es", "ru": "ru"
        }
        to_lang = lang_map.get(self.target_lang, "zh-CHS")
        url = "https://fanyi.youdao.com/translate_o"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://fanyi.youdao.com/",
            "Cookie": "OUTFOX_SEARCH_USER_ID_NCOO=1234567890;"
        }
        data = {
            "i": text, "from": "AUTO", "to": to_lang,
            "smartresult": "dict", "client": "fanyideskweb",
            "salt": salt, "sign": sign, "ts": ts, "bv": "",
            "doctype": "json", "version": "2.1",
            "keyfrom": "fanyi.web", "action": "FY_BY_REALTlME"
        }
        resp = requests.post(url, data=data, headers=headers, timeout=8)
        resp.raise_for_status()
        result_data = resp.json()
        if result_data.get("errorCode") != 0:
            raise Exception(f"有道翻译错误码: {result_data.get('errorCode')}")
        parts = []
        for item in result_data.get("translateResult", []):
            for r in item:
                parts.append(r.get("tgt", ""))
        translated = "\n".join(parts)
        return {
            "text": translated,
            "from_lang": "auto",
            "to_lang": self.target_lang,
            "engine": "有道",
            "error": None
        }

    def _google(self, text: str) -> dict:
        """使用 Google Translate 非官方接口"""
        encoded = urllib.parse.quote(text)
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=auto&tl={self.target_lang}"
            f"&dt=t&q={encoded}"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        # 拼接翻译结果
        result_parts = [item[0] for item in data[0] if item[0]]
        translated = "".join(result_parts)
        from_lang = data[2] if len(data) > 2 else "auto"
        return {
            "text": html.unescape(translated),
            "from_lang": from_lang,
            "to_lang": self.target_lang,
            "engine": "Google",
            "error": None
        }

    def _bing(self, text: str) -> dict:
        """使用 Bing Translate 非官方接口"""
        # 先获取 token
        token_url = "https://edge.microsoft.com/translate/auth"
        headers = {"User-Agent": "Mozilla/5.0"}
        token_resp = requests.get(token_url, headers=headers, timeout=5)
        token = token_resp.text.strip()

        url = "https://api.cognitive.microsofttranslator.com/translate"
        params = {"api-version": "3.0", "to": self.target_lang}
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        body = [{"Text": text}]
        resp = requests.post(url, params=params, headers=req_headers,
                             json=body, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        translated = data[0]["translations"][0]["text"]
        from_lang = data[0].get("detectedLanguage", {}).get("language", "auto")
        return {
            "text": translated,
            "from_lang": from_lang,
            "to_lang": self.target_lang,
            "engine": "Bing",
            "error": None
        }

    def _baidu(self, text: str) -> dict:
        import hashlib, random
        salt = str(random.randint(32768, 65536))
        sign_str = self.baidu_appid + text + salt + self.baidu_secret
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        # 语言代码映射
        lang_map = {"zh-CN": "zh", "en": "en", "ja": "jp", "ko": "kor",
                    "fr": "fra", "de": "de", "es": "spa", "ru": "ru"}
        tl = lang_map.get(self.target_lang, "zh")
        url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
        params = {
            "q": text, "from": "auto", "to": tl,
            "appid": self.baidu_appid, "salt": salt, "sign": sign
        }
        resp = requests.get(url, params=params, timeout=8)
        data = resp.json()
        if "error_code" in data:
            return {"error": f"百度翻译错误: {data.get('error_msg')}"}
        translated = "\n".join(r["dst"] for r in data["trans_result"])
        return {
            "text": translated,
            "from_lang": data["from"],
            "to_lang": data["to"],
            "engine": "百度",
            "error": None
        }


# ─────────────────────────────────────────────
# 取词模块 - 从光标位置获取文字
# ─────────────────────────────────────────────
class WordGrabber:
    """从鼠标位置取词：优先剪贴板选词，其次 OCR"""

    def get_word_at_cursor(self, x: int, y: int, use_ocr=False) -> str:
        """尝试通过模拟 Ctrl+C 获取选中文字（最多重试3次）"""
        old_clip = self._get_clipboard()
        for attempt in range(3):
            self._set_clipboard("")
            time.sleep(0.08)
            pyautogui.press('escape')
            time.sleep(0.05)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            new_clip = self._get_clipboard()
            if new_clip and new_clip.strip() and new_clip.strip() != old_clip:
                if old_clip:
                    self._set_clipboard(old_clip)
                return new_clip.strip()
        if old_clip:
            self._set_clipboard(old_clip)
        return ""

    def get_word_from_selection(self) -> str:
        """直接获取当前选中的文本"""
        old_clip = self._get_clipboard()
        for attempt in range(3):
            self._set_clipboard("")
            time.sleep(0.08)
            # 按 Escape 确保输入法不会干扰 Ctrl+C
            pyautogui.press('escape')
            time.sleep(0.05)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.2)
            text = self._get_clipboard()
            if text and text.strip() and text.strip() != old_clip:
                if old_clip:
                    self._set_clipboard(old_clip)
                return text.strip()
        if old_clip:
            self._set_clipboard(old_clip)
        return ""

    def _get_clipboard(self) -> str:
        data = ""
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        except Exception:
            pass
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
        return data if data else ""

    def _set_clipboard(self, text: str):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        except Exception:
            pass
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def get_text_from_screenshot(self, x: int, y: int, size: int = 300) -> str:
        """
        截图并OCR识别文字（fallback 模式：在光标附近截取区域识别）。
        注意：这是 Ctrl+C 取词失败时的备用方案，
        真正的截图翻译（F8）走 ScreenshotSelector 流程，不经过这里。
        """
        if not OCR_AVAILABLE:
            return ""
        try:
            from PIL import Image
            # 截图区域（鼠标周围，增大到 300px 提高命中率）
            left = max(0, x - size // 2)
            top = max(0, y - size // 2)
            screenshot = ImageGrab.grab(bbox=(left, top, left + size, top + size))
            # OCR识别，优先中文+英文混合
            text = pytesseract.image_to_string(screenshot, lang='eng+chi_sim')
            return text.strip()
        except Exception as e:
            print(f"OCR错误: {e}")
            return ""


# ─────────────────────────────────────────────
# 翻译工作线程
# ─────────────────────────────────────────────
class TranslateWorker(QThread):
    result_ready = pyqtSignal(dict, int, int)

    def __init__(self, engine: TranslatorEngine, text: str, x: int, y: int):
        super().__init__()
        self.engine = engine
        self.text = text
        self.x = x
        self.y = y

    def run(self):
        result = self.engine.translate(self.text)
        # 将原文注入结果字典，避免外部猴子补丁
        result["_original"] = self.text
        self.result_ready.emit(result, self.x, self.y)


# ─────────────────────────────────────────────
# 翻译结果浮动窗口
# ─────────────────────────────────────────────
class TranslationPopup(QWidget):
    STYLE = """
        QWidget#popup {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #1e1e2e, stop:1 #16213e);
            border: 1px solid #3d5a80;
            border-radius: 12px;
        }
        QLabel#original {
            color: #a8b2c8;
            font-size: 12px;
            padding: 4px 8px 0 8px;
        }
        QLabel#translated {
            color: #e2f0ff;
            font-size: 15px;
            font-weight: bold;
            padding: 4px 10px 8px 10px;
        }
        QLabel#meta {
            color: #5a7fa8;
            font-size: 10px;
            padding: 0 8px 4px 8px;
        }
        QPushButton#close_btn {
            background: transparent;
            color: #5a7fa8;
            border: none;
            font-size: 14px;
            padding: 2px 6px;
        }
        QPushButton#close_btn:hover {
            color: #e07070;
        }
        QPushButton#copy_btn {
            background: #3d5a80;
            color: #e2f0ff;
            border: none;
            border-radius: 6px;
            font-size: 11px;
            padding: 3px 10px;
            margin: 0 6px 6px 0;
        }
        QPushButton#copy_btn:hover {
            background: #507aad;
        }
        QFrame#divider {
            color: #2d3a5e;
            background: #2d3a5e;
            max-height: 1px;
        }
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("popup")
        # 移除 WA_TranslucentBackground（Windows Qt 下会导致事件异常）
        # 改用正常背景 + 圆角阴影实现透明效果
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.NoDropShadowWindowHint
        )
        self.setStyleSheet(self.STYLE + """
            #popup {
                background: transparent;
                border-radius: 12px;
            }
        """)
        self._drag_pos = None
        self._translated_text = ""
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(10, 6, 6, 2)
        self._engine_label = QLabel("🌐 翻译")
        self._engine_label.setObjectName("meta")
        self._engine_label.setFont(QFont("Segoe UI", 9))
        title_bar.addWidget(self._engine_label)
        title_bar.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.clicked.connect(self.hide)
        close_btn.setFixedSize(22, 22)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        # 分割线
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)

        # 原文
        self._original_label = QLabel()
        self._original_label.setObjectName("original")
        self._original_label.setWordWrap(True)
        self._original_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self._original_label)

        # 译文
        self._translated_label = QLabel()
        self._translated_label.setObjectName("translated")
        self._translated_label.setWordWrap(True)
        self._translated_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        layout.addWidget(self._translated_label)

        # 底部操作栏
        bottom = QHBoxLayout()
        bottom.setContentsMargins(8, 0, 8, 6)
        self._meta_label = QLabel()
        self._meta_label.setObjectName("meta")
        bottom.addWidget(self._meta_label)
        bottom.addStretch()
        copy_btn = QPushButton("📋 复制")
        copy_btn.setObjectName("copy_btn")
        copy_btn.clicked.connect(self._copy_result)
        bottom.addWidget(copy_btn)
        layout.addLayout(bottom)

        self.setMinimumWidth(260)
        self.setMaximumWidth(480)

    def show_result(self, original: str, result: dict, x: int, y: int):
        self._hide_timer.stop()
        self._translated_text = result.get("text", "")

        # 原文截断
        display_original = original[:80] + "..." if len(original) > 80 else original
        self._original_label.setText(display_original)

        if result.get("error"):
            self._translated_label.setText(f"⚠️ {result['error']}")
            self._translated_label.setStyleSheet("color: #e07070;")
        else:
            self._translated_label.setText(result.get("text", ""))
            self._translated_label.setStyleSheet("color: #e2f0ff;")

        engine = result.get("engine", "")
        from_lang = result.get("from_lang", "")
        to_lang = result.get("to_lang", "")
        self._engine_label.setText(f"🌐 {engine}")
        self._meta_label.setText(f"{from_lang} → {to_lang}")

        self.adjustSize()
        self._position_near(x, y)
        self.show()
        self.raise_()

        # 10秒自动隐藏
        self._hide_timer.start(10000)

    def show_loading(self, x: int, y: int):
        self._hide_timer.stop()
        self._original_label.setText("正在翻译...")
        self._translated_label.setText("⏳")
        self._translated_label.setStyleSheet("color: #a8b2c8;")
        self._engine_label.setText("🌐 翻译中")
        self._meta_label.setText("")
        self.adjustSize()
        self._position_near(x, y)
        self.show()
        self.raise_()

    def _position_near(self, x: int, y: int):
        screen = QApplication.primaryScreen().geometry()
        w, h = self.sizeHint().width(), self.sizeHint().height()
        # 默认在光标右下方
        px, py = x + 16, y + 16
        # 防止超出屏幕右边
        if px + w > screen.width():
            px = x - w - 10
        # 防止超出屏幕底部
        if py + h > screen.height():
            py = y - h - 10
        self.move(max(0, px), max(0, py))

    def _copy_result(self):
        if self._translated_text:
            QApplication.clipboard().setText(self._translated_text)
            # 短暂反馈
            old = self.findChild(QPushButton, "copy_btn")

    def _fade_out(self):
        self.hide()

    # 支持拖拽移动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            self._hide_timer.stop()  # 拖拽时暂停自动隐藏

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        # 透明背景方案：半透明深色渐变 + 边框
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(30, 30, 46, 240))
        gradient.setColorAt(1, QColor(22, 33, 62, 240))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor("#3d5a80"), 1))
        painter.drawRoundedRect(rect, 12, 12)


# ─────────────────────────────────────────────
# 全局鼠标监听线程
# ─────────────────────────────────────────────
class MouseListenerThread(QThread):
    """监听全局鼠标事件，双击或快捷键触发翻译"""
    translate_request = pyqtSignal(int, int)  # x, y
    screenshot_request = pyqtSignal()  # 截图翻译请求

    def __init__(self, mode="double_click"):
        super().__init__()
        self.mode = mode  # "double_click" | "ctrl_click" | "alt_click" | "screenshot_hotkey"
        self._last_click_time = 0
        self._last_click_pos = (0, 0)
        self._active = True
        self._ctrl_pressed = False
        self._alt_pressed = False
        self._shift_pressed = False
        self._f8_pressed = False
        self._listener = None
        self._kb_listener = None

    def run(self):
        def on_click(x, y, button, pressed):
            if not self._active:
                return
            if button == mouse.Button.left and pressed:
                now = time.time()
                if self.mode == "double_click":
                    # 双击检测：300ms内在相近位置点击两次
                    lx, ly = self._last_click_pos
                    dist = ((x - lx)**2 + (y - ly)**2) ** 0.5
                    if now - self._last_click_time < 0.5 and dist < 30:
                        self.translate_request.emit(x, y)
                        self._last_click_time = 0
                        return
                    self._last_click_time = now
                    self._last_click_pos = (x, y)
                elif self.mode == "ctrl_click" and self._ctrl_pressed:
                    self.translate_request.emit(x, y)
                elif self.mode == "alt_click" and self._alt_pressed:
                    self.translate_request.emit(x, y)

        def on_key_press(key):
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                self._ctrl_pressed = True
            elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                self._alt_pressed = True
            elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                self._shift_pressed = True
            elif key == keyboard.Key.f8:
                self._f8_pressed = True
                # F8 触发截图翻译
                self.screenshot_request.emit()

        def on_key_release(key):
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                self._ctrl_pressed = False
            elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                self._alt_pressed = False
            elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                self._shift_pressed = False
            elif key == keyboard.Key.f8:
                self._f8_pressed = False

        self._kb_listener = keyboard.Listener(
            on_press=on_key_press, on_release=on_key_release)
        self._kb_listener.start()

        with mouse.Listener(on_click=on_click) as self._listener:
            self._listener.join()

    def stop(self):
        self._active = False
        if self._listener:
            self._listener.stop()
        if self._kb_listener:
            self._kb_listener.stop()

    def set_mode(self, mode: str):
        self.mode = mode


# ─────────────────────────────────────────────
# 设置面板
# ─────────────────────────────────────────────
class SettingsPanel(QWidget):
    settings_changed = pyqtSignal(dict)

    STYLE = """
        QWidget {
            background: #1a1a2e;
            color: #c8d4e8;
            font-family: 'Microsoft YaHei', 'Segoe UI';
        }
        QGroupBox {
            border: 1px solid #2d3a5e;
            border-radius: 8px;
            margin-top: 8px;
            padding-top: 8px;
            font-size: 12px;
            color: #7090b8;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
        }
        QComboBox, QSpinBox {
            background: #16213e;
            border: 1px solid #2d3a5e;
            border-radius: 4px;
            padding: 4px 8px;
            color: #c8d4e8;
            font-size: 12px;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox QAbstractItemView {
            background: #16213e;
            color: #c8d4e8;
            selection-background-color: #3d5a80;
        }
        QPushButton {
            background: #3d5a80;
            color: #e2f0ff;
            border: none;
            border-radius: 6px;
            padding: 6px 16px;
            font-size: 12px;
        }
        QPushButton:hover { background: #507aad; }
        QPushButton#start_btn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2ecc71, stop:1 #27ae60);
            font-size: 13px;
            font-weight: bold;
            padding: 8px 24px;
        }
        QPushButton#stop_btn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #e74c3c, stop:1 #c0392b);
            font-size: 13px;
            font-weight: bold;
            padding: 8px 24px;
        }
        QCheckBox {
            font-size: 12px;
            spacing: 6px;
        }
        QCheckBox::indicator {
            width: 14px; height: 14px;
            border: 1px solid #3d5a80;
            border-radius: 3px;
            background: #16213e;
        }
        QCheckBox::indicator:checked {
            background: #3d5a80;
            image: none;
        }
        QLabel#title {
            font-size: 18px;
            font-weight: bold;
            color: #e2f0ff;
        }
        QLabel#subtitle {
            font-size: 11px;
            color: #5a7fa8;
        }
        QLabel#status_on {
            color: #2ecc71;
            font-size: 12px;
            font-weight: bold;
        }
        QLabel#status_off {
            color: #e74c3c;
            font-size: 12px;
        }
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Click Translator 设置")
        self.setFixedWidth(380)
        self.setStyleSheet(self.STYLE)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self._running = False
        self._setup_ui()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(12)

        # 标题
        title_row = QHBoxLayout()
        icon_label = QLabel("🌐")
        icon_label.setFont(QFont("Segoe UI Emoji", 24))
        title_row.addWidget(icon_label)
        title_col = QVBoxLayout()
        title = QLabel("Click Translator")
        title.setObjectName("title")
        subtitle = QLabel("点击即翻译 · 实时取词")
        subtitle.setObjectName("subtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_row.addLayout(title_col)
        title_row.addStretch()
        main.addLayout(title_row)

        # 状态指示
        self._status_label = QLabel("● 未运行")
        self._status_label.setObjectName("status_off")
        main.addWidget(self._status_label)

        # 触发方式
        trigger_group = QGroupBox("触发方式")
        trigger_layout = QVBoxLayout(trigger_group)
        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems([
            "双击鼠标左键（推荐）",
            "Ctrl + 鼠标左键",
            "Alt + 鼠标左键",
            "F8 截图翻译（选不中的文字）"
        ])
        trigger_layout.addWidget(self._trigger_combo)
        hint = QLabel("💡 双击模式：先选中文字，再双击即可翻译\n💡 F8模式：按F8后框选区域截图翻译")
        hint.setStyleSheet("color: #5a7fa8; font-size: 10px;")
        hint.setWordWrap(True)
        trigger_layout.addWidget(hint)
        main.addWidget(trigger_group)

        # 翻译设置
        trans_group = QGroupBox("翻译设置")
        trans_layout = QVBoxLayout(trans_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("翻译引擎"))
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["腾讯翻译 (免费国内)", "有道翻译 (免费国内)", "Google (需VPN)", "Bing (免费)", "百度翻译"])
        row1.addWidget(self._engine_combo)
        trans_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("目标语言"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems([
            "中文简体 (zh-CN)", "中文繁体 (zh-TW)", "English (en)",
            "日本語 (ja)", "한국어 (ko)", "Français (fr)",
            "Deutsch (de)", "Español (es)", "Русский (ru)"
        ])
        row2.addWidget(self._lang_combo)
        trans_layout.addLayout(row2)

        main.addWidget(trans_group)

        # 控制按钮
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("▶ 开始监听")
        self._start_btn.setObjectName("start_btn")
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn = QPushButton("■ 停止")
        self._stop_btn.setObjectName("stop_btn")
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        main.addLayout(btn_row)

        # OCR设置
        ocr_group = QGroupBox("截图翻译 (OCR)")
        ocr_layout = QVBoxLayout(ocr_group)
        
        self._ocr_checkbox = QCheckBox("启用截图翻译 (选不中文字时使用)")
        # 只有 OCR 真正可用时才默认勾选
        self._ocr_checkbox.setChecked(OCR_AVAILABLE)
        ocr_layout.addWidget(self._ocr_checkbox)
        
        ocr_hint = QLabel("💡 如果文字选不中（如图片、PDF扫描件），\n   软件会自动截图并识别文字")
        ocr_hint.setStyleSheet("color: #5a7fa8; font-size: 10px;")
        ocr_hint.setWordWrap(True)
        ocr_layout.addWidget(ocr_hint)
        
        self._ocr_status = QLabel("OCR状态: 检查中...")
        self._ocr_status.setStyleSheet("color: #888; font-size: 10px;")
        ocr_layout.addWidget(self._ocr_status)
        
        main.addWidget(ocr_group)

        # 使用说明
        help_group = QGroupBox("使用说明")
        help_layout = QVBoxLayout(help_group)
        help_text = (
            "1. 点击「开始监听」启动翻译\n"
            "2. 在任意软件中选中文字\n"
            "3. 双击（或 Ctrl/Alt + 点击）触发翻译\n"
            "4. 或按 F8 后框选区域截图翻译\n"
            "5. 翻译结果悬浮显示在光标旁\n"
            "6. 可拖拽翻译窗口，点击「复制」复制结果"
        )
        help_label = QLabel(help_text)
        help_label.setStyleSheet("color: #6880a0; font-size: 11px; line-height: 1.5;")
        help_layout.addWidget(help_label)
        main.addWidget(help_group)

        main.addStretch()
        
        # 检查OCR状态
        self._check_ocr_status()

    def _on_start(self):
        self._running = True
        self._status_label.setText("● 监听中")
        self._status_label.setObjectName("status_on")
        self._status_label.setStyleSheet("color: #2ecc71; font-size: 12px; font-weight: bold;")
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self.settings_changed.emit(self._get_settings())

    def _on_stop(self):
        self._running = False
        self._status_label.setText("● 已停止")
        self._status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        settings = self._get_settings()
        settings["action"] = "stop"
        self.settings_changed.emit(settings)

    def _get_settings(self) -> dict:
        engine_map = {0: "tencent", 1: "youdao", 2: "google", 3: "bing", 4: "baidu"}
        lang_map = {
            0: "zh-CN", 1: "zh-TW", 2: "en", 3: "ja",
            4: "ko", 5: "fr", 6: "de", 7: "es", 8: "ru"
        }
        trigger_map = {0: "double_click", 1: "ctrl_click", 2: "alt_click", 3: "screenshot_hotkey"}
        return {
            "action": "start",
            "engine": engine_map.get(self._engine_combo.currentIndex(), "google"),
            "target_lang": lang_map.get(self._lang_combo.currentIndex(), "zh-CN"),
            "trigger": trigger_map.get(self._trigger_combo.currentIndex(), "double_click"),
            "ocr_enabled": self._ocr_checkbox.isChecked()
        }
    
    def _check_ocr_status(self):
        """检查OCR是否可用，联动复选框状态"""
        if OCR_AVAILABLE:
            try:
                pytesseract.get_tesseract_version()
                self._ocr_status.setText("OCR状态: 已就绪")
                self._ocr_status.setStyleSheet("color: #2ecc71; font-size: 10px;")
                self._ocr_checkbox.setEnabled(True)
            except Exception:
                self._ocr_status.setText("OCR状态: 需要安装Tesseract引擎")
                self._ocr_status.setStyleSheet("color: #e74c3c; font-size: 10px;")
                self._ocr_checkbox.setEnabled(False)
                self._ocr_checkbox.setChecked(False)
        else:
            self._ocr_status.setText("OCR状态: 未安装 pytesseract")
            self._ocr_status.setStyleSheet("color: #888; font-size: 10px;")
            self._ocr_checkbox.setEnabled(False)
            self._ocr_checkbox.setChecked(False)


# ─────────────────────────────────────────────
# 截图选择器 - 框选区域
# ─────────────────────────────────────────────
class ScreenshotSelector(QWidget):
    """
    全屏截图选择器，使用 Windows Overlay 模式，
    避免 Qt WA_TranslucentBackground 在 Windows 下的兼容性问题。
    按 ESC 取消，左键拖拽框选，右键退出。
    """
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        # 使用 SubSurface 在桌面之上、其余窗口之下
        # 不使用 Tool/Frameless+透明背景（Windows Qt BUG）
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        
        # 全屏尺寸
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
        # ── 全屏半透明遮罩层 ──
        self._overlay = QLabel(self)
        self._overlay.setGeometry(0, 0, screen.width(), screen.height())
        self._overlay.setStyleSheet("background: rgba(0, 0, 0, 150);")
        self._overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # ── 操作提示 ──
        self._hint = QLabel("拖拽框选区域  |  ESC 取消  |  右键退出", self)
        self._hint.setStyleSheet(
            "color: white; background: rgba(0,0,0,0); "
            "font-size: 14px; padding: 8px 16px;"
        )
        self._hint.adjustSize()
        self._hint.move(20, 20)
        self._hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # ── 尺寸标签（跟随鼠标显示选区大小）──
        self._size_label = QLabel("", self)
        self._size_label.setStyleSheet(
            "color: white; background: rgba(30,30,50,180); "
            "font-size: 12px; padding: 2px 8px; border-radius: 4px;"
        )
        self._size_label.hide()
        self._size_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.start_pos = None
        self.end_pos = None
        self.drawing = False
        self._selection_rect = None
        
        self.grabKeyboard()
    
    def paintEvent(self, event):
        # 绘制选择框（从遮罩上"挖出"透明区域）
        if self._selection_rect:
            qp = QPainter(self)
            qp.setPen(QPen(QColor("#00d4ff"), 2))
            qp.setBrush(QBrush(QColor(0, 212, 255, 30)))
            qp.drawRect(self._selection_rect)
            # 选区尺寸文字
            w = self._selection_rect.width()
            h = self._selection_rect.height()
            self._size_label.setText(f" {w} × {h} ")
            self._size_label.adjustSize()
            # 放在选区右下角，避免超出屏幕
            sl_pos = self._selection_rect.bottomRight()
            screen = QApplication.primaryScreen().geometry()
            lx = min(sl_pos.x() + 4, screen.width() - self._size_label.width() - 4)
            ly = min(sl_pos.y() + 2, screen.height() - self._size_label.height() - 4)
            self._size_label.move(lx, ly)
            self._size_label.show()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._size_label.hide()
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.drawing = True
    
    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_pos = event.pos()
            self._selection_rect = QRect(self.start_pos, self.end_pos).normalized()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            self.end_pos = event.pos()
            self._selection_rect = QRect(self.start_pos, self.end_pos).normalized()
            self.update()
            
            rect = self._selection_rect
            if rect.width() >= 5 and rect.height() >= 5:
                self.close()
                # 延迟回调，确保窗口已关闭
                QTimer.singleShot(50, lambda: self.callback(
                    rect.left(), rect.top(), rect.right(), rect.bottom()
                ))
            else:
                self.close()
        elif event.button() == Qt.RightButton:
            self.close()
    
    def closeEvent(self, event):
        self.releaseKeyboard()
        event.accept()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)


# ─────────────────────────────────────────────
# 主应用控制器
# ─────────────────────────────────────────────
class ClickTranslatorApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self._setup_style()

        self.engine = TranslatorEngine()
        self.grabber = WordGrabber()
        self.popup = TranslationPopup()
        self.settings_panel = SettingsPanel()
        self.mouse_listener = None
        self._worker = None

        self.settings_panel.settings_changed.connect(self._on_settings_changed)
        self._setup_tray()

    def _setup_style(self):
        self.app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#1a1a2e"))
        palette.setColor(QPalette.WindowText, QColor("#c8d4e8"))
        self.app.setPalette(palette)

    def _setup_tray(self):
        # 系统托盘
        self.tray = QSystemTrayIcon()
        # 创建一个简单的图标
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#3d5a80")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setPen(QPen(QColor("white"), 2))
        painter.setFont(QFont("Segoe UI Emoji", 14))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "译")
        painter.end()
        self.tray.setIcon(QIcon(pixmap))
        self.tray.setToolTip("Click Translator - 点击即翻译")

        menu = QMenu()
        show_action = QAction("⚙ 设置", menu)
        show_action.triggered.connect(self.settings_panel.show)
        show_action.triggered.connect(self.settings_panel.raise_)
        quit_action = QAction("✕ 退出", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.settings_panel.show()
            self.settings_panel.raise_()

    def _on_settings_changed(self, settings: dict):
        action = settings.get("action", "start")
        if action == "stop":
            self._stop_listener()
            return

        # 更新引擎设置
        self.engine.engine = settings["engine"]
        self.engine.target_lang = settings["target_lang"]
        self._ocr_enabled = settings.get("ocr_enabled", True)

        # 重启监听器
        self._stop_listener()
        self.mouse_listener = MouseListenerThread(mode=settings["trigger"])
        self.mouse_listener.translate_request.connect(self._on_translate_request)
        self.mouse_listener.screenshot_request.connect(self._on_screenshot_request)
        self.mouse_listener.start()
        self.tray.showMessage(
            "Click Translator",
            f"监听已启动 | {settings['trigger']} 模式",
            QSystemTrayIcon.Information, 2000
        )

    def _stop_listener(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener.wait(1000)
            self.mouse_listener = None

    def _on_translate_request(self, x: int, y: int):
        """获取当前选中文字并翻译，如果选不中则尝试OCR截图"""
        try:
            text = self.grabber.get_word_from_selection()
            
            # 如果剪贴板没有文字，且启用了OCR，尝试截图识别
            if not text and OCR_AVAILABLE and getattr(self, '_ocr_enabled', True):
                text = self.grabber.get_text_from_screenshot(x, y)
            
            if not text:
                return
            
            # 显示加载状态
            self.popup.show_loading(x, y)
            # 异步翻译
            if self._worker and self._worker.isRunning():
                self._worker.terminate()
            self._worker = TranslateWorker(self.engine, text, x, y)
            self._worker.result_ready.connect(self._on_result_ready)
            self._worker.start()
        except Exception as e:
            try:
                self.tray.showMessage(
                    "Click Translator",
                    f"取词失败: {str(e)}",
                    QSystemTrayIcon.Warning, 3000
                )
            except Exception:
                pass  # 完全兜底，不闪退

    def _on_result_ready(self, result: dict, x: int, y: int):
        original = result.get("_original", "")
        self.popup.show_result(original, result, x, y)
        
        # 翻译失败时弹托盘通知（用户可能没注意到弹窗）
        if result.get("error"):
            self.tray.showMessage(
                "Click Translator",
                f"翻译失败: {result['error']}",
                QSystemTrayIcon.Warning, 3000
            )

    def _on_screenshot_request(self):
        """F8快捷键触发截图翻译"""
        # 显示截图选择器
        self.screenshot_selector = ScreenshotSelector(self._on_screenshot_selected)
        self.screenshot_selector.show()

    def _on_screenshot_selected(self, x1, y1, x2, y2):
        """截图选择完成后进行OCR翻译"""
        if not OCR_AVAILABLE:
            self.tray.showMessage(
                "Click Translator",
                "OCR未安装，请先安装 pytesseract 和 Tesseract-OCR",
                QSystemTrayIcon.Warning, 3000
            )
            return
        
        # 确保坐标正确
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)
        
        if right - left < 10 or bottom - top < 10:
            return  # 区域太小，取消
        
        # 截图并OCR
        try:
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            text = pytesseract.image_to_string(screenshot, lang='eng+chi_sim').strip()
            
            if text:
                # 显示加载状态
                self.popup.show_loading((left + right) // 2, top)
                # 异步翻译
                if self._worker and self._worker.isRunning():
                    self._worker.terminate()
                self._worker = TranslateWorker(self.engine, text, (left + right) // 2, top)
                self._worker.result_ready.connect(self._on_result_ready)
                self._worker.start()
            else:
                self.tray.showMessage(
                    "Click Translator",
                    "未识别到文字，请尝试选择更大的区域",
                    QSystemTrayIcon.Information, 2000
                )
        except Exception as e:
            self.tray.showMessage(
                "Click Translator",
                f"截图翻译失败: {str(e)}",
                QSystemTrayIcon.Warning, 3000
            )

    def run(self):
        self.settings_panel.show()
        sys.exit(self.app.exec_())

    def _quit(self):
        self._stop_listener()
        self.app.quit()


if __name__ == "__main__":
    # 提升进程DPI感知（Windows高分屏）
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    app_instance = ClickTranslatorApp()
    app_instance.run()
