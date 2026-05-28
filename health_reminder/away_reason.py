import json
from datetime import date, datetime

from .config_store import ensure_data_dir
from .constants import AWAY_REASON_FILE


AWAY_REASONS = {
    "bathroom": "上厕所",
    "meeting": "开会",
    "smoke": "抽根烟",
    "fieldwork": "外勤",
}


class AwayReasonTracker:
    """Track and persist away-reason events."""

    def __init__(self, log):
        self.log = log
        self.stats = self._load()
        self.ensure_today()

    def _today(self):
        return date.today().isoformat()

    def _default_stats(self):
        return {
            "date": self._today(),
            "bathroom_count": 0,
            "meeting_count": 0,
            "smoke_count": 0,
            "fieldwork_count": 0,
            "events": [],
        }

    def _load(self):
        ensure_data_dir()
        if AWAY_REASON_FILE.exists():
            try:
                return json.loads(AWAY_REASON_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return self._default_stats()

    def save(self):
        ensure_data_dir()
        try:
            AWAY_REASON_FILE.write_text(
                json.dumps(self.stats, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def ensure_today(self):
        if self.stats.get("date") != self._today():
            self.stats = self._default_stats()
            self.save()

    def record(self, reason_key):
        """Record an away reason event. Returns today's count for that reason."""
        self.ensure_today()
        count_key = f"{reason_key}_count"
        label = AWAY_REASONS.get(reason_key, reason_key)
        self.stats[count_key] = int(self.stats.get(count_key, 0)) + 1
        self.stats.setdefault("events", []).append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason_key,
        })
        self.save()
        count = self.stats[count_key]
        self.log.write(f"离席记录：{label}（今日第 {count} 次）")
        return count

    def get_today_counts(self):
        self.ensure_today()
        return {
            key: int(self.stats.get(f"{key}_count", 0))
            for key in AWAY_REASONS
        }

    def summary_text(self):
        self.ensure_today()
        counts = self.get_today_counts()
        parts = []
        for key, label in AWAY_REASONS.items():
            c = counts.get(key, 0)
            if c > 0:
                parts.append(f"{label} {c} 次")
        if not parts:
            return "今日暂无离席记录"
        return "今日离席：" + "，".join(parts)
