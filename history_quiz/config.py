from __future__ import annotations
from pathlib import Path
import os, sys

APP = "history_quiz"
ORG = "ForbesComputing"  # purely a folder name on Windows


def user_data_root() -> Path:
    """Per-user, writable, non-OneDrive default location for app data."""
    if os.name == "nt":  # Windows
        base = os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / ORG / APP
    elif sys.platform == "darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / APP
    else:  # Linux/other
        base = os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        return Path(base) / APP

# Allow overrides via env vars, but use safe defaults
DATA_ROOT = Path(os.getenv("HQ_DATA_ROOT", user_data_root()))
MAIN_DB_PATH = Path(os.getenv("MAIN_DB_PATH", DATA_ROOT / "main.db"))
TOPICS_DIR = Path(os.getenv("TOPICS_DIR", DATA_ROOT / "topics"))

# Ensure folders exist at import time
DATA_ROOT.mkdir(parents=True, exist_ok=True)
TOPICS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_initialized() -> None:
    """Create main.db if missing (idempotent)."""
    if not MAIN_DB_PATH.exists():
        try:
            from .create_main_db import create_main_db
            MAIN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            create_main_db(str(MAIN_DB_PATH))
        except Exception:
            # safe to ignore; CLI ops may still create later
            pass