from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .paths import DataPaths
from .storage import deep_merge, read_json, write_json


DEFAULT_CONFIG: dict[str, Any] = {
    "version": "v2.8.1",
    "work_time": {
        "start": "08:30",
        "end": "17:00",
    },
    "reminders": {
        "sedentary_interval_minutes": 45,
        "water_interval_minutes": 60,
        "water_snooze_minutes": 10,
        "merge_window_minutes": 5,
    },
    "do_not_disturb": {
        "enabled": False,
        "start": "12:00",
        "end": "13:00",
    },
    "detection": {
        "idle_after_seconds": 300,
        "away_after_seconds": 180,
        "camera_enabled": True,
        "privacy_mode": False,
        "camera_idle_threshold_seconds": 20,
        "camera_interval_seconds": 15,
        "camera_away_interval_seconds": 60,
        "camera_confirm_misses": 3,
        "away_red_after_seconds": 1200,
        "stand_watch_interval_seconds": 20,
        "stand_watch_duration_seconds": 180,
        "center_popup_enabled": True,
        "away_to_stand_max_seconds": 1200,
        "away_to_stand_min_sedentary_seconds": 300,
    },
    "system": {
        "autostart": False,
        "show_main_on_start": False,
        "sound_volume_percent": 80,
        "popup_mode": "app",
        "popup_retention_seconds": 600,
    },
    "goals": {
        "water_ml": 2000,
        "stand_count": 8,
        "max_sit_streak_minutes": 45,
    },
}


@dataclass
class ConfigStore:
    """配置文件存储类，自动处理默认值合并和JSON读写。"""
    paths: DataPaths

    def load(self) -> dict[str, Any]:
        """加载配置文件，缺失字段自动补全为默认值。"""
        loaded = read_json(self.paths.config, {})
        config = deep_merge(deepcopy(DEFAULT_CONFIG), loaded if isinstance(loaded, dict) else {})
        config["version"] = DEFAULT_CONFIG["version"]
        write_json(self.paths.config, config)
        return config

    def save(self, config: dict[str, Any]) -> bool:
        """将配置写入JSON文件。"""
        merged = deep_merge(deepcopy(DEFAULT_CONFIG), config)
        merged["version"] = DEFAULT_CONFIG["version"]
        return write_json(self.paths.config, merged)

    def update(self, dotted_key: str, value: Any) -> dict[str, Any]:
        """更新配置中的指定字段。"""
        config = self.load()
        cursor = config
        keys = dotted_key.split(".")
        for key in keys[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[keys[-1]] = value
        self.save(config)
        return config
