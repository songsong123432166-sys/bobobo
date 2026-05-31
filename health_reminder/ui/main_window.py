from __future__ import annotations

import calendar
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageTk

from .. import __version__
from ..core.config import ConfigStore
from ..core.event_log import EventLogger
from ..core.health_state import HealthStateStore
from ..core.paths import resource_path
from ..platform import autostart
from ..core.scoring import ScoreBreakdown

import customtkinter as ctk

BG = "#f3f4f6"
SIDEBAR = "#ffffff"
TEXT = "#20242a"
MUTED = "#6b7280"
LINE = "#e5e7eb"
BLUE = "#2f80ed"
GREEN = "#34a853"
RED = "#ff6b5f"
YELLOW = "#fbbc04"


def format_duration(seconds: int) -> str:
    minutes = max(0, seconds) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}小时{minutes:02d}分"


def metric_value(data: dict[str, Any], key: str) -> int:
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get(key, 0))
    except (TypeError, ValueError):
        return 0


class ScrollPage:
    _BAR_W = 6
    _BAR_COLOR = "#c5c9d0"
    _HIDE_DELAY = 1200

    def __init__(self, parent: tk.Frame) -> None:
        self.canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        self.frame = tk.Frame(self.canvas, bg=BG)
        self.window_id = self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self._bar = tk.Canvas(parent, width=self._BAR_W, bg=BG, highlightthickness=0, bd=0)
        self._bar_visible = False
        self._bar_hide_id = None
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.frame.bind("<Configure>", self._update_region)
        self.canvas.bind("<Configure>", self._fit_width)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def destroy(self) -> None:
        if self._bar_hide_id:
            self.canvas.after_cancel(self._bar_hide_id)
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.destroy()
        self._bar.destroy()

    def _update_region(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _fit_width(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _bind_wheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_wheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_scroll(self, first, last):
        f, l = float(first), float(last)
        if f <= 0.0 and l >= 1.0:
            self._hide_bar()
            return
        self._show_bar(f, l)
        self._schedule_hide()

    def _show_bar(self, f, l):
        bar = self._bar
        bar.update_idletasks()
        h = bar.winfo_height()
        if h < 20:
            return
        y1, y2 = int(f * h), max(int(l * h), int(f * h) + 24)
        bar.delete("all")
        if not self._bar_visible:
            bar.place(relx=1.0, rely=0, relheight=1.0, anchor="ne", x=-2)
            self._bar_visible = True
        bar.create_rectangle(2, y1, self._BAR_W + 2, y2, fill=self._BAR_COLOR, outline="")

    def _hide_bar(self):
        if self._bar_visible:
            self._bar.place_forget()
            self._bar_visible = False

    def _schedule_hide(self):
        if self._bar_hide_id:
            self.canvas.after_cancel(self._bar_hide_id)
        self._bar_hide_id = self.canvas.after(self._HIDE_DELAY, self._hide_bar)


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        config_store: ConfigStore,
        state: HealthStateStore,
        logger: EventLogger,
        get_remaining: Callable[[], tuple[int, int]],
        on_save_config: Callable[[dict[str, Any]], None],
        on_test_sound: Callable[[], None],
        on_test_camera: Callable[[], str],
        on_test_popup: Callable[[], None],
        on_test_center_popup: Callable[[], None],
    ) -> None:
        self.root = root
        self.config_store = config_store
        self.state = state
        self.logger = logger
        self.get_remaining = get_remaining
        self.on_save_config = on_save_config
        self.on_test_sound = on_test_sound
        self.on_test_camera = on_test_camera
        self.on_test_popup = on_test_popup
        self.on_test_center_popup = on_test_center_popup
        self.window: tk.Toplevel | None = None
        self.content: tk.Frame | None = None
        self.page: str = "visual"
        self.scroll_page: ScrollPage | None = None
        self.setting_vars: dict[str, tk.Variable] = {}
        self._refresh_after: str | None = None
        self._window_icon: ImageTk.PhotoImage | None = None
        self._sidebar_icon: ImageTk.PhotoImage | None = None
        self._visual_labels: dict[str, tk.Label] = {}
        self._visual_canvases: dict[str, tk.Canvas] = {}
        self._selected_day = datetime.now().date().isoformat()
        self._history_mode = "chart"
        self._history_body: tk.Frame | None = None
        self._nav_buttons: dict = {}

    def show(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self._schedule_refresh()
            return
        self.window = tk.Toplevel(self.root)
        self.window.title(f"健康提醒 {__version__}")
        self.window.geometry("980x650")
        self.window.minsize(860, 560)
        self.window.configure(bg=BG)
        self._apply_window_icon()
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self._build_shell()
        self._render_page()
        self._schedule_refresh()

    def hide(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.withdraw()
        self._cancel_refresh()

    def _build_shell(self) -> None:
        assert self.window is not None
        shell = tk.Frame(self.window, bg=BG)
        shell.pack(fill="both", expand=True)

        nav = tk.Frame(shell, bg=SIDEBAR, width=205)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        header = tk.Frame(nav, bg=SIDEBAR)
        header.pack(fill="x", padx=22, pady=(26, 20))
        self._sidebar_icon = self._load_app_icon(44)
        if self._sidebar_icon is not None:
            tk.Label(header, image=self._sidebar_icon, bg=SIDEBAR).pack(side="left", padx=(0, 10))
        tk.Label(header, text="控制台", bg=SIDEBAR, fg=TEXT, font=("Microsoft YaHei UI", 19, "bold")).pack(side="left")
        self._nav_button(nav, "可视化数据", "visual").pack(fill="x", padx=16, pady=5)
        self._nav_button(nav, "记录日历", "calendar").pack(fill="x", padx=16, pady=5)
        self._nav_button(nav, "设置", "settings").pack(fill="x", padx=16, pady=5)
        tk.Label(nav, text=__version__, bg=SIDEBAR, fg="#9ca3af", font=("Microsoft YaHei UI", 9)).pack(side="bottom", anchor="w", padx=24, pady=22)

        self.content = tk.Frame(shell, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

    def _load_app_icon(self, size: int) -> ImageTk.PhotoImage | None:
        try:
            image = Image.open(resource_path("assets/app_icon.png")).convert("RGBA")
            image = image.resize((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
        except Exception:
            return None

    def _apply_window_icon(self) -> None:
        assert self.window is not None
        try:
            icon_path = resource_path("assets/app_icon.ico")
            if icon_path.exists():
                self.window.iconbitmap(default=str(icon_path))
        except Exception:
            pass
        self._window_icon = self._load_app_icon(256)
        if self._window_icon is not None:
            try:
                self.window.iconphoto(True, self._window_icon)
            except Exception:
                pass

    def _nav_button(self, parent: tk.Frame, text: str, page: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            anchor="w",
            relief="flat",
            borderwidth=0,
            bg=SIDEBAR,
            fg=TEXT,
            activebackground="#eef4ff",
            activeforeground=BLUE,
            font=("Microsoft YaHei UI", 11),
            padx=14,
            pady=12,
            command=lambda: self._switch(page),
        )

    def _switch(self, page: str) -> None:
        if self.page == page:
            return
        self.page = page
        self._render_page()
        self._schedule_refresh()

    def _render_page(self) -> None:
        if not self.window or not self.window.winfo_exists() or not self.content:
            return
        self._cancel_refresh()
        self._visual_labels = {}
        self._visual_canvases = {}
        self._history_body = None
        self.setting_vars = {}
        if self.scroll_page is not None:
            self.scroll_page.destroy()
        self.scroll_page = ScrollPage(self.content)
        if self.page == "visual":
            self._build_visual(self.scroll_page.frame)
        elif self.page == "calendar":
            self._build_calendar(self.scroll_page.frame)
        else:
            self._build_settings(self.scroll_page.frame)
        self.scroll_page.canvas.yview_moveto(0)

    def _schedule_refresh(self) -> None:
        if not self.window or not self.window.winfo_exists():
            return
        self._cancel_refresh()
        self._refresh_after = self.window.after(5000, self._refresh_dynamic)

    def _cancel_refresh(self) -> None:
        if self.window and self._refresh_after is not None:
            try:
                self.window.after_cancel(self._refresh_after)
            except tk.TclError:
                pass
        self._refresh_after = None

    def _refresh_dynamic(self) -> None:
        if not self.window or not self.window.winfo_exists():
            return
        if self.page == "visual" and self._visual_labels:
            self._update_visual_values()
        self._schedule_refresh()

    def _header(self, parent: tk.Misc, title: str, subtitle: str) -> None:
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", padx=28, pady=(26, 16))
        tk.Label(frame, text=title, bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w")
        tk.Label(frame, text=subtitle, bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(4, 0))

    def _card(self, parent: tk.Misc, title: str | None = None) -> tk.Frame:
        frame = ctk.CTkFrame(parent, corner_radius=16, fg_color="white", border_width=1, border_color="#e0e3e8")
        if title:
            ctk.CTkLabel(frame, text=title, text_color=TEXT, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        return frame

    def _build_visual(self, parent: tk.Frame) -> None:
        self._header(parent, "今日健康摘要", "久坐、喝水、离席和电脑使用状态都在这里。")

        score_card = self._card(parent)
        score_card.pack(fill="x", padx=28)
        self._score_ring(score_card)

        status_card = self._card(parent, "当前状态")
        status_card.pack(fill="x", padx=28, pady=(14, 0))
        self._status_lights(status_card)
        self._metric_line(status_card, "当前久坐时长", "sedentary_seconds", RED)
        self._metric_line(status_card, "久坐剩余时间", "sedentary_left", GREEN)
        self._metric_line(status_card, "喝水剩余时间", "water_left", BLUE)
        self._metric_line(status_card, "电脑使用时长", "computer_seconds", RED)
        self._daily_metrics(status_card)

        today_card = self._card(parent, "今日状态")
        today_card.pack(fill="x", padx=28, pady=(14, 24))
        self._today_status(today_card)

        self._update_visual_values()

    def _score_ring(self, parent: tk.Frame) -> None:
        body = tk.Frame(parent, bg="white")
        body.pack(fill="x", padx=28, pady=(20, 16))
        self._score_num_label = tk.Label(body, text="--", bg="white", fg=TEXT,
                                          font=("Microsoft YaHei UI", 52, "bold"))
        self._score_num_label.pack(anchor="center")
        tk.Label(body, text="健康分", bg="white", fg=MUTED,
                 font=("Microsoft YaHei UI", 13)).pack(anchor="center", pady=(2, 0))
        self._grade_text_label = tk.Label(body, text="", bg="white", fg=MUTED,
                                           font=("Microsoft YaHei UI", 10))
        self._grade_text_label.pack(anchor="center", pady=(4, 0))
        self._score_tip_label = tk.Label(body, text="", bg="white", fg=MUTED,
                                         font=("Microsoft YaHei UI", 10), wraplength=520, justify="center")
        self._score_tip_label.pack(anchor="center", pady=(6, 0))

    def _status_lights(self, parent: tk.Frame) -> None:
        lights = tk.Frame(parent, bg="white")
        lights.pack(fill="x", padx=18, pady=(0, 8))
        for key, label, color in [
            ("light_using", "正在使用", GREEN),
            ("light_away_short", "离席 0-20 分钟", YELLOW),
            ("light_away_long", "离席超过 20 分钟", RED),
        ]:
            item = tk.Frame(lights, bg="white")
            item.pack(side="left", padx=(0, 16))
            canvas = tk.Canvas(item, width=18, height=18, bg="white", highlightthickness=0)
            canvas.pack(side="left")
            canvas.create_oval(3, 3, 15, 15, fill="#d1d5db", outline="", tags=("dot",))
            self._visual_canvases[key] = canvas
            tk.Label(item, text=label, bg="white", fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(5, 0))


    def _metric_line(self, parent: tk.Frame, label: str, key: str, color: str) -> None:
        row = tk.Frame(parent, bg="white")
        row.pack(fill="x", padx=18, pady=5)
        tk.Label(row, text=label, bg="white", fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(side="left")
        value = tk.Label(row, text="", bg="white", fg=color, font=("Microsoft YaHei UI", 11, "bold"))
        value.pack(side="right")
        self._visual_labels[key] = value


    def _today_status(self, parent: tk.Frame) -> None:
        body = tk.Frame(parent, bg="white")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        status = tk.Label(body, text="", bg="white", fg=MUTED, font=("Microsoft YaHei UI", 10), wraplength=320, justify="left")
        status.pack(anchor="w", pady=(8, 18))
        self._visual_labels["last_status"] = status
        self._metric_line(body, "运行时长", "run_seconds", BLUE)
        self._metric_line(body, "统计日期", "date", GREEN)



    def _update_visual_values(self) -> None:
        stats = self.state.today()
        bd = stats.score_breakdown
        sedentary_left, water_left = self.get_remaining()
        values = {
            "water_count": f"{stats.water_count} 次",
            "stand_count": f"{stats.stand_count} 次",
            "away_count": f"{stats.away_count} 次",
            "sedentary_alerts": f"{stats.sedentary_alerts} 次",
            "sedentary_seconds": format_duration(stats.sedentary_seconds),
            "sedentary_left": format_duration(sedentary_left),
            "water_left": format_duration(water_left),
            "computer_seconds": format_duration(stats.computer_seconds),
            "run_seconds": format_duration(stats.run_seconds),
            "date": stats.date,
            "last_status": stats.last_status,
        }
        for key, value in values.items():
            if key in self._visual_labels:
                self._visual_labels[key].configure(text=value)
        self._pending_breakdown = bd
        self._draw_score(stats.health_score)
        self._set_light("light_using", GREEN, stats.presence_status == "using")
        self._set_light("light_away_short", YELLOW, stats.presence_status == "away_short")
        self._set_light("light_away_long", RED, stats.presence_status == "away_long")

    def _draw_score(self, score: int) -> None:
        color = GREEN if score >= 80 else YELLOW if score >= 60 else RED
        if hasattr(self, "_score_num_label"):
            self._score_num_label.configure(text=str(score), fg=color)
        bd = getattr(self, "_pending_breakdown", None)
        if hasattr(self, "_grade_text_label") and bd:
            self._grade_text_label.configure(text=f"{bd.grade} {bd.label}")
        if hasattr(self, "_score_tip_label") and bd:
            self._score_tip_label.configure(text=bd.insight())

    def _set_light(self, key: str, color: str, active: bool) -> None:
        canvas = self._visual_canvases.get(key)
        if canvas is not None:
            canvas.itemconfigure("dot", fill=color if active else "#d1d5db")

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
            tk.Label(item, text=label, bg="#f9fafb", fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=10, pady=(8, 2))
            value = tk.Label(item, text="", bg="#f9fafb", fg=color, font=("Microsoft YaHei UI", 14, "bold"))
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
            font=("Microsoft YaHei UI", 11, "bold"),
            wraplength=720,
            justify="left",
        ).pack(anchor="w")

    def _month_calendar(self, parent: tk.Frame) -> None:
        now = datetime.now()
        history = self.state.history()
        grid = tk.Frame(parent, bg="white")
        grid.pack(fill="x", padx=18, pady=12)
        for index, name in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            tk.Label(grid, text=name, bg="white", fg=MUTED, font=("Microsoft YaHei UI", 9)).grid(row=0, column=index, sticky="ew", pady=4)
        for row, week in enumerate(calendar.monthcalendar(now.year, now.month), start=1):
            for col, day in enumerate(week):
                self._calendar_cell(grid, row, col, now.year, now.month, day, history)
        for col in range(7):
            grid.columnconfigure(col, weight=1, uniform="calendar")

    def _calendar_cell(self, grid: tk.Frame, row: int, col: int, year: int, month: int, day: int, history: dict[str, Any]) -> None:
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
        day_label = tk.Label(cell, text=label, bg=color, fg=text_color, font=("Microsoft YaHei UI", 10, "bold"))
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
            tk.Label(box, text=label, bg="white", fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
            tk.Label(box, text=value, bg="white", fg=color, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(4, 0))
            row.columnconfigure(index, weight=1)

    def _history_switcher(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg="white")
        header.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(header, text="历史统计", bg="white", fg=TEXT, font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        ttk.Button(header, text="柱状统计图", command=lambda: self._set_history_mode("chart")).pack(side="right", padx=(8, 0))
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
            canvas.create_text(360, 120, text="暂无历史数据", fill=MUTED, font=("Microsoft YaHei UI", 11))
            return
        width = 760
        left, top, bottom = 42, 20, 218
        group = max(34, (width - left - 20) // max(1, len(days)))
        max_value = max(1, max(metric_value(history[day], key) for day in days for key in ("water_count", "stand_count", "away_count")))
        colors = [("water_count", BLUE), ("stand_count", GREEN), ("away_count", YELLOW)]
        canvas.create_line(left, bottom, width, bottom, fill=LINE)
        for index, day in enumerate(days):
            base_x = left + index * group + 8
            for offset, (key, color) in enumerate(colors):
                value = metric_value(history[day], key)
                bar_h = int((value / max_value) * 160)
                x0 = base_x + offset * 8
                canvas.create_rectangle(x0, bottom - bar_h, x0 + 6, bottom, fill=color, outline="")
            canvas.create_text(base_x + 12, bottom + 16, text=day[-5:], fill=MUTED, font=("Microsoft YaHei UI", 8))
        legend = [("喝水", BLUE), ("起身", GREEN), ("离席", YELLOW)]
        for index, (label, color) in enumerate(legend):
            x = left + index * 70
            canvas.create_rectangle(x, 238, x + 12, 250, fill=color, outline="")
            canvas.create_text(x + 36, 244, text=label, fill=MUTED, font=("Microsoft YaHei UI", 9))

    def _history_list(self, parent: tk.Frame) -> None:
        history = self.state.history()
        for day, data in sorted(history.items(), reverse=True)[:20]:
            text = (
                f"{day}  喝水 {metric_value(data, 'water_count')}  "
                f"起身 {metric_value(data, 'stand_count')}  "
                f"离席 {metric_value(data, 'away_count')}  "
                f"使用 {format_duration(metric_value(data, 'computer_seconds'))}"
            )
            tk.Label(parent, text=text, bg="white", fg="#4b5563", anchor="w", font=("Microsoft YaHei UI", 9)).pack(fill="x", pady=5)

    def _build_settings(self, parent: tk.Frame) -> None:
        self._header(parent, "设置", "分组调整工作时间、提醒、勿扰、检测和系统行为。")
        config = self.config_store.load()
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self._settings_group(wrap, "工作时间", [("上班时间", "work_time.start", config["work_time"]["start"]), ("下班时间", "work_time.end", config["work_time"]["end"])])
        self._settings_group(
            wrap,
            "提醒设置",
            [
                ("久坐间隔（分钟）", "reminders.sedentary_interval_minutes", config["reminders"]["sedentary_interval_minutes"]),
                ("喝水间隔（分钟）", "reminders.water_interval_minutes", config["reminders"]["water_interval_minutes"]),
                ("喝水稍后提醒（分钟）", "reminders.water_snooze_minutes", config["reminders"]["water_snooze_minutes"]),
                ("合并提醒窗口（分钟）", "reminders.merge_window_minutes", config["reminders"]["merge_window_minutes"]),
            ],
        )
        self._settings_group(
            wrap,
            "勿扰设置",
            [
                ("是否启用", "do_not_disturb.enabled", config["do_not_disturb"]["enabled"]),
                ("开始时间", "do_not_disturb.start", config["do_not_disturb"]["start"]),
                ("结束时间", "do_not_disturb.end", config["do_not_disturb"]["end"]),
            ],
        )
        self._settings_group(
            wrap,
            "状态检测",
            [
                ("离开判断时间（秒）", "detection.away_after_seconds", config["detection"]["away_after_seconds"]),
                ("空闲判断时间（秒）", "detection.idle_after_seconds", config["detection"]["idle_after_seconds"]),
                ("摄像头触发空闲时间（秒）", "detection.camera_idle_threshold_seconds", config["detection"]["camera_idle_threshold_seconds"]),
                ("摄像头检测间隔（秒）", "detection.camera_interval_seconds", config["detection"]["camera_interval_seconds"]),
                ("无人后摄像头检测间隔（秒）", "detection.camera_away_interval_seconds", config["detection"]["camera_away_interval_seconds"]),
                ("离席红灯阈值（秒）", "detection.away_red_after_seconds", config["detection"]["away_red_after_seconds"]),
                ("站起检测间隔（秒）", "detection.stand_watch_interval_seconds", config["detection"]["stand_watch_interval_seconds"]),
                ("站起检测持续时间（秒）", "detection.stand_watch_duration_seconds", config["detection"]["stand_watch_duration_seconds"]),
                ("摄像头检测", "detection.camera_enabled", config["detection"]["camera_enabled"]),
                ("隐私模式（暂停摄像头）", "detection.privacy_mode", config["detection"]["privacy_mode"]),
                ("中央弹窗", "detection.center_popup_enabled", config["detection"]["center_popup_enabled"]),
            ],
        )
        self._privacy_note(wrap)
        self._settings_group(
            wrap,
            "今日目标",
            [
                ("喝水目标（ml）", "goals.water_ml", config["goals"]["water_ml"]),
                ("起身目标（次）", "goals.stand_count", config["goals"]["stand_count"]),
                ("最长久坐目标（分钟）", "goals.max_sit_streak_minutes", config["goals"]["max_sit_streak_minutes"]),
            ],
        )
        self._settings_group(
            wrap,
            "系统设置",
            [
                ("开机自启", "system.autostart", autostart.is_enabled()),
                ("提示音音量（0-100）", "system.sound_volume_percent", config["system"]["sound_volume_percent"]),
            ],
        )
        self._preset_tools(wrap)
        self._test_tools(wrap)
        ttk.Button(wrap, text="保存设置", command=self._save_settings).pack(anchor="e", pady=(0, 18), padx=2)
        self._settings_log(wrap)

    def _settings_group(self, parent: tk.Frame, title: str, rows: list[tuple[str, str, Any]]) -> None:
        card = self._card(parent, title)
        card.pack(fill="x", pady=(0, 14))
        for label, key, value in rows:
            row = tk.Frame(card, bg="white")
            row.pack(fill="x", padx=18, pady=7)
            tk.Label(row, text=label, bg="white", fg=TEXT, font=("Microsoft YaHei UI", 10)).pack(side="left")
            if isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                ttk.Checkbutton(row, variable=var).pack(side="right")
            else:
                var = tk.StringVar(value=str(value))
                ttk.Entry(row, textvariable=var, width=18).pack(side="right")
            self.setting_vars[key] = var

    def _privacy_note(self, parent: tk.Frame) -> None:
        card = self._card(parent, "隐私说明")
        card.pack(fill="x", pady=(0, 14))
        tk.Label(
            card,
            text="摄像头只在键鼠空闲后短暂检测是否有人，不保存画面，也不会上传画面。开启隐私模式后，程序不会调用摄像头。",
            bg="white",
            fg=MUTED,
            font=("Microsoft YaHei UI", 10),
            wraplength=720,
            justify="left",
        ).pack(fill="x", padx=18, pady=(0, 16))

    def _preset_tools(self, parent: tk.Frame) -> None:
        card = self._card(parent, "模式预设")
        card.pack(fill="x", pady=(0, 14))
        row = tk.Frame(card, bg="white")
        row.pack(fill="x", padx=18, pady=(0, 16))
        presets = [
            ("推荐模式", {
                "reminders.sedentary_interval_minutes": "45",
                "reminders.water_interval_minutes": "60",
                "detection.camera_enabled": True,
                "detection.privacy_mode": False,
                "detection.camera_idle_threshold_seconds": "20",
                "detection.camera_interval_seconds": "15",
                "detection.camera_away_interval_seconds": "60",
                "detection.center_popup_enabled": True,
            }),
            ("轻量模式", {
                "reminders.sedentary_interval_minutes": "60",
                "reminders.water_interval_minutes": "90",
                "detection.camera_enabled": False,
                "detection.privacy_mode": True,
                "detection.camera_idle_threshold_seconds": "60",
                "detection.camera_interval_seconds": "60",
                "detection.center_popup_enabled": False,
            }),
            ("隐私模式", {
                "detection.camera_enabled": False,
                "detection.privacy_mode": True,
                "detection.center_popup_enabled": False,
            }),
        ]
        for text, values in presets:
            ttk.Button(row, text=text, command=lambda item=values: self._apply_preset(item)).pack(side="left", padx=(0, 8))

    def _apply_preset(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            var = self.setting_vars.get(key)
            if var is not None:
                var.set(value)
        messagebox.showinfo("模式已套用", "预设已填入，点击保存设置后生效。")

    def _test_tools(self, parent: tk.Frame) -> None:
        card = self._card(parent, "测试工具")
        card.pack(fill="x", pady=(0, 14))
        row = tk.Frame(card, bg="white")
        row.pack(fill="x", padx=18, pady=(0, 16))
        ttk.Button(row, text="测试提示音", command=self.on_test_sound).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="测试右下角弹窗", command=self.on_test_popup).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="测试中央弹窗", command=self.on_test_center_popup).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="测试摄像头", command=self._show_camera_diagnostic).pack(side="left")

    def _show_camera_diagnostic(self) -> None:
        messagebox.showinfo("摄像头检测结果", self.on_test_camera())

    def _settings_log(self, parent: tk.Frame) -> None:
        log_card = self._card(parent, "运行日志")
        log_card.pack(fill="x", pady=(0, 18))
        for line in self.logger.tail(10) or ["暂无日志"]:
            tk.Label(log_card, text=line, bg="white", fg="#4b5563", anchor="w", font=("Consolas", 9)).pack(fill="x", padx=18, pady=3)

    def _save_settings(self) -> None:
        config = self.config_store.load()
        for key, var in self.setting_vars.items():
            cursor = config
            parts = key.split(".")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            default = cursor.get(parts[-1])
            raw = var.get()
            if isinstance(default, bool):
                value = bool(raw)
            elif isinstance(default, int):
                try:
                    value = int(raw)
                except ValueError:
                    value = default
            else:
                value = str(raw)
            cursor[parts[-1]] = value

        autostart.set_enabled(bool(config.get("system", {}).get("autostart", False)))
        self.config_store.save(config)
        self.on_save_config(config)
        self.logger.log("settings_saved", "user saved settings")
        messagebox.showinfo("设置已保存", "新的提醒设置已经生效。")
