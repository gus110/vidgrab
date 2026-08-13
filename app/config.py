"""Configuración global de VidGrab."""
import json
import os
from pathlib import Path

APP_NAME = "VidGrab"
APP_VERSION = "1.0.0"

CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / "VidGrab"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "VidGrab")

FREE_DAILY_LIMIT = 5

DEFAULTS = {
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "quality": "best",          # best | 1080 | 720 | 480 | audio
    "theme": "dark",            # dark | light | system
    "accent": "blue",           # blue | green | dark-blue
    "server_port": 8743,
    "auto_open_folder": False,
    "notify_on_complete": True,
    "license_key": "",
    "is_pro": False,
    "daily_count": 0,
    "daily_date": "",           # fecha (YYYY-MM-DD) del contador actual
    "sharpen": False,           # aplica un filtro de nitidez tras descargar
    "youtube_cookies_file": "", # ruta a un cookies.txt exportado (para YouTube)
}


def _ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    Path(DEFAULTS["download_dir"]).mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    _ensure_dirs()
    if not CONFIG_FILE.exists():
        save_config(DEFAULTS)
        return dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save_config(cfg: dict) -> None:
    _ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def load_history() -> list:
    _ensure_dirs()
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_history(items: list) -> None:
    _ensure_dirs()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(items[-200:], f, indent=2, ensure_ascii=False)
