# 📱 LumaLink

[![Version](https://img.shields.io/badge/Version-v1.2-blue.svg)](https://github.com/Kipfel-log/LumaLink)
[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6%20%7C%20QFluentWidgets-005fb8.svg)](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**LumaLink**（中文名：**拾光**）是一款基于 Python、PySide6 和 QFluentWidgets 开发的现代化局域网无线拍照桌面应用程序。它内置轻量级局域网 HTTP Web 服务器，允许手机在无需安装任何 App 的情况下，通过扫描二维码或访问 URL 连接到电脑，输入 6 位动态 PIN 码安全配对后，直接使用手机摄像头拍照或上传图片，并实时无感推送到电脑端自动重命名归档。

此外，应用还支持等比例自适应大图预览、自定义自动重命名规则、历史照片文件管理以及 Windows 11 Fluent 风格界面（含 Mica 云母半透明材质与深浅色主题）。

---

## ✨ 核心特性

- **📱 局域网扫码 / 网页无线拍照**
  - **零 App 安装**：手机自带浏览器 / 相机扫码即用，兼容 iOS 与 Android 原生系统相机和相册。
  - **安全 PIN 码配对**：动态生成 6 位 PIN 验证码，支持 6 位自动提交与 5 分钟超时刷新机制。
  - **智能网卡检测**：自动识别系统物理网卡、Wi-Fi、热点等多 IP 地址，支持在界面中自由切换通信网卡。
  - **实时预分配序号**：手机端 H5 界面实时显示下一张拍摄照片的预分配编号（如 `#001 (IMG_001.jpg)`）。
  - **无感实时推送**：手机拍照上传后，电脑端主界面秒级接收、显示并保存。

- **🔢 智能自动命名与保存**
  - **自定义重命名规则**：可配置前缀（如 `IMG_`）、起始/当前序号、补零位数（如 3 位 `001`）。
  - **自动自增与持久化**：每次拍照成功后序号自动 +1 并实时持久化保存到配置文件，防止重启或重复覆盖。
  - **灵活的回退机制**：未开启自动重命名时，自动降级为精确到秒的时间戳命名格式。

- **🖼️ 居中自适应预览与历史管理**
  - **100% 比例居中渲染 (`AspectVideoWidget`)**：无论窗口如何缩放，画帧与照片均保持原始宽高比展示，绝不变形拉伸。
  - **历史卡片流**：展示已接收/采集照片的缩略图、文件名、拍摄时间/设备、分辨率及文件大小。
  - **快捷文件操作**：一键在 Windows 资源管理器中定位文件、用系统默认查看器打开原图或从磁盘彻底删除。

- **🎨 Modern Fluent UI 极简设计**
  - 基于 QFluentWidgets 打造 Modern Windows 11 Fluent 风格。
  - 支持 Windows 11 Mica 云母半透明材质效果。
  - 支持跟随系统 / 浅色模式 / 深色模式全局一键切换。

---

## 📁 目录结构

```text
Photo/
├── main.py                   # 应用程序主入口
├── main_window.py            # Fluent 主窗口 (无线拍照主页、设置页与历史管理)
├── mobile_server.py          # 嵌入式局域网 HTTP 服务器与手机 H5 网页
├── config_manager.py         # AppConfig 配置持久化管理 (config.json)
├── config.json               # 应用程序同级目录 JSON 配置文件 (自动生成)
├── aspect_video_widget.py    # 自适应等比例居中画面渲染控件
└── qr_utils.py               # 二维码生成工具
```

---

## 🛠️ 环境要求与依赖安装

### 环境要求
- **Python**: `3.8` 或更高版本
- **操作系统**: Windows 10/11 (推荐), macOS, Linux

### 依赖安装

在命令行或终端中运行以下命令安装必要的 Python 依赖包：

```bash
pip install PySide6 qfluentwidgets qrcode Pillow
```

---

## 🚀 快速开始

### 1. 运行程序

在项目根目录下，执行以下命令启动应用：

```bash
python main.py
```

### 2. 手机无线拍照流程

1. **连接相同局域网**：确保电脑与手机连接在同一个 Wi-Fi 或局域网下（或手机开启热点供电脑连接）。
2. **扫码或访问 URL**：
   - 打开电脑软件主界面，使用手机扫描左侧展示的二维码；
   - 或在手机浏览器地址栏中直接输入显示的 URL（例如 `http://192.168.1.100:8989`）。
3. **输入 PIN 码**：在手机页面中输入电脑屏幕上显示的 6 位验证码（输入满 6 位后自动校验配对）。
4. **拍照上传**：配对成功后，点击手机端的 **“点击拍摄 / 选取照片”** 卡片，选择拍照或从相册上传照片。
5. **实时接收**：电脑端主界面将实时接收并展示照片，同时按配置规则自动保存到指定目录中！

---

## ⚙️ 配置说明

应用程序会在软件根目录（同级路径）下自动创建 JSON 配置文件 `config.json`。你可以在软件的 **“应用设置”** 页面中直接修改以下配置，也可以直接编辑 `config.json` 文件：

| 设置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| **照片保存目录** | `~/Pictures/MobilePhotos` | 照片自动保存的本地绝对路径 |
| **通信服务端口** | `8989` | 手机端访问的 HTTP 端口 |
| **外观主题** | `Auto` | 可选 `Auto` (跟随系统)、`Light` (浅色)、`Dark` (深色) |
| **自动重命名** | `True` | 是否启用按序号规则自动重命名照片 |
| **文件名前缀** | `IMG_` | 重命名文件名前缀 |
| **起始/当前序号** | `1` | 计数的当前起始编号 |
| **补零位数** | `3` | 编号补零位数（如 3 位对应 `001`, `002`） |

---

## 👤 开发者与关于

- **项目名称**：LumaLink (中文名：**拾光**)
- **软件版本**：`v1.2`
- **GitHub 开发者**：[Kipfel-Log](https://github.com/Kipfel-log)
- **项目开源仓库**：[Kipfel-log/LumaLink](https://github.com/Kipfel-log/LumaLink)

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 协议开源，欢迎自由使用、修改与分发。
