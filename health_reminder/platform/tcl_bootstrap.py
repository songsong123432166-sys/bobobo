from __future__ import annotations

import os
import sys
from pathlib import Path



def _enable_dpi_awareness() -> None:
    """Enable per-monitor DPI awareness for crisp text on high-DPI displays."""
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

def configure_tcl_tk() -> None:
    """Point tkinter at bundled Tcl/Tk folders before the first Tk import."""
    bases = [
        Path(getattr(sys, "_MEIPASS", "")),
        Path(sys.executable).resolve().parent,
        Path(sys.base_prefix),
        Path(sys.exec_prefix),
    ]

    for base in bases:
        if not str(base):
            continue
        _add_dll_dir(base)
        _add_dll_dir(base / "DLLs")
        tcl_root = _find_tcl_root(base)
        if tcl_root is None:
            continue
        tcl = tcl_root / "tcl8.6"
        tk = tcl_root / "tk8.6"
        if (tcl / "init.tcl").exists():
            os.environ.setdefault("TCL_LIBRARY", str(tcl))
        if (tk / "tk.tcl").exists():
            os.environ.setdefault("TK_LIBRARY", str(tk))
        return


def _find_tcl_root(base: Path) -> Path | None:
    """在给定路径下查找Tcl库根目录。"""
    candidates = [
        base / "tcl",
        base / "_internal" / "tcl",
        base / "lib" / "tcl",
        base.parent / "tcl",
    ]
    for candidate in candidates:
        if (candidate / "tcl8.6" / "init.tcl").exists():
            return candidate
    return None


def _add_dll_dir(path: Path) -> None:
    """将目录添加到DLL搜索路径，确保Tcl/Tk依赖库能被找到。"""
    if not path.exists() or not hasattr(os, "add_dll_directory"):
        return
    try:
        os.add_dll_directory(str(path))
    except (tk.TclError, AttributeError):
        pass
