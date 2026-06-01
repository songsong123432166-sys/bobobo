"""记录日历页面模块，从主界面拆分而来。"""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Any

import customtkinter as ctk
from . import scaling

BG = "#f3f4f6"
TEXT = "#20242a"
MUTED = "#6b7280"
LINE = "#e5e7eb"
BLUE = "#2f80ed"
GREEN = "#34a853"
YELLOW = "#fbbc04"
RED = "#ff6b5f"


def format_duration(seconds: int) -> str:
    """将秒数格式化为 X小时XX分 的形式。"""
    minutes = max(0, seconds) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}小时{minutes:02d}分"


def metric_value(data: dict[str, Any], key: str) -> int:
    """从字典中安全读取整数指标值。"""
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get(key, 0))
    except (TypeError, ValueError):
        return 0


class CalendarPageMixin:
    """记录日历页面 Mixin，提供日历视图和历史图表方法。"""


    def _weekly_summary(self) -> str:
        history = self.state.history()
        days = sorted(history.items(), reverse=True)[:7]
        if not days:
            return "暂无历史数据"
        avg_water = sum(metric_value(data, "water_count") for _day, data in days) / len(days)
        avg_stand = sum(metric_value(data, "stand_count") for _day, data in days) / len(days)
        max_sit = max(metric_value(data, "max_sit_streak_minutes") for _day, data in days)
        return f"近7天 日均喝水{avg_water:.1f}次，起身{avg_stand:.1f}次，最长久坐{max_sit}分钟"

    def _daily_metrics(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg="white")
        box.pack(fill="x", padx=18, pady=(12, 14))
        metrics = [
            ("今日喝水", "water_count", BLUE),
            ("今日起身", "stand_count", GREEN),
            ("今日离席", "away_count", YELLOW),
            ("久坐提醒", "sedentary_alerts", RED),
        ]
        for index, (label, key, color) in enumerate(metrics):
            item = tk.Frame(box, bg="#f9fafb", highlightbackground="#dfe4ea", highlightthickness=1)
            item.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 8, 0), pady=0)
            tk.Label(item, text=label, bg="#f9fafb", fg=MUTED, font=scaling.font("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10,
                pady=(8, 2))
            value = tk.Label(item, text="", bg="#f9fafb", fg=color, font=scaling.font("Microsoft YaHei UI", 14, "bold"))
            value.pack(anchor="w", padx=10, pady=(0, 8))
            self._visual_labels[key] = value
            box.columnconfigure(index, weight=1)



    def _build_calendar(self, parent: tk.Frame) -> None:
        self._header(parent, "记录日历", "查看每天喝水、起身、离席和电脑使用时长。")
        cal_card = self._card(parent, "月历视图")
        cal_card.pack(fill="x", padx=28, pady=(0, 14))
        self._month_calendar(cal_card)

        detail_card = self._card(parent, "当日数据")
        detail_card.pack(fill="x", padx=28, pady=(0, 14))
        self._selected_day_detail(detail_card)

        week_card = self._card(parent, "本周总结")
        week_card.pack(fill="x", padx=28, pady=(0, 14))
        self._weekly_summary_card(week_card)

        history_card = self._card(parent)
        history_card.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self._history_switcher(history_card)

    def _weekly_summary_card(self, parent: tk.Frame) -> None:
        body = tk.Frame(parent, bg="white")
        body.pack(fill="x", padx=18, pady=(0, 16))
        tk.Label(
            body,
            text=self._weekly_summary(),
            bg="white",
            fg=TEXT,
            font=scaling.font("Microsoft YaHei UI", 11, "bold"),
            wraplength=720,
            justify="left",
        ).pack(anchor="w")

    def _month_calendar(self, parent: tk.Frame) -> None:
        now = datetime.now()
        history = self.state.history()
        grid = tk.Frame(parent, bg="white")
        grid.pack(fill="x", padx=18, pady=12)
        for index, name in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            tk.Label(grid, text=name, bg="white", fg=MUTED, font=scaling.font("Microsoft YaHei UI", 9)).grid(row=0, column=index,
                sticky="ew", pady=4)
        for row, week in enumerate(calendar.monthcalendar(now.year, now.month), start=1):
            for col, day in enumerate(week):
                self._calendar_cell(grid, row, col, now.year, now.month, day, history)
        for col in range(7):
            grid.columnconfigure(col, weight=1, uniform="calendar")

    def _calendar_cell(self, grid: tk.Frame, row: int, col: int, year: int, month: int, day: int, history: dict[str,
        Any]) -> None:
        label = "" if day == 0 else str(day)
        key = f"{year}-{month:02d}-{day:02d}" if day else ""
        data = history.get(key, {})
        selected = key == self._selected_day
        color = GREEN if data.get("water_count", 0) >= 4 else BLUE if data else "#f9fafb"
        if selected:
            color = "#111827"
        cell = tk.Frame(grid, bg=color, height=50, highlightbackground="#ffffff", highlightthickness=2)
        cell.grid(row=row, column=col, sticky="nsew")
        cell.pack_propagate(False)
        text_color = "white" if data or selected else MUTED
        day_label = tk.Label(cell, text=label, bg=color, fg=text_color, font=scaling.font("Microsoft YaHei UI", 10, "bold"))
        day_label.pack(expand=True)
        if day:
            cell.bind("<Button-1>", lambda _event, item=key: self._select_day(item))
            day_label.bind("<Button-1>", lambda _event, item=key: self._select_day(item))

    def _select_day(self, day: str) -> None:
        self._selected_day = day
        self._render_page()

    def _selected_day_detail(self, parent: tk.Frame) -> None:
        data = self.state.history().get(self._selected_day, {})
        values = [
            ("日期", self._selected_day, BLUE),
            ("喝水", f"{metric_value(data, 'water_count')} 次", BLUE),
            ("起身", f"{metric_value(data, 'stand_count')} 次", GREEN),
            ("离席", f"{metric_value(data, 'away_count')} 次", YELLOW),
            ("电脑使用", format_duration(metric_value(data, "computer_seconds")), RED),
        ]
        row = tk.Frame(parent, bg="white")
        row.pack(fill="x", padx=18, pady=(0, 16))
        for index, (label, value, color) in enumerate(values):
            box = tk.Frame(row, bg="white")
            box.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 12, 0))
            tk.Label(box, text=label, bg="white", fg=MUTED, font=scaling.font("Microsoft YaHei UI", 9)).pack(anchor="w")
            tk.Label(box, text=value, bg="white", fg=color, font=scaling.font("Microsoft YaHei UI", 12, "bold")).pack(anchor="w",
                pady=(4, 0))
            row.columnconfigure(index, weight=1)

    def _history_switcher(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg="white")
        header.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(header, text="历史统计", bg="white", fg=TEXT, font=scaling.font("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        ttk.Button(header, text="柱状统计图", command=lambda: self._set_history_mode("chart")).pack(side="right", padx=(8,
            0))
        ttk.Button(header, text="列表视图", command=lambda: self._set_history_mode("list")).pack(side="right")
        body = tk.Frame(parent, bg="white")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self._history_body = body
        self._render_history_body()

    def _set_history_mode(self, mode: str) -> None:
        if self._history_mode == mode:
            return
        self._history_mode = mode
        if self.page == "calendar" and self._history_body is not None and self._history_body.winfo_exists():
            self._render_history_body()
            if self.scroll_page is not None:
                self.scroll_page.canvas.configure(scrollregion=self.scroll_page.canvas.bbox("all"))
            return
        self._render_page()

    def _render_history_body(self) -> None:
        if self._history_body is None:
            return
        for child in self._history_body.winfo_children():
            child.destroy()
        if self._history_mode == "chart":
            self._history_chart(self._history_body)
        else:
            self._history_list(self._history_body)

    def _history_chart(self, parent: tk.Frame) -> None:
        history = dict(sorted(self.state.history().items(), reverse=True)[:14])
        days = list(reversed(list(history.keys())))
        canvas = tk.Canvas(parent, height=260, bg="white", highlightthickness=0)
        canvas.pack(fill="x", expand=True)
        if not days:
            canvas.create_text(360, 120, text="暂无历史数据", fill=MUTED, font=scaling.font("Microsoft YaHei UI", 11))
            return
        width = 760
        left, top, bottom = 42, 20, 218
        group = max(34, (width - left - 20) // max(1, len(days)))
        max_value = max(1, max(metric_value(history[day], key) for day in days for key in ("water_count", "stand_count",
            "away_count")))
        colors = [("water_count", BLUE), ("stand_count", GREEN), ("away_count", YELLOW)]
        canvas.create_line(left, bottom, width, bottom, fill=LINE)
        for index, day in enumerate(days):
            base_x = left + index * group + 8
            for offset, (key, color) in enumerate(colors):
                value = metric_value(history[day], key)
                bar_h = int((value / max_value) * 160)
                x0 = base_x + offset * 8
                canvas.create_rectangle(x0, bottom - bar_h, x0 + 6, bottom, fill=color, outline="")
            canvas.create_text(base_x + 12, bottom + 16, text=day[-5:], fill=MUTED, font=scaling.font("Microsoft YaHei UI", 8))
        legend = [("喝水", BLUE), ("起身", GREEN), ("离席", YELLOW)]
        for index, (label, color) in enumerate(legend):
            x = left + index * 70
            canvas.create_rectangle(x, 238, x + 12, 250, fill=color, outline="")
            canvas.create_text(x + 36, 244, text=label, fill=MUTED, font=scaling.font("Microsoft YaHei UI", 9))

    def _history_list(self, parent: tk.Frame) -> None:
        history = self.state.history()
        for day, data in sorted(history.items(), reverse=True)[:20]:
            text = (
                f"{day}  喝水 {metric_value(data, 'water_count')}  "
                f"起身 {metric_value(data, 'stand_count')}  "
                f"离席 {metric_value(data, 'away_count')}  "
                f"使用 {format_duration(metric_value(data, 'computer_seconds'))}"
            )
            tk.Label(parent, text=text, bg="white", fg="#4b5563", anchor="w", font=scaling.font("Microsoft YaHei UI", 9)).pack(fill="x", pady=5)

