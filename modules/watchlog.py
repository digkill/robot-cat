# -*- coding: utf-8 -*-
"""Логирование состояния и действий робота (файл + консоль)."""

import sys
import threading
from datetime import datetime
from pathlib import Path

from config import BASE_DIR

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "robot.log"
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3

_lock = threading.Lock()
_state = "idle"


def _ensure_log_dir():
    LOG_DIR.mkdir(exist_ok=True)


def _console(msg: str):
    """Вывод в консоль с немедленным сбросом буфера."""
    print(msg, end="", flush=True)


def set_state(state: str):
    """Установить текущее состояние."""
    global _state
    with _lock:
        _state = state
        _ensure_log_dir()
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] STATE: {state}\n"
        _console(line)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def get_state() -> str:
    with _lock:
        return _state


def log(action: str, detail: str = ""):
    """Записать действие в лог и консоль (всегда)."""
    _ensure_log_dir()
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {action}"
    if detail:
        line += f" | {detail}"
    line += "\n"
    _console(line)
    try:
        with _lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            _rotate_log()
    except Exception:
        pass


def _rotate_log():
    for i in range(LOG_BACKUP_COUNT - 1, 0, -1):
        old = LOG_FILE.with_suffix(f".log.{i}")
        new = LOG_FILE.with_suffix(f".log.{i + 1}")
        if old.exists():
            old.rename(new)
    if LOG_FILE.exists():
        LOG_FILE.rename(LOG_FILE.with_suffix(".log.1"))


def read_tail(lines: int = 100) -> str:
    """Прочитать последние строки лога."""
    if not LOG_FILE.exists():
        return ""
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception:
        return ""
