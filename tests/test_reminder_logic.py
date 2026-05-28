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


if __name__ == "__main__":
    unittest.main()
