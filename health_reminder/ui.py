import calendar
import queue
import threading
from datetime import date, timedelta
from .away_reason import AWAY_REASONS
from .calendar_data import METRICS, draw_bar_chart, draw_legend, load_day_stats, load_month_stats
from .config_store import parse_clock, safe_int
from .constants import APP_TITLE, APP_VERSION, CONFIG_FILE, DEFAULT_CONFIG, LOG_FILE
from .windows_integration import configure_tcl_tk_for_frozen_app
configure_tcl_tk_for_frozen_app()
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None
_C = dict(bg="#f5f5f7",sidebar="#1d1d1f",side_hi="#333336",side_txt="#a1a1a6",
    side_act="#ffffff",card="#ffffff",border="#e5e5ea",txt="#1d1d1f",txt2="#6e6e73",
    accent="#0071e3",green="#34c759",orange="#ff9500",red="#ff3b30",
    purple="#af52de",cyan="#5ac8fa",teal="#5cdb95",blue="#007aff")
NAV_ITEMS = [("dashboard","\u25a3","\u53ef\u89c6\u5316\u6570\u636e"),
    ("calendar","\u25a6","\u8bb0\u5f55\u65e5\u5386"),
    ("settings","\u25a7","\u8bbe\u7f6e")]

class UiManager:
    def __init__(self, app):
        self.app = app
        self.root = None
        self.main_window = None
        self.water_popup_open = False
        self.away_popup_open = False
        self.toast_windows = []
        self.tasks = queue.Queue()
        self._current_nav = "dashboard"
        self._cal_year = date.today().year
        self._cal_month = date.today().month
        self._cal_view = "chart"
        self._status_labels = {}
        self._stat_values = {}
        self._cal_content = None
        self._nav_buttons = {}

    @property
    def available(self):
        return tk is not None

    def start(self):
        if not self.available:
            self.app.log.write("tkinter not available")
            return
        def ui_loop():
            root = tk.Tk()
            root.withdraw()
            self.root = root
            self._poll_tasks()
            root.mainloop()
        threading.Thread(target=ui_loop, daemon=True).start()

    def dispatch(self, task):
        if not self.available: return
        self.tasks.put(task)

    def _poll_tasks(self):
        while True:
            try: task = self.tasks.get_nowait()
            except queue.Empty: break
            try: task(self.root)
            except Exception as exc: self.app.log.write(f"UI task failed: {exc}")
        self.root.after(100, self._poll_tasks)

    def _slide_window_in(self, window, width, height, y_offset=70):
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        tx = sw - width - 24
        y = sh - height - y_offset
        sx = sw + 12
        window.geometry(f"{width}x{height}+{sx}+{y}")
        def step(x):
            if not window.winfo_exists(): return
            if x <= tx:
                window.geometry(f"{width}x{height}+{tx}+{y}")
                return
            window.geometry(f"{width}x{height}+{x}+{y}")
            window.after(12, lambda: step(max(tx, x - 28)))
        step(sx)

    def _slide_window_out(self, window, width):
        if not window.winfo_exists(): return
        x, y = window.winfo_x(), window.winfo_y()
        sw = window.winfo_screenwidth()
        def step(cx):
            if not window.winfo_exists(): return
            if cx >= sw + 12:
                window.destroy()
                return
            window.geometry(f"+{cx}+{y}")
            window.after(12, lambda: step(cx + 30))
        step(x)
    def show_toast(self, title, message):
        if not self.available: return
        def _create(root):
            w, h = 360, 116
            win = tk.Toplevel(root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=_C["card"])
            fr = tk.Frame(win, bg=_C["card"], bd=1, relief="solid")
            fr.pack(fill="both", expand=True)
            tk.Label(fr, text=title, font=("Microsoft YaHei UI", 12, "bold"),
                bg=_C["card"], fg=_C["txt"], anchor="w").pack(fill="x", padx=16, pady=(14, 4))
            tk.Label(fr, text=message, font=("Microsoft YaHei UI", 10),
                bg=_C["card"], fg=_C["txt2"], anchor="w", justify="left",
                wraplength=318).pack(fill="x", padx=16)
            tk.Button(fr, text="\u00d7", command=lambda: self._slide_window_out(win, w),
                bg=_C["card"], fg=_C["txt2"], relief="flat", bd=0,
                font=("Microsoft YaHei UI", 12, "bold")).place(x=326, y=8, width=24, height=24)
            self._slide_window_in(win, w, h)
            win.after(5200, lambda: self._slide_window_out(win, w))
        self.dispatch(_create)

    def show_water_popup(self, message):
        if not self.available: return
        with self.app.state_lock:
            if self.water_popup_open: return
            self.water_popup_open = True
        def _create(root):
            w, h = 400, 200
            win = tk.Toplevel(root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=_C["card"])
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            fr = tk.Frame(win, bg=_C["card"], bd=1, relief="solid")
            fr.pack(fill="both", expand=True)
            tk.Label(fr, text="\u559d\u6c34\u63d0\u9192", font=("Microsoft YaHei UI", 14, "bold"),
                bg=_C["card"], fg=_C["txt"]).pack(pady=(16, 4))
            tk.Label(fr, text=message, font=("Microsoft YaHei UI", 10),
                bg=_C["card"], fg=_C["txt2"], wraplength=360, justify="center").pack(pady=(0, 12))
            bf = tk.Frame(fr, bg=_C["card"])
            bf.pack(pady=(0, 16))
            def close():
                self.water_popup_open = False
                win.destroy()
            def drank():
                self.app.reset_water_timer()
                close()
            def later():
                self.app.snooze_water_timer()
                self.app.notify("\u559d\u6c34\u63d0\u9192", f"\u597d\u7684\uff0c{self.app.config['water_snooze_minutes']}\u5206\u949f\u540e\u63d0\u9192")
                close()
            tk.Button(bf, text="\u6211\u559d\u4e86", width=12, command=drank,
                bg=_C["accent"], fg="white", relief="flat").pack(side="left", padx=8)
            tk.Button(bf, text=f"{self.app.config['water_snooze_minutes']}\u5206\u949f\u540e\u63d0\u9192",
                width=14, command=later, bg="#e5e7eb", fg=_C["txt"],
                relief="flat").pack(side="left", padx=8)
            win.protocol("WM_DELETE_WINDOW", close)
        self.dispatch(_create)
    def show_away_reason_popup(self):
        if not self.available: return
        with self.app.state_lock:
            if self.away_popup_open: return
            self.away_popup_open = True
        def _create(root):
            w, h = 480, 260
            win = tk.Toplevel(root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=_C["card"])
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            fr = tk.Frame(win, bg=_C["card"], bd=2, relief="solid")
            fr.pack(fill="both", expand=True)
            tk.Label(fr, text="\u4f60\u79bb\u5f00\u4e86\u5417\uff1f\u8bf7\u9009\u62e9\u79bb\u5e2d\u539f\u56e0",
                font=("Microsoft YaHei UI", 14, "bold"),
                bg=_C["card"], fg=_C["txt"]).pack(pady=(20, 16))
            bf = tk.Frame(fr, bg=_C["card"])
            bf.pack(pady=(0, 20))
            def close():
                self.away_popup_open = False
                if win.winfo_exists(): win.destroy()
            def pick(k):
                self.app.handle_away_reason(k)
                close()
            btns = [("bathroom","\U0001f6bf \u4e0a\u5395\u6240",_C["accent"]),
                    ("meeting","\U0001f4ac \u5f00\u4f1a",_C["purple"]),
                    ("smoke","\U0001f6ac \u62bd\u6839\u70df",_C["orange"]),
                    ("fieldwork","\U0001f4bc \u5916\u52e4",_C["green"])]
            for key, label, color in btns:
                tk.Button(bf, text=label, width=10, height=2,
                    font=("Microsoft YaHei UI", 11, "bold"),
                    bg=color, fg="white", relief="flat", cursor="hand2",
                    command=lambda k=key: pick(k)).pack(side="left", padx=6)
            win.protocol("WM_DELETE_WINDOW", close)
            win.focus_force()
        self.dispatch(_create)
    def show_main_window(self, icon=None, item=None):
        self.dispatch(self._create_main_window)

    def _create_main_window(self, root):
        if self.main_window is not None and self.main_window.winfo_exists():
            self.main_window.lift()
            self.main_window.focus_force()
            return
        win = tk.Toplevel(root)
        self.main_window = win
        win.title(APP_TITLE)
        win.geometry("960x640")
        win.minsize(860, 560)
        win.configure(bg=_C["bg"])
        sidebar = tk.Frame(win, bg=_C["sidebar"], width=200)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="\u63a7\u5236\u53f0", font=("Microsoft YaHei UI", 16, "bold"),
            bg=_C["sidebar"], fg="white", anchor="w").pack(fill="x", padx=20, pady=(28, 4))
        tk.Label(sidebar, text=f"v{APP_VERSION}",
            font=("Microsoft YaHei UI", 9), bg=_C["sidebar"],
            fg=_C["side_txt"], anchor="w").pack(fill="x", padx=22, pady=(0, 24))
        self._nav_buttons = {}
        for nav_id, icon_char, label in NAV_ITEMS:
            btn = tk.Label(sidebar, text=f"  {icon_char}  {label}",
                font=("Microsoft YaHei UI", 12), bg=_C["sidebar"],
                fg=_C["side_txt"], anchor="w", padx=20, pady=10, cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, nid=nav_id: self._switch_nav(nid))
            self._nav_buttons[nav_id] = btn
        content = tk.Frame(win, bg=_C["bg"])
        content.pack(side="left", fill="both", expand=True)
        self._content = content
        self._panels = {}
        self._build_dashboard(content)
        self._build_calendar(content)
        self._build_settings(content)
        self._switch_nav("dashboard")
        def on_close():
            self.main_window = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
        def tick():
            if win.winfo_exists():
                self._refresh_dashboard()
                win.after(1000, tick)
        tick()

    def _switch_nav(self, nav_id):
        self._current_nav = nav_id
        for nid, btn in self._nav_buttons.items():
            if nid == nav_id:
                btn.configure(bg=_C["side_hi"], fg=_C["side_act"])
            else:
                btn.configure(bg=_C["sidebar"], fg=_C["side_txt"])
        for pid, panel in self._panels.items():
            if pid == nav_id:
                panel.pack(fill="both", expand=True)
            else:
                panel.pack_forget()
        if nav_id == "calendar":
            self._refresh_calendar()
    def _build_dashboard(self, parent):
        panel = tk.Frame(parent, bg=_C["bg"])
        self._panels["dashboard"] = panel
        canvas = tk.Canvas(panel, bg=_C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=_C["bg"])
        canvas.create_window((4, 4), window=inner, anchor="nw", tags="inner")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure("inner", width=e.width - 8))
        hdr = tk.Frame(inner, bg=_C["bg"])
        hdr.pack(fill="x", padx=28, pady=(24, 4))
        tk.Label(hdr, text="\u53ef\u89c6\u5316\u6570\u636e", font=("Microsoft YaHei UI", 22, "bold"),
            bg=_C["bg"], fg=_C["txt"]).pack(side="left")
        tk.Label(hdr, text=date.today().strftime("%Y\u5e74%m\u6708%d\u65e5"),
            font=("Microsoft YaHei UI", 12), bg=_C["bg"], fg=_C["txt2"]).pack(side="right")
        ring_fr = tk.Frame(inner, bg=_C["card"], highlightbackground=_C["border"], highlightthickness=1)
        ring_fr.pack(fill="x", padx=28, pady=(16, 8))
        ring_left = tk.Frame(ring_fr, bg=_C["card"])
        ring_left.pack(side="left", padx=(24, 16), pady=20)
        cv = tk.Canvas(ring_left, width=140, height=140, bg=_C["card"], highlightthickness=0)
        cv.pack()
        self._score_canvas = cv
        ring_right = tk.Frame(ring_fr, bg=_C["card"])
        ring_right.pack(side="left", fill="x", expand=True, pady=20)
        tk.Label(ring_right, text="\u4eca\u65e5\u5065\u5eb7\u5206",
            font=("Microsoft YaHei UI", 14, "bold"), bg=_C["card"], fg=_C["txt"]).pack(anchor="w")
        self._score_detail = tk.Label(ring_right, text="", font=("Microsoft YaHei UI", 11),
            bg=_C["card"], fg=_C["txt2"], justify="left", anchor="w")
        self._score_detail.pack(anchor="w", pady=(6, 0))
        cards_fr = tk.Frame(inner, bg=_C["bg"])
        cards_fr.pack(fill="x", padx=28, pady=(8, 8))
        card_defs = [
            ("water_count","\u559d\u6c34",_C["accent"],"\U0001f4a7"),
            ("bathroom_count","\u4e0a\u5395\u6240",_C["orange"],"\U0001f6bf"),
            ("meeting_count","\u5f00\u4f1a",_C["purple"],"\U0001f4ac"),
            ("smoke_count","\u62bd\u6839\u70df",_C["red"],"\U0001f6ac"),
            ("fieldwork_count","\u5916\u52e4",_C["green"],"\U0001f4bc"),
            ("sit_count","\u8d77\u8eab",_C["cyan"],"\U0001f9b6")]
        for i, (key, label, color, emoji) in enumerate(card_defs):
            row, col = divmod(i, 3)
            card = tk.Frame(cards_fr, bg=_C["card"], highlightbackground=_C["border"], highlightthickness=1)
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            cards_fr.columnconfigure(col, weight=1)
            dot = tk.Canvas(card, width=10, height=10, bg=_C["card"], highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=color, outline="")
            dot.place(x=16, y=16)
            tk.Label(card, text=f"{emoji} {label}", font=("Microsoft YaHei UI", 11),
                bg=_C["card"], fg=_C["txt2"]).pack(anchor="w", padx=14, pady=(14, 0))
            val = tk.Label(card, text="0", font=("Microsoft YaHei UI", 28, "bold"),
                bg=_C["card"], fg=_C["txt"])
            val.pack(anchor="w", padx=14, pady=(0, 14))
            self._stat_values[key] = val
        info = tk.Frame(inner, bg=_C["card"], highlightbackground=_C["border"], highlightthickness=1)
        info.pack(fill="x", padx=28, pady=(8, 4))
        for i, label in enumerate(["\u72b6\u6001", "\u6444\u50cf\u5934", "\u79bb\u5e2d\u8bb0\u5f55"]):
            tk.Label(info, text=label, font=("Microsoft YaHei UI", 10),
                bg=_C["card"], fg=_C["txt2"]).grid(row=i, column=0, sticky="w", padx=16, pady=6)
            val = tk.Label(info, text="\u2014", font=("Microsoft YaHei UI", 10, "bold"),
                bg=_C["card"], fg=_C["txt"])
            val.grid(row=i, column=1, sticky="w", padx=8, pady=6)
            info.columnconfigure(1, weight=1)
            self._status_labels[label] = val
    def _refresh_dashboard(self):
        if not self._stat_values: return
        # Use live in-memory data for instant feedback
        hs = self.app.health_score.stats
        ar = self.app.away_reason.stats
        live = {
            "water_count": int(hs.get("water_count", 0)),
            "sit_count": int(hs.get("sit_count", 0)),
            "meeting_minutes": int(hs.get("meeting_minutes", 0)),
            "bathroom_count": int(ar.get("bathroom_count", 0)),
            "smoke_count": int(ar.get("smoke_count", 0)),
            "fieldwork_count": int(ar.get("fieldwork_count", 0)),
            "meeting_count": int(ar.get("meeting_count", 0)),
        }
        for key in self._stat_values:
            self._stat_values[key].configure(text=str(live.get(key, 0)))
        try:
            cv = self._score_canvas
            cv.delete("all")
            data = self.app.health_score.calculate(
                self.app.get_current_sit_minutes(), self.app.get_runtime_minutes())
            total = data["total"]
            cv.create_oval(10, 10, 130, 130, fill="#f0f0f5", outline="")
            extent = max(1, int(360 * total / 100))
            cv.create_arc(10, 10, 130, 130, start=90, extent=-extent,
                style="arc", outline=_C["accent"], width=10)
            cv.create_text(70, 70, text=str(total),
                font=("Microsoft YaHei UI", 32, "bold"), fill=_C["txt"])
            self._score_detail.configure(text=(
                f"\u559d\u6c34 {data['water_count']} \u6b21  \u8d77\u8eab {data['sit_count']} \u6b21\n"
                f"\u4e45\u5750 {int(self.app.get_current_sit_minutes())} \u5206\u949f  "
                f"\u5f00\u4f1a {data['meeting_minutes']} \u5206\u949f"))
        except Exception:
            pass
        # traffic light
        try:
            tc = self._traffic_canvas
            tc.delete("all")
            state = self.app.activity.state
            lights = [
                ("away",  _C["red"],    24),   # red
                ("idle",  _C["orange"], 64),   # yellow
                ("using", _C["blue"],  104),   # blue
            ]
            for name, color, y in lights:
                fill_c = color if name == state else "#d1d5db"
                tc.create_oval(10, y, 38, y + 28, fill=fill_c, outline="#9ca3af", width=1)
            label_map = {"away":"\u79bb\u5f00","idle":"\u53ef\u80fd\u79bb\u5f00","using":"\u4f7f\u7528\u4e2d"}
            self._traffic_label.configure(text=label_map.get(state, ""))
        except Exception:
            pass
        mode = "\u5f00\u4f1a\u6a21\u5f0f" if self.app.is_meeting_mode() else "\u6b63\u5e38"
        work = "\u5de5\u4f5c\u65f6\u95f4" if self.app.is_work_time() else "\u975e\u5de5\u4f5c\u65f6\u95f4"
        act = self.app.activity.label()
        self._status_labels["\u72b6\u6001"].configure(text=f"{mode} / {work} / {act}")
        self._status_labels["\u6444\u50cf\u5934"].configure(text=self.app.camera_presence.last_result)
        self._status_labels["\u79bb\u5e2d\u8bb0\u5f55"].configure(text=self.app.away_reason.summary_text())
        try:
            lt = self._dash_log
            lt.configure(state="normal")
            lt.delete("1.0", "end")
            lt.insert("end", self.app.log.read_recent())
            lt.configure(state="disabled")
            lt.see("end")
        except Exception:
            pass
    def _build_calendar(self, parent):
        panel = tk.Frame(parent, bg=_C["bg"])
        self._panels["calendar"] = panel
        hdr = tk.Frame(panel, bg=_C["bg"])
        hdr.pack(fill="x", padx=28, pady=(24, 8))
        tk.Label(hdr, text="\u8bb0\u5f55\u65e5\u5386", font=("Microsoft YaHei UI", 22, "bold"),
            bg=_C["bg"], fg=_C["txt"]).pack(side="left")
        tog = tk.Frame(hdr, bg=_C["bg"])
        tog.pack(side="right")
        self._btn_chart = tk.Label(tog, text="\u67f1\u72b6\u56fe", font=("Microsoft YaHei UI", 10),
            bg=_C["accent"], fg="white", padx=12, pady=4, cursor="hand2")
        self._btn_chart.pack(side="left", padx=(0, 2))
        self._btn_list = tk.Label(tog, text="\u5217\u8868", font=("Microsoft YaHei UI", 10),
            bg="#e5e7eb", fg=_C["txt"], padx=12, pady=4, cursor="hand2")
        self._btn_list.pack(side="left")
        self._btn_chart.bind("<Button-1>", lambda e: self._set_cal_view("chart"))
        self._btn_list.bind("<Button-1>", lambda e: self._set_cal_view("list"))
        nav = tk.Frame(panel, bg=_C["bg"])
        nav.pack(fill="x", padx=28, pady=(0, 8))
        self._btn_prev = tk.Label(nav, text="\u25c0", font=("Segoe UI", 14),
            bg=_C["bg"], fg=_C["accent"], cursor="hand2")
        self._btn_prev.pack(side="left")
        self._btn_prev.bind("<Button-1>", lambda e: self._cal_nav(-1))
        self._month_label = tk.Label(nav, text="", font=("Microsoft YaHei UI", 14, "bold"),
            bg=_C["bg"], fg=_C["txt"])
        self._month_label.pack(side="left", padx=12)
        self._btn_next = tk.Label(nav, text="\u25b6", font=("Segoe UI", 14),
            bg=_C["bg"], fg=_C["accent"], cursor="hand2")
        self._btn_next.pack(side="left")
        self._btn_next.bind("<Button-1>", lambda e: self._cal_nav(1))
        self._cal_grid = tk.Frame(panel, bg=_C["bg"])
        self._cal_grid.pack(fill="x", padx=28)
        self._cal_content = tk.Frame(panel, bg=_C["bg"])
        self._cal_content.pack(fill="both", expand=True, padx=28, pady=(8, 28))

    def _set_cal_view(self, mode):
        self._cal_view = mode
        if mode == "chart":
            self._btn_chart.configure(bg=_C["accent"], fg="white")
            self._btn_list.configure(bg="#e5e7eb", fg=_C["txt"])
        else:
            self._btn_chart.configure(bg="#e5e7eb", fg=_C["txt"])
            self._btn_list.configure(bg=_C["accent"], fg="white")
        self._refresh_calendar()

    def _cal_nav(self, delta):
        self._cal_month += delta
        if self._cal_month > 12:
            self._cal_month = 1
            self._cal_year += 1
        elif self._cal_month < 1:
            self._cal_month = 12
            self._cal_year -= 1
        self._refresh_calendar()
    def _refresh_calendar(self):
        if not self._cal_content: return
        y, m = self._cal_year, self._cal_month
        self._month_label.configure(text=f"{y}\u5e74{m}\u6708")
        for w in self._cal_grid.winfo_children(): w.destroy()
        days = ["\u4e00","\u4e8c","\u4e09","\u56db","\u4e94","\u516d","\u65e5"]
        for i, d in enumerate(days):
            tk.Label(self._cal_grid, text=d, width=6, font=("Microsoft YaHei UI", 9),
                bg=_C["bg"], fg=_C["txt2"]).grid(row=0, column=i)
        month_data = load_month_stats(y, m)
        first_weekday, days_in_month = calendar.monthrange(y, m)
        today_str = date.today().isoformat()
        for day in range(1, days_in_month + 1):
            r, c = divmod(first_weekday + day - 1, 7)
            ds = f"{y}-{m:02d}-{day:02d}"
            stats = month_data.get(ds, {})
            total = sum(stats.get(k, 0) for k, _, _ in METRICS)
            is_today = (ds == today_str)
            bg = _C["accent"] if is_today else (_C["card"] if total > 0 else _C["bg"])
            fg = "white" if is_today else (_C["txt"] if total > 0 else _C["txt2"])
            tk.Label(self._cal_grid, text=str(day), width=6,
                font=("Microsoft YaHei UI", 10, "bold" if is_today else "normal"),
                bg=bg, fg=fg, relief="flat").grid(row=r+1, column=c, padx=1, pady=1)
        for w in self._cal_content.winfo_children(): w.destroy()
        if self._cal_view == "chart":
            self._draw_chart_view(y, m, month_data)
        else:
            self._draw_list_view(y, m, month_data)

    def _draw_chart_view(self, y, m, month_data):
        tk.Label(self._cal_content, text="\u8fd1 7 \u5929\u8d8b\u52bf",
            font=("Microsoft YaHei UI", 12, "bold"), bg=_C["bg"], fg=_C["txt"]).pack(anchor="w", pady=(4, 8))
        chart_card = tk.Frame(self._cal_content, bg=_C["card"],
            highlightbackground=_C["border"], highlightthickness=1)
        chart_card.pack(fill="both", expand=True)
        cv = tk.Canvas(chart_card, bg=_C["card"], highlightthickness=0)
        cv.pack(fill="both", expand=True, padx=8, pady=8)
        today = date.today()
        last7 = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            ds = d.isoformat()
            last7.append((ds, month_data.get(ds, load_day_stats(d))))
        def draw(event):
            cv.delete("all")
            w, h = event.width, event.height
            draw_bar_chart(cv, last7, w, h - 30)
            draw_legend(cv, 40, h - 24)
        cv.bind("<Configure>", draw)

    def _draw_list_view(self, y, m, month_data):
        tk.Label(self._cal_content, text="\u6bcf\u65e5\u660e\u7ec6",
            font=("Microsoft YaHei UI", 12, "bold"), bg=_C["bg"], fg=_C["txt"]).pack(anchor="w", pady=(4, 8))
        cols = ["\u65e5\u671f","\u559d\u6c34","\u4e0a\u5395\u6240","\u5f00\u4f1a","\u62bd\u6839\u70df","\u5916\u52e4","\u8d77\u8eab"]
        keys = ["water_count","bathroom_count","meeting_count","smoke_count","fieldwork_count","sit_count"]
        header_fr = tk.Frame(self._cal_content, bg=_C["card"],
            highlightbackground=_C["border"], highlightthickness=1)
        header_fr.pack(fill="x")
        for ci, col in enumerate(cols):
            tk.Label(header_fr, text=col, width=10 if ci else 14,
                font=("Microsoft YaHei UI", 10, "bold"), bg=_C["card"], fg=_C["txt"],
                anchor="w" if ci == 0 else "center").grid(row=0, column=ci, padx=4, pady=8, sticky="w")
        list_cv = tk.Canvas(self._cal_content, bg=_C["card"],
            highlightbackground=_C["border"], highlightthickness=1)
        list_cv.pack(fill="both", expand=True)
        rows_fr = tk.Frame(list_cv, bg=_C["card"])
        list_cv.create_window((0, 0), window=rows_fr, anchor="nw", tags="rows")
        rows_fr.bind("<Configure>", lambda e: list_cv.configure(scrollregion=list_cv.bbox("all")))
        today_str = date.today().isoformat()
        for ri, ds in enumerate(sorted(month_data.keys(), reverse=True)):
            stats = month_data.get(ds, {})
            is_today = (ds == today_str)
            bg = _C["bg"] if is_today else _C["card"]
            tk.Label(rows_fr, text=ds + (" \u4eca\u5929" if is_today else ""), width=14,
                font=("Microsoft YaHei UI", 10, "bold" if is_today else "normal"),
                bg=bg, fg=_C["txt"], anchor="w").grid(row=ri, column=0, padx=4, pady=4)
            for ci, key in enumerate(keys):
                tk.Label(rows_fr, text=str(stats.get(key, 0)), width=10,
                    font=("Microsoft YaHei UI", 10), bg=bg,
                    fg=_C["txt"], anchor="center").grid(row=ri, column=ci+1, padx=4, pady=4)
    def _build_settings(self, parent):
        panel = tk.Frame(parent, bg=_C["bg"])
        self._panels["settings"] = panel
        cv = tk.Canvas(panel, bg=_C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(panel, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(cv, bg=_C["bg"])
        cv.create_window((4, 4), window=inner, anchor="nw", tags="inner")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure("inner", width=e.width - 8))

        tk.Label(inner, text="\u8bbe\u7f6e", font=("Microsoft YaHei UI", 22, "bold"),
            bg=_C["bg"], fg=_C["txt"]).pack(anchor="w", padx=28, pady=(24, 16))

        # --- toggle switches ---
        sw_fr = tk.LabelFrame(inner, text="\u5f00\u5173\u9009\u9879",
            font=("Microsoft YaHei UI", 12, "bold"), bg=_C["card"], fg=_C["txt"],
            labelanchor="nw", padx=16, pady=12)
        sw_fr.pack(fill="x", padx=28, pady=(0, 12))
        self._toggle_vars = {}
        toggle_defs = [
            ("startup_enabled","\u5f00\u673a\u81ea\u542f"),
            ("meeting_mode","\u5f00\u4f1a\u6a21\u5f0f"),
            ("quiet_enabled","\u52ff\u6270\u6a21\u5f0f"),
            ("center_popup_enabled","\u4e2d\u592e\u5f39\u7a97")]
        for i, (key, label) in enumerate(toggle_defs):
            var = tk.BooleanVar(value=bool(self.app.config.get(key, True)))
            self._toggle_vars[key] = var
            tk.Checkbutton(sw_fr, text=label, variable=var,
                font=("Microsoft YaHei UI", 11), bg=_C["card"], fg=_C["txt"],
                selectcolor=_C["card"], activebackground=_C["card"],
                anchor="w").grid(row=i // 2, column=i % 2, sticky="w", padx=12, pady=6)
        sw_fr.columnconfigure(0, weight=1)
        sw_fr.columnconfigure(1, weight=1)

        # --- time settings ---
        tm_fr = tk.LabelFrame(inner, text="\u65f6\u95f4\u8bbe\u7f6e",
            font=("Microsoft YaHei UI", 12, "bold"), bg=_C["card"], fg=_C["txt"],
            labelanchor="nw", padx=16, pady=12)
        tm_fr.pack(fill="x", padx=28, pady=(0, 12))
        tm_fr.columnconfigure(1, weight=1)
        self._time_vars = {}
        time_defs = [("work_start","\u4e0a\u73ed\u65f6\u95f4 HH:MM"),
            ("work_end","\u4e0b\u73ed\u65f6\u95f4 HH:MM"),
            ("sit_interval","\u4e45\u5750\u95f4\u9694\uff08\u5206\u949f\uff09"),
            ("water_interval","\u559d\u6c34\u95f4\u9694\uff08\u5206\u949f\uff09"),
            ("snooze_interval","\u7a0d\u540e\u63d0\u9192\uff08\u5206\u949f\uff09")]
        for i, (key, label) in enumerate(time_defs):
            tk.Label(tm_fr, text=label, font=("Microsoft YaHei UI", 10),
                bg=_C["card"], fg=_C["txt"]).grid(row=i, column=0, sticky="w", padx=12, pady=6)
            if "start" in key or "end" in key:
                cfg_key = "work_start" if "start" in key else "work_end"
                val = self.app.config.get(cfg_key, DEFAULT_CONFIG.get(cfg_key, "08:30"))
            else:
                cfg_map = {"sit_interval":"sit_interval_minutes",
                    "water_interval":"water_interval_minutes","snooze_interval":"water_snooze_minutes"}
                val = str(self.app.config.get(cfg_map[key], 45))
            var = tk.StringVar(value=str(val))
            self._time_vars[key] = var
            tk.Entry(tm_fr, textvariable=var, width=12,
                font=("Microsoft YaHei UI", 10), relief="solid", bd=1
                ).grid(row=i, column=1, sticky="ew", padx=(10, 12), pady=6)

        # --- activity detection ---
        act_fr = tk.LabelFrame(inner, text="\u72b6\u6001\u68c0\u6d4b",
            font=("Microsoft YaHei UI", 12, "bold"), bg=_C["card"], fg=_C["txt"],
            labelanchor="nw", padx=16, pady=12)
        act_fr.pack(fill="x", padx=28, pady=(0, 12))
        act_fr.columnconfigure(1, weight=1)
        self._act_vars = {}
        for i, (key, label, cfg_key, default) in enumerate([
            ("away_after","\u53ef\u80fd\u79bb\u5f00\u5224\u5b9a\uff08\u5206\u949f\uff09","away_after_minutes",10),
            ("idle_after","\u79bb\u5f00\u5224\u5b9a\uff08\u5206\u949f\uff09","idle_after_minutes",15)]):
            tk.Label(act_fr, text=label, font=("Microsoft YaHei UI", 10),
                bg=_C["card"], fg=_C["txt"]).grid(row=i, column=0, sticky="w", padx=12, pady=6)
            var = tk.StringVar(value=str(self.app.config.get(cfg_key, default)))
            self._act_vars[key] = var
            tk.Entry(act_fr, textvariable=var, width=12,
                font=("Microsoft YaHei UI", 10), relief="solid", bd=1
                ).grid(row=i, column=1, sticky="ew", padx=(10, 12), pady=6)

        # --- buttons ---
        btn_fr = tk.Frame(inner, bg=_C["bg"])
        btn_fr.pack(fill="x", padx=28, pady=(4, 8))
        tk.Button(btn_fr, text="\u4fdd\u5b58\u8bbe\u7f6e", font=("Microsoft YaHei UI", 11, "bold"),
            bg=_C["accent"], fg="white", relief="flat", padx=24, pady=8,
            command=self._save_settings).pack(side="left")
        tk.Button(btn_fr, text="\u6211\u7ad9\u8d77\u6765\u4e86", font=("Microsoft YaHei UI", 10),
            bg="#e5e7eb", fg=_C["txt"], relief="flat", padx=16, pady=8,
            command=self.app.reset_sit_timer).pack(side="left", padx=(12, 0))
        tk.Button(btn_fr, text="\u559d\u6c34\u4e86", font=("Microsoft YaHei UI", 10),
            bg="#e5e7eb", fg=_C["txt"], relief="flat", padx=16, pady=8,
            command=self.app.reset_water_timer).pack(side="left", padx=(12, 0))

        tk.Label(inner, text=f"\u914d\u7f6e\uff1a{CONFIG_FILE}\n\u65e5\u5fd7\uff1a{LOG_FILE}",
            font=("Microsoft YaHei UI", 9), bg=_C["bg"],
            fg=_C["txt2"]).pack(anchor="w", padx=28, pady=(8, 12))

        # --- log ---
        log_fr = tk.LabelFrame(inner, text="\u8fd0\u884c\u65e5\u5fd7",
            font=("Microsoft YaHei UI", 12, "bold"), bg=_C["card"], fg=_C["txt"],
            labelanchor="nw", padx=10, pady=10)
        log_fr.pack(fill="both", expand=True, padx=28, pady=(0, 28))
        log_text = tk.Text(log_fr, height=8, wrap="word", font=("Consolas", 9),
            bg=_C["card"], fg=_C["txt2"], bd=0)
        log_text.pack(fill="both", expand=True)
        log_text.configure(state="disabled")
        self._dash_log = log_text
    def _save_settings(self):
        start = parse_clock(self._time_vars["work_start"].get().strip(),
            DEFAULT_CONFIG["work_start"]).strftime("%H:%M")
        end = parse_clock(self._time_vars["work_end"].get().strip(),
            DEFAULT_CONFIG["work_end"]).strftime("%H:%M")
        new_config = {
            "work_start": start, "work_end": end,
            "sit_interval_minutes": safe_int(self._time_vars["sit_interval"].get(), 45, 1, 480),
            "water_interval_minutes": safe_int(self._time_vars["water_interval"].get(), 60, 1, 480),
            "water_snooze_minutes": safe_int(self._time_vars["snooze_interval"].get(), 10, 1, 120),
            "away_after_minutes": safe_int(self._act_vars["away_after"].get(), 10, 1, 120),
            "idle_after_minutes": safe_int(self._act_vars["idle_after"].get(), 15, 1, 240),
            "startup_enabled": bool(self._toggle_vars["startup_enabled"].get()),
            "meeting_mode": bool(self._toggle_vars["meeting_mode"].get()),
            "quiet_enabled": bool(self._toggle_vars["quiet_enabled"].get()),
            "center_popup_enabled": bool(self._toggle_vars["center_popup_enabled"].get()),
        }
        self.app.apply_settings(new_config)
        self.app.notify("\u8bbe\u7f6e\u5df2\u4fdd\u5b58", "\u65b0\u7684\u63d0\u9192\u8bbe\u7f6e\u5df2\u7ecf\u751f\u6548")

class _ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable=None, on_color="#0071e3",
            off_color="#d1d5db", width=44, height=24, **kw):
        super().__init__(parent, width=width, height=height,
            bg=kw.pop("bg", parent["bg"]), highlightthickness=0, **kw)
        self._var = variable or tk.BooleanVar()
        self._on_color = on_color
        self._off_color = off_color
        self._w = width
        self._h = height
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _toggle(self, event=None):
        self._var.set(not self._var.get())
        self._draw()

    def _draw(self):
        self.delete("all")
        r = self._h // 2
        on = self._var.get()
        bg = self._on_color if on else self._off_color
        self.create_oval(0, 0, self._h, self._h, fill=bg, outline="")
        self.create_oval(self._w - self._h, 0, self._w, self._h, fill=bg, outline="")
        self.create_rectangle(r, 0, self._w - r, self._h, fill=bg, outline="")
        knob_x = self._w - r - 2 if on else r + 2
        self.create_oval(knob_x - r + 4, 2, knob_x + r - 4, self._h - 2,
            fill="white", outline="")





