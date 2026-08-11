# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Windows build (.exe)
# Ruleaza din radacina repo-ului:  pyinstaller build/build-windows.spec

import os

block_cipher = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))

_icon_path = os.path.join(ROOT, "icon", "icon.ico")
ICON = _icon_path if os.path.isfile(_icon_path) else None

a = Analysis(
    [os.path.join(ROOT, "src", "gui.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="GDCVideoRepair",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=ICON,
)
