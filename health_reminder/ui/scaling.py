# -*- coding: utf-8 -*-
"""
分辨率自适应缩放模块。

根据屏幕分辨率自动调整字体大小，
确保在不同分辨率下都有合适的显示效果。
"""

from __future__ import annotations

import tkinter as tk

_BASE_WIDTH = 1920
_BASE_HEIGHT = 1080

_root: tk.Tk | None = None
_screen_w: int = 0
_screen_h: int = 0
_font_scale: float = 1.0
_initialized: bool = False


def init(root: tk.Tk | None = None) -> None:
    """初始化缩放系统，检测屏幕参数。"""
    global _root, _screen_w, _screen_h, _font_scale, _initialized
    if _initialized:
        return

    _root = root
    try:
        _screen_w = root.winfo_screenwidth() if root else 1920
        _screen_h = root.winfo_screenheight() if root else 1080
    except Exception:
        _screen_w, _screen_h = 1920, 1080

    res_scale = min(_screen_w / _BASE_WIDTH, _screen_h / _BASE_HEIGHT)
    _font_scale = max(1.0, res_scale)
    _initialized = True


def s(value: int | float) -> int:
    """缩放一个数值（像素值等），当前不缩放。"""
    return int(value)


def sf(value: float) -> float:
    """缩放浮点数，当前不缩放。"""
    return value


def font(family: str = "Microsoft YaHei UI", size: int = 10, *styles: str) -> tuple:
    """生成缩放后的字体元组，字体自动放大加粗。

    用法: font("Microsoft YaHei UI", 14, "bold")
    """
    if not _initialized:
        init()
    scaled_size = int(size * _font_scale)
    if "bold" not in styles:
        styles = ("bold",) + styles
    return (family, scaled_size) + styles


def geometry(width: int, height: int) -> str:
    """生成窗口尺寸字符串，如 '980x650'（不缩放）。"""
    return f"{width}x{height}"


def padding(x: int, y: int) -> tuple[int, int]:
    """生成内边距 (padx, pady)（不缩放）。"""
    return x, y


def get_font_scale() -> float:
    """获取字体缩放比例。"""
    if not _initialized:
        init()
    return _font_scale


def get_scale() -> float:
    """获取缩放比例（始终为1.0）。"""
    return 1.0


def get_screen_size() -> tuple[int, int]:
    """获取屏幕分辨率。"""
    if not _initialized:
        init()
    return _screen_w, _screen_h
