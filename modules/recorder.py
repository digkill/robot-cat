# -*- coding: utf-8 -*-
"""Запись видео и серия снимков при движении."""

import cv2
import subprocess
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime

from config import RECORDINGS_DIR, MOTION_RECORD_SEC, SNAPSHOTS_DIR


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


def capture_motion_snapshots(
    count: int = None,
    interval_sec: float = 1.0,
    output_dir: str | Path = None,
) -> list[Path]:
    """Сделать серию снимков через libcamera/rpicam."""
    count = max(1, int(count or MOTION_RECORD_SEC))
    interval_sec = max(0.1, float(interval_sec))
    output_dir = Path(output_dir or SNAPSHOTS_DIR)
    output_dir.mkdir(exist_ok=True)

    def _capture_one(output_path: Path) -> bool:
        cmd = None
        if shutil.which("rpicam-still"):
            cmd = [
                "rpicam-still",
                "-n",
                "-t", "1",
                "-o", str(output_path),
            ]
        elif shutil.which("libcamera-still"):
            cmd = [
                "libcamera-still",
                "-n",
                "-t", "1",
                "-o", str(output_path),
            ]
        elif shutil.which("ffmpeg"):
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "v4l2",
                "-i", "/dev/video0",
                "-frames:v", "1",
                str(output_path),
            ]
        if not cmd:
            _log("recorder", "rpicam-still, libcamera-still или ffmpeg не найден")
            return False
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                return True
            stderr = result.stderr.decode(errors="ignore").strip()
            if stderr:
                _log("recorder", f"снимок ошибка: {stderr[:160]}")
        except Exception as e:
            _log("recorder", f"снимок ошибка: {e}")
        return False

    paths: list[Path] = []
    for index in range(count):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = output_dir / f"motion_{ts}_{index + 1:02d}.jpg"
        if _capture_one(path):
            _log("recorder", f"снимок {index + 1}/{count}: {path.name}")
            paths.append(path)
        if index < count - 1:
            time.sleep(interval_sec)
    return paths


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
