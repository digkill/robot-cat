#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест дисплея GC9A01 на Raspberry Pi Zero 2 W.
Выводит тестовые данные: заливки, фигуры, текст (если установлен Pillow).
Воспроизводит тестовый звук через WM8960-Audio-HAT.
Запуск: sudo python3 test_display.py
"""

import time
import sys
import subprocess
import os
from gc9a01 import GC9A01, WIDTH, HEIGHT

try:
    from config import DISPLAY_BACKLIGHT_PIN
except ImportError:
    DISPLAY_BACKLIGHT_PIN = None

# Тестовые WAV-файлы (проверяются по порядку)
TEST_WAV_FILES = [
    "/usr/share/sounds/alsa/Front_Center.wav",
    "/usr/share/sounds/alsa/Front_Left.wav",
    "/usr/share/sounds/alsa/Front_Right.wav",
]

# Опционально: вывод текста через Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_wm8960_device():
    """Находит устройство WM8960 в списке ALSA. Возвращает 'hw:X,0' или None."""
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if "wm8960" in line.lower() or "wm8960-soundcard" in line.lower():
                # Формат: "card X: wm8960soundcard ..."
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "card" and i + 1 < len(parts):
                        card = parts[i + 1].rstrip(":")
                        return f"plughw:{card},0"
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def play_test_sound(device=None, wav_path=None):
    """Воспроизводит тестовый WAV через WM8960-Audio-HAT (или default)."""
    wav = wav_path
    if not wav:
        for p in TEST_WAV_FILES:
            if os.path.isfile(p):
                wav = p
                break
    if not wav:
        print("  [Audio] Тестовый WAV не найден, пропуск звука")
        return False
    dev = device or get_wm8960_device() or "default"
    try:
        cmd = ["aplay", "-q", "-D", dev, wav]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc
    except FileNotFoundError:
        print("  [Audio] aplay не найден, пропуск звука")
        return False


def draw_circle(d, cx, cy, r, color):
    """Окружность (приближение по пикселям)."""
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            if x * x + y * y <= r * r and x * x + y * y >= (r - 1) * (r - 1):
                px, py = cx + x, cy + y
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    d.pixel(px, py, color)


def run_test(disp):
    """Последовательность тестовых кадров."""
    rgb = disp.color_rgb

    # 1) Синяя заливка
    disp.fill(rgb(0, 0, 200))
    time.sleep(1.5)

    # 2) Прямоугольники
    disp.fill(rgb(20, 20, 20))
    disp.fill_rect(20, 20, 80, 60, rgb(255, 0, 0))
    disp.fill_rect(140, 20, 80, 60, rgb(0, 255, 0))
    disp.fill_rect(20, 160, 80, 60, rgb(0, 0, 255))
    disp.fill_rect(140, 160, 80, 60, rgb(255, 255, 0))
    disp.fill_rect(70, 90, 100, 60, rgb(200, 100, 255))
    time.sleep(2)

    # 3) Круг в центре (дисплей круглый — 120, 120)
    disp.fill(rgb(0, 50, 80))
    draw_circle(disp, 120, 120, 80, rgb(255, 200, 0))
    draw_circle(disp, 120, 120, 40, rgb(0, 255, 200))
    time.sleep(2)

    # 4) Текст и тестовые данные (если есть Pillow) + звук через WM8960
    dev = get_wm8960_device()
    if dev:
        print(f"  [Audio] WM8960: {dev}")
    else:
        print("  [Audio] WM8960 не найден, пробуем default")
    audio_proc = play_test_sound(device=dev)
    if audio_proc:
        print("  [Audio] Воспроизведение тестового звука...")

    if HAS_PIL:
        img = Image.new("RGB", (WIDTH, HEIGHT), (10, 10, 30))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except OSError:
            font = ImageFont.load_default()
        draw.text((20, 30), "GC9A01 Test", fill=(255, 255, 255), font=font)
        draw.text((20, 70), "Raspberry Pi", fill=(100, 255, 100), font=font)
        draw.text((20, 110), "240 x 240 px", fill=(255, 200, 100), font=font)
        draw.text((20, 150), "SPI OK", fill=(100, 200, 255), font=font)
        draw.text((20, 190), "WM8960 Audio", fill=(255, 150, 100), font=font)
        # Вывод изображения на дисплей (RGB -> RGB565, чанками не больше 4096 байт)
        pix = img.load()
        for y in range(0, HEIGHT, 20):
            buf = []
            for yy in range(y, min(y + 20, HEIGHT)):
                for x in range(WIDTH):
                    r, g, b = pix[x, yy]
                    c = rgb(r, g, b)
                    buf.append((c >> 8) & 0xFF)
                    buf.append(c & 0xFF)
            disp.set_window(0, y, WIDTH - 1, min(y + 20, HEIGHT) - 1)
            disp._start_ram_write()
            chunk_size = 4096
            for i in range(0, len(buf), chunk_size):
                disp._write_pixels(buf[i : i + chunk_size])
            disp._end_ram_write()
        time.sleep(3)
    else:
        # Без Pillow — просто надпись из прямоугольников "OK"
        disp.fill(rgb(30, 30, 50))
        disp.fill_rect(50, 100, 120, 20, rgb(255, 255, 255))
        disp.fill_rect(50, 120, 20, 40, rgb(255, 255, 255))
        disp.fill_rect(150, 120, 20, 40, rgb(255, 255, 255))
        time.sleep(2)

    # 5) Белый экран
    disp.fill(rgb(255, 255, 255))
    time.sleep(1)
    # Чёрный
    disp.fill(rgb(0, 0, 0))
    time.sleep(0.5)


def main():
    # Пины по умолчанию для Raspberry Pi Zero 2 W
    # DC=24, RST=25, CS=8 (SPI CE0 -> /dev/spidev0.0), подсветка GPIO 18
    disp = GC9A01(dc=24, rst=25, cs=8, backlight=DISPLAY_BACKLIGHT_PIN)
    if DISPLAY_BACKLIGHT_PIN is not None:
        disp.backlight(True)
    try:
        print("Тест дисплея GC9A01. Выход: Ctrl+C")
        run_test(disp)
        print("Тест завершён.")
    except KeyboardInterrupt:
        print("\nПрервано.")
    finally:
        disp.close()


if __name__ == "__main__":
    main()
