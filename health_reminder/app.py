from __future__ import annotations

import queue
import sys
from datetime import datetime
from typing import Any

from .platform.tcl_bootstrap import configure_tcl_tk

configure_tcl_tk()

import tkinter as tk
from tkinter import messagebox, ttk

from . import __version__
from .core.config import ConfigStore
from .core.event_log import EventLogger
from .core.health_state import HealthStateStore
from .core.paths import get_data_paths
from .platform.tray import TrayController
from .services.reminders import ReminderEvent, ReminderService
from .ui.main_window import MainWindow
from .ui.popup import PopupManager


class AppController:
    def __init__(self) -> None:
        self.paths = get_data_paths()
        self.config_store = ConfigStore(self.paths)
        self.config = self.config_store.load()
        self.logger = EventLogger(self.paths.log)
        self.state = HealthStateStore(self.paths.health_score, self.paths.away_reason)
        self.ui_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._stopping = False
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("健康提醒")
        self.root.report_callback_exception = self._handle_tk_error
        self._apply_style()

        self.popup = PopupManager(self.root)
        self.service = ReminderService(self._get_config, self.ui_queue, self.state, self.logger)
        self.main_window = MainWindow(
            self.root,
            self.config_store,
            self.state,
            self.logger,
            self._remaining_seconds,
            self._save_config,
        )
        self.tray = TrayController(
            on_open=lambda: self.ui_queue.put(("show_main", None)),
            on_about=lambda: self.ui_queue.put(("about", None)),
            on_exit=lambda: self.ui_queue.put(("quit", None)),
        )
        if self.paths.degraded:
            self.logger.log("data_path_degraded", self.paths.error or str(self.paths.root))

    def run(self) -> None:
        self.logger.log("app_start", __version__)
        self.service.start()
        self.tray.start()
        if self.config.get("system", {}).get("show_main_on_start", False):
            self.main_window.show()
        self.root.after(200, self._poll_ui_queue)
        self.root.mainloop()

    def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self.logger.log("app_exit", "stopping application")
        self.service.stop()
        self.tray.stop()
        try:
            if self.root.winfo_exists():
                self.root.quit()
                self.root.destroy()
        except tk.TclError:
            pass

    def _get_config(self) -> dict[str, Any]:
        return self.config

    def _save_config(self, config: dict[str, Any]) -> None:
        self.config = config

    def _remaining_seconds(self) -> tuple[int, int]:
        return self.service.engine.remaining_seconds(datetime.now(), self.config)

    def _poll_ui_queue(self) -> None:
        if self._stopping:
            return
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                self._handle_ui_event(kind, payload)
                if self._stopping:
                    return
        except queue.Empty:
            pass
        try:
            if not self._stopping and self.root.winfo_exists():
                self.root.after(200, self._poll_ui_queue)
        except tk.TclError:
            pass

    def _handle_ui_event(self, kind: str, payload: Any) -> None:
        if self._stopping and kind != "quit":
            return
        if kind == "show_main":
            self.main_window.show()
            return
        if kind == "about":
            messagebox.showinfo("关于程序", f"健康提醒\n{__version__}\n\n一个后台运行的健康提醒托盘程序。")
            return
        if kind == "quit":
            self.stop()
            return
        if kind == "reminder" and isinstance(payload, ReminderEvent):
            self._show_reminder(payload)
            return
        if kind == "away_reason":
            self.popup.show_away_reason(self._record_away_reason)

    def _show_reminder(self, event: ReminderEvent) -> None:
        self.popup.show_reminder(
            event,
            on_water=self._confirm_water,
            on_snooze=self._snooze_water,
        )

    def _confirm_water(self) -> None:
        self.state.increment("water_count", 1)
        self.service.engine.confirm_water()
        self.logger.log("water_confirmed", "user clicked drank")

    def _snooze_water(self) -> None:
        minutes = int(self.config.get("reminders", {}).get("water_snooze_minutes", 10))
        self.service.engine.snooze_water(minutes)
        self.logger.log("water_snoozed", f"{minutes} minutes")

    def _record_away_reason(self, reason: str) -> None:
        if reason != "未记录":
            self.state.record_away_reason(reason)
            self.logger.log("away_reason", reason)
        else:
            self.logger.log("away_reason_skipped", "user skipped")

    def _handle_tk_error(self, exc: type[BaseException], value: BaseException, _traceback) -> None:
        self.logger.log("tk_error", f"{exc.__name__}: {value}")

    def _apply_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 7))
        style.configure("TEntry", padding=(8, 5))
        style.configure("TCheckbutton", background="white")


def main() -> None:
    try:
        app = AppController()
        app.run()
    except Exception as exc:
        try:
            paths = get_data_paths()
            EventLogger(paths.log).log("fatal_error", str(exc))
        except Exception:
            pass
        if sys.stderr:
            print(f"HealthTrayReminder fatal error: {exc}", file=sys.stderr)
