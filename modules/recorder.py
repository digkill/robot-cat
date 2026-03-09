# -*- coding: utf-8 -*-
"""Запись видео и серия снимков при движении."""

import cv2
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

from config import RECORDINGS_DIR, SNAPSHOTS_DIR


def _log(action: str, detail: str):
    try:
        from modules.watchlog import log
        log(action, detail)
    except Exception:
        pass


def save_detection_snapshot(frame, is_rgb: bool = False, prefix: str = "motion") -> Path | None:
    """Сохранить кадр детектора как один JPEG-снимок."""
    if frame is None:
        return None
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SNAPSHOTS_DIR / f"{prefix}_{ts}.jpg"
    try:
        save_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) if is_rgb else frame
        if cv2.imwrite(str(path), save_frame):
            _log("recorder", f"снимок сохранен: {path.name}")
            return path
    except Exception as e:
        _log("recorder", f"снимок ошибка: {e}")
    return None


def record_audio(duration_sec: int = 10, output_path: str = None) -> Path | None:
    """Записывает звук с микрофона через arecord."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_path or str(RECORDINGS_DIR / f"audio_{ts}.wav")

    if not shutil.which("arecord"):
        _log("recorder", "arecord не найден")
        return None

    try:
        _log("recorder", f"запись аудио {duration_sec}с -> {output_path}")
        subprocess.run(
            ["arecord", "-D", "default", "-d", str(duration_sec), "-f", "cd", output_path],
            capture_output=True,
            timeout=duration_sec + 5,
        )
        if Path(output_path).exists():
            _log("recorder", f"аудио сохранено {Path(output_path).stat().st_size} байт")
            return Path(output_path)
    except Exception as e:
        _log("recorder", f"ошибка записи звука: {e}")
    return None
