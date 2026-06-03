# -*- coding: utf-8 -*-
"""首次启动引导向导，帮助用户快速完成基础设置。"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

from . import scaling

# ── 与主界面统一的色系 ──
BG = "#f3f4f6"
CARD_BG = "#ffffff"
TEXT = "#20242a"
MUTED = "#6b7280"
LINE = "#e5e7eb"
BLUE = "#2f80ed"
GREEN = "#34a853"
YELLOW = "#fbbc04"
RED = "#ff6b5f"


class OnboardingWizard(ctk.CTkToplevel):
    """首次启动分步向导，5 页完成基础配置。"""

    TOTAL_PAGES = 5

    def __init__(
        self,
        parent: tk.Tk,
        config: dict[str, Any],
        on_complete: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(parent)
        self.title("欢迎使用健康提醒助手")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

        self._config = config
        self._on_complete = on_complete
        self._page_index = 0

        # ── 控件引用（各页填写后回读） ──
        self._work_start_var = tk.StringVar(value=config.get("work_time", {}).get("start", "08:30"))
        self._work_end_var = tk.StringVar(value=config.get("work_time", {}).get("end", "17:00"))
        self._dnd_enabled_var = tk.BooleanVar(value=config.get("do_not_disturb", {}).get("enabled", False))
        self._dnd_start_var = tk.StringVar(value=config.get("do_not_disturb", {}).get("start", "12:00"))
        self._dnd_end_var = tk.StringVar(value=config.get("do_not_disturb", {}).get("end", "13:00"))
        self._detection_mode = tk.StringVar(value="recommended")
        self._sedentary_var = tk.IntVar(value=config.get("reminders", {}).get("sedentary_interval_minutes", 45))
        self._water_var = tk.IntVar(value=config.get("reminders", {}).get("water_interval_minutes", 60))
        self._sound_var = tk.BooleanVar(value=True)
        self._volume_var = tk.IntVar(value=config.get("system", {}).get("sound_volume_percent", 80))

        # ── 窗口尺寸 & 居中 ──
        win_w, win_h = 620, 440
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.configure(fg_color=BG)

        # ── 顶部进度条 ──
        self._progress_frame = tk.Frame(self, bg=LINE, height=4)
        self._progress_frame.pack(fill="x", padx=40, pady=(24, 0))
        self._progress_bar = tk.Frame(self._progress_frame, bg=BLUE, height=4)

        # ── 内容区 ──
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True, padx=40, pady=(16, 0))

        # ── 底部按钮 ──
        btn_bar = tk.Frame(self, bg=BG)
        btn_bar.pack(fill="x", padx=40, pady=(0, 24))
        self._btn_prev = ctk.CTkButton(btn_bar, text="上一步", width=100,
                                        command=self._prev_page, fg_color=LINE, text_color=TEXT,
                                        hover_color="#d1d5db", font=scaling.font("Microsoft YaHei UI", 11))
        self._btn_prev.pack(side="left")
        self._btn_skip = ctk.CTkButton(btn_bar, text="跳过", width=80,
                                        command=self._on_skip, fg_color="transparent", text_color=MUTED,
                                        hover_color="#e5e7eb", font=scaling.font("Microsoft YaHei UI", 10))
        self._btn_skip.pack(side="left", padx=(12, 0))
        self._btn_next = ctk.CTkButton(btn_bar, text="下一步", width=110,
                                        command=self._next_page, fg_color=BLUE, text_color="white",
                                        hover_color="#1a6dd4", font=scaling.font("Microsoft YaHei UI", 11, "bold"))
        self._btn_next.pack(side="right")



        self.grab_set()
        self.bind("<Escape>", lambda _e: self._on_skip())
        self._render_page()

    # ══════════════════════════════════════
    # 页面切换
    # ══════════════════════════════════════

    def _render_page(self) -> None:
        """清空内容区，渲染当前页。"""
        for w in self._content.winfo_children():
            w.destroy()

        pages = [
            self._page_welcome,
            self._page_work_time,
            self._page_detection,
            self._page_reminders,
            self._page_done,
        ]
        pages[self._page_index]()

        # 进度条
        ratio = (self._page_index + 1) / self.TOTAL_PAGES
        bar_w = int(540 * ratio)
        self._progress_bar.place(x=0, y=0, width=bar_w, height=4)

        # 按钮状态
        self._btn_prev.configure(state="normal" if self._page_index > 0 else "disabled")
        if self._page_index == 0:
            self._btn_prev.pack_forget()
        else:
            self._btn_prev.pack(side="left")

        if self._page_index == self.TOTAL_PAGES - 1:
            self._btn_next.configure(text="开始使用", width=130)
            self._btn_skip.pack_forget()
        else:
            self._btn_next.configure(text="下一步", width=110)
            if not self._btn_skip.winfo_ismapped():
                self._btn_skip.pack(side="left", padx=(12, 0))

    def _next_page(self) -> None:
        if self._page_index < self.TOTAL_PAGES - 1:
            self._page_index += 1
            self._render_page()
        else:
            self._apply_and_close()

    def _prev_page(self) -> None:
        if self._page_index > 0:
            self._page_index -= 1
            self._render_page()

    def _on_skip(self) -> None:
        self.destroy()

    # ══════════════════════════════════════
    # 第 1 页：欢迎
    # ══════════════════════════════════════

    def _page_welcome(self) -> None:
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="🏥", font=("Segoe UI Emoji", 56), bg=BG).pack(pady=(32, 12))
        tk.Label(frame, text="欢迎使用健康提醒助手", bg=BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 20, "bold")).pack()
        tk.Label(frame, text="帮你管理久坐、喝水和前列腺健康的桌面小工具", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 12)).pack(pady=(8, 0))
        tk.Label(frame, text="它会安静地待在系统托盘里，在合适的时候提醒你起身和喝水。",
                 bg=BG, fg=MUTED, font=scaling.font("Microsoft YaHei UI", 11)).pack(pady=(4, 0))
        tk.Label(frame, text="接下来只需 1 分钟完成基础设置", bg=BG, fg=BLUE,
                 font=scaling.font("Microsoft YaHei UI", 11, "bold")).pack(pady=(20, 0))

    # ══════════════════════════════════════
    # 第 2 页：工作时间
    # ══════════════════════════════════════

    def _page_work_time(self) -> None:
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="⏰  工作时间", bg=BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", pady=(8, 4))
        tk.Label(frame, text="设置你的工作时间段，程序会在这段时间内主动提醒你。", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(anchor="w", pady=(0, 16))

        card = self._card(frame)
        # 上班 / 下班
        row1 = tk.Frame(card, bg=CARD_BG)
        row1.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(row1, text="上班时间", bg=CARD_BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(side="left")
        ctk.CTkEntry(row1, textvariable=self._work_start_var, width=90,
                      font=scaling.font("Microsoft YaHei UI", 12)).pack(side="right")

        row2 = tk.Frame(card, bg=CARD_BG)
        row2.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(row2, text="下班时间", bg=CARD_BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(side="left")
        ctk.CTkEntry(row2, textvariable=self._work_end_var, width=90,
                      font=scaling.font("Microsoft YaHei UI", 12)).pack(side="right")

        # 午休免打扰
        row3 = tk.Frame(card, bg=CARD_BG)
        row3.pack(fill="x", padx=20, pady=(8, 16))
        ctk.CTkSwitch(row3, text="午休免打扰", variable=self._dnd_enabled_var,
                       font=scaling.font("Microsoft YaHei UI", 11),
                       fg_color="#d1d5db", progress_color=BLUE).pack(side="left")
        ctk.CTkEntry(row3, textvariable=self._dnd_start_var, width=70,
                      font=scaling.font("Microsoft YaHei UI", 11)).pack(side="left", padx=(16, 4))
        tk.Label(row3, text="—", bg=CARD_BG, fg=MUTED).pack(side="left")
        ctk.CTkEntry(row3, textvariable=self._dnd_end_var, width=70,
                      font=scaling.font("Microsoft YaHei UI", 11)).pack(side="left", padx=(4, 0))

        tk.Label(frame, text="💡 下班后和午休时间不会弹出提醒", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(8, 0))

    # ══════════════════════════════════════
    # 第 3 页：检测模式
    # ══════════════════════════════════════

    def _page_detection(self) -> None:
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="🔍  检测模式", bg=BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", pady=(8, 4))
        tk.Label(frame, text="选择程序如何判断你是否在电脑前：", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(anchor="w", pady=(0, 12))

        modes = [
            ("recommended", "🎥  推荐模式", "键盘鼠标 + 摄像头联合检测",
             "最准确，能自动确认起身。摄像头仅在空闲时短暂开启，不保存画面。"),
            ("lightweight", "⌨️  轻量模式", "仅通过键盘鼠标判断",
             "不使用摄像头，起身判断需手动确认。适合无摄像头的用户。"),
            ("privacy", "🔒  隐私模式", "仅键盘鼠标，强化隐私保护",
             "关闭摄像头和中央弹窗，对隐私极度敏感的用户适用。"),
        ]
        for value, title, subtitle, desc in modes:
            self._mode_card(frame, value, title, subtitle, desc)

        tk.Label(frame, text="💡 你随时可以在设置里切换模式", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(8, 0))

    def _mode_card(self, parent, value, title, subtitle, desc) -> None:
        border_color = BLUE if self._detection_mode.get() == value else LINE
        card = tk.Frame(parent, bg=CARD_BG, highlightbackground=border_color,
                        highlightthickness=2, highlightcolor=border_color)
        card.pack(fill="x", pady=(0, 8))

        def _on_click(_e=None, v=value):
            self._detection_mode.set(v)
            self._render_page()

        card.bind("<Button-1>", _on_click)

        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill="x", padx=16, pady=10)
        inner.bind("<Button-1>", _on_click)

        tk.Label(inner, text=title, bg=CARD_BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        sub = tk.Label(inner, text=subtitle, bg=CARD_BG, fg=BLUE,
                       font=scaling.font("Microsoft YaHei UI", 10))
        sub.pack(anchor="w", pady=(2, 0))
        sub.bind("<Button-1>", _on_click)
        desc_label = tk.Label(inner, text=desc, bg=CARD_BG, fg=MUTED,
                              font=scaling.font("Microsoft YaHei UI", 9), wraplength=480, justify="left")
        desc_label.pack(anchor="w", pady=(2, 0))
        desc_label.bind("<Button-1>", _on_click)

    # ══════════════════════════════════════
    # 第 4 页：提醒方式
    # ══════════════════════════════════════

    def _page_reminders(self) -> None:
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="🔔  提醒方式", bg=BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", pady=(8, 4))
        tk.Label(frame, text="调整提醒间隔，找到适合你的节奏。", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(anchor="w", pady=(0, 16))

        card = self._card(frame)

        # 久坐间隔
        r1 = tk.Frame(card, bg=CARD_BG)
        r1.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(r1, text="久坐提醒间隔", bg=CARD_BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(side="left")
        self._sedentary_label = tk.Label(r1, text=f"{self._sedentary_var.get()} 分钟",
                                          bg=CARD_BG, fg=BLUE, font=scaling.font("Microsoft YaHei UI", 11, "bold"))
        self._sedentary_label.pack(side="right")
        s1 = ctk.CTkSlider(r1, from_=15, to=120, number_of_steps=21,
                            variable=self._sedentary_var, command=self._update_sedentary_label,
                            fg_color="#d1d5db", progress_color=BLUE, button_color=BLUE,
                            button_hover_color="#1a6dd4", width=220)
        s1.pack(side="right", padx=(12, 12))

        # 喝水间隔
        r2 = tk.Frame(card, bg=CARD_BG)
        r2.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(r2, text="喝水提醒间隔", bg=CARD_BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(side="left")
        self._water_label = tk.Label(r2, text=f"{self._water_var.get()} 分钟",
                                      bg=CARD_BG, fg=BLUE, font=scaling.font("Microsoft YaHei UI", 11, "bold"))
        self._water_label.pack(side="right")
        s2 = ctk.CTkSlider(r2, from_=15, to=120, number_of_steps=21,
                            variable=self._water_var, command=self._update_water_label,
                            fg_color="#d1d5db", progress_color=BLUE, button_color=BLUE,
                            button_hover_color="#1a6dd4", width=220)
        s2.pack(side="right", padx=(12, 12))

        # 提示音
        r3 = tk.Frame(card, bg=CARD_BG)
        r3.pack(fill="x", padx=20, pady=(8, 16))
        ctk.CTkSwitch(r3, text="提示音", variable=self._sound_var,
                       font=scaling.font("Microsoft YaHei UI", 11),
                       fg_color="#d1d5db", progress_color=BLUE).pack(side="left")
        ctk.CTkButton(r3, text="🔊 试听", width=70, fg_color=GREEN, text_color="white",
                       hover_color="#2d9348", font=scaling.font("Microsoft YaHei UI", 10),
                       command=self._test_sound).pack(side="right")

        tk.Label(frame, text="💡 提醒弹窗出现在屏幕右下角，10 分钟后自动消失", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(8, 0))

    def _update_sedentary_label(self, val) -> None:
        self._sedentary_label.configure(text=f"{int(float(val))} 分钟")

    def _update_water_label(self, val) -> None:
        self._water_label.configure(text=f"{int(float(val))} 分钟")

    def _test_sound(self) -> None:
        from ..platform.sound import play_ribbit
        play_ribbit(self._volume_var.get())

    # ══════════════════════════════════════
    # 第 5 页：完成
    # ══════════════════════════════════════

    def _page_done(self) -> None:
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="✅", font=("Segoe UI Emoji", 48), bg=BG).pack(pady=(24, 8))
        tk.Label(frame, text="设置完成！", bg=BG, fg=TEXT,
                 font=scaling.font("Microsoft YaHei UI", 18, "bold")).pack()
        tk.Label(frame, text="程序已最小化到系统托盘（屏幕右下角小箭头里）", bg=BG, fg=MUTED,
                 font=scaling.font("Microsoft YaHei UI", 11)).pack(pady=(4, 16))

        tips_frame = tk.Frame(frame, bg=CARD_BG, highlightbackground=LINE, highlightthickness=1)
        tips_frame.pack(fill="x", padx=40)
        tips = [
            ("🖱️ 左键点击", "托盘图标", "打开主界面"),
            ("🖱️ 右键点击", "托盘图标", "暂停提醒 / 退出"),
            ("💧 喝水提醒", "弹出时", "输入饮水量即可记录"),
            ("🚶 久坐提醒", "起身走动", "会被自动检测到"),
        ]
        for icon, key, val in tips:
            row = tk.Frame(tips_frame, bg=CARD_BG)
            row.pack(fill="x", padx=16, pady=3)
            tk.Label(row, text=f"{icon}  {key}", bg=CARD_BG, fg=TEXT,
                     font=scaling.font("Microsoft YaHei UI", 10)).pack(side="left")
            tk.Label(row, text=val, bg=CARD_BG, fg=MUTED,
                     font=scaling.font("Microsoft YaHei UI", 10)).pack(side="right")

        tk.Label(frame, text="祝你健康！", bg=BG, fg=GREEN,
                 font=scaling.font("Microsoft YaHei UI", 12, "bold")).pack(pady=(16, 0))

    # ══════════════════════════════════════
    # 辅助 & 保存
    # ══════════════════════════════════════

    def _card(self, parent) -> tk.Frame:
        """创建白色卡片容器。"""
        card = tk.Frame(parent, bg=CARD_BG, highlightbackground=LINE,
                        highlightthickness=1, highlightcolor=LINE)
        card.pack(fill="x", pady=(0, 12))
        return card

    def _apply_and_close(self) -> None:
        """读取各页控件值，写入配置，关闭向导。"""
        c = self._config
        c.setdefault("work_time", {})
        c["work_time"]["start"] = self._work_start_var.get()
        c["work_time"]["end"] = self._work_end_var.get()

        c.setdefault("do_not_disturb", {})
        c["do_not_disturb"]["enabled"] = bool(self._dnd_enabled_var.get())
        c["do_not_disturb"]["start"] = self._dnd_start_var.get()
        c["do_not_disturb"]["end"] = self._dnd_end_var.get()

        c.setdefault("reminders", {})
        c["reminders"]["sedentary_interval_minutes"] = int(self._sedentary_var.get())
        c["reminders"]["water_interval_minutes"] = int(self._water_var.get())

        c.setdefault("detection", {})
        mode = self._detection_mode.get()
        if mode == "recommended":
            c["detection"]["camera_enabled"] = True
            c["detection"]["privacy_mode"] = False
            c["detection"]["center_popup_enabled"] = True
        elif mode == "lightweight":
            c["detection"]["camera_enabled"] = False
            c["detection"]["privacy_mode"] = True
            c["detection"]["center_popup_enabled"] = False
        else:  # privacy
            c["detection"]["camera_enabled"] = False
            c["detection"]["privacy_mode"] = True
            c["detection"]["center_popup_enabled"] = False

        c.setdefault("system", {})
        c["system"]["sound_volume_percent"] = int(self._volume_var.get())

        c["onboarding_done"] = True

        self._on_complete(c)
        self.destroy()