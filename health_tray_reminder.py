import sys
import time
import random
import threading
from datetime import datetime, timedelta, time as datetime_time
from pathlib import Path

import schedule
from PIL import Image, ImageDraw
from plyer import notification
from pystray import Icon, Menu, MenuItem

try:
    import tkinter as tk
except ImportError:
    tk = None

try:
    import winreg
except ImportError:
    winreg = None


APP_NAME = "HealthTrayReminder"
APP_DISPLAY_NAME = "健康提醒"
APP_VERSION = "1.3.0"
APP_TITLE = f"{APP_DISPLAY_NAME} v{APP_VERSION}"

WORK_START = datetime_time(8, 30)
WORK_END = datetime_time(17, 0)

SIT_INTERVAL_MINUTES = 45
WATER_INTERVAL_MINUTES = 60
WATER_SNOOZE_MINUTES = 10

SIT_REMINDERS = [
    "出去拔根小烟，顺便让腿开机",
    "该离开椅子一会儿了，出去透口气",
    "屁股申请解绑椅子，批准一下",
    "站起来晃一圈，别和椅子处太久",
    "出去走两步，假装自己很忙",
    "腿都快忘了自己是腿了，起来用一下",
    "起来活动一下，顺便看看窗外真实世界",
    "出去放个风，让脑子换换气",
    "椅子占用时间过长，建议强制下线",
    "站起来巡逻一圈，检查一下公司空气",
    "出去溜达两步，回来继续装作很专业",
    "身体提示：需要短暂重启一下",
    "该起身了，别把自己焊在工位上",
    "离开屏幕一分钟，让眼睛也下个班",
    "出去站会儿，顺便把灵魂叫回来",
    "腿部系统提示：长期未运行",
    "起来走走，别让椅子以为赢了",
    "出去转一圈，给今天续点状态",
    "站起来活动活动，顺便接杯水也行",
    "工位先放这儿，人出去喘口气",
]

WATER_REMINDERS = [
    "给身体补点水，别让它靠意志力硬撑 💧",
    "咖啡负责清醒，温水负责续命，轮到温水上场了",
    "喉咙可能没说话，但它正在等一口水",
    "喝一口水，让脑子从加载中回到在线",
    "水杯已经看你很久了，给它一点存在感",
    "少喝点浓茶，给身体来一口朴素的温柔",
    "现在喝水，等会儿的你会偷偷感谢现在的你",
    "补水时间到，别把自己熬成低电量模式",
    "来一口温水，给今天的精神状态加点缓冲",
    "喝水不是任务，是给身体发工资",
    "你的细胞申请一点点后勤补给",
    "别等口渴才喝水，口渴已经是在催单了",
    "电脑要散热，人也要补水",
    "水杯不只是桌面摆件，是你的隐藏队友",
    "喝点水，让咖啡因别一个人扛全场",
    "现在起身接水，顺便让眼睛休息十秒",
    "给肾一点掌声，也给它一点水",
    "一口水下去，疲惫不一定消失，但仪式感到了",
    "别让嘴唇先发现你缺水",
    "喝水小回合开始，目标：保持清醒又不焦躁",
]

last_sit_reset = datetime.now()
last_water_reset = datetime.now()
water_popup_open = False
running = True
tray_icon = None
state_lock = threading.Lock()


def is_work_time():
    """判断当前时间是否在 8:30 到 17:00 之间。"""
    now = datetime.now().time()
    return WORK_START <= now <= WORK_END


def show_notice(title, message):
    """显示 Windows 桌面通知。"""
    notification.notify(
        title=title,
        message=message,
        app_name=APP_TITLE,
        timeout=10,
    )


def show_about(icon=None, item=None):
    show_notice("关于程序", f"{APP_TITLE}\n久坐、喝水和上下班提醒工具")


def morning_notice():
    show_notice(
        "早上好",
        "新的一天开始了，记得多喝水，久了起来走走 💧",
    )


def evening_notice():
    show_notice(
        "下班时间到了",
        "今天辛苦了，回家记得泡个温水澡放松一下 🛁",
    )


def reset_sit_timer(icon=None, item=None):
    global last_sit_reset
    with state_lock:
        last_sit_reset = datetime.now()
    show_notice("久坐提醒", "好的，计时重新开始")


def reset_water_timer(icon=None, item=None):
    global last_water_reset
    with state_lock:
        last_water_reset = datetime.now()
    show_notice("喝水提醒", "好的，记得保持")


