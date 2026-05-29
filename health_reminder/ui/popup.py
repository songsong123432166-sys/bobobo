from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..services.reminders import ReminderEvent


class PopupManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._active: tk.Toplevel | None = None
        self._away_active: tk.Toplevel | None = None

    def show_reminder(
        self,
        event: ReminderEvent,
        on_water: Callable[[], None],
        on_snooze: Callable[[], None],
    ) -> None:
        if self._active and self._active.winfo_exists():
            return
        win = tk.Toplevel(self.root)
        self._active = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#f4f5f7")

        width, height = 330, 168
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        target_x = screen_w - width - 24
        target_y = screen_h - height - 58
        start_x = screen_w + 12
        win.geometry(f"{width}x{height}+{start_x}+{target_y}")

        card = tk.Frame(win, bg="white", highlightthickness=1, highlightbackground="#e6e8ec")
        card.pack(fill="both", expand=True, padx=1, pady=1)

        color = {
            "water": "#2f80ed",
            "sedentary": "#34a853",
            "combined": "#fbbc04",
            "work_start": "#34a853",
            "work_end": "#ff6b5f",
        }.get(event.kind, "#2f80ed")
        tk.Frame(card, width=5, bg=color).pack(side="left", fill="y")

        body = tk.Frame(card, bg="white")
        body.pack(side="left", fill="both", expand=True, padx=18, pady=16)
        tk.Label(body, text=event.title, bg="white", fg="#1f2328", font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(
            body,
            text=event.message,
            bg="white",
            fg="#5c6570",
            font=("Microsoft YaHei UI", 9),
            wraplength=270,
            justify="left",
        ).pack(anchor="w", pady=(7, 12))

        actions = tk.Frame(body, bg="white")
        actions.pack(anchor="e", fill="x")

        def close() -> None:
            if win.winfo_exists():
                win.destroy()
            self._active = None

        def action(callback: Callable[[], None]) -> None:
            callback()
            close()

        if event.kind in {"water", "combined"}:
            ttk.Button(actions, text="我喝了", command=lambda: action(on_water)).pack(side="right", padx=(8, 0))
            ttk.Button(actions, text="稍后", command=lambda: action(on_snooze)).pack(side="right")
        if event.kind.startswith("work_"):
            ttk.Button(actions, text="知道了", command=close).pack(side="right")

        self._slide(win, start_x, target_x, target_y)
        win.after(22000, close)

    def show_away_reason(self, on_select: Callable[[str], None]) -> None:
        if self._away_active and self._away_active.winfo_exists():
            return
        win = tk.Toplevel(self.root)
        self._away_active = win
        win.title("离席原因")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.configure(bg="#f4f5f7")

        width, height = 360, 230
        x = (win.winfo_screenwidth() - width) // 2
        y = (win.winfo_screenheight() - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(win, bg="white", padx=22, pady=20)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(frame, text="刚才离开了一会儿？", bg="white", fg="#1f2328", font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        tk.Label(frame, text="选择原因后会记入今日健康数据。", bg="white", fg="#68717d", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(5, 16))

        grid = tk.Frame(frame, bg="white")
        grid.pack(fill="x")
        reasons = ["上厕所", "开会", "抽根烟", "外勤"]

        def choose(reason: str) -> None:
            on_select(reason)
            if win.winfo_exists():
                win.destroy()
            self._away_active = None

        for index, reason in enumerate(reasons):
            button = ttk.Button(grid, text=reason, command=lambda item=reason: choose(item))
            button.grid(row=index // 2, column=index % 2, padx=6, pady=6, sticky="ew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        ttk.Button(frame, text="不记录", command=lambda: choose("未记录")).pack(anchor="e", pady=(12, 0))

    def _slide(self, win: tk.Toplevel, current_x: int, target_x: int, target_y: int) -> None:
        if not win.winfo_exists():
            return
        next_x = max(target_x, current_x - 38)
        win.geometry(f"+{next_x}+{target_y}")
        if next_x > target_x:
            win.after(12, lambda: self._slide(win, next_x, target_x, target_y))
