from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .storage import read_json, write_json


DEFAULT_DAY = {
    "water_count": 0,
    "stand_count": 0,
    "away_count": 0,
    "sedentary_alerts": 0,
    "sedentary_seconds": 0,
    "computer_seconds": 0,
    "run_seconds": 0,
    "presence_status": "using",
    "last_status": "运行中",
    "last_update": "",
}


@dataclass
class TodayStats:
    date: str
    water_count: int
    stand_count: int
    away_count: int
    sedentary_alerts: int
    sedentary_seconds: int
    computer_seconds: int
    run_seconds: int
    health_score: int
    presence_status: str
    last_status: str


class HealthStateStore:
    def __init__(self, score_path: Path, away_path: Path) -> None:
        self.score_path = score_path
        self.away_path = away_path
        self._lock = RLock()

    def _load(self) -> dict[str, Any]:
        data = read_json(self.score_path, {"days": {}})
        if not isinstance(data, dict):
            data = {"days": {}}
        data.setdefault("days", {})
        return data

    def _day(self, data: dict[str, Any], day: str | None = None) -> dict[str, Any]:
        key = day or date.today().isoformat()
        days = data.setdefault("days", {})
        current = days.setdefault(key, DEFAULT_DAY.copy())
        for item, value in DEFAULT_DAY.items():
            current.setdefault(item, value)
        current["last_update"] = datetime.now().isoformat(timespec="seconds")
        return current

    def _save(self, data: dict[str, Any]) -> bool:
        return write_json(self.score_path, data)

    def increment(self, metric: str, amount: int = 1) -> None:
        with self._lock:
            data = self._load()
            day = self._day(data)
            day[metric] = int(day.get(metric, 0)) + amount
            self._save(data)

    def add_seconds(self, metric: str, seconds: int) -> None:
        if seconds <= 0:
            return
        self.increment(metric, seconds)

    def set_status(self, status: str) -> None:
        with self._lock:
            data = self._load()
            day = self._day(data)
            day["last_status"] = status
            self._save(data)

    def set_presence(self, presence_status: str, sedentary_seconds: int) -> None:
        with self._lock:
            data = self._load()
            day = self._day(data)
            day["presence_status"] = presence_status
            day["sedentary_seconds"] = max(0, int(sedentary_seconds))
            self._save(data)

    def record_away_reason(self, reason: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        entry = {"time": now, "reason": reason}
        with self._lock:
            self.increment("away_count", 1)
            data = read_json(self.away_path, {"items": []})
            if not isinstance(data, dict):
                data = {"items": []}
            data.setdefault("items", []).append(entry)
            write_json(self.away_path, data)

    def today(self) -> TodayStats:
        with self._lock:
            data = self._load()
            key = date.today().isoformat()
            day = self._day(data, key)
            score = calculate_health_score(day)
            self._save(data)
            return TodayStats(
                date=key,
                water_count=int(day.get("water_count", 0)),
                stand_count=int(day.get("stand_count", 0)),
                away_count=int(day.get("away_count", 0)),
                sedentary_alerts=int(day.get("sedentary_alerts", 0)),
                sedentary_seconds=int(day.get("sedentary_seconds", 0)),
                computer_seconds=int(day.get("computer_seconds", 0)),
                run_seconds=int(day.get("run_seconds", 0)),
                health_score=score,
                presence_status=str(day.get("presence_status", "using")),
                last_status=str(day.get("last_status", "运行中")),
            )

    def history(self) -> dict[str, Any]:
        return self._load().get("days", {})


def calculate_health_score(day: dict[str, Any]) -> int:
    water = min(int(day.get("water_count", 0)), 8)
    stand = min(int(day.get("stand_count", 0)), 8)
    away = int(day.get("away_count", 0))
    sedentary = int(day.get("sedentary_alerts", 0))
    run_hours = int(day.get("run_seconds", 0)) / 3600

    score = 55
    score += round(water / 8 * 18)
    score += round(stand / 8 * 18)
    score += 6 if run_hours >= 4 else round(run_hours / 4 * 6)
    score -= min(sedentary * 3, 15)
    score -= min(max(away - 4, 0) * 2, 8)
    return max(0, min(100, int(score)))
