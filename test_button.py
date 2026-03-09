#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест кнопки — проверка GPIO 23. Запуск: sudo python3 test_button.py"""

import time
try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO не установлен")
    exit(1)

PIN = 23
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Тест кнопки на GPIO 23 (pin 16). Нажмите кнопку...")
print("Idle (не нажата): HIGH = 1. Нажата: LOW = 0")
last = GPIO.input(PIN)
try:
    while True:
        state = GPIO.input(PIN)
        if state != last:
            print(f"  [{time.strftime('%H:%M:%S')}] State: {state} {'<- НАЖАТА' if state == 0 else ''}")
            last = state
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nВыход.")
GPIO.cleanup()
