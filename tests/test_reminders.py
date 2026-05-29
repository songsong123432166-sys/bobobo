from datetime import datetime, timedelta
import unittest

from health_reminder.core.config import DEFAULT_CONFIG
from health_reminder.services.reminders import ReminderDecisionEngine, in_do_not_disturb


class ReminderDecisionEngineTest(unittest.TestCase):
    def test_close_sedentary_and_water_are_merged(self):
        base = datetime(2026, 5, 29, 8, 0)
        config = DEFAULT_CONFIG.copy()
        config["reminders"] = {
            "sedentary_interval_minutes": 45,
            "water_interval_minutes": 48,
            "water_snooze_minutes": 10,
            "merge_window_minutes": 5,
        }
        engine = ReminderDecisionEngine(base)
        event = engine.due(base + timedelta(minutes=45), config)
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, "combined")

    def test_sedentary_reminder_waits_for_stand_confirmation(self):
        base = datetime(2026, 5, 29, 8, 0)
        config = DEFAULT_CONFIG.copy()
        config["reminders"] = {
            "sedentary_interval_minutes": 45,
            "water_interval_minutes": 120,
            "water_snooze_minutes": 10,
            "merge_window_minutes": 5,
        }
        engine = ReminderDecisionEngine(base)
        first = engine.due(base + timedelta(minutes=45), config)
        second = engine.due(base + timedelta(minutes=46), config)
        self.assertEqual(first.kind, "sedentary")
        self.assertIsNone(second)
        engine.confirm_stand(base + timedelta(minutes=50))
        self.assertEqual(engine.remaining_seconds(base + timedelta(minutes=50), config)[0], 2700)

    def test_do_not_disturb_crosses_midnight(self):
        config = DEFAULT_CONFIG.copy()
        config["do_not_disturb"] = {"enabled": True, "start": "23:00", "end": "07:00"}
        self.assertTrue(in_do_not_disturb(datetime(2026, 5, 29, 23, 30), config))
        self.assertTrue(in_do_not_disturb(datetime(2026, 5, 30, 6, 30), config))
        self.assertFalse(in_do_not_disturb(datetime(2026, 5, 30, 12, 0), config))


if __name__ == "__main__":
    unittest.main()
