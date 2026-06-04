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

    "sedentary": "该起身活动一下了",

    "water": "该喝水了",

    "combined": "喝水 + 起身活动",

    "work_start": "上班提醒",

    "work_end": "下班提醒",

}


@dataclass

class ReminderEvent:

    """提醒事件数据类，包含提醒类型和相关文案。"""

    kind: str

    title: str

    message: str


def parse_clock(value: str) -> dt_time:

    """解析HH:MM时间字符串。"""

    hour, minute = value.split(":", 1)

    return dt_time(int(hour), int(minute))


def is_time_between(now_time: dt_time, start: dt_time, end: dt_time) -> bool:

    """判断是否在时间段内。"""

    if start <= end:

        return start <= now_time <= end

    return now_time >= start or now_time <= end


def in_do_not_disturb(now: datetime, config: dict[str, Any]) -> bool:

    """判断是否在勿扰时段。"""

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

        """重置所有计时器。"""

        base = now or datetime.now()

        self.last_sedentary = base

        self.last_water = base

        self.water_snooze_until = None

        self.sedentary_alert_active = False


    def snooze_water(self, minutes: int, now: datetime | None = None) -> None:

        """延迟喝水提醒。"""

        self.water_snooze_until = (now or datetime.now()) + timedelta(minutes=minutes)


    def confirm_water(self, now: datetime | None = None) -> None:

        """确认喝水。"""

        self.last_water = now or datetime.now()

        self.water_snooze_until = None


    def confirm_stand(self, now: datetime | None = None) -> None:

        """确认起身。"""

        self.last_sedentary = now or datetime.now()

        self.sedentary_alert_active = False


    def due(self, now: datetime, config: dict[str, Any], paused: bool = False) -> ReminderEvent | None:

        """检查待触发的提醒。"""

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

                                 (

                                     "休息一下，喝口水，顺便活动肩膀。"))


        if sedentary_due:

            self.sedentary_alert_active = True

            return ReminderEvent("sedentary", REMINDER_TITLES["sedentary"],

                                 (

                                     "离开椅子走动两分钟，眼睛也休息一下。"))


        if water_due:

            self.last_water = now

            self.water_snooze_until = None

            return ReminderEvent("water", REMINDER_TITLES["water"],

                                 (

                                     "补充一杯水，给今天的健康分加一点蓝色。"))


        return None


    def remaining_seconds(self, now: datetime, config: dict[str, Any]) -> tuple[int, int]:

        """返回距下次提醒的剩余秒数。"""

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

    """提醒后台服务，在独立线程中运行提醒引擎。"""

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
        self._away_sedentary_seconds = 0
        self._away_stand_counted = False

        self._camera_misses = 0

        self._last_camera_check = 0.0

        self._stand_watch_until = 0.0

        self._next_stand_watch_check = 0.0

        self._away_pending = False

        self._last_work_event: str | None = None
        self._last_tick_mono: float = time.monotonic()


    def start(self) -> None:

        """启动提醒服务线程。"""

        self._thread = threading.Thread(target=self._run, name="reminder-service", daemon=True)

        self._thread.start()


    def stop(self) -> None:

        """停止提醒服务线程。"""

        self._stop_event.set()


    def pause_for(self, minutes: int) -> None:

        """暂停提醒。"""

        self._paused_until = datetime.now() + timedelta(minutes=max(1, minutes))

        self.logger.log("reminders_paused", f"{minutes} minutes")


    def resume(self) -> None:

        """恢复提醒。"""

        self._paused_until = None

        self.logger.log("reminders_resumed", "manual resume")


    def is_paused(self, now: datetime | None = None) -> bool:

        """是否暂停中。"""

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

        now_mono = time.monotonic()

        event = self.engine.due(now, config, paused=paused)

        if event is not None:

            self.logger.log("reminder_fired", event.kind)
            if event.kind in ("sedentary", "combined"):
                self.state.increment("sedentary_alerts", 1)
                self._start_stand_watch(now_mono, config)

            self.ui_queue.put(("reminder", event))


        idle = seconds_since_last_input()

        self._update_presence_from_input(now_mono, idle, config)


        if self._stand_watch_until > 0:

            self._check_stand_watch(now_mono, config)

        self._check_camera(now_mono, idle, config)

        self._publish_presence_metrics(now_mono, config)

        # 累加运行时长和电脑使用时长
        elapsed = int(now_mono - self._last_tick_mono)
        self._last_tick_mono = now_mono
        if elapsed > 0:
            self.state.add_seconds("run_seconds", elapsed)
            if self._presence_status == "using":
                self.state.add_seconds("computer_seconds", elapsed)


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

                ("上班时间开始，记得收尾并放松一下。"

                 if event_kind == "work_end"

                  else "工作时间开始了，加油！"),

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

            self.state.set_status("已记录一次起身，久坐计时已重置。")

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

        """执行摄像头诊断。"""

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
        away_duration = 0
        if was_away and self._away_started_mono is not None:
            away_duration = max(0, int(now_mono - self._away_started_mono))

        self._presence_status = "using"

        self._away_started_mono = None

        self._camera_misses = 0

        if was_away:

            self._sedentary_started_mono = now_mono

            self.engine.confirm_stand()

            self.logger.log("presence_return", source)

            self.state.set_status(

                "电脑正在使用，久坐计时已重新开始")

            if self._away_pending and self._center_popup_enabled():

                self.ui_queue.put(("away_reason", {
                    "duration_seconds": away_duration,
                    "sedentary_seconds": self._away_sedentary_seconds,
                    "stand_counted": self._away_stand_counted,
                    "return_source": source,
                }))

            self._away_pending = False
            self._away_sedentary_seconds = 0
            self._away_stand_counted = False


    def _mark_absent(self, now_mono: float, source: str) -> None:

        if self._presence_status == "using":

            self.logger.log("presence_away", source)

            self._away_started_mono = now_mono
            self._away_sedentary_seconds = max(0, int(now_mono - self._sedentary_started_mono))
            self._away_stand_counted = source == "stand_confirmed"

            self._sedentary_started_mono = now_mono

            self.engine.confirm_stand()

            self.state.set_status("检测到人不在电脑前")

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

