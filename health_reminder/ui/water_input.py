"""Water intake input popup with 10-minute auto-dismiss."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


_PRESETS = [200, 250, 300, 500]


class WaterInputDialog:
    """Slide-in popup for recording water intake (ml).
    Auto-dismisses after timeout_ms (default 10 minutes).
    """

    def __init__(self, root: tk.Tk, timeout_ms: int = 600_000) -> None:
        self.root = root
        self.timeout_ms = timeout_ms
        self._win: tk.Toplevel | None = None

    @property
    def active(self) -> bool:
        return self._win is not None and self._win.winfo_exists()

    def show(self, on_submit: Callable[[int], None]) -> None:
        if self.active:
            return

        win = tk.Toplevel(self.root)
        self._win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#f4f5f7")

        width, height = 340, 280
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        target_x = screen_w - width - 24
        target_y = screen_h - height - 58
        start_x = screen_w + 12
        win.geometry(f"{width}x{height}+{start_x}+{target_y}")

        card = tk.Frame(win, bg="white", highlightthickness=1, highlightbackground="#e6e8ec")
        card.pack(fill="both", expand=True, padx=1, pady=1)

        tk.Frame(card, width=5, bg="#2f80ed").pack(side="left", fill="y")

        body = tk.Frame(card, bg="white")
        body.pack(side="left", fill="both", expand=True, padx=18, pady=14)

        tk.Label(
            body, text="\u559d\u6c34\u6253\u5361", bg="white", fg="#1f2328",
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body, text="\u8f93\u5165\u996e\u6c34\u91cf\uff08\u6beb\u5347\uff09\uff0c\u8bb0\u5f55\u4eca\u65e5\u5065\u5eb7\u6570\u636e", bg="white", fg="#5c6570",
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(4, 10))

        preset_frame = tk.Frame(body, bg="white")
        preset_frame.pack(fill="x", pady=(0, 8))
        entry_var = tk.StringVar(value="250")
        for ml in _PRESETS:
            btn = ttk.Button(
                preset_frame, text=f"{ml}ml", width=6,
                command=lambda v=ml: entry_var.set(str(v)),
            )
            btn.pack(side="left", padx=(0, 6))

        entry_row = tk.Frame(body, bg="white")
        entry_row.pack(fill="x", pady=(0, 10))
        entry = ttk.Entry(entry_row, textvariable=entry_var, width=10, font=("Microsoft YaHei UI", 11))
        entry.pack(side="left")
        tk.Label(entry_row, text="ml", bg="white", fg="#5c6570",
                 font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(6, 0))

        actions = tk.Frame(body, bg="white")
        actions.pack(anchor="e", fill="x")

        def close() -> None:
            if win.winfo_exists():
                win.destroy()
            self._win = None

        def submit() -> None:
            try:
                ml = int(entry_var.get().strip())
                if ml > 0:
                    on_submit(ml)
            except (ValueError, TypeError):
                pass
            close()

        win.bind("<Return>", lambda _e: submit())

        ttk.Button(actions, text="\u7a0d\u540e\u63d0\u9192", command=close).pack(side="right")
        ttk.Button(actions, text="\u8bb0\u5f55\u996e\u6c34", command=submit).pack(side="right", padx=(0, 8))

        entry.focus_set()
        self._slide(win, start_x, target_x, target_y)
        win.after(self.timeout_ms, close)

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