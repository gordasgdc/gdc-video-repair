# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — macOS build (.app)
# Ruleaza din radacina repo-ului:  pyinstaller build/build-mac.spec

import os

block_cipher = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))

_icon_path = os.path.join(ROOT, "icon", "icon.icns")
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
    [],
    exclude_binaries=True,
    name="GDCVideoRepair",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GDCVideoRepair",
)

app = BUNDLE(
    coll,
    name="GDCVideoRepair.app",
    icon=ICON,
    bundle_identifier="com.gordasgdc.videorepair",
    info_plist={
        "CFBundleName": "GDC Video Repair",
        "CFBundleDisplayName": "GDC Video Repair",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "NSHumanReadableCopyright": "© Cristi Gordas (GDC)",
    },
)
