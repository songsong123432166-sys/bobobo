from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from health_reminder.core.health_state import HealthStateStore, calculate_health_score


class HealthStateTest(unittest.TestCase):
    def test_score_is_bounded(self):
        self.assertEqual(calculate_health_score({"water_count": 99, "stand_count": 99, "run_seconds": 999999}), 97)
        self.assertEqual(calculate_health_score({"sedentary_alerts": 99, "away_count": 99}), 32)

    def test_increment_today(self):
        with TemporaryDirectory() as temp:
            store = HealthStateStore(Path(temp) / "health_score.json", Path(temp) / "away_reason.json")
            store.increment("water_count")
            store.increment("stand_count", 2)
            today = store.today()
            self.assertEqual(today.water_count, 1)
            self.assertEqual(today.stand_count, 2)

    def test_presence_metrics_are_stored(self):
        with TemporaryDirectory() as temp:
            store = HealthStateStore(Path(temp) / "health_score.json", Path(temp) / "away_reason.json")
            store.set_presence("away_short", sedentary_seconds=0)
            today = store.today()
            self.assertEqual(today.presence_status, "away_short")
            self.assertEqual(today.sedentary_seconds, 0)


if __name__ == "__main__":
    unittest.main()
