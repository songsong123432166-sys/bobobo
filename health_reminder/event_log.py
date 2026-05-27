from datetime import datetime

from .config_store import ensure_data_dir
from .constants import LOG_FILE


class EventLog:
    def __init__(self):
        self.last_event = "程序启动中"

    def write(self, message):
        self.last_event = message
        ensure_data_dir()
        line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {message}\n"
        try:
            with LOG_FILE.open("a", encoding="utf-8") as file:
                file.write(line)
        except OSError:
            pass

    def read_recent(self, limit=80):
        if not LOG_FILE.exists():
            return ""
        try:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""
        return "\n".join(lines[-limit:])