def snooze_water_timer():
    global last_water_reset
    with state_lock:
        last_water_reset = datetime.now() - timedelta(
            minutes=WATER_INTERVAL_MINUTES - WATER_SNOOZE_MINUTES
        )


def close_water_popup(window):
    global water_popup_open
    water_popup_open = False
    window.destroy()


def get_water_reminder():
    return random.choice(WATER_REMINDERS)


def show_water_popup(message):
    global water_popup_open

    if tk is None:
        return

    with state_lock:
        if water_popup_open:
            return
        water_popup_open = True

    def popup_thread():
        window = tk.Tk()
        window.title("喝水提醒")
        window.resizable(False, False)
        window.attributes("-topmost", True)

        width = 320
        height = 150
        screen_height = window.winfo_screenheight()
        x = 24
        y = screen_height - height - 70
        window.geometry(f"{width}x{height}+{x}+{y}")

        window.configure(bg="#f7fbff")

        title = tk.Label(
            window,
            text="该补充水分了",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg="#f7fbff",
            fg="#1d4ed8",
        )
        title.pack(pady=(18, 6))

        message = tk.Label(
            window,
            text=message,
            font=("Microsoft YaHei UI", 10),
            bg="#f7fbff",
            fg="#1f2937",
            wraplength=270,
            justify="center",
        )
        message.pack(pady=(0, 14))

        button_frame = tk.Frame(window, bg="#f7fbff")
        button_frame.pack()

        def drank_water():
            reset_water_timer()
            close_water_popup(window)

        def remind_later():
            snooze_water_timer()
            show_notice("喝水提醒", f"好的，{WATER_SNOOZE_MINUTES}分钟后再提醒")
            close_water_popup(window)

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
            text="10分钟后提醒",
            width=14,
            command=remind_later,
            bg="#e5e7eb",
            fg="#111827",
            activebackground="#d1d5db",
            relief="flat",
        ).pack(side="left", padx=8)

        window.protocol("WM_DELETE_WINDOW", lambda: close_water_popup(window))
        window.mainloop()

    threading.Thread(target=popup_thread, daemon=True).start()


def check_sit_reminder():
    global last_sit_reset
    if not is_work_time():
        return

    with state_lock:
        minutes_passed = (datetime.now() - last_sit_reset).total_seconds() / 60
        if minutes_passed < SIT_INTERVAL_MINUTES:
            return
        last_sit_reset = datetime.now()

    show_notice("久坐提醒", random.choice(SIT_REMINDERS))


def check_water_reminder():
    global last_water_reset
    if not is_work_time():
        return

    with state_lock:
        minutes_passed = (datetime.now() - last_water_reset).total_seconds() / 60
        if minutes_passed < WATER_INTERVAL_MINUTES:
            return
        last_water_reset = datetime.now()

    message = get_water_reminder()
    show_notice("喝水提醒", message)
    show_water_popup(message)


def get_startup_command():
    """生成开机启动命令：打包后启动 exe，源码运行时启动 Python 脚本。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    python_exe = pythonw if pythonw.exists() else Path(sys.executable)
    script_path = Path(__file__).resolve()
    return f'"{python_exe}" "{script_path}"'


def add_to_startup():
    """把程序加入当前用户的 Windows 开机启动项。"""
    if winreg is None:
        return

    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        command = get_startup_command()
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
    except OSError:
        pass


def create_icon_image():
    """用代码生成一个蓝色圆形托盘图标。"""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 6, size - 6, size - 6), fill=(30, 136, 229, 255))
    draw.ellipse((18, 14, 34, 30), fill=(120, 200, 255, 230))
    return image


def scheduler_loop():
    while running:
        schedule.run_pending()
        check_sit_reminder()
        check_water_reminder()
        time.sleep(1)


def quit_program(icon, item):
    global running
    running = False
    icon.stop()


def setup_schedule():
    schedule.every().day.at("08:30").do(morning_notice)
    schedule.every().day.at("17:00").do(evening_notice)


def main():
    global tray_icon

    add_to_startup()
    setup_schedule()

    threading.Thread(target=scheduler_loop, daemon=True).start()

    menu = Menu(
        MenuItem(f"关于程序 v{APP_VERSION}", show_about),
        MenuItem("我站起来了", reset_sit_timer),
        MenuItem("喝水了", reset_water_timer),
        MenuItem("退出程序", quit_program),
    )

    tray_icon = Icon(
        APP_NAME,
        create_icon_image(),
        APP_TITLE,
        menu,
    )
    tray_icon.run()


if __name__ == "__main__":
    main()
