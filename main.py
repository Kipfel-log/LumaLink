import ctypes
import os
import sys
from pathlib import Path

# 注册 Windows 显式 AppUserModelID，确保 Windows 任务栏正常显示自定义应用图标
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KipfelLog.LumaLink.v1.2")
except Exception:
    pass

# 修复 Windows PyInstaller 环境下 PySide6 C++ DLL 加载路径问题
if getattr(sys, "frozen", False):
    base_dir = Path(sys.executable).parent
    internal_dir = base_dir / "_internal"
    pyside_dir = internal_dir / "PySide6"
    for d in [pyside_dir, internal_dir, pyside_dir / "Qt" / "bin"]:
        if d.exists():
            try:
                os.add_dll_directory(str(d))
            except Exception:
                pass

# 显式首先导入 PySide6 触发 C++ 动态库初始化
import PySide6
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

from config_manager import AppConfig
from main_window import MainWindow, load_svg_pixmap


def get_app_root() -> Path:
    """获取应用程序运行根目录（兼容源码开发、PyInstaller打包与Nuitka C++编译环境）。"""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def main() -> None:
    # 启用高 DPI 屏幕自适应缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # 设置任务栏全局图标 (assets/lumalink_icon_mark.png)
    icon_path = get_app_root() / "assets" / "lumalink_icon_mark.png"
    if icon_path.exists():
        from PySide6.QtGui import QPixmap
        pix = QPixmap(str(icon_path))
        if not pix.isNull():
            app.setWindowIcon(QIcon(pix))

    # 全局设置应用默认字体为 MiSans (含备用字体 fallback)
    app_font = QFont()
    app_font.setFamilies(["MiSans", "Microsoft YaHei", "Segoe UI", "sans-serif"])
    app.setFont(app_font)

    # 读取持久化配置
    config_mgr = AppConfig()

    # 应用加载持久化的外观主题
    if config_mgr.theme == "Dark":
        setTheme(Theme.DARK)
    elif config_mgr.theme == "Light":
        setTheme(Theme.LIGHT)
    else:
        setTheme(Theme.AUTO)

    window = MainWindow(config_mgr=config_mgr)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
