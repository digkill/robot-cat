#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Глаза как на референсе: два полых круга (кольца) с голубым свечением на чёрном фоне.
Без зрачков, только контур. Моргание — кольцо плавно сжимается.
Дополнительно: проигрывание звука при старте, снимок камерой каждые 5 секунд.
Запуск: sudo python3 robot_eyes.py
Выход: Ctrl+C
"""

import re
import time
import math
import random
import subprocess
import os
import shutil
import threading
from datetime import datetime
from gc9a01 import GC9A01, WIDTH, HEIGHT

try:
    from config import DISPLAY_BACKLIGHT_PIN
except ImportError:
    DISPLAY_BACKLIGHT_PIN = None

# --- Настройки звука и камеры ---
SOUND_FILES = [
    "/usr/share/sounds/alsa/Front_Center.wav",
    "/usr/share/sounds/alsa/Front_Left.wav",
    "/usr/share/sounds/alsa/Front_Right.wav",
    "/usr/share/sounds/alsa/Noise.wav",
]
SOUND_DEVICE = None  # None=авто, или "default", "plughw:0,0", "plughw:1,0" и т.д.
SNAPSHOT_INTERVAL = 5  # секунд между снимками
SNAPSHOT_DIR = "/home/mini/gc9a01_rpi/snapshots"  # папка для снимков

# Камера: rpicam-still (subprocess) — надёжно для CSI; picamera2 / OpenCV — альтернативы
CAMERA_BACKEND = "rpicam"  # "rpicam" | "picamera2" | "opencv"
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
try:
    from picamera2 import Picamera2
    HAS_PICAMERA2 = True
except ImportError:
    HAS_PICAMERA2 = False

# Центр экрана (круглый дисплей 240x240)
CX, CY = 120, 120

# Цвета (RGB565) — как на картинке: светящийся голубой контур, глубокий чёрный фон
def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

COLOR_BG = rgb(5, 5, 8)               # глубокий чёрный, чуть глянцевый
COLOR_GLOW = rgb(100, 200, 255)       # яркий голубой/cyan — свечение кольца


def fill_circle(disp, cx, cy, radius, color):
    """Залитый круг (radius — целое)."""
    if radius <= 0:
        return
    for dy in range(-radius, radius + 1):
        y = cy + dy
        if y < 0 or y >= HEIGHT:
            continue
        t = dy / radius
        if t * t > 1:
            continue
        half = radius * math.sqrt(1 - t * t)
        x0 = max(0, int(cx - half))
        x1 = min(WIDTH - 1, int(cx + half))
        if x1 >= x0:
            disp.fill_rect(x0, y, x1 - x0 + 1, 1, color)


def draw_eye_ring(disp, cx, cy, radius, thickness, open_ratio):
    """
    Один глаз — полое кольцо (контур круга). Центр тёмный, светится только обводка.
    При моргании кольцо сжимается (radius и thickness умножаются на open_ratio).
    """
    if open_ratio <= 0:
        return
    r_outer = max(1, int(radius * open_ratio))
    r_inner = max(0, r_outer - max(1, int(thickness * open_ratio)))
    # Сначала заливаем внешний круг цветом свечения
    fill_circle(disp, cx, cy, r_outer, COLOR_GLOW)
    # Внутренний круг — фон (получается кольцо)
    if r_inner > 0:
        fill_circle(disp, cx, cy, r_inner, COLOR_BG)


def draw_face(disp, blink_ratio):
    """Два глаза-кольца, симметрично. Без зрачков."""
    disp.fill(COLOR_BG)
    eye_radius = 32
    ring_thickness = 5
    eye_cx_left = CX - 40
    eye_cx_right = CX + 40
    eye_cy = CY
    draw_eye_ring(disp, eye_cx_left, eye_cy, eye_radius, ring_thickness, blink_ratio)
    draw_eye_ring(disp, eye_cx_right, eye_cy, eye_radius, ring_thickness, blink_ratio)


def ease_smoothstep(x):
    """Плавная кривая 0..1: медленно в начале и в конце (ease-in-out)."""
    x = max(0, min(1, x))
    return x * x * (3 - 2 * x)


def ease_blink(t):
    """t 0..1: плавное закрытие и открытие без рывков."""
    if t < 0.5:
        # закрываем: 1 -> 0 с плавным замедлением в конце
        return 1.0 - ease_smoothstep(t * 2)
    # открываем: 0 -> 1 с плавным разгоном в начале
    return ease_smoothstep((t - 0.5) * 2)


def _get_playback_devices():
    """Парсит aplay -l, возвращает список (card_num, name) для PLAYBACK устройств."""
    devices = []
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        for line in result.stdout.splitlines():
            m = re.search(r"card\s+(\d+):\s+([^,]+)", line)
            if m:
                card_num, card_name = int(m.group(1)), m.group(2).strip()
                devices.append((card_num, card_name))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return devices


def get_audio_device():
    """Возвращает устройство для aplay: SOUND_DEVICE или авто-поиск."""
    if SOUND_DEVICE:
        return SOUND_DEVICE
    devices = _get_playback_devices()
    for card, name in devices:
        if "wm8960" in name.lower() or "seeed" in name.lower() or "soundcard" in name.lower():
            return f"plughw:{card},0"
    if devices:
        return f"plughw:{devices[0][0]},0"
    return "default"


def play_sound(wav_path=None, device=None):
    """Воспроизводит WAV-файл в фоне (через aplay). При sudo пробует запуск от пользователя."""
    wav = wav_path
    if not wav or not os.path.isfile(wav):
        for p in SOUND_FILES:
            if os.path.isfile(p):
                wav = p
                break
    if not wav or not os.path.isfile(wav):
        print("[Audio] WAV не найден. Проверьте SOUND_FILES или укажите путь.")
        return False
    dev = device or get_audio_device()
    cmd = ["aplay", "-q", "-D", dev, wav]

    def _run(cmd_list):
        return subprocess.Popen(
            cmd_list,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    proc = None
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and os.geteuid() == 0:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        try:
            import pwd
            run_dir = f"/run/user/{pwd.getpwnam(sudo_user).pw_uid}"
            if os.path.isdir(run_dir):
                env["XDG_RUNTIME_DIR"] = run_dir
        except (ImportError, KeyError, OSError):
            pass
        try:
            proc = subprocess.Popen(
                ["sudo", "-u", sudo_user, "aplay", "-q", "-D", dev, wav],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
            )
        except Exception:
            proc = None
    if proc is None:
        try:
            proc = _run(cmd)
        except FileNotFoundError:
            print("[Audio] aplay не найден")
            return False

    def _check_result(p):
        p.wait(timeout=5)
        if p.returncode != 0 and p.stderr:
            err = p.stderr.read().decode(errors="ignore").strip()
            if err:
                print("[Audio] Ошибка aplay:", err[:150])

    threading.Thread(target=lambda: _check_result(proc), daemon=True).start()
    print("[Audio] Воспроизведение:", wav, "→", dev)
    return True


def _check_rpicam_available():
    """Проверяет наличие rpicam-still или libcamera-still."""
    for cmd in ["rpicam-still", "libcamera-still"]:
        if shutil.which(cmd):
            return cmd
    return None


def camera_snapshot_loop(stop_event):
    """Поток: снимок камерой каждые SNAPSHOT_INTERVAL секунд."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    cam = None
    use_opencv = False
    use_rpicam = False
    rpicam_cmd = None

    # 1) rpicam-still (subprocess) — надёжно для CSI, работает как rpicam-hello
    if CAMERA_BACKEND == "rpicam":
        rpicam_cmd = _check_rpicam_available()
        if rpicam_cmd:
            use_rpicam = True
            print("[Camera] rpicam-still (CSI), снимки каждые", SNAPSHOT_INTERVAL, "сек в", SNAPSHOT_DIR)

    # 2) picamera2 (Python)
    if not use_rpicam and CAMERA_BACKEND == "picamera2" and HAS_PICAMERA2:
        try:
            cam = Picamera2()
            cam.configure(cam.create_still_configuration())
            cam.start()
            print("[Camera] Picamera2 (CSI), снимки каждые", SNAPSHOT_INTERVAL, "сек в", SNAPSHOT_DIR)
        except Exception as e:
            print("[Camera] Picamera2 ошибка:", e)
            cam = None

    # 3) OpenCV (USB)
    if cam is None and not use_rpicam and CAMERA_BACKEND == "opencv" and HAS_OPENCV:
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            cam.release()
            cam = None
        else:
            cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            use_opencv = True
            print("[Camera] OpenCV (USB), снимки каждые", SNAPSHOT_INTERVAL, "сек в", SNAPSHOT_DIR)

    # Fallback: rpicam если выбран другой бэкенд но он не сработал
    if cam is None and not use_rpicam and not use_opencv:
        rpicam_cmd = _check_rpicam_available()
        if rpicam_cmd:
            use_rpicam = True
            print("[Camera] rpicam-still (fallback), снимки каждые", SNAPSHOT_INTERVAL, "сек в", SNAPSHOT_DIR)
        elif HAS_PICAMERA2:
            try:
                cam = Picamera2()
                cam.configure(cam.create_still_configuration())
                cam.start()
                print("[Camera] Picamera2 (fallback), снимки каждые", SNAPSHOT_INTERVAL, "сек в", SNAPSHOT_DIR)
            except Exception as e:
                print("[Camera] Picamera2 fallback ошибка:", e)
                cam = None
        if cam is None and HAS_OPENCV:
            cam = cv2.VideoCapture(0)
            if cam.isOpened():
                cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                use_opencv = True
                print("[Camera] OpenCV (fallback), снимки каждые", SNAPSHOT_INTERVAL, "сек в", SNAPSHOT_DIR)
            else:
                cam.release()
                cam = None

    if not use_rpicam and cam is None:
        print("[Camera] Камера недоступна. Установите: sudo apt install rpicam-apps")
        return

    try:
        while not stop_event.is_set():
            stop_event.wait(SNAPSHOT_INTERVAL)
            if stop_event.is_set():
                break
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(SNAPSHOT_DIR, f"snapshot_{ts}.jpg")
                if use_rpicam and rpicam_cmd:
                    # -n = без превью, -o = выход
                    result = subprocess.run(
                        [rpicam_cmd, "-n", "-o", path],
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and os.path.isfile(path):
                        print("[Camera] Снимок:", path)
                    else:
                        err = result.stderr.decode(errors="ignore") if result.stderr else "unknown"
                        print("[Camera] Ошибка rpicam:", err[:200])
                elif use_opencv and cam is not None:
                    ret, frame = cam.read()
                    if ret:
                        cv2.imwrite(path, frame)
                        print("[Camera] Снимок:", path)
                    else:
                        print("[Camera] Ошибка чтения кадра")
                elif cam is not None:
                    cam.capture_file(path)
                    print("[Camera] Снимок:", path)
            except Exception as e:
                print("[Camera] Ошибка снимка:", e)
    finally:
        if use_opencv and cam is not None:
            cam.release()
        elif cam is not None:
            try:
                cam.stop()
            except Exception:
                pass


def run_eyes(disp):
    """Цикл: глаза-кольца, только плавное моргание (без взгляда по сторонам)."""
    # Плавное появление: кольца «разгораются»
    for i in range(20):
        t = ease_smoothstep(i / 19)
        draw_face(disp, t)
        time.sleep(0.035)
    blink_ratio = 1.0
    # Моргание в ~10 раз реже: первое через 50–100 сек, дальше каждые 50–120 сек
    next_blink = time.monotonic() + random.uniform(50.0, 100.0)
    while True:
        now = time.monotonic()
        if now >= next_blink:
            # Очень плавно: много кадров, радиус меняется ~на 1 пиксель за кадр (нет дёрганья)
            frames = 70
            frame_time = 0.014
            for i in range(frames + 1):
                t = i / frames
                blink_ratio = ease_blink(t)
                draw_face(disp, blink_ratio)
                time.sleep(frame_time)
            blink_ratio = 1.0
            next_blink = now + random.uniform(50.0, 120.0)
            if random.random() < 0.1:  # очень редко — двойное моргание
                time.sleep(0.15)
                for i in range(frames + 1):
                    t = i / frames
                    blink_ratio = ease_blink(t)
                    draw_face(disp, blink_ratio)
                    time.sleep(frame_time)
                blink_ratio = 1.0
            continue
        # В простое не перерисовываем — без мигания
        time.sleep(0.1)


def main():
    disp = GC9A01(dc=24, rst=25, cs=8, backlight=DISPLAY_BACKLIGHT_PIN)
    if DISPLAY_BACKLIGHT_PIN is not None:
        disp.backlight(True)

    # Звук при старте (в фоне)
    dev = get_audio_device()
    print("[Audio] Устройство:", dev)
    threading.Thread(target=play_sound, daemon=True).start()

    # Поток снимков камеры
    stop_camera = threading.Event()
    cam_thread = threading.Thread(target=camera_snapshot_loop, args=(stop_camera,), daemon=True)
    cam_thread.start()

    try:
        print("Глаза (кольца). Выход: Ctrl+C")
        run_eyes(disp)
    except KeyboardInterrupt:
        print("\nВыход.")
    finally:
        stop_camera.set()
        disp.close()


if __name__ == "__main__":
    main()
