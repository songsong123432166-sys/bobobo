from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock


class EventLogger:
    """事件日志记录器，每条日志包含时间戳、事件类型和详情。"""
    def __init__(self, path: Path, max_bytes: int = 1_000_000) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self._lock = Lock()

    def log(self, event: str, detail: str = "") -> None:
        """记录一条事件日志。"""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp} | {event}"
        if detail:
            line += f" | {detail}"
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size > self.max_bytes:
                    self.path.replace(self.path.with_suffix(".log.1"))
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        except Exception:
            pass

    def tail(self, count: int = 20) -> list[str]:
        """读取最近N条日志，用于界面展示。"""
        try:
            if not self.path.exists():
                return []
            lines = self.path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return lines[-count:]
        except Exception:
            return []
