# -*- coding: utf-8 -*-
"""Запись видео при движении."""

import subprocess
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime

from config import RECORDINGS_DIR, MOTION_RECORD_SEC


def _log(action: str, detail: str):
    try:
        from modules.watchlog import log
        log(action, detail)
    except Exception:
        pass


def record_video(duration_sec: int = None, output_path: str = None) -> Path | None:
    """Записывает видео через rpicam-vid или ffmpeg. Возвращает путь к файлу."""
    duration_sec = duration_sec or MOTION_RECORD_SEC
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_path or str(RECORDINGS_DIR / f"motion_{ts}.mp4")

    cmd = None
    if shutil.which("rpicam-vid"):
        cmd = [
            "rpicam-vid",
            "-n",
            "-t", str(duration_sec * 1000),
            "-o", output_path,
        ]
    elif shutil.which("libcamera-vid"):
        cmd = [
            "libcamera-vid",
            "-n",
            "-t", str(duration_sec * 1000),
            "-o", output_path,
        ]
    elif shutil.which("ffmpeg"):
        cmd = [
            "ffmpeg", "-y",
            "-f", "v4l2", "-i", "/dev/video0",
            "-t", str(duration_sec),
            "-c:v", "libx264", "-preset", "fast",
            output_path,
        ]

    if not cmd:
        _log("recorder", "rpicam-vid, libcamera-vid или ffmpeg не найден")
        return None

    try:
        _log("recorder", f"запись {duration_sec}с -> {output_path}")
        subprocess.run(cmd, capture_output=True, timeout=duration_sec + 60)
        if Path(output_path).exists():
            _log("recorder", f"сохранено {Path(output_path).stat().st_size} байт")
            return Path(output_path)
    except Exception as e:
        _log("recorder", f"ошибка: {e}")
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
