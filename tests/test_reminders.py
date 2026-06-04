from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from health_reminder.app import AppController
from health_reminder.core.config import DEFAULT_CONFIG
from health_reminder.core.event_log import EventLogger
from health_reminder.core.health_state import HealthStateStore
from health_reminder.services.reminders import ReminderDecisionEngine, in_do_not_disturb
from health_reminder.services.reminders import ReminderService


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

    def test_center_popup_switch_controls_away_reason_dialog(self):
        config = DEFAULT_CONFIG.copy()
        config["detection"] = {**config["detection"], "center_popup_enabled": False}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            ui_queue: Queue = Queue()
            service = ReminderService(
                lambda: config,
                ui_queue,
                HealthStateStore(root / "health_score.json", root / "away_reason.json"),
                EventLogger(root / "run.log"),
            )
            service._mark_absent(100.0, "test")
            service._mark_present(110.0, "test")
            self.assertTrue(ui_queue.empty())

    def test_return_payload_contains_away_context(self):
        config = DEFAULT_CONFIG.copy()
        config["detection"] = {**config["detection"], "center_popup_enabled": True}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            ui_queue: Queue = Queue()
            service = ReminderService(
                lambda: config,
                ui_queue,
                HealthStateStore(root / "health_score.json", root / "away_reason.json"),
                EventLogger(root / "run.log"),
            )
            service._sedentary_started_mono = 0.0
            service._mark_absent(600.0, "test")
            service._mark_present(900.0, "test")
            kind, payload = ui_queue.get_nowait()
            self.assertEqual(kind, "away_reason")
            self.assertEqual(payload["duration_seconds"], 300)
            self.assertEqual(payload["sedentary_seconds"], 600)
            self.assertFalse(payload["stand_counted"])

    def test_camera_interval_slows_down_after_away(self):
        config = DEFAULT_CONFIG.copy()

        with TemporaryDirectory() as temp:
            root = Path(temp)
            service = ReminderService(
                lambda: config,
                Queue(),
                HealthStateStore(root / "health_score.json", root / "away_reason.json"),
                EventLogger(root / "run.log"),
            )
            detection = config["detection"]
            self.assertEqual(service._camera_interval(detection), 15)
            service._mark_absent(100.0, "test")
            self.assertEqual(service._camera_interval(detection), 60)

    def test_pause_for_suppresses_due_reminders(self):
        base = datetime(2026, 5, 29, 8, 0)
        config = DEFAULT_CONFIG.copy()
        engine = ReminderDecisionEngine(base)
        event = engine.due(base + timedelta(minutes=90), config, paused=True)
        self.assertIsNone(event)

    def test_sedentary_tick_starts_stand_watch(self):
        base = datetime(2026, 5, 29, 8, 0)
        config = DEFAULT_CONFIG.copy()
        config["reminders"] = {
            **config["reminders"],
            "sedentary_interval_minutes": 1,
            "water_interval_minutes": 120,
        }
        config["detection"] = {**config["detection"], "privacy_mode": True}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            service = ReminderService(
                lambda: config,
                Queue(),
                HealthStateStore(root / "health_score.json", root / "away_reason.json"),
                EventLogger(root / "run.log"),
            )
            service.engine.last_sedentary = datetime.now() - timedelta(minutes=2)
            service._tick()
            self.assertGreater(service._stand_watch_until, 0)
            self.assertEqual(service.state.today().sedentary_alerts, 1)

    def test_short_non_negative_away_can_count_as_stand(self):
        fake = SimpleNamespace(config=DEFAULT_CONFIG)
        context = {"duration_seconds": 300, "sedentary_seconds": 600, "stand_counted": False}
        self.assertTrue(AppController._should_count_away_as_stand(fake, "上厕所", context))
        self.assertFalse(AppController._should_count_away_as_stand(fake, "抽根烟", context))
        self.assertFalse(AppController._should_count_away_as_stand(fake, "未记录", context))
        self.assertFalse(
            AppController._should_count_away_as_stand(
                fake, "上厕所", {**context, "duration_seconds": 1800}
            )
        )
        self.assertFalse(
            AppController._should_count_away_as_stand(
                fake, "上厕所", {**context, "stand_counted": True}
            )
        )

    def test_privacy_mode_skips_camera_diagnostic(self):
        config = DEFAULT_CONFIG.copy()
        config["detection"] = {**config["detection"], "privacy_mode": True}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            service = ReminderService(
                lambda: config,
                Queue(),
                HealthStateStore(root / "health_score.json", root / "away_reason.json"),
                EventLogger(root / "run.log"),
            )
            self.assertIn("隐私模式", service.camera_diagnostic())


if __name__ == "__main__":
    unittest.main()
