from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


APP_DIR_NAME = "HealthTrayReminder"


@dataclass(frozen=True)
class DataPaths:
    root: Path
    degraded: bool = False
    error: str | None = None

    @property
    def config(self) -> Path:
        return self.root / "config.json"

    @property
    def log(self) -> Path:
        return self.root / "run.log"

    @property
    def health_score(self) -> Path:
        return self.root / "health_score.json"

    @property
    def away_reason(self) -> Path:
        return self.root / "away_reason.json"


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def _try_make(path: Path) -> tuple[bool, str | None]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, None
    except Exception as exc:  # pragma: no cover - depends on host permissions
        return False, str(exc)


def get_data_paths() -> DataPaths:
    candidates: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / APP_DIR_NAME)
    candidates.append(Path.home() / f".{APP_DIR_NAME}")
    candidates.append(Path(tempfile.gettempdir()) / APP_DIR_NAME)

    first_error: str | None = None
    for index, candidate in enumerate(candidates):
        ok, error = _try_make(candidate)
        if ok:
            return DataPaths(candidate, degraded=index > 0, error=first_error)
        first_error = first_error or error

    fallback = Path.cwd() / APP_DIR_NAME
    _try_make(fallback)
    return DataPaths(fallback, degraded=True, error=first_error)
