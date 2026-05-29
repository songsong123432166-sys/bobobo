from ..components.calendar_panel import build_calendar, refresh_calendar
from ..components.dashboard import build_dashboard, refresh_dashboard
from ..components.settings_panel import build_settings
from ..config.ui_config import NAV_ITEMS
from ..constants import APP_TITLE, APP_VERSION


def create_main_window(manager, root):
    tk = manager.tk
    colors = manager.colors
    if manager.main_window is not None and manager.main_window.winfo_exists():
        manager.main_window.lift()
        manager.main_window.focus_force()
        return

    win = tk.Toplevel(root)
    manager.main_window = win
    win.title(APP_TITLE)
    win.geometry("960x640")
    win.minsize(860, 560)
    win.configure(bg=colors["bg"])

    sidebar = tk.Frame(win, bg=colors["sidebar"], width=200)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    tk.Label(sidebar, text="控制台", font=("Microsoft YaHei UI", 16, "bold"), bg=colors["sidebar"], fg="white", anchor="w").pack(fill="x", padx=20, pady=(28, 4))
    tk.Label(sidebar, text=f"v{APP_VERSION}", font=("Microsoft YaHei UI", 9), bg=colors["sidebar"], fg=colors["side_txt"], anchor="w").pack(fill="x", padx=22, pady=(0, 24))

    manager._nav_buttons = {}
    for nav_id, icon, label in NAV_ITEMS:
        button = tk.Label(sidebar, text=f"  {icon}  {label}", font=("Microsoft YaHei UI", 12), bg=colors["sidebar"], fg=colors["side_txt"], anchor="w", padx=20, pady=10, cursor="hand2")
        button.pack(fill="x")
        button.bind("<Button-1>", lambda event, current=nav_id: switch_nav(manager, current))
        manager._nav_buttons[nav_id] = button

    content = tk.Frame(win, bg=colors["bg"])
    content.pack(side="left", fill="both", expand=True)
    manager._content = content
    manager._panels = {}
    build_dashboard(manager, content)
    build_calendar(manager, content)
    build_settings(manager, content)
    switch_nav(manager, "dashboard")

    def on_close():
        manager.main_window = None
        win.destroy()

    def tick():
        if win.winfo_exists():
            refresh_dashboard(manager)
            win.after(1000, tick)

    win.protocol("WM_DELETE_WINDOW", on_close)
    tick()


def switch_nav(manager, nav_id):
    colors = manager.colors
    manager._current_nav = nav_id
    for current_id, button in manager._nav_buttons.items():
        if current_id == nav_id:
            button.configure(bg=colors["side_hi"], fg=colors["side_act"])
        else:
            button.configure(bg=colors["sidebar"], fg=colors["side_txt"])
    for panel_id, panel in manager._panels.items():
        if panel_id == nav_id:
            panel.pack(fill="both", expand=True)
        else:
            panel.pack_forget()
    if nav_id == "calendar":
        refresh_calendar(manager)
