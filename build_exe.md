# LumaLink 打包与编译指南

本项目支持使用 **PyInstaller** 或 **Nuitka** 将应用打包为 Windows 可执行程序。

---

## 1. Nuitka 方案（推荐 🚀，C++ 原生编译，秒级启动）

Nuitka 将 Python 源码编译为原生 C++ 机器码，彻底消除解包延迟与 CPU 解压开销，启动速度提升数倍。

### 准备环境
```bash
pip install nuitka zstandard
```
> **注意**：Nuitka 第一次运行若提示缺少 C++ 编译器（如 GCC/MSVC），按提示回车 `y` 即可自动下载并安装 MinGW64 编译器。

### 一键打包命令
```bash
# 1. 独立文件夹模式 (推荐，启动速度最快)
python build_nuitka.py --mode standalone

# 2. 单文件 EXE 模式
python build_nuitka.py --mode onefile

# 3. 或直接双击运行脚本
build_nuitka.bat
```
打包产物位于 `dist_nuitka/` 目录。

---

## 2. PyInstaller 方案（传统方式）

```bash
# 1. 文件夹模式打包 (onedir)
pyinstaller --clean --noconfirm LumaLink.spec

# 2. 单文件模式打包 (onefile)
pyinstaller --clean --noconfirm LumaLink_oneflie.spec
```
打包产物位于 `dist/` 目录。