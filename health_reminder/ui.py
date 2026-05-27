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
            screen_height = window.winfo_screenheight()
            x = 24
            y = screen_height - height - 70
            window.geometry(f"{width}x{height}+{x}+{y}")
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
                window.destroy()

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
        window.geometry("680x560")
        window.minsize(640, 520)

        container = ttk.Frame(window, padding=18)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="健康提醒控制台",
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor="w")

        status_var = tk.StringVar(value=self.app.get_status_text())
        ttk.Label(
            container,
            textvariable=status_var,
            justify="left",
            padding=(0, 10, 0, 10),
        ).pack(anchor="w", fill="x")

        settings = ttk.LabelFrame(container, text="提醒设置", padding=12)
        settings.pack(fill="x", pady=(4, 12))
        settings.columnconfigure(1, weight=1)

        work_start_var = tk.StringVar(value=self.app.config["work_start"])
        work_end_var = tk.StringVar(value=self.app.config["work_end"])
        sit_var = tk.StringVar(value=str(self.app.config["sit_interval_minutes"]))
        water_var = tk.StringVar(value=str(self.app.config["water_interval_minutes"]))
        snooze_var = tk.StringVar(value=str(self.app.config["water_snooze_minutes"]))
        startup_var = tk.BooleanVar(value=bool(self.app.config["startup_enabled"]))
        meeting_var = tk.BooleanVar(value=bool(self.app.config["meeting_mode"]))
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

        checks = ttk.Frame(settings)
        checks.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(checks, text="开机自启", variable=startup_var).pack(
            side="left",
            padx=(0, 18),
        )
        ttk.Checkbutton(checks, text="开会模式（暂停提醒）", variable=meeting_var).pack(
            side="left",
            padx=(0, 18),
        )
        ttk.Checkbutton(
            checks,
            text="开启开会模式时进入屏保",
            variable=screensaver_var,
        ).pack(side="left")

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
                "startup_enabled": bool(startup_var.get()),
                "meeting_mode": bool(meeting_var.get()),
                "meeting_auto_screensaver": bool(screensaver_var.get()),
            }
            self.app.apply_settings(new_config)
            status_var.set(self.app.get_status_text())
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
                window.after(1000, tick)

        def on_close():
            self.main_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)
        tick()
