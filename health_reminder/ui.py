import queue
import threading

from .constants import APP_TITLE, CONFIG_FILE, DEFAULT_CONFIG, LOG_FILE
from .config_store import parse_clock, safe_int
from .windows_integration import configure_tcl_tk_for_frozen_app


configure_tcl_tk_for_frozen_app()

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None


class UiManager:
    def __init__(self, app):
        self.app = app
        self.root = None
        self.main_window = None
        self.water_popup_open = False
        self.toast_windows = []
        self.tasks = queue.Queue()

    @property
    def available(self):
        return tk is not None

    def start(self):
        if not self.available:
            self.app.log.write("未检测到 tkinter，主界面不可用")
            return

        def ui_loop():
            root = tk.Tk()
            root.withdraw()
            self.root = root
            self._poll_tasks()
            root.mainloop()

        threading.Thread(target=ui_loop, daemon=True).start()

    def dispatch(self, task):
        if not self.available:
            self.app.notify("界面", "当前 Python 环境不支持 tkinter，无法打开界面")
            return
        self.tasks.put(task)

    def _poll_tasks(self):
        while True:
            try:
                task = self.tasks.get_nowait()
            except queue.Empty:
                break
            try:
                task(self.root)
            except Exception as exc:
                self.app.log.write(f"界面任务失败：{exc}")
        self.root.after(100, self._poll_tasks)

    def _slide_window_in(self, window, width, height, y_offset=70):
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        target_x = screen_width - width - 24
        y = screen_height - height - y_offset
        start_x = screen_width + 12
        window.geometry(f"{width}x{height}+{start_x}+{y}")

        def step(x):
            if not window.winfo_exists():
                return
            if x <= target_x:
                window.geometry(f"{width}x{height}+{target_x}+{y}")
                return
            window.geometry(f"{width}x{height}+{x}+{y}")
            window.after(12, lambda: step(max(target_x, x - 28)))

        step(start_x)

    def _slide_window_out(self, window, width):
        if not window.winfo_exists():
            return
        x = window.winfo_x()
        y = window.winfo_y()
        screen_width = window.winfo_screenwidth()

        def step(current_x):
            if not window.winfo_exists():
                return
            if current_x >= screen_width + 12:
                window.destroy()
                return
            window.geometry(f"+{current_x}+{y}")
            window.after(12, lambda: step(current_x + 30))

        step(x)

    def show_toast(self, title, message):
        if not self.available:
            return

        def create_toast(root):
            width = 360
            height = 116
            window = tk.Toplevel(root)
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.configure(bg="#eef6ff")

            frame = tk.Frame(window, bg="#eef6ff", bd=1, relief="solid")
            frame.pack(fill="both", expand=True)

            tk.Label(
                frame,
                text=title,
                font=("Microsoft YaHei UI", 12, "bold"),
                bg="#eef6ff",
                fg="#0f172a",
                anchor="w",
            ).pack(fill="x", padx=16, pady=(14, 4))

            tk.Label(
                frame,
                text=message,
                font=("Microsoft YaHei UI", 10),
                bg="#eef6ff",
                fg="#334155",
                anchor="w",
                justify="left",
                wraplength=318,
            ).pack(fill="x", padx=16)

            close_button = tk.Button(
                frame,
                text="×",
                command=lambda: self._slide_window_out(window, width),
                bg="#eef6ff",
                fg="#475569",
                activebackground="#dbeafe",
                relief="flat",
                bd=0,
                font=("Microsoft YaHei UI", 12, "bold"),
            )
            close_button.place(x=326, y=8, width=24, height=24)

            self._slide_window_in(window, width, height)
            window.after(5200, lambda: self._slide_window_out(window, width))

        self.dispatch(create_toast)

    def show_water_popup(self, message):
        if not self.available:
            return

        with self.app.state_lock:
            if self.water_popup_open:
                return
            self.water_popup_open = True

        def create_popup(root):
            window = tk.Toplevel(root)
            window.title("喝水提醒")
            window.resizable(False, False)
            window.attributes("-topmost", True)

            width = 340
            height = 168
            window.configure(bg="#f7fbff")

            tk.Label(
                window,
                text="该补充水分了",
                font=("Microsoft YaHei UI", 14, "bold"),
                bg="#f7fbff",
                fg="#1d4ed8",
            ).pack(pady=(18, 6))

            tk.Label(
                window,
                text=message,
                font=("Microsoft YaHei UI", 10),
                bg="#f7fbff",
                fg="#1f2937",
                wraplength=292,
                justify="center",
            ).pack(pady=(0, 14))

            button_frame = tk.Frame(window, bg="#f7fbff")
            button_frame.pack()

            def close_popup():
                with self.app.state_lock:
                    self.water_popup_open = False
                self._slide_window_out(window, width)

            def drank_water():
                self.app.reset_water_timer()
                close_popup()

            def remind_later():
                self.app.snooze_water_timer()
                self.app.notify(
                    "喝水提醒",
                    f"好的，{self.app.config['water_snooze_minutes']}分钟后再提醒",
                )
                close_popup()

            tk.Button(
                button_frame,
                text="我喝了",
                width=12,
                command=drank_water,
                bg="#2563eb",
                fg="white",
                activebackground="#1d4ed8",
                activeforeground="white",
                relief="flat",
            ).pack(side="left", padx=8)

            tk.Button(
                button_frame,
                text=f"{self.app.config['water_snooze_minutes']}分钟后提醒",
                width=14,
                command=remind_later,
                bg="#e5e7eb",
                fg="#111827",
                activebackground="#d1d5db",
                relief="flat",
            ).pack(side="left", padx=8)

            window.protocol("WM_DELETE_WINDOW", close_popup)
            self._slide_window_in(window, width, height)

        self.dispatch(create_popup)

    def show_main_window(self, icon=None, item=None):
        self.dispatch(self._create_main_window)

    def _create_main_window(self, root):
        if self.main_window is not None and self.main_window.winfo_exists():
            self.main_window.lift()
            self.main_window.focus_force()
            return

        window = tk.Toplevel(root)
        self.main_window = window
        window.title(APP_TITLE)
        window.geometry("720x640")
        window.minsize(680, 560)

        shell = ttk.Frame(window)
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, highlightthickness=0)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        container = ttk.Frame(canvas, padding=18)
        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")

        def update_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(canvas_window, width=canvas.winfo_width())

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        container.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", update_scroll_region)
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        ttk.Label(
            container,
            text="健康提醒控制台",
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor="w")

        status_card = ttk.LabelFrame(container, text="当前状态", padding=12)
        status_card.pack(fill="x", pady=(10, 12))

        traffic_frame = ttk.Frame(status_card)
        traffic_frame.pack(anchor="w", fill="x", pady=(0, 8))
        traffic_canvas = tk.Canvas(
            traffic_frame,
            width=86,
            height=28,
            highlightthickness=0,
        )
        traffic_canvas.pack(side="left")
        traffic_label_var = tk.StringVar(value="")
        ttk.Label(
            traffic_frame,
            textvariable=traffic_label_var,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side="left", padx=(10, 0))

        def draw_traffic_status():
            traffic_canvas.delete("all")
            state = self.app.activity.state
            media = self.app.activity.media_active
            active_color = {
                "using": "#16a34a",
                "idle": "#f59e0b",
                "away": "#dc2626",
            }.get(state, "#94a3b8")
            label = {
                "using": "使用中（视频/会议）" if media else "使用中",
                "idle": "可能离开",
                "away": "离开",
            }.get(state, "未知")
            lights = [
                ("away", "#dc2626", 10),
                ("idle", "#f59e0b", 38),
                ("using", "#16a34a", 66),
            ]
            for name, color, x in lights:
                fill = color if name == state else "#cbd5e1"
                outline = active_color if name == state else "#94a3b8"
                traffic_canvas.create_oval(x, 4, x + 20, 24, fill=fill, outline=outline, width=2)
            traffic_label_var.set(label)

        status_var = tk.StringVar(value=self.app.get_status_text())
        ttk.Label(
            status_card,
            textvariable=status_var,
            justify="left",
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", fill="x")

        health_frame = ttk.LabelFrame(container, text="今日健康分", padding=12)
        health_frame.pack(fill="x", pady=(0, 12))
        health_var = tk.StringVar(value=self.app.get_health_score_text())
        ttk.Label(
            health_frame,
            textvariable=health_var,
            justify="left",
        ).pack(anchor="w", fill="x")

        settings = ttk.LabelFrame(container, text="提醒设置", padding=12)
        settings.pack(fill="x", pady=(4, 12))
        settings.columnconfigure(1, weight=1)

        work_start_var = tk.StringVar(value=self.app.config["work_start"])
        work_end_var = tk.StringVar(value=self.app.config["work_end"])
        sit_var = tk.StringVar(value=str(self.app.config["sit_interval_minutes"]))
        water_var = tk.StringVar(value=str(self.app.config["water_interval_minutes"]))
        snooze_var = tk.StringVar(value=str(self.app.config["water_snooze_minutes"]))
        away_var = tk.StringVar(value=str(self.app.config["away_after_minutes"]))
        idle_var = tk.StringVar(value=str(self.app.config["idle_after_minutes"]))
        camera_interval_var = tk.StringVar(
            value=str(self.app.config["camera_detection_interval_minutes"])
        )
        startup_var = tk.BooleanVar(value=bool(self.app.config["startup_enabled"]))
        meeting_var = tk.BooleanVar(value=bool(self.app.config["meeting_mode"]))
        camera_var = tk.BooleanVar(value=bool(self.app.config["camera_detection_enabled"]))
        screensaver_var = tk.BooleanVar(
            value=bool(self.app.config["meeting_auto_screensaver"])
        )

        def add_row(row, label, widget):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky="w", pady=5)
            widget.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))

        add_row(0, "上班时间 HH:MM", ttk.Entry(settings, textvariable=work_start_var))
        add_row(1, "下班时间 HH:MM", ttk.Entry(settings, textvariable=work_end_var))
        add_row(2, "久坐间隔（分钟）", ttk.Entry(settings, textvariable=sit_var))
        add_row(3, "喝水间隔（分钟）", ttk.Entry(settings, textvariable=water_var))
        add_row(4, "稍后提醒（分钟）", ttk.Entry(settings, textvariable=snooze_var))

        activity_settings = ttk.LabelFrame(container, text="状态检测", padding=12)
        activity_settings.pack(fill="x", pady=(0, 12))
        activity_settings.columnconfigure(1, weight=1)

        def add_activity_row(row, label, widget):
            ttk.Label(activity_settings, text=label).grid(row=row, column=0, sticky="w", pady=5)
            widget.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))

        add_activity_row(0, "可能离开判定（分钟）", ttk.Entry(activity_settings, textvariable=away_var))
        add_activity_row(1, "离开判定（分钟）", ttk.Entry(activity_settings, textvariable=idle_var))
        add_activity_row(
            2,
            "摄像头检测间隔（分钟）",
            ttk.Entry(activity_settings, textvariable=camera_interval_var),
        )

        options = ttk.LabelFrame(container, text="可选功能", padding=12)
        options.pack(fill="x", pady=(0, 12))
        ttk.Checkbutton(options, text="开机自启", variable=startup_var).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 18),
            pady=4,
        )
        ttk.Checkbutton(options, text="开会模式（暂停提醒）", variable=meeting_var).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 18),
            pady=4,
        )
        ttk.Checkbutton(options, text="摄像头检测（默认关闭）", variable=camera_var).grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 18),
            pady=4,
        )
        ttk.Checkbutton(
            options,
            text="开启开会模式时进入屏保",
            variable=screensaver_var,
        ).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=4)

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(0, 12))

        log_frame = ttk.LabelFrame(container, text="运行日志", padding=10)
        log_frame.pack(fill="both", expand=True)
        log_text = tk.Text(log_frame, height=10, wrap="word", font=("Consolas", 9))
        log_text.pack(fill="both", expand=True)
        log_text.configure(state="disabled")

        def refresh_logs():
            log_text.configure(state="normal")
            log_text.delete("1.0", "end")
            log_text.insert("end", self.app.log.read_recent())
            log_text.configure(state="disabled")
            log_text.see("end")

        def save_settings():
            start_value = parse_clock(
                work_start_var.get().strip(),
                DEFAULT_CONFIG["work_start"],
            ).strftime("%H:%M")
            end_value = parse_clock(
                work_end_var.get().strip(),
                DEFAULT_CONFIG["work_end"],
            ).strftime("%H:%M")
            new_config = {
                "work_start": start_value,
                "work_end": end_value,
                "sit_interval_minutes": safe_int(sit_var.get(), 45, 1, 480),
                "water_interval_minutes": safe_int(water_var.get(), 60, 1, 480),
                "water_snooze_minutes": safe_int(snooze_var.get(), 10, 1, 120),
                "away_after_minutes": safe_int(away_var.get(), 5, 1, 120),
                "idle_after_minutes": safe_int(idle_var.get(), 15, 1, 240),
                "camera_detection_enabled": bool(camera_var.get()),
                "camera_detection_interval_minutes": safe_int(
                    camera_interval_var.get(),
                    30,
                    5,
                    240,
                ),
                "startup_enabled": bool(startup_var.get()),
                "meeting_mode": bool(meeting_var.get()),
                "meeting_auto_screensaver": bool(screensaver_var.get()),
            }
            self.app.apply_settings(new_config)
            status_var.set(self.app.get_status_text())
            health_var.set(self.app.get_health_score_text())
            refresh_logs()

        ttk.Button(buttons, text="保存设置", command=save_settings).pack(
            side="left",
            padx=(0, 8),
        )
        ttk.Button(buttons, text="立即进入屏保", command=self.app.start_screensaver).pack(
            side="left",
            padx=(0, 8),
        )
        ttk.Button(buttons, text="刷新日志", command=refresh_logs).pack(
            side="left",
            padx=(0, 8),
        )
        ttk.Button(buttons, text="我站起来了", command=self.app.reset_sit_timer).pack(
            side="left",
            padx=(0, 8),
        )
        ttk.Button(buttons, text="喝水了", command=self.app.reset_water_timer).pack(
            side="left"
        )

        refresh_logs()

        ttk.Label(
            container,
            text=f"配置：{CONFIG_FILE}\n日志：{LOG_FILE}",
            foreground="#4b5563",
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        def tick():
            if window.winfo_exists():
                status_var.set(self.app.get_status_text())
                health_var.set(self.app.get_health_score_text())
                draw_traffic_status()
                window.after(1000, tick)

        def on_close():
            self.main_window = None
            canvas.unbind_all("<MouseWheel>")
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)
        draw_traffic_status()
        tick()
