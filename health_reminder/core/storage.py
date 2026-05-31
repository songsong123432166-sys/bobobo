from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    """读取JSON文件，文件不存在或格式错误时返回默认值。"""
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def write_json(path: Path, data: Any) -> bool:
    """原子写入JSON文件，先写临时文件再重命名，避免数据损坏。"""
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
    """深度合并两个字典，loaded中的值覆盖default中的对应值。"""
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
