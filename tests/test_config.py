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

    def test_version_is_migrated_to_current_release(self):
        with TemporaryDirectory() as temp:
            paths = DataPaths(Path(temp))
            paths.config.write_text('{"version": "v2.7.6-beta"}', encoding="utf-8")
            config = ConfigStore(paths).load()
            self.assertEqual(config["version"], "v2.7.7")


if __name__ == "__main__":
    unittest.main()
