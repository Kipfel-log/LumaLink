"""
诊断 PyInstaller 打包后 DLL 缺失或冲突问题
直接运行：python diag_build.py
"""
import os
import sys
from pathlib import Path
import subprocess

DIST_DIR = Path(r"C:\data\project\Photo\dist\LumaLink\_internal")
PYSIDE6_SITE = Path(r"C:\data\apps\python\Lib\site-packages\PySide6")

print("=== 1. 检查 dist/_internal 目录是否存在 ===")
if DIST_DIR.exists():
    print(f"OK: {DIST_DIR}")
else:
    print(f"MISSING: {DIST_DIR}")
    sys.exit(1)

print("\n=== 2. 检查 dist/_internal/PySide6 中的关键 DLL ===")
pyside_dist = DIST_DIR / "PySide6"
key_dlls = ["Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll", "Qt6Network.dll", "Qt6Svg.dll"]
for dll in key_dlls:
    path = pyside_dist / dll
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    print(f"  {'OK' if exists else 'MISSING'}: {dll} ({size:,} bytes)")

print("\n=== 3. 检查 VCRUNTIME DLLs ===")
vcruntime_dlls = ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll"]
for dll in vcruntime_dlls:
    # 检查dist下是否有
    in_dist = (DIST_DIR / dll).exists()
    in_pyside = (pyside_dist / dll).exists()
    print(f"  {dll}: dist={in_dist}, pyside6_dist={in_pyside}")

print("\n=== 4. 检查 dist 目录文件总数 ===")
if DIST_DIR.exists():
    all_files = list(DIST_DIR.rglob("*.dll"))
    print(f"  共找到 {len(all_files)} 个 DLL")
    
print("\n=== 5. 用 dumpbin 检查 Qt6Core.dll 依赖 ===")
qt6core = pyside_dist / "Qt6Core.dll"
if qt6core.exists():
    try:
        result = subprocess.run(
            ["dumpbin", "/IMPORTS", str(qt6core)],
            capture_output=True, text=True, timeout=15
        )
        lines = result.stdout.splitlines()
        # 只打印 DLL 依赖行
        for line in lines:
            if ".dll" in line.lower():
                print(f"  {line.strip()}")
    except Exception as e:
        print(f"  dumpbin 不可用: {e}")
        # 用 python-pefile 替代
        try:
            import pefile
            pe = pefile.PE(str(qt6core))
            print("  依赖 DLL (via pefile):")
            for entry in pe.DIRECTORY_ENTRY_IMPORT:
                print(f"    {entry.dll.decode()}")
        except ImportError:
            print("  pefile 未安装，跳过依赖分析")

print("\n=== 6. 检查 Qt6Core.dll 在 dist 与 site-packages 的大小是否一致 ===")
dist_core = pyside_dist / "Qt6Core.dll"
src_core = PYSIDE6_SITE / "Qt6Core.dll"
if dist_core.exists() and src_core.exists():
    d_size = dist_core.stat().st_size
    s_size = src_core.stat().st_size
    match = d_size == s_size
    print(f"  dist: {d_size:,} bytes")
    print(f"  source: {s_size:,} bytes")
    print(f"  一致: {match}")

print("\nDone.")
