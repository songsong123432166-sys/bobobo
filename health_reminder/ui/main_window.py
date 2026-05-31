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
from .settings_page import SettingsPageMixin
from .calendar_page import CalendarPageMixin

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
    """将秒数格式化为X小时XX分。"""
    minutes = max(0, seconds) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}小时{minutes:02d}分"


def metric_value(data: dict[str, Any], key: str) -> int:
    """安全读取整数指标值。"""
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get(key, 0))
    except (TypeError, ValueError):
        return 0


class ScrollPage:
    """可滚动页面容器，带薄型自动隐藏滚动条。"""
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


class MainWindow(SettingsPageMixin, CalendarPageMixin):
    """主界面窗口，包含可视化数据、记录日历和设置三个页面。"""
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
        self.window = ctk.CTkToplevel(self.root)
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
        tk.Label(nav, text=__version__, bg=SIDEBAR, fg="#9ca3af", font=("Microsoft YaHei UI", 9)).pack(side="bottom",
            anchor="w", padx=24, pady=22)

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
        except (OSError, ValueError):
            pass
        self._window_icon = self._load_app_icon(256)
        if self._window_icon is not None:
            try:
                self.window.iconphoto(True, self._window_icon)
            except (OSError, ValueError):
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
            ctk.CTkLabel(frame, text=title, text_color=TEXT, font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w",
                padx=18, pady=(16, 8))
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
            tk.Label(item, text=label, bg="white", fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(5,
                0))


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
        status = tk.Label(body, text="", bg="white", fg=MUTED, font=("Microsoft YaHei UI", 10), wraplength=320,
            justify="left")
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

