from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def write_json(path: Path, data: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        tmp.replace(path)
        return True
    except Exception:
        return False


def deep_merge(default: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in default.items():
        loaded_value = loaded.get(key) if isinstance(loaded, dict) else None
        if isinstance(value, dict):
            result[key] = deep_merge(value, loaded_value if isinstance(loaded_value, dict) else {})
        else:
            result[key] = loaded_value if loaded_value is not None else value

    if isinstance(loaded, dict):
        for key, value in loaded.items():
            if key not in result:
                result[key] = value
    return result
