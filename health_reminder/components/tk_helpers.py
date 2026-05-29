def center_geometry(window, width, height):
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    return f"{width}x{height}+{(screen_w - width) // 2}+{(screen_h - height) // 2}"


def slide_window_in(window, width, height, y_offset=70):
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    target_x = screen_w - width - 24
    y = screen_h - height - y_offset
    start_x = screen_w + 12
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


def slide_window_out(window, width):
    if not window.winfo_exists():
        return
    x, y = window.winfo_x(), window.winfo_y()
    screen_w = window.winfo_screenwidth()

    def step(current_x):
        if not window.winfo_exists():
            return
        if current_x >= screen_w + 12:
            window.destroy()
            return
        window.geometry(f"+{current_x}+{y}")
        window.after(12, lambda: step(current_x + 30))

    step(x)
