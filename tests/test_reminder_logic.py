import unittest
from datetime import datetime, timedelta

from health_reminder.app import HealthReminderApp
from health_reminder.constants import DEFAULT_CONFIG


class ReminderLogicTests(unittest.TestCase):
    def make_app(self):
        app = HealthReminderApp.__new__(HealthReminderApp)
        app.config = DEFAULT_CONFIG.copy()
        app.last_sit_reset = datetime(2026, 5, 28, 8, 30)
        app.last_water_reset = datetime(2026, 5, 28, 8, 30)
        return app

    def attach_fake_outputs(self, app):
        class FakeLog:
            def __init__(self):
                self.entries = []

            def write(self, message):
                self.entries.append(message)

        class FakeUi:
            def __init__(self):
                self.toasts = []
                self.water_popups = []

            def show_toast(self, title, message):
                self.toasts.append((title, message))

            def show_water_popup(self, message):
                self.water_popups.append(message)

        app.log = FakeLog()
        app.ui = FakeUi()
        return app

    def test_due_reminders_are_merged_when_next_one_is_nearby(self):
        app = self.make_app()
        app.config["sit_interval_minutes"] = 45
        app.config["water_interval_minutes"] = 49
        app.config["merge_window_minutes"] = 5

        now = datetime(2026, 5, 28, 9, 15)
        due = app._collect_due_reminders(now)
        merged = app._merge_nearby_reminders(now, due)

        self.assertEqual({"sit", "water"}, {item["kind"] for item in merged})

    def test_due_reminders_are_not_merged_outside_window(self):
        app = self.make_app()
        app.config["sit_interval_minutes"] = 45
        app.config["water_interval_minutes"] = 51
        app.config["merge_window_minutes"] = 5

        now = datetime(2026, 5, 28, 9, 15)
        due = app._collect_due_reminders(now)
        merged = app._merge_nearby_reminders(now, due)

        self.assertEqual(["sit"], [item["kind"] for item in merged])

    def test_reset_health_timers_uses_same_timestamp(self):
        app = self.make_app()
        when = datetime(2026, 5, 28, 10, 0)

        app._reset_health_timers(when)

        self.assertEqual(when, app.last_sit_reset)
        self.assertEqual(when, app.last_water_reset)

    def test_quiet_time_supports_overnight_ranges(self):
        app = self.make_app()
        app.config["quiet_enabled"] = True
        app.config["quiet_start"] = "22:00"
        app.config["quiet_end"] = "08:00"

        original_datetime = __import__("health_reminder.app").app.datetime

        class FakeDateTime:
            @classmethod
            def now(cls):
                return datetime(2026, 5, 28, 23, 0)

        try:
            __import__("health_reminder.app").app.datetime = FakeDateTime
            self.assertTrue(app.is_quiet_time())
        finally:
            __import__("health_reminder.app").app.datetime = original_datetime

    def test_water_reminder_uses_only_confirmation_popup(self):
        app = self.attach_fake_outputs(self.make_app())

        app._show_health_reminders([
            {
                "kind": "water",
                "title": "喝水提醒",
                "message": "喝口水",
            }
        ])

        self.assertEqual([], app.ui.toasts)
        self.assertEqual(["喝口水"], app.ui.water_popups)
        self.assertEqual(["喝水提醒: 喝口水"], app.log.entries)

    def test_merged_water_reminder_uses_single_confirmation_popup(self):
        app = self.attach_fake_outputs(self.make_app())

        app._show_health_reminders([
            {
                "kind": "sit",
                "title": "久坐提醒",
                "message": "起来走走",
            },
            {
                "kind": "water",
                "title": "喝水提醒",
                "message": "喝口水",
            },
        ])

        self.assertEqual([], app.ui.toasts)
        self.assertEqual(["久坐提醒：起来走走\n喝水提醒：喝口水"], app.ui.water_popups)
        self.assertEqual(
            ["健康提醒: 久坐提醒：起来走走\n喝水提醒：喝口水"],
            app.log.entries,
        )


if __name__ == "__main__":
    unittest.main()
