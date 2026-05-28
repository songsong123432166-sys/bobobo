"""Calendar data aggregation and chart rendering.

Collects daily stats from health_score.json and away_reason.json, and
provides helpers for drawing bar-chart / list views inside tkinter.
"""

import json
import calendar
from datetime import date, timedelta
from pathlib import Path

from .constants import AWAY_REASON_FILE, DATA_DIR, HEALTH_SCORE_FILE


# ── data loading ──────────────────────────────────────────────────────

def _load_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _all_log_files():
    """Yield (date_str, full_path) for every per-day log file, if any."""
    # Currently stats are single-file (latest day).  For future-proofing we
    # also scan for per-day files matching ``health_score_YYYY-MM-DD.json``.
    for p in DATA_DIR.glob("health_score_*.json"):
        d = p.stem.replace("health_score_", "")
        if len(d) == 10:
            yield d, p


def load_day_stats(target_date=None):
    """Return aggregated stats dict for *target_date* (default today)."""
    if target_date is None:
        target_date = date.today()
    ds = target_date.isoformat()

    hs = _load_json(HEALTH_SCORE_FILE)
    ar = _load_json(AWAY_REASON_FILE)

    # Only use data that matches the requested date
    if hs.get("date") != ds:
        hs = {}
    if ar.get("date") != ds:
        ar = {}

    return {
        "date": ds,
        "water_count": int(hs.get("water_count", 0)),
        "sit_count": int(hs.get("sit_count", 0)),
        "meeting_minutes": int(hs.get("meeting_minutes", 0)),
        "bathroom_count": int(ar.get("bathroom_count", 0)),
        "smoke_count": int(ar.get("smoke_count", 0)),
        "fieldwork_count": int(ar.get("fieldwork_count", 0)),
        "meeting_count": int(ar.get("meeting_count", 0)),
    }


def load_month_stats(year, month):
    """Return a dict mapping ``date_str -> day_stats`` for the given month.

    For now this only contains today's data (single-file storage).  The
    structure is ready for future per-day persistence.
    """
    days_in_month = calendar.monthrange(year, month)[1]
    result = {}
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        result[d.isoformat()] = load_day_stats(d)
    return result


# ── chart colours ─────────────────────────────────────────────────────

METRICS = [
    ("water_count",    "#3b82f6", "喝水"),
    ("bathroom_count", "#f59e0b", "上厕所"),
    ("meeting_count",  "#8b5cf6", "开会"),
    ("smoke_count",    "#ef4444", "抽根烟"),
    ("fieldwork_count","#10b981", "外勤"),
    ("sit_count",      "#06b6d4", "起身"),
]


# ── drawing helpers ───────────────────────────────────────────────────

def draw_bar_chart(canvas, day_stats_list, canvas_width, canvas_height,
                   selected_date=None):
    """Draw a grouped bar chart on *canvas*.

    *day_stats_list* is a list of ``(date_str, stats_dict)`` pairs
    (typically 7 days).  Each bar group has one bar per metric.
    """
    canvas.delete("all")
    if not day_stats_list:
        return

    n_groups = len(day_stats_list)
    active_metrics = [(k, c, l) for k, c, l in METRICS
                      if any(s.get(k, 0) > 0 for _, s in day_stats_list)]
    if not active_metrics:
        active_metrics = METRICS[:3]

    n_bars = len(active_metrics)
    margin_left = 40
    margin_right = 16
    margin_top = 20
    margin_bottom = 40
    chart_w = canvas_width - margin_left - margin_right
    chart_h = canvas_height - margin_top - margin_bottom

    group_w = chart_w / n_groups
    bar_w = max(6, min(18, (group_w * 0.7) / n_bars))
    gap = max(2, bar_w * 0.2)

    max_val = 1
    for _, stats in day_stats_list:
        for k, _, _ in active_metrics:
            max_val = max(max_val, stats.get(k, 0))
    max_val = max(max_val, 1)

    # grid lines
    for i in range(5):
        y = margin_top + chart_h * i / 4
        val = int(max_val * (4 - i) / 4)
        canvas.create_line(margin_left, y, canvas_width - margin_right, y,
                           fill="#e5e7eb", dash=(2, 4))
        canvas.create_text(margin_left - 4, y, text=str(val), anchor="e",
                           font=("Segoe UI", 8), fill="#9ca3af")

    for gi, (ds, stats) in enumerate(day_stats_list):
        cx = margin_left + group_w * gi + group_w / 2
        for bi, (key, color, _) in enumerate(active_metrics):
            val = stats.get(key, 0)
            bh = (val / max_val) * chart_h if max_val > 0 else 0
            x0 = cx - (n_bars * (bar_w + gap)) / 2 + bi * (bar_w + gap)
            y0 = margin_top + chart_h - bh
            x1 = x0 + bar_w
            y1 = margin_top + chart_h
            canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

        # date label
        label = ds[5:]  # MM-DD
        canvas.create_text(cx, canvas_height - 10, text=label,
                           font=("Segoe UI", 8), fill="#6b7280")


def draw_legend(canvas, x, y):
    """Draw a compact legend below the chart area."""
    for i, (key, color, label) in enumerate(METRICS):
        cx = x + i * 80
        canvas.create_rectangle(cx, y, cx + 12, y + 12, fill=color, outline="")
        canvas.create_text(cx + 16, y + 6, text=label, anchor="w",
                           font=("Segoe UI", 9), fill="#374151")
