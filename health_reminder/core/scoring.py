"""Prostatitis-oriented health scoring algorithm.

Five dimensions weighted for chronic prostatitis management:
  water(25%) + stand(25%) + toilet(20%) + sit_streak(20%) + smoke(10%) = 100
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScoreBreakdown:
    """评分细分结果，包含各维度得分、总分、等级和标签。"""
    total: int
    grade: str
    label: str
    water: int
    stand: int
    toilet: int
    sit_streak: int
    smoke: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "grade": self.grade,
            "label": self.label,
            "water": self.water,
            "stand": self.stand,
            "toilet": self.toilet,
            "sit_streak": self.sit_streak,
            "smoke": self.smoke,
        }

    def weakest_dimension(self) -> tuple[str, int]:
        items = [
            ("喝水", self.water),
            ("起身", self.stand),
            ("如厕", self.toilet),
            ("久坐", self.sit_streak),
            ("抽烟", self.smoke),
        ]
        return min(items, key=lambda item: item[1])

    def insight(self) -> str:
        name, _score = self.weakest_dimension()
        tips = {
            "喝水": "今天主要可以从补充喝水量开始改善。",
            "起身": "今天起身活动偏少，适合多离开座位走动。",
            "如厕": "今天如厕节奏不够理想，可以留意憋尿或过频情况。",
            "久坐": "今天连续久坐时间偏长，建议缩短单次坐着的时间。",
            "抽烟": "今天抽烟记录影响健康分，减少一次就会更友好。",
        }
        return tips.get(name, "保持现在的节奏，继续观察今日状态。")


# Weights (sum = 100)
W_WATER = 25
W_STAND = 25
W_TOILET = 20
W_SIT = 20
W_SMOKE = 10

# Grade thresholds
_GRADES = [
    (90, "A", "\u524d\u5217\u817a\u53cb\u597d\u65e5"),
    (75, "B", "\u4e0d\u9519\uff0c\u6709\u6539\u5584\u7a7a\u95f4"),
    (60, "C", "\u6ce8\u610f\uff01\u6709\u98ce\u9669\u884c\u4e3a"),
    (40, "D", "\u4eca\u5929\u4f24\u5bb3\u4e86\u4e0d\u5c11\uff0c\u660e\u5929\u8c03\u6574"),
    (0,  "E", "\u9ad8\u5371\u65e5\uff0c\u5efa\u8bae\u590d\u76d8\u5177\u4f53\u539f\u56e0"),
]


def _score_water(ml: int) -> float:
    if ml <= 0:
        return 0.0
    if ml <= 500:
        return 0.15
    if ml <= 1000:
        return 0.30
    if ml <= 1500:
        return 0.55
    if ml <= 2000:
        return 0.80
    if ml <= 2500:
        return 1.0
    if ml <= 3000:
        return 0.90
    return 0.75


def _score_stand(count: int) -> float:
    if count <= 0:
        return 0.0
    return min(1.0, count / 8.0)


def _score_toilet(count: int, max_gap_hours: float) -> float:
    if count <= 0:
        return 0.25
    if count <= 3:
        base = 0.30
    elif count <= 5:
        base = 0.60
    elif count <= 8:
        base = 1.0
    elif count <= 12:
        base = 0.80
    else:
        base = 0.55
    if max_gap_hours >= 4.0:
        base -= 0.40
    elif max_gap_hours >= 3.0:
        base -= 0.20
    return max(0.0, min(1.0, base))


def _score_sit_streak(max_minutes: int) -> float:
    if max_minutes <= 0:
        return 1.0
    if max_minutes <= 30:
        return 1.0
    if max_minutes <= 45:
        return 0.90
    if max_minutes <= 60:
        return 0.75
    if max_minutes <= 90:
        return 0.50
    if max_minutes <= 120:
        return 0.25
    return 0.0


def _score_smoke(count: int) -> float:
    if count <= 0:
        return 1.0
    if count <= 3:
        return 0.60
    if count <= 6:
        return 0.30
    if count <= 10:
        return 0.10
    return 0.0


def _grade(total: int) -> tuple[str, str]:
    for threshold, g, label in _GRADES:
        if total >= threshold:
            return g, label
    return "E", _GRADES[-1][2]


def calculate_score(day: dict[str, Any]) -> ScoreBreakdown:
    water_ml = int(day.get("water_ml", 0))
    stand_count = int(day.get("stand_count", 0))
    toilet_count = int(day.get("toilet_count", 0))
    max_gap = float(day.get("toilet_max_gap_hours", 0.0))
    sit_minutes = int(day.get("max_sit_streak_minutes", 0))
    smoke_count = int(day.get("smoke_count", 0))

    s_water = round(_score_water(water_ml) * W_WATER)
    s_stand = round(_score_stand(stand_count) * W_STAND)
    s_toilet = round(_score_toilet(toilet_count, max_gap) * W_TOILET)
    s_sit = round(_score_sit_streak(sit_minutes) * W_SIT)
    s_smoke = round(_score_smoke(smoke_count) * W_SMOKE)

    total = max(0, min(100, s_water + s_stand + s_toilet + s_sit + s_smoke))
    grade, label = _grade(total)

    return ScoreBreakdown(
        total=total, grade=grade, label=label,
        water=s_water, stand=s_stand, toilet=s_toilet,
        sit_streak=s_sit, smoke=s_smoke,
    )
