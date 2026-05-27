import json
from datetime import datetime

from .constants import CONFIG_FILE, DATA_DIR, DEFAULT_CONFIG


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_data_dir()
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **loaded}
        except (OSError, json.JSONDecodeError):
            pass

    config = DEFAULT_CONFIG.copy()
    save_config(config)
    return config


def save_config(config):
    ensure_data_dir()
    try:
        CONFIG_FILE.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def parse_clock(value, fallback):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return datetime.strptime(fallback, "%H:%M").time()


def normalize_clock(value, fallback):
    return parse_clock(value, fallback).strftime("%H:%M")


def safe_int(value, fallback, minimum=1, maximum=24 * 60):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))
