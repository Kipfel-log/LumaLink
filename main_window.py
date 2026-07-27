"""main_window.py — 手机扫码拍照助手主界面 (无冗余顶栏与无 Emoji 极简 Fluent 风)。

页面设计：
1. 「无线拍照主页」：界面无顶部大卡片，极简清爽。呈现扫码配对、PIN 码显示、下一张照片预分配序号、100% 比例大图预览与已保存历史列表。
2. 「应用设置页」：独立配置图片保存目录、自定义通信端口、通信网卡/IP 切换、文件自动重命名规则（前缀与起始序号）以及外观深色/浅色主题（全局持久化存储）。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    FluentWindow,
    HyperlinkButton,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    NavigationItemPosition,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SpinBox,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
    TitleLabel,
    TransparentToolButton,
    isDarkTheme,
    toggleTheme,
)

from aspect_video_widget import AspectVideoWidget
from config_manager import AppConfig
from mobile_server import MobileServerManager, get_all_lan_ips_info
from qr_utils import generate_qr_pixmap


class PhotoItemWidget(QWidget):
    """已接收照片历史卡片组件。"""

    def __init__(
        self,
        file_path: str,
        qimg: QImage,
        info_str: str,
        on_delete_cb,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.file_path = file_path
        self.path_obj = Path(file_path)
        self.qimg = qimg
        self.info_str = info_str
        self.on_delete_cb = on_delete_cb

        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(12)

        # 缩略图 (100x75)
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(100, 75)
        self.thumb_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 0.25); border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.1);"
        )
        scaled = qimg.scaled(
            100, 75,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumb_label.setPixmap(QPixmap.fromImage(scaled))
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumb_label)

        # 文字描述区
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = StrongBodyLabel(self.path_obj.name)
        info_layout.addWidget(title)

        time_lbl = CaptionLabel(f"时间/设备: {info_str}")
        time_lbl.setStyleSheet("color: #888888;")
        info_layout.addWidget(time_lbl)

        # 计算文件大小
        size_str = "文件写入中"
        if self.path_obj.exists():
            bytes_size = self.path_obj.stat().st_size
            if bytes_size >= 1024 * 1024:
                size_str = f"{bytes_size / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{bytes_size / 1024:.1f} KB"

        detail_lbl = CaptionLabel(f"分辨率: {qimg.width()} × {qimg.height()} | 大小: {size_str}")
        detail_lbl.setStyleSheet("color: #888888;")
        info_layout.addWidget(detail_lbl)

        layout.addLayout(info_layout, 1)

        # 功能按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.open_folder_btn = TransparentToolButton(FIF.FOLDER, self)
        self.open_folder_btn.setToolTip("在文件夹中选中此照片")
        self.open_folder_btn.clicked.connect(self._locate_file)
        btn_layout.addWidget(self.open_folder_btn)

        self.open_img_btn = TransparentToolButton(FIF.VIEW, self)
        self.open_img_btn.setToolTip("用系统查看器打开原图")
        self.open_img_btn.clicked.connect(self._open_file)
        btn_layout.addWidget(self.open_img_btn)

        self.del_btn = TransparentToolButton(FIF.DELETE, self)
        self.del_btn.setToolTip("从磁盘彻底删除")
        self.del_btn.clicked.connect(lambda: self.on_delete_cb(self))
        btn_layout.addWidget(self.del_btn)

        layout.addLayout(btn_layout)

    def _locate_file(self) -> None:
        if self.path_obj.exists():
            os.system(f'explorer /select,"{str(self.path_obj.resolve())}"')

    def _open_file(self) -> None:
        if self.path_obj.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path_obj.resolve())))


class MainWindow(FluentWindow):
    """手机无线扫码拍照助手主窗口。"""

    def __init__(self, config_mgr: AppConfig | None = None, save_dir: Path | None = None) -> None:
        super().__init__()
        self.config_mgr = config_mgr if config_mgr is not None else AppConfig()

        if save_dir:
            self.save_dir = Path(save_dir).resolve()
            self.config_mgr.save_dir = str(self.save_dir)
            self.config_mgr.save()
        else:
            self.save_dir = Path(self.config_mgr.save_dir).resolve()

        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._staged_count = 0

        self.server_mgr = MobileServerManager(
            save_dir=self.save_dir,
            config_mgr=self.config_mgr,
            parent=self,
        )

        self.setWindowTitle("LumaLink")
        self.resize(1180, 760)
        self.setMinimumSize(850, 580)

        # 开启 Windows 11 Mica 云母材质
        try:
            self.setMicaEffectEnabled(True)
        except Exception:
            pass

        # 1. 独立设置页与主功能页 Widget
        self.home_interface = QWidget(self)
        self.home_interface.setObjectName("homeInterface")

        # 使用 QFluentWidgets 的 ScrollArea 作为设置页滚动区域，防止界面卡片重叠
        self.settings_interface = ScrollArea(self)
        self.settings_interface.setObjectName("settingsInterface")
        self.settings_interface.setWidgetResizable(True)
        self.settings_interface.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.settings_container = QWidget()
        self.settings_container.setObjectName("settingsContainer")
        self.settings_container.setStyleSheet("background-color: transparent;")
        self.settings_interface.setWidget(self.settings_container)

        # 先初始化设置界面与主界面控件
        self._init_settings_interface()
        self._init_home_interface()

        # 3. 注册添加到侧边栏导航
        self.addSubInterface(
            self.home_interface,
            FIF.CAMERA,
            "无线拍照主页",
            NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            "应用设置",
            NavigationItemPosition.BOTTOM,
        )

        self._start_server()

    # ── 1. 无线拍照主页 ──
    def _init_home_interface(self) -> None:
        main_vbox = QVBoxLayout(self.home_interface)
        main_vbox.setContentsMargins(18, 16, 18, 16)
        main_vbox.setSpacing(12)

        # Splitter：左侧扫码卡片 vs 右侧预览/列表
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self.home_interface)
        self.splitter.setChildrenCollapsible(False)
        main_vbox.addWidget(self.splitter, 1)

        # (A) 左侧扫码与配对面板
        left_card = CardWidget(self.home_interface)
        left_card.setMinimumWidth(360)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(12)

        # 左侧头部：标题 + 简明服务状态指示
        left_header = QHBoxLayout()
        left_header.addWidget(SubtitleLabel("扫码无线配对"))
        left_header.addStretch(1)

        self.status_label = StrongBodyLabel("服务准备中...", self.home_interface)
        self.status_label.setStyleSheet("color: #10b981; font-size: 13px;")
        left_header.addWidget(self.status_label)

        left_layout.addLayout(left_header)

        # 二维码与 URL 容器
        qr_box = QVBoxLayout()
        qr_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.qr_label = QLabel(self.home_interface)
        self.qr_label.setFixedSize(210, 210)
        self.qr_label.setStyleSheet(
            "border: 2px solid rgba(0, 95, 184, 0.3); border-radius: 12px; background: white; padding: 4px;"
        )
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_box.addWidget(self.qr_label)

        self.url_label = StrongBodyLabel("正在检测局域网地址...", self.home_interface)
        self.url_label.setStyleSheet("color: #005fb8; font-size: 15px; margin-top: 6px;")
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_box.addWidget(self.url_label)

        left_layout.addLayout(qr_box)

        # 6 位 PIN 码配对卡片
        pin_card = CardWidget(self.home_interface)
        pin_card.setStyleSheet("background-color: rgba(0, 95, 184, 0.05); border: 1px dashed #005fb8; border-radius: 8px;")
        pin_layout = QHBoxLayout(pin_card)
        pin_layout.setContentsMargins(14, 8, 14, 8)

        pin_info_vbox = QVBoxLayout()
        pin_info_vbox.setSpacing(2)
        pin_info_vbox.addWidget(CaptionLabel("手机网页 6 位验证码:"))
        self.pin_val_label = TitleLabel("------", self.home_interface)
        self.pin_val_label.setStyleSheet("color: #005fb8; font-weight: 800; letter-spacing: 4px;")
        pin_info_vbox.addWidget(self.pin_val_label)
        pin_layout.addLayout(pin_info_vbox, 1)

        self.refresh_pin_btn = TransparentToolButton(FIF.SYNC, self.home_interface)
        self.refresh_pin_btn.setToolTip("刷新验证码")
        self.refresh_pin_btn.clicked.connect(self._on_refresh_pin)
        pin_layout.addWidget(self.refresh_pin_btn)

        left_layout.addWidget(pin_card)

        # 已连接设备指示
        self.client_label = CaptionLabel("已连接设备: 0 台手机", self.home_interface)
        self.client_label.setStyleSheet("color: #888888; font-size: 12px;")
        left_layout.addWidget(self.client_label)

        # 使用指南
        guide_card = CardWidget(self.home_interface)
        guide_vbox = QVBoxLayout(guide_card)
        guide_vbox.setContentsMargins(12, 10, 12, 10)
        guide_vbox.setSpacing(4)
        guide_vbox.addWidget(StrongBodyLabel("扫码连接指南："))
        guide_vbox.addWidget(CaptionLabel("1. 手机需与电脑连接在同一 Wi-Fi 或局域网"))
        guide_vbox.addWidget(CaptionLabel("2. 使用手机微信/相机/浏览器扫码"))
        guide_vbox.addWidget(CaptionLabel("3. 网页中输入 6 位验证码后即可拍照传输"))
        left_layout.addWidget(guide_card)

        left_layout.addStretch(1)
        self.splitter.addWidget(left_card)

        # (B) 右侧预览大图与历史列表
        right_widget = QWidget(self.home_interface)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 上半部分：AspectVideoWidget 预览大图与下一张序号展示
        preview_header = QHBoxLayout()
        preview_header.setSpacing(10)
        preview_header.addWidget(SubtitleLabel("最新拍摄照片预览"))
        
        # 下一张照片预分配序号指示标签
        self.next_seq_label = StrongBodyLabel("下一张照片: #001 (IMG_001.jpg)", self.home_interface)
        self.next_seq_label.setStyleSheet(
            "color: #005fb8; font-size: 12px; font-weight: bold; background: rgba(0, 95, 184, 0.08); padding: 4px 10px; border-radius: 6px;"
        )
        preview_header.addWidget(self.next_seq_label)

        preview_header.addStretch(1)
        self.preview_count_lbl = CaptionLabel("本次启动已接收: 0 张照片")
        preview_header.addWidget(self.preview_count_lbl)
        right_layout.addLayout(preview_header)

        self.video_widget = AspectVideoWidget(self.home_interface)
        self.video_widget.setText("等待手机扫码拍照...\n拍摄照片将实时在此展示大图，并同步写入电脑保存目录")
        right_layout.addWidget(self.video_widget, 4)

        # 下半部分：已保存照片 ListWidget 历史
        list_header = QHBoxLayout()
        self.history_title = StrongBodyLabel("已保存照片历史 (0 张)")
        list_header.addWidget(self.history_title)
        list_header.addStretch(1)

        self.clear_btn = PushButton(FIF.DELETE, "清空列表显示", self.home_interface)
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self._on_clear_list)
        list_header.addWidget(self.clear_btn)

        right_layout.addLayout(list_header)

        self.photo_list = ListWidget(self.home_interface)
        self.photo_list.setSelectionMode(ListWidget.SelectionMode.SingleSelection)
        self.photo_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        right_layout.addWidget(self.photo_list, 3)

        self.splitter.addWidget(right_widget)

        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([380, 680])

        self._update_next_seq_display()

    # ── 2. 独立应用设置页面 ──
    def _init_settings_interface(self) -> None:
        settings_vbox = QVBoxLayout(self.settings_container)
        settings_vbox.setContentsMargins(24, 20, 24, 20)
        settings_vbox.setSpacing(18)

        # 页面标题
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_vbox.addWidget(TitleLabel("应用设置"))
        title_vbox.addWidget(CaptionLabel("管理照片存入路径、通信服务端口与网卡、文件自动重命名规则及外观主题（永久自动保存）"))
        settings_vbox.addLayout(title_vbox)

        # 设置卡片 1: 照片保存目录设置
        dir_card = CardWidget(self.settings_container)
        dir_layout = QVBoxLayout(dir_card)
        dir_layout.setContentsMargins(20, 16, 20, 16)
        dir_layout.setSpacing(10)

        dir_layout.addWidget(SubtitleLabel("照片保存目录设置"))
        dir_layout.addWidget(CaptionLabel("设置从手机拍摄并实时存入电脑本地的文件保存路径"))

        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)
        dir_row.addWidget(StrongBodyLabel("当前目录:", self.settings_container))

        self.path_edit = LineEdit(self.settings_container)
        self.path_edit.setText(str(self.save_dir))
        self.path_edit.setReadOnly(True)
        dir_row.addWidget(self.path_edit, 1)

        self.browse_dir_btn = PrimaryPushButton(FIF.FOLDER, "浏览选择目录", self.settings_container)
        self.browse_dir_btn.clicked.connect(self._on_change_dir)
        dir_row.addWidget(self.browse_dir_btn)

        self.open_dir_btn = PushButton(FIF.SEARCH, "打开保存目录", self.settings_container)
        self.open_dir_btn.clicked.connect(self._on_open_dir)
        dir_row.addWidget(self.open_dir_btn)

        dir_layout.addLayout(dir_row)
        settings_vbox.addWidget(dir_card)

        # 设置卡片 2: 通信网卡与自定义服务端口
        net_card = CardWidget(self.settings_container)
        net_layout = QVBoxLayout(net_card)
        net_layout.setContentsMargins(20, 16, 20, 16)
        net_layout.setSpacing(12)

        net_layout.addWidget(SubtitleLabel("通信网卡与自定义服务端口"))
        net_layout.addWidget(CaptionLabel("可自定义局域网 HTTP 通信端口，并选择手机扫码访问的主机 IP 地址"))

        net_row = QHBoxLayout()
        net_row.setSpacing(10)
        net_row.addWidget(StrongBodyLabel("通信网卡/IP:", self.settings_container))

        self.net_combo = ComboBox(self.settings_container)
        self.net_combo.setMinimumWidth(280)
        net_row.addWidget(self.net_combo, 1)

        net_row.addWidget(StrongBodyLabel("服务端口:", self.settings_container))
        self.port_spin = SpinBox(self.settings_container)
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(self.config_mgr.server_port)
        net_row.addWidget(self.port_spin)

        self.apply_port_btn = PrimaryPushButton(FIF.SYNC, "应用端口设置", self.settings_container)
        self.apply_port_btn.clicked.connect(self._on_apply_port)
        net_row.addWidget(self.apply_port_btn)

        net_layout.addLayout(net_row)
        settings_vbox.addWidget(net_card)

        # 设置卡片 3: 文件自动重命名与序号设置
        rename_card = CardWidget(self.settings_container)
        rename_layout = QVBoxLayout(rename_card)
        rename_layout.setContentsMargins(20, 16, 20, 16)
        rename_layout.setSpacing(12)

        rename_header = QHBoxLayout()
        rename_header.addWidget(SubtitleLabel("文件自动重命名与序号规则"))
        rename_header.addStretch(1)

        self.rename_switch = SwitchButton("启用文件自动重命名", self.settings_container)
        self.rename_switch.setChecked(self.config_mgr.auto_rename_enabled)
        self.rename_switch.checkedChanged.connect(self._on_rename_enabled_changed)
        rename_header.addWidget(self.rename_switch)
        rename_layout.addLayout(rename_header)

        rename_layout.addWidget(CaptionLabel("开启后，手机接收的照片将按设定的前缀与自动递增序号重命名（手机及电脑预览端实时提示下一张序号）"))

        rename_grid = QHBoxLayout()
        rename_grid.setSpacing(16)

        # 文件名前缀输入
        prefix_vbox = QVBoxLayout()
        prefix_vbox.setSpacing(4)
        prefix_vbox.addWidget(StrongBodyLabel("文件名前缀:"))
        self.prefix_edit = LineEdit(self.settings_container)
        self.prefix_edit.setText(self.config_mgr.name_prefix)
        self.prefix_edit.setPlaceholderText("例如: IMG_ 或 Photo_")
        self.prefix_edit.textChanged.connect(self._on_prefix_changed)
        prefix_vbox.addWidget(self.prefix_edit)
        rename_grid.addLayout(prefix_vbox, 2)

        # 起始 / 当前序号
        seq_vbox = QVBoxLayout()
        seq_vbox.setSpacing(4)
        seq_vbox.addWidget(StrongBodyLabel("起始 / 当前序号:"))
        self.seq_spin = SpinBox(self.settings_container)
        self.seq_spin.setRange(1, 999999)
        self.seq_spin.setValue(self.config_mgr.current_index)
        self.seq_spin.valueChanged.connect(self._on_seq_changed)
        seq_vbox.addWidget(self.seq_spin)
        rename_grid.addLayout(seq_vbox, 1)

        # 补零位数
        digit_vbox = QVBoxLayout()
        digit_vbox.setSpacing(4)
        digit_vbox.addWidget(StrongBodyLabel("序号位数补零:"))
        self.digit_spin = SpinBox(self.settings_container)
        self.digit_spin.setRange(1, 8)
        self.digit_spin.setValue(self.config_mgr.digit_padding)
        self.digit_spin.valueChanged.connect(self._on_digit_changed)
        digit_vbox.addWidget(self.digit_spin)
        rename_grid.addLayout(digit_vbox, 1)

        rename_layout.addLayout(rename_grid)

        # 效果示意
        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)
        self.rename_preview_lbl = StrongBodyLabel("效果预估: IMG_001.jpg", self.settings_container)
        self.rename_preview_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
        preview_row.addWidget(self.rename_preview_lbl)
        rename_layout.addLayout(preview_row)

        settings_vbox.addWidget(rename_card)

        # 设置卡片 4: 外观与视觉主题
        theme_card = CardWidget(self.settings_container)
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.setContentsMargins(20, 16, 20, 16)
        theme_layout.setSpacing(10)

        theme_layout.addWidget(SubtitleLabel("外观主题与 Windows 11 Mica 材质"))
        theme_layout.addWidget(CaptionLabel("一键无缝切换系统的深色 / 浅色模式，持久化记忆偏好"))

        theme_row = QHBoxLayout()
        theme_row.setSpacing(10)
        theme_row.addWidget(StrongBodyLabel("当前主题风格:", self.settings_container))
        theme_row.addStretch(1)

        self.theme_btn = PushButton(FIF.BRIGHTNESS, "切换深色 / 浅色主题", self.settings_container)
        self.theme_btn.clicked.connect(self._on_toggle_theme)
        theme_row.addWidget(self.theme_btn)

        theme_layout.addLayout(theme_row)
        settings_vbox.addWidget(theme_card)

        # 设置卡片 5: 关于与开发者信息
        about_card = CardWidget(self.settings_container)
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(20, 16, 20, 16)
        about_layout.setSpacing(10)

        about_layout.addWidget(SubtitleLabel("关于与开发者"))
        about_layout.addWidget(CaptionLabel("LumaLink（中文名：拾光）— 极简局域网无线拍照助手"))

        about_row = QHBoxLayout()
        about_row.setSpacing(16)

        about_info = QVBoxLayout()
        about_info.setSpacing(4)
        about_info.addWidget(StrongBodyLabel("项目名称: LumaLink (中文名: 拾光)", self.settings_container))
        about_info.addWidget(CaptionLabel("软件版本: v1.2  |  GitHub 开发者: Kipfel-Log", self.settings_container))
        about_row.addLayout(about_info, 1)

        # GitHub 开发者主页链接按钮 (HyperlinkButton 内置自动打开 URL，无需重复 connect)
        github_btn = HyperlinkButton(
            url="https://github.com/Kipfel-log",
            text="GitHub: Kipfel-Log",
            parent=self.settings_container,
            icon=FIF.GITHUB,
        )
        about_row.addWidget(github_btn)

        # GitHub 项目仓库链接按钮
        project_btn = HyperlinkButton(
            url="https://github.com/Kipfel-log/LumaLink",
            text="GitHub: LumaLink",
            parent=self.settings_container,
            icon=FIF.LINK,
        )
        about_row.addWidget(project_btn)

        about_layout.addLayout(about_row)
        settings_vbox.addWidget(about_card)

        settings_vbox.addStretch(1)

        # 根据当前配置同步组件禁用状态
        self._on_rename_enabled_changed(self.config_mgr.auto_rename_enabled)

    # ── 3. 业务逻辑与事件控制 ──
    def _populate_network_cards(self) -> None:
        """填充设置页面中的网卡下拉框。"""
        self.net_combo.blockSignals(True)
        self.net_combo.clear()

        net_list = get_all_lan_ips_info()
        for ip, label in net_list:
            self.net_combo.addItem(label, userData=ip)

        self.net_combo.blockSignals(False)
        self.net_combo.currentIndexChanged.connect(self._on_network_card_changed)

    def _start_server(self) -> None:
        """启动后台 HTTP 服务。"""
        self.server_mgr.photo_saved.connect(self._on_photo_saved)
        self.server_mgr.client_connected.connect(self._on_client_connected)
        self.server_mgr.client_disconnected.connect(self._on_client_disconnected)
        self.server_mgr.next_seq_changed.connect(self._on_next_seq_changed)

        ok, default_url = self.server_mgr.start_server(self.config_mgr.server_port)

        self._populate_network_cards()

        if ok:
            current_ip = self.server_mgr.current_ip
            for idx in range(self.net_combo.count()):
                if self.net_combo.itemData(idx) == current_ip:
                    self.net_combo.setCurrentIndex(idx)
                    break

            self._update_qr_and_url(current_ip)
            self.pin_val_label.setText(self.server_mgr.pin_code)
        else:
            self.status_label.setText("服务器启动失败")
            InfoBar.error(
                title="服务器启动失败",
                content=default_url,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000,
            )

    def _update_qr_and_url(self, ip_address: str) -> None:
        """更新二维码与访问 URL。"""
        url = f"http://{ip_address}:{self.server_mgr.port}"
        self.url_label.setText(url)
        self.status_label.setText("服务运行中")

        pm = generate_qr_pixmap(url, size=210)
        self.qr_label.setPixmap(pm)

    def _on_apply_port(self) -> None:
        """用户提交修改服务端口。"""
        new_port = self.port_spin.value()
        self.config_mgr.server_port = new_port
        self.config_mgr.save()

        ok, default_url = self.server_mgr.restart_server(new_port)
        if ok:
            current_ip = self.server_mgr.current_ip
            self._update_qr_and_url(current_ip)
            InfoBar.success(
                title="通信端口已更新",
                content=f"已成功绑定端口 {new_port}，访问地址: {default_url}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3500,
            )
        else:
            self.status_label.setText("端口绑定失败")
            InfoBar.error(
                title="端口重启失败",
                content=default_url,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000,
            )

    def _on_rename_enabled_changed(self, checked: bool) -> None:
        """重命名开关变更。"""
        self.config_mgr.auto_rename_enabled = checked
        self.config_mgr.save()

        self.prefix_edit.setEnabled(checked)
        self.seq_spin.setEnabled(checked)
        self.digit_spin.setEnabled(checked)
        self._update_next_seq_display()

    def _on_prefix_changed(self, text: str) -> None:
        """前缀文本变更。"""
        self.config_mgr.name_prefix = text.strip()
        self.config_mgr.save()
        self._update_next_seq_display()

    def _on_seq_changed(self, val: int) -> None:
        """起始序号变更。"""
        self.config_mgr.set_start_index(val)
        self._update_next_seq_display()

    def _on_digit_changed(self, val: int) -> None:
        """序号位数变更。"""
        self.config_mgr.digit_padding = val
        self.config_mgr.save()
        self._update_next_seq_display()

    @Slot(str, int)
    def _on_next_seq_changed(self, next_fn: str, next_seq: int) -> None:
        """当手机成功拍摄保存图片后，更新 UI 的序号展示。"""
        if hasattr(self, "seq_spin"):
            self.seq_spin.blockSignals(True)
            self.seq_spin.setValue(next_seq)
            self.seq_spin.blockSignals(False)
        self._update_next_seq_display()

    def _update_next_seq_display(self) -> None:
        """刷新电脑主界面及设置页面的序号预估信息。"""
        fn, seq = self.config_mgr.peek_next_filename(".jpg")
        if self.config_mgr.auto_rename_enabled:
            num_str = f"{seq:0{self.config_mgr.digit_padding}d}"
            text = f"下一张照片: #{num_str} ({fn})"
            preview = f"格式生效示例: {fn}"
        else:
            text = f"下一张照片: 原始时间戳自动命名"
            preview = f"自动重命名已禁用 (使用时间戳)"

        if hasattr(self, "next_seq_label"):
            self.next_seq_label.setText(text)
        if hasattr(self, "rename_preview_lbl"):
            self.rename_preview_lbl.setText(preview)

    def _on_toggle_theme(self) -> None:
        """一键切换主题并持久化保存。"""
        toggleTheme()
        new_theme = "Dark" if isDarkTheme() else "Light"
        self.config_mgr.theme = new_theme
        self.config_mgr.save()

        InfoBar.success(
            title="主题模式已切换",
            content=f"已同步更新系统的 Fluent / Mica 视觉效果并永久保留为 [{new_theme}]",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000,
        )

    @Slot(int)
    def _on_network_card_changed(self, index: int) -> None:
        """切换通信网卡触发。"""
        chosen_ip = self.net_combo.itemData(index)
        if not chosen_ip:
            return

        self.server_mgr.current_ip = chosen_ip
        self._update_qr_and_url(chosen_ip)

        InfoBar.info(
            title="通信网卡/IP 已切换",
            content=f"手机访问 IP 已切换为: {chosen_ip}",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000,
        )

    @Slot(str, QImage, str)
    def _on_photo_saved(self, file_path: str, qimg: QImage, info_str: str) -> None:
        """手机拍照传输成功触发。"""
        self._staged_count += 1
        path_obj = Path(file_path)

        self.video_widget.setPixmap(QPixmap.fromImage(qimg))
        self.preview_count_lbl.setText(f"本次启动已接收: {self._staged_count} 张照片")

        item_widget = PhotoItemWidget(
            file_path=file_path,
            qimg=qimg,
            info_str=info_str,
            on_delete_cb=self._on_delete_photo_item,
            parent=self.photo_list,
        )

        item = QListWidgetItem(self.photo_list)
        item.setSizeHint(QSize(300, 88))
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        self.photo_list.insertItem(0, item)
        self.photo_list.setItemWidget(item, item_widget)
        self.photo_list.setCurrentItem(item)

        self._update_list_ui()

        InfoBar.success(
            title="手机拍照保存成功",
            content=f"图片已保存为 {path_obj.name} 至当前保存目录",
            parent=self,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3500,
        )

    @Slot(str, str)
    def _on_client_connected(self, token: str, dev_name: str) -> None:
        count = len(self.server_mgr.active_devices)
        self.client_label.setText(f"已连接设备: {count} 台 ({dev_name})")
        InfoBar.info(
            title="手机设备已连接",
            content=f"{dev_name} 通过验证码配对成功",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000,
        )

    @Slot(str, str)
    def _on_client_disconnected(self, token: str, dev_name: str) -> None:
        count = len(self.server_mgr.active_devices)
        self.client_label.setText(f"已连接设备: {count} 台")

    def _on_refresh_pin(self) -> None:
        new_pin = self.server_mgr.generate_pin()
        self.pin_val_label.setText(new_pin)
        InfoBar.success(
            title="验证码已重置",
            content=f"最新配对验证码: {new_pin}",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000,
        )

    def _on_change_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "选择手机照片保存目录",
            str(self.save_dir),
            QFileDialog.Option.ShowDirsOnly,
        )
        if chosen:
            self.save_dir = Path(chosen).resolve()
            self.save_dir.mkdir(parents=True, exist_ok=True)
            self.config_mgr.save_dir = str(self.save_dir)
            self.config_mgr.save()

            self.server_mgr.save_dir = self.save_dir
            self.path_edit.setText(str(self.save_dir))

            InfoBar.success(
                title="保存目录已更改并保存",
                content=f"后续拍摄的照片将存入: {self.save_dir}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3500,
            )

    def _on_open_dir(self) -> None:
        if self.save_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.save_dir)))

    def _on_delete_photo_item(self, widget: PhotoItemWidget) -> None:
        if widget.path_obj.exists():
            try:
                widget.path_obj.unlink()
            except Exception as e:
                InfoBar.error(title="文件删除失败", content=str(e), parent=self)
                return

        for row in range(self.photo_list.count()):
            item = self.photo_list.item(row)
            w = self.photo_list.itemWidget(item)
            if w == widget:
                self.photo_list.takeItem(row)
                break

        self._update_list_ui()
        InfoBar.info(title="照片已彻底删除", content=f"从磁盘移除了文件: {widget.path_obj.name}", parent=self)

    def _on_clear_list(self) -> None:
        self.photo_list.clear()
        self._update_list_ui()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        w = self.photo_list.itemWidget(item)
        if isinstance(w, PhotoItemWidget):
            w._open_file()

    def _update_list_ui(self) -> None:
        count = self.photo_list.count()
        self.history_title.setText(f"已保存照片历史 ({count} 张)")
        self.clear_btn.setEnabled(count > 0)

    def closeEvent(self, event) -> None:
        self.server_mgr.stop_server()
        super().closeEvent(event)
