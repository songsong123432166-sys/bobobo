# -*- coding: utf-8 -*-
"""UI 工具函数：动画、格式化等共享逻辑。"""

from __future__ import annotations

import tkinter as tk


def slide_window(
    win: tk.Toplevel,
    start_x: int,
    target_x: int,
    target_y: int,
    step: int = 0,
    total_steps: int = 18,
) -> None:
    """平滑滑入动画，用于弹窗从屏幕边缘滑入。"""
    if step > total_steps:
        return
    t = step / total_steps
    ease = t * t * (3 - 2 * t)
    current_x = int(start_x + (target_x - start_x) * ease)
    try:
        win.geometry(f"+{current_x}+{target_y}")
    except tk.TclError:
        return
    win.after(14, lambda: slide_window(win, start_x, target_x, target_y, step + 1, total_steps))


def format_duration(seconds: int) -> str:
    """将秒数格式化为X小时XX分。"""
    minutes = max(0, seconds) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}小时{minutes:02d}分"


def metric_value(data: dict, key: str) -> int:
    """安全获取数据指标值。"""
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get(key, 0))
    except (TypeError, ValueError):
        return 0
