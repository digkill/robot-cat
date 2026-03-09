#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест TTS. Запуск: python3 test_tts.py"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("Проверка TTS...")
    print("  espeak:", "OK" if shutil.which("espeak") else "НЕТ (sudo apt install espeak)")
    print("  espeak-ng:", "OK" if shutil.which("espeak-ng") else "НЕТ")
    print("  gTTS:", end=" ")
    try:
        import gtts
        print("OK")
    except ImportError:
        print("НЕТ (pip install gtts)")
    print("  mpg123:", "OK" if shutil.which("mpg123") else "НЕТ")
    print("  ffmpeg:", "OK" if shutil.which("ffmpeg") else "НЕТ")
    print()

    from modules.tts import speak
    print("Озвучивание: «Привет, это тест»")
    speak("Привет, это тест", blocking=True)
    print("Готово. Слышали звук?")
    return 0

if __name__ == "__main__":
    sys.exit(main())
