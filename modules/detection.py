# -*- coding: utf-8 -*-
"""Детекция лица и движения через камеру."""

import cv2
import threading
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from modules.recorder import save_detection_snapshot

try:
    from picamera2 import Picamera2
    HAS_PICAMERA2 = True
except ImportError:
    HAS_PICAMERA2 = False

try:
    from config import CAMERA_DETECTION, CAMERA_INDEX, CAMERA_ROTATE_180, SNAPSHOTS_DIR, SNAPSHOT_INTERVAL
except ImportError:
    CAMERA_DETECTION = "opencv"
    CAMERA_INDEX = 0
    CAMERA_ROTATE_180 = True
    SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"
    SNAPSHOT_INTERVAL = 0


class EventType(Enum):
    PERSON = "person"
    MOTION = "motion"
    NONE = "none"


@dataclass
class DetectionEvent:
    type: EventType
    frame: any
    timestamp: float
    confidence: float = 0.0
    face_boxes: any = None


class PersonMotionDetector:
    """Детекция человека (Haar/HOG) и движения (diff кадров)."""

    def __init__(
        self,
        person_callback=None,
        motion_callback=None,
        motion_threshold=25,
        motion_min_area=500,
        person_interval=5.0,
        motion_cooldown=2.0,
    ):
        self.person_callback = person_callback
        self.motion_callback = motion_callback
        self.motion_threshold = motion_threshold
        self.motion_min_area = motion_min_area
        self.person_interval = person_interval
        self.motion_cooldown = motion_cooldown
        self._last_person_time = 0
        self._last_motion_time = 0
        self._last_snapshot_time = 0
        self._prev_frame = None
        self._running = False
        self._thread = None
        self._cam = None
        self._use_picam = False

        # Haar cascade для лица
        cascade_name = "haarcascade_frontalface_default.xml"
        cascade_path = None
        if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            p = Path(cv2.data.haarcascades) / cascade_name
            if p.exists():
                cascade_path = p
        if cascade_path is None:
            for p in [
                Path("/usr/share/opencv4/haarcascades") / cascade_name,
                Path("/usr/share/opencv/haarcascades") / cascade_name,
                Path(__file__).parent.parent / "data" / cascade_name,
            ]:
                if p.exists():
                    cascade_path = p
                    break
        if cascade_path is None:
            local_path = Path(__file__).parent.parent / "data" / cascade_name
            local_path.parent.mkdir(exist_ok=True)
            try:
                import urllib.request
                urllib.request.urlretrieve(
                    "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/" + cascade_name,
                    str(local_path),
                )
                if local_path.exists():
                    cascade_path = local_path
            except Exception:
                pass
        self._face_cascade = None
        if cascade_path and cascade_path.exists():
            self._face_cascade = cv2.CascadeClassifier(str(cascade_path))
            if self._face_cascade.empty():
                self._face_cascade = None
    def _init_camera(self):
        if CAMERA_DETECTION == "opencv":
            self._cam = cv2.VideoCapture(CAMERA_INDEX)
            if self._cam.isOpened():
                self._cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self._cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self._use_picam = False
                return True
            if self._cam:
                self._cam.release()
                self._cam = None

        if HAS_PICAMERA2:
            try:
                self._cam = Picamera2()
                self._cam.configure(self._cam.create_video_configuration(
                    main={"size": (640, 480), "format": "RGB888"}
                ))
                self._cam.start()
                self._use_picam = True
                return True
            except Exception as e:
                if self._cam:
                    try:
                        self._cam.close()
                    except Exception:
                        pass
                    self._cam = None
                try:
                    from modules.watchlog import log
                    log("camera", f"ошибка Picamera2: {e}")
                except Exception:
                    pass
        return False

    def _read_frame(self):
        if self._use_picam and self._cam:
            frame = self._cam.capture_array()
        elif self._cam and self._cam.isOpened():
            ret, frame = self._cam.read()
            if not ret:
                return None
        else:
            return None
        if CAMERA_ROTATE_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        return frame

    def _detect_person(self, frame):
        """Детекция лица только через Haar cascade."""
        if len(frame.shape) == 3:
            if self._use_picam:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        # Для CSI-камеры контраст часто "плоский", equalizeHist заметно улучшает Haar.
        gray = cv2.equalizeHist(gray)
        if self._face_cascade is not None:
            faces = self._face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.03,
                minNeighbors=3,
                minSize=(32, 32),
            )
            if len(faces) > 0:
                return True, 0.8, faces
        return False, 0.0, []

    def _detect_motion(self, frame):
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self._prev_frame is None:
            self._prev_frame = gray
            return False
        diff = cv2.absdiff(self._prev_frame, gray)
        thresh = cv2.threshold(diff, self.motion_threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self._prev_frame = gray
        for c in contours:
            if cv2.contourArea(c) >= self.motion_min_area:
                return True
        return False

    def _run_loop(self):
        while self._running and self._cam:
            frame = self._read_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            now = time.time()
            person_found = False

            # Человек проверяем первым, чтобы лицо не терялось на фоне постоянного движения.
            if self.person_callback and (now - self._last_person_time) >= self.person_interval:
                found, conf, faces = self._detect_person(frame)
                if found:
                    accepted = self.person_callback(DetectionEvent(EventType.PERSON, frame.copy(), now, conf, face_boxes=faces))
                    if accepted is not False:
                        person_found = True
                        self._last_person_time = now
                        try:
                            from modules.watchlog import log
                            log("detection", f"человек обнаружен (conf={conf:.2f}) — вызов person_callback")
                        except Exception:
                            pass

            # Движение отдельно, но не в тот же кадр, где уже нашли человека.
            if (not person_found) and self.motion_callback and (now - self._last_motion_time) >= self.motion_cooldown:
                if self._detect_motion(frame):
                    accepted = self.motion_callback(DetectionEvent(EventType.MOTION, frame.copy(), now))
                    if accepted is not False:
                        self._last_motion_time = now
                        try:
                            from modules.watchlog import log
                            log("detection", "движение обнаружено — вызов motion_callback")
                        except Exception:
                            pass

            # Снимки
            if SNAPSHOT_INTERVAL > 0 and (now - self._last_snapshot_time) >= SNAPSHOT_INTERVAL:
                self._last_snapshot_time = now
                try:
                    result = save_detection_snapshot(frame, is_rgb=self._use_picam, prefix="snapshot")
                    if result:
                        from modules.watchlog import log
                        log("snapshot", result.get("s3_key") or result.get("name") or "ok")
                except Exception as e:
                    try:
                        from modules.watchlog import log
                        log("snapshot", f"ошибка: {e}")
                    except Exception:
                        pass

            time.sleep(0.5)

    def start(self):
        if not self._init_camera():
            raise RuntimeError("Камера недоступна")
        try:
            from modules.watchlog import log
            log("camera", f"инициализирована ({'picamera2' if self._use_picam else 'opencv'})")
            if self._face_cascade is None:
                log("detection", "Haar cascade не загружен — только HOG (тело)")
            else:
                log("detection", "Haar cascade загружен — детекция лица")
        except Exception:
            pass
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        try:
            from modules.watchlog import log
            log("detector", "цикл детекции запущен")
        except Exception:
            pass

    def pause(self):
        """Временно освободить камеру для записи."""
        try:
            from modules.watchlog import log
            log("detector", "пауза детекции")
        except Exception:
            pass
        self._running = False
        if self._thread:
            try:
                self._thread.join(timeout=2)
            except KeyboardInterrupt:
                try:
                    from modules.watchlog import log
                    log("detector", "join прерван Ctrl+C во время pause")
                except Exception:
                    pass
        if self._use_picam and self._cam:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception:
                pass
            self._cam = None
        elif self._cam and hasattr(self._cam, "release"):
            self._cam.release()
            self._cam = None

    def resume(self):
        """Возобновить детекцию после записи."""
        time.sleep(2)
        if self._init_camera():
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            try:
                from modules.watchlog import log
                log("detector", "детекция возобновлена")
            except Exception:
                pass

    def stop(self):
        try:
            from modules.watchlog import log
            log("detector", "остановка детекции")
        except Exception:
            pass
        self._running = False
        if self._thread:
            try:
                self._thread.join(timeout=2)
            except KeyboardInterrupt:
                try:
                    from modules.watchlog import log
                    log("detector", "join прерван Ctrl+C во время stop")
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
