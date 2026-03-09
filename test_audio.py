#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка звука. Запуск: python3 test_audio.py (или sudo python3 test_audio.py)"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("1. Список устройств (aplay -l):")
    r = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5)
    print(r.stdout or r.stderr or "(пусто)")
    print()

    print("2. Устройство для TTS:")
    from modules.tts import _get_audio_device
    dev = _get_audio_device()
    print(f"   {dev}")
    print()

    print("3. Тест aplay (тестовый WAV):")
    wav = "/usr/share/sounds/alsa/Front_Center.wav"
    if Path(wav).exists():
        r = subprocess.run(["aplay", "-q", "-D", dev, wav], capture_output=True, timeout=5)
        print("   OK" if r.returncode == 0 else f"   Ошибка: {r.stderr.decode()[:100]}")
    else:
        print("   Файл не найден")
    print()

    print("4. Тест espeak:")
    r = subprocess.run(
        ["espeak", "-v", "ru", "-s", "120", "тест"],
        capture_output=True,
        timeout=15,
    )
    print("   OK" if r.returncode == 0 else f"   Ошибка: {r.stderr.decode()[:100]}")
    print()

    print("5. Громкость (amixer -c 0):")
    r = subprocess.run(["amixer", "-c", "0", "sget", "Headphone"], capture_output=True, text=True, timeout=2)
    for line in (r.stdout or "").splitlines()[:3]:
        print(f"   {line}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
