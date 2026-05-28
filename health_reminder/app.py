import random
import threading
import time
from datetime import datetime, timedelta

import schedule
from pystray import Icon, Menu, MenuItem

from .activity import ActivityMonitor
from .camera_presence import CameraPresenceDetector
from .config_store import load_config, normalize_clock, parse_clock, save_config
from .constants import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    DEFAULT_CONFIG,
    EVENING_REMINDERS,
    MORNING_REMINDERS,
    SIT_REMINDERS,
    WATER_REMINDERS,
)
from .event_log import EventLog
from .health_score import HealthScore
from .tray_icon import create_icon_image
from .ui import UiManager
from .windows_integration import get_idle_seconds, is_media_playing, set_startup


class HealthReminderApp:
    def __init__(self):
        self.config = load_config()
        self.log = EventLog()
        self.health_score = HealthScore(self.log)
        self.activity = ActivityMonitor(
            get_idle_seconds,
            is_media_playing,
            self.config.get("away_after_minutes", DEFAULT_CONFIG["away_after_minutes"]),
            self.config.get("idle_after_minutes", DEFAULT_CONFIG["idle_after_minutes"]),
        )
        self.camera_presence = CameraPresenceDetector(
            self.log,
            self.config.get("camera_detection_enabled", False),
            self.config.get(
                "camera_detection_interval_minutes",
                DEFAULT_CONFIG["camera_detection_interval_minutes"],
            ),
        )
        self.ui = UiManager(self)
        self.started_at = datetime.now()
        self.meeting_started_at = datetime.now() if self.config.get("meeting_mode") else None
        self.last_sit_reset = datetime.now()
        self.last_water_reset = datetime.now()
        self.running = True
        self.tray_icon = None
        self.state_lock = threading.Lock()

    def notify(self, title, message):
        self.log.write(f"{title}: {message}")
        self.ui.show_toast(title, message)

    def is_work_time(self):
        now = datetime.now().time()
        start = parse_clock(self.config["work_start"], DEFAULT_CONFIG["work_start"])
        end = parse_clock(self.config["work_end"], DEFAULT_CONFIG["work_end"])
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end

    def is_meeting_mode(self):
        return bool(self.config.get("meeting_mode", False))

    def is_quiet_time(self):
        if not self.config.get("quiet_enabled", False):
            return False
        now = datetime.now().time()
        start = parse_clock(self.config.get("quiet_start"), DEFAULT_CONFIG["quiet_start"])
        end = parse_clock(self.config.get("quiet_end"), DEFAULT_CONFIG["quiet_end"])
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end

    def can_send_health_reminders(self):
        return (
            not self.is_meeting_mode()
            and not self.is_quiet_time()
            and self.is_work_time()
            and self.activity.is_available_for_reminders()
        )

    def apply_startup_setting(self):
        set_startup(bool(self.config.get("startup_enabled", True)), self.log)

    def setup_schedule(self):
        self.config["work_start"] = normalize_clock(
            self.config.get("work_start"),
            DEFAULT_CONFIG["work_start"],
        )
        self.config["work_end"] = normalize_clock(
            self.config.get("work_end"),
            DEFAULT_CONFIG["work_end"],
        )
        schedule.clear()
        schedule.every().day.at(self.config["work_start"]).do(self.morning_notice)
        schedule.every().day.at(self.config["work_end"]).do(self.evening_notice)
        self.log.write(
            f"已更新提醒计划：上班 {self.config['work_start']}，下班 {self.config['work_end']}"
        )

    def morning_notice(self):
        self.notify("早上好", random.choice(MORNING_REMINDERS))

    def evening_notice(self):
        self.notify("下班时间到了", random.choice(EVENING_REMINDERS))

    def reset_sit_timer(self, icon=None, item=None):
        with self.state_lock:
            self.last_sit_reset = datetime.now()
        score = self.health_score.record_sit_break()
        self.notify("久坐提醒", f"好的，计时重新开始。起身 +5 分，今日健康分 {score}")

    def reset_water_timer(self, icon=None, item=None):
        with self.state_lock:
            self.last_water_reset = datetime.now()
        score = self.health_score.record_water()
        self.notify("喝水提醒", f"好的，记得保持。喝水 +4 分，今日健康分 {score}")

    def _reset_health_timers(self, when=None):
        when = when or datetime.now()
        self.last_sit_reset = when
        self.last_water_reset = when

    def snooze_water_timer(self):
        with self.state_lock:
            self.last_water_reset = datetime.now() - timedelta(
                minutes=self.config["water_interval_minutes"]
                - self.config["water_snooze_minutes"]
            )

    def check_health_reminders(self):
        if not self.can_send_health_reminders():
            return

        now = datetime.now()
        with self.state_lock:
            due_items = self._collect_due_reminders(now)
            if not due_items:
                return
            reminders = self._merge_nearby_reminders(now, due_items)
            for item in reminders:
                if item["kind"] == "sit":
                    self.last_sit_reset = now
                elif item["kind"] == "water":
                    self.last_water_reset = now

        self._show_health_reminders(reminders)

    def _reminder_candidates(self):
        return [
            {
                "kind": "sit",
                "title": "久坐提醒",
                "message": random.choice(SIT_REMINDERS),
                "due_at": self.last_sit_reset
                + timedelta(minutes=self.config["sit_interval_minutes"]),
            },
            {
                "kind": "water",
                "title": "喝水提醒",
                "message": random.choice(WATER_REMINDERS),
                "due_at": self.last_water_reset
                + timedelta(minutes=self.config["water_interval_minutes"]),
            },
        ]

    def _collect_due_reminders(self, now):
        return [item for item in self._reminder_candidates() if item["due_at"] <= now]

    def _merge_nearby_reminders(self, now, due_items):
        merge_window = timedelta(minutes=self.config.get("merge_window_minutes", 5))
        reminders = list(due_items)
        kinds = {item["kind"] for item in reminders}

        for item in self._reminder_candidates():
            if item["kind"] in kinds:
                continue
            if timedelta(0) < item["due_at"] - now <= merge_window:
                reminders.append(item)
                kinds.add(item["kind"])

        return reminders

    def _show_health_reminders(self, reminders):
        if len(reminders) == 1:
            item = reminders[0]
            if item["kind"] == "water":
                self.log.write(f"{item['title']}: {item['message']}")
                self.ui.show_water_popup(item["message"])
            else:
                self.notify(item["title"], item["message"])
            return

        title = "健康提醒"
        message = "\n".join(f"{item['title']}：{item['message']}" for item in reminders)
        if any(item["kind"] == "water" for item in reminders):
            self.log.write(f"{title}: {message}")
            self.ui.show_water_popup(message)
        else:
            self.notify(title, message)

    def scheduler_loop(self):
        while self.running:
            self.check_activity_state()
            self.check_camera_presence()
            schedule.run_pending()
            self.check_health_reminders()
            time.sleep(1)

    def check_camera_presence(self):
        result = self.camera_presence.detect_if_due()
        if result is True:
            if self.activity.state != "using":
                self.activity.state = "using"
                with self.state_lock:
                    self._reset_health_timers()
                self.log.write("摄像头检测到电脑前有人，提醒计时已重新开始")
        elif result is False and self.activity.state == "using":
            self.activity.state = "idle"
            self.log.write("摄像头未检测到人，进入可能离开状态")

    def check_activity_state(self):
        old_state, new_state = self.activity.refresh()
        if old_state == new_state:
            return

        if new_state == "using":
            with self.state_lock:
                self._reset_health_timers()
            self.log.write("检测到用户回到电脑前，提醒计时已重新开始")
        elif new_state == "idle":
            self.log.write("检测到电脑进入可能离开状态，暂停健康提醒")
        else:
            self.log.write("检测到电脑进入离开状态，暂停健康提醒")

    def get_status_text(self):
        mode = "开会模式" if self.is_meeting_mode() else "正常提醒"
        work = "工作时间内" if self.is_work_time() else "非工作时间"
        activity = self.activity.label()
        idle_minutes = int(self.activity.idle_minutes())
        camera = self.camera_presence.last_result
        with self.state_lock:
            sit_next = max(
                0,
                int(
                    self.config["sit_interval_minutes"]
                    - (datetime.now() - self.last_sit_reset).total_seconds() / 60
                ),
            )
            water_next = max(
                0,
                int(
                    self.config["water_interval_minutes"]
                    - (datetime.now() - self.last_water_reset).total_seconds() / 60
                ),
            )
        return (
            f"状态：{mode} / {work} / 电脑{activity}\n"
            f"勿扰时间：{'开启中' if self.is_quiet_time() else '未开启'}\n"
            f"空闲时间：约 {idle_minutes} 分钟\n"
            f"摄像头检测：{camera}\n"
            f"久坐提醒：约 {sit_next} 分钟后\n"
            f"喝水提醒：约 {water_next} 分钟后\n"
            f"最近事件：{self.log.last_event}"
        )

    def get_current_sit_minutes(self):
        with self.state_lock:
            return (datetime.now() - self.last_sit_reset).total_seconds() / 60

    def get_runtime_minutes(self):
        return (datetime.now() - self.started_at).total_seconds() / 60

    def get_health_score_text(self):
        return self.health_score.summary_text(
            self.get_current_sit_minutes(),
            self.get_runtime_minutes(),
        )

    def apply_settings(self, new_config):
        previous_meeting = bool(self.config["meeting_mode"])
        self.config.update(new_config)
        save_config(self.config)
        self.activity.update_thresholds(
            self.config["away_after_minutes"],
            self.config["idle_after_minutes"],
        )
        self.camera_presence.update_settings(
            self.config["camera_detection_enabled"],
            self.config["camera_detection_interval_minutes"],
        )
        self.apply_startup_setting()
        self.setup_schedule()

        if self.config["meeting_mode"] and not previous_meeting:
            self.meeting_started_at = datetime.now()
            self.log.write("已开启开会模式")
        elif not self.config["meeting_mode"] and previous_meeting:
            self._record_meeting_duration()
            self.log.write("已关闭开会模式")

        self.notify("设置已保存", "新的提醒设置已经生效")

    def toggle_meeting_mode(self, icon=None, item=None):
        was_meeting = bool(self.config["meeting_mode"])
        self.config["meeting_mode"] = not was_meeting
        save_config(self.config)
        if self.config["meeting_mode"]:
            self.meeting_started_at = datetime.now()
            self.notify("开会模式", "已开启，久坐和喝水提醒会暂停")
        else:
            self._record_meeting_duration()
            self.notify("开会模式", "已关闭，提醒恢复运行")

    def show_about(self, icon=None, item=None):
        self.notify("关于程序", f"{APP_TITLE} 正在运行")

    def quit_program(self, icon, item):
        self._record_meeting_duration()
        self.running = False
        self.log.write("程序退出")
        icon.stop()

    def _record_meeting_duration(self):
        if self.meeting_started_at is None:
            return
        minutes = int((datetime.now() - self.meeting_started_at).total_seconds() / 60)
        self.health_score.add_meeting_minutes(minutes)
        self.meeting_started_at = None

    def run(self):
        self.log.write(f"程序启动：{APP_TITLE}")
        self.apply_startup_setting()
        self.setup_schedule()
        self.ui.start()
        threading.Thread(target=self.scheduler_loop, daemon=True).start()

        menu = Menu(
            MenuItem("打开主界面", self.ui.show_main_window),
            MenuItem("切换开会模式", self.toggle_meeting_mode),
            MenuItem(f"关于程序 v{APP_VERSION}", self.show_about),
            MenuItem("我站起来了", self.reset_sit_timer),
            MenuItem("喝水了", self.reset_water_timer),
            MenuItem("退出程序", self.quit_program),
        )

        self.tray_icon = Icon(APP_NAME, create_icon_image(), APP_TITLE, menu)
        self.tray_icon.run()
