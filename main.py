"""main.py — 手机扫码拍照助手程序入口。"""
from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

from config_manager import AppConfig
from main_window import MainWindow


def main() -> None:
    # 启用高 DPI 屏幕自适应缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

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
