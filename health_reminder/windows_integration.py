import ctypes
import sys
from pathlib import Path

from .constants import APP_NAME


try:
    import winreg
except ImportError:
    winreg = None


def configure_tcl_tk_for_frozen_app():
    if not getattr(sys, "frozen", False):
        return

    base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    tcl_dir = base_dir / "tcl" / "tcl8.6"
    tk_dir = base_dir / "tcl" / "tk8.6"

    if tcl_dir.exists():
        import os

        os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
    if tk_dir.exists():
        import os

        os.environ.setdefault("TK_LIBRARY", str(tk_dir))


def get_startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    python_exe = pythonw if pythonw.exists() else Path(sys.executable)
    script_path = Path(sys.argv[0]).resolve()
    return f'"{python_exe}" "{script_path}"'


def set_startup(enabled, log):
    if winreg is None:
        log.write("当前系统不支持写入开机启动项")
        return False

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_startup_command())
                log.write("已开启开机自启")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
                log.write("已关闭开机自启")
        return True
    except OSError as exc:
        log.write(f"更新开机自启失败：{exc}")
        return False


def start_screensaver(notify, log):
    if not sys.platform.startswith("win"):
        notify("屏保", "当前系统不支持 Windows 屏保命令")
        return

    try:
        hwnd_broadcast = 0xFFFF
        wm_syscommand = 0x0112
        sc_screensave = 0xF140
        ctypes.windll.user32.SendMessageW(
            hwnd_broadcast,
            wm_syscommand,
            sc_screensave,
            0,
        )
        log.write("已发送进入屏保命令")
    except Exception as exc:
        notify("屏保", f"启动屏保失败：{exc}")
