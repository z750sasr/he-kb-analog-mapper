# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the 64-bit, windowed tray application."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

binaries = [("vendor/ViGEmClient.dll", ".")]
image_files = [str(path) for path in Path("images").glob("*.png")]
datas = [("controller_icons/*.png", "controller_icons")]
datas.extend((path, "images") for path in image_files)
application_icon = "images/icon.png" if Path("images/icon.png").is_file() else None
# The normal module graph finds Pillow and pystray. These two imports make the
# compiled hidapi extension and Windows tray backend explicit without bundling
# pystray's unused Linux and macOS implementations.
hiddenimports = [
    "hid",
    "pystray._win32",
    *collect_submodules("he_keyboard_mapper.keyboards"),
]

a = Analysis(
    ["HallAnalogMapper.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HallAnalogMapper",
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
    icon=application_icon,
)
