#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест детекции лица. Запуск: python3 test_detection.py
Показывает кадр с камеры и рисует прямоугольники вокруг найденных лиц.
Выход: q или Ctrl+C."""

import cv2
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config import CAMERA_DETECTION
except ImportError:
    CAMERA_DETECTION = "opencv"

try:
    from picamera2 import Picamera2
    HAS_PICAM = True
except ImportError:
    HAS_PICAM = False


def main():
    cascade_name = "haarcascade_frontalface_default.xml"
    cascade_path = None
    for p in [
        Path(cv2.data.haarcascades) / cascade_name if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades") else None,
        Path("/usr/share/opencv4/haarcascades") / cascade_name,
        Path("/usr/share/opencv/haarcascades") / cascade_name,
        Path(__file__).parent / "data" / cascade_name,
    ]:
        if p and p.exists():
            cascade_path = p
            break
    if not cascade_path:
        print("Ошибка: haarcascade_frontalface_default.xml не найден")
        return 1

    face_cascade = cv2.CascadeClassifier(str(cascade_path))
    if face_cascade.empty():
        print("Ошибка: не удалось загрузить cascade")
        return 1
    print(f"Cascade: {cascade_path}")

    cam = None
    use_picam = False
    if CAMERA_DETECTION == "opencv":
        cam = cv2.VideoCapture(0)
        if cam.isOpened():
            cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        else:
            cam = None
    if cam is None and HAS_PICAM:
        try:
            cam = Picamera2()
            cam.configure(cam.create_video_configuration(main={"size": (640, 480), "format": "RGB888"}))
            cam.start()
            use_picam = True
        except Exception as e:
            print("Picamera2:", e)
            cam = None

    if cam is None:
        print("Камера недоступна")
        return 1
    print(f"Камера: {'picamera2' if use_picam else 'opencv'}")

    print("Смотрите в камеру. Выход: q")
    while True:
        if use_picam:
            frame = cam.capture_array()
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            display = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            ret, frame = cam.read()
            if not ret:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            display = frame.copy()

        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=4, minSize=(40, 40))
        for (x, y, w, h) in faces:
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(display, "FACE", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.putText(display, f"Faces: {len(faces)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Face Detection Test", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    if use_picam:
        cam.stop()
        cam.close()
    else:
        cam.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
