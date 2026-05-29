import queue
import threading
from datetime import date

from .components.notifications import (
    show_away_reason_popup,
    show_toast,
    show_water_popup,
)
from .config.ui_config import COLORS
from .pages.main_window import create_main_window
from .windows_integration import configure_tcl_tk_for_frozen_app

configure_tcl_tk_for_frozen_app()

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None


class UiManager:
    """Tk entry point. Components and pages live in dedicated modules."""

    def __init__(self, app):
        self.app = app
        self.tk = tk
        self.ttk = ttk
        self.colors = COLORS
        self.root = None
        self.main_window = None
        self.water_popup_open = False
        self.away_popup_open = False
        self.tasks = queue.Queue()
        self._current_nav = "dashboard"
        self._cal_year = date.today().year
        self._cal_month = date.today().month
        self._status_labels = {}
        self._stat_values = {}
        self._nav_buttons = {}
        self._panels = {}
        self._cal_grid = None
        self._cal_content = None

    @property
    def available(self):
        return self.tk is not None

    def start(self):
        if not self.available:
            self.app.log.write("tkinter not available")
            return

        def ui_loop():
            root = self.tk.Tk()
            root.withdraw()
            self.root = root
            self._poll_tasks()
            root.mainloop()

        threading.Thread(target=ui_loop, daemon=True).start()

    def dispatch(self, task):
        if self.available:
            self.tasks.put(task)

    def _poll_tasks(self):
        while True:
            try:
                task = self.tasks.get_nowait()
            except queue.Empty:
                break
            try:
                task(self.root)
            except Exception as exc:
                self.app.log.write(f"UI task failed: {exc}")
        self.root.after(100, self._poll_tasks)

    def show_toast(self, title, message):
        show_toast(self, title, message)

    def show_water_popup(self, message):
        show_water_popup(self, message)

    def show_away_reason_popup(self):
        show_away_reason_popup(self)

    def show_main_window(self, icon=None, item=None):
        self.dispatch(lambda root: create_main_window(self, root))
