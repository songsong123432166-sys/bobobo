"""Reminder scheduling service with prostatitis-aware intervals."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Any, Callable

from ..core.event_log import EventLogger
from ..core.health_state import HealthStateStore
from ..platform.camera import CameraPresenceDetector
from ..platform.media import is_media_playing
from ..platform.windows_idle import seconds_since_last_input


REMINDER_TITLES = {
    "sedentary": "\u8be5\u8d77\u8eab\u6d3b\u52a8\u4e00\u4e0b\u4e86",
    "water": "\u8be5\u559d\u6c34\u4e86",
    "combined": "\u559d\u6c34 + \u8d77\u8eab\u6d3b\u52a8",
    "work_start": "\u4e0a\u73ed\u63d0\u9192",
    "work_end": "\u4e0b\u73ed\u63d0\u9192",
}


@dataclass
class ReminderEvent:
    kind: str
    title: str
    message: str


def parse_clock(value: str) -> dt_time:
    hour, minute = value.split(":", 1)
    return dt_time(int(hour), int(minute))


def is_time_between(now_time: dt_time, start: dt_time, end: dt_time) -> bool:
    if start <= end:
        return start <= now_time <= end
    return now_time >= start or now_time <= end


def in_do_not_disturb(now: datetime, config: dict[str, Any]) -> bool:
    dnd = config.get("do_not_disturb", {})
    if not dnd.get("enabled", False):
        return False
    try:
        return is_time_between(now.time(), parse_clock(dnd["start"]), parse_clock(dnd["end"]))
    except Exception:
        return False


class ReminderDecisionEngine:
    def __init__(self, now: datetime | None = None) -> None:
        base = now or datetime.now()
        self.last_sedentary = base
        self.last_water = base
        self.water_snooze_until: datetime | None = None
        self.sedentary_alert_active = False

    def reset(self, now: datetime | None = None) -> None:
        base = now or datetime.now()
        self.last_sedentary = base
        self.last_water = base
        self.water_snooze_until = None
        self.sedentary_alert_active = False

    def snooze_water(self, minutes: int, now: datetime | None = None) -> None:
        self.water_snooze_until = (now or datetime.now()) + timedelta(minutes=minutes)

    def confirm_water(self, now: datetime | None = None) -> None:
        self.last_water = now or datetime.now()
        self.water_snooze_until = None

    def confirm_stand(self, now: datetime | None = None) -> None:
        self.last_sedentary = now or datetime.now()
        self.sedentary_alert_active = False

    def due(self, now: datetime, config: dict[str, Any], paused: bool = False) -> ReminderEvent | None:
        if paused or in_do_not_disturb(now, config):
            return None

        reminders = config.get("reminders", {})
        sedentary_minutes = max(1, int(reminders.get("sedentary_interval_minutes", 45)))
        water_minutes = max(1, int(reminders.get("water_interval_minutes", 60)))
        merge_minutes = max(0, int(reminders.get("merge_window_minutes", 5)))

        sedentary_due_at = self.last_sedentary + timedelta(minutes=sedentary_minutes)
        water_due_at = self.last_water + timedelta(minutes=water_minutes)
        if self.water_snooze_until is not None:
            water_due_at = max(water_due_at, self.water_snooze_until)

        sedentary_due = now >= sedentary_due_at and not self.sedentary_alert_active
        water_due = now >= water_due_at
        close = abs((sedentary_due_at - water_due_at).total_seconds()) <= merge_minutes * 60

        if (sedentary_due and water_due) or (close and (sedentary_due or water_due)):
            if sedentary_due:
                self.sedentary_alert_active = True
            self.last_water = now
            self.water_snooze_until = None
            return ReminderEvent("combined", REMINDER_TITLES["combined"],
                                 "\u4f11\u606f\u4e00\u4e0b\uff0c\u559d\u53e3\u6c34\uff0c\u987a\u4fbf\u6d3b\u52a8\u80a9\u8180\u3002")

        if sedentary_due:
            self.sedentary_alert_active = True
            return ReminderEvent("sedentary", REMINDER_TITLES["sedentary"],
                                 "\u79bb\u5f00\u6905\u5b50\u8d70\u52a8\u4e24\u5206\u949f\uff0c\u773c\u775b\u4e5f\u4f11\u606f\u4e00\u4e0b\u3002")

        if water_due:
            self.last_water = now
            self.water_snooze_until = None
            return ReminderEvent("water", REMINDER_TITLES["water"],
                                 "\u8865\u5145\u4e00\u676f\u6c34\uff0c\u7ed9\u4eca\u5929\u7684\u5065\u5eb7\u5206\u52a0\u4e00\u70b9\u84dd\u8272\u3002")

        return None

    def remaining_seconds(self, now: datetime, config: dict[str, Any]) -> tuple[int, int]:
        reminders = config.get("reminders", {})
        sedentary_due_at = self.last_sedentary + timedelta(minutes=int(reminders.get("sedentary_interval_minutes", 45)))
        water_due_at = self.last_water + timedelta(minutes=int(reminders.get("water_interval_minutes", 60)))
        if self.water_snooze_until is not None:
            water_due_at = max(water_due_at, self.water_snooze_until)
        return (
            max(0, int((sedentary_due_at - now).total_seconds())),
            max(0, int((water_due_at - now).total_seconds())),
        )


class ReminderService:
    TICK_SECONDS = 5

    def __init__(
        self,
        get_config: Callable[[], dict[str, Any]],
        ui_queue: queue.Queue[tuple[str, Any]],
        state: HealthStateStore,
        logger: EventLogger,
    ) -> None:
        self._get_config = get_config
        self.ui_queue = ui_queue
        self.state = state
        self.logger = logger
        self.engine = ReminderDecisionEngine()
        self.camera = CameraPresenceDetector()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._paused_until: datetime | None = None
        self._presence_status = "using"
        self._away_started_mono: float | None = None
        self._sedentary_started_mono: float = time.monotonic()
        self._camera_misses = 0
        self._last_camera_check = 0.0
        self._stand_watch_until = 0.0
        self._next_stand_watch_check = 0.0
        self._away_pending = False
        self._last_work_event: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="reminder-service", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def pause_for(self, minutes: int) -> None:
        self._paused_until = datetime.now() + timedelta(minutes=max(1, minutes))
        self.logger.log("reminders_paused", f"{minutes} minutes")

    def resume(self) -> None:
        self._paused_until = None
        self.logger.log("reminders_resumed", "manual resume")

    def is_paused(self, now: datetime | None = None) -> bool:
        if self._paused_until is None:
            return False
        current = now or datetime.now()
        if current >= self._paused_until:
            self._paused_until = None
            self.logger.log("reminders_resumed", "pause expired")
            return False
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                self.logger.log("service_tick_error", str(exc))
            self._stop_event.wait(self.TICK_SECONDS)

    def _tick(self) -> None:
        now = datetime.now()
        config = self._get_config()
        paused = self.is_paused(now)
        if not paused:
            self._check_work_events(now, config)

        event = self.engine.due(now, config, paused=paused)
        if event is not None:
            self.logger.log("reminder_fired", event.kind)
            self.ui_queue.put(("reminder", event))

        idle = seconds_since_last_input()
        now_mono = time.monotonic()
        self._update_presence_from_input(now_mono, idle, config)

        if self._stand_watch_until > 0:
            self._check_stand_watch(now_mono, config)
        self._check_camera(now_mono, idle, config)
        self._publish_presence_metrics(now_mono, config)

    def _check_work_events(self, now: datetime, config: dict[str, Any]) -> None:
        work = config.get("work_time", {})
        start_str = work.get("start", "")
        end_str = work.get("end", "")
        if not start_str or not end_str:
            return
        try:
            start_t = parse_clock(start_str)
            end_t = parse_clock(end_str)
        except Exception:
            return

        event_kind: str | None = None
        if is_time_between(now.time(), start_t, (datetime.combine(now.date(), start_t) + timedelta(minutes=2)).time()):
            event_kind = "work_start"
        elif is_time_between(now.time(), end_t, (datetime.combine(now.date(), end_t) + timedelta(minutes=2)).time()):
            event_kind = "work_end"

        if event_kind and event_kind != self._last_work_event:
            self._last_work_event = event_kind
            self.logger.log("work_event", event_kind)
            self.ui_queue.put(("reminder", ReminderEvent(
                event_kind, REMINDER_TITLES[event_kind],
                "\u4e0a\u73ed\u65f6\u95f4\u5f00\u59cb\uff0c\u8bb0\u5f97\u6536\u5c3e\u5e76\u653e\u677e\u4e00\u4e0b\u3002" if event_kind == "work_end" else "\u5de5\u4f5c\u65f6\u95f4\u5f00\u59cb\u4e86\uff0c\u52a0\u6cb9\uff01",
            )))

    def _update_presence_from_input(self, now_mono: float, idle_seconds: float, config: dict[str, Any]) -> None:
        threshold = int(config.get("detection", {}).get("camera_idle_threshold_seconds", 60))
        if idle_seconds < threshold:
            self._mark_present(now_mono, "keyboard_mouse")

    def _start_stand_watch(self, now_mono: float, config: dict[str, Any]) -> None:
        detection = config.get("detection", {})
        duration = max(20, int(detection.get("stand_watch_duration_seconds", 180)))
        interval = max(5, int(detection.get("stand_watch_interval_seconds", 20)))
        self._stand_watch_until = now_mono + duration
        self._next_stand_watch_check = now_mono + interval
        self.logger.log("stand_watch_start", f"duration={duration}s interval={interval}s")

    def _check_stand_watch(self, now_mono: float, config: dict[str, Any]) -> None:
        if self._stand_watch_until <= 0:
            return
        if now_mono >= self._stand_watch_until:
            self._stand_watch_until = 0.0
            self.logger.log("stand_watch_timeout", "no away detected")
            return
        if now_mono < self._next_stand_watch_check:
            return
        interval = max(5, int(config.get("detection", {}).get("stand_watch_interval_seconds", 20)))
        self._next_stand_watch_check = now_mono + interval
        result = self.camera.check()
        self.logger.log("stand_watch_camera", result.message)
        if result.available and result.person_present is False:
            self.state.increment("stand_count", 1)
            self.engine.confirm_stand()
            self._stand_watch_until = 0.0
            self._mark_absent(now_mono, "stand_confirmed")
            self.logger.log("stand_confirmed_by_camera", "person left after reminder")

    def _check_camera(self, now_mono: float, idle_seconds: float, config: dict[str, Any]) -> None:
        detection = config.get("detection", {})
        if detection.get("privacy_mode", False) or not detection.get("camera_enabled", True):
            return
        idle_threshold = int(detection.get("camera_idle_threshold_seconds", 60))
        if idle_seconds < idle_threshold:
            return
        interval = self._camera_interval(detection)
        if now_mono - self._last_camera_check < interval:
            return
        self._last_camera_check = now_mono
        result = self.camera.check()
        self.logger.log("camera_check", result.message)
        if not result.available or result.person_present is None:
            idle_after = int(detection.get("idle_after_seconds", 300))
            if idle_seconds >= idle_after:
                self._mark_absent(now_mono, "idle_fallback")
            return
        if result.person_present:
            self._camera_misses = 0
            self._mark_present(now_mono, "camera")
            return
        self._camera_misses += 1
        confirm_misses = max(1, int(detection.get("camera_confirm_misses", 3)))
        if self._camera_misses >= confirm_misses:
            self._mark_absent(now_mono, "camera")

    def _camera_interval(self, detection: dict[str, Any]) -> int:
        if self._presence_status == "using":
            return max(5, int(detection.get("camera_interval_seconds", 15)))
        return max(15, int(detection.get("camera_away_interval_seconds", 60)))

    def camera_diagnostic(self) -> str:
        detection = self._get_config().get("detection", {})
        if detection.get("privacy_mode", False):
            return "隐私模式已开启，摄像头检测已暂停。"
        if not detection.get("camera_enabled", True):
            return "摄像头检测已关闭。"
        result = self.camera.check()
        status = "检测到有人" if result.person_present else "未检测到人" if result.person_present is False else "无法判断"
        return f"{status}\n可用：{result.available}\n结果：{result.message}"

    def _mark_present(self, now_mono: float, source: str) -> None:
        was_away = self._presence_status != "using"
        self._presence_status = "using"
        self._away_started_mono = None
        self._camera_misses = 0
        if was_away:
            self._sedentary_started_mono = now_mono
            self.engine.confirm_stand()
            self.logger.log("presence_return", source)
            self.state.set_status("\u7535\u8111\u6b63\u5728\u4f7f\u7528\uff0c\u4e45\u5750\u8ba1\u65f6\u5df2\u91cd\u65b0\u5f00\u59cb")
            if self._away_pending and self._center_popup_enabled():
                self.ui_queue.put(("away_reason", None))
            self._away_pending = False

    def _mark_absent(self, now_mono: float, source: str) -> None:
        if self._presence_status == "using":
            self.logger.log("presence_away", source)
            self._away_started_mono = now_mono
            self._sedentary_started_mono = now_mono
            self.engine.confirm_stand()
            self.state.set_status("\u68c0\u6d4b\u5230\u4eba\u4e0d\u5728\u7535\u8111\u524d")
        self._presence_status = "away"
        self._away_pending = True

    def _center_popup_enabled(self) -> bool:
        config = self._get_config()
        return bool(config.get("detection", {}).get("center_popup_enabled", True))

    def _publish_presence_metrics(self, now_mono: float, config: dict[str, Any]) -> None:
        red_after = int(config.get("detection", {}).get("away_red_after_seconds", 1200))
        if self._presence_status == "using":
            sedentary_seconds = int(now_mono - self._sedentary_started_mono)
            status = "using"
        else:
            away_started = self._away_started_mono or now_mono
            away_seconds = int(now_mono - away_started)
            sedentary_seconds = 0
            status = "away_long" if away_seconds >= red_after else "away_short"
        self.state.set_presence(status, sedentary_seconds)
