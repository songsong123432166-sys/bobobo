from __future__ import annotations

import ctypes
import sys


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def seconds_since_last_input() -> float:
    if sys.platform != "win32":
        return 0.0
    try:
        last_input = LASTINPUTINFO()
        last_input.cbSize = ctypes.sizeof(last_input)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input)):
            return 0.0
        tick_count = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (tick_count - last_input.dwTime) / 1000.0)
    except Exception:
        return 0.0
