from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Any

from ..core.event_log import EventLogger
from ..core.health_state import HealthStateStore
from ..platform.camera import CameraPresenceDetector
from ..platform.media import is_media_playing
from ..platform.windows_idle import seconds_since_last_input


REMINDER_TITLES = {
    "sedentary": "该起身活动一下了",
    "water": "该喝水了",
    "combined": "喝水 + 起身活动",
    "work_start": "上班提醒",
    "work_end": "下班提醒",
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
            return ReminderEvent("combined", REMINDER_TITLES["combined"], "休息一下，喝口水，顺便活动肩颈。")

        if sedentary_due:
            self.sedentary_alert_active = True
            return ReminderEvent("sedentary", REMINDER_TITLES["sedentary"], "离开椅子走动两分钟，眼睛也休息一下。")

        if water_due:
            self.last_water = now
            self.water_snooze_until = None
            return ReminderEvent("water", REMINDER_TITLES["water"], "补充一杯水，给今天的健康分加一点蓝色。")

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
    def __init__(
        self,
        config_getter,
        ui_queue: queue.Queue,
        state: HealthStateStore,
        logger: EventLogger,
    ) -> None:
        self.config_getter = config_getter
        self.ui_queue = ui_queue
        self.state = state
        self.logger = logger
        self.engine = ReminderDecisionEngine()
        self.camera = CameraPresenceDetector()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_work_day: str | None = None
        self._work_start_shown = False
        self._work_end_shown = False
        self._last_camera_check = 0.0
        self._camera_misses = 0
        self._away_pending = False
        self._presence_status = "using"
        self._away_started_mono: float | None = None
        self._sedentary_started_mono = time.monotonic()
        self._stand_watch_until = 0.0
        self._next_stand_watch_check = 0.0
        self._last_tick = time.monotonic()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="health-reminder-service", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self) -> None:
        self.logger.log("service_start", "background reminder service started")
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                self.logger.log("service_error", str(exc))
            self._stop.wait(1)
        self.logger.log("service_stop", "background reminder service stopped")

    def _tick(self) -> None:
        now_mono = time.monotonic()
        elapsed = int(now_mono - self._last_tick)
        self._last_tick = now_mono
        if elapsed > 0:
            self.state.add_seconds("run_seconds", elapsed)
            self.state.add_seconds("computer_seconds", elapsed)

        config = self.config_getter()
        now = datetime.now()
        self._check_work_reminders(now, config)

        idle_seconds = seconds_since_last_input()
        self._update_presence_from_input(now_mono, idle_seconds, config)
        self._check_stand_watch(now_mono, config)
        self._check_camera(now_mono, idle_seconds, config)
        self._publish_presence_metrics(now_mono, config)

        paused = self._presence_status != "using"

        if is_media_playing():
            self.state.set_status("检测到媒体播放，提醒降低打扰")

        event = self.engine.due(now, config, paused=paused)
        if event:
            self.logger.log("reminder", event.kind)
            if event.kind in {"sedentary", "combined"}:
                self.state.increment("sedentary_alerts", 1)
                self._start_stand_watch(now_mono, config)
            self.ui_queue.put(("reminder", event))

    def _check_work_reminders(self, now: datetime, config: dict[str, Any]) -> None:
        today = now.date().isoformat()
        if today != self._last_work_day:
            self._last_work_day = today
            self._work_start_shown = False
            self._work_end_shown = False
        try:
            start = parse_clock(config.get("work_time", {}).get("start", "08:30"))
            end = parse_clock(config.get("work_time", {}).get("end", "17:00"))
        except Exception:
            return
        current = now.time().replace(second=0, microsecond=0)
        if not self._work_start_shown and current >= start:
            self._work_start_shown = True
            self.ui_queue.put(("reminder", ReminderEvent("work_start", REMINDER_TITLES["work_start"], "今天也要注意补水和起身活动。")))
        if not self._work_end_shown and current >= end:
            self._work_end_shown = True
            self.ui_queue.put(("reminder", ReminderEvent("work_end", REMINDER_TITLES["work_end"], "工作时间结束，记得收尾并放松一下。")))

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
        if not detection.get("camera_enabled", True):
            return
        idle_threshold = int(detection.get("camera_idle_threshold_seconds", 60))
        if idle_seconds < idle_threshold:
            return
        interval = max(10, int(detection.get("camera_interval_seconds", 60)))
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

    def _mark_present(self, now_mono: float, source: str) -> None:
        was_away = self._presence_status != "using"
        self._presence_status = "using"
        self._away_started_mono = None
        self._camera_misses = 0
        if was_away:
            self._sedentary_started_mono = now_mono
            self.engine.confirm_stand()
            self.logger.log("presence_return", source)
            self.state.set_status("电脑正在使用，久坐计时已重新开始")
            if self._away_pending:
                self.ui_queue.put(("away_reason", None))
                self._away_pending = False

    def _mark_absent(self, now_mono: float, source: str) -> None:
        if self._presence_status == "using":
            self.logger.log("presence_away", source)
            self._away_started_mono = now_mono
            self._sedentary_started_mono = now_mono
            self.engine.confirm_stand()
            self.state.set_status("检测到人不在电脑前")
        self._presence_status = "away"
        self._away_pending = True

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
