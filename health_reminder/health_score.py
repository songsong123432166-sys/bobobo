import json
from datetime import date

from .config_store import ensure_data_dir
from .constants import HEALTH_SCORE_FILE


class HealthScore:
    def __init__(self, log):
        self.log = log
        self.stats = self._load()
        self.ensure_today()

    def _today(self):
        return date.today().isoformat()

    def _default_stats(self):
        return {
            "date": self._today(),
            "water_count": 0,
            "sit_count": 0,
        }

    def _load(self):
        ensure_data_dir()
        if HEALTH_SCORE_FILE.exists():
            try:
                return json.loads(HEALTH_SCORE_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return self._default_stats()

    def save(self):
        ensure_data_dir()
        try:
            HEALTH_SCORE_FILE.write_text(
                json.dumps(self.stats, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def ensure_today(self):
        if self.stats.get("date") != self._today():
            self.stats = self._default_stats()
            self.save()

    def record_water(self):
        self.ensure_today()
        self.stats["water_count"] = int(self.stats.get("water_count", 0)) + 1
        self.save()
        score = self.calculate()["total"]
        self.log.write(f"喝水完成，今日喝水 {self.stats['water_count']} 次，健康分 {score}")
        return score

    def record_sit_break(self):
        self.ensure_today()
        self.stats["sit_count"] = int(self.stats.get("sit_count", 0)) + 1
        self.save()
        score = self.calculate()["total"]
        self.log.write(f"起身完成，今日起身 {self.stats['sit_count']} 次，健康分 {score}")
        return score
    def calculate(self, current_sit_minutes=0, runtime_minutes=0):
        self.ensure_today()
        water_count = int(self.stats.get("water_count", 0))
        sit_count = int(self.stats.get("sit_count", 0))

        water_score = min(30, water_count * 4)
        sit_score = min(30, sit_count * 5)

        if current_sit_minutes <= 60:
            rhythm_score = 20
        elif current_sit_minutes <= 90:
            rhythm_score = 14
        elif current_sit_minutes <= 120:
            rhythm_score = 8
        else:
            rhythm_score = 0

        runtime_score = min(10, int(runtime_minutes / 24))
        total = water_score + sit_score + rhythm_score + runtime_score 
        return {
            "total": min(100, total),
            "water_count": water_count,
            "sit_count": sit_count,
            "water_score": water_score,
            "sit_score": sit_score,
            "rhythm_score": rhythm_score,
            "runtime_score": runtime_score,
        }

    def summary_text(self, current_sit_minutes=0, runtime_minutes=0):
        score = self.calculate(current_sit_minutes, runtime_minutes)
        total = score["total"]
        if total >= 90:
            comment = "状态很好，今天挺会照顾自己"
        elif total >= 75:
            comment = "不错，继续保持这个节奏"
        elif total >= 60:
            comment = "还行，再补点水活动一下"
        else:
            comment = "今天需要稍微拉一把"

        return (
            f"今日健康分：{total} / 100\n"
            f"{comment}\n"
            f"喝水：{score['water_count']} 次  起身：{score['sit_count']} 次\n"
            f"连续久坐：约 {int(current_sit_minutes)} 分钟  "
        )

