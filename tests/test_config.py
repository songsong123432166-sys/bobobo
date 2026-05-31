from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from health_reminder.core.config import ConfigStore
from health_reminder.core.paths import DataPaths


class ConfigStoreTest(unittest.TestCase):
    def test_load_merges_defaults(self):
        with TemporaryDirectory() as temp:
            paths = DataPaths(Path(temp))
            paths.config.write_text('{"reminders": {"water_interval_minutes": 30}}', encoding="utf-8")
            config = ConfigStore(paths).load()
            self.assertEqual(config["reminders"]["water_interval_minutes"], 30)
            self.assertEqual(config["reminders"]["sedentary_interval_minutes"], 45)
            self.assertEqual(config["work_time"]["start"], "08:30")
            self.assertEqual(config["system"]["sound_volume_percent"], 80)
            self.assertEqual(config["detection"]["camera_idle_threshold_seconds"], 20)
            self.assertEqual(config["detection"]["camera_interval_seconds"], 15)
            self.assertEqual(config["detection"]["camera_away_interval_seconds"], 60)
            self.assertFalse(config["detection"]["privacy_mode"])
            self.assertEqual(config["goals"]["water_ml"], 2000)
            self.assertEqual(config["goals"]["stand_count"], 8)

    def test_version_is_migrated_to_current_release(self):
        with TemporaryDirectory() as temp:
            paths = DataPaths(Path(temp))
            paths.config.write_text('{"version": "v2.7.6-beta"}', encoding="utf-8")
            config = ConfigStore(paths).load()
            self.assertEqual(config["version"], "v2.7.7")


if __name__ == "__main__":
    unittest.main()
