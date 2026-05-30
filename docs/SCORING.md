# Prostatitis Health Scoring System

Technical documentation for the five-dimension health scoring algorithm designed for office workers with chronic prostatitis.

## Design Rationale

Chronic prostatitis symptoms are strongly influenced by three factors:

1. **Pelvic congestion** — prolonged sitting increases perineal pressure
2. **Urinary stasis** — holding urine causes retrograde flow into prostate ducts
3. **Poor local circulation** — nicotine and immobility reduce blood flow to the prostate

All scoring dimensions target one or more of these mechanisms.

## Scoring Architecture

**Total: 100 points** = weighted sum of five independent dimensions.

| Dimension | Weight | Target | Prostatitis Mechanism |
|-----------|--------|--------|----------------------|
| Water intake | 25 | 2000–2500 ml/day | Flushes urethra, reduces bacterial concentration |
| Standing breaks | 25 | 8+ times/day | Relieves pelvic pressure, restores circulation |
| Toilet frequency | 20 | 6–8 times/day, no 3h+ gaps | Prevents urine reflux into prostate |
| Continuous sitting | 20 | Longest streak ≤ 60 min | Limits perineal compression |
| Smoking | 10 | 0 cigarettes | Nicotine constricts prostate blood vessels |

## Dimension Scoring Functions

### 1. Water Intake (25 pts)

Optimal range: **2000–2500 ml**, distributed throughout the day.

| Intake (ml) | Raw Score | Points |
|-------------|-----------|--------|
| 0 | 0.00 | 0 |
| ≤ 500 | 0.15 | 4 |
| ≤ 1000 | 0.30 | 8 |
| ≤ 1500 | 0.55 | 14 |
| ≤ 2000 | 0.80 | 20 |
| **≤ 2500** | **1.00** | **25** |
| ≤ 3000 | 0.90 | 23 |
| > 3000 | 0.75 | 19 |

Over-drinking (>3000 ml) is slightly penalized — excessive intake increases kidney burden and nocturia.

### 2. Standing Breaks (25 pts)

Target: at least **8 breaks per workday** (every ~45 min in an 8-hour day).

Formula: min(1.0, count / 8) × 25

| Breaks | Points |
|--------|--------|
| 0 | 0 |
| 2 | 6 |
| 4 | 12 |
| 6 | 19 |
| 8+ | 25 |

### 3. Toilet Frequency (20 pts)

Ideal: **6–8 times/day**. Holding urine for 3+ hours is a high-risk behavior for prostatitis.

| Frequency | Base Score |
|-----------|------------|
| 0 | 0.25 |
| 1–3 | 0.30 |
| 4–5 | 0.60 |
| **6–8** | **1.00** |
| 9–12 | 0.80 |
| > 12 | 0.55 |

**Holding penalty** (applied to base score):

| Max gap between visits | Penalty |
|------------------------|---------|
| < 3 hours | None |
| 3–4 hours | −0.20 |
| ≥ 4 hours | −0.40 |

The penalty is subtracted from the base score, floored at 0.

### 4. Continuous Sitting Streak (20 pts)

Evaluates the **longest single continuous sitting period** in the day.

| Longest streak | Points |
|----------------|--------|
| ≤ 30 min | 20 |
| ≤ 45 min | 18 |
| ≤ 60 min | 15 |
| ≤ 90 min | 10 |
| ≤ 120 min | 5 |
| > 120 min | 0 |

This dimension complements "standing breaks" — you could stand 8 times but still have a 2-hour streak if breaks are clustered.

### 5. Smoking (10 pts)

No safe threshold for prostatitis patients. Nicotine causes vasoconstriction in prostate tissue.

| Cigarettes | Points |
|------------|--------|
| 0 | 10 |
| 1–3 | 6 |
| 4–6 | 3 |
| 7–10 | 1 |
| > 10 | 0 |

## Grade System

| Score | Grade | Label |
|-------|-------|-------|
| 90–100 | A | Prostate-friendly day |
| 75–89 | B | Good, room to improve |
| 60–74 | C | Warning: risky behaviors |
| 40–59 | D | Significant harm today |
| < 40 | E | High-risk day, review causes |

## Data Model

Per-day record stored in health_score.json:

`json
{
  "days": {
    "2026-05-29": {
      "water_ml": 2100,
      "water_count": 7,
      "stand_count": 6,
      "toilet_count": 7,
      "toilet_times": ["2026-05-29T09:15", "2026-05-29T11:30", "..."],
      "toilet_max_gap_hours": 2.5,
      "max_sit_streak_minutes": 52,
      "smoke_count": 0,
      "sedentary_alerts": 2,
      "away_count": 3,
      "last_update": "2026-05-29T17:30:00"
    }
  }
}
`

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| water_ml | int | Total water intake in milliliters |
| water_count | int | Number of water intake records |
| stand_count | int | Confirmed standing breaks |
| 	oilet_count | int | Toilet visits (manual or auto from away reasons) |
| 	oilet_times | list[str] | ISO timestamps of each visit (for gap calculation) |
| 	oilet_max_gap_hours | float | Longest gap between consecutive visits |
| max_sit_streak_minutes | int | Longest continuous sitting period |
| smoke_count | int | Cigarettes smoked |
| sedentary_alerts | int | Sedentary reminders fired |
| way_count | int | Away-from-desk events |

## Water Intake Flow

`
Timer fires → "呱" sound plays → Slide-in popup appears
                                 ├─ Preset buttons (200/250/300/500 ml)
                                 ├─ Manual input field
                                 ├─ [记录饮水] → records ml → closes
                                 └─ [稍后提醒] → snoozes → closes
                                 Auto-dismiss after 10 minutes
`

## Away Reason → Scoring Mapping

When the user returns from being away, they select a reason:

| Away Reason | Mapped To |
|-------------|-----------|
| 上厕所 | 	oilet_count += 1 |
| 抽根烟 | smoke_count += 1 |
| 开会 | (away_count only) |
| 外勤 | (away_count only) |

## Implementation Files

| File | Purpose |
|------|---------|
| core/scoring.py | Pure scoring algorithm, no I/O |
| core/health_state.py | Data model, persistence, field updates |
| ui/water_input.py | Water intake popup with 10-min auto-dismiss |
| platform/sound.py | Sound playback (frog ribbit WAV) |
| ui/popup.py | Popup orchestration, sound triggers |
| pp.py | Wiring: popup callbacks → state updates |
| ssets/ribbit.wav | Frog croak sound effect |

## Extending the System

- **Add a dimension**: Define _score_<name>() in scoring.py, add weight constant, wire into calculate_score().
- **Adjust weights**: Modify W_* constants in scoring.py. Must sum to 100.
- **Change thresholds**: Modify the lookup tables in each _score_* function.
- **Auto water detection**: Replace WaterInputDialog with smart cup API integration.
- **Trend alerts**: Compare 7-day rolling averages against thresholds in main_window.py.