# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files


block_cipher = None
project_root = Path.cwd()


def collect_tk_binaries():
    binaries = []
    candidates = [
        Path(sys.base_prefix) / "DLLs",
        Path(sys.base_prefix),
        Path(sys.exec_prefix) / "DLLs",
        Path(sys.exec_prefix),
    ]
    for folder in candidates:
        if not folder.exists():
            continue
        for name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll"):
            path = folder / name
            if path.exists():
                binaries.append((str(path), "."))
    return binaries


def collect_tk_datas():
    datas = []
    for base in (Path(sys.base_prefix), Path(sys.exec_prefix)):
        tcl_root = base / "tcl"
        if not tcl_root.exists():
            continue
        for folder_name in ("tcl8.6", "tk8.6"):
            folder = tcl_root / folder_name
            if folder.exists():
                datas.append((str(folder), f"tcl/{folder_name}"))
    return datas


datas = collect_data_files("health_reminder", includes=["assets/**", "models/**"])
datas += collect_tk_datas()

a = Analysis(
    ["health_reminder/__main__.py"],
    pathex=[str(project_root)],
    binaries=collect_tk_binaries(),
    datas=datas,
    hiddenimports=[
        "PIL._tkinter_finder",
        "pystray._win32",
        "schedule",
        "cv2",
        "pycaw.pycaw",
        "comtypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    name="HealthTrayReminder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
