from __future__ import annotations

import threading
from typing import Callable

from .. import __version__
from .icon import create_tray_icon


class TrayController:
    def __init__(
        self,
        on_open: Callable[[], None],
        on_about: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.on_open = on_open
        self.on_about = on_about
        self.on_exit = on_exit
        self._icon = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("打开主界面", lambda _icon, _item: self.on_open(), default=True),
                pystray.MenuItem(f"关于程序 / {__version__}", lambda _icon, _item: self.on_about()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出程序", lambda _icon, _item: self.on_exit()),
            )
            self._icon = pystray.Icon("HealthTrayReminder", create_tray_icon(), "健康提醒", menu)
            self._thread = threading.Thread(target=self._icon.run, name="health-tray-icon", daemon=True)
            self._thread.start()
        except Exception:
            self._icon = None

    def stop(self) -> None:
        try:
            if self._icon is not None:
                self._icon.stop()
        except Exception:
            pass
