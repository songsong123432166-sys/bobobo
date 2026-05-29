from datetime import date
import calendar

from ..calendar_data import METRICS, load_month_stats


def build_calendar(manager, parent):
    tk = manager.tk
    colors = manager.colors
    panel = tk.Frame(parent, bg=colors["bg"])
    manager._panels["calendar"] = panel
    header = tk.Frame(panel, bg=colors["bg"])
    header.pack(fill="x", padx=28, pady=(24, 8))
    tk.Label(header, text="记录日历", font=("Microsoft YaHei UI", 22, "bold"), bg=colors["bg"], fg=colors["txt"]).pack(side="left")
    manager._month_label = tk.Label(header, text="", font=("Microsoft YaHei UI", 14, "bold"), bg=colors["bg"], fg=colors["txt"])
    manager._month_label.pack(side="right")
    manager._cal_grid = tk.Frame(panel, bg=colors["bg"])
    manager._cal_grid.pack(fill="x", padx=28, pady=(8, 8))
    manager._cal_content = tk.Frame(panel, bg=colors["card"], highlightbackground=colors["border"], highlightthickness=1)
    manager._cal_content.pack(fill="both", expand=True, padx=28, pady=(0, 28))


def refresh_calendar(manager):
    tk = manager.tk
    colors = manager.colors
    year, month = manager._cal_year, manager._cal_month
    manager._month_label.configure(text=f"{year}年{month}月")
    for widget in manager._cal_grid.winfo_children():
        widget.destroy()
    for index, label in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
        tk.Label(manager._cal_grid, text=label, width=6, bg=colors["bg"], fg=colors["txt2"]).grid(row=0, column=index)
    data = load_month_stats(year, month)
    first_weekday, days_in_month = calendar.monthrange(year, month)
    today = date.today().isoformat()
    for day in range(1, days_in_month + 1):
        row, col = divmod(first_weekday + day - 1, 7)
        day_key = f"{year}-{month:02d}-{day:02d}"
        total = sum(data.get(day_key, {}).get(key, 0) for key, _, _ in METRICS)
        is_today = day_key == today
        bg = colors["accent"] if is_today else (colors["card"] if total else colors["bg"])
        fg = "white" if is_today else colors["txt"]
        tk.Label(manager._cal_grid, text=str(day), width=6, bg=bg, fg=fg).grid(row=row + 1, column=col, padx=1, pady=1)
    render_month_summary(manager, data)


def render_month_summary(manager, data):
    tk = manager.tk
    colors = manager.colors
    for widget in manager._cal_content.winfo_children():
        widget.destroy()
    totals = {key: 0 for key, _, _ in METRICS}
    for stats in data.values():
        for key in totals:
            totals[key] += int(stats.get(key, 0))
    tk.Label(manager._cal_content, text="本月汇总", font=("Microsoft YaHei UI", 13, "bold"), bg=colors["card"], fg=colors["txt"]).pack(anchor="w", padx=16, pady=(14, 8))
    for key, label, _ in METRICS:
        tk.Label(manager._cal_content, text=f"{label}: {totals.get(key, 0)}", font=("Microsoft YaHei UI", 11), bg=colors["card"], fg=colors["txt2"]).pack(anchor="w", padx=16, pady=3)
