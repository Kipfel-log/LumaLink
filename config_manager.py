"""config_manager.py — 应用程序配置持久化管理模块。

使用 JSON 文件持久化保存所有用户设置：
- 照片保存目录
- 通信服务端口
- 外观主题 (Auto/Light/Dark)
- 文件自动重命名规则 (启用开关、前缀、起始/当前序号、补零位数)
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


import sys

if getattr(sys, "frozen", False):
    # 打包为 EXE 运行：配置文件存放在 EXE 程序所在同级目录下
    DEFAULT_CONFIG_PATH = Path(sys.executable).parent / "config.json"
else:
    # 源码模式运行：配置文件存放在源码同级目录下
    DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


class AppConfig:
    """应用设置数据模型与持久化类。"""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._lock = threading.Lock()

        # 默认设置项
        default_dir = Path.home() / "Pictures" / "MobilePhotos"
        self.save_dir: str = str(default_dir)
        self.server_port: int = 8989
        self.preferred_ip: str = ""
        self.theme: str = "Dark"
        self.background_image: str = "kipfel_1.png"
        self.bg_opacity: int = 100

        # 自动重命名设置
        self.auto_rename_enabled: bool = True
        self.name_prefix: str = "IMG_"
        self.start_index: int = 1
        self.current_index: int = 1
        self.digit_padding: int = 3

        self.load()

    def load(self) -> None:
        """从 JSON 文件加载持久化配置。"""
        with self._lock:
            if not self.config_path.exists():
                self.save_unlocked()
                return

            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data: dict[str, Any] = json.load(f)

                self.save_dir = str(data.get("save_dir", self.save_dir))
                self.server_port = int(data.get("server_port", self.server_port))
                self.preferred_ip = str(data.get("preferred_ip", self.preferred_ip))
                self.theme = str(data.get("theme", self.theme))
                self.background_image = str(data.get("background_image", self.background_image))
                self.bg_opacity = int(data.get("bg_opacity", self.bg_opacity))

                self.auto_rename_enabled = bool(data.get("auto_rename_enabled", self.auto_rename_enabled))
                self.name_prefix = str(data.get("name_prefix", self.name_prefix))
                self.start_index = int(data.get("start_index", self.start_index))
                self.current_index = int(data.get("current_index", self.current_index))
                self.digit_padding = int(data.get("digit_padding", self.digit_padding))
            except Exception as e:
                print(f"[AppConfig] 加载配置文件失败，将使用默认配置: {e}")
                self.save_unlocked()

    def save_unlocked(self) -> None:
        """保存配置到文件 (非线程锁内部使用)。"""
        data = {
            "save_dir": self.save_dir,
            "server_port": self.server_port,
            "preferred_ip": self.preferred_ip,
            "theme": self.theme,
            "background_image": self.background_image,
            "bg_opacity": self.bg_opacity,
            "auto_rename_enabled": self.auto_rename_enabled,
            "name_prefix": self.name_prefix,
            "start_index": self.start_index,
            "current_index": self.current_index,
            "digit_padding": self.digit_padding,
        }
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AppConfig] 保存配置文件失败: {e}")

    def save(self) -> None:
        """保存当前配置到文件。"""
        with self._lock:
            self.save_unlocked()

    def peek_next_filename(self, extension: str = ".jpg") -> tuple[str, int]:
        """查看下一张照片的文件名与序号 (不增加序号)。"""
        with self._lock:
            if not self.auto_rename_enabled:
                return "IMG_YYYYMMDD_HHMMSS_001" + extension, self.current_index
            
            num_str = f"{self.current_index:0{self.digit_padding}d}"
            filename = f"{self.name_prefix}{num_str}{extension}"
            return filename, self.current_index

    def consume_next_filename(self, extension: str = ".jpg") -> tuple[str, int]:
        """获取当前文件名并自动将序号 +1，保存配置文件。"""
        with self._lock:
            ext = extension if extension.startswith(".") else f".{extension}"
            if not self.auto_rename_enabled:
                import time
                ts = time.strftime("%Y%m%d_%H%M%S")
                filename = f"IMG_{ts}_001{ext}"
                return filename, self.current_index

            num_str = f"{self.current_index:0{self.digit_padding}d}"
            filename = f"{self.name_prefix}{num_str}{ext}"
            used_index = self.current_index
            self.current_index += 1
            self.save_unlocked()
            return filename, used_index

    def set_start_index(self, index: int) -> None:
        """更新起始/当前序号并持久化。"""
        with self._lock:
            self.start_index = max(1, index)
            self.current_index = max(1, index)
            self.save_unlocked()
