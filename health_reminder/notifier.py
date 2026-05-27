from plyer import notification

from .constants import APP_TITLE


class Notifier:
    def __init__(self, log):
        self.log = log
        self.tray_icon = None

    def set_tray_icon(self, tray_icon):
        self.tray_icon = tray_icon

    def notify(self, title, message):
        try:
            notification.notify(
                title=title,
                message=message,
                app_name=APP_TITLE,
                timeout=10,
            )
        except Exception:
            pass

        if self.tray_icon is not None:
            try:
                self.tray_icon.notify(message, title)
            except Exception:
                pass

        self.log.write(f"{title}: {message}")
