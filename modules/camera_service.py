# -*- coding: utf-8 -*-
"""Общий сервис камеры: live stream, кадры для детекции, запись видео."""

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2

from config import (
    AUDIO_DEVICE,
    CAMERA_DETECTION,
    CAMERA_FPS,
    CAMERA_HEIGHT,
    CAMERA_INDEX,
    CAMERA_JPEG_QUALITY,
    CAMERA_ROTATE_180,
    CAMERA_WIDTH,
    RECORDINGS_DIR,
)

try:
    from picamera2 import Picamera2
    HAS_PICAMERA2 = True
except ImportError:
    HAS_PICAMERA2 = False


def _log(action: str, detail: str):
    try:
        from modules.watchlog import log
        log(action, detail)
    except Exception:
        pass


@dataclass
class RecordingResult:
    name: str
    local_path: str | None
    s3_key: str | None
    with_audio: bool


class CameraService:
    def __init__(self):
        self._cam = None
        self._use_picam = False
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._frame_ready = threading.Condition(self._lock)
        self._latest_frame = None
        self._latest_jpeg = None
        self._frame_seq = 0
        self._recording = None

    def _init_camera(self):
        if CAMERA_DETECTION == "opencv":
            self._cam = cv2.VideoCapture(CAMERA_INDEX)
            if self._cam.isOpened():
                self._cam.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self._cam.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                self._cam.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                self._use_picam = False
                return True
            if self._cam:
                self._cam.release()
                self._cam = None

        if HAS_PICAMERA2:
            try:
                self._cam = Picamera2()
                self._cam.configure(
                    self._cam.create_video_configuration(
                        main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"}
                    )
                )
                self._cam.start()
                self._use_picam = True
                return True
            except Exception as e:
                _log("camera", f"ошибка Picamera2: {e}")
                if self._cam:
                    try:
                        self._cam.close()
                    except Exception:
                        pass
                    self._cam = None
        return False

    def _read_frame(self):
        if self._use_picam and self._cam:
            frame = self._cam.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif self._cam and self._cam.isOpened():
            ok, frame = self._cam.read()
            if not ok:
                return None
        else:
            return None
        if CAMERA_ROTATE_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        return frame

    def _encode_jpeg(self, frame):
        ok, buf = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), max(30, min(100, CAMERA_JPEG_QUALITY))],
        )
        return buf.tobytes() if ok else None

    def _capture_loop(self):
        delay = 1.0 / max(1.0, CAMERA_FPS)
        while self._running:
            frame = self._read_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            jpeg = self._encode_jpeg(frame)
            with self._frame_ready:
                self._latest_frame = frame
                self._latest_jpeg = jpeg
                self._frame_seq += 1
                recording = self._recording
                self._frame_ready.notify_all()
            if recording:
                try:
                    recording["writer"].write(frame)
                    recording["frames"] += 1
                except Exception as e:
                    _log("recording", f"ошибка записи кадра: {e}")
            time.sleep(delay)

    def start(self):
        with self._lock:
            if self._running:
                return
            if not self._init_camera():
                raise RuntimeError("Камера недоступна")
            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="camera-service")
            self._thread.start()
        _log("camera", f"сервис камеры запущен ({'picamera2' if self._use_picam else 'opencv'})")

    def stop(self):
        with self._lock:
            self._running = False
            self._frame_ready.notify_all()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._recording:
            try:
                self.stop_recording()
            except Exception:
                pass
        if self._use_picam and self._cam:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception:
                pass
        elif self._cam and hasattr(self._cam, "release"):
            self._cam.release()
        self._cam = None
        self._latest_frame = None
        self._latest_jpeg = None

    def get_frame(self, wait_timeout: float = 1.0):
        with self._frame_ready:
            if self._latest_frame is None:
                self._frame_ready.wait(timeout=wait_timeout)
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def iter_jpeg(self):
        last_seq = -1
        while True:
            with self._frame_ready:
                if not self._running:
                    break
                if self._frame_seq == last_seq:
                    self._frame_ready.wait(timeout=1.0)
                    if self._frame_seq == last_seq:
                        continue
                last_seq = self._frame_seq
                jpeg = self._latest_jpeg
            if jpeg:
                yield jpeg

    def recording_status(self):
        with self._lock:
            if not self._recording:
                return {"recording": False}
            rec = self._recording
            return {
                "recording": True,
                "started_at": rec["started_at"],
                "video_name": Path(rec["final_path"]).name,
                "frames": rec["frames"],
                "with_audio": rec["audio_proc"] is not None,
            }

    def _audio_command(self, audio_path: Path):
        audio_device = AUDIO_DEVICE.strip()
        if shutil.which("pw-record"):
            cmd = ["pw-record"]
            if audio_device:
                cmd.extend(["--target", audio_device])
            cmd.extend([str(audio_path)])
            return cmd
        if shutil.which("arecord"):
            cmd = ["arecord"]
            if audio_device:
                cmd.extend(["-D", audio_device])
            cmd.extend(["-f", "cd", str(audio_path)])
            return cmd
        return None

    def start_recording(self):
        self.start()
        with self._lock:
            if self._recording:
                raise RuntimeError("Запись уже идёт")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_video_path = RECORDINGS_DIR / f"camera_{ts}_video.mp4"
            audio_path = RECORDINGS_DIR / f"camera_{ts}_audio.wav"
            final_path = RECORDINGS_DIR / f"camera_{ts}.mp4"
            writer = cv2.VideoWriter(
                str(raw_video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                max(5.0, CAMERA_FPS),
                (CAMERA_WIDTH, CAMERA_HEIGHT),
            )
            if not writer.isOpened():
                raise RuntimeError("Не удалось открыть видеозапись")
            audio_proc = None
            cmd = self._audio_command(audio_path)
            if cmd:
                try:
                    audio_proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as e:
                    _log("recording", f"аудио не стартовало: {e}")
                    audio_proc = None
            self._recording = {
                "writer": writer,
                "raw_video_path": raw_video_path,
                "audio_path": audio_path,
                "final_path": final_path,
                "audio_proc": audio_proc,
                "started_at": datetime.now().isoformat(),
                "frames": 0,
            }
        _log("recording", f"старт записи: {final_path.name}")
        return self.recording_status()

    def stop_recording(self):
        with self._lock:
            if not self._recording:
                raise RuntimeError("Запись не запущена")
            rec = self._recording
            self._recording = None

        rec["writer"].release()
        audio_proc = rec["audio_proc"]
        if audio_proc:
            try:
                audio_proc.terminate()
                audio_proc.wait(timeout=5)
            except Exception:
                try:
                    audio_proc.kill()
                except Exception:
                    pass

        raw_video_path = Path(rec["raw_video_path"])
        audio_path = Path(rec["audio_path"])
        final_path = Path(rec["final_path"])
        with_audio = False

        if audio_path.exists() and shutil.which("ffmpeg"):
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_video_path),
                "-i",
                str(audio_path),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(final_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=60, check=True)
                with_audio = True
            except Exception as e:
                _log("recording", f"ffmpeg не склеил аудио: {e}")

        if not final_path.exists():
            raw_video_path.replace(final_path)

        try:
            if raw_video_path.exists():
                raw_video_path.unlink()
        except Exception:
            pass
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception:
            pass

        s3_key = None
        try:
            from modules.s3_upload import upload_file
            s3_key = upload_file(final_path)
        except Exception as e:
            _log("s3", f"ошибка загрузки записи: {e}")

        _log("recording", f"запись сохранена: {final_path.name}")
        return RecordingResult(
            name=final_path.name,
            local_path=str(final_path) if final_path.exists() else None,
            s3_key=s3_key,
            with_audio=with_audio,
        )


_camera_service = CameraService()


def get_camera_service() -> CameraService:
    return _camera_service
