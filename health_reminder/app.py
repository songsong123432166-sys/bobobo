"""Application controller wiring UI, services, and platform components."""

from __future__ import annotations

import queue
import sys
from datetime import datetime
from typing import Any

from .platform.tcl_bootstrap import configure_tcl_tk

configure_tcl_tk()

import customtkinter as ctk
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
from .ui import scaling
from .ui.popup import PopupManager
from .ui.onboarding import OnboardingWizard


class AppController:
    """应用控制器，负责编排UI、服务和平台组件。"""

    def __init__(self) -> None:
        self.paths = get_data_paths()
        self.config_store = ConfigStore(self.paths)
        self.config = self.config_store.load()
        self.logger = EventLogger(self.paths.log)
        self.state = HealthStateStore(self.paths.health_score, self.paths.away_reason)
        self.ui_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._stopping = False
        self._pending_away_context: dict[str, Any] = {}
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk()
        self.root.withdraw()
        scaling.init(self.root)
        self.root.title("健康提醒")
        self.root.report_callback_exception = self._handle_tk_error
        self._apply_style()
        self.popup = PopupManager(self.root, self._sound_volume, self._popup_retention_seconds)
        self.service = ReminderService(self._get_config, self.ui_queue, self.state, self.logger)
        self.main_window = MainWindow(
            self.root,
            self.config_store,
            self.state,
            self.logger,
            self._remaining_seconds,
            self._save_config,
            self._test_sound,
            self._test_camera,
            self._test_popup,
            self._test_center_popup,
            self._test_onboarding,
        )
        self.tray = TrayController(
            on_open=lambda: self.ui_queue.put(("show_main", None)),
            on_pause_30=lambda: self.ui_queue.put(("pause_reminders", 30)),
            on_pause_60=lambda: self.ui_queue.put(("pause_reminders", 60)),
            on_resume=lambda: self.ui_queue.put(("resume_reminders", None)),
            on_about=lambda: self.ui_queue.put(("about", None)),
            on_exit=lambda: self.ui_queue.put(("quit", None)),
        )
        if self.paths.degraded:
            self.logger.log("data_path_degraded", self.paths.error or str(self.paths.root))

    def run(self) -> None:
        """启动应用主循环。"""
        self.logger.log("app_start", __version__)
        self.service.start()
        self.tray.start()
        if self.config.get("system", {}).get("show_main_on_start", False):
            self.main_window.show()
        # 首次启动：弹出引导向导
        if not self.config.get("onboarding_done", False):
            self.root.after(500, self._show_onboarding)
        self.root.after(200, self._poll_ui_queue)
        self.root.mainloop()

    def stop(self) -> None:
        """停止应用，清理后台服务和托盘。"""
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

    def _show_onboarding(self) -> None:
        """弹出首次启动向导。"""
        OnboardingWizard(self.root, self.config, on_complete=self._onboarding_done)
        self.logger.log("onboarding_shown", "first launch wizard")

    def _onboarding_done(self, config: dict[str, Any]) -> None:
        """向导完成后回调：保存配置并应用。"""
        self.config_store.save(config)
        self.config = config
        self.logger.log("onboarding_done", "user completed onboarding")

    def _get_config(self) -> dict[str, Any]:
        return self.config

    def _save_config(self, config: dict[str, Any]) -> None:
        self.config = config

    def _remaining_seconds(self) -> tuple[int, int]:
        return self.service.engine.remaining_seconds(datetime.now(), self.config)

    def _sound_volume(self) -> int:
        try:
            return int(self.config.get("system", {}).get("sound_volume_percent", 80))
        except (TypeError, ValueError):
            return 80

    def _popup_retention_seconds(self) -> int:
        try:
            return int(self.config.get("system", {}).get("popup_retention_seconds", 600))
        except (TypeError, ValueError):
            return 600

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
            messagebox.showinfo(
                "关于程序", "健康提醒\n" + f"{__version__}\n\n" + "一个后台运行的健康提醒托盘程序。"
            )
            return
        if kind == "quit":
            self.stop()
            return
        if kind == "reminder" and isinstance(payload, ReminderEvent):
            self._show_reminder(payload)
            return
        if kind == "away_reason":
            self._pending_away_context = payload if isinstance(payload, dict) else {}
            self.popup.show_away_reason(self._record_away_reason)
            return
        if kind == "pause_reminders":
            self.service.pause_for(int(payload))
            self.logger.log("tray_pause", f"{payload} minutes")
            return
        if kind == "resume_reminders":
            self.service.resume()
            return

    def _show_reminder(self, event: ReminderEvent) -> None:
        self.popup.show_reminder(
            event,
            on_water=self._confirm_water,
            on_snooze=self._snooze_water,
        )

    def _confirm_water(self, ml: int = 250) -> None:
        self.state.record_water_ml(ml)
        self.service.engine.confirm_water()
        today = self.state.today()
        self.state.set_status(f"已记录喝水 {ml}ml，今日累计 {today.water_ml}ml。")
        self.logger.log("water_confirmed", f"{ml}ml recorded")

    def _snooze_water(self) -> None:
        minutes = int(self.config.get("reminders", {}).get("water_snooze_minutes", 10))
        self.service.engine.snooze_water(minutes)
        self.logger.log("water_snoozed", f"{minutes} minutes")

    def _on_reminder_dismiss(self, reason: str = "timeout") -> None:
        """记录提醒被忽略（超时关闭或 ESC）。"""
        kind = getattr(self, "_last_reminder_kind", "unknown")
        self.logger.log("reminder_dismissed", f"{kind}:{reason}")

    def _record_away_reason(self, reason: str) -> None:
        should_count_stand = self._should_count_away_as_stand(reason, self._pending_away_context)
        if reason != "未记录":
            self.state.record_away_reason(reason, count_stand=should_count_stand)
            suffix = " stand_counted" if should_count_stand else ""
            self.logger.log("away_reason", f"{reason}{suffix}")
        else:
            self.logger.log("away_reason_skipped", "user skipped")
        self._pending_away_context = {}

    def _should_count_away_as_stand(self, reason: str, context: dict[str, Any]) -> bool:
        """判断一次离席是否可以折算为健康起身。"""
        if context.get("stand_counted", False):
            return False
        if reason == "未记录":
            return False
        excluded = ("抽烟", "抽根", "开会", "外勤")
        if any(item in reason for item in excluded):
            return False
        detection = self.config.get("detection", {})
        max_seconds = int(detection.get("away_to_stand_max_seconds", 1200))
        min_sedentary = int(detection.get("away_to_stand_min_sedentary_seconds", 300))
        duration = int(context.get("duration_seconds", 0))
        sedentary = int(context.get("sedentary_seconds", 0))
        return 0 < duration <= max_seconds and sedentary >= min_sedentary

    def _test_onboarding(self) -> None:
        """测试首次启动向导（不检查 onboarding_done）。"""
        OnboardingWizard(self.root, self.config, on_complete=self._onboarding_done)
        self.logger.log("test_onboarding", "shown")

    def _test_sound(self) -> None:
        from .platform.sound import play_ribbit

        play_ribbit(self._sound_volume())
        self.logger.log("test_sound", "played")

    def _test_camera(self) -> str:
        message = self.service.camera_diagnostic()
        self.logger.log("test_camera", message.replace("\n", " | "))
        return message

    def _test_popup(self) -> None:
        self.popup.show_reminder(
            ReminderEvent("sedentary", "测试提醒", "这是右下角提醒弹窗测试。"),
            on_water=lambda _ml=250: None,
            on_snooze=lambda: None,
        )
        self.logger.log("test_popup", "shown")

    def _test_center_popup(self) -> None:
        self.popup.show_away_reason(lambda reason: self.logger.log("test_center_popup", reason))

    def _handle_tk_error(self, exc: type[BaseException], value: BaseException, _traceback) -> None:
        self.logger.log("tk_error", f"{exc.__name__}: {value}")

    def _apply_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=scaling.font("Microsoft YaHei UI", 10), padding=(12, 7))
        style.configure("TEntry", padding=(8, 5))
        style.configure("TCheckbutton", background="white")


def main() -> None:
    """程序入口函数。"""
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
