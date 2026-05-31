from __future__ import annotations

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE = "HealthTrayReminder"


def current_command() -> str:
    """获取当前启动快捷方式指向的命令。"""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    return f'"{Path(sys.executable)}" -m health_reminder'


def is_enabled() -> bool:
    """检查当前是否已设置开机自启。"""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_VALUE)
            return True
    except Exception:
        return False


def set_enabled(enabled: bool) -> bool:
    """启用或禁用开机自启（通过Windows启动文件夹快捷方式）。"""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_VALUE, 0, winreg.REG_SZ, current_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
