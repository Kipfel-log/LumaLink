"""build_exe.py — LumaLink 自动打包脚本。

解决 PySide6 + Conda 环境下 DLL load failed while importing QtCore 问题的完美打包配置。
将完整收集 PySide6, shiboken6, qfluentwidgets 的原生 C++ 动态链接库 (.dll)。
"""
import subprocess
import sys


def build() -> None:
    print("🚀 开始打包 LumaLink 为独立 EXE 可执行程序...")

    # 1. 确保安装 PyInstaller
    try:
        import PyInstaller  # type: ignore # noqa: F401
    except ImportError:
        print("📦 正在自动安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. PyInstaller 打包参数配置 (完整搜集 PySide6 & Shiboken6 C++ DLLs)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",                     # 隐藏黑色的 CMD 命令行控制台窗口
        "--onedir",                        # 推荐目录独立绿色包 (最稳定，防止 Conda DLL 路径冲突，启动秒开)
        "--name=LumaLink",                 # 生成的程序文件夹与 EXE 名称
        "--collect-all=PySide6",           # 强制搜集所有 PySide6 核心 DLL (Qt6Core, Qt6Gui, Qt6Widgets 等)
        "--collect-all=shiboken6",         # 搜集 Shiboken C++ 绑定库
        "--collect-all=qfluentwidgets",    # 搜集 QFluentWidgets UI 图标与资源
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtNetwork",
        "--hidden-import=PySide6.QtSvg",
        "--icon=assets/lumalink_icon_mark.png",  # 设置生成的 EXE 程序图标
        "--add-data=assets;assets",        # 将 assets 静态资源文件夹打入程序中
        "--clean",                         # 清理旧的打包临时缓存
        "main.py",
    ]

    print("🔨 执行打包指令:")
    print("   " + " ".join(cmd))
    print("--------------------------------------------------")

    # 3. 执行打包
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("--------------------------------------------------")
        print("🎉 打包成功！生成的独立绿色软件包位于:")
        print("👉 dist/LumaLink/LumaLink.exe")
        print("\n💡 提示：打包生成的 `dist/LumaLink` 文件夹包含了全部运行环境！")
        print("只需要把 `LumaLink` 文件夹打包压缩为 .zip 发给别人，别人解压后双击 `LumaLink.exe` 即可运行！")
    else:
        print("❌ 打包失败，请检查上方日志输出。")


if __name__ == "__main__":
    build()
