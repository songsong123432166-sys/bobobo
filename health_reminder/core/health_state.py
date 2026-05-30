"""Health state tracking with prostatitis-oriented scoring."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .scoring import ScoreBreakdown, calculate_score
from .storage import read_json, write_json


DEFAULT_DAY: dict[str, Any] = {
    # Legacy fields (kept for backward compat)
    "water_count": 0,
    "stand_count": 0,
    "away_count": 0,
    "sedentary_alerts": 0,
    "sedentary_seconds": 0,
    "computer_seconds": 0,
    "run_seconds": 0,
    "presence_status": "using",
    "last_status": "\u8fd0\u884c\u4e2d",
    "last_update": "",
    # New scoring fields
    "water_ml": 0,
    "toilet_count": 0,
    "smoke_count": 0,
    "max_sit_streak_minutes": 0,
    "toilet_max_gap_hours": 0.0,
    "toilet_times": [],
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
    # New scoring fields
    water_ml: int
    toilet_count: int
    smoke_count: int
    max_sit_streak_minutes: int
    toilet_max_gap_hours: float
    score_breakdown: ScoreBreakdown | None = None


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
            # Update max sit streak
            streak_min = sedentary_seconds // 60
            if streak_min > int(day.get("max_sit_streak_minutes", 0)):
                day["max_sit_streak_minutes"] = streak_min
            self._save(data)

    def record_water_ml(self, ml: int) -> None:
        with self._lock:
            data = self._load()
            day = self._day(data)
            day["water_ml"] = int(day.get("water_ml", 0)) + max(0, ml)
            day["water_count"] = int(day.get("water_count", 0)) + 1
            self._save(data)

    def record_toilet(self) -> None:
        now = datetime.now()
        with self._lock:
            data = self._load()
            day = self._day(data)
            day["toilet_count"] = int(day.get("toilet_count", 0)) + 1
            times: list[str] = day.get("toilet_times", [])
            times.append(now.isoformat(timespec="minutes"))
            day["toilet_times"] = times
            # Calculate max gap
            if len(times) >= 2:
                parsed = [datetime.fromisoformat(t) for t in times]
                gaps = [(parsed[i+1] - parsed[i]).total_seconds() / 3600 for i in range(len(parsed) - 1)]
                day["toilet_max_gap_hours"] = round(max(gaps), 2)
            self._save(data)

    def record_smoke(self, count: int = 1) -> None:
        with self._lock:
            data = self._load()
            day = self._day(data)
            day["smoke_count"] = int(day.get("smoke_count", 0)) + max(0, count)
            self._save(data)

    def record_away_reason(self, reason: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        entry = {"time": now, "reason": reason}
        with self._lock:
            self.increment("away_count", 1)
            # Auto-map away reasons to scoring
            if "\u4e0a\u5395\u6240" in reason:  # contains toilet
                data = self._load()
                day = self._day(data)
                day["toilet_count"] = int(day.get("toilet_count", 0)) + 1
                self._save(data)
            elif "\u62bd\u70df" in reason or "\u62bd\u6839" in reason:  # contains smoke
                data = self._load()
                day = self._day(data)
                day["smoke_count"] = int(day.get("smoke_count", 0)) + 1
                self._save(data)
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
            legacy_score = _calculate_legacy_score(day)
            breakdown = calculate_score(day)
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
                health_score=breakdown.total,
                presence_status=str(day.get("presence_status", "using")),
                last_status=str(day.get("last_status", "\u8fd0\u884c\u4e2d")),
                water_ml=int(day.get("water_ml", 0)),
                toilet_count=int(day.get("toilet_count", 0)),
                smoke_count=int(day.get("smoke_count", 0)),
                max_sit_streak_minutes=int(day.get("max_sit_streak_minutes", 0)),
                toilet_max_gap_hours=float(day.get("toilet_max_gap_hours", 0.0)),
                score_breakdown=breakdown,
            )

    def history(self) -> dict[str, Any]:
        return self._load().get("days", {})


def _calculate_legacy_score(day: dict[str, Any]) -> int:
    """Legacy score calculation, kept for backward compatibility."""
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