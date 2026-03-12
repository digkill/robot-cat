# -*- coding: utf-8 -*-
"""Запись видео и серия снимков при движении."""

import cv2
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

from config import RECORDINGS_DIR, SNAPSHOTS_DIR, SNAPSHOTS_UPLOAD_TO_S3


def _log(action: str, detail: str):
    try:
        from modules.watchlog import log
        log(action, detail)
    except Exception:
        pass


def _snapshot_s3_key(path: Path) -> str:
    ts = datetime.now().strftime("%Y/%m/%d/%H%M%S")
    return f"snapshots/{ts}_{path.name}"


def save_detection_snapshot(frame, is_rgb: bool = False, prefix: str = "motion", face_boxes=None) -> dict | None:
    """Сохранить кадр детектора, при необходимости загрузить в S3."""
    if frame is None:
        return None
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SNAPSHOTS_DIR / f"{prefix}_{ts}.jpg"
    try:
        save_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) if is_rgb else frame
        if face_boxes:
            for (x, y, w, h) in face_boxes:
                cv2.rectangle(save_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(save_frame, "FACE", (x, max(0, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        if cv2.imwrite(str(path), save_frame):
            _log("recorder", f"снимок сохранен: {path.name}")
            s3_key = None
            if SNAPSHOTS_UPLOAD_TO_S3:
                try:
                    from modules.s3_upload import upload_file
                    s3_key = upload_file(path, s3_key=_snapshot_s3_key(path))
                    if s3_key:
                        _log("s3", f"снимок загружен: {s3_key}")
                        try:
                            path.unlink()
                        except Exception:
                            pass
                except Exception as e:
                    _log("s3", f"снимок ошибка загрузки: {e}")
            return {"name": path.name, "local_path": str(path) if path.exists() else None, "s3_key": s3_key}
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
