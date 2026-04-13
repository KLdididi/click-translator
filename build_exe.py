"""
打包 Click Translator 为独立可执行文件
使用 PyInstaller 打包成单文件 exe
"""

import os
import sys
import subprocess
import shutil


def check_pyinstaller():
    """检查是否安装了 PyInstaller"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """安装 PyInstaller"""
    print("正在安装 PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    print("PyInstaller 安装完成")


def build_exe():
    """打包 exe"""
    
    # 当前目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    # 清理旧的构建
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # PyInstaller 参数
    cmd = [
        "pyinstaller",
        "--name=ClickTranslator",
        "--onefile",           # 单文件
        "--windowed",          # 无控制台窗口
        "--icon=NONE",         # 无图标（使用默认）
        "--clean",             # 清理缓存
        "--noconfirm",         # 不确认覆盖
        # 隐藏导入
        "--hidden-import=PyQt5.sip",
        "--hidden-import=PyQt5.QtCore",
        "--hidden-import=PyQt5.QtGui",
        "--hidden-import=PyQt5.QtWidgets",
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
        "--hidden-import=requests",
        "--hidden-import=PIL",
        "--hidden-import=pyautogui",
        "--hidden-import=win32api",
        "--hidden-import=win32con",
        "--hidden-import=win32gui",
        "--hidden-import=win32clipboard",
        # 数据文件
        "--add-data=README.md;.",
        "translator.py"
    ]
    
    print("开始打包...")
    print(f"命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("✅ 打包成功！")
        print("=" * 50)
        
        exe_path = os.path.join(base_dir, "dist", "ClickTranslator.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n可执行文件: {exe_path}")
            print(f"文件大小: {size_mb:.1f} MB")
            print(f"\n你可以直接把这个 exe 文件复制到其他电脑上运行")
            print("不需要安装 Python！")
        
        return True
    else:
        print("\n" + "=" * 50)
        print("❌ 打包失败")
        print("=" * 50)
        print("错误输出:")
        print(result.stderr)
        return False


def main():
    print("=" * 50)
    print("Click Translator 打包工具")
    print("=" * 50)
    
    # 检查 PyInstaller
    if not check_pyinstaller():
        print("\n未检测到 PyInstaller，需要安装...")
        try:
            install_pyinstaller()
        except Exception as e:
            print(f"安装失败: {e}")
            print("请手动运行: pip install pyinstaller")
            return
    else:
        print("\n✓ PyInstaller 已安装")
    
    # 开始打包
    print("\n开始打包过程...")
    success = build_exe()
    
    if success:
        print("\n" + "=" * 50)
        print("打包完成！")
        print("=" * 50)
        print("\n📦 输出文件:")
        print("  dist/ClickTranslator.exe")
        print("\n💡 提示:")
        print("  1. 把这个 exe 文件发给其他人即可")
        print("  2. 接收方不需要安装 Python")
        print("  3. Windows 系统直接双击运行")
        print("  4. 如果被杀毒软件拦截，请添加信任")
    else:
        print("\n打包失败，请检查错误信息")
        input("按回车键退出...")


if __name__ == "__main__":
    main()
