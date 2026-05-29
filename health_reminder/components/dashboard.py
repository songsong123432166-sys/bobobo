from datetime import date

from ..config.ui_config import STAT_CARDS


def build_dashboard(manager, parent):
    tk = manager.tk
    ttk = manager.ttk
    colors = manager.colors
    panel = tk.Frame(parent, bg=colors["bg"])
    manager._panels["dashboard"] = panel

    canvas = tk.Canvas(panel, bg=colors["bg"], highlightthickness=0)
    vsb = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=colors["bg"])
    canvas.create_window((4, 4), window=inner, anchor="nw", tags="inner")
    inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure("inner", width=event.width - 8))

    header = tk.Frame(inner, bg=colors["bg"])
    header.pack(fill="x", padx=28, pady=(24, 4))
    tk.Label(header, text="可视化数据", font=("Microsoft YaHei UI", 22, "bold"), bg=colors["bg"], fg=colors["txt"]).pack(side="left")
    tk.Label(header, text=date.today().strftime("%Y年%m月%d日"), font=("Microsoft YaHei UI", 12), bg=colors["bg"], fg=colors["txt2"]).pack(side="right")

    score_card = tk.Frame(inner, bg=colors["card"], highlightbackground=colors["border"], highlightthickness=1)
    score_card.pack(fill="x", padx=28, pady=(16, 8))
    manager._score_canvas = tk.Canvas(score_card, width=140, height=140, bg=colors["card"], highlightthickness=0)
    manager._score_canvas.pack(side="left", padx=(24, 16), pady=20)
    score_text = tk.Frame(score_card, bg=colors["card"])
    score_text.pack(side="left", fill="x", expand=True, pady=20)
    tk.Label(score_text, text="今日健康分", font=("Microsoft YaHei UI", 14, "bold"), bg=colors["card"], fg=colors["txt"]).pack(anchor="w")
    manager._score_detail = tk.Label(score_text, text="", font=("Microsoft YaHei UI", 11), bg=colors["card"], fg=colors["txt2"], justify="left", anchor="w")
    manager._score_detail.pack(anchor="w", pady=(6, 0))

    cards = tk.Frame(inner, bg=colors["bg"])
    cards.pack(fill="x", padx=28, pady=(8, 8))
    for index, (key, label, color_key, icon) in enumerate(STAT_CARDS):
        row, col = divmod(index, 3)
        card = tk.Frame(cards, bg=colors["card"], highlightbackground=colors["border"], highlightthickness=1)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        cards.columnconfigure(col, weight=1)
        tk.Label(card, text=f"{icon} {label}", font=("Microsoft YaHei UI", 11), bg=colors["card"], fg=colors["txt2"]).pack(anchor="w", padx=14, pady=(14, 0))
        value = tk.Label(card, text="0", font=("Microsoft YaHei UI", 28, "bold"), bg=colors["card"], fg=colors["txt"])
        value.pack(anchor="w", padx=14, pady=(0, 14))
        manager._stat_values[key] = value

    info = tk.Frame(inner, bg=colors["card"], highlightbackground=colors["border"], highlightthickness=1)
    info.pack(fill="x", padx=28, pady=(8, 4))
    for row, label in enumerate(["状态", "摄像头", "离席记录"]):
        tk.Label(info, text=label, font=("Microsoft YaHei UI", 10), bg=colors["card"], fg=colors["txt2"]).grid(row=row, column=0, sticky="w", padx=16, pady=6)
        value = tk.Label(info, text="—", font=("Microsoft YaHei UI", 10, "bold"), bg=colors["card"], fg=colors["txt"])
        value.grid(row=row, column=1, sticky="w", padx=8, pady=6)
        info.columnconfigure(1, weight=1)
        manager._status_labels[label] = value


def refresh_dashboard(manager):
    if not manager._stat_values:
        return
    health = manager.app.health_score.stats
    away = manager.app.away_reason.stats
    live = {
        "water_count": int(health.get("water_count", 0)),
        "sit_count": int(health.get("sit_count", 0)),
        "bathroom_count": int(away.get("bathroom_count", 0)),
        "smoke_count": int(away.get("smoke_count", 0)),
        "fieldwork_count": int(away.get("fieldwork_count", 0)),
    }
    for key, label in manager._stat_values.items():
        label.configure(text=str(live.get(key, 0)))
    draw_score(manager)
    work = "工作时间" if manager.app.is_work_time() else "非工作时间"
    manager._status_labels["状态"].configure(text=f"正常提醒 / {work} / {manager.app.activity.label()}")
    manager._status_labels["摄像头"].configure(text=manager.app.camera_presence.last_result)
    manager._status_labels["离席记录"].configure(text=manager.app.away_reason.summary_text())


def draw_score(manager):
    colors = manager.colors
    canvas = manager._score_canvas
    canvas.delete("all")
    data = manager.app.health_score.calculate(manager.app.get_current_sit_minutes(), manager.app.get_runtime_minutes())
    total = data["total"]
    canvas.create_oval(10, 10, 130, 130, fill="#f0f0f5", outline="")
    canvas.create_arc(10, 10, 130, 130, start=90, extent=-max(1, int(360 * total / 100)), style="arc", outline=colors["accent"], width=10)
    canvas.create_text(70, 70, text=str(total), font=("Microsoft YaHei UI", 32, "bold"), fill=colors["txt"])
    manager._score_detail.configure(text=f"喝水 {data['water_count']} 次  起身 {data['sit_count']} 次\n久坐 {int(manager.app.get_current_sit_minutes())} 分钟")
