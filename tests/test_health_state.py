from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from health_reminder.core.health_state import HealthStateStore
from health_reminder.core.scoring import calculate_score


class HealthStateTest(unittest.TestCase):
    def test_score_is_bounded(self):
        best = calculate_score(
            {
                "water_ml": 2200,
                "stand_count": 8,
                "toilet_count": 6,
                "toilet_max_gap_hours": 2,
                "max_sit_streak_minutes": 30,
                "smoke_count": 0,
            }
        )
        worst = calculate_score(
            {
                "water_ml": 0,
                "stand_count": 0,
                "toilet_count": 20,
                "toilet_max_gap_hours": 5,
                "max_sit_streak_minutes": 180,
                "smoke_count": 12,
            }
        )
        self.assertEqual(best.total, 100)
        self.assertEqual(worst.total, 3)

    def test_score_insight_points_to_weakest_dimension(self):
        score = calculate_score(
            {
                "water_ml": 0,
                "stand_count": 8,
                "toilet_count": 6,
                "toilet_max_gap_hours": 2,
                "max_sit_streak_minutes": 30,
                "smoke_count": 0,
            }
        )
        self.assertEqual(score.weakest_dimension()[0], "喝水")
        self.assertIn("喝水", score.insight())

    def test_increment_today(self):
        with TemporaryDirectory() as temp:
            store = HealthStateStore(
                Path(temp) / "health_score.json", Path(temp) / "away_reason.json"
            )
            store.increment("water_count")
            store.increment("stand_count", 2)
            today = store.today()
            self.assertEqual(today.water_count, 1)
            self.assertEqual(today.stand_count, 2)

    def test_presence_metrics_are_stored(self):
        with TemporaryDirectory() as temp:
            store = HealthStateStore(
                Path(temp) / "health_score.json", Path(temp) / "away_reason.json"
            )
            store.set_presence("away_short", sedentary_seconds=0)
            today = store.today()
            self.assertEqual(today.presence_status, "away_short")
            self.assertEqual(today.sedentary_seconds, 0)

    def test_away_reason_does_not_increment_away_count_but_can_count_stand(self):
        with TemporaryDirectory() as temp:
            store = HealthStateStore(
                Path(temp) / "health_score.json", Path(temp) / "away_reason.json"
            )
            store.record_away_reason("上厕所", count_stand=True)
            today = store.today()
            self.assertEqual(today.away_count, 0)
            self.assertEqual(today.stand_count, 1)
            self.assertEqual(today.toilet_count, 1)


if __name__ == "__main__":
    unittest.main()
