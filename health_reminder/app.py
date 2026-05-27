import random
import threading
import time
from datetime import datetime, timedelta

import schedule
from pystray import Icon, Menu, MenuItem

from .config_store import load_config, normalize_clock, parse_clock, save_config
from .constants import APP_NAME, APP_TITLE, APP_VERSION, DEFAULT_CONFIG, SIT_REMINDERS, WATER_REMINDERS
from .event_log import EventLog
from .notifier import Notifier
from .tray_icon import create_icon_image
from .ui import UiManager
from .windows_integration import set_startup, start_screensaver


class HealthReminderApp:
    def __init__(self):
        self.config = load_config()
        self.log = EventLog()
        self.notifier = Notifier(self.log)
        self.ui = UiManager(self)
        self.last_sit_reset = datetime.now()
        self.last_water_reset = datetime.now()
        self.running = True
        self.tray_icon = None
        self.state_lock = threading.Lock()

    def notify(self, title, message):
        self.notifier.notify(title, message)

    def is_work_time(self):
        now = datetime.now().time()
        start = parse_clock(self.config["work_start"], DEFAULT_CONFIG["work_start"])
        end = parse_clock(self.config["work_end"], DEFAULT_CONFIG["work_end"])
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end

    def is_meeting_mode(self):
        return bool(self.config.get("meeting_mode", False))

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
        self.notify("早上好", "新的一天开始了，记得多喝水，久了起来走走 💧")

    def evening_notice(self):
        self.notify("下班时间到了", "今天辛苦了，回家记得泡个温水澡放松一下 🛁")

    def reset_sit_timer(self, icon=None, item=None):
        with self.state_lock:
            self.last_sit_reset = datetime.now()
        self.notify("久坐提醒", "好的，计时重新开始")

    def reset_water_timer(self, icon=None, item=None):
        with self.state_lock:
            self.last_water_reset = datetime.now()
        self.notify("喝水提醒", "好的，记得保持")

    def snooze_water_timer(self):
        with self.state_lock:
            self.last_water_reset = datetime.now() - timedelta(
                minutes=self.config["water_interval_minutes"]
                - self.config["water_snooze_minutes"]
            )

    def check_sit_reminder(self):
        if self.is_meeting_mode() or not self.is_work_time():
            return

        with self.state_lock:
            minutes_passed = (datetime.now() - self.last_sit_reset).total_seconds() / 60
            if minutes_passed < self.config["sit_interval_minutes"]:
                return
            self.last_sit_reset = datetime.now()

        self.notify("久坐提醒", random.choice(SIT_REMINDERS))

    def check_water_reminder(self):
        if self.is_meeting_mode() or not self.is_work_time():
            return

        with self.state_lock:
            minutes_passed = (datetime.now() - self.last_water_reset).total_seconds() / 60
            if minutes_passed < self.config["water_interval_minutes"]:
                return
            self.last_water_reset = datetime.now()

        message = random.choice(WATER_REMINDERS)
        self.notify("喝水提醒", message)
        self.ui.show_water_popup(message)

    def scheduler_loop(self):
        while self.running:
            schedule.run_pending()
            self.check_sit_reminder()
            self.check_water_reminder()
            time.sleep(1)

    def get_status_text(self):
        mode = "开会模式" if self.is_meeting_mode() else "正常提醒"
        work = "工作时间内" if self.is_work_time() else "非工作时间"
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
            f"状态：{mode} / {work}\n"
            f"久坐提醒：约 {sit_next} 分钟后\n"
            f"喝水提醒：约 {water_next} 分钟后\n"
            f"最近事件：{self.log.last_event}"
        )

    def apply_settings(self, new_config):
        previous_meeting = bool(self.config["meeting_mode"])
        self.config.update(new_config)
        save_config(self.config)
        self.apply_startup_setting()
        self.setup_schedule()

        if self.config["meeting_mode"] and not previous_meeting:
            self.log.write("已开启开会模式")
            if self.config["meeting_auto_screensaver"]:
                self.start_screensaver()
        elif not self.config["meeting_mode"] and previous_meeting:
            self.log.write("已关闭开会模式")

        self.notify("设置已保存", "新的提醒设置已经生效")

    def toggle_meeting_mode(self, icon=None, item=None):
        self.config["meeting_mode"] = not bool(self.config["meeting_mode"])
        save_config(self.config)
        if self.config["meeting_mode"]:
            self.notify("开会模式", "已开启，久坐和喝水提醒会暂停")
            if self.config.get("meeting_auto_screensaver", False):
                self.start_screensaver()
        else:
            self.notify("开会模式", "已关闭，提醒恢复运行")

    def start_screensaver(self):
        start_screensaver(self.notify, self.log)

    def show_about(self, icon=None, item=None):
        self.notify("关于程序", f"{APP_TITLE} 正在运行")

    def quit_program(self, icon, item):
        self.running = False
        self.log.write("程序退出")
        icon.stop()

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
        self.notifier.set_tray_icon(self.tray_icon)
        self.tray_icon.run()
