from .tk_helpers import center_geometry, slide_window_in, slide_window_out


def show_toast(manager, title, message):
    if not manager.available:
        return

    def _create(root):
        tk = manager.tk
        colors = manager.colors
        width, height = 360, 116
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=colors["card"])
        frame = tk.Frame(win, bg=colors["card"], bd=1, relief="solid")
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=title, font=("Microsoft YaHei UI", 12, "bold"), bg=colors["card"], fg=colors["txt"], anchor="w").pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(frame, text=message, font=("Microsoft YaHei UI", 10), bg=colors["card"], fg=colors["txt2"], anchor="w", justify="left", wraplength=318).pack(fill="x", padx=16)
        tk.Button(frame, text="×", command=lambda: slide_window_out(win, width), bg=colors["card"], fg=colors["txt2"], relief="flat", bd=0, font=("Microsoft YaHei UI", 12, "bold")).place(x=326, y=8, width=24, height=24)
        slide_window_in(win, width, height)
        win.after(5200, lambda: slide_window_out(win, width))

    manager.dispatch(_create)


def show_water_popup(manager, message):
    if not manager.available:
        return
    with manager.app.state_lock:
        if manager.water_popup_open:
            return
        manager.water_popup_open = True

    def _create(root):
        tk = manager.tk
        colors = manager.colors
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=colors["card"])
        win.geometry(center_geometry(win, 400, 200))
        frame = tk.Frame(win, bg=colors["card"], bd=1, relief="solid")
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="喝水提醒", font=("Microsoft YaHei UI", 14, "bold"), bg=colors["card"], fg=colors["txt"]).pack(pady=(16, 4))
        tk.Label(frame, text=message, font=("Microsoft YaHei UI", 10), bg=colors["card"], fg=colors["txt2"], wraplength=360, justify="center").pack(pady=(0, 12))
        buttons = tk.Frame(frame, bg=colors["card"])
        buttons.pack(pady=(0, 16))

        def close():
            manager.water_popup_open = False
            win.destroy()

        def drank():
            manager.app.reset_water_timer()
            close()

        def later():
            manager.app.snooze_water_timer()
            manager.app.notify("喝水提醒", f"好的，{manager.app.config['water_snooze_minutes']}分钟后提醒")
            close()

        tk.Button(buttons, text="我喝了", width=12, command=drank, bg=colors["accent"], fg="white", relief="flat").pack(side="left", padx=8)
        tk.Button(buttons, text=f"{manager.app.config['water_snooze_minutes']}分钟后提醒", width=14, command=later, bg="#e5e7eb", fg=colors["txt"], relief="flat").pack(side="left", padx=8)
        win.protocol("WM_DELETE_WINDOW", close)

    manager.dispatch(_create)


def show_away_reason_popup(manager):
    if not manager.available:
        return
    with manager.app.state_lock:
        if manager.away_popup_open:
            return
        manager.away_popup_open = True

    def _create(root):
        tk = manager.tk
        colors = manager.colors
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=colors["card"])
        win.geometry(center_geometry(win, 480, 260))
        frame = tk.Frame(win, bg=colors["card"], bd=2, relief="solid")
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="你离开了吗？请选择离席原因", font=("Microsoft YaHei UI", 14, "bold"), bg=colors["card"], fg=colors["txt"]).pack(pady=(20, 16))
        buttons = tk.Frame(frame, bg=colors["card"])
        buttons.pack(pady=(0, 20))

        def close():
            manager.away_popup_open = False
            if win.winfo_exists():
                win.destroy()

        def pick(key):
            manager.app.handle_away_reason(key)
            close()

        for key, label, color in [("bathroom", "🚿 上厕所", colors["accent"]), ("smoke", "🚬 抽根烟", colors["orange"]), ("fieldwork", "💼 外勤", colors["green"])]:
            tk.Button(buttons, text=label, width=10, height=2, font=("Microsoft YaHei UI", 11, "bold"), bg=color, fg="white", relief="flat", cursor="hand2", command=lambda k=key: pick(k)).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", close)
        win.focus_force()

    manager.dispatch(_create)
