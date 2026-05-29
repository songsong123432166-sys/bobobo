from ..config_store import parse_clock, safe_int
from ..constants import CONFIG_FILE, DEFAULT_CONFIG, LOG_FILE


def build_settings(manager, parent):
    tk = manager.tk
    ttk = manager.ttk
    colors = manager.colors
    panel = tk.Frame(parent, bg=colors["bg"])
    manager._panels["settings"] = panel
    canvas = tk.Canvas(panel, bg=colors["bg"], highlightthickness=0)
    vsb = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=colors["bg"])
    canvas.create_window((4, 4), window=inner, anchor="nw", tags="inner")
    inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure("inner", width=event.width - 8))
    tk.Label(inner, text="设置", font=("Microsoft YaHei UI", 22, "bold"), bg=colors["bg"], fg=colors["txt"]).pack(anchor="w", padx=28, pady=(24, 16))

    manager._toggle_vars = {}
    add_toggle_group(manager, inner)
    add_time_group(manager, inner)
    add_activity_group(manager, inner)
    add_action_buttons(manager, inner)
    tk.Label(inner, text=f"配置：{CONFIG_FILE}\n日志：{LOG_FILE}", font=("Microsoft YaHei UI", 9), bg=colors["bg"], fg=colors["txt2"]).pack(anchor="w", padx=28, pady=(8, 12))


def card_frame(manager, parent, title):
    tk = manager.tk
    colors = manager.colors
    frame = tk.LabelFrame(parent, text=title, font=("Microsoft YaHei UI", 12, "bold"), bg=colors["card"], fg=colors["txt"], labelanchor="nw", padx=16, pady=12)
    frame.pack(fill="x", padx=28, pady=(0, 12))
    frame.columnconfigure(1, weight=1)
    return frame


def add_toggle_group(manager, parent):
    tk = manager.tk
    colors = manager.colors
    frame = card_frame(manager, parent, "开关选项")
    for row, (key, label) in enumerate([("startup_enabled", "开机自启"), ("quiet_enabled", "勿扰模式"), ("center_popup_enabled", "中央弹窗")]):
        var = tk.BooleanVar(value=bool(manager.app.config.get(key, True)))
        manager._toggle_vars[key] = var
        tk.Checkbutton(frame, text=label, variable=var, font=("Microsoft YaHei UI", 11), bg=colors["card"], fg=colors["txt"], selectcolor=colors["card"], activebackground=colors["card"], anchor="w").grid(row=row // 2, column=row % 2, sticky="w", padx=12, pady=6)


def add_time_group(manager, parent):
    tk = manager.tk
    colors = manager.colors
    frame = card_frame(manager, parent, "时间设置")
    manager._time_vars = {}
    fields = [
        ("work_start", "上班时间 HH:MM", manager.app.config.get("work_start", DEFAULT_CONFIG["work_start"])),
        ("work_end", "下班时间 HH:MM", manager.app.config.get("work_end", DEFAULT_CONFIG["work_end"])),
        ("sit_interval", "久坐间隔（分钟）", manager.app.config.get("sit_interval_minutes", 45)),
        ("water_interval", "喝水间隔（分钟）", manager.app.config.get("water_interval_minutes", 60)),
        ("snooze_interval", "稍后提醒（分钟）", manager.app.config.get("water_snooze_minutes", 10)),
    ]
    for row, (key, label, value) in enumerate(fields):
        tk.Label(frame, text=label, font=("Microsoft YaHei UI", 10), bg=colors["card"], fg=colors["txt"]).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        var = tk.StringVar(value=str(value))
        manager._time_vars[key] = var
        tk.Entry(frame, textvariable=var, width=12, font=("Microsoft YaHei UI", 10), relief="solid", bd=1).grid(row=row, column=1, sticky="ew", padx=(10, 12), pady=6)


def add_activity_group(manager, parent):
    tk = manager.tk
    colors = manager.colors
    frame = card_frame(manager, parent, "状态检测")
    manager._act_vars = {}
    fields = [("away_after", "可能离开判定（分钟）", "away_after_minutes", 10), ("idle_after", "离开判定（分钟）", "idle_after_minutes", 15)]
    for row, (key, label, config_key, default) in enumerate(fields):
        tk.Label(frame, text=label, font=("Microsoft YaHei UI", 10), bg=colors["card"], fg=colors["txt"]).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        var = tk.StringVar(value=str(manager.app.config.get(config_key, default)))
        manager._act_vars[key] = var
        tk.Entry(frame, textvariable=var, width=12, font=("Microsoft YaHei UI", 10), relief="solid", bd=1).grid(row=row, column=1, sticky="ew", padx=(10, 12), pady=6)


def add_action_buttons(manager, parent):
    tk = manager.tk
    colors = manager.colors
    frame = tk.Frame(parent, bg=colors["bg"])
    frame.pack(fill="x", padx=28, pady=(4, 8))
    tk.Button(frame, text="保存设置", font=("Microsoft YaHei UI", 11, "bold"), bg=colors["accent"], fg="white", relief="flat", padx=24, pady=8, command=lambda: save_settings(manager)).pack(side="left")
    tk.Button(frame, text="我站起来了", font=("Microsoft YaHei UI", 10), bg="#e5e7eb", fg=colors["txt"], relief="flat", padx=16, pady=8, command=manager.app.reset_sit_timer).pack(side="left", padx=(12, 0))
    tk.Button(frame, text="喝水了", font=("Microsoft YaHei UI", 10), bg="#e5e7eb", fg=colors["txt"], relief="flat", padx=16, pady=8, command=manager.app.reset_water_timer).pack(side="left", padx=(12, 0))


def save_settings(manager):
    start = parse_clock(manager._time_vars["work_start"].get().strip(), DEFAULT_CONFIG["work_start"]).strftime("%H:%M")
    end = parse_clock(manager._time_vars["work_end"].get().strip(), DEFAULT_CONFIG["work_end"]).strftime("%H:%M")
    manager.app.apply_settings({
        "work_start": start,
        "work_end": end,
        "sit_interval_minutes": safe_int(manager._time_vars["sit_interval"].get(), 45, 1, 480),
        "water_interval_minutes": safe_int(manager._time_vars["water_interval"].get(), 60, 1, 480),
        "water_snooze_minutes": safe_int(manager._time_vars["snooze_interval"].get(), 10, 1, 120),
        "away_after_minutes": safe_int(manager._act_vars["away_after"].get(), 10, 1, 120),
        "idle_after_minutes": safe_int(manager._act_vars["idle_after"].get(), 15, 1, 240),
        "startup_enabled": bool(manager._toggle_vars["startup_enabled"].get()),
        "quiet_enabled": bool(manager._toggle_vars["quiet_enabled"].get()),
        "center_popup_enabled": bool(manager._toggle_vars["center_popup_enabled"].get()),
    })
