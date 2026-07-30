# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files
import os, glob

PYSIDE6_DIR = r"C:\data\apps\python\Lib\site-packages\PySide6"
SHIBOKEN6_DIR = r"C:\data\apps\python\Lib\site-packages\shiboken6"

datas = [('assets', 'assets')]
binaries = []
hiddenimports = ['qfluentwidgets']

tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('shiboken6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# 强制覆盖：直接把正确环境的关键 DLL 写入 binaries，防止 AppData 旁加载版本混入
_key_dlls = [
    "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll", "Qt6Network.dll",
    "Qt6Svg.dll", "Qt6SvgWidgets.dll", "Qt6PrintSupport.dll", "Qt6OpenGL.dll",
    "Qt6OpenGLWidgets.dll", "Qt6Xml.dll",
    "pyside6.abi3.dll", "pyside6qml.abi3.dll",
    "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll",
    "concrt140.dll", "vcamp140.dll", "vcomp140.dll",
]
for _dll in _key_dlls:
    _src = os.path.join(PYSIDE6_DIR, _dll)
    if os.path.exists(_src):
        binaries = [b for b in binaries if os.path.basename(b[0]).lower() != _dll.lower()]
        binaries.append((_src, 'PySide6'))

# shiboken6 DLL
for _f in glob.glob(os.path.join(SHIBOKEN6_DIR, "*.dll")):
    _name = os.path.basename(_f)
    binaries = [b for b in binaries if os.path.basename(b[0]).lower() != _name.lower()]
    binaries.append((_f, 'shiboken6'))

datas += collect_data_files('qfluentwidgets')

# 安全过滤：剔除所有来自 AppData 或 PyQt6 目录的二进制文件，防止版本污染
_bad_prefixes = (
    r"C:\Users\25227\AppData".lower(),
    "pyqt6",
)
binaries = [
    b for b in binaries
    if not any(p in b[0].lower() for p in _bad_prefixes)
]

excludes = [
    # 排除大第三方科学计算与框架
    'numpy',
    'scipy',
    'matplotlib',
    'pycparser',
    'PyQt5',
    'PyQt6',
    'tkinter',
    'torch',
    'PIL.ImageTk',

    # 排除 Qt 3D 相关全部模块
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DExtras',
    'PySide6.QtQuick3D',
    'PySide6.QtQuick3DPhysics',
    'PySide6.QtQuick3DSpatialAudio',
    'PySide6.QtQuick3DUtils',

    # 排除 Qt WebEngine 浏览器内核 (极其臃肿 150MB+)
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtWebChannel',
    'PySide6.QtWebView',

    # 排除 Qt Quick / QML / Designer
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQuickControls2',
    'PySide6.QtQml',
    'PySide6.QtDesigner',
    'PySide6.QtUiTools',

    # 排除 Qt 音视频多媒体与空间音频
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtSpatialAudio',
    'PySide6.QtTextToSpeech',

    # 排除硬件/串口/传感器/SQL/定位
    'PySide6.QtBluetooth',
    'PySide6.QtNfc',
    'PySide6.QtPositioning',
    'PySide6.QtSensors',
    'PySide6.QtSerialBus',
    'PySide6.QtSerialPort',
    'PySide6.QtSql',
    'PySide6.QtStateMachine',
    'PySide6.QtTest',
    'PySide6.QtCharts',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LumaLink',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\lumalink_icon_mark.png'],
)