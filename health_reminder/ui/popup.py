"""Popup windows for reminders and away-reason input."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..services.reminders import ReminderEvent
from ..platform.sound import play_ribbit
from .water_input import WaterInputDialog


class PopupManager:
    def __init__(self, root: tk.Tk, get_sound_volume: Callable[[], int] | None = None) -> None:
        self.root = root
        self.get_sound_volume = get_sound_volume or (lambda: 80)
        self._active: tk.Toplevel | None = None
        self._away_active: tk.Toplevel | None = None
        self._water_dialog = WaterInputDialog(root, timeout_ms=600_000)

    def show_reminder(
        self,
        event: ReminderEvent,
        on_water: Callable[[int], None],
        on_snooze: Callable[[], None],
    ) -> None:
        self._play_sound()

        if event.kind in ("water", "combined"):
            self._water_dialog.show(on_submit=on_water)
        else:
            self._show_simple_popup(event)

    def _show_simple_popup(self, event: ReminderEvent) -> None:
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
            "sedentary": "#34a853",
            "work_start": "#34a853",
            "work_end": "#ff6b5f",
        }.get(event.kind, "#2f80ed")
        tk.Frame(card, width=5, bg=color).pack(side="left", fill="y")

        body = tk.Frame(card, bg="white")
        body.pack(side="left", fill="both", expand=True, padx=18, pady=16)
        tk.Label(body, text=event.title, bg="white", fg="#1f2328",
                 font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(
            body, text=event.message, bg="white", fg="#5c6570",
            font=("Microsoft YaHei UI", 9), wraplength=270, justify="left",
        ).pack(anchor="w", pady=(7, 12))

        actions = tk.Frame(body, bg="white")
        actions.pack(anchor="e", fill="x")

        def close() -> None:
            if win.winfo_exists():
                win.destroy()
            self._active = None

        if event.kind.startswith("work_"):
            ttk.Button(actions, text="\u77e5\u9053\u4e86", command=close).pack(side="right")

        self._slide(win, start_x, target_x, target_y)
        win.after(22000, close)

    def show_away_reason(self, on_select: Callable[[str], None]) -> None:
        if self._away_active and self._away_active.winfo_exists():
            return
        self._play_sound()

        win = tk.Toplevel(self.root)
        self._away_active = win
        win.title("\u79bb\u5e2d\u539f\u56e0")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.configure(bg="#f4f5f7")

        width, height = 360, 230
        x = (win.winfo_screenwidth() - width) // 2
        y = (win.winfo_screenheight() - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(win, bg="white", padx=22, pady=20)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(frame, text="\u521a\u624d\u79bb\u5f00\u4e86\u4e00\u4f1a\u513f",
                 bg="white", fg="#1f2328",
                 font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        tk.Label(frame, text="\u9009\u62e9\u539f\u56e0\u540e\u4f1a\u8bb0\u5165\u4eca\u65e5\u5065\u5eb7\u6570\u636e",
                 bg="white", fg="#68717d",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(5, 16))

        grid = tk.Frame(frame, bg="white")
        grid.pack(fill="x")
        reasons = ["\u4e0a\u5395\u6240", "\u5f00\u4f1a", "\u62bd\u6839\u70df", "\u5916\u52e4"]

        def choose(reason: str) -> None:
            on_select(reason)
            if win.winfo_exists():
                win.destroy()
            self._away_active = None

        def close_without_record(_event: tk.Event | None = None) -> str:
            choose("\u672a\u8bb0\u5f55")
            return "break"

        for index, reason in enumerate(reasons):
            button = ttk.Button(grid, text=reason, command=lambda item=reason: choose(item))
            button.grid(row=index // 2, column=index % 2, padx=6, pady=6, sticky="ew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        ttk.Button(frame, text="\u4e0d\u8bb0\u5f55",
                   command=lambda: choose("\u672a\u8bb0\u5f55")).pack(anchor="e", pady=(12, 0))
        win.bind("<space>", close_without_record)
        win.bind("<Escape>", close_without_record)
        win.after(50, win.focus_force)

    def _play_sound(self) -> None:
        play_ribbit(self.get_sound_volume())

    def _slide(self, win: tk.Toplevel, start_x: int, target_x: int, target_y: int,
               step: int = 0, total_steps: int = 18) -> None:
        """Smooth slide-in with cubic ease-out."""
        if not win.winfo_exists():
            return
        if step >= total_steps:
            win.geometry(f"+{target_x}+{target_y}")
            return
        t = step / total_steps
        ease = 1 - (1 - t) ** 3
        current_x = int(start_x + (target_x - start_x) * ease)
        win.geometry(f"+{current_x}+{target_y}")
        win.after(14, lambda: self._slide(win, start_x, target_x, target_y, step + 1, total_steps))
